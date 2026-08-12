import re
from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Any

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.audit import AuditLog
from app.models.enums import StudentStatus
from app.models.student import Student, StudentHistoryEvent
from app.models.tenant import Tenant


class AmoCrmWebhookError(RuntimeError):
    def __init__(self, message: str, *, status_code: int = 400) -> None:
        super().__init__(message)
        self.status_code = status_code


@dataclass(frozen=True)
class AmoCrmStudentStatusResult:
    tenant_slug: str
    requested_status: StudentStatus
    received_lead_ids: list[str]
    matched_students: int
    updated_students: int
    unmatched_lead_ids: list[str]


_LEAD_ID_KEY = re.compile(r"^leads\[(?:status|update|add)\]\[\d+\]\[id\]$")


def extract_amocrm_lead_ids(payload: dict[str, Any]) -> list[str]:
    values: list[Any] = []
    for direct_key in ("lead_id", "deal_id", "id"):
        if direct_key in payload:
            values.append(payload[direct_key])

    for key, value in payload.items():
        if _LEAD_ID_KEY.match(str(key)):
            values.append(value)

    leads = payload.get("leads")
    if isinstance(leads, dict):
        for action in ("status", "update", "add"):
            rows = leads.get(action)
            if isinstance(rows, dict):
                rows = list(rows.values())
            if isinstance(rows, list):
                values.extend(row.get("id") for row in rows if isinstance(row, dict))

    normalized: list[str] = []
    for value in values:
        if isinstance(value, (list, tuple, set)):
            candidates = value
        else:
            candidates = [value]
        for candidate in candidates:
            text = str(candidate or "").strip()
            if text and text not in normalized:
                normalized.append(text)
    return normalized


async def update_student_status_from_amocrm(
    db: AsyncSession,
    *,
    tenant_slug: str,
    student_status: StudentStatus,
    lead_ids: list[str],
) -> AmoCrmStudentStatusResult:
    normalized_tenant_slug = tenant_slug.strip().lower()
    tenant = await db.scalar(select(Tenant).where(Tenant.slug == normalized_tenant_slug))
    if tenant is None:
        raise AmoCrmWebhookError("Партнер не найден", status_code=404)
    normalized_ids = list(
        dict.fromkeys(
            str(lead_id).strip() for lead_id in lead_ids if str(lead_id).strip()
        )
    )
    if not normalized_ids:
        raise AmoCrmWebhookError("В webhook не найден ID сделки")

    students = (
        await db.scalars(
            select(Student)
            .where(
                Student.tenant_id == tenant.id,
                Student.crm_deal_id.in_(normalized_ids),
            )
            .with_for_update()
        )
    ).all()
    now = datetime.now(UTC)
    updated_students = 0
    for student in students:
        previous_status = student.status
        if previous_status == student_status:
            continue
        student.status = student_status
        student.status_updated_at = now
        if student_status == StudentStatus.ACTIVE:
            student.departed_at = None
        elif student_status == StudentStatus.DEPARTED and student.departed_at is None:
            student.departed_at = now
        db.add(
            StudentHistoryEvent(
                tenant_id=tenant.id,
                student_id=student.id,
                event_type="status_changed",
                from_status=previous_status.value,
                to_status=student_status.value,
                changed_fields=["status"],
                source="amocrm_webhook",
            )
        )
        updated_students += 1

    matched_ids = {student.crm_deal_id for student in students if student.crm_deal_id}
    unmatched_ids = [lead_id for lead_id in normalized_ids if lead_id not in matched_ids]
    db.add(
        AuditLog(
            tenant_id=tenant.id,
            action="amocrm.student_status_updated",
            entity_type="student",
            payload={
                "requested_status": student_status.value,
                "lead_ids": normalized_ids,
                "matched_students": len(students),
                "updated_students": updated_students,
                "unmatched_lead_ids": unmatched_ids,
            },
        )
    )
    await db.commit()
    return AmoCrmStudentStatusResult(
        tenant_slug=tenant.slug,
        requested_status=student_status,
        received_lead_ids=normalized_ids,
        matched_students=len(students),
        updated_students=updated_students,
        unmatched_lead_ids=unmatched_ids,
    )
