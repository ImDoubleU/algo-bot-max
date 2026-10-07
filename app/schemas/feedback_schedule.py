from datetime import date
from typing import Literal
from uuid import UUID

from pydantic import (
    BaseModel,
    ConfigDict,
    Field,
    StrictBool,
    StrictInt,
    field_validator,
    model_validator,
)


class FeedbackScheduleRow(BaseModel):
    model_config = ConfigDict(extra="forbid")
    id: UUID
    date: date
    lesson: StrictInt | None = Field(default=None, ge=1, le=100)
    topic: str | None = Field(default=None, max_length=200)
    number: StrictInt = Field(ge=1, le=999)
    repeat: StrictBool
    skipped: StrictBool

    @model_validator(mode="after")
    def validate_material(self):
        if self.lesson is None:
            if not self.topic or not self.topic.strip():
                raise ValueError("Укажите тему своего занятия")
            self.topic = self.topic.strip()
            if self.repeat:
                raise ValueError("Занятие со своей темой не является повторением")
        elif self.topic is not None:
            raise ValueError("Для материала курса нельзя задавать отдельную тему")
        return self

    @field_validator("date", mode="before")
    @classmethod
    def validate_date(cls, value):
        if not isinstance(value, str) or len(value) != 10:
            raise ValueError("Укажите дату в формате YYYY-MM-DD")
        parsed = date.fromisoformat(value)
        if parsed.isoformat() != value:
            raise ValueError("Укажите дату в формате YYYY-MM-DD")
        return parsed


class FeedbackScheduleData(BaseModel):
    model_config = ConfigDict(extra="forbid")
    course: str = Field(min_length=1, max_length=200)
    mode: Literal["group", "online"]
    rows: list[FeedbackScheduleRow] = Field(min_length=1, max_length=100)

    @model_validator(mode="after")
    def validate_rows(self):
        if len({row.id for row in self.rows}) != len(self.rows):
            raise ValueError("Повторяются идентификаторы занятий")
        active = [row for row in self.rows if not row.skipped]
        if not active or len({row.number for row in active}) != len(active):
            raise ValueError("Проверьте номера включённых занятий")
        if any(row.date.year < 2000 or row.date.year > 2100 for row in self.rows):
            raise ValueError("Дата должна быть с 2000 по 2100 год")
        return self


class FeedbackScheduleSave(BaseModel):
    model_config = ConfigDict(extra="forbid")
    group_name: str = Field(min_length=1, max_length=200)
    revision: StrictInt = Field(ge=0)
    schedule: FeedbackScheduleData
