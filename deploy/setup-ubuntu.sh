#!/usr/bin/env bash
# Native Ubuntu install, same pattern as Teoria: app in /opt/aipassport,
# dedicated system user, .venv + .env in the app home, systemd services on
# loopback ports 8013 (API) / 8014 (frontend). Public HTTPS is Cloudflare
# Tunnel (not nginx/Caddy). Run from the cloned repo as root:
#
#   sudo ./deploy/setup-ubuntu.sh
#
set -euo pipefail

if [[ "${EUID}" -ne 0 ]]; then
  echo "run as root: sudo $0" >&2
  exit 1
fi

REPO="$(cd "$(dirname "$0")/.." && pwd)"
APP_USER="${AIPASSPORT_USER:-aipassport}"
APP_HOME="${AIPASSPORT_HOME:-/opt/aipassport}"
API_PORT="${AIPASSPORT_API_PORT:-8013}"
WEB_PORT="${AIPASSPORT_WEB_PORT:-8014}"
DOMAIN="${AIPASSPORT_DOMAIN:-aipassport.g1orga.dev}"

systemctl stop aipassport-api.service aipassport-web.service 2>/dev/null || true

export DEBIAN_FRONTEND=noninteractive
apt-get update -y
apt-get install -y python3 python3-venv python3-pip git rsync curl postgresql postgresql-contrib
systemctl enable --now postgresql

# Frontend needs Node >= 20 (Vite). Install Node 22 if missing/too old.
if ! command -v node >/dev/null || [[ "$(node -v | sed 's/v//;s/\..*//')" -lt 20 ]]; then
  curl -fsSL https://deb.nodesource.com/setup_22.x | bash -
  apt-get install -y nodejs
fi

if ! id -u "${APP_USER}" >/dev/null 2>&1; then
  useradd --system --home-dir "${APP_HOME}" --create-home --shell /usr/sbin/nologin "${APP_USER}"
fi

mkdir -p "${APP_HOME}"
if [[ "${REPO}" != "${APP_HOME}" ]]; then
  rsync -a --delete \
    --exclude '.venv' --exclude 'frontend/node_modules' --exclude 'frontend/.output' \
    --exclude 'backend/data' --exclude '.env' --exclude 'deploy/.env.production' \
    "${REPO}/" "${APP_HOME}/"
fi
chown -R "${APP_USER}:${APP_USER}" "${APP_HOME}"

if [[ ! -d "${APP_HOME}/.venv" ]]; then
  sudo -u "${APP_USER}" python3 -m venv "${APP_HOME}/.venv"
fi
sudo -u "${APP_USER}" "${APP_HOME}/.venv/bin/pip" install --upgrade pip
sudo -u "${APP_USER}" "${APP_HOME}/.venv/bin/pip" install -r "${APP_HOME}/backend/requirements.txt"

# Production secrets at /opt/aipassport/.env (same convention as Teoria).
if [[ ! -f "${APP_HOME}/.env" ]]; then
  ADMIN_KEY="$(python3 -c 'import secrets; print(secrets.token_hex(32))')"
  APP_SECRET="$(python3 -c 'import secrets; print(secrets.token_hex(32))')"
  install -o "${APP_USER}" -g "${APP_USER}" -m 600 /dev/null "${APP_HOME}/.env"
  cat > "${APP_HOME}/.env" <<EOF
HOST=127.0.0.1
PORT=${API_PORT}
ADMIN_API_KEY=${ADMIN_KEY}
APP_SECRET=${APP_SECRET}
ALLOW_RESET=false
ALLOW_DEV_EMAIL_AUTH=true
CORS_ORIGINS=https://${DOMAIN}
SHEET_SOURCE=seed
ANCHOR_MODE=simulated
EOF
  echo "Generated ${APP_HOME}/.env (ADMIN_API_KEY inside — needed below for the frontend build)"
fi

# Verification emails: codes are only sent by email, never returned by the
# API. Fill in SMTP_* in /opt/aipassport/.env (Gmail: smtp.gmail.com:587 +
# an App Password) or sign-in stays disabled with a clear 503 message.
if ! grep -q "ALLOW_DEV_VERIFICATION_CODES" "${APP_HOME}/.env"; then
  cat >> "${APP_HOME}/.env" <<'EOF'
ALLOW_DEV_VERIFICATION_CODES=false
# SMTP_HOST=smtp.gmail.com
# SMTP_PORT=587
# SMTP_USER=
# SMTP_PASSWORD=
# SMTP_FROM=
EOF
fi

# Self-hosted PostgreSQL (same convention as Teoria): dedicated role+db,
# DATABASE_URL in /opt/aipassport/.env. Idempotent; safe to re-run.
set -a; source "${APP_HOME}/.env"; set +a
if [[ -z "${DATABASE_URL:-}" ]]; then
  DB_PASS="$(python3 -c 'import secrets; print(secrets.token_urlsafe(24))')"
  sudo -u postgres psql -v ON_ERROR_STOP=1 <<SQL
