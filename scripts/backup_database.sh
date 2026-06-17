#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)"
ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"

export BENCH_ROOT="${BENCH_ROOT:-$ROOT}"
PYTHON_BIN="${PYTHON_BIN:-python3}"

mkdir -p "$BENCH_ROOT/logs"
exec "$PYTHON_BIN" "$SCRIPT_DIR/backup_database.py"
