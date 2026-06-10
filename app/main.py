from pathlib import Path
import os
import yaml
from fastapi import FastAPI
from fastapi.responses import HTMLResponse

ROOT = Path(os.environ.get("BENCH_ROOT", ".")).resolve()
CONFIG_PATH = Path(os.environ.get("CONFIG_PATH", ROOT / "config.yaml"))

app = FastAPI(title="Emotion Benchmark", version="0.1-dev")


def load_config() -> dict:
    if not CONFIG_PATH.exists():
        return {}
    with CONFIG_PATH.open("r", encoding="utf-8") as f:
        return yaml.safe_load(f) or {}


@app.get("/health")
def health() -> dict:
    return {"status": "ok", "root": str(ROOT), "config_exists": CONFIG_PATH.exists()}


@app.get("/", response_class=HTMLResponse)
def index() -> str:
    cfg = load_config()
    return (
        "<html><head><title>Emotion Benchmark</title></head>"
        "<body><h1>Emotion Benchmark</h1>"
        "<p>Development service is running.</p>"
        f"<p>num_classes: {cfg.get('num_classes', 'unset')}</p>"
        '<p><a href="/health">health</a></p>'
        "</body></html>"
    )
