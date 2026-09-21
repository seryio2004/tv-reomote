./scripts/setup-host.sh --docker
TV_REMOTE_UID="$(id -u)" TV_REMOTE_GID="$(id -g)" docker compose up -d --build