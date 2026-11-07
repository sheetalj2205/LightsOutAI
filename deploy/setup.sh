#!/usr/bin/env bash
# Run ON the Vultr server (Ubuntu 24.04) as root, after copying the repo to /opt/lightsout:
#     bash /opt/lightsout/deploy/setup.sh            # serve on http://<server-ip>
#     bash /opt/lightsout/deploy/setup.sh mydomain.xyz   # serve on https://mydomain.xyz
# Safe to run again after every code update (it restarts the API).
set -euo pipefail
APP=/opt/lightsout
DOMAIN="${1:-}"

if ! command -v caddy >/dev/null; then
  apt-get update -y
  apt-get install -y python3-venv python3-pip debian-keyring debian-archive-keyring apt-transport-https curl gnupg
  curl -1sLf 'https://dl.cloudsmith.io/public/caddy/stable/gpg.key' | gpg --dearmor -o /usr/share/keyrings/caddy-stable-archive-keyring.gpg
  curl -1sLf 'https://dl.cloudsmith.io/public/caddy/stable/debian.deb.txt' > /etc/apt/sources.list.d/caddy-stable.list
  apt-get update -y && apt-get install -y caddy
fi

python3 -m venv $APP/backend/.venv
$APP/backend/.venv/bin/pip install -q -r $APP/backend/requirements.txt

[ -f $APP/.env ] || { echo "Missing $APP/.env — copy it from your laptop first (see SETUP.md)"; exit 1; }

cat > /etc/systemd/system/lightsout.service <<UNIT
[Unit]
Description=Lights Out AI API
After=network.target

[Service]
WorkingDirectory=$APP/backend
ExecStart=$APP/backend/.venv/bin/uvicorn app.main:app --host 127.0.0.1 --port 8000
Restart=always
RestartSec=2

[Install]
WantedBy=multi-user.target
UNIT

SITE="${DOMAIN:-:80}"
cat > /etc/caddy/Caddyfile <<CADDY
$SITE {
    @api path /api/* /ws /output/* /docs /openapi.json
    handle @api {
        reverse_proxy 127.0.0.1:8000
    }
    handle {
        root * $APP/frontend
        file_server
    }
}
CADDY

ufw allow 80/tcp >/dev/null 2>&1 || true
ufw allow 443/tcp >/dev/null 2>&1 || true
systemctl daemon-reload
systemctl enable --now lightsout
systemctl restart lightsout
systemctl reload caddy || systemctl restart caddy
sleep 2
curl -fsS http://127.0.0.1:8000/api/health && echo && echo "Deployed. Open http://${DOMAIN:-<server-ip>}/docs"
