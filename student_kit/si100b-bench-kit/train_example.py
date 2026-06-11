from __future__ import annotations

import argparse
import importlib
import sys
from pathlib import Path

import torch
import torch.nn as nn
from torch.utils.data import DataLoader
from torchvision import datasets, transforms
from tqdm import tqdm

from bench.transforms import GRAY_MEAN, GRAY_STD, RGB_MEAN, RGB_STD


ROOT = Path(__file__).resolve().parent
NUM_CLASSES = 7
CLASS_NAMES = ["angry", "disgust", "fear", "happy", "neutral", "sad", "surprise"]


def choose_device(name: str) -> torch.device:
    # auto 会优先用 NVIDIA GPU，其次 Apple Silicon MPS，最后才是 CPU。
    if name != "auto":
        return torch.device(name)
    if torch.cuda.is_available():
        return torch.device("cuda")
    if hasattr(torch.backends, "mps") and torch.backends.mps.is_available():
        return torch.device("mps")
    return torch.device("cpu")


def image_transform(split: str, input_size: int, channels: int):
    # 这里的 resize / normalize 要尽量和服务器评测保持一致。
    # 训练集只额外加了一个水平翻转增强，验证集不做随机增强。
    if channels == 1:
        color = transforms.Grayscale(num_output_channels=1)
        mean, std = GRAY_MEAN, GRAY_STD
    elif channels == 3:
        color = transforms.Lambda(lambda image: image.convert("RGB"))
        mean, std = RGB_MEAN, RGB_STD
    else:
        raise ValueError("channels must be 1 or 3")

    ops = [color, transforms.Resize((input_size, input_size))]
    if split == "train":
        ops.append(transforms.RandomHorizontalFlip(p=0.5))
    ops.extend([transforms.ToTensor(), transforms.Normalize(mean, std)])
    return transforms.Compose(ops)


def load_fer2013(data_root: Path, input_size: int, channels: int, batch_size: int, num_workers: int):
    # FER2013 解压后应包含 train/ 和 test/ 两个目录，每个目录下有 7 个类别文件夹。
    train_dir = data_root / "train"
    val_dir = data_root / "test"
    if not train_dir.is_dir() or not val_dir.is_dir():
        raise SystemExit(f"找不到 FER2013 train/test 目录：{data_root}\n请先运行 python download_fer2013.py")

    train_set = datasets.ImageFolder(train_dir, transform=image_transform("train", input_size, channels))
    val_set = datasets.ImageFolder(val_dir, transform=image_transform("val", input_size, channels))
    if train_set.classes != CLASS_NAMES:
        raise SystemExit(f"类别目录应为 {CLASS_NAMES}，当前为 {train_set.classes}")
    if val_set.classes != CLASS_NAMES:
        raise SystemExit(f"验证集类别目录应为 {CLASS_NAMES}，当前为 {val_set.classes}")

    train_loader = DataLoader(train_set, batch_size=batch_size, shuffle=True, num_workers=num_workers, pin_memory=torch.cuda.is_available())
    val_loader = DataLoader(val_set, batch_size=batch_size, shuffle=False, num_workers=num_workers, pin_memory=torch.cuda.is_available())
    return train_loader, val_loader


def import_student_model() -> torch.nn.Module:
    # 默认训练路线：直接使用 model/__init__.py 里的 build_model()。
    # 这样训练出来的权重最容易被 bench.py pack 正确加载。
    if str(ROOT) not in sys.path:
        sys.path.insert(0, str(ROOT))
    importlib.invalidate_caches()
    sys.modules.pop("model", None)
    module = importlib.import_module("model")
    return module.build_model()


def adapt_resnet_first_conv(model: nn.Module, channels: int) -> None:
    # torchvision 的 ResNet 默认吃 3 通道图片。
    # 如果你选择灰度 C=1，这里把第一层卷积改成 1 通道。
    if channels == 3:
        return
    old = model.conv1
    new = nn.Conv2d(
        channels,
        old.out_channels,
        kernel_size=old.kernel_size,
        stride=old.stride,
        padding=old.padding,
        bias=old.bias is not None,
    )
    with torch.no_grad():
        new.weight.copy_(old.weight.mean(dim=1, keepdim=True))
        if old.bias is not None:
            new.bias.copy_(old.bias)
    model.conv1 = new


