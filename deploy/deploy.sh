#!/usr/bin/env bash
# Run ON the Ubuntu server, from the repo root, after `git pull`.
# (Re)builds everything and restarts the two systemd services.
set -euo pipefail
cd "$(dirname "$0")/.."
REPO="$PWD"
DOMAIN="https://aipassport.g1orga.dev"

echo "==> Python backend deps (single venv at repo root: .venv)"
[ -d .venv ] || python3 -m venv .venv
.venv/bin/pip install -q -r backend/requirements.txt

echo "==> Building frontend (API base = $DOMAIN/api, baked in at build time)"
cd frontend
npm install --no-audit --no-fund
# Optional: only if deploy/.env.production sets ADMIN_API_KEY and you accept
# the demo trade-off (see README) — VITE_ADMIN_API_KEY=$ADMIN_API_KEY
VITE_API_BASE_URL="$DOMAIN/api" NITRO_PRESET=node-server npm run build
cd "$REPO"

echo "==> Restarting services"
sudo systemctl restart aipassport-api aipassport-web
sleep 2
curl -fs http://127.0.0.1:8000/health && echo
curl -fs -o /dev/null -w "frontend: %{http_code}\n" http://127.0.0.1:3001/
curl -fs -o /dev/null -w "proxy:    %{http_code}\n" http://127.0.0.1:8081/
echo "Done. Public check: $DOMAIN"
