from typing import Literal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, field_validator

SupportRole = Literal["parent", "student", "staff"]
SupportStatus = Literal["new", "in_progress", "waiting", "resolved"]


def clean_name(value: str) -> str:
    value = " ".join(value.split())
    if not value or len(value) > 80 or not any(c.isalpha() for c in value):
        raise ValueError("Укажите имя и фамилию буквами")
    if any(not (c.isalpha() or c in " -'’.") for c in value):
        raise ValueError("Укажите имя и фамилию буквами")
    return value


def clean_city(value: str) -> str:
    value = " ".join(value.split())
    if (not value or len(value) > 120 or not any(c.isalpha() for c in value)
            or any(not (c.isalpha() or c.isdigit() or c in " -'’.") for c in value)):
        raise ValueError("Напишите название города, например: Нижний Новгород")
    return value


def clean_child_name(value: str) -> str:
    parts = value.split()
    if len(parts) < 2 or len(" ".join(parts)) > 160:
        raise ValueError("Напишите имя и фамилию ребёнка одним сообщением")
    return " ".join(clean_name(part) for part in parts)


class SupportCreate(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)
    request_id: UUID
    role: SupportRole
    first_name: str = Field(min_length=1, max_length=80)
    last_name: str = Field(min_length=1, max_length=80)
    city_name: str | None = Field(default=None, max_length=120)
    child_full_name: str | None = Field(default=None, max_length=160)
    message: str = Field(min_length=1, max_length=4000)
    photo_ids: list[UUID] = Field(default_factory=list, max_length=5)

    @field_validator("first_name", "last_name")
    @classmethod
    def name(cls, value):
        return clean_name(value)

    @field_validator("city_name")
    @classmethod
    def city(cls, value):
        return clean_city(value) if value is not None else None

    @field_validator("child_full_name")
    @classmethod
    def child_name(cls, value):
        return clean_child_name(value) if value is not None else None

    @field_validator("photo_ids")
    @classmethod
    def unique_photos(cls, value):
        if len(set(value)) != len(value):
            raise ValueError("Фото не должно повторяться")
        return value


class SupportUpdate(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)
    status: SupportStatus
    private_note: str = Field(default="", max_length=4000)


class SupportReplyCreate(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)
    request_id: UUID
    message: str = Field(min_length=1, max_length=3500)


class SupportBotEvent(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)
    # Identity is taken exclusively from the signed bot token, never from these fields.
    max_user_id: int = Field(gt=0)
    tenant_slug: str = Field(min_length=1, max_length=160)
    action: Literal["start", "role", "message", "submit", "cancel", "reply", "choose", "exit"]
    ticket_id: int | None = Field(default=None, gt=0)
    role: SupportRole | None = None
    text: str = Field(default="", max_length=4000)
    photo_urls: list[str] = Field(default_factory=list, max_length=5)
    event_id: str = Field(default="", max_length=200)


class SupportRead(BaseModel):
    model_config = ConfigDict(extra="forbid")
    reply_ids: list[UUID] = Field(max_length=500)
