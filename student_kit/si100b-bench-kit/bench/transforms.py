from __future__ import annotations

from PIL import Image
from torchvision import transforms


INPUT_SIZE = 224
NORMALIZE_MEAN = [0.485, 0.456, 0.406]
NORMALIZE_STD = [0.229, 0.224, 0.225]


def build_transform() -> transforms.Compose:
    return transforms.Compose(
        [
            transforms.Resize((INPUT_SIZE, INPUT_SIZE)),
            transforms.ToTensor(),
            transforms.Normalize(mean=NORMALIZE_MEAN, std=NORMALIZE_STD),
        ]
    )


def load_image(path):
    with Image.open(path) as image:
        return build_transform()(image.convert("RGB"))
