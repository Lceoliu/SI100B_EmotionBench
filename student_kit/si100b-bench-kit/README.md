# SI100B Emotional Bench 学生工具包

你只允许修改 `model/` 目录。其他文件都是评测工具，不要动。

## 三分钟最短路径

```bash
conda create -n si100b-bench python=3.10 -y
conda activate si100b-bench
pip install -r requirements.txt
python bench.py check
python bench.py pack --weights 你的权重.pth
```

生成 `submission.zip` 后，到课程评测网站先选择 `dry-run` 上传。dry-run 不计分、不占每日配额；dry-run 不通过，正式提交也大概率会失败。

## 你要改哪里

只改：

```text
model/__init__.py
```

这个文件里有三条路线：

- 路线 A：默认 SimpleCNN，能直接跑通流程。
- 路线 B：用 timm 现成模型，只改模型名。
- 路线 C：把 GitHub 找到的模型代码复制进 `model/` 后 import。

无论哪条路线，都必须满足：

- `build_model()` 不接受参数，返回 `torch.nn.Module`。
- 输入是 `[B, 3, 224, 224]` 的 float32 tensor。
- 输出是 `[B, 7]` 的 logits。
- `pretrained` 必须是 `False`，`weights` 必须是 `None`。
- 不要在模型文件里读写文件、下载权重、print、训练或加载 checkpoint。

## 一条命令入口

```bash
python bench.py check
python bench.py score --weights 你的权重.pth
python bench.py pack --weights 你的权重.pth
```

`pack` 会自动执行 check，然后转换 safetensors，并生成 `submission.zip`。

## 本地评分说明

`score` 会使用 `bench/devset/` 中的公开样例数据。如果你下载的版本暂时没有 devset 图片，`score` 会告诉你等待 TA 发布新版工具包；这不影响 `check` 和 `pack`。

本地分数只供参考，不计入成绩。正式成绩以网站 public/private/realworld 评测为准。

## 常见错误

| 报错关键词 | 人话原因 | 怎么改 |
| --- | --- | --- |
| `Missing key(s) ... module.` | 训练时用了 DataParallel/DDP | `bench.py` 会自动去掉 `module.`；如果还失败，说明模型结构和训练时不一致 |
| `size mismatch` | 分类头不是 7 类或模型结构改了 | 检查 `num_classes=7`，改完重新训练 |
| `weights=... 非 None` | 模型定义还想下载预训练权重 | 改成 `weights=None` |
| `pretrained=True` | 模型定义还想下载预训练权重 | 改成 `pretrained=False` |
| `output shape (N, 1000)` | 忘了换 7 类分类头 | 按模板把分类头改成 7 类 |
| `参数量超过上限` | 模型太大 | 换小模型，优先试 resnet18 / mobilenetv3 |
| dry-run 超时 | build_model 里写了训练或慢操作 | 把训练代码移出 `model/` |

提问前，请先运行：

```bash
python bench.py check
```

并把完整输出截图发给 TA。
