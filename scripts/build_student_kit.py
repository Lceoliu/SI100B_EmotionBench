from __future__ import annotations

import shutil
import zipfile
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
KIT_ROOT = ROOT / "student_kit" / "si100b-bench-kit"
OUT_DIR = ROOT / "storage" / "resources"
OUT_ZIP = OUT_DIR / "si100b-bench-kit-v0.2.zip"


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
            if path.name == "__pycache__" or "__pycache__" in path.parts:
                continue
            arcname = Path("si100b-bench-kit") / path.relative_to(KIT_ROOT)
            zf.write(path, arcname.as_posix())
    print(f"wrote {OUT_ZIP} ({OUT_ZIP.stat().st_size / 1024 / 1024:.2f} MB)")


if __name__ == "__main__":
    main()
