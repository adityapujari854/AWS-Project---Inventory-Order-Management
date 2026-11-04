#!/usr/bin/env bash
set -euo pipefail

SOURCE_DIR="${1:?Pass a reviewed local release directory, not a URL with credentials.}"
APP_ROOT=/opt/inventoryhub
APP_DIR="$APP_ROOT/app"
ENV_FILE=/etc/inventoryhub/inventoryhub.env

test -f "$SOURCE_DIR/requirements.txt"
test -f "$SOURCE_DIR/app/main.py"
test -f "$ENV_FILE" || { echo "Create $ENV_FILE with mode 0600 before starting the service." >&2; exit 1; }

dnf install -y python3.11 nginx git rsync
id inventoryhub >/dev/null 2>&1 || useradd --system --create-home --shell /sbin/nologin inventoryhub
install -d -o inventoryhub -g inventoryhub -m 0750 "$APP_ROOT" "$APP_DIR" "$APP_ROOT/data"

rsync -a \
  --exclude '.env' --exclude '.venv' --exclude '__pycache__' --exclude '.pytest_cache' \
  --exclude '*.db' --exclude '*.sqlite3' --exclude '.git' \
  "$SOURCE_DIR/" "$APP_DIR/"

/usr/bin/python3.11 -m venv "$APP_ROOT/venv"
"$APP_ROOT/venv/bin/pip" install --upgrade pip
"$APP_ROOT/venv/bin/pip" install -r "$APP_DIR/requirements.txt"

install -m 0644 "$APP_DIR/infrastructure/ec2/nginx.conf" /etc/nginx/conf.d/inventoryhub.conf
install -m 0644 "$APP_DIR/infrastructure/ec2/inventoryhub.service" /etc/systemd/system/inventoryhub.service
chown -R inventoryhub:inventoryhub "$APP_ROOT"

nginx -t
systemctl daemon-reload
systemctl enable --now nginx
systemctl enable --now inventoryhub
curl --fail --silent --show-error http://127.0.0.1:8000/health
curl --fail --silent --show-error http://127.0.0.1/health
