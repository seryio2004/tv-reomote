#!/usr/bin/env bash
set -euo pipefail

if [[ "$(id -u)" -eq 0 ]]; then
    echo "Ejecuta este script con tu usuario normal; usará sudo para instalar los servicios." >&2
    exit 1
fi

case "${1:-}" in
    "") INSTALL_API=1 ;;
    --docker) INSTALL_API=0 ;;
    *) echo "Uso: $0 [--docker]" >&2; exit 2 ;;
esac
if [[ "$INSTALL_API" -eq 0 ]] && ! systemctl cat docker.service >/dev/null 2>&1; then
    echo "No se encontró docker.service. Instala Docker Engine antes de usar --docker." >&2
    exit 1
fi

PROJECT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
USER_NAME="$(id -un)"
USER_UID="$(id -u)"
USER_GID="$(id -g)"

sudo apt-get update
sudo apt-get install -y ydotoold
ydotool_version="$(dpkg-query -W -f='${Version}' ydotoold)"
if [[ "$ydotool_version" != 0.1.8-* ]]; then
    echo "Esta integración requiere ydotoold 0.1.8 de Ubuntu; versión instalada: $ydotool_version" >&2
    exit 1
fi
if [[ "$INSTALL_API" -eq 1 ]]; then
    sudo apt-get install -y python3-venv
    python3 -m venv "$PROJECT_DIR/.venv"
    "$PROJECT_DIR/.venv/bin/python" -m pip install -r "$PROJECT_DIR/requirements.txt"
fi

sudo tee /etc/systemd/system/tv-remote-ydotoold.service >/dev/null <<EOF
[Unit]
Description=TV Remote virtual input daemon
After=systemd-udevd.service

[Service]
Type=exec
ExecStartPre=/usr/sbin/modprobe uinput
ExecStart=/usr/bin/ydotoold
ExecStartPost=/bin/bash $PROJECT_DIR/scripts/allow-ydotool-socket.sh $USER_UID $USER_GID
Restart=on-failure
RestartSec=2

[Install]
WantedBy=multi-user.target
EOF

if [[ "$INSTALL_API" -eq 1 ]]; then
sudo tee /etc/systemd/system/tv-remote-api.service >/dev/null <<EOF
[Unit]
Description=TV Remote API
After=network.target tv-remote-ydotoold.service
Wants=tv-remote-ydotoold.service

[Service]
Type=exec
User=$USER_NAME
WorkingDirectory=$PROJECT_DIR
Environment=PYTHONDONTWRITEBYTECODE=1
ExecStart=$PROJECT_DIR/scripts/start-server.sh
Restart=on-failure
RestartSec=2

[Install]
WantedBy=multi-user.target
EOF
else
    sudo mkdir -p /etc/systemd/system/docker.service.d
    sudo tee /etc/systemd/system/docker.service.d/tv-remote.conf >/dev/null <<'EOF'
[Unit]
Requires=tv-remote-ydotoold.service
After=tv-remote-ydotoold.service
EOF
fi

sudo systemctl daemon-reload
sudo systemctl enable tv-remote-ydotoold.service
sudo systemctl restart tv-remote-ydotoold.service
if [[ "$INSTALL_API" -eq 1 ]]; then
    sudo systemctl enable tv-remote-api.service
    sudo systemctl restart tv-remote-api.service
else
    if systemctl cat tv-remote-api.service >/dev/null 2>&1; then
        sudo systemctl disable --now tv-remote-api.service
    fi
    sudo systemctl enable --now docker.service
fi
python3 - <<'PY'
import socket
import time

for attempt in range(5):
    try:
        with socket.socket(socket.AF_UNIX, socket.SOCK_STREAM) as client:
            client.settimeout(1)
            client.connect("/tmp/.ydotool_socket")
        print("Entrada del sistema: conectada.")
        break
    except OSError:
        pass
    time.sleep(1)
else:
    raise SystemExit("ydotoold no responde. Comprueba systemctl status tv-remote-ydotoold.")
PY
"$PROJECT_DIR/scripts/install-browser-autostart.sh"
if [[ "$INSTALL_API" -eq 1 ]]; then
    echo "API local instalada y habilitada para arrancar al encender el ordenador."
else
    echo "Entrada preparada para Docker. Inicia la API una vez con docker compose up -d --build."
fi
