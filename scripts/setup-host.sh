#!/usr/bin/env bash
set -euo pipefail

if [[ "$(id -u)" -eq 0 ]]; then
    echo "Ejecuta este script con tu usuario normal; usará sudo para instalar el servicio." >&2
    exit 1
fi
if [[ "${1:-}" != "" && "${1:-}" != "--docker" || $# -gt 1 ]]; then
    echo "Uso: $0 [--docker]" >&2
    exit 2
fi

PROJECT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
SOCKET_PATH="$PROJECT_DIR/runtime/ydotool.sock"
YDOTOOLD=/usr/local/bin/ydotoold
USER_UID="$(id -u)"
USER_GID="$(id -g)"

if [[ ! -x "$YDOTOOLD" ]]; then
    echo "Falta $YDOTOOLD. Instala ydotool 1.x en /usr/local/bin antes de ejecutar este script." >&2
    echo "Consulta las instrucciones de compilación en README.md; no se utilizará /usr/bin/ydotoold 0.1.8." >&2
    exit 1
fi
version="$("$YDOTOOLD" --version 2>&1)" || {
    echo "No se pudo consultar la versión de $YDOTOOLD." >&2
    exit 1
}
if [[ ! "$version" =~ (^|[^[:digit:]])v?1\.[[:digit:]] ]]; then
    echo "Se requiere ydotoold 1.x en $YDOTOOLD; versión encontrada: $version" >&2
    exit 1
fi
if (( ${#SOCKET_PATH} >= 108 )); then
    echo "La ruta del socket Unix es demasiado larga: $SOCKET_PATH" >&2
    exit 1
fi

mkdir -p "$PROJECT_DIR/runtime"
chmod 0700 "$PROJECT_DIR/runtime"

# Remove Docker's old dependency before stopping the proxy it required.
sudo rm -f /etc/systemd/system/docker.service.d/tv-remote.conf \
    /etc/systemd/system/snap.docker.dockerd.service.d/tv-remote.conf
sudo systemctl daemon-reload
sudo systemctl disable --now tv-remote-socket-proxy.service tv-remote-api.service 2>/dev/null || true
sudo rm -f /etc/systemd/system/tv-remote-socket-proxy.service \
    /etc/systemd/system/tv-remote-api.service

service_file="$(mktemp)"
trap 'rm -f "$service_file"' EXIT
cat > "$service_file" <<EOF
[Unit]
Description=TV Remote virtual input daemon
After=systemd-udevd.service

[Service]
Type=exec
ExecStartPre=/usr/sbin/modprobe uinput
ExecStart=$YDOTOOLD --socket-path=$SOCKET_PATH --socket-perm=0600 --socket-own=$USER_UID:$USER_GID
Restart=on-failure
RestartSec=2

[Install]
WantedBy=multi-user.target
EOF
if ! sudo cmp -s "$service_file" /etc/systemd/system/tv-remote-ydotoold.service; then
    sudo install -m 0644 "$service_file" /etc/systemd/system/tv-remote-ydotoold.service
    service_changed=1
else
    service_changed=0
fi
sudo systemctl daemon-reload
sudo systemctl enable tv-remote-ydotoold.service
if [[ "$service_changed" -eq 1 ]] || ! systemctl is-active --quiet tv-remote-ydotoold.service; then
    sudo systemctl restart tv-remote-ydotoold.service
fi

YDOTOOL_SOCKET="$SOCKET_PATH" python3 - <<'PY'
import os
import socket
import time

path = os.environ["YDOTOOL_SOCKET"]
for _ in range(30):
    try:
        with socket.socket(socket.AF_UNIX, socket.SOCK_DGRAM) as client:
            client.connect(path)
        print("ydotoold 1.x: socket de datagramas disponible.")
        break
    except OSError:
        time.sleep(0.1)
else:
    raise SystemExit("ydotoold no responde. Comprueba systemctl status tv-remote-ydotoold.service.")
PY

"$PROJECT_DIR/scripts/install-browser-autostart.sh"
if command -v docker >/dev/null 2>&1; then
    if [[ "$(command -v docker)" == /snap/bin/docker ]] && \
        command -v snap >/dev/null 2>&1 && snap list docker >/dev/null 2>&1; then
        if ! systemctl is-active --quiet snap.docker.dockerd.service; then
            sudo snap start --enable docker.dockerd || \
                echo "Aviso: no se pudo iniciar Docker Snap (snap.docker.dockerd.service)." >&2
        fi
    elif systemctl cat docker.service >/dev/null 2>&1; then
        if ! systemctl is-active --quiet docker.service; then
            sudo systemctl start docker.service || \
                echo "Aviso: no se pudo iniciar docker.service; consulta systemctl status docker.service." >&2
        fi
    fi
    if command -v snap >/dev/null 2>&1 && snap list docker >/dev/null 2>&1 && \
        [[ "$(command -v docker)" == /snap/bin/docker ]] && [[ "$PROJECT_DIR" != "$HOME/"* ]]; then
        echo "Aviso: Docker Snap solo puede montar el proyecto dentro de $HOME. Mueve el proyecto antes de usar Compose." >&2
    fi
    docker_error="$(timeout 5s docker info --format '{{.ServerVersion}}' 2>&1)" || {
        if [[ "$docker_error" == *"permission denied"* || "$docker_error" == *"Permission denied"* ]]; then
            echo "Aviso: sin permiso para /var/run/docker.sock. Añade tu usuario al grupo docker y vuelve a iniciar sesión." >&2
        else
            echo "Aviso: Docker no responde: $docker_error" >&2
        fi
    }
else
    echo "Aviso: Docker no está instalado o no está en PATH; instala Docker Engine antes de iniciar la API." >&2
fi

echo "Host preparado. Inicia FastAPI con: TV_REMOTE_UID=$USER_UID TV_REMOTE_GID=$USER_GID docker compose up -d --build"