def build_model(args) -> torch.nn.Module:
    if args.arch == "model":
        model = import_student_model()
    elif args.arch == "resnet18":
        from torchvision.models import ResNet18_Weights, resnet18

        # 训练时可以下载 ImageNet 预训练权重；提交/导出模板里仍然要写 weights=None。
        weights = ResNet18_Weights.DEFAULT if args.imagenet else None
        model = resnet18(weights=weights)
        adapt_resnet_first_conv(model, args.channels)
        model.fc = nn.Linear(model.fc.in_features, NUM_CLASSES)
    else:
        raise SystemExit(f"unknown arch: {args.arch}")

    with torch.inference_mode():
        # 在真正训练前先跑一遍假输入，提前发现输入通道或输出类别数错误。
        y = model(torch.randn(2, args.channels, args.input_size, args.input_size))
    if tuple(y.shape) != (2, NUM_CLASSES):
        raise SystemExit(f"模型输出形状应为 (B, 7)，当前为 {tuple(y.shape)}")
    return model


def run_one_epoch(model, loader, criterion, optimizer, device: torch.device, train: bool) -> tuple[float, float]:
    model.train(train)
    total_loss = 0.0
    total_correct = 0
    total_count = 0
    iterator = tqdm(loader, leave=False, desc="train" if train else "val")
    for images, labels in iterator:
        images = images.to(device)
        labels = labels.to(device)
        if train:
            optimizer.zero_grad(set_to_none=True)
        logits = model(images)
        loss = criterion(logits, labels)
        if train:
            loss.backward()
            optimizer.step()
        total_loss += float(loss.item()) * labels.numel()
        total_correct += int((logits.argmax(dim=1) == labels).sum().item())
        total_count += labels.numel()
        iterator.set_postfix(loss=total_loss / max(total_count, 1), acc=total_correct / max(total_count, 1))
    return total_loss / total_count, total_correct / total_count


def main() -> None:
    parser = argparse.ArgumentParser(description="Minimal FER2013 training script")
    parser.add_argument("--data", default="datasets/fer2013/extracted", help="FER2013 extracted directory")
    parser.add_argument("--arch", default="model", choices=["model", "resnet18"], help="model uses model/build_model(); resnet18 uses torchvision")
    parser.add_argument("--imagenet", action="store_true", help="only for --arch resnet18: initialize from ImageNet weights")
    parser.add_argument("--input-size", type=int, default=112, choices=[48, 64, 96, 112, 160, 224])
    parser.add_argument("--channels", type=int, default=3, choices=[1, 3])
    parser.add_argument("--epochs", type=int, default=10)
    parser.add_argument("--batch-size", type=int, default=128)
    parser.add_argument("--lr", type=float, default=1e-3)
    parser.add_argument("--weight-decay", type=float, default=1e-4)
    parser.add_argument("--num-workers", type=int, default=0)
    parser.add_argument("--device", default="auto", help="auto, cuda, mps, or cpu")
    parser.add_argument("--out", default="checkpoints/best.pth")
    args = parser.parse_args()

    device = choose_device(args.device)
    print(f"device: {device}")
    print(f"input: C={args.channels}, H=W={args.input_size}")
    train_loader, val_loader = load_fer2013(Path(args.data), args.input_size, args.channels, args.batch_size, args.num_workers)
    print(f"train images: {len(train_loader.dataset)} | val images: {len(val_loader.dataset)}")

    model = build_model(args).to(device)
    if args.epochs <= 0:
        print("epochs <= 0: only checked data loading and model construction; no weights were saved.")
        return

    criterion = nn.CrossEntropyLoss()
    optimizer = torch.optim.AdamW(model.parameters(), lr=args.lr, weight_decay=args.weight_decay)

    best_acc = -1.0
    out_path = Path(args.out)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    for epoch in range(1, args.epochs + 1):
        train_loss, train_acc = run_one_epoch(model, train_loader, criterion, optimizer, device, train=True)
        with torch.inference_mode():
            val_loss, val_acc = run_one_epoch(model, val_loader, criterion, optimizer, device, train=False)
        print(
            f"epoch {epoch:03d}/{args.epochs:03d} "
            f"train_loss={train_loss:.4f} train_acc={train_acc:.4f} "
            f"val_loss={val_loss:.4f} val_acc={val_acc:.4f}"
        )
        if val_acc > best_acc:
            # 只保存验证集 accuracy 最好的那一次权重，导出 ONNX 时用它。
            best_acc = val_acc
            torch.save(model.state_dict(), out_path)
            print(f"saved: {out_path} (best val_acc={best_acc:.4f})")

    print(f"done. best weights: {out_path}")


if __name__ == "__main__":
    main()
