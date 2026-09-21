#!/usr/bin/env bash

set -e

URL="${TV_REMOTE_URL:-http://localhost:8000/player}"

if command -v chromium >/dev/null 2>&1; then
    CHROMIUM_BIN="chromium"
elif command -v chromium-browser >/dev/null 2>&1; then
    CHROMIUM_BIN="chromium-browser"
else
    echo "No se encontró Chromium."
    echo "Instálalo y vuelve a ejecutar este script."
    exit 1
fi

exec "$CHROMIUM_BIN" \
    --kiosk \
    --no-first-run \
    --disable-session-crashed-bubble \
    "$URL"
