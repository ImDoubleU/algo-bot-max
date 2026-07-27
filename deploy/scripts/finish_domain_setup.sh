#!/usr/bin/env bash
set -euo pipefail

domain="${1:?Usage: finish_domain_setup.sh example.ru EXPECTED_IPV4}"
expected_ipv4="${2:?Usage: finish_domain_setup.sh example.ru EXPECTED_IPV4}"
project_dir="${PROJECT_DIR:-/opt/algo-max}"
env_file="${ENV_FILE:-/etc/algo-max/algo-max.env}"

if [[ "$EUID" -ne 0 ]]; then
    echo "Run this script as root." >&2
    exit 1
fi
if [[ ! "$domain" =~ ^[A-Za-z0-9.-]+$ ]]; then
    echo "Invalid domain: $domain" >&2
    exit 1
fi
if [[ ! "$expected_ipv4" =~ ^[0-9.]+$ ]]; then
    echo "Invalid IPv4 address: $expected_ipv4" >&2
    exit 1
fi

resolved_ipv4="$(
    dig +short A "$domain" @8.8.8.8 \
        | grep -Fx "$expected_ipv4" \
        | head -n 1 \
        || true
)"
if [[ "$resolved_ipv4" != "$expected_ipv4" ]]; then
    echo "$domain is not publicly resolved to $expected_ipv4 yet." >&2
    exit 1
fi

nginx -t
curl --fail --silent --show-error \
    --resolve "$domain:80:$expected_ipv4" \
    "http://$domain/api/v1/health" \
    >/dev/null

certbot --nginx \
    --domain "$domain" \
    --redirect \
    --non-interactive \
    --agree-tos \
    --register-unsafely-without-email

systemctl restart algo-max-api.service algo-max-feedback.service

mapfile -t polling_units < <(
    systemctl list-units --all --plain --no-legend "algo-max-id-polling*" \
        | awk '{print $1}'
)
if (( ${#polling_units[@]} > 0 )); then
    systemctl stop "${polling_units[@]}"
fi

set -a
# shellcheck disable=SC1090
source "$env_file"
set +a
cd "$project_dir"
runuser -u algomax --preserve-environment -- \
    env HOME=/home/algomax \
    "$project_dir/.venv/bin/python" -m app.cli.configure_webhook

curl --fail --silent --show-error \
    --resolve "$domain:443:$expected_ipv4" \
    "https://$domain/api/v1/ready" \
    >/dev/null

if [[ "${DEPLOY_NOTIFY_CHAT_ID:-}" =~ ^[0-9]+$ ]]; then
    runuser -u algomax --preserve-environment -- \
        env HOME=/home/algomax \
        "$project_dir/.venv/bin/python" - "$DEPLOY_NOTIFY_CHAT_ID" "$domain" <<'PY'
import sys

from app.bot.max_client import MaxApiClient
from app.core.config import get_settings

chat_id = int(sys.argv[1])
domain = sys.argv[2]
settings = get_settings()
client = MaxApiClient(
    str(settings.max_bot_token),
    api_base=settings.max_api_base,
    timeout_seconds=settings.max_api_timeout_seconds,
)
client.send_message(
    chat_id=chat_id,
    text=f"Algo MAX готов к работе: https://{domain}/miniapp",
)
PY
fi

systemctl disable algo-max-domain-setup.service >/dev/null 2>&1 || true
echo "Production domain setup completed for $domain."
