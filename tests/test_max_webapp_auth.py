from __future__ import annotations

import hashlib
import hmac
import json
from urllib import parse

import pytest

from app.core.max_webapp_auth import MaxWebAppAuthError, verify_max_webapp_data


def signed_init_data(*, user_id: int, auth_date: int, bot_token: str) -> str:
    values = {
        "auth_date": str(auth_date),
        "query_id": "query-1",
        "user": json.dumps({"id": user_id}, separators=(",", ":")),
    }
    check_string = "\n".join(
        f"{key}={value}" for key, value in sorted(values.items())
    )
    secret_key = hmac.new(
        b"WebAppData",
        bot_token.encode("utf-8"),
        hashlib.sha256,
    ).digest()
    values["hash"] = hmac.new(
        secret_key,
        check_string.encode("utf-8"),
        hashlib.sha256,
    ).hexdigest()
    return parse.urlencode(values)


def test_max_webapp_identity_comes_from_signed_launch_data() -> None:
    init_data = signed_init_data(
        user_id=53364725,
        auth_date=1_800_000_000,
        bot_token="bot-token",
    )

    identity = verify_max_webapp_data(
        init_data,
        bot_token="bot-token",
        max_age_seconds=3600,
        now=1_800_000_030,
    )

    assert identity.max_user_id == 53364725


def test_max_webapp_rejects_changed_user_id() -> None:
    init_data = signed_init_data(
        user_id=53364725,
        auth_date=1_800_000_000,
        bot_token="bot-token",
    ).replace("53364725", "259570124")

    with pytest.raises(MaxWebAppAuthError, match="Подпись MAX"):
        verify_max_webapp_data(
            init_data,
            bot_token="bot-token",
            max_age_seconds=3600,
            now=1_800_000_030,
        )
