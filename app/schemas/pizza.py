from datetime import datetime
from typing import Literal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, StrictInt, field_validator


class PizzaPayload(BaseModel):
    model_config = ConfigDict(extra="forbid")


class PizzaOfferCreate(PizzaPayload):
    title: str = Field(min_length=2, max_length=120)
    description: str = Field(default="", max_length=500)
    share: StrictInt = Field(ge=1, le=100_000)

    @field_validator("title", "description")
    @classmethod
    def trim_text(cls, value):
        return value.strip()

    @field_validator("title")
    @classmethod
    def title_not_blank(cls, value):
        if len(value) < 2:
            raise ValueError("Введите название")
        return value


class PizzaCampaignCreate(PizzaPayload):
    offer_id: UUID
    group_name: str = Field(min_length=1, max_length=160)
    deadline: datetime

    @field_validator("deadline")
    @classmethod
    def timezone_required(cls, value):
        if value.tzinfo is None:
            raise ValueError("Укажите часовой пояс")
        return value


class PizzaContribute(PizzaPayload):
    student_id: UUID


class PizzaAction(PizzaPayload):
    action: Literal["cancel", "paid", "ordered", "delivered"]
