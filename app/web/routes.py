from pathlib import Path

from fastapi import APIRouter
from fastapi.responses import FileResponse

router = APIRouter()
STATIC_ROOT = Path(__file__).resolve().parent / "static"
MINIAPP_INDEX = STATIC_ROOT / "miniapp" / "index.html"


@router.get("/miniapp", include_in_schema=False)
async def miniapp_index() -> FileResponse:
    return FileResponse(MINIAPP_INDEX)
