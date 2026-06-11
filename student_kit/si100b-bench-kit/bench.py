# 请不要改动这个文件，除非你知道自己在做什么！你唯一需要修改的是 model/ 目录。
from __future__ import annotations

import argparse
import ast
import hashlib
import importlib
import json
import sys
import traceback
from datetime import datetime, timezone
from pathlib import Path

import numpy as np
import torch

from bench.scoring import compute_macro_f1, load_labels, save_metrics, write_confusion_png
from bench.transforms import ALLOWED_CHANNELS, ALLOWED_INPUT_SIZES, load_image

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
if hasattr(sys.stderr, "reconfigure"):
    sys.stderr.reconfigure(encoding="utf-8", errors="replace")

ROOT = Path(__file__).resolve().parent
MODEL_DIR = ROOT / "model"
MODEL_FILE = MODEL_DIR / "__init__.py"
DEVSET_DIR = ROOT / "bench" / "devset"
DEVSET_IMAGES = DEVSET_DIR / "images"
DEVSET_LABELS = DEVSET_DIR / "labels.csv"
KIT_VERSION = "0.2.2-onnx"
NUM_CLASSES = 7
MAX_PARAMS = 50_000_000
MAX_MODEL_MB = 200
IMAGE_SUFFIXES = {".jpg", ".jpeg", ".png", ".bmp", ".webp"}
CLASS_ORDER = "angry,disgust,fear,happy,neutral,sad,surprise"

FORBIDDEN_IMPORTS = {
    "ctypes",
    "multiprocessing",
    "os",
    "pathlib",
    "requests",
    "shutil",
    "socket",
    "subprocess",
    "sys",
    "urllib",
}
FORBIDDEN_CALLS = {"__import__", "compile", "eval", "exec", "input", "open"}


class BenchError(Exception):
    pass


def headline() -> None:
    print("=" * 62)
    print("SI100B Emotional Bench Kit · ONNX")
    print("唯一允许修改的目录：model/")
    print("=" * 62)


def fail(message: str, verbose: bool = False) -> None:
    print(f"\n❌ {message}")
    print("   → 请按提示修改后重新运行同一条命令。")
    if verbose:
        traceback.print_exc()
    raise SystemExit(1)


def ok(message: str) -> None:
    print(f"✅ {message}")


def warn(message: str) -> None:
    print(f"⚠ {message}")


def node_line(node: ast.AST) -> str:
    return f"model/__init__.py 第 {getattr(node, 'lineno', '?')} 行"


def check_model_source() -> None:
    if not MODEL_FILE.exists():
        raise BenchError("找不到 model/__init__.py。请确认你在代码框架根目录运行。")
    source = MODEL_FILE.read_text(encoding="utf-8")
    try:
        tree = ast.parse(source)
    except SyntaxError as exc:
        raise BenchError(f"model/__init__.py 第 {exc.lineno} 行语法错误：{exc.msg}")

    has_build_model = False
    for node in ast.walk(tree):
        if isinstance(node, ast.FunctionDef) and node.name == "build_model":
            has_build_model = True
        elif isinstance(node, ast.Import):
            for alias in node.names:
                root = alias.name.split(".", 1)[0]
                if root in FORBIDDEN_IMPORTS:
                    raise BenchError(f"检测到禁止 import：{alias.name} ({node_line(node)})。请删除该 import。")
        elif isinstance(node, ast.ImportFrom):
            root = (node.module or "").split(".", 1)[0]
            if root in FORBIDDEN_IMPORTS:
                raise BenchError(f"检测到禁止 import：from {node.module} ({node_line(node)})。请删除该 import。")
        elif isinstance(node, ast.Call):
            if isinstance(node.func, ast.Name) and node.func.id in FORBIDDEN_CALLS:
                raise BenchError(f"禁止调用 {node.func.id}() ({node_line(node)})。模型文件里不要读写文件或执行代码。")
            for kw in node.keywords:
                if kw.arg == "pretrained" and isinstance(kw.value, ast.Constant) and kw.value.value is True:
                    raise BenchError(f"检测到 pretrained=True ({node_line(node)})。请改成 pretrained=False。")
                if kw.arg == "weights" and not (isinstance(kw.value, ast.Constant) and kw.value.value is None):
                    raise BenchError(f"检测到 weights=... 非 None ({node_line(node)})。请改成 weights=None。")
    if not has_build_model:
        raise BenchError("未找到 build_model()。请在 model/__init__.py 中定义 build_model()。")
    ok("model/__init__.py 静态检查通过")


def import_student_model():
    if str(ROOT) not in sys.path:
        sys.path.insert(0, str(ROOT))
    importlib.invalidate_caches()
    sys.modules.pop("model", None)
    try:
        return importlib.import_module("model")
    except Exception as exc:
        raise BenchError(f"导入 model/__init__.py 失败：{type(exc).__name__}: {exc}") from exc


