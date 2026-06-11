from __future__ import annotations

import argparse
import json
import shutil
import sys
from datetime import datetime, timezone
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from sandbox.transforms import ALLOWED_CHANNELS, ALLOWED_INPUT_SIZES, IMAGE_SUFFIXES, cache_name, preprocess_image


def image_paths(images_dir: Path) -> list[Path]:
    return sorted(path for path in images_dir.rglob("*") if path.is_file() and path.suffix.lower() in IMAGE_SUFFIXES)


def build_cache(split_dir: Path, channels: int, input_size: int, force: bool) -> dict:
    images_dir = split_dir / "images"
    if not images_dir.exists():
        raise RuntimeError(f"images directory not found: {images_dir}")
    cache_root = split_dir / "cache" / cache_name(channels, input_size)
    manifest_path = cache_root / "cache_manifest.json"
    if manifest_path.exists() and not force:
        return json.loads(manifest_path.read_text(encoding="utf-8"))
    tmp_root = cache_root.with_name(cache_root.name + ".tmp")
    if tmp_root.exists():
        shutil.rmtree(tmp_root)
    tmp_root.mkdir(parents=True, exist_ok=True)
    items = []
    for image_path in image_paths(images_dir):
        rel = image_path.relative_to(images_dir).as_posix()
        cache_rel = f"{rel}.npy"
        output_path = tmp_root / cache_rel
        output_path.parent.mkdir(parents=True, exist_ok=True)
        np.save(output_path, preprocess_image(image_path, input_size=input_size, channels=channels), allow_pickle=False)
        items.append({"filename": rel, "array": cache_rel})
    manifest = {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "source_images": str(images_dir),
        "channels": channels,
        "input_size": input_size,
        "count": len(items),
        "format": "float32 NCHW normalized numpy arrays",
        "items": items,
    }
    (tmp_root / "cache_manifest.json").write_text(json.dumps(manifest, ensure_ascii=False, indent=2), encoding="utf-8")
    if cache_root.exists():
        shutil.rmtree(cache_root)
    tmp_root.rename(cache_root)
    return manifest


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--split-dir", type=Path, required=True)
    parser.add_argument("--force", action="store_true")
    args = parser.parse_args()
    summaries = []
    for channels in ALLOWED_CHANNELS:
        for input_size in ALLOWED_INPUT_SIZES:
            manifest = build_cache(args.split_dir, channels, input_size, args.force)
            summaries.append({"channels": channels, "input_size": input_size, "count": manifest["count"]})
            print(json.dumps(summaries[-1]), flush=True)
    (args.split_dir / "cache" / "summary.json").write_text(json.dumps(summaries, ensure_ascii=False, indent=2), encoding="utf-8")


if __name__ == "__main__":
    main()
