from __future__ import annotations

from app.main import SessionLocal, write_sync_index


def sync_indexes() -> dict:
    with SessionLocal() as db:
        return write_sync_index(db)
