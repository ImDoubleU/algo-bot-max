from dataclasses import dataclass
from datetime import UTC, date, datetime, timedelta
from zoneinfo import ZoneInfo

from app.core.config import get_settings
from app.models.enums import StudentStatus
from app.models.student import Student
from app.models.tenant import Tenant


@dataclass(frozen=True)
class StudentAccessWindow:
    allowed: bool
    access_until: date | None = None
    paused: bool = False
    days_remaining: int | None = None


def _in_freeze_period(
    day: date,
    *,
    freeze_from: date | None,
    freeze_until: date | None,
) -> bool:
    return bool(
        freeze_from is not None
        and freeze_until is not None
        and freeze_from <= day <= freeze_until
    )


def departed_access_until(
    departed_on: date,
    *,
    grace_days: int,
    freeze_from: date | None = None,
    freeze_until: date | None = None,
) -> date:
    """Return the last accessible calendar day, excluding frozen days."""
    remaining = max(1, grace_days)
    cursor = departed_on
    while True:
        if not _in_freeze_period(
            cursor,
            freeze_from=freeze_from,
            freeze_until=freeze_until,
        ):
            remaining -= 1
            if remaining == 0:
                return cursor
        cursor += timedelta(days=1)


def _local_date(value: datetime, timezone_name: str) -> date:
    if value.tzinfo is None:
        value = value.replace(tzinfo=UTC)
    return value.astimezone(ZoneInfo(timezone_name)).date()


def student_access_window(
    student: Student,
    tenant: Tenant,
    *,
    on_date: date | None = None,
    timezone_name: str | None = None,
) -> StudentAccessWindow:
    if student.status == StudentStatus.ACTIVE:
        return StudentAccessWindow(allowed=True)
    if student.status == StudentStatus.ARCHIVED:
        return StudentAccessWindow(allowed=False)

    timezone_name = timezone_name or get_settings().app_timezone
    departed_at = student.departed_at or student.status_updated_at or datetime.now(UTC)
    departed_on = _local_date(departed_at, timezone_name)
    access_until = departed_access_until(
        departed_on,
        grace_days=tenant.departed_access_days,
        freeze_from=tenant.access_freeze_from,
        freeze_until=tenant.access_freeze_until,
    )
    current_date = on_date or datetime.now(ZoneInfo(timezone_name)).date()
    allowed = current_date <= access_until
    paused = allowed and _in_freeze_period(
        current_date,
        freeze_from=tenant.access_freeze_from,
        freeze_until=tenant.access_freeze_until,
    )
    days_remaining = max(0, (access_until - current_date).days + 1) if allowed else 0
    return StudentAccessWindow(
        allowed=allowed,
        access_until=access_until,
        paused=paused,
        days_remaining=days_remaining,
    )
