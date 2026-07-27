#!/usr/bin/env bash
set -euo pipefail

project_dir="${PROJECT_DIR:-/opt/algo-max}"
env_file="${ENV_FILE:-/etc/algo-max/algo-max.env}"

if [[ "$EUID" -ne 0 ]]; then
    echo "Run this script as root." >&2
    exit 1
fi

cd "$project_dir"
set -a
# shellcheck disable=SC1090
source "$env_file"
set +a
sudo -u algomax git -C "$project_dir" pull --ff-only
sudo -u algomax "$project_dir/.venv/bin/pip" install -r "$project_dir/requirements-prod.txt"
install -m 0644 deploy/systemd/algo-max-api.service /etc/systemd/system/algo-max-api.service
install -m 0644 deploy/systemd/algo-max-feedback.service /etc/systemd/system/algo-max-feedback.service
install -m 0644 deploy/systemd/algo-max-backup.service /etc/systemd/system/algo-max-backup.service
install -m 0644 deploy/systemd/algo-max-backup.timer /etc/systemd/system/algo-max-backup.timer
install -m 0755 deploy/scripts/backup_postgres.sh /usr/local/sbin/algo-max-backup
systemctl daemon-reload
sudo --preserve-env -u algomax "$project_dir/.venv/bin/python" -m alembic upgrade head
sudo --preserve-env -u algomax "$project_dir/.venv/bin/python" -m app.cli.doctor --production
systemctl restart algo-max-api algo-max-feedback
sleep 2
curl --fail --silent --show-error http://127.0.0.1:8000/api/v1/health
systemctl --no-pager --full status algo-max-api
