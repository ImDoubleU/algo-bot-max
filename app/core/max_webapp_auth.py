from __future__ import annotations

import hashlib
import hmac
import json
import time
from dataclasses import dataclass
from urllib import parse


class MaxWebAppAuthError(ValueError):
    pass


@dataclass(frozen=True, slots=True)
class MaxWebAppIdentity:
    max_user_id: int
    auth_date: int


def verify_max_webapp_data(
    init_data: str,
    *,
    bot_token: str,
    max_age_seconds: int,
    now: int | None = None,
) -> MaxWebAppIdentity:
    try:
        pairs = parse.parse_qsl(
            init_data,
            keep_blank_values=True,
            strict_parsing=True,
        )
    except ValueError as exc:
        raise MaxWebAppAuthError("Некорректные данные запуска MAX") from exc

    keys = [key for key, _ in pairs]
    if not pairs or len(keys) != len(set(keys)):
        raise MaxWebAppAuthError("Некорректные данные запуска MAX")

    values = dict(pairs)
    supplied_hash = values.pop("hash", "")
    if len(supplied_hash) != 64:
        raise MaxWebAppAuthError("Подпись MAX отсутствует")

    check_string = "\n".join(
        f"{key}={value}" for key, value in sorted(values.items())
    )
    secret_key = hmac.new(
        b"WebAppData",
        bot_token.encode("utf-8"),
        hashlib.sha256,
    ).digest()
    expected_hash = hmac.new(
        secret_key,
        check_string.encode("utf-8"),
        hashlib.sha256,
    ).hexdigest()
    if not hmac.compare_digest(supplied_hash, expected_hash):
        raise MaxWebAppAuthError("Подпись MAX не прошла проверку")

    try:
        auth_date = int(values["auth_date"])
        user = json.loads(values["user"])
        max_user_id = int(user["id"])
    except (KeyError, TypeError, ValueError, json.JSONDecodeError) as exc:
        raise MaxWebAppAuthError("В данных MAX отсутствует пользователь") from exc
    if max_user_id < 1:
        raise MaxWebAppAuthError("Некорректный MAX user_id")

    current_time = int(time.time() if now is None else now)
    if auth_date > current_time + 60:
        raise MaxWebAppAuthError("Некорректное время запуска MAX")
    if current_time - auth_date > max_age_seconds:
        raise MaxWebAppAuthError("Сессия MAX устарела. Откройте mini-app заново")

    return MaxWebAppIdentity(
        max_user_id=max_user_id,
        auth_date=auth_date,
    )
