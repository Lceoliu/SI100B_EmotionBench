from __future__ import annotations

import argparse
import shutil
import urllib.request
import zipfile
from pathlib import Path


DEFAULT_URL = "https://www.kaggle.com/api/v1/datasets/download/msambare/fer2013"


def download(url: str, target: Path) -> None:
    target.parent.mkdir(parents=True, exist_ok=True)
    with urllib.request.urlopen(url) as response, target.open("wb") as output:
        total = int(response.headers.get("Content-Length") or 0)
        copied = 0
        while True:
            chunk = response.read(1024 * 1024)
            if not chunk:
                break
            output.write(chunk)
            copied += len(chunk)
            if total:
                print(f"\rdownloaded {copied / 1024 / 1024:.1f}/{total / 1024 / 1024:.1f} MB", end="")
        print()


def extract(zip_path: Path, out_dir: Path, force: bool) -> None:
    if out_dir.exists() and any(out_dir.iterdir()):
        if not force:
            print(f"skip extract: {out_dir} already exists. Use --force to overwrite.")
            return
        shutil.rmtree(out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    with zipfile.ZipFile(zip_path) as zf:
        zf.extractall(out_dir)
    print(f"extracted: {out_dir}")


def main() -> None:
    parser = argparse.ArgumentParser(description="Download and extract FER2013")
    parser.add_argument("--url", default=DEFAULT_URL)
    parser.add_argument("--zip", default="datasets/fer2013/fer2013-msambare.zip")
    parser.add_argument("--out", default="datasets/fer2013/extracted")
    parser.add_argument("--force", action="store_true")
    args = parser.parse_args()

    zip_path = Path(args.zip)
    out_dir = Path(args.out)
    if not zip_path.exists():
        print(f"downloading: {args.url}")
        download(args.url, zip_path)
    else:
        print(f"using existing zip: {zip_path}")
    extract(zip_path, out_dir, args.force)

    train_dir = out_dir / "train"
    test_dir = out_dir / "test"
    if not train_dir.is_dir() or not test_dir.is_dir():
        raise SystemExit("解压后没有找到 train/test 目录。请检查 zip 文件是否正确。")
    print("FER2013 is ready.")


if __name__ == "__main__":
    main()
