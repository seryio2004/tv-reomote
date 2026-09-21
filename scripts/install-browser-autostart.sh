#!/usr/bin/env bash
set -euo pipefail

if [[ "$(id -u)" -eq 0 ]]; then
    echo "Ejecuta este script con tu usuario normal, sin sudo." >&2
    exit 1
fi

PROJECT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
AUTOSTART_DIR="${XDG_CONFIG_HOME:-$HOME/.config}/autostart"
mkdir -p "$AUTOSTART_DIR"

cat >"$AUTOSTART_DIR/tv-remote-browser.desktop" <<EOF
[Desktop Entry]
Type=Application
Name=TV Remote Browser
Comment=Abre Chrome para el mando remoto
Exec=/usr/bin/env BROWSER_MODE=fullscreen "$PROJECT_DIR/scripts/start-browser.sh"
Terminal=false
X-GNOME-Autostart-enabled=true
EOF

echo "Chrome se abrirá a pantalla completa al iniciar sesión en Ubuntu."
