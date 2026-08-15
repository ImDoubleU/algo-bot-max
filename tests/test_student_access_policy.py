from datetime import UTC, date, datetime
from types import SimpleNamespace

from app.models.enums import StudentStatus
from app.services.student_access_policy import departed_access_until, student_access_window


def test_departed_access_pauses_for_configured_summer_period() -> None:
    assert departed_access_until(
        date(2026, 5, 1),
        grace_days=30,
        freeze_from=date(2026, 5, 1),
        freeze_until=date(2026, 8, 31),
    ) == date(2026, 9, 30)


def test_departed_student_is_locked_after_grace_period() -> None:
    student = SimpleNamespace(
        status=StudentStatus.DEPARTED,
        departed_at=datetime(2026, 7, 1, tzinfo=UTC),
        status_updated_at=None,
    )
    tenant = SimpleNamespace(
        departed_access_days=30,
        access_freeze_from=None,
        access_freeze_until=None,
    )

    access = student_access_window(
        student,
        tenant,
        on_date=date(2026, 7, 31),
        timezone_name="UTC",
    )

    assert access.allowed is False
    assert access.access_until == date(2026, 7, 30)


def test_active_student_keeps_access_without_deadline() -> None:
    student = SimpleNamespace(status=StudentStatus.ACTIVE)
    tenant = SimpleNamespace()

    access = student_access_window(student, tenant, on_date=date(2026, 8, 13))

    assert access.allowed is True
    assert access.access_until is None
