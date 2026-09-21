#!/usr/bin/env bash
set -euo pipefail

python3 - <<'PY'
import json
import sys
import urllib.request

opener = urllib.request.build_opener(urllib.request.ProxyHandler({}))

def get_json(url):
    with opener.open(url, timeout=3) as response:
        return json.load(response)

api_reachable = False
api_ok = False
cdp_ok = False

try:
    status = get_json("http://127.0.0.1:8000/api/status")
    api_reachable = True
    api_ok = status.get("connected") is True
    print("API: activa; Chrome " + ("conectado" if api_ok else "desconectado"))
except Exception as exc:
    print(f"API: no responde ({exc})")

try:
    version = get_json("http://127.0.0.1:9222/json/version")
    cdp_ok = True
    print("CDP: activo (" + version.get("Browser", "navegador desconocido") + ")")
except Exception as exc:
    print(f"CDP: no responde ({exc})")

if not cdp_ok:
    print("Inicia Chrome/Chromium con ./scripts/start-browser.sh.")
if not api_reachable:
    print("Comprueba que Docker esté iniciado y ejecuta docker compose up -d --build.")
elif not api_ok and cdp_ok:
    print("La API responde, pero no se conecta a Chrome; comprueba BROWSER_CDP_URL.")
if not api_ok or not cdp_ok:
    sys.exit(1)
PY
