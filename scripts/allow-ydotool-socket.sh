#!/usr/bin/env bash
set -euo pipefail

target_uid="$1"
target_gid="$2"
socket_path="${3:-/tmp/.ydotool_socket}"
for attempt in {1..50}; do
    if [[ -S "$socket_path" ]]; then
        chown "$target_uid:$target_gid" "$socket_path"
        chmod 0600 "$socket_path"
        exit 0
    fi
    sleep 0.1
done
echo "ydotoold no creó $socket_path" >&2
exit 1
