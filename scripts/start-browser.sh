#!/usr/bin/env bash
set -euo pipefail
START_URL="${START_URL:-https://www.youtube.com/}"
BROWSER_MODE="${BROWSER_MODE:-fullscreen}"
CDP_PORT="${CDP_PORT:-9222}"
find_browser(){ for c in google-chrome-stable google-chrome chromium chromium-browser; do if command -v "$c" >/dev/null 2>&1; then echo "$c"; return 0; fi; done; return 1; }
BROWSER_BIN="$(find_browser || true)"
if [[ -z "$BROWSER_BIN" ]]; then echo "No se encontró Google Chrome ni Chromium."; exit 1; fi
if [[ -n "${TV_REMOTE_PROFILE:-}" ]]; then
    PROFILE_DIR="$TV_REMOTE_PROFILE"
elif [[ "$(command -v "$BROWSER_BIN")" == /snap/bin/* ]]; then
    # Chromium Snap cannot use a profile inside hidden directories such as ~/.local.
    PROFILE_DIR="$HOME/snap/chromium/common/tv-reomote-profile"
else
    PROFILE_DIR="$HOME/.local/share/tv-reomote/chrome-profile"
fi
mkdir -p "$PROFILE_DIR"
MODE_ARGS=(); case "$BROWSER_MODE" in kiosk) MODE_ARGS+=(--kiosk);; fullscreen) MODE_ARGS+=(--start-fullscreen);; maximized) MODE_ARGS+=(--start-maximized);; window) ;; *) echo "BROWSER_MODE debe ser kiosk, fullscreen, maximized o window."; exit 1;; esac
echo "Navegador: $BROWSER_BIN"; echo "Perfil: $PROFILE_DIR"; echo "Modo: $BROWSER_MODE"; echo "CDP: 127.0.0.1:$CDP_PORT"
exec "$BROWSER_BIN" --remote-debugging-address=127.0.0.1 --remote-debugging-port="$CDP_PORT" --user-data-dir="$PROFILE_DIR" --no-first-run --disable-session-crashed-bubble "${MODE_ARGS[@]}" "$START_URL"
