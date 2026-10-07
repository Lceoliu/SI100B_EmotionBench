"""Process-level settings read from the environment once at import time."""

from __future__ import annotations

import os
import secrets
from datetime import timedelta, timezone
from pathlib import Path

ROOT = Path(os.environ.get("BENCH_ROOT", ".")).resolve()
CONFIG_PATH = Path(os.environ.get("CONFIG_PATH", ROOT / "config.yaml"))
STORAGE_ROOT = Path(os.environ.get("STORAGE_ROOT", ROOT / "storage")).resolve()
SUBMISSION_ROOT = STORAGE_ROOT / "submissions"
INDEX_ROOT = STORAGE_ROOT / "index"
RESOURCE_ROOT = STORAGE_ROOT / "resources"
RESULTS_ROOT = Path(os.environ.get("RESULTS_ROOT", ROOT / "results")).resolve()
FRONTEND_DIST = Path(os.environ.get("FRONTEND_DIST", ROOT / "frontend" / "dist")).resolve()
DATABASE_URL = os.environ.get("DATABASE_URL", f"sqlite:///{STORAGE_ROOT / 'bench.db'}")

APP_ENV = os.environ.get("APP_ENV", "dev").lower()
IS_PRODUCTION = APP_ENV in {"prod", "production"}
SECRET_KEY = os.environ.get("SECRET_KEY")
if not SECRET_KEY:
    if IS_PRODUCTION:
        raise RuntimeError("SECRET_KEY must be set in production.")
    # Ephemeral key: sessions do not survive a restart, which is fine for local development.
    SECRET_KEY = secrets.token_urlsafe(32)
SESSION_COOKIE_SECURE = os.environ.get("SESSION_COOKIE_SECURE", "1" if IS_PRODUCTION else "0") == "1"
INVITE_CODE = os.environ.get("INVITE_CODE", "").strip()
DOWNLOAD_LIMIT_PER_MINUTE = int(os.environ.get("DOWNLOAD_LIMIT_PER_MINUTE", "40"))
AUTH_LIMIT_PER_MINUTE = int(os.environ.get("AUTH_LIMIT_PER_MINUTE", "20"))

DEFAULT_QUOTA_PER_DAY = 4
MIN_PASSWORD_LENGTH = 8
SEEDED_INVITE_SETTING = "seeded_invite_code"
COURSE_TZ = timezone(timedelta(hours=8))
