# Deploying to `aipassport.g1orga.dev` — same pattern as Teoria / Litera

Configured exactly like the other `g1orga.dev` sites (Teoria is the
template): native Ubuntu install, **no nginx/Caddy**, public HTTPS only
via the existing Cloudflare Tunnel.

```
/opt/aipassport            app home (system user `aipassport`, .venv + .env inside)
  aipassport-api.service   Python backend  -> 127.0.0.1:8013
  aipassport-web.service   frontend (Node) -> 127.0.0.1:8014
/etc/cloudflared/config.yml
  aipassport.g1orga.dev  /api-paths -> 8013, everything else -> 8014
```

(8000/8001 are cloudflared's, Teoria is 8012 — hence 8013/8014. The setup
script refuses to start if the ports are taken.)

Unlike Teoria's single gunicorn process, this app is two processes
(Python API + Node frontend). So cloudflared routes **by path on the same
hostname**: requests to `/passports`, `/records`, `/sync`, `/verify/<code>`,
`/me/passport`, `/auth/*`, `/anchors/*`, `/admin/reset`, `/issuer`,
`/health`, `/docs` go to the API; all other paths (pages, `/assets/*`)
go to the frontend. The frontend is built with
`VITE_API_BASE_URL=https://aipassport.g1orga.dev`, so browser API calls
stay on the same origin.

## Install (once, on the server)

```bash
git clone https://github.com/G10rga/AI-Skills-Digital-Passport.git
cd AI-Skills-Digital-Passport
sudo ./deploy/setup-ubuntu.sh
```

The script (mirroring `teoria/deploy/setup-ubuntu.sh`): installs
python/venv/Node 22, creates the `aipassport` system user, rsyncs the app
to `/opt/aipassport`, builds the venv and the frontend, generates
`/opt/aipassport/.env` (mode 600) with real `ADMIN_API_KEY`/`APP_SECRET`,
installs both systemd units, checks the ports are free, starts the
services, and prints the tunnel snippet.

Then merge `deploy/cloudflared-ingress.snippet.yml` into
`/etc/cloudflared/config.yml` (**keep** your other hostnames and the
final `http_status:404` rule), and:

```bash
sudo cloudflared tunnel route dns <TUNNEL_NAME> aipassport.g1orga.dev
sudo systemctl restart cloudflared
```

Open **https://aipassport.g1orga.dev**.

## Verify on the server

```bash
curl http://127.0.0.1:8013/health
curl -o /dev/null -w "%{http_code}\n" http://127.0.0.1:8014/
sudo systemctl status aipassport-api aipassport-web
journalctl -u aipassport-api -f
```

## Update

```bash
cd /opt/aipassport && sudo ./deploy/deploy.sh   # git pull, rebuild, restart
```

## Notes

- **Back up together:** `/opt/aipassport/backend/data/passports.db` and
  `.../backend/data/issuer_key.pem` (the BTU signing key).
- **Admin security:** the frontend build bakes `VITE_ADMIN_API_KEY` from
  `/opt/aipassport/.env` so the Admin page can call the API — visible in
  page source, i.e. demo-grade like the rest of the MVP. For real
  protection, put `/admin` behind Cloudflare Access.
- Litera note: its runbook uses the same conventions (systemd service,
  host-only `.env`, secrets generated with `secrets.token_hex(32)`),
  which is what `setup-ubuntu.sh` does here.
