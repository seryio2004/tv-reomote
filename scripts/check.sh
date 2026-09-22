#!/usr/bin/env bash
set -euo pipefail

PROJECT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
YDOTOOL_SOCKET="$PROJECT_DIR/runtime/ydotool.sock" python3 - <<'PY'
import json
import os
import shutil
import socket
import stat
import subprocess
import sys
import urllib.request

failed = False

def result(name, ok, detail):
    global failed
    print(f"{name}: {'OK' if ok else 'ERROR'} — {detail}")
    failed |= not ok

def command(*args):
    return subprocess.run(args, capture_output=True, text=True, timeout=4)

def get_json(url):
    opener = urllib.request.build_opener(urllib.request.ProxyHandler({}))
    with opener.open(url, timeout=3) as response:
        return json.load(response)

if not shutil.which("docker"):
    result("Docker", False, "docker no está instalado o no está en PATH")
else:
    try:
        proc = command("docker", "info", "--format", "{{.ServerVersion}}")
        if proc.returncode == 0:
            result("Docker", True, f"daemon accesible (versión {proc.stdout.strip()})")
        else:
            error = (proc.stderr or proc.stdout).strip()
            if "permission denied" in error.lower():
                error = "sin permiso para /var/run/docker.sock; añade el usuario al grupo docker y vuelve a iniciar sesión"
            result("Docker", False, error)
    except Exception as exc:
        result("Docker", False, str(exc))
    if shutil.which("snap"):
        try:
            snap = command("snap", "list", "docker")
            if snap.returncode == 0 and shutil.which("docker") == "/snap/bin/docker" and not os.path.realpath(os.environ["YDOTOOL_SOCKET"]).startswith(
                os.path.expanduser("~/")
            ):
                result("Docker Snap", False, "el proyecto debe estar dentro de tu carpeta personal para montar runtime/")
        except Exception:
            pass

try:
    status = get_json("http://127.0.0.1:8000/api/status")
    result("API", True, "responde en :8000" + ("; entrada conectada" if status.get("input_connected") else "; entrada desconectada"))
    if not status.get("connected"):
        print("API: no consigue conectar con Chrome por CDP")
except Exception as exc:
    result("API", False, f"no responde en :8000 ({exc})")

try:
    version = get_json("http://127.0.0.1:9222/json/version")
    result("CDP", True, version.get("Browser", "navegador desconocido"))
except Exception as exc:
    result("CDP", False, f"no responde en 127.0.0.1:9222 ({exc}); ejecuta scripts/start-browser.sh")

try:
    proc = command("systemctl", "is-active", "tv-remote-ydotoold.service")
    active = proc.returncode == 0 and proc.stdout.strip() == "active"
    binary = "/usr/local/bin/ydotoold"
    version = command(binary, "--version") if os.access(binary, os.X_OK) else None
    valid = version is not None and version.returncode == 0 and any(
        part.startswith(("1.", "v1.")) for part in (version.stdout + version.stderr).replace("-", " ").split()
    )
    result("ydotoold", active and valid,
           f"servicio {'activo' if active else 'inactivo'}; /usr/local/bin/ydotoold {'1.x' if valid else 'ausente o no es 1.x'}")
except Exception as exc:
    result("ydotoold", False, str(exc))

path = os.environ["YDOTOOL_SOCKET"]
try:
    info = os.stat(path)
    if not stat.S_ISSOCK(info.st_mode) or not os.access(path, os.W_OK):
        result("Socket", False, f"{path}; no es un socket accesible")
    else:
        with socket.socket(socket.AF_UNIX, socket.SOCK_DGRAM) as client:
            client.settimeout(1)
            client.connect(path)
        result("Socket", True, f"{path}; datagrama accesible")
except OSError as exc:
    result("Socket", False, f"{path}: {exc}")

try:
    info = os.stat("/dev/uinput")
    result("/dev/uinput", stat.S_ISCHR(info.st_mode), "dispositivo de caracteres presente" if stat.S_ISCHR(info.st_mode) else "no es un dispositivo de caracteres")
except OSError as exc:
    result("/dev/uinput", False, str(exc))

sys.exit(1 if failed else 0)
PY
