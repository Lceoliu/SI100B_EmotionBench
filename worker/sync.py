from __future__ import annotations

from app.db import SessionLocal
from app.leaderboard import write_sync_index


def sync_indexes() -> dict:
    with SessionLocal() as db:
        return write_sync_index(db)
