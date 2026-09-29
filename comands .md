TV_REMOTE_UID="$(id -u)" TV_REMOTE_GID="$(id -g)" docker compose up -d --build
./scripts/check.sh


Visualización local:
uvicorn backend.main:app --reload