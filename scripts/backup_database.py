#!/usr/bin/env python3
from __future__ import annotations

import gzip
import json
import os
import shutil
import sqlite3
import time
from datetime import datetime, timezone
from pathlib import Path


ROOT = Path(os.environ.get("BENCH_ROOT", Path(__file__).resolve().parents[1])).resolve()
DB_PATH = Path(os.environ.get("DATABASE_PATH", ROOT / "storage" / "bench.db")).resolve()
BACKUP_DIR = Path(os.environ.get("BACKUP_DIR", ROOT / "storage" / "backups")).resolve()
RETENTION_DAYS = int(os.environ.get("BACKUP_RETENTION_DAYS", "14"))


def main() -> None:
    if not DB_PATH.is_file():
        raise SystemExit(f"database not found: {DB_PATH}")

    BACKUP_DIR.mkdir(parents=True, exist_ok=True)
    stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    temp_db = BACKUP_DIR / f".bench-{stamp}.db.tmp"
    output = BACKUP_DIR / f"bench-{stamp}.db.gz"

    try:
        source_uri = f"file:{DB_PATH.as_posix()}?mode=ro"
        with sqlite3.connect(source_uri, uri=True, timeout=30) as source:
            with sqlite3.connect(temp_db) as target:
                source.backup(target)

        with temp_db.open("rb") as source_file:
            with gzip.open(output, "wb", compresslevel=6) as backup_file:
                shutil.copyfileobj(source_file, backup_file)
    finally:
        temp_db.unlink(missing_ok=True)

    cutoff = time.time() - RETENTION_DAYS * 24 * 60 * 60
    removed = 0
    for old_backup in BACKUP_DIR.glob("bench-*.db.gz"):
        try:
            if old_backup.stat().st_mtime < cutoff:
                old_backup.unlink()
                removed += 1
        except OSError:
            continue

    print(
        json.dumps(
            {
                "ok": True,
                "database": str(DB_PATH),
                "backup": str(output),
                "size_bytes": output.stat().st_size,
                "retention_days": RETENTION_DAYS,
                "removed_old_backups": removed,
            },
            ensure_ascii=False,
        )
    )


if __name__ == "__main__":
    main()
