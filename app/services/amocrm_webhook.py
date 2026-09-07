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
from app.services.bank import bank_local_date, close_bank_deposit_for_inactive_student
from app.services.crm_import import (
    CRM_TEMPLATE_COLUMNS,
    HEADER_ALIASES,
    CrmStudentRow,
    normalize_header,
    normalize_text,
    parse_birth_date,
)
from app.services.crm_sync import (
    CrmSyncDefaults,
    upsert_crm_student_rows,
)


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


@dataclass(frozen=True)
class AmoCrmStudentSyncResult:
    tenant_slug: str
    received_lead_ids: list[str]
    created_students: int
    updated_students: int
    existing_students: int
    incomplete_leads: dict[str, list[str]]


_LEAD_ID_KEY = re.compile(r"^leads\[(?:status|update|add)\]\[\d+\]\[id\]$")
_LEAD_FIELD_KEY = re.compile(
    r"^leads\[(status|update|add)\]\[(\d+)\]\[([^\]]+)\]$"
)
_CUSTOM_FIELD_META_KEY = re.compile(
    r"^leads\[(status|update|add)\]\[(\d+)\]\[custom_fields(?:_values)?\]"
    r"\[(\d+)\]\[(name|field_name|code)\]$"
)
_CUSTOM_FIELD_VALUE_KEY = re.compile(
    r"^leads\[(status|update|add)\]\[(\d+)\]\[custom_fields(?:_values)?\]"
    r"\[(\d+)\]\[values\]\[\d*\](?:\[value\])?$"
)
_AMOCRM_FIELD_BY_NAME = {
    normalize_header(alias): field
    for field, aliases in HEADER_ALIASES.items()
    for alias in (*aliases, field)
}
# The webhook URL already fixes the target tenant, so a repeated city field is optional.
_WEBHOOK_REQUIRED_STUDENT_FIELDS = tuple(
    (field, header)
    for field, header, required, _, _ in CRM_TEMPLATE_COLUMNS
    if required and field != "city"
)


def _scalar_values(value: Any) -> list[str]:
    if isinstance(value, dict):
        if "value" in value:
            return _scalar_values(value["value"])
        values: list[str] = []
        for nested in value.values():
            values.extend(_scalar_values(nested))
        return values
    if isinstance(value, (list, tuple, set)):
        values = []
        for nested in value:
            values.extend(_scalar_values(nested))
        return values
    normalized = normalize_text(value)
    return [normalized] if normalized else []


def _nested_lead_records(payload: dict[str, Any]) -> list[dict[str, Any]]:
    leads = payload.get("leads")
    if not isinstance(leads, dict):
        return []
    records: list[dict[str, Any]] = []
    for action in ("add", "update", "status"):
        action_rows = leads.get(action)
        if isinstance(action_rows, dict):
            action_rows = list(action_rows.values())
        if isinstance(action_rows, list):
            records.extend(row for row in action_rows if isinstance(row, dict))
    return records


def _flattened_lead_records(payload: dict[str, Any]) -> list[dict[str, Any]]:
    records: dict[tuple[str, str], dict[str, Any]] = {}
    custom_fields: dict[tuple[str, str, str], dict[str, Any]] = {}
    for raw_key, value in payload.items():
        key = str(raw_key)
        meta_match = _CUSTOM_FIELD_META_KEY.match(key)
        if meta_match:
            action, row_index, field_index, attribute = meta_match.groups()
            field = custom_fields.setdefault((action, row_index, field_index), {})
            values = _scalar_values(value)
            if values:
                field[attribute] = values[0]
            continue
        value_match = _CUSTOM_FIELD_VALUE_KEY.match(key)
        if value_match:
            action, row_index, field_index = value_match.groups()
            field = custom_fields.setdefault((action, row_index, field_index), {})
            field.setdefault("values", []).extend(_scalar_values(value))
            continue
        field_match = _LEAD_FIELD_KEY.match(key)
        if field_match:
            action, row_index, field_name = field_match.groups()
            records.setdefault((action, row_index), {})[field_name] = value

    for (action, row_index, _), field in custom_fields.items():
        records.setdefault((action, row_index), {}).setdefault(
            "custom_fields",
            [],
        ).append(field)
    return list(records.values())


def _record_custom_fields(record: dict[str, Any]) -> list[dict[str, Any]]:
    raw_fields = record.get("custom_fields") or record.get("custom_fields_values")
    if isinstance(raw_fields, dict):
        raw_fields = list(raw_fields.values())
    if not isinstance(raw_fields, list):
        return []
    return [field for field in raw_fields if isinstance(field, dict)]


def _record_student_fields(record: dict[str, Any]) -> dict[str, str]:
    fields: dict[str, str] = {}
    for raw_name, raw_value in record.items():
        field_name = _AMOCRM_FIELD_BY_NAME.get(normalize_header(raw_name))
        values = _scalar_values(raw_value)
        if field_name and values:
            fields[field_name] = ", ".join(values)

    for custom_field in _record_custom_fields(record):
        raw_name = (
            custom_field.get("name")
            or custom_field.get("field_name")
            or custom_field.get("code")
        )
        field_name = _AMOCRM_FIELD_BY_NAME.get(normalize_header(raw_name))
        values = _scalar_values(custom_field.get("values"))
        if field_name and values:
            fields[field_name] = ", ".join(values)
    return fields


def _amocrm_birth_date(value: str | None):
    try:
        return parse_birth_date(value)
    except ValueError as exc:
        raise AmoCrmWebhookError(
            "Дата рождения из amoCRM должна быть в формате ДД.ММ.ГГГГ"
        ) from exc


