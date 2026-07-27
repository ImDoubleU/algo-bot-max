from __future__ import annotations

from dataclasses import dataclass
from typing import Any


@dataclass(frozen=True)
class PendingContact:
    contact_id: str
    tenant_slug: str
    students: list[dict[str, Any]]


@dataclass
class PendingStaffInvite:
    created_at: float
    username: str | None
    display_name: str | None
    tenants: list[dict[str, Any]]
    roles: list[str]
    tenant_slug: str | None = None


@dataclass(frozen=True)
class PendingStaffRequest:
    request_id: str
    created_at: float
    max_user_id: int
    username: str | None
    display_name: str | None
    tenant_slug: str
    tenant_name: str
    city_name: str
    role: str


@dataclass(frozen=True)
class BotResponse:
    text: str
    attachments: list[dict[str, Any]] | None = None

    def as_message_body(self) -> dict[str, Any]:
        body: dict[str, Any] = {"text": self.text}
        if self.attachments:
            body["attachments"] = self.attachments
        return body
