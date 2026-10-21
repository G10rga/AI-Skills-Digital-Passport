#!/usr/bin/env bash
# Update an existing install (run as root on the server):
#   cd /opt/aipassport && sudo ./deploy/deploy.sh
set -euo pipefail
cd "$(dirname "$0")/.."
APP_HOME="$PWD"
APP_USER="${AIPASSPORT_USER:-aipassport}"
DOMAIN="${AIPASSPORT_DOMAIN:-aipassport.g1orga.dev}"

git pull
.venv/bin/pip install -q -r backend/requirements.txt

set -a; source .env; set +a
sudo -u "${APP_USER}" bash -lc "
  cd '${APP_HOME}/frontend' &&
  npm install --no-audit --no-fund &&
  VITE_API_BASE_URL='https://${DOMAIN}' VITE_ADMIN_API_KEY='${ADMIN_API_KEY:-}' \
    NITRO_PRESET=node-server npm run build"

systemctl restart aipassport-api aipassport-web
sleep 2
curl -fs http://127.0.0.1:8013/health && echo
curl -fs -o /dev/null -w "frontend: %{http_code}\n" http://127.0.0.1:8014/
echo "Done: https://${DOMAIN}"
