from __future__ import annotations

import json
import os
import ssl
from typing import Any
from urllib import error, parse, request

try:
    import truststore
    truststore.inject_into_ssl()
except Exception:
    pass

API_BASE = os.getenv("MAX_API_BASE", "https://platform-api2.max.ru")
UPDATE_TYPES = "message_created,bot_started,message_callback"


class MaxApiError(RuntimeError):
    pass


class MaxApiClient:
    def __init__(
        self,
        token: str,
        api_base: str = API_BASE,
        *,
        timeout_seconds: int = 15,
        poll_timeout_seconds: int = 30,
    ) -> None:
        self.token = token
        self.api_base = api_base.rstrip("/")
        self.timeout_seconds = timeout_seconds
        self.poll_timeout_seconds = poll_timeout_seconds

    def _build_url(self, path: str, params: dict[str, Any] | None = None) -> str:
        url = f"{self.api_base}{path}"
        if not params:
            return url

        clean_params = {key: value for key,
                        value in params.items() if value is not None}
        query = parse.urlencode(clean_params)
        return f"{url}?{query}" if query else url

    def _request(
        self,
        method: str,
        path: str,
        *,
        params: dict[str, Any] | None = None,
        body: dict[str, Any] | None = None,
        timeout: int | None = None,
    ) -> dict[str, Any]:
        url = self._build_url(path, params)
        headers = {
            "Authorization": self.token,
            "Accept": "application/json",
        }
        data = None

        if body is not None:
            headers["Content-Type"] = "application/json"
            data = json.dumps(body, ensure_ascii=False).encode("utf-8")

        req = request.Request(
            url, data=data, headers=headers, method=method.upper())
        ssl_context = ssl.create_default_context()

        try:
            with request.urlopen(
                req,
                timeout=timeout or self.timeout_seconds,
                context=ssl_context,
            ) as response:
                raw = response.read()
        except error.HTTPError as exc:
            detail = exc.read().decode("utf-8", errors="replace")
            raise MaxApiError(
                f"HTTP {exc.code} {exc.reason} для {method.upper()} {path}: {detail}"
            ) from exc
        except error.URLError as exc:
            raise MaxApiError(
                f"Сетевая ошибка для {method.upper()} {path}: {exc}") from exc

        if not raw:
            return {}

        try:
            return json.loads(raw.decode("utf-8"))
        except json.JSONDecodeError as exc:
            raise MaxApiError(
                f"MAX API вернул некорректный JSON: {raw!r}") from exc

    def get_me(self) -> dict[str, Any]:
        return self._request("GET", "/me")

    def get_subscriptions(self) -> dict[str, Any]:
        return self._request("GET", "/subscriptions")

    def create_subscription(
        self,
        *,
        url: str,
        update_types: list[str],
        secret: str,
    ) -> dict[str, Any]:
        return self._request(
            "POST",
            "/subscriptions",
            body={
                "url": url,
                "update_types": update_types,
                "secret": secret,
            },
        )

    def delete_subscription(self, url: str) -> dict[str, Any]:
        return self._request(
            "DELETE",
            "/subscriptions",
            params={"url": url},
        )

    def get_updates(self, marker: int | None) -> dict[str, Any]:
        request_timeout = self.poll_timeout_seconds + 10
        return self._request(
            "GET",
            "/updates",
            params={
                "marker": marker,
                "limit": 100,
                "timeout": self.poll_timeout_seconds,
                "types": UPDATE_TYPES,
            },
            timeout=request_timeout,
        )

    def send_message(
        self,
        *,
        text: str,
        attachments: list[dict[str, Any]] | None = None,
        user_id: int | None = None,
        chat_id: int | None = None,
    ) -> dict[str, Any]:
        if chat_id is None and user_id is None:
            raise ValueError("Нужен chat_id или user_id")

        body: dict[str, Any] = {"text": text}
        if attachments:
            body["attachments"] = attachments

        return self._request(
            "POST",
            "/messages",
            params={"chat_id": chat_id, "user_id": user_id},
            body=body,
        )

    def answer_callback(
        self,
        *,
        callback_id: str,
        response: Any,
        notification: str | None = None,
    ) -> dict[str, Any]:
        body: dict[str, Any] = {"message": response.as_message_body()}
        if notification:
            body["notification"] = notification
        return self._request(
            "POST",
            "/answers",
            params={"callback_id": callback_id},
            body=body,
        )


class SimulationMaxClient:
    def __init__(self) -> None:
        self.sent_messages: list[dict[str, Any]] = []

    def get_me(self) -> dict[str, Any]:
        return {
            "user_id": 0,
            "username": "LocalSimulationBot",
            "first_name": "Local Simulation",
        }

    def send_message(
        self,
        *,
        text: str,
        attachments: list[dict[str, Any]] | None = None,
        user_id: int | None = None,
        chat_id: int | None = None,
    ) -> dict[str, Any]:
        self.sent_messages.append(
            {
                "text": text,
                "attachments": attachments,
                "user_id": user_id,
                "chat_id": chat_id,
            }
        )
        return {}

    def answer_callback(
        self,
        *,
        callback_id: str,
        response: Any,
        notification: str | None = None,
    ) -> dict[str, Any]:
        message = response.as_message_body()
        self.sent_messages.append(
            {
                **message,
                "callback_id": callback_id,
                "notification": notification,
            }
        )
        return {}
