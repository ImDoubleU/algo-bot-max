from datetime import datetime
from typing import Literal
from uuid import UUID

from pydantic import BaseModel, Field, field_validator

BroadcastRecipientCategory = Literal["all", "parents", "students"]
BroadcastAudienceFilter = Literal["all", "low_balance", "active_orders", "no_orders"]
BroadcastLessonMode = Literal["offline", "online", "individual"]


class BroadcastAudienceRequest(BaseModel):
    max_user_id: int = Field(gt=0)
    tenant_slug: str | None = None
    recipient_category: BroadcastRecipientCategory = "all"
    audience_filter: BroadcastAudienceFilter = "all"
    group_names: list[str] = Field(default_factory=list, max_length=100)
    venue_names: list[str] = Field(default_factory=list, max_length=50)
    lesson_modes: list[BroadcastLessonMode] = Field(default_factory=list, max_length=3)
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
    selected_lesson_modes: list[BroadcastLessonMode]


class BroadcastVenueRuleRead(BaseModel):
    id: UUID
    name: str
    keywords: list[str]
    group_names: list[str]
    matched_group_count: int = 0


class BroadcastTargetOptionsRead(BaseModel):
    groups: list[str]
    venues: list[BroadcastVenueRuleRead]
    can_manage_venues: bool = False


class BroadcastVenueRuleUpsert(BaseModel):
    max_user_id: int = Field(gt=0)
    tenant_slug: str | None = None
    name: str = Field(min_length=1, max_length=180)
    keywords: list[str] = Field(default_factory=list, max_length=50)
    group_names: list[str] = Field(default_factory=list, max_length=100)

    @field_validator("name")
    @classmethod
    def normalize_name(cls, value: str) -> str:
        return " ".join(value.split())

    @field_validator("keywords", "group_names")
    @classmethod
    def normalize_rule_lists(cls, values: list[str]) -> list[str]:
        result: list[str] = []
        seen: set[str] = set()
        for value in values:
            normalized = " ".join(value.split())
            key = normalized.casefold()
            if normalized and key not in seen:
                seen.add(key)
                result.append(normalized)
        return result


class SchoolBroadcastRead(BaseModel):
    id: UUID
    title: str | None
    message: str
    image_url: str | None
    recipient_category: BroadcastRecipientCategory
    audience_filter: BroadcastAudienceFilter
    group_names: list[str]
    venue_names: list[str]
    lesson_modes: list[BroadcastLessonMode]
    balance_threshold: int | None
    status: str
    recipient_count: int
    delivered_count: int
    failed_count: int
    creator_name: str
    sent_at: datetime | None
    created_at: datetime
