# 请不要改动这个文件，除非你知道自己在做什么！如果你不确定，请先在 model/__init__.py 里修改模型代码，确保 check 和 score 都通过后再运行 pack。改动这个文件可能导致评测服务器无法正确评分，甚至无法解压提交包。
from __future__ import annotations

import argparse
import ast
import hashlib
import importlib
import json
import shutil
import sys
import tempfile
import traceback
import zipfile
from pathlib import Path

import torch

from bench.scoring import compute_macro_f1, load_labels, save_metrics, write_confusion_png
from bench.transforms import load_image

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
NUM_CLASSES = 7
MAX_PARAMS = 50_000_000
MAX_WEIGHT_MB = 200
INPUT_SHAPE = (2, 3, 224, 224)
IMAGE_SUFFIXES = {".jpg", ".jpeg", ".png", ".bmp", ".webp"}

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
    print("SI100B Emotional Bench Kit")
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
        raise BenchError("找不到 model/__init__.py。请确认你在工具包根目录运行。")
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


def check_model_contract(model: torch.nn.Module) -> int:
    n_params = sum(param.numel() for param in model.parameters())
    if n_params > MAX_PARAMS:
        raise BenchError(f"参数量超过上限：{n_params:,} > {MAX_PARAMS:,}。请换小模型。")
    ok(f"参数量 {n_params:,} / {MAX_PARAMS:,}")
    model.eval()
    with torch.inference_mode():
        output = model(torch.randn(*INPUT_SHAPE))
    if tuple(output.shape) != (INPUT_SHAPE[0], NUM_CLASSES):
        raise BenchError(f"输出形状 {tuple(output.shape)}，应为 ({INPUT_SHAPE[0]}, {NUM_CLASSES})。请把分类头改成 7 类。")
    if torch.isnan(output).any():
        raise BenchError("前向输出包含 NaN。请检查模型结构。")
    ok(f"前向契约通过：{INPUT_SHAPE} -> {tuple(output.shape)}")
    return n_params


def strip_module_prefix(state: dict) -> dict:
    if state and all(str(key).startswith("module.") for key in state):
        warn("检测到 DataParallel/DDP 的 module. 前缀，已自动剥除。")
        return {key[len("module.") :]: value for key, value in state.items()}
    return state


def load_state(path: Path) -> dict:
    if not path.exists():
        raise BenchError(f"找不到权重文件：{path}")
    if path.suffix == ".safetensors":
        from safetensors.torch import load_file

        return load_file(str(path), device="cpu")
    if path.suffix in {".pth", ".pt", ".ckpt"}:
        obj = torch.load(path, map_location="cpu", weights_only=True)
        if isinstance(obj, dict):
            obj = obj.get("state_dict", obj.get("model", obj))
        if not isinstance(obj, dict):
            raise BenchError("权重文件不是 state_dict。请保存 model.state_dict()。")
        return strip_module_prefix(obj)
    raise BenchError(f"无法识别权重格式：{path.suffix}。支持 .pth/.pt/.ckpt/.safetensors。")


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
    check_model_contract(model)
    ok("check 完成。下一步可运行：python bench.py pack --weights 你的权重.pth")


def list_devset_images() -> list[Path]:
    return sorted(path for path in DEVSET_IMAGES.rglob("*") if path.suffix.lower() in IMAGE_SUFFIXES and path.is_file())


def command_score(args) -> dict | None:
    headline()
    if not DEVSET_LABELS.exists() or not list_devset_images():
        warn("当前工具包没有 devset 图片或 labels.csv，暂时不能本地评分。")
        print("   → 这不影响 check/pack。等待 TA 发布包含 devset 的新版工具包后再运行 score。")
        return None
    check_model_source()
    model = load_weights(build_model(), Path(args.weights))
    model.eval()
    labels = load_labels(DEVSET_LABELS)
    y_true: list[int] = []
    y_pred: list[int] = []
    with torch.inference_mode():
        for image_path in list_devset_images():
            key = image_path.relative_to(DEVSET_IMAGES).as_posix()
            label = labels.get(key, labels.get(image_path.name))
            if label is None:
                continue
            batch = load_image(image_path).unsqueeze(0)
            pred = int(model(batch).argmax(dim=1).item())
            y_true.append(int(label))
            y_pred.append(pred)
    if not y_true:
        raise BenchError("devset 图片和 labels.csv 没有匹配项。请联系 TA 更新工具包。")
    macro_f1, accuracy, confusion, per_class = compute_macro_f1(y_true, y_pred, NUM_CLASSES)
    write_confusion_png(ROOT / "local_confusion.png", confusion)
    payload = {"macro_f1": macro_f1, "accuracy": accuracy, "matched": len(y_true), "confusion": confusion, "per_class": per_class}
    save_metrics(ROOT / "local_metrics.json", payload)
    print(f"本地评分结果 (devset, {len(y_true)} 张，仅供参考)")
    print(f"  Macro-F1   {macro_f1 * 100:.1f}        Accuracy   {accuracy * 100:.1f}")
    print("  逐类 F1: " + " | ".join(f"{cls}:{item['f1']:.2f}" for cls, item in per_class.items()))
    print("  混淆矩阵已保存至 local_confusion.png，指标 JSON 已保存至 local_metrics.json")
    return payload


def export_safetensors(model: torch.nn.Module, out_path: Path) -> None:
    from safetensors.torch import save_model

    save_model(model, str(out_path))
    size_mb = out_path.stat().st_size / 1024 / 1024
    if size_mb > MAX_WEIGHT_MB:
        raise BenchError(f"model.safetensors 为 {size_mb:.1f} MB，超过 {MAX_WEIGHT_MB} MB 上限。")
    ok(f"model.safetensors 已生成 ({size_mb:.1f} MB)")


def command_pack(args) -> None:
    headline()
    check_model_source()
    model = build_model()
    check_model_contract(model)
    model = load_weights(model, Path(args.weights))
    score_payload = command_score(args)
    with tempfile.TemporaryDirectory() as tmp:
        tmp_dir = Path(tmp)
        model_py = tmp_dir / "model.py"
        weights = tmp_dir / "model.safetensors"
        shutil.copy2(MODEL_FILE, model_py)
        export_safetensors(model, weights)
        zip_path = ROOT / "submission.zip"
        with zipfile.ZipFile(zip_path, "w", zipfile.ZIP_DEFLATED) as zf:
            zf.write(model_py, "model.py")
            zf.write(weights, "model.safetensors")
    sha = hashlib.sha256(zip_path.read_bytes()).hexdigest()[:16]
    suffix = f"（本地参考 Macro-F1 {score_payload['macro_f1'] * 100:.1f}）" if score_payload else ""
    print(f"\n✅ submission.zip 已生成 {suffix}")
    print(f"   sha256 前 16 位：{sha}")
    print("   下一步：打开评测网站，先选择 dry-run 上传；通过后再正式提交。")


def main() -> None:
    parser = argparse.ArgumentParser(description="SI100B Emotional Bench Kit")
    sub = parser.add_subparsers(dest="command", required=True)
    check = sub.add_parser("check", help="检查模型契约，不需要权重")
    check.set_defaults(func=command_check)
    score = sub.add_parser("score", help="在 devset 上本地评分")
    score.add_argument("--weights", required=True)
    score.set_defaults(func=command_score)
    pack = sub.add_parser("pack", help="检查、评分并生成 submission.zip")
    pack.add_argument("--weights", required=True)
    pack.set_defaults(func=command_pack)
    args = parser.parse_args()
    try:
        args.func(args)
    except BenchError as exc:
        fail(str(exc))


if __name__ == "__main__":
    main()
