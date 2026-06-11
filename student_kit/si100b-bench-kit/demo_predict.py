from __future__ import annotations

import argparse
from pathlib import Path

import numpy as np
import onnxruntime as ort
from PIL import Image, ImageDraw

from bench.transforms import ALLOWED_CHANNELS, ALLOWED_INPUT_SIZES, load_image


CLASS_NAMES = ["angry", "disgust", "fear", "happy", "neutral", "sad", "surprise"]
IMAGE_SUFFIXES = {".jpg", ".jpeg", ".png", ".bmp", ".webp"}


def list_images(image: str | None, images: str | None) -> list[Path]:
    paths: list[Path] = []
    if image:
        paths.append(Path(image))
    if images:
        root = Path(images)
        paths.extend(sorted(path for path in root.rglob("*") if path.suffix.lower() in IMAGE_SUFFIXES and path.is_file()))
    if not paths:
        raise SystemExit("请提供 --image 或 --images")
    return paths


def predict(session: ort.InferenceSession, path: Path, input_size: int, channels: int) -> tuple[int, float]:
    input_name = session.get_inputs()[0].name
    batch = load_image(path, input_size, channels)[None, ...].astype(np.float32)
    logits = session.run(None, {input_name: batch})[0][0]
    logits = logits - logits.max()
    prob = np.exp(logits) / np.exp(logits).sum()
    pred = int(prob.argmax())
    return pred, float(prob[pred])


def make_canvas(path: Path, text: str) -> Image.Image:
    image = Image.open(path).convert("RGB")
    image.thumbnail((640, 640))
    canvas = Image.new("RGB", (image.width, image.height + 42), (245, 245, 245))
    canvas.paste(image, (0, 42))
    draw = ImageDraw.Draw(canvas)
    draw.rectangle((0, 0, canvas.width, 42), fill=(20, 24, 28))
    draw.text((12, 12), text, fill=(255, 255, 255))
    return canvas


def show_with_cv(canvas: Image.Image, title: str) -> int:
    try:
        import cv2
    except Exception as exc:
        raise SystemExit("OpenCV 未安装。请运行：python -m pip install -r requirements-demo.txt -i https://pypi.tuna.tsinghua.edu.cn/simple") from exc
    array = cv2.cvtColor(np.asarray(canvas), cv2.COLOR_RGB2BGR)
    cv2.imshow(title, array)
    return cv2.waitKey(0) & 0xFF


def main() -> None:
    parser = argparse.ArgumentParser(description="Visualize ONNX predictions")
    parser.add_argument("--onnx", default="model.onnx")
    parser.add_argument("--image")
    parser.add_argument("--images")
    parser.add_argument("--input-size", type=int, default=112, choices=ALLOWED_INPUT_SIZES)
    parser.add_argument("--channels", type=int, default=3, choices=ALLOWED_CHANNELS)
    parser.add_argument("--save-dir")
    args = parser.parse_args()

    onnx_path = Path(args.onnx)
    if not onnx_path.exists():
        raise SystemExit(f"找不到 ONNX 文件：{onnx_path}")
    session = ort.InferenceSession(str(onnx_path), providers=["CPUExecutionProvider"])
    save_dir = Path(args.save_dir) if args.save_dir else None
    if save_dir:
        save_dir.mkdir(parents=True, exist_ok=True)

    for path in list_images(args.image, args.images):
        pred, conf = predict(session, path, args.input_size, args.channels)
        label = f"{CLASS_NAMES[pred]}  {conf * 100:.1f}%"
        print(f"{path}: {label}")
        canvas = make_canvas(path, label)
        if save_dir:
            canvas.save(save_dir / f"{path.stem}_pred.jpg", quality=92)
        else:
            key = show_with_cv(canvas, "SI100B demo")
            if key in {27, ord("q"), ord("Q")}:
                break


if __name__ == "__main__":
    main()
