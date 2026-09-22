# Iniciar TV Reomote

```bash
./scripts/setup-host.sh --docker
TV_REMOTE_UID="$(id -u)" TV_REMOTE_GID="$(id -g)" docker compose up -d --build
./scripts/start-browser.sh
./scripts/check.sh
```

Se requiere `/usr/local/bin/ydotoold` 1.x. Consulta [README.md](README.md) para instalarlo y diagnosticar Docker Snap o los permisos de Docker.
