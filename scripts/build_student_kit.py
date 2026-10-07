from __future__ import annotations

import shutil
import zipfile
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
KIT_ROOT = ROOT / "student_kit" / "si100b-bench-kit"
OUT_DIR = ROOT / "storage" / "resources"
DEFAULT_KIT_FILENAME = "si100b-bench-kit-v0.2.2.zip"


def kit_filename() -> str:
    """Use the filename the web app serves for the `student-kit` resource in config.yaml."""
    try:
        import yaml
    except ImportError:
        return DEFAULT_KIT_FILENAME
    config_path = ROOT / "config.yaml"
    if not config_path.exists():
        return DEFAULT_KIT_FILENAME
    cfg = yaml.safe_load(config_path.read_text(encoding="utf-8")) or {}
    for item in cfg.get("resources") or []:
        if isinstance(item, dict) and item.get("id") == "student-kit" and item.get("filename"):
            return str(item["filename"])
    return DEFAULT_KIT_FILENAME


OUT_ZIP = OUT_DIR / kit_filename()
SKIP_DIRS = {"__pycache__", ".venv", "venv", "env", "checkpoints", "demo_outputs", "datasets"}
SKIP_FILES = {"model.onnx", "local_metrics.json", "local_confusion.png"}


def main() -> None:
    if not KIT_ROOT.exists():
        raise SystemExit(f"missing kit source: {KIT_ROOT}")
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    if OUT_ZIP.exists():
        OUT_ZIP.unlink()
    with zipfile.ZipFile(OUT_ZIP, "w", zipfile.ZIP_DEFLATED) as zf:
        for path in sorted(KIT_ROOT.rglob("*")):
            if path.is_dir():
                continue
            if path.name in SKIP_FILES or any(part in SKIP_DIRS for part in path.parts):
                continue
            arcname = Path("si100b-bench-kit") / path.relative_to(KIT_ROOT)
            zf.write(path, arcname.as_posix())
    print(f"wrote {OUT_ZIP} ({OUT_ZIP.stat().st_size / 1024 / 1024:.2f} MB)")


if __name__ == "__main__":
    main()
