#!/usr/bin/env bash
# Run ON YOUR LAPTOP from the repo root to send code + .env to the server and (re)start it:
#     deploy/push.sh <server-ip> [domain]
set -euo pipefail
IP="$1"; DOMAIN="${2:-}"
rsync -az --delete --exclude .git --exclude .venv --exclude __pycache__ --exclude 'backend/output/tuning' \
  ./ "root@$IP:/opt/lightsout/"
ssh "root@$IP" "bash /opt/lightsout/deploy/setup.sh $DOMAIN"
