"""Benchmark configuration: config.yaml defaults overridden by settings saved from the TA console."""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

import yaml
from fastapi import HTTPException
from sqlalchemy import text
from sqlalchemy.orm import Session

from app import env
from app.db import engine
from app.models import Setting

BOOLEAN_SETTINGS = {"freeze_leaderboard"}


def load_file_config() -> dict[str, Any]:
    if not env.CONFIG_PATH.exists():
        return {}
    with env.CONFIG_PATH.open("r", encoding="utf-8") as f:
        return yaml.safe_load(f) or {}


def load_config() -> dict[str, Any]:
    cfg = load_file_config()
    try:
        with engine.connect() as conn:
            rows = conn.execute(text("SELECT key, value FROM settings")).mappings().all()
        for row in rows:
            key = str(row["key"])
            value = str(row["value"])
            if key in BOOLEAN_SETTINGS:
                cfg[key] = value.lower() in {"1", "true", "yes", "on"}
            else:
                cfg[key] = value
    except Exception:
        pass
    return cfg


def set_setting(db: Session, key: str, value: Any) -> None:
    setting = db.get(Setting, key)
    text_value = "" if value is None else str(value)
    if setting is None:
        setting = Setting(key=key, value=text_value)
        db.add(setting)
    else:
        setting.value = text_value


def configured_quota_per_day(cfg: dict[str, Any]) -> int:
    try:
        quota = int(cfg.get("quota_per_day", env.DEFAULT_QUOTA_PER_DAY))
    except (TypeError, ValueError):
        quota = env.DEFAULT_QUOTA_PER_DAY
    return max(0, quota)


def parse_deadline(value: Any) -> datetime | None:
    if value is None:
        return None
    raw = str(value).strip()
    if not raw or "XX" in raw:
        return None
    try:
        parsed = datetime.fromisoformat(raw.replace("Z", "+00:00"))
    except ValueError:
        return None
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=timezone.utc)
    return parsed.astimezone(timezone.utc)


def normalize_deadline(value: Any) -> str:
    raw = str(value or "").strip()
    if not raw:
        return ""
    parsed = parse_deadline(raw)
    if parsed is None:
        raise HTTPException(status_code=400, detail="截止时间格式无效。请使用 ISO 时间，例如 2026-06-30T23:59:59+08:00。")
    return parsed.isoformat()
