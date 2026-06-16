#!/usr/bin/env bash
set -euo pipefail

cd "$(dirname "$0")/../frontend"
npm ci
npm run build
cd ..
docker compose restart web
curl -fsS http://127.0.0.1:${WEB_PORT:-18080}/health
echo