def build_model() -> torch.nn.Module:
    module = import_student_model()
    try:
        model = module.build_model()
    except Exception as exc:
        raise BenchError(f"调用 build_model() 失败：{type(exc).__name__}: {exc}") from exc
    if not isinstance(model, torch.nn.Module):
        raise BenchError("build_model() 返回值不是 torch.nn.Module。请返回模型对象。")
    return model


def check_input_spec(input_size: int, channels: int) -> None:
    if input_size not in ALLOWED_INPUT_SIZES:
        raise BenchError(f"输入尺寸必须是 {ALLOWED_INPUT_SIZES} 之一。")
    if channels not in ALLOWED_CHANNELS:
        raise BenchError("输入通道只能是 1 或 3。")


def check_model_contract(model: torch.nn.Module, input_size: int, channels: int) -> int:
    check_input_spec(input_size, channels)
    n_params = sum(param.numel() for param in model.parameters())
    if n_params > MAX_PARAMS:
        raise BenchError(f"参数量超过上限：{n_params:,} > {MAX_PARAMS:,}。请换小模型。")
    ok(f"参数量 {n_params:,} / {MAX_PARAMS:,}")
    model.eval()
    with torch.inference_mode():
        output = model(torch.randn(2, channels, input_size, input_size))
    if tuple(output.shape) != (2, NUM_CLASSES):
        raise BenchError(f"输出形状 {tuple(output.shape)}，应为 (B, {NUM_CLASSES})。请把分类头改成 7 类。")
    if torch.isnan(output).any():
        raise BenchError("前向输出包含 NaN。请检查模型结构。")
    ok(f"前向契约通过：[B, {channels}, {input_size}, {input_size}] -> {tuple(output.shape)}")
    return n_params


def strip_module_prefix(state: dict) -> dict:
    if state and all(str(key).startswith("module.") for key in state):
        warn("检测到 DataParallel/DDP 的 module. 前缀，已自动剥除。")
        return {key[len("module.") :]: value for key, value in state.items()}
    return state


def load_state(path: Path) -> dict:
    if not path.exists():
        raise BenchError(f"找不到权重文件：{path}")
    if path.suffix in {".pth", ".pt", ".ckpt"}:
        obj = torch.load(path, map_location="cpu", weights_only=True)
        if isinstance(obj, dict):
            obj = obj.get("state_dict", obj.get("model", obj))
        if not isinstance(obj, dict):
            raise BenchError("权重文件不是 state_dict。请保存 model.state_dict()。")
        return strip_module_prefix(obj)
    raise BenchError(f"无法识别权重格式：{path.suffix}。支持 .pth/.pt/.ckpt。")


def load_weights(model: torch.nn.Module, path: Path) -> torch.nn.Module:
    state = load_state(path)
    try:
        model.load_state_dict(state, strict=True)
    except RuntimeError as exc:
        raise BenchError(f"权重与模型结构不匹配：{exc}") from exc
    ok("权重与模型结构严格匹配")
    return model


def command_check(args) -> None:
    headline()
    check_model_source()
    model = build_model()
    check_model_contract(model, args.input_size, args.channels)
    ok("check 完成。下一步可运行：python bench.py pack --weights 你的权重.pth")


def list_devset_images() -> list[Path]:
    return sorted(path for path in DEVSET_IMAGES.rglob("*") if path.suffix.lower() in IMAGE_SUFFIXES and path.is_file())


def run_onnx(model_path: Path, images: list[Path], input_size: int, channels: int) -> list[int]:
    import onnxruntime as ort

    session = ort.InferenceSession(str(model_path), providers=["CPUExecutionProvider"])
    input_info = session.get_inputs()[0]
    preds: list[int] = []
    batch_size = 64
    for index in range(0, len(images), batch_size):
        batch_paths = images[index : index + batch_size]
        batch = np.stack([load_image(path, input_size, channels) for path in batch_paths], axis=0).astype(np.float32)
        logits = session.run(None, {input_info.name: batch})[0]
        preds.extend(logits.argmax(axis=1).tolist())
    return preds


