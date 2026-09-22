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
PROJECT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
USER_NAME="$(id -un)"
USER_UID="$(id -u)"
USER_GID="$(id -g)"
SOCKET_PATH="$PROJECT_DIR/runtime/ydotool.sock"
HOST_SOCKET_PATH=/tmp/.ydotool_socket

if [[ "$INSTALL_API" -eq 0 ]]; then
    if [[ "$(command -v docker || true)" == /snap/bin/docker ]] && snap list docker >/dev/null 2>&1; then
        DOCKER_SERVICE=snap.docker.dockerd.service
        DOCKER_SNAP=1
    elif systemctl cat docker.service >/dev/null 2>&1; then
        DOCKER_SERVICE=docker.service
        DOCKER_SNAP=0
    elif systemctl cat snap.docker.dockerd.service >/dev/null 2>&1; then
        DOCKER_SERVICE=snap.docker.dockerd.service
        DOCKER_SNAP=1
    else
        echo "No se encontró el servicio de Docker Engine ni el de Docker Snap." >&2
        exit 1
    fi
    if [[ "$DOCKER_SNAP" -eq 1 && "$PROJECT_DIR" != "$HOME/"* ]]; then
        echo "Docker Snap necesita que el proyecto esté dentro de tu carpeta personal: $HOME" >&2
        exit 1
    fi
fi

mkdir -p "$PROJECT_DIR/runtime"
chmod 0700 "$PROJECT_DIR/runtime"

sudo apt-get update
installed_ydotool_version="$(dpkg-query -W -f='${Version}' ydotool 2>/dev/null || true)"
ydotoold_candidate="$(LC_ALL=C apt-cache policy ydotoold 2>/dev/null | awk '/Candidate:/ {print $2}' || true)"
if [[ "$installed_ydotool_version" != 1.* && -n "$ydotoold_candidate" && "$ydotoold_candidate" != "(none)" ]]; then
    sudo apt-get install -y ydotoold
    ydotool_version="$(dpkg-query -W -f='${Version}' ydotoold)"
    if [[ "$ydotool_version" != 0.1.8-* ]]; then
        echo "Versión de ydotoold no compatible: $ydotool_version" >&2
        exit 1
    fi
    SOCKET_TYPE=stream
    YDOTOOLD_COMMAND=/usr/bin/ydotoold
else
    sudo apt-get install -y ydotool
    ydotool_version="$(dpkg-query -W -f='${Version}' ydotool)"
    if [[ "$ydotool_version" != 1.* ]]; then
        echo "Versión de ydotool no compatible: $ydotool_version" >&2
        exit 1
    fi
    SOCKET_TYPE=dgram
    HOST_SOCKET_PATH="$SOCKET_PATH"
    YDOTOOLD_COMMAND="/usr/bin/ydotoold --socket-path=$SOCKET_PATH --socket-perm=0600"
    if (( ${#SOCKET_PATH} >= 108 )); then
        echo "La ruta del socket Unix es demasiado larga: $SOCKET_PATH" >&2
        exit 1
    fi
fi
if [[ "$INSTALL_API" -eq 0 && "$SOCKET_TYPE" == stream ]]; then
    sudo apt-get install -y socat
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
ExecStart=$YDOTOOLD_COMMAND
ExecStartPost=/bin/bash $PROJECT_DIR/scripts/allow-ydotool-socket.sh $USER_UID $USER_GID $HOST_SOCKET_PATH
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
Environment=YDOTOOL_SOCKET=$HOST_SOCKET_PATH
ExecStart=$PROJECT_DIR/scripts/start-server.sh
Restart=on-failure
RestartSec=2

[Install]
WantedBy=multi-user.target
EOF
else
if [[ "$SOCKET_TYPE" == stream ]]; then
sudo tee /etc/systemd/system/tv-remote-socket-proxy.service >/dev/null <<EOF
[Unit]
Description=TV Remote socket bridge for Docker
Requires=tv-remote-ydotoold.service
After=tv-remote-ydotoold.service

[Service]
Type=exec
User=$USER_NAME
WorkingDirectory=$PROJECT_DIR
ExecStartPre=/bin/rm -f $SOCKET_PATH
ExecStart=/usr/bin/socat UNIX-LISTEN:$SOCKET_PATH,mode=0600,fork UNIX-CONNECT:/tmp/.ydotool_socket
Restart=on-failure
RestartSec=2

[Install]
WantedBy=multi-user.target
EOF
    DOCKER_DEPENDENCY=tv-remote-socket-proxy.service
else
    DOCKER_DEPENDENCY=tv-remote-ydotoold.service
fi
    sudo mkdir -p "/etc/systemd/system/$DOCKER_SERVICE.d"
    sudo tee "/etc/systemd/system/$DOCKER_SERVICE.d/tv-remote.conf" >/dev/null <<EOF
[Unit]
Requires=$DOCKER_DEPENDENCY
After=$DOCKER_DEPENDENCY
EOF
fi

sudo systemctl daemon-reload
if [[ "$SOCKET_TYPE" == dgram ]] && systemctl cat tv-remote-socket-proxy.service >/dev/null 2>&1; then
    sudo systemctl disable --now tv-remote-socket-proxy.service
fi
sudo systemctl enable tv-remote-ydotoold.service
sudo systemctl restart tv-remote-ydotoold.service
if [[ "$INSTALL_API" -eq 1 ]]; then
    sudo systemctl enable tv-remote-api.service
    sudo systemctl restart tv-remote-api.service
else
    if systemctl cat tv-remote-api.service >/dev/null 2>&1; then
        sudo systemctl disable --now tv-remote-api.service
    fi
    if [[ "$SOCKET_TYPE" == stream ]]; then
        sudo systemctl enable --now tv-remote-socket-proxy.service
    fi
    if [[ "$DOCKER_SNAP" -eq 1 ]]; then
        sudo snap start --enable docker.dockerd
    else
        sudo systemctl enable --now docker.service
    fi
fi
YDOTOOL_SOCKET="$HOST_SOCKET_PATH" YDOTOOL_SOCKET_TYPE="$SOCKET_TYPE" python3 - <<'PY'
import socket
import time
import os

socket_type = socket.SOCK_DGRAM if os.environ["YDOTOOL_SOCKET_TYPE"] == "dgram" else socket.SOCK_STREAM
for attempt in range(5):
    try:
        with socket.socket(socket.AF_UNIX, socket_type) as client:
            client.settimeout(1)
            client.connect(os.environ["YDOTOOL_SOCKET"])
        print("Entrada del sistema: conectada.")
        break
    except OSError:
        pass
    time.sleep(1)
else:
    raise SystemExit("ydotoold no responde. Comprueba systemctl status tv-remote-ydotoold.")
PY
if [[ "$INSTALL_API" -eq 0 && "$SOCKET_TYPE" == stream ]]; then
    YDOTOOL_SOCKET="$SOCKET_PATH" python3 - <<'PY'
import os
import socket

with socket.socket(socket.AF_UNIX, socket.SOCK_STREAM) as client:
    client.settimeout(2)
    client.connect(os.environ["YDOTOOL_SOCKET"])
print("Puente de entrada para Docker: conectado.")
PY
fi
"$PROJECT_DIR/scripts/install-browser-autostart.sh"
if [[ "$INSTALL_API" -eq 1 ]]; then
    echo "API local instalada y habilitada para arrancar al encender el ordenador."
else
    echo "Entrada preparada para Docker. Inicia la API una vez con docker compose up -d --build."
fi
