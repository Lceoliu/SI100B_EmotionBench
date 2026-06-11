from __future__ import annotations

import json
import os
from pathlib import Path

import numpy as np
import onnxruntime as ort

from transforms import IMAGE_SUFFIXES, cache_name, preprocess_image


def find_model(sub_dir: Path) -> Path:
    matches = sorted(sub_dir.rglob("*.onnx"))
    if len(matches) != 1:
        raise RuntimeError(f"expected exactly one .onnx file, found {len(matches)}")
    return matches[0]


def load_cache(data_dir: Path) -> list[tuple[str, Path]]:
    manifest_path = data_dir / "cache_manifest.json"
    if not manifest_path.exists():
        return []
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    items = []
    for item in manifest.get("items", []):
        items.append((str(item["filename"]), data_dir / str(item["array"])))
    if not items:
        raise RuntimeError(f"cache manifest has no items: {manifest_path}")
    return items


def list_images(data_dir: Path) -> list[tuple[str, Path]]:
    images = sorted(path for path in data_dir.rglob("*") if path.suffix.lower() in IMAGE_SUFFIXES and path.is_file())
    if not images:
        raise RuntimeError("no images or cache arrays found under /data")
    return [(path.relative_to(data_dir).as_posix(), path) for path in images]


def input_shape(session: ort.InferenceSession) -> tuple[str, int, int]:
    inputs = session.get_inputs()
    if len(inputs) != 1:
        raise RuntimeError("ONNX model must have exactly one input")
    shape = inputs[0].shape
    if len(shape) != 4:
        raise RuntimeError("ONNX input must be NCHW [B, C, H, W]")
    channels, height, width = shape[1], shape[2], shape[3]
    if channels not in (1, 3) or height != width or height not in (48, 64, 96, 112, 160, 224):
        raise RuntimeError(f"unsupported ONNX input shape: {shape}")
    return inputs[0].name, int(channels), int(height)


def output_name(session: ort.InferenceSession) -> str | None:
    outputs = session.get_outputs()
    return outputs[0].name if outputs else None


def read_batch(
    items: list[tuple[str, Path]],
    *,
    channels: int,
    input_size: int,
    from_cache: bool,
) -> tuple[np.ndarray, list[str]]:
    arrays = []
    keys = []
    for key, path in items:
        if from_cache:
            arrays.append(np.load(path, allow_pickle=False))
        else:
            arrays.append(preprocess_image(path, input_size=input_size, channels=channels))
        keys.append(key)
    return np.stack(arrays, axis=0).astype(np.float32, copy=False), keys


def infer(session: ort.InferenceSession, data_dir: Path, channels: int, input_size: int) -> dict[str, int]:
    cached = load_cache(data_dir)
    from_cache = bool(cached)
    items = cached if from_cache else list_images(data_dir)
    input_name = session.get_inputs()[0].name
    out_name = output_name(session)
    predictions: dict[str, int] = {}
    batch_size = int(os.environ.get("BATCH_SIZE", "64"))
    index = 0
    while index < len(items):
        current = items[index : index + batch_size]
        try:
            batch, keys = read_batch(current, channels=channels, input_size=input_size, from_cache=from_cache)
            outputs = session.run([out_name] if out_name else None, {input_name: batch})
            logits = outputs[0]
            if logits.ndim != 2 or logits.shape[1] != int(os.environ.get("NUM_CLASSES", "7")):
                raise RuntimeError(f"ONNX output must be [B, 7], got {tuple(logits.shape)}")
            preds = logits.argmax(axis=1).tolist()
            predictions.update({key: int(pred) for key, pred in zip(keys, preds)})
            index += batch_size
        except Exception as exc:
            message = str(exc).lower()
            if ("out of memory" in message or "cuda" in message) and batch_size > 1:
                batch_size = max(1, batch_size // 2)
                print(f"batch failed, reducing batch size to {batch_size}: {exc}", flush=True)
                continue
            raise
    return predictions


def main() -> None:
    sub_dir = Path(os.environ.get("SUBMISSION_DIR", "/sub"))
    data_dir = Path(os.environ.get("DATA_DIR", "/data"))
    out_dir = Path(os.environ.get("RESULT_DIR", "/out"))
    out_dir.mkdir(parents=True, exist_ok=True)

    model_path = find_model(sub_dir)
    available = ort.get_available_providers()
    requested = ["CUDAExecutionProvider", "CPUExecutionProvider"] if "CUDAExecutionProvider" in available else ["CPUExecutionProvider"]
    session = ort.InferenceSession(str(model_path), providers=requested)
    input_name, channels, input_size = input_shape(session)
    expected_cache = cache_name(channels, input_size)
    predictions = infer(session, data_dir, channels, input_size)
    payload = {
        "status": "ok",
        "provider": session.get_providers()[0],
        "providers": session.get_providers(),
        "input_name": input_name,
        "input_channels": channels,
        "input_size": input_size,
        "expected_cache": expected_cache,
        "count": len(predictions),
        "predictions": predictions,
    }
    (out_dir / "predictions.json").write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps({key: payload[key] for key in ("status", "provider", "input_channels", "input_size", "count")}), flush=True)


if __name__ == "__main__":
    main()
