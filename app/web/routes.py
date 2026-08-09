from pathlib import Path

from fastapi import APIRouter, HTTPException
from fastapi.responses import FileResponse, Response

from app.core.config import get_settings
from app.services.crm_import import build_crm_import_template
from app.services.student_invitations import (
    STUDENT_INVITE_PREFIX,
    StudentInvitationError,
    invitation_qr_png,
    verify_student_invitation_token,
)

router = APIRouter()
STATIC_ROOT = Path(__file__).resolve().parent / "static"
MINIAPP_INDEX = STATIC_ROOT / "miniapp" / "index.html"


@router.get("/miniapp", include_in_schema=False)
async def miniapp_index() -> FileResponse:
    return FileResponse(MINIAPP_INDEX)


@router.get("/miniapp/import-template.xlsx", include_in_schema=False)
async def crm_import_template() -> Response:
    return Response(
        content=build_crm_import_template(),
        media_type=(
            "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
        ),
        headers={
            "Cache-Control": "public, max-age=3600",
            "Content-Disposition": (
                'attachment; filename="algo-max-students-import-template.xlsx"'
            ),
            "X-Content-Type-Options": "nosniff",
        },
    )


@router.get("/miniapp/qr/{token}.png", include_in_schema=False)
async def student_invitation_qr(token: str) -> Response:
    try:
        verify_student_invitation_token(token)
    except StudentInvitationError as exc:
        raise HTTPException(status_code=404, detail="QR-код не найден") from exc

    bot_username = str(get_settings().max_bot_username or "").strip().lstrip("@")
    if not bot_username:
        raise HTTPException(status_code=503, detail="Бот не настроен")
    link = f"https://max.ru/{bot_username}?start={STUDENT_INVITE_PREFIX}{token}"
    return Response(
        content=invitation_qr_png(link),
        media_type="image/png",
        headers={
            "Cache-Control": "private, max-age=300",
            "Content-Disposition": 'attachment; filename="algo-max-student-qr.png"',
            "X-Content-Type-Options": "nosniff",
        },
    )
