# SI100B Emotional Bench 代码框架

本代码框架用于训练、检查、导出并提交表情分类模型。你最终只需要向网站上传一个 `model.onnx` 文件。

你主要会改两个位置：

- `model/__init__.py`：提交时使用的模型结构，必须提供 `build_model()`。
- `train_example.py`：本地训练脚本，可以按自己的想法修改。

不要修改 `bench.py`、`bench/` 目录。它们和服务器评测逻辑保持一致。

## 0. 目录结构

```text
si100b-bench-kit/
  model/__init__.py          # 你的模型定义，提交前必须和训练权重匹配
  train_example.py           # FER2013 训练示例
  download_fer2013.py        # 下载并解压 FER2013
  demo_predict.py            # 本地可视化预测 demo，可选
  bench.py                   # 检查、评分、导出 ONNX 的工具
  bench/transforms.py        # 与服务器一致的 resize/normalize
  bench/devset/              # 小样本参考集，仅用于本地自测
```

## 1. 建议使用 Python venv

推荐 Python 3.10 或 3.11。除非你已经熟悉 conda，否则优先使用 Python 自带的 `venv`，它更轻、更容易复现。

Windows PowerShell：

```powershell
cd si100b-bench-kit
py -3.10 -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install -U pip -i https://pypi.tuna.tsinghua.edu.cn/simple
python -m pip install -r requirements.txt -i https://pypi.tuna.tsinghua.edu.cn/simple
```

如果 PowerShell 不允许激活虚拟环境，先执行一次：

```powershell
Set-ExecutionPolicy -Scope CurrentUser RemoteSigned
```

Linux / macOS：

```bash
cd si100b-bench-kit
python3 -m venv .venv
source .venv/bin/activate
python -m pip install -U pip -i https://pypi.tuna.tsinghua.edu.cn/simple
python -m pip install -r requirements.txt -i https://pypi.tuna.tsinghua.edu.cn/simple
```

也可以使用上海交大镜像：

```bash
python -m pip install -r requirements.txt -i https://mirror.sjtu.edu.cn/pypi/web/simple
```

不要同时混用 conda 环境和 venv；一个项目只保留一种环境管理方式。

## 2. macOS 同学注意

macOS 没有 NVIDIA CUDA。Apple Silicon 可以使用 PyTorch 的 MPS 后端，训练脚本会自动尝试：

```bash
python train_example.py --data datasets/fer2013/extracted --epochs 1
```

如果看到 `device: mps`，说明正在使用 Apple GPU。如果某个算子在 MPS 上报错，可以临时改用 CPU：

```bash
python train_example.py --data datasets/fer2013/extracted --device cpu
```

OpenCV 弹窗 demo 在 macOS 上可能需要额外授权终端访问屏幕；如果弹窗失败，用 `--save-dir demo_outputs` 保存可视化结果。

## 3. 确认环境是否可用

先跑一次模型契约检查：

```bash
python bench.py check --input-size 112 --channels 3
```

通过后应该看到类似：

```text
参数量 ...
前向契约通过：[B, 3, 112, 112] -> (2, 7)
```

如果显示 `torch.cuda.is_available()` 为 false，但你有 NVIDIA GPU，优先检查显卡驱动和 PyTorch 版本。不要在课程项目里反复盲目重装环境。

## 4. 写模型代码

提交时，平台只会加载 `model/__init__.py` 里的 `build_model()`，再加载你训练出的权重，然后导出 ONNX。

最小要求：

```python
def build_model() -> torch.nn.Module:
    return 你的模型
```

模型输入和输出必须满足：

```text
输入: [B, C, H, W]
输出: [B, 7]
```

类别顺序固定：

```text
0 angry
1 disgust
2 fear
3 happy
4 neutral
5 sad
6 surprise
```

### 使用 ResNet18

如果要用 torchvision 的 ResNet18，把 `model/__init__.py` 改成类似下面这样：

```python
import torch.nn as nn
from torchvision.models import resnet18

NUM_CLASSES = 7

def build_model() -> nn.Module:
    model = resnet18(weights=None)
    model.fc = nn.Linear(model.fc.in_features, NUM_CLASSES)
    return model
```

重要：提交用的 `model/__init__.py` 必须写 `weights=None`。不要在提交模型里写 `weights=ResNet18_Weights.DEFAULT`，否则服务器会尝试联网下载权重并拒绝。

训练时可以使用 ImageNet 预训练初始化：

```bash
python train_example.py --data datasets/fer2013/extracted --arch resnet18 --imagenet --input-size 112 --channels 3 --epochs 10
```

这样训练得到的 `checkpoints/best.pth` 仍然可以用上面的 `weights=None` 模型结构导出，因为预训练权重已经被保存进你自己的 state_dict。

如果 ImageNet 权重下载失败，先去掉 `--imagenet` 跑通流程；不要把下载失败误认为代码错误。

## 5. 下载 FER2013

FER2013 用于本地训练和自测。推荐放在代码框架内的 `datasets/fer2013/extracted`。

自动下载：

```bash
python download_fer2013.py
```

脚本会下载：

```text
https://www.kaggle.com/api/v1/datasets/download/msambare/fer2013
```

并解压成：

```text
datasets/fer2013/extracted/train/angry/...
datasets/fer2013/extracted/test/angry/...
```

如果下载很慢或失败，可以在浏览器中下载 zip，然后手动放到：

```text
datasets/fer2013/fer2013-msambare.zip
```

再运行：

```bash
python download_fer2013.py --zip datasets/fer2013/fer2013-msambare.zip
```

## 6. 开始训练

先用 1 个 epoch 确认数据、模型、GPU 都能跑：

