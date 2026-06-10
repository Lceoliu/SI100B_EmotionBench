"""
你唯一允许修改的目录是 model/。

必须提供 build_model()，它返回一个未加载权重的 torch.nn.Module。
评测平台会自动加载你提交的 model.safetensors。

类顺序：
0=anger, 1=disgust, 2=fear, 3=happiness, 4=neutral, 5=sadness, 6=surprise
"""

import torch
import torch.nn as nn

NUM_CLASSES = 7


# =========================
# 路线 A：我只想跑通
# =========================
class SimpleCNN(nn.Module):
    def __init__(self, channels: int = 32, dropout: float = 0.1):
        super().__init__()
        self.features = nn.Sequential(
            nn.Conv2d(3, channels, 3, stride=2, padding=1),
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
            nn.Dropout(dropout),
            nn.Linear(channels * 4, NUM_CLASSES),
        )

    def forward(self, x: torch.Tensor) -> torch.Tensor:
        x = self.features(x)
        x = torch.flatten(x, 1)
        return self.classifier(x)


def build_model() -> nn.Module:
    return SimpleCNN()


# =========================
# 路线 B：我想用现成强模型
# =========================
# 需要先 pip install timm。服务器 dry-run/正式评测也已安装 timm。
#
# import timm
#
# def build_model() -> nn.Module:
#     return timm.create_model("resnet18", num_classes=NUM_CLASSES, pretrained=False)
#
# 可尝试模型名：
# resnet18, resnet34, mobilenetv3_small_100, mobilenetv3_large_100,
# efficientnet_b0, convnext_tiny


# =========================
# 路线 C：我想用 GitHub 模型代码
# =========================
# 1. 把模型 .py 文件复制进 model/ 目录。
# 2. 在这里 import 它。
# 3. 在 build_model() 里创建模型，并确保分类头是 7 类。
#
# from .my_network import MyNetwork
#
# def build_model() -> nn.Module:
#     return MyNetwork(num_classes=NUM_CLASSES)
