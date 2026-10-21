# Deploying to `aipassport.g1orga.dev` (Ubuntu + Cloudflare Tunnel)

Same pattern as your other `g1orga.dev` sites: **Cloudflare Tunnel is the
only public door.** Nothing on the server listens on a public port.

```
Employer / student browser
  https://aipassport.g1orga.dev
        │  Cloudflare (DNS + HTTPS, tunnel)
        ▼
  cloudflared on the Ubuntu server          (~/.cloudflared/config.yml)
        │  http://127.0.0.1:8081
        ▼
  Caddy (localhost only)                    deploy/Caddyfile
        ├── /api/*  → Python backend        127.0.0.1:8000  (systemd: aipassport-api)
        └── /*      → frontend (Node)       127.0.0.1:3001  (systemd: aipassport-web)
```

Verified locally before writing this: the frontend production build
(`NITRO_PRESET=node-server`) serves HTTP 200 from `node .output/server/index.mjs`,
and the API answers on `:8000`. The `/api` prefix exists only in public;
Caddy strips it, so the backend's routes stay exactly as documented.

## One-time setup on the server

```bash
# 1. Clone + Python deps (one venv at repo root, Python 3.11+)
git clone <this-repo> ~/ai-skills-digital-passport && cd ~/ai-skills-digital-passport
python3 -m venv .venv && .venv/bin/pip install -r backend/requirements.txt

# 2. Production secrets
cp deploy/.env.production.example deploy/.env.production
nano deploy/.env.production        # set ADMIN_API_KEY / APP_SECRET: openssl rand -hex 32

# 3. Build the frontend for the public domain (value is baked in at build time)
cd frontend && npm install
VITE_API_BASE_URL=https://aipassport.g1orga.dev/api NITRO_PRESET=node-server npm run build
cd ..

# 4. Caddy (skip if you already run it — just add deploy/Caddyfile as a site)
sudo apt install -y caddy          # or: your existing reverse proxy, same two rules
sudo cp deploy/Caddyfile /etc/caddy/Caddyfile && sudo systemctl reload caddy
#    If Caddy is not a system service for you, run it under systemd yourself
#    (caddy run --config deploy/Caddyfile) or translate the 2 rules to nginx:
#      location /api/ { proxy_pass http://127.0.0.1:8000/; }
#      location /     { proxy_pass http://127.0.0.1:3001; }

# 5. systemd services (edit User=/home paths inside first if not ~/ai-skills-digital-passport)
sudo cp deploy/aipassport-api.service deploy/aipassport-web.service /etc/systemd/system/
sudo systemctl daemon-reload
sudo systemctl enable --now aipassport-api aipassport-web

# 6. Local smoke tests (all on the server, nothing public yet)
curl http://127.0.0.1:8000/health
curl -o /dev/null -w "%{http_code}\n" http://127.0.0.1:3001/
curl -o /dev/null -w "%{http_code}\n" http://127.0.0.1:8081/
curl http://127.0.0.1:8081/api/health
```

## Route the subdomain through your existing tunnel

Exactly like your teoria site — in `~/.cloudflared/config.yml`, add the
entry from `deploy/cloudflared-ingress.yml` **above** the final
`- service: http_status:404` catch-all, then:

```bash
cloudflared tunnel route dns <YOUR_TUNNEL_NAME> aipassport.g1orga.dev
cloudflared tunnel ingress validate
sudo systemctl restart cloudflared
```

Open **https://aipassport.g1orga.dev** — frontend, sync, verification all
live under that one subdomain; `/api/*` reaches Python.

(If your tunnel is managed in the Cloudflare dashboard instead of a local
config file: Zero Trust → Networks → Tunnels → your tunnel → Public
Hostnames → Add: subdomain `aipassport`, domain `g1orga.dev`, service
`http://127.0.0.1:8081`.)

## Updating later

```bash
cd ~/ai-skills-digital-passport && git pull && bash deploy/deploy.sh
```

## Production notes / honest limitations

- **Admin endpoints:** with `ADMIN_API_KEY` set, `/passports`, `/records`,
  `/sync` need the `X-Admin-Key` header. The web Admin page can only send it
  if the same value is baked in as `VITE_ADMIN_API_KEY` at build time —
  visible to anyone who views page source, so treat it as demo-grade
  obscurity, not real security. Proper fix when you want it: put `/admin`
  (and the API paths) behind Cloudflare Access, or add real BTU admin login.
- **Keep these two files backed up together:** `backend/data/passports.db`
  and `backend/data/issuer_key.pem`. Losing the DB loses passports; losing
  the key means BTU can't produce signatures matching what was issued.
- **Do not lose the `/api` rebuild rule:** if you ever change the domain,
  rebuild the frontend with the new `VITE_API_BASE_URL` — Vite bakes it in.
- Student "login" is still the demo email login; public verification by
  code is intentionally open, per the hackathon spec.
