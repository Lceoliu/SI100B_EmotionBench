"""
你唯一允许修改的目录是 model/。

必须提供 build_model()，它返回一个未加载权重的 torch.nn.Module。
代码框架会把模型和权重导出为单个 model.onnx，评测平台只接收 .onnx 文件。

类顺序：
0=angry, 1=disgust, 2=fear, 3=happy, 4=neutral, 5=sad, 6=surprise
"""

import torch
import torch.nn as nn

NUM_CLASSES = 7


# =========================
# 路线 A：我只想跑通，直接写个简单模型
# =========================
class SimpleCNN(nn.Module):
    def __init__(self, in_channels: int = 3, channels: int = 32, dropout: float = 0.1):
        super().__init__()
        # features 负责从图片里提取特征，最后用 AdaptiveAvgPool2d 压成一个向量。
        self.features = nn.Sequential(
            nn.Conv2d(in_channels, channels, 3, stride=2, padding=1),
            nn.BatchNorm2d(channels),
            nn.ReLU(inplace=True),
            nn.Conv2d(channels, channels * 2, 3, stride=2, padding=1),
            nn.BatchNorm2d(channels * 2),
            nn.ReLU(inplace=True),
            nn.Conv2d(channels * 2, channels * 4, 3, stride=2, padding=1),
            nn.BatchNorm2d(channels * 4),
            nn.ReLU(inplace=True),
            nn.AdaptiveAvgPool2d(1),
        )
        self.classifier = nn.Sequential(
            # classifier 负责把特征变成 7 个类别的 logits。
            nn.Dropout(dropout),
            nn.Linear(channels * 4, NUM_CLASSES),
        )

    def forward(self, x: torch.Tensor) -> torch.Tensor:
        x = self.features(x)
        x = torch.flatten(x, 1)
        return self.classifier(x)


def build_model() -> nn.Module:
    # 默认使用 RGB 输入，所以 in_channels=3。
    # 如果你训练和提交都选择灰度 C=1，这里也要改成 in_channels=1。
    return SimpleCNN(in_channels=3)


# =========================
# 路线 B：我想用现成强模型
# =========================
# 推荐先用 torchvision 自带的 ResNet18。提交用的模型必须 weights=None，
# 不要让评测服务器联网下载 ImageNet 权重。
#
# from torchvision.models import resnet18
#
# def build_model() -> nn.Module:
#     model = resnet18(weights=None)
#     model.fc = nn.Linear(model.fc.in_features, NUM_CLASSES)
#     return model
#
# 如果训练时想用 ImageNet 预训练：
# 1. 运行 train_example.py --arch resnet18 --imagenet ...
# 2. 训练完成后仍然保持这里 weights=None。
# 3. 用 bench.py pack 加载你训练好的 checkpoints/best.pth。


# =========================
# 路线 C：我想用更复杂的模型代码！（推荐）
# =========================
# 1. 把模型等 .py 文件复制进 model/ 目录。
# 2. 在这里 import 它。
# 3. 最终只要保证在 build_model() 里创建模型，并确保分类头是 7 类。
#
# from .my_network import MyNetwork
#
# def build_model() -> nn.Module:
#     return MyNetwork(num_classes=NUM_CLASSES)