DO \$\$
BEGIN
  IF NOT EXISTS (SELECT FROM pg_roles WHERE rolname = '${APP_USER}') THEN
    CREATE ROLE ${APP_USER} LOGIN PASSWORD '${DB_PASS}';
  ELSE
    ALTER ROLE ${APP_USER} LOGIN PASSWORD '${DB_PASS}';
  END IF;
END
\$\$;
SELECT 'CREATE DATABASE ${APP_USER} OWNER ${APP_USER}'
WHERE NOT EXISTS (SELECT FROM pg_database WHERE datname = '${APP_USER}')\gexec
GRANT ALL PRIVILEGES ON DATABASE ${APP_USER} TO ${APP_USER};
SQL
  sudo -u postgres psql -d "${APP_USER}" -v ON_ERROR_STOP=1 \
    -c "GRANT ALL ON SCHEMA public TO ${APP_USER}; ALTER SCHEMA public OWNER TO ${APP_USER};"
  DATABASE_URL="postgresql://${APP_USER}:${DB_PASS}@127.0.0.1:5432/${APP_USER}"
  echo "DATABASE_URL=${DATABASE_URL}" >> "${APP_HOME}/.env"
  chown "${APP_USER}:${APP_USER}" "${APP_HOME}/.env"; chmod 600 "${APP_HOME}/.env"
  echo "PostgreSQL ready: database '${APP_USER}' on 127.0.0.1:5432"
fi

# If a previous SQLite install has real data, copy it into Postgres
# (idempotent, leaves the .db file untouched as backup/rollback).
if [[ -f "${APP_HOME}/backend/data/passports.db" ]]; then
  echo "Migrating existing SQLite data to PostgreSQL (if any)..."
  sudo -u "${APP_USER}" env DATABASE_URL="${DATABASE_URL}" \
    "${APP_HOME}/.venv/bin/python" "${APP_HOME}/backend/tools/migrate_sqlite_to_postgres.py" \
    "${APP_HOME}/backend/data/passports.db" || \
    echo "note: SQLite migration skipped/failed — Postgres will seed fresh from records.json"
fi

# Frontend build. The API base is baked in at build time; API paths share
# the public subdomain and cloudflared routes them to 8013 by path.
# VITE_ADMIN_API_KEY lets the Admin page send X-Admin-Key (demo-grade:
# it is visible in page source — protect /admin with Cloudflare Access
# when you want real admin security).
set -a; source "${APP_HOME}/.env"; set +a
sudo -u "${APP_USER}" bash -lc "
  cd '${APP_HOME}/frontend' &&
  npm install --no-audit --no-fund &&
  VITE_API_BASE_URL='https://${DOMAIN}' VITE_ADMIN_API_KEY='${ADMIN_API_KEY:-}' \
    NITRO_PRESET=node-server npm run build"

for UNIT in aipassport-api aipassport-web; do
  sed \
    -e "s|/opt/aipassport|${APP_HOME}|g" \
    -e "s|User=aipassport|User=${APP_USER}|g" \
    -e "s|Group=aipassport|Group=${APP_USER}|g" \
    -e "s|PORT=8014|PORT=${WEB_PORT}|" \
    "${APP_HOME}/deploy/${UNIT}.service" > "/etc/systemd/system/${UNIT}.service"
done

for P in "${API_PORT}" "${WEB_PORT}"; do
  if ss -lnt | awk '{print $4}' | grep -qE "[:.]${P}\$"; then
    echo "port ${P} is already in use. Set AIPASSPORT_API_PORT/AIPASSPORT_WEB_PORT to free loopback ports (not 8000/8001)." >&2
    ss -lntp | grep -E "[:.]${P}\b" || true
    exit 1
  fi
done

systemctl daemon-reload
systemctl enable --now aipassport-api.service aipassport-web.service

sleep 2
echo
echo "AI Passport API is listening on 127.0.0.1:${API_PORT}"
echo "Check: curl -sS http://127.0.0.1:${API_PORT}/health"
echo "Frontend is listening on 127.0.0.1:${WEB_PORT}"
echo "Check: curl -sS -o /dev/null -w '%{http_code}\n' http://127.0.0.1:${WEB_PORT}/"
echo
echo "Cloudflare Tunnel — merge into /etc/cloudflared/config.yml (keep your other hostnames):"
echo "  - hostname: ${DOMAIN}"
echo "    path: ^/(passports(/.*)?|records|sync|verify/.*|me/.*|auth/.*|skills/.*|skill-requests(/.*)?|passport-requests|admin/.*|anchors/.*|issuer|health|docs|openapi\.json)$"
echo "    service:  http://127.0.0.1:${API_PORT}"
echo "  - hostname: ${DOMAIN}"
echo "    service:  http://127.0.0.1:${WEB_PORT}"
echo
echo "Then:"
echo "  sudo cloudflared tunnel route dns <TUNNEL_NAME> ${DOMAIN}"
echo "  sudo systemctl restart cloudflared"
echo
echo "Application files: ${APP_HOME}"
echo "Secrets file:      ${APP_HOME}/.env"
