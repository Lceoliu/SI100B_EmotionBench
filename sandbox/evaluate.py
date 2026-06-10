from __future__ import annotations

import importlib.util
import json
import os
from pathlib import Path

import torch
from PIL import Image
from safetensors.torch import load_file
from torchvision import transforms


IMAGE_SUFFIXES = {".jpg", ".jpeg", ".png", ".bmp", ".webp"}


def find_one(root: Path, name: str) -> Path:
    matches = list(root.rglob(name))
    if len(matches) != 1:
        raise RuntimeError(f"expected exactly one {name}, found {len(matches)}")
    return matches[0]


def load_student_model(sub_dir: Path, device: torch.device) -> torch.nn.Module:
    model_py = find_one(sub_dir, "model.py")
    weights = find_one(sub_dir, "model.safetensors")
    spec = importlib.util.spec_from_file_location("student_model", model_py)
    if spec is None or spec.loader is None:
        raise RuntimeError("cannot import model.py")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    if not hasattr(module, "build_model"):
        raise RuntimeError("model.py must expose build_model()")
    model = module.build_model()
    if not isinstance(model, torch.nn.Module):
        raise RuntimeError("build_model() must return torch.nn.Module")
    state = load_file(str(weights), device=str(device))
    model.load_state_dict(state, strict=True)
    model.to(device)
    model.eval()
    return model


def list_images(data_dir: Path) -> list[Path]:
    images = sorted(path for path in data_dir.rglob("*") if path.suffix.lower() in IMAGE_SUFFIXES and path.is_file())
    if not images:
        raise RuntimeError("no images found under /data")
    return images


def build_transform() -> transforms.Compose:
    input_size = int(os.environ.get("INPUT_SIZE", "224"))
    mean = json.loads(os.environ.get("NORMALIZE_MEAN", "[0.485, 0.456, 0.406]"))
    std = json.loads(os.environ.get("NORMALIZE_STD", "[0.229, 0.224, 0.225]"))
    return transforms.Compose(
        [
            transforms.Resize((input_size, input_size)),
            transforms.ToTensor(),
            transforms.Normalize(mean=mean, std=std),
        ]
    )


def read_batch(paths: list[Path], data_dir: Path, transform) -> tuple[torch.Tensor, list[str]]:
    tensors = []
    keys = []
    for path in paths:
        with Image.open(path) as img:
            tensors.append(transform(img.convert("RGB")))
        keys.append(path.relative_to(data_dir).as_posix())
    return torch.stack(tensors, dim=0), keys


def infer(model: torch.nn.Module, images: list[Path], data_dir: Path, device: torch.device) -> dict[str, int]:
    transform = build_transform()
    predictions: dict[str, int] = {}
    batch_size = int(os.environ.get("BATCH_SIZE", "32"))
    index = 0
    with torch.inference_mode():
        while index < len(images):
            current = images[index : index + batch_size]
            try:
                batch, keys = read_batch(current, data_dir, transform)
                logits = model(batch.to(device, dtype=torch.float32))
                pred = logits.argmax(dim=1).detach().cpu().tolist()
                predictions.update({key: int(value) for key, value in zip(keys, pred)})
                index += batch_size
            except RuntimeError as exc:
                if "out of memory" in str(exc).lower() and batch_size > 1:
                    torch.cuda.empty_cache()
                    batch_size = max(1, batch_size // 2)
                    print(f"OOM, reducing batch size to {batch_size}", flush=True)
                    continue
                raise
    return predictions


def main() -> None:
    sub_dir = Path(os.environ.get("SUBMISSION_DIR", "/sub"))
    data_dir = Path(os.environ.get("DATA_DIR", "/data"))
    out_dir = Path(os.environ.get("RESULT_DIR", "/out"))
    out_dir.mkdir(parents=True, exist_ok=True)

    device = torch.device("cuda" if torch.cuda.is_available() else "cpu")
    model = load_student_model(sub_dir, device)
    images = list_images(data_dir)
    predictions = infer(model, images, data_dir, device)
    payload = {"status": "ok", "device": str(device), "count": len(predictions), "predictions": predictions}
    (out_dir / "predictions.json").write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps({"status": "ok", "device": str(device), "count": len(predictions)}), flush=True)


if __name__ == "__main__":
    main()
