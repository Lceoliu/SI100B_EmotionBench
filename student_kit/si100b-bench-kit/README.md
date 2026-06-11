# SI100B Emotional Bench 代码框架

这份代码框架只做一件事：帮你把 PyTorch 模型变成网站能评测的 `model.onnx`。

最终提交时，网站只收一个文件：

```text
model.onnx
```

网站不会读取你的 `model/__init__.py`，也不会读取你的训练代码。`model/__init__.py` 只在你本地运行 `bench.py pack`、导出 ONNX 时使用。

## 1. 你先记住这条流程

```text
创建 Python 环境
安装依赖
下载 FER2013
写 model/__init__.py
训练，得到 checkpoints/best.pth
导出 model.onnx
上传 model.onnx
```

如果你现在完全不知道该做什么，就按下面命令一条一条执行。

## 2. 创建 Python 环境

推荐 Python 3.10 或 3.11。优先用 Python 自带的 `venv`，不要一上来就用 conda。

### Windows PowerShell

进入代码框架目录：

```powershell
cd si100b-bench-kit
```

创建虚拟环境：

```powershell
py -3.10 -m venv .venv
```

激活虚拟环境：

```powershell
.\.venv\Scripts\Activate.ps1
```

如果提示不允许运行脚本，执行：

```powershell
Set-ExecutionPolicy -Scope CurrentUser RemoteSigned
```

然后重新激活：

```powershell
.\.venv\Scripts\Activate.ps1
```

### Linux / macOS

```bash
cd si100b-bench-kit
python3 -m venv .venv
source .venv/bin/activate
```

### 怎样判断已经激活成功

命令行前面一般会出现：

```text
(.venv)
```

再运行：

```bash
python --version
```

如果能看到 Python 版本，继续下一步。

## 3. 安装依赖

必须使用国内镜像源，否则可能很慢。

```bash
python -m pip install -U pip -i https://pypi.tuna.tsinghua.edu.cn/simple
python -m pip install -r requirements.txt -i https://pypi.tuna.tsinghua.edu.cn/simple
```

如果清华源失败，换上海交大源：

```bash
python -m pip install -r requirements.txt -i https://mirror.sjtu.edu.cn/pypi/web/simple
```

不要安装一堆你不知道干什么的库。本框架默认只安装训练、导出 ONNX、本地评分需要的库。

## 4. 先检查代码框架能不能跑

运行：

```bash
python bench.py check --input-size 112 --channels 3
```

如果通过，会看到类似：

```text
model/__init__.py 静态检查通过
前向契约通过：[B, 3, 112, 112] -> (2, 7)
```

如果这一步都失败，不要开始训练。先把这一步修好。

## 5. 下载 FER2013 数据集

FER2013 是你们可以用来训练的数据集。

自动下载：

```bash
python download_fer2013.py
```

下载完成后应该出现：

```text
datasets/fer2013/extracted/train/angry/...
datasets/fer2013/extracted/test/angry/...
```

如果自动下载失败：

1. 在浏览器里打开 Kaggle 下载地址。
2. 下载 zip 文件。
3. 把 zip 放到：

```text
datasets/fer2013/fer2013-msambare.zip
```

4. 运行：

```bash
python download_fer2013.py --zip datasets/fer2013/fer2013-msambare.zip
```

## 6. 写模型代码

你最重要的文件是：

```text
model/__init__.py
```

这个文件里必须有：

```python
def build_model():
    return 模型对象
```

模型必须满足：

```text
输入: [B, C, H, W]
输出: [B, 7]
```

`B` 是 batch size。`C` 是通道数，只能是 `1` 或 `3`。`H=W` 只能选：

```text
48, 64, 96, 112, 160, 224
```

7 个类别的顺序固定：

```text
0 angry
1 disgust
2 fear
3 happy
4 neutral
5 sad
6 surprise
```

### 最简单路线：先用默认 SimpleCNN

你可以先不改 `model/__init__.py`，直接训练默认模型，先跑通流程。

### ResNet18 路线

如果你想用 ResNet18，把 `model/__init__.py` 改成：

```python
import torch.nn as nn
from torchvision.models import resnet18

NUM_CLASSES = 7

def build_model() -> nn.Module:
    model = resnet18(weights=None)
    model.fc = nn.Linear(model.fc.in_features, NUM_CLASSES)
    return model
```

这里为什么是 `weights=None`？

因为 `model/__init__.py` 是本地导出 ONNX 时用的。导出时要先创建模型结构，再加载你训练好的 `checkpoints/best.pth`。预训练权重如果有用到，已经被保存进 `best.pth` 了。

不要在 `model/__init__.py` 里写：

```python
weights=ResNet18_Weights.DEFAULT
```

否则导出 ONNX 时可能尝试联网下载权重，导致失败，也不利于复现。

正确理解：

```text
训练时可以用 ImageNet 预训练。
导出/提交用的 model/__init__.py 要能离线创建同一个模型结构。
网站最终只收 model.onnx。
```

## 7. 开始训练

先用 1 个 epoch 测试：

```bash
python train_example.py --data datasets/fer2013/extracted --epochs 1 --input-size 112 --channels 3
```

你应该看日志里的 `device:`：

```text
device: cuda
```

表示 NVIDIA GPU 正在工作。

```text
device: mps
```

表示 macOS Apple Silicon GPU 正在工作。

```text
device: cpu
```

表示没有用 GPU，能跑，但是会慢。

默认模型正式训练：

```bash
python train_example.py --data datasets/fer2013/extracted --epochs 20 --batch-size 128 --lr 0.001 --input-size 112 --channels 3
```

