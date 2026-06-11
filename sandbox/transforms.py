from __future__ import annotations

from pathlib import Path

import numpy as np
from PIL import Image


ALLOWED_INPUT_SIZES = (48, 64, 96, 112, 160, 224)
ALLOWED_CHANNELS = (1, 3)
IMAGE_SUFFIXES = {".jpg", ".jpeg", ".png", ".bmp", ".webp"}
RESAMPLE = Image.Resampling.BILINEAR

# Computed once on the FER2013 train split. See scripts/compute_fer2013_gray_stats.py.
GRAY_MEAN = (0.5077,)
GRAY_STD = (0.2551,)

RGB_MEAN = (0.485, 0.456, 0.406)
RGB_STD = (0.229, 0.224, 0.225)


def normalize_constants(channels: int) -> tuple[tuple[float, ...], tuple[float, ...]]:
    if channels == 1:
        return GRAY_MEAN, GRAY_STD
    if channels == 3:
        return RGB_MEAN, RGB_STD
    raise ValueError("channels must be 1 or 3")


def preprocess_image(path: Path, *, input_size: int, channels: int) -> np.ndarray:
    if input_size not in ALLOWED_INPUT_SIZES:
        raise ValueError(f"input_size must be one of {ALLOWED_INPUT_SIZES}")
    if channels not in ALLOWED_CHANNELS:
        raise ValueError("channels must be 1 or 3")
    mode = "L" if channels == 1 else "RGB"
    with Image.open(path) as image:
        image = image.convert(mode).resize((input_size, input_size), RESAMPLE)
        array = np.asarray(image, dtype=np.float32) / 255.0
    if channels == 1:
        array = array[None, :, :]
    else:
        array = array.transpose(2, 0, 1)
    mean, std = normalize_constants(channels)
    mean_array = np.asarray(mean, dtype=np.float32).reshape(channels, 1, 1)
    std_array = np.asarray(std, dtype=np.float32).reshape(channels, 1, 1)
    return ((array - mean_array) / std_array).astype(np.float32, copy=False)


def cache_name(channels: int, input_size: int) -> str:
    return f"c{channels}_s{input_size}"
