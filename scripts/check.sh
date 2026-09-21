#!/usr/bin/env bash
set -u
echo "== API =="; curl -fsS http://127.0.0.1:8000/api/status || true; echo; echo "== Chrome DevTools =="; curl -fsS http://127.0.0.1:9222/json/version || true; echo
