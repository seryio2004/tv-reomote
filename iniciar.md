Desde la carpeta del proyecto, con tu usuario normal:

```bash
./scripts/setup-host.sh --docker
TV_REMOTE_UID="$(id -u)" TV_REMOTE_GID="$(id -g)" docker compose up -d --build
./scripts/check.sh
```

El instalador admite Docker instalado mediante Snap. Si no tienes permiso para usar `docker compose`, configura el acceso de tu usuario según el apartado «Arranque con Docker Compose» de README.md.
