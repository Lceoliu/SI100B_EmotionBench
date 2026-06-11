from __future__ import annotations

import argparse
from pathlib import Path

import numpy as np
from PIL import Image


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--train-root", type=Path, required=True)
    args = parser.parse_args()
    paths = sorted(path for path in args.train_root.rglob("*") if path.suffix.lower() in {".jpg", ".jpeg", ".png"})
    if not paths:
        raise RuntimeError(f"no images found under {args.train_root}")
    total = 0.0
    total_sq = 0.0
    pixels = 0
    for path in paths:
        array = np.asarray(Image.open(path).convert("L"), dtype=np.float64) / 255.0
        total += float(array.sum())
        total_sq += float((array * array).sum())
        pixels += int(array.size)
    mean = total / pixels
    std = (total_sq / pixels - mean * mean) ** 0.5
    print(f"images={len(paths)} pixels={pixels} mean={mean:.8f} std={std:.8f} rounded=({mean:.4f}, {std:.4f})")


if __name__ == "__main__":
    main()
