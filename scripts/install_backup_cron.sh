#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)"
ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"

export BENCH_ROOT="${BENCH_ROOT:-$ROOT}"
SCHEDULE="${BACKUP_CRON_SCHEDULE:-17 3 * * *}"
LOG_PATH="${BACKUP_LOG_PATH:-$BENCH_ROOT/logs/db_backup.log}"
MARKER="# emotion-bench database backup"
JOB="$SCHEDULE BENCH_ROOT=$BENCH_ROOT $BENCH_ROOT/scripts/backup_database.sh >> $LOG_PATH 2>&1 $MARKER"

mkdir -p "$(dirname "$LOG_PATH")"
tmp_file="$(mktemp)"
trap 'rm -f "$tmp_file"' EXIT

(crontab -l 2>/dev/null | grep -vF "$MARKER" || true) > "$tmp_file"
printf '%s\n' "$JOB" >> "$tmp_file"
crontab "$tmp_file"

echo "installed cron: $JOB"
