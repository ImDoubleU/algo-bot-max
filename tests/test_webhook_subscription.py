"""A missing subscription is recovered, while deliberate endpoint changes are respected."""

from unittest.mock import Mock

import pytest

from app.bot.max_client import UPDATE_TYPES
from app.cli.ensure_webhook import ensure_subscription

URL = "https://bot.example.ru/api/v1/max/webhook"
SECRET = "test-only-secret"


def check(client, ready=None):
    return ensure_subscription(
        client, url=URL, secret=SECRET, ready=ready if ready is not None else lambda: True
    )


def test_existing_subscription_is_not_rewritten_or_health_checked():
    client, ready = Mock(), Mock()
    client.get_subscriptions.return_value = {"subscriptions": [{"url": URL}]}
    assert check(client, ready) == "present"
    client.create_subscription.assert_not_called()
    ready.assert_not_called()


def test_missing_subscription_is_registered_and_verified_without_deleting_anything():
    client = Mock()
    client.get_subscriptions.side_effect = [
        {"subscriptions": []},
        {"subscriptions": [{"url": URL}]},
    ]
    client.create_subscription.return_value = {"success": True}
    assert check(client) == "restored"
    client.create_subscription.assert_called_once_with(
        url=URL, secret=SECRET, update_types=UPDATE_TYPES.split(",")
    )
    client.delete_subscription.assert_not_called()


def test_another_endpoint_is_never_overwritten_or_subscribed_in_parallel():
    client = Mock()
    client.get_subscriptions.return_value = {
        "subscriptions": [{"url": "https://other.example/hook"}]
    }
    with pytest.raises(RuntimeError, match="different webhook"):
        check(client)
    client.create_subscription.assert_not_called()
    client.delete_subscription.assert_not_called()


@pytest.mark.parametrize(
    "response", [{}, {"subscriptions": None}, {"subscriptions": "bad"}, {"subscriptions": [None]}]
)
def test_invalid_api_results_cannot_trigger_a_registration(response):
    client = Mock()
    client.get_subscriptions.return_value = response
    with pytest.raises(RuntimeError, match="invalid subscription"):
        check(client)
    client.create_subscription.assert_not_called()


def test_failed_readiness_prevents_re_registration():
    client = Mock()
    client.get_subscriptions.return_value = {"subscriptions": []}
    with pytest.raises(RuntimeError, match="readiness"):
        check(client, lambda: False)
    client.create_subscription.assert_not_called()


def test_api_timeout_does_not_guess_that_a_subscription_is_missing():
    client = Mock()
    client.get_subscriptions.side_effect = TimeoutError()
    with pytest.raises(TimeoutError):
        check(client)
    client.create_subscription.assert_not_called()


@pytest.mark.parametrize("accepted,after", [(False, []), (True, [])])
def test_failed_or_unconfirmed_registration_is_reported(accepted, after):
    client = Mock()
    client.get_subscriptions.side_effect = [{"subscriptions": []}, {"subscriptions": after}]
    client.create_subscription.return_value = {"success": accepted}
    with pytest.raises(RuntimeError):
        check(client)


@pytest.mark.parametrize(
    "url", ["http://bot.example/hook", "https://user:password@bot.example/hook"]
)
def test_insecure_configurations_do_not_touch_max(url):
    client = Mock()
    with pytest.raises(ValueError):
        ensure_subscription(client, url=url, secret=SECRET, ready=lambda: True)
    client.get_subscriptions.assert_not_called()