def extract_amocrm_student_rows(payload: dict[str, Any]) -> list[CrmStudentRow]:
    records = [*_nested_lead_records(payload), *_flattened_lead_records(payload)]
    if not records and any(key in payload for key in ("lead_id", "deal_id", "id")):
        records = [payload]

    merged_fields: dict[str, dict[str, str]] = {}
    for record in records:
        lead_values = _scalar_values(
            record.get("id") or record.get("lead_id") or record.get("deal_id")
        )
        if not lead_values:
            continue
        lead_id = lead_values[0]
        fields = merged_fields.setdefault(lead_id, {})
        fields.update(_record_student_fields(record))
        fields["deal_id"] = lead_id

    return [
        CrmStudentRow(
            row_number=index,
            deal_id=lead_id,
            uuid=fields.get("uuid"),
            lms_student_id=fields.get("lms_student_id"),
            first_name=fields.get("first_name"),
            last_name=fields.get("last_name"),
            group_name=fields.get("group_name"),
            course_name=fields.get("course_name"),
            venue_name=fields.get("venue_name"),
            teacher_name=fields.get("teacher_name"),
            city=fields.get("city"),
            status_name=fields.get("status_name"),
            contact_ids=fields.get("contact_ids"),
            contact_names=fields.get("contact_names"),
            birth_date=_amocrm_birth_date(fields.get("birth_date")),
        )
        for index, (lead_id, fields) in enumerate(merged_fields.items(), start=1)
    ]


def missing_amocrm_student_fields(row: CrmStudentRow) -> list[str]:
    return [
        header
        for field, header in _WEBHOOK_REQUIRED_STUDENT_FIELDS
        if not normalize_text(getattr(row, field))
    ]


async def sync_students_from_amocrm(
    db: AsyncSession,
    *,
    tenant_slug: str,
    student_status: StudentStatus,
    rows: list[CrmStudentRow],
    commit: bool = True,
) -> AmoCrmStudentSyncResult:
    normalized_tenant_slug = tenant_slug.strip().lower()
    tenant = await db.scalar(
        select(Tenant)
        .where(Tenant.slug == normalized_tenant_slug)
        .with_for_update()
    )
    if tenant is None:
        raise AmoCrmWebhookError("Партнер не найден", status_code=404)

    lead_ids = list(
        dict.fromkeys(row.deal_id for row in rows if row.deal_id)
    )
    existing_students_by_lead_id = {
        student.crm_deal_id: student
        for student in (
            await db.scalars(
                select(Student).where(
                Student.tenant_id == tenant.id,
                Student.crm_deal_id.in_(lead_ids),
            )
            )
        ).all()
        if student.crm_deal_id
    }
    created_students = 0
    updated_students = 0
    incomplete_leads: dict[str, list[str]] = {}
    existing_students = 0
    defaults = CrmSyncDefaults(
        partner_slug="amocrm",
        partner_name="amoCRM",
        tenant_slug=tenant.slug,
    )

    for row in rows:
        lead_id = row.deal_id
        if not lead_id:
            continue
        existing_student = existing_students_by_lead_id.get(lead_id)
        if existing_student is not None:
            existing_students += 1
            new_group_name = normalize_text(row.group_name)
            previous_group_name = existing_student.group_name
            changed_fields: list[str] = []
            if new_group_name and previous_group_name != new_group_name:
                existing_student.group_name = new_group_name
                changed_fields.append("group_name")
            if row.birth_date is not None and existing_student.birth_date != row.birth_date:
                existing_student.birth_date = row.birth_date
                changed_fields.append("birth_date")
            if changed_fields:
                db.add(
                    StudentHistoryEvent(
                        tenant_id=tenant.id,
                        student_id=existing_student.id,
                        event_type=(
                            "group_changed" if "group_name" in changed_fields else "updated"
                        ),
                        from_status=existing_student.status.value,
                        to_status=existing_student.status.value,
                        from_group_name=previous_group_name,
                        to_group_name=existing_student.group_name,
                        changed_fields=changed_fields,
                        source="amocrm_webhook",
                    )
                )
                updated_students += 1
            continue
        missing_fields = missing_amocrm_student_fields(row)
        if missing_fields:
            incomplete_leads[lead_id] = missing_fields
            continue
        sync_result = await upsert_crm_student_rows(
            db,
            [row],
            defaults=defaults,
            commit=False,
            target_tenant=tenant,
            student_status=student_status,
            history_source="amocrm_webhook",
        )
        created_students += sync_result.created_students
        updated_students += sync_result.updated_students
        created_student = await db.scalar(
            select(Student).where(
                Student.tenant_id == tenant.id,
                Student.crm_deal_id == lead_id,
            )
        )
        if created_student is not None:
            existing_students_by_lead_id[lead_id] = created_student

    db.add(
        AuditLog(
            tenant_id=tenant.id,
            action="amocrm.students_synced",
            entity_type="student",
            payload={
                "lead_ids": lead_ids,
                "created_students": created_students,
                "updated_students": updated_students,
                "existing_students": existing_students,
                "incomplete_leads": incomplete_leads,
            },
        )
    )
    if commit:
        await db.commit()
    return AmoCrmStudentSyncResult(
        tenant_slug=tenant.slug,
        received_lead_ids=lead_ids,
        created_students=created_students,
        updated_students=updated_students,
        existing_students=existing_students,
        incomplete_leads=incomplete_leads,
    )


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
        if previous_status == StudentStatus.ACTIVE and student_status != StudentStatus.ACTIVE:
            await close_bank_deposit_for_inactive_student(
                db,
                tenant=tenant,
                student=student,
                closed_on=bank_local_date(now),
                close_reason=f"student_{student_status.value}",
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
