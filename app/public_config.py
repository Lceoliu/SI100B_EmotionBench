"""Configuration exposed to the browser via GET /api/config."""

from __future__ import annotations

from typing import Any

from app.config import configured_quota_per_day, load_config
from app.course import course_info, lectures
from app.onnx_validation import ALLOWED_CHANNELS, ALLOWED_INPUT_SIZES


def public_config_payload() -> dict[str, Any]:
    cfg = load_config()
    return {
        "course": course_info(cfg),
        "lectures": lectures(cfg),
        "quota_per_day": configured_quota_per_day(cfg),
        "max_params": cfg.get("max_params", 50_000_000),
        "max_weight_mb": cfg.get("max_weight_mb", 200),
        "eval_timeout_sec": cfg.get("eval_timeout_sec", 600),
        "num_classes": cfg.get("num_classes", 7),
        "submission_format": "onnx",
        "allowed_input_sizes": sorted(ALLOWED_INPUT_SIZES),
        "allowed_input_channels": sorted(ALLOWED_CHANNELS),
        "normalize": {
            "gray": {"mean": [0.5077], "std": [0.2551]},
            "rgb": {"mean": [0.485, 0.456, 0.406], "std": [0.229, 0.224, 0.225]},
        },
        "freeze_leaderboard": bool(cfg.get("freeze_leaderboard", False)),
        "final_pick_deadline": cfg.get("final_pick_deadline"),
    }
