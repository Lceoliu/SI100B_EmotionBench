#!/usr/bin/env bash
set -euo pipefail
cd "$(dirname "$0")/.."
for path in config.yaml docker-compose.yml docker/web.Dockerfile docker/eval.Dockerfile requirements-web.txt requirements-eval.txt; do
  test -f "$path" || { echo "missing $path"; exit 1; }
done
for path in data storage results logs; do
  test -d "$path" || { echo "missing $path"; exit 1; }
done
echo "layout ok"
