from __future__ import annotations

import argparse
import json
import sys

from app.bot.max_client import UPDATE_TYPES, MaxApiClient, MaxApiError
from app.core.config import get_settings, is_placeholder


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Управление webhook-подпиской MAX")
    action = parser.add_mutually_exclusive_group()
    action.add_argument("--list", action="store_true", help="Показать текущие подписки")
    action.add_argument("--delete", action="store_true", help="Удалить MAX_WEBHOOK_URL")
    return parser.parse_args()


def main() -> int:
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")
    args = parse_args()
    settings = get_settings()
    token = settings.max_bot_token
    if is_placeholder(token):
        print("MAX_BOT_TOKEN не задан.", file=sys.stderr)
        return 1

    client = MaxApiClient(
        str(token).strip(),
        api_base=settings.max_api_base,
        timeout_seconds=settings.max_api_timeout_seconds,
        poll_timeout_seconds=settings.max_poll_timeout_seconds,
    )
    try:
        if args.list:
            result = client.get_subscriptions()
        else:
            url = settings.max_webhook_url
            if is_placeholder(url):
                print("MAX_WEBHOOK_URL не задан.", file=sys.stderr)
                return 1
            if args.delete:
                result = client.delete_subscription(str(url))
            else:
                secret = settings.max_webhook_secret
                if is_placeholder(secret):
                    print("MAX_WEBHOOK_SECRET не задан.", file=sys.stderr)
                    return 1
                result = client.create_subscription(
                    url=str(url),
                    update_types=UPDATE_TYPES.split(","),
                    secret=str(secret),
                )
        print(json.dumps(result, ensure_ascii=False, indent=2))
    except MaxApiError as exc:
        print(str(exc), file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
