import json
import os
from pathlib import Path


def main() -> None:
    out_dir = Path(os.environ.get("RESULT_DIR", "/out"))
    out_dir.mkdir(parents=True, exist_ok=True)
    payload = {
        "status": "placeholder",
        "message": "evaluation entrypoint is installed; wire model loading in M1",
    }
    (out_dir / "predictions.json").write_text(json.dumps(payload, indent=2), encoding="utf-8")
    print(json.dumps(payload), flush=True)


if __name__ == "__main__":
    main()