```bash
python train_example.py --data datasets/fer2013/extracted --epochs 1 --input-size 112 --channels 3
```

确认使用 GPU：

- NVIDIA：日志里应显示 `device: cuda`。
- Apple Silicon：日志里应显示 `device: mps`。
- 没有 GPU：会显示 `device: cpu`，能跑但会慢。

正式训练可以增加 epoch：

```bash
python train_example.py --data datasets/fer2013/extracted --epochs 20 --batch-size 128 --lr 0.001 --input-size 112 --channels 3
```

使用 ResNet18 + ImageNet 初始化：

```bash
python train_example.py --data datasets/fer2013/extracted --arch resnet18 --imagenet --epochs 10 --batch-size 128 --lr 0.0003 --input-size 112 --channels 3
```

训练脚本会保存最好的验证集权重：

```text
checkpoints/best.pth
```

如果显存不足：

```bash
python train_example.py --data datasets/fer2013/extracted --batch-size 32 --input-size 96
```

## 7. 本地可视化 demo

默认依赖不安装 OpenCV。需要 demo 时再安装：

```bash
python -m pip install -r requirements-demo.txt -i https://pypi.tuna.tsinghua.edu.cn/simple
```

先导出 ONNX，再看预测效果：

```bash
python demo_predict.py --onnx model.onnx --image bench/devset/images/0004_angry_angry_African_93_face0.jpg --input-size 112 --channels 3
```

查看一个目录：

```bash
python demo_predict.py --onnx model.onnx --images bench/devset/images --input-size 112 --channels 3
```

如果当前环境不能弹窗：

```bash
python demo_predict.py --onnx model.onnx --images bench/devset/images --save-dir demo_outputs --input-size 112 --channels 3
```

## 8. 导出 ONNX

训练完成后，先确认 `model/__init__.py` 和训练时的模型结构一致。例如你用 ResNet18 训练，就必须把 `model/__init__.py` 改成 ResNet18 版本，而不是保留默认 SimpleCNN。

然后运行：

```bash
python bench.py pack --weights checkpoints/best.pth --input-size 112 --channels 3
```

`pack` 会做这些事情：

1. 检查 `model/__init__.py` 是否安全、是否有 `build_model()`。
2. 检查模型输入输出是否是 `[B,C,H,W] -> [B,7]`。
3. 加载 `checkpoints/best.pth`。
4. 导出单文件 `model.onnx`，batch 维是动态的。
5. 写入 metadata：kit 版本、输入尺寸、通道、导出时间、类别顺序。
6. 如果 devset 存在，自动生成本地参考分数、`local_metrics.json` 和 `local_confusion.png`。

本地再跑一次 ONNX 评分：

```bash
python bench.py score --onnx model.onnx --input-size 112 --channels 3
```

## 9. 提交到网站

打开评测网站，在提交页面选择和导出时完全一致的参数：

- 输入尺寸：和 `--input-size` 一致。
- 通道数：和 `--channels` 一致。
- 文件：上传 `model.onnx`。

第一次提交前建议先用“测试”模式确认流程。正式排行榜分数就是最终分数，显示的是排行榜评测集上的 Macro-F1 百分制。

## 10. 固定预处理规则

服务器保存的是高分辨率人脸裁切图。评测时只做固定预处理：

- resize：PIL bilinear。
- `C=1`：转灰度，`mean=0.5077, std=0.2551`。
- `C=3`：转 RGB，ImageNet `mean=[0.485, 0.456, 0.406]`，`std=[0.229, 0.224, 0.225]`。

本地 `bench/transforms.py` 与服务器同源。训练和导出时请保持同样的尺寸和通道。

## 11. 常见故障

| 现象 | 常见原因 | 处理 |
| --- | --- | --- |
| `ONNX input channels` | 网站选择的通道和导出时不同 | 上传时选择和 `pack --channels` 相同的值 |
| `H/W` | 网站选择的尺寸和 ONNX 声明不同 | 上传时选择和 `pack --input-size` 相同的值 |
| `external data` | ONNX 被拆成旁挂权重文件 | 使用本框架的 `bench.py pack` 导出，且模型小于 200 MB |
| `output must be [B, 7]` | 分类头不是 7 类 | 修改最后一层输出为 7 |
| `Missing key(s)` / `size mismatch` | 权重和模型结构不匹配 | 确认训练用的模型和 `model/__init__.py` 完全一致 |
| `weights=... 非 None` | 提交模型试图下载预训练权重 | 提交用 `model/__init__.py` 写 `weights=None`，训练时再使用预训练 |
| `CUDA out of memory` | batch 太大或尺寸太大 | 降低 `--batch-size` 或 `--input-size` |
| 训练很慢 | 没用上 GPU | 看训练日志的 `device:`；有 NVIDIA GPU 时应为 `cuda` |
| `No module named ...` | 虚拟环境没激活或依赖没装 | 重新激活 `.venv`，再安装 `requirements.txt` |
| macOS demo 不弹窗 | OpenCV GUI 权限或环境限制 | 使用 `--save-dir demo_outputs` |

## 12. 遇到问题如何定位

先收集最小信息：

```bash
python --version
python -c "import torch; print(torch.__version__, torch.cuda.is_available())"
python bench.py check --input-size 112 --channels 3
```

提问时请贴：

- 你运行的完整命令。
- 完整报错，不要只贴最后一行。
- 操作系统、Python 版本、是否有 GPU。
- `model/__init__.py` 中 `build_model()` 相关代码。
- 你选择的 `input-size` 和 `channels`。

建议阅读《提问的智慧》：

- 中文：`https://github.com/ryanhanwu/How-To-Ask-Questions-The-Smart-Way`
- 英文：`http://www.catb.org/~esr/faqs/smart-questions.html`

