from __future__ import annotations

from dataclasses import dataclass
from typing import Any


@dataclass(frozen=True)
class PendingContact:
    contact_id: str
    tenant_slug: str
    students: list[dict[str, Any]]


@dataclass(frozen=True)
class BotResponse:
    text: str
    attachments: list[dict[str, Any]] | None = None

    def as_message_body(self) -> dict[str, Any]:
        body: dict[str, Any] = {"text": self.text}
        if self.attachments:
            body["attachments"] = self.attachments
        return body
