#!/usr/bin/env bash
# Arranque em produção (Render): obriga host 0.0.0.0 e porta $PORT, sem --reload.
set -euo pipefail
PORT="${PORT:-10000}"
exec python -m uvicorn app:app --host 0.0.0.0 --port "$PORT"