def score_onnx(model_path: Path, input_size: int, channels: int) -> dict | None:
    if not DEVSET_LABELS.exists() or not list_devset_images():
        warn("当前代码框架没有 devset 图片或 labels.csv，暂时不能本地评分。")
        print("   → 这不影响 check/pack。等待 TA 发布包含 devset 的新版代码框架后再运行 score。")
        return None
    labels = load_labels(DEVSET_LABELS)
    paths = []
    y_true = []
    for image_path in list_devset_images():
        key = image_path.relative_to(DEVSET_IMAGES).as_posix()
        label = labels.get(key, labels.get(image_path.name))
        if label is None:
            continue
        paths.append(image_path)
        y_true.append(int(label))
    if not y_true:
        raise BenchError("devset 图片和 labels.csv 没有匹配项。请联系 TA 更新代码框架。")
    y_pred = run_onnx(model_path, paths, input_size, channels)
    macro_f1, accuracy, confusion, per_class = compute_macro_f1(y_true, y_pred, NUM_CLASSES)
    write_confusion_png(ROOT / "local_confusion.png", confusion)
    payload = {"macro_f1": macro_f1, "accuracy": accuracy, "matched": len(y_true), "confusion": confusion, "per_class": per_class}
    save_metrics(ROOT / "local_metrics.json", payload)
    print(f"本地评分结果 (devset, {len(y_true)} 张，仅供参考)")
    print(f"  Macro-F1   {macro_f1 * 100:.1f}        Accuracy   {accuracy * 100:.1f}")
    print("  逐类 F1: " + " | ".join(f"{cls}:{item['f1']:.2f}" for cls, item in per_class.items()))
    print("  混淆矩阵已保存至 local_confusion.png，指标 JSON 已保存至 local_metrics.json")
    return payload


def command_score(args) -> dict | None:
    headline()
    check_input_spec(args.input_size, args.channels)
    model_path = Path(args.onnx)
    if not model_path.exists():
        raise BenchError(f"找不到 ONNX 文件：{model_path}")
    return score_onnx(model_path, args.input_size, args.channels)


def export_onnx(model: torch.nn.Module, output_path: Path, input_size: int, channels: int) -> None:
    import onnx

    dummy = torch.randn(2, channels, input_size, input_size)
    model.eval()
    torch.onnx.export(
        model,
        dummy,
        output_path,
        input_names=["input"],
        output_names=["logits"],
        dynamic_axes={"input": {0: "batch"}, "logits": {0: "batch"}},
        opset_version=18,
        do_constant_folding=True,
        external_data=False,
    )
    onnx_model = onnx.load(output_path, load_external_data=False)
    for tensor in onnx_model.graph.initializer:
        if tensor.external_data:
            raise BenchError("导出的 ONNX 使用了 external data，平台会拒收。请减小模型或检查导出设置。")
    onnx.helper.set_model_props(
        onnx_model,
        {
            "si100b_kit_version": KIT_VERSION,
            "input_size": str(input_size),
            "input_channels": str(channels),
            "packed_at": datetime.now(timezone.utc).isoformat(),
            "class_order": CLASS_ORDER,
        },
    )
    onnx.checker.check_model(onnx_model)
    onnx.save(onnx_model, output_path)
    size_mb = output_path.stat().st_size / 1024 / 1024
    if size_mb > MAX_MODEL_MB:
        raise BenchError(f"model.onnx 为 {size_mb:.1f} MB，超过 {MAX_MODEL_MB} MB 上限。")
    ok(f"model.onnx 已生成 ({size_mb:.1f} MB)")


def command_pack(args) -> None:
    headline()
    check_model_source()
    model = build_model()
    check_model_contract(model, args.input_size, args.channels)
    model = load_weights(model, Path(args.weights))
    onnx_path = ROOT / "model.onnx"
    export_onnx(model, onnx_path, args.input_size, args.channels)
    score_payload = score_onnx(onnx_path, args.input_size, args.channels)
    sha = hashlib.sha256(onnx_path.read_bytes()).hexdigest()[:16]
    suffix = f"（本地参考 Macro-F1 {score_payload['macro_f1'] * 100:.1f}）" if score_payload else ""
    print(f"\n✅ model.onnx 已生成 {suffix}")
    print(f"   sha256 前 16 位：{sha}")
    print("   下一步：打开评测网站，选择相同的输入尺寸和通道，直接上传 model.onnx。")


def add_input_args(parser: argparse.ArgumentParser) -> None:
    parser.add_argument("--input-size", type=int, default=112, choices=ALLOWED_INPUT_SIZES)
    parser.add_argument("--channels", type=int, default=3, choices=ALLOWED_CHANNELS)


def main() -> None:
    parser = argparse.ArgumentParser(description="SI100B Emotional Bench Kit")
    sub = parser.add_subparsers(dest="command", required=True)
    check = sub.add_parser("check", help="检查模型契约，不需要权重")
    add_input_args(check)
    check.set_defaults(func=command_check)
    score = sub.add_parser("score", help="在 devset 上本地评分")
    score.add_argument("--onnx", default="model.onnx")
    add_input_args(score)
    score.set_defaults(func=command_score)
    pack = sub.add_parser("pack", help="检查、评分并生成 model.onnx")
    pack.add_argument("--weights", required=True)
    add_input_args(pack)
    pack.set_defaults(func=command_pack)
    args = parser.parse_args()
    try:
        args.func(args)
    except BenchError as exc:
        fail(str(exc))


if __name__ == "__main__":
    main()
