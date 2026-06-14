from __future__ import annotations

import argparse
import json
import os
import sys
import time
from pathlib import Path
from typing import Any
from urllib import error, parse, request


API_BASE = os.getenv("MAX_API_BASE", "https://platform-api.max.ru")
MARKER_FILE = Path(__file__).with_suffix(".marker")
UPDATE_TYPES = "message_created,bot_started"


class MaxApiError(RuntimeError):
    pass


class MaxApiClient:
    def __init__(self, token: str, api_base: str = API_BASE) -> None:
        self.token = token
        self.api_base = api_base.rstrip("/")

    def _build_url(self, path: str, params: dict[str, Any] | None = None) -> str:
        url = f"{self.api_base}{path}"
        if not params:
            return url

        clean_params: dict[str, Any] = {}
        for key, value in params.items():
            if value is None:
                continue
            clean_params[key] = value

        query = parse.urlencode(clean_params)
        return f"{url}?{query}" if query else url

    def _request(
        self,
        method: str,
        path: str,
        *,
        params: dict[str, Any] | None = None,
        body: dict[str, Any] | None = None,
        timeout: int = 30,
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

        req = request.Request(url, data=data, headers=headers, method=method.upper())

        try:
            with request.urlopen(req, timeout=timeout) as response:
                raw = response.read()
        except error.HTTPError as exc:
            detail = exc.read().decode("utf-8", errors="replace")
            raise MaxApiError(
                f"HTTP {exc.code} {exc.reason} for {method.upper()} {path}: {detail}"
            ) from exc
        except error.URLError as exc:
            raise MaxApiError(f"Network error for {method.upper()} {path}: {exc}") from exc

        if not raw:
            return {}

        try:
            return json.loads(raw.decode("utf-8"))
        except json.JSONDecodeError as exc:
            raise MaxApiError(f"Invalid JSON from {method.upper()} {path}: {raw!r}") from exc

    def get_me(self) -> dict[str, Any]:
        return self._request("GET", "/me", timeout=15)

    def get_subscriptions(self) -> dict[str, Any]:
        return self._request("GET", "/subscriptions", timeout=15)

    def delete_subscription(self, url: str) -> dict[str, Any]:
        return self._request(
            "DELETE",
            "/subscriptions",
            params={"url": url},
            timeout=15,
        )

    def get_updates(self, marker: int | None) -> dict[str, Any]:
        return self._request(
            "GET",
            "/updates",
            params={
                "marker": marker,
                "limit": 100,
                "timeout": 30,
                "types": UPDATE_TYPES,
            },
            timeout=40,
        )

    def send_message(
        self,
        *,
        text: str,
        user_id: int | None = None,
        chat_id: int | None = None,
    ) -> dict[str, Any]:
        if chat_id is None and user_id is None:
            raise ValueError("chat_id or user_id is required")

        return self._request(
            "POST",
            "/messages",
            params={"chat_id": chat_id, "user_id": user_id},
            body={"text": text},
            timeout=15,
        )


class LongPollingBot:
    def __init__(self, client: MaxApiClient) -> None:
        self.client = client
        self.bot_info = self.client.get_me()
        self.bot_user_id = self.bot_info.get("user_id")
        self.running = True

    def load_marker(self) -> int | None:
        if not MARKER_FILE.exists():
            return None

        value = MARKER_FILE.read_text(encoding="utf-8").strip()
        if not value:
            return None

        try:
            return int(value)
        except ValueError:
            return None

    def save_marker(self, marker: int | None) -> None:
        if marker is None:
            return
        MARKER_FILE.write_text(str(marker), encoding="utf-8")

    def reset_marker(self) -> None:
        if MARKER_FILE.exists():
            MARKER_FILE.unlink()

    def ensure_polling_available(self, *, drop_webhooks: bool) -> None:
        data = self.client.get_subscriptions()
        subscriptions = data.get("subscriptions") or []

        if not subscriptions:
            return

        urls = [item.get("url") for item in subscriptions if item.get("url")]

        if drop_webhooks:
            for url in urls:
                self.client.delete_subscription(url)
                print(f"[info] Removed webhook subscription: {url}")
            return

        joined = ", ".join(urls) if urls else "unknown"
        raise SystemExit(
            "У бота активен webhook, поэтому long polling не заработает.\n"
            f"Текущие подписки: {joined}\n"
            "Либо удалите их в MAX, либо запустите:\n"
            "python main_bot.py --drop-webhooks"
        )

    def target_from_message(self, message: dict[str, Any]) -> tuple[int | None, int | None]:
        recipient = message.get("recipient") or {}
        sender = message.get("sender") or {}

        chat_id = recipient.get("chat_id")
        user_id = recipient.get("user_id") or sender.get("user_id")
        return chat_id, user_id

    def send_reply(
        self,
        *,
        text: str,
        chat_id: int | None = None,
        user_id: int | None = None,
    ) -> None:
        self.client.send_message(text=text, chat_id=chat_id, user_id=user_id)

    def help_text(self) -> str:
        return (
            "Привет! Я тестовый MAX-бот на long polling.\n\n"
            "Команды:\n"
            "/start - приветствие\n"
            "/help - список команд\n"
            "/ping - проверка связи\n"
            "/id - показать user_id и chat_id\n\n"
            "Любой другой текст я пока просто повторю."
        )

    def handle_bot_started(self, update: dict[str, Any]) -> None:
        user = update.get("user") or {}
        user_id = user.get("user_id")
        chat_id = update.get("chat_id")
        payload = update.get("payload")

        text = self.help_text()
        if payload:
            text += f"\n\nСтартовый payload: {payload}"

        self.send_reply(text=text, chat_id=chat_id, user_id=user_id)

    def handle_message_created(self, update: dict[str, Any]) -> None:
        message = update.get("message") or {}
        sender = message.get("sender") or {}

        if sender.get("is_bot"):
            return
        if self.bot_user_id is not None and sender.get("user_id") == self.bot_user_id:
            return

        chat_id, user_id = self.target_from_message(message)
        body = message.get("body") or {}
        text = (body.get("text") or "").strip()

        if not text:
            self.send_reply(
                text="Пока я понимаю только текстовые сообщения.",
                chat_id=chat_id,
                user_id=user_id,
            )
            return

        command = text.split(maxsplit=1)[0].lower()

        if command == "/start":
            response = self.help_text()
        elif command == "/help":
            response = self.help_text()
        elif command == "/ping":
            response = "pong"
        elif command == "/id":
            sender_id = sender.get("user_id")
            response = (
                f"user_id: {sender_id}\n"
                f"chat_id: {chat_id}\n"
                f"username: {sender.get('username')}"
            )
        else:
            response = f"Вы написали: {text}"

        self.send_reply(text=response, chat_id=chat_id, user_id=user_id)

    def handle_update(self, update: dict[str, Any]) -> None:
        update_type = update.get("update_type")

        if update_type == "bot_started":
            self.handle_bot_started(update)
            return

        if update_type == "message_created":
            self.handle_message_created(update)
            return

        print(f"[skip] Unsupported update_type={update_type}")

    def run(self) -> None:
        marker = self.load_marker()
        bot_name = self.bot_info.get("first_name") or self.bot_info.get("name") or "MAX bot"
        bot_username = self.bot_info.get("username") or "-"

        print(f"[info] Bot started: {bot_name} (@{bot_username})")
        print(f"[info] Marker file: {MARKER_FILE}")
        print("[info] Waiting for updates. Press Ctrl+C to stop.")

        while self.running:
            try:
                page = self.client.get_updates(marker)
                updates = page.get("updates") or []
                next_marker = page.get("marker")

                for update in updates:
                    try:
                        self.handle_update(update)
                    except Exception as exc:  # noqa: BLE001
                        print(f"[error] Failed to handle update: {exc}")

                if next_marker is not None:
                    marker = next_marker
                    self.save_marker(marker)

            except KeyboardInterrupt:
                print("\n[info] Stopped by user.")
                break
            except MaxApiError as exc:
                print(f"[error] {exc}")
                time.sleep(3)
            except Exception as exc:  # noqa: BLE001
                print(f"[error] Unexpected error: {exc}")
                time.sleep(3)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Simple MAX bot with long polling")
    parser.add_argument(
        "--check",
        action="store_true",
        help="Check token, bot info and current subscriptions without starting polling",
    )
    parser.add_argument(
        "--drop-webhooks",
        action="store_true",
        help="Delete active webhook subscriptions before start",
    )
    parser.add_argument(
        "--reset-marker",
        action="store_true",
        help="Remove saved marker before start",
    )
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    token = os.getenv("MAX_BOT_TOKEN")

    if not token:
        print("Environment variable MAX_BOT_TOKEN is not set.", file=sys.stderr)
        print('PowerShell example: $env:MAX_BOT_TOKEN = "your_token_here"', file=sys.stderr)
        return 1

    client = MaxApiClient(token)
    bot = LongPollingBot(client)

    if args.reset_marker:
        bot.reset_marker()
        print(f"[info] Marker removed: {MARKER_FILE}")

    bot.ensure_polling_available(drop_webhooks=args.drop_webhooks)

    if args.check:
        subscriptions = client.get_subscriptions().get("subscriptions") or []
        print(json.dumps(bot.bot_info, ensure_ascii=False, indent=2))
        print(f"[info] Active webhook subscriptions: {len(subscriptions)}")
        for item in subscriptions:
            url = item.get("url")
            if url:
                print(f" - {url}")
        return 0

    bot.run()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
