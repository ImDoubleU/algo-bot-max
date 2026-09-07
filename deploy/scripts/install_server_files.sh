#!/usr/bin/env bash
set -euo pipefail

domain="${1:?Usage: sudo bash deploy/scripts/install_server_files.sh bot.example.ru}"
project_dir="${PROJECT_DIR:-/opt/algo-max}"
env_file="${ENV_FILE:-/etc/algo-max/algo-max.env}"

if [[ "$EUID" -ne 0 ]]; then
    echo "Run this script as root." >&2
    exit 1
fi
if [[ "$domain" == *"://"* || "$domain" == */* ]]; then
    echo "Pass a hostname without protocol or path, for example bot.example.ru." >&2
    exit 1
fi
if [[ ! "$domain" =~ ^[A-Za-z0-9.-]+$ ]]; then
    echo "Hostname contains unsupported characters: $domain" >&2
    exit 1
fi

id algomax >/dev/null 2>&1 || useradd --system --create-home --home-dir /home/algomax --shell /bin/bash algomax
install -d -o algomax -g algomax -m 0750 \
    /etc/algo-max \
    /var/backups/algo-max \
    /var/lib/algo-max/product-media \
    "$project_dir"
install -m 0644 deploy/systemd/algo-max-api.service /etc/systemd/system/algo-max-api.service
install -m 0644 deploy/systemd/algo-max-backup.service /etc/systemd/system/algo-max-backup.service
install -m 0644 deploy/systemd/algo-max-backup.timer /etc/systemd/system/algo-max-backup.timer
install -m 0644 deploy/systemd/algo-max-birthday.service /etc/systemd/system/algo-max-birthday.service
install -m 0644 deploy/systemd/algo-max-birthday.timer /etc/systemd/system/algo-max-birthday.timer
install -m 0644 deploy/systemd/algo-max-bank.service /etc/systemd/system/algo-max-bank.service
install -m 0644 deploy/systemd/algo-max-bank.timer /etc/systemd/system/algo-max-bank.timer
install -m 0755 deploy/scripts/backup_postgres.sh /usr/local/sbin/algo-max-backup
sed "s/bot\.example\.ru/$domain/g" deploy/nginx/algo-max.conf > /etc/nginx/sites-available/algo-max
if [[ ! -f "$env_file" ]]; then
    sed "s/bot\.example\.ru/$domain/g" deploy/algo-max.env.example > "$env_file"
    chown root:algomax "$env_file"
    chmod 0640 "$env_file"
fi
ln -sfn /etc/nginx/sites-available/algo-max /etc/nginx/sites-enabled/algo-max
rm -f /etc/nginx/sites-enabled/default
systemctl daemon-reload
systemctl enable algo-max-birthday.timer
systemctl enable algo-max-bank.timer
nginx -t
systemctl reload nginx

echo "Installed systemd, nginx and environment template."
echo "Next: edit $env_file and replace every CHANGE_* value."
