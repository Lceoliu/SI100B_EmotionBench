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
            nn.Dropout(dropout),
            nn.Linear(channels * 4, NUM_CLASSES),
        )

    def forward(self, x: torch.Tensor) -> torch.Tensor:
        x = self.features(x)
        x = torch.flatten(x, 1)
        return self.classifier(x)


def build_model() -> nn.Module:
    return SimpleCNN(in_channels=3)


# =========================
# 路线 B：我想用现成强模型
# =========================
# 需要先 pip install timm。服务器测试/正式评测也已安装 timm。
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
