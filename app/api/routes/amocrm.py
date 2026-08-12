import hmac
from typing import Annotated, Any

from fastapi import APIRouter, Depends, Header, HTTPException, Query, Request, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import get_settings, is_placeholder
from app.db.session import get_db_session
from app.models.enums import StudentStatus
from app.services.amocrm_webhook import (
    AmoCrmWebhookError,
    extract_amocrm_lead_ids,
    extract_amocrm_student_rows,
    sync_students_from_amocrm,
    update_student_status_from_amocrm,
)

router = APIRouter()
DbSession = Annotated[AsyncSession, Depends(get_db_session)]


async def _webhook_payload(request: Request) -> dict[str, Any]:
    content_type = request.headers.get("content-type", "").lower()
    if "application/json" in content_type:
        body = await request.json()
        return body if isinstance(body, dict) else {}
    form = await request.form()
    payload: dict[str, Any] = {}
    for key, value in form.multi_items():
        if key in payload:
            current = payload[key]
            payload[key] = [*current, value] if isinstance(current, list) else [current, value]
        else:
            payload[key] = value
    return payload


@router.post("/student-status")
async def receive_student_status_webhook(
    request: Request,
    db: DbSession,
    tenant_slug: Annotated[str, Query(min_length=2, max_length=120)],
    student_status: Annotated[StudentStatus, Query()],
    secret: Annotated[str | None, Query(max_length=256)] = None,
    webhook_secret: Annotated[
        str | None,
        Header(alias="X-Algo-Webhook-Secret"),
    ] = None,
) -> dict[str, Any]:
    settings = get_settings()
    expected_secret = settings.amocrm_webhook_secret
    if is_placeholder(expected_secret):
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="amoCRM webhook is not configured",
        )
    supplied_secret = webhook_secret or secret
    if supplied_secret is None or not hmac.compare_digest(str(expected_secret), supplied_secret):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid webhook secret",
        )

    try:
        payload = await _webhook_payload(request)
        lead_ids = extract_amocrm_lead_ids(payload)
        sync_result = await sync_students_from_amocrm(
            db,
            tenant_slug=tenant_slug,
            student_status=student_status,
            rows=extract_amocrm_student_rows(payload),
            commit=False,
        )
        result = await update_student_status_from_amocrm(
            db,
            tenant_slug=tenant_slug,
            student_status=student_status,
            lead_ids=lead_ids,
        )
    except AmoCrmWebhookError as exc:
        raise HTTPException(status_code=exc.status_code, detail=str(exc)) from exc
    return {
        "ok": True,
        "tenant_slug": result.tenant_slug,
        "status": result.requested_status.value,
        "received_lead_ids": result.received_lead_ids,
        "matched_students": result.matched_students,
        "updated_students": result.updated_students,
        "created_students": sync_result.created_students,
        "updated_student_cards": sync_result.updated_students,
        "existing_students": sync_result.existing_students,
        "incomplete_leads": sync_result.incomplete_leads,
        "unmatched_lead_ids": result.unmatched_lead_ids,
    }
