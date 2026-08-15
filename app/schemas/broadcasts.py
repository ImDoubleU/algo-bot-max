from datetime import datetime
from typing import Literal
from uuid import UUID

from pydantic import BaseModel, Field, field_validator

BroadcastRecipientCategory = Literal["all", "parents", "students"]
BroadcastAudienceFilter = Literal["all", "low_balance", "active_orders", "no_orders"]


class BroadcastAudienceRequest(BaseModel):
    max_user_id: int = Field(gt=0)
    tenant_slug: str | None = None
    recipient_category: BroadcastRecipientCategory = "all"
    audience_filter: BroadcastAudienceFilter = "all"
    group_names: list[str] = Field(default_factory=list, max_length=100)
    venue_names: list[str] = Field(default_factory=list, max_length=50)
    balance_threshold: int | None = Field(default=None, ge=0, le=1_000_000)

    @field_validator("group_names", "venue_names")
    @classmethod
    def normalize_string_lists(cls, values: list[str]) -> list[str]:
        result: list[str] = []
        for value in values:
            normalized = value.strip()
            if normalized and normalized not in result:
                result.append(normalized)
        return result


class BroadcastAudiencePreviewRead(BaseModel):
    recipient_count: int
    matched_students: int
    unavailable_students: int = 0
    selected_groups: list[str]
    selected_venues: list[str]


class SchoolBroadcastRead(BaseModel):
    id: UUID
    title: str | None
    message: str
    image_url: str | None
    recipient_category: BroadcastRecipientCategory
    audience_filter: BroadcastAudienceFilter
    group_names: list[str]
    venue_names: list[str]
    balance_threshold: int | None
    status: str
    recipient_count: int
    delivered_count: int
    failed_count: int
    creator_name: str
    sent_at: datetime | None
    created_at: datetime