ResNet18 + ImageNet 预训练：

```bash
python train_example.py --data datasets/fer2013/extracted --arch resnet18 --imagenet --epochs 10 --batch-size 128 --lr 0.0003 --input-size 112 --channels 3
```

训练完成后会保存：

```text
checkpoints/best.pth
```

这个文件是你训练好的 PyTorch 权重。

如果显存爆了，降低 batch size：

```bash
python train_example.py --data datasets/fer2013/extracted --batch-size 32 --input-size 112
```

还不行就降低图片尺寸：

```bash
python train_example.py --data datasets/fer2013/extracted --batch-size 32 --input-size 96
```

## 8. 导出 ONNX

训练好以后运行：

```bash
python bench.py pack --weights checkpoints/best.pth --input-size 112 --channels 3
```

这一步会生成：

```text
model.onnx
```

`pack` 实际做了这些事：

1. 读取 `model/__init__.py`，调用 `build_model()` 创建模型。
2. 加载 `checkpoints/best.pth`。
3. 检查输入输出形状。
4. 导出单文件 `model.onnx`。
5. 把输入尺寸、通道数、kit 版本写进 ONNX metadata。
6. 用小样本 devset 跑一个本地参考分数。

注意：本地参考分数不等于排行榜分数，只是帮你检查模型有没有明显坏掉。

## 9. 本地看一下分类效果

默认不安装 OpenCV。需要可视化时再装：

```bash
python -m pip install -r requirements-demo.txt -i https://pypi.tuna.tsinghua.edu.cn/simple
```

查看单张图：

```bash
python demo_predict.py --onnx model.onnx --image bench/devset/images/0004_angry_angry_African_93_face0.jpg --input-size 112 --channels 3
```

查看整个目录：

```bash
python demo_predict.py --onnx model.onnx --images bench/devset/images --input-size 112 --channels 3
```

如果不能弹窗，保存图片：

```bash
python demo_predict.py --onnx model.onnx --images bench/devset/images --save-dir demo_outputs --input-size 112 --channels 3
```

## 10. 提交到网站

打开评测网站，提交页面选择：

```text
输入尺寸 = 你导出时的 --input-size
通道数 = 你导出时的 --channels
文件 = model.onnx
```

例如你导出时用了：

```bash
python bench.py pack --weights checkpoints/best.pth --input-size 112 --channels 3
```

网站上也必须选：

```text
输入尺寸 112
通道数 3
```

不要上传：

```text
best.pth
submission.zip
model.py
整个文件夹
```

只上传：

```text
model.onnx
```

## 11. macOS 同学注意

macOS 没有 NVIDIA CUDA。

Apple Silicon 可以用 MPS。训练脚本会自动尝试：

```bash
python train_example.py --data datasets/fer2013/extracted --epochs 1
```

如果出现 MPS 相关报错，可以先用 CPU 跑通：

```bash
python train_example.py --data datasets/fer2013/extracted --device cpu --epochs 1
```

OpenCV 弹窗在 macOS 上可能因为权限失败。用 `--save-dir` 保存结果即可。

## 12. 固定预处理规则

服务器评测时只做固定预处理：

```text
resize: PIL bilinear
C=1: 转灰度，mean=0.5077, std=0.2551
C=3: 转 RGB，ImageNet mean/std
```

`bench/transforms.py` 和服务器一致。

如果你训练时用 `--channels 3`，提交时也选通道 `3`。

如果你训练时用 `--input-size 112`，提交时也选尺寸 `112`。

## 13. 常见错误

| 报错或现象 | 你大概率做错了什么 | 怎么办 |
| --- | --- | --- |
| `No module named torch` | 没激活 `.venv`，或没安装依赖 | 重新激活 `.venv`，再安装 `requirements.txt` |
| `找不到 FER2013 train/test 目录` | 数据集没下载或路径写错 | 先运行 `python download_fer2013.py` |
| `size mismatch` | `model/__init__.py` 和训练权重不是同一个结构 | 用训练时相同的模型结构导出 |
| `Missing key(s)` | 权重文件和模型结构不匹配 | 不要用 A 模型的权重加载到 B 模型 |
| `weights=... 非 None` | 你在 `model/__init__.py` 里写了联网下载预训练权重 | 改成 `weights=None` |
| `output must be [B, 7]` | 最后一层不是 7 类 | 把分类头输出改成 7 |
| `ONNX input channels` | 网站选择的通道和 ONNX 不一致 | 网站选择和 `--channels` 一样的值 |
| `H/W` | 网站选择的尺寸和 ONNX 不一致 | 网站选择和 `--input-size` 一样的值 |
| `external data` | ONNX 被拆成多个文件 | 用 `bench.py pack` 重新导出 |
| `CUDA out of memory` | 显存不够 | 降低 `--batch-size`，再降低 `--input-size` |
| 训练特别慢 | 没用 GPU | 看 `device:`，NVIDIA 应该是 `cuda` |

## 14. 提问前先收集这些信息

运行：

```bash
python --version
python -c "import torch; print(torch.__version__, torch.cuda.is_available())"
python bench.py check --input-size 112 --channels 3
```

提问时请贴：

- 你运行的完整命令。
- 完整报错，从第一行到最后一行。
- 操作系统。
- Python 版本。
- 有没有 GPU。
- `model/__init__.py` 里 `build_model()` 的代码。
- 你导出 ONNX 时用的 `--input-size` 和 `--channels`。

建议阅读：

- 中文：《提问的智慧》`https://github.com/ryanhanwu/How-To-Ask-Questions-The-Smart-Way`
- 英文：`http://www.catb.org/~esr/faqs/smart-questions.html`

