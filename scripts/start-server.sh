#!/usr/bin/env bash
set -euo pipefail

PROJECT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
if [[ ! -x "$PROJECT_DIR/.venv/bin/python" ]]; then
    echo "Falta .venv. Ejecuta ./scripts/setup-host.sh primero." >&2
    exit 1
fi
cd "$PROJECT_DIR"
export PYTHONDONTWRITEBYTECODE=1
exec "$PROJECT_DIR/.venv/bin/python" -m uvicorn backend.main:app --host 0.0.0.0 --port "${PORT:-8000}"
