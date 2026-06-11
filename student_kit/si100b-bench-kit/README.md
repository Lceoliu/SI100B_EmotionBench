# SI100B Emotional Bench 代码框架

你只允许修改 `model/` 目录。其他文件是本地检查、ONNX 导出和 devset 评分工具，不要改。

## 三分钟最短路径

```bash
conda create -n si100b-bench python=3.10 -y
conda activate si100b-bench
pip install -r requirements.txt
python bench.py check --input-size 112 --channels 3
python bench.py pack --weights 你的权重.pth --input-size 112 --channels 3
```

生成 `model.onnx` 后，到课程评测网站选择相同的输入尺寸和通道，直接上传这个 `.onnx` 文件。第一次建议选择“测试”，测试不计分、不占每日配额。

## 输入合约

平台只接受 ONNX 单输入：

```text
[B, C, H, W]
```

- `B` 可以是动态 batch。
- `C` 只能是 `1` 或 `3`。
- `H=W`，只能从 `48 / 64 / 96 / 112 / 160 / 224` 中选择。
- 输出必须是 `[B, 7]` logits。
- 类别顺序：`angry, disgust, fear, happy, neutral, sad, surprise`。

## 固定预处理

服务器保存的是人脸裁切图。评测时按 ONNX 声明的尺寸和通道读取缓存张量：

- `C=1`：转灰度，resize，使用 FER2013 train split 统计量 `mean=0.5077, std=0.2551`。
- `C=3`：转 RGB，resize，使用 ImageNet `mean=[0.485,0.456,0.406]`，`std=[0.229,0.224,0.225]`。

本地 `bench/transforms.py` 与服务器同源。不要在模型里再做额外 resize/normalize，除非你明确知道自己训练时也完全一致。

## 常用命令

```bash
python bench.py check --input-size 112 --channels 3
python bench.py pack --weights 你的权重.pth --input-size 112 --channels 3
python bench.py score --onnx model.onnx --input-size 112 --channels 3
```

`pack` 会：

1. 静态检查 `model/__init__.py`。
2. 加载权重。
3. 导出 `model.onnx`，batch 维动态。
4. 写入 ONNX metadata：kit 版本、输入尺寸、通道、打包时间、类别顺序。
5. 如果 devset 可用，顺手跑本地参考分数。

## 常见错误

| 报错关键词 | 原因 | 怎么改 |
| --- | --- | --- |
| `ONNX input channels` | 网站选择的通道和 ONNX 声明不一致 | 上传时选择和 `pack --channels` 相同的值 |
| `H/W` | 网站选择的尺寸和 ONNX 声明不一致 | 上传时选择和 `pack --input-size` 相同的值 |
| `external data` | ONNX 旁挂权重文件 | 使用本框架导出；平台只收单文件 ONNX |
| `output must be [B, 7]` | 分类头不是 7 类 | 修改最后一层输出为 7 |
| `Missing key(s)` / `size mismatch` | 权重和模型结构不匹配 | 确认训练代码和 `model/__init__.py` 一致 |
| `weights=... 非 None` | 模型定义试图下载预训练权重 | 改为 `weights=None` 或 `pretrained=False` |

排行榜分数即最终平台评测分数，使用排行榜评测集上的 Macro-F1，并以百分制显示。
