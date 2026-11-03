"""Restore a missing MAX subscription without restarting the app or changing its DB."""

import json
import logging
from urllib.parse import urlsplit
from urllib.request import urlopen

from app.bot.max_client import UPDATE_TYPES, MaxApiClient
from app.core.config import get_settings, is_placeholder

logger = logging.getLogger(__name__)


def subscriptions(client):
    rows = client.get_subscriptions().get("subscriptions")
    if not isinstance(rows, list) or any(not isinstance(row, dict) for row in rows):
        raise RuntimeError("MAX returned an invalid subscription list")
    return rows


def ensure_subscription(client, *, url, secret, ready):
    parsed = urlsplit(url)
    if parsed.scheme != "https" or not parsed.hostname or parsed.username or parsed.password:
        raise ValueError("A public HTTPS webhook URL is required")
    if is_placeholder(secret):
        raise ValueError("Webhook secret is required")
    rows = subscriptions(client)
    if any(row.get("url") == url for row in rows):
        return "present"
    if rows:
        # A deliberate switch to another endpoint must not create duplicate delivery.
        raise RuntimeError("A different webhook subscription exists; manual review is required")
    if not ready():
        raise RuntimeError("Application readiness check failed; subscription was not changed")
    response = client.create_subscription(
        url=url, secret=secret, update_types=UPDATE_TYPES.split(",")
    )
    if response.get("success") is not True:
        raise RuntimeError("MAX did not confirm webhook registration")
    if not any(row.get("url") == url for row in subscriptions(client)):
        raise RuntimeError("Webhook registration is not visible in MAX")
    return "restored"


def public_health(url):
    parsed = urlsplit(url)
    health_url = f"{parsed.scheme}://{parsed.netloc}/api/v1/health"
    with urlopen(health_url, timeout=10) as response:
        return response.status == 200 and json.load(response).get("status") == "ok"


def main():
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
    settings = get_settings()
    if settings.bot_mode.strip().lower() != "webhook":
        return 0
    if any(
        is_placeholder(value)
        for value in (
            settings.max_bot_token,
            settings.max_webhook_url,
            settings.max_webhook_secret,
        )
    ):
        logger.error("MAX webhook configuration is incomplete")
        return 1
    client = MaxApiClient(
        str(settings.max_bot_token).strip(), api_base=settings.max_api_base, timeout_seconds=10
    )
    try:
        status = ensure_subscription(
            client,
            url=str(settings.max_webhook_url),
            secret=str(settings.max_webhook_secret),
            ready=lambda: public_health(str(settings.max_webhook_url)),
        )
    except Exception as error:
        # Never include API responses, environment values or credentials in the journal.
        logger.error("MAX webhook check failed error_type=%s", type(error).__name__)
        return 1
    if status == "restored":
        logger.warning("MAX webhook subscription was missing and has been restored")
    else:
        logger.info("MAX webhook subscription is present")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
