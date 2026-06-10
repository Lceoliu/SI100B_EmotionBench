"""极简训练脚本占位。

正式课程材料可以把自己的 Dataset/DataLoader 填进来。
本文件不是提交入口，提交只需要运行 bench.py pack。
"""

from pathlib import Path


def main() -> None:
    print("请参考 Lab 训练代码，把训练好的 state_dict 保存为 checkpoints/best.pth。")
    print(f"当前目录：{Path.cwd()}")


if __name__ == "__main__":
    main()
