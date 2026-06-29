from typing import Annotated

from fastapi import APIRouter, Depends, File, Form, HTTPException, Query, UploadFile, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import get_settings
from app.db.session import get_db_session
from app.schemas.miniapp import (
    MiniAppAccrualCreate,
    MiniAppAccrualRead,
    MiniAppCatalogRead,
    MiniAppOrderCreate,
    MiniAppOrderCreatedRead,
    MiniAppProductImportRead,
    MiniAppSessionRead,
)
from app.services.miniapp import (
    MiniAppStoreError,
    accrue_miniapp_astrocoins,
    create_miniapp_order,
    get_miniapp_session,
    import_miniapp_products,
    list_miniapp_catalog,
)

router = APIRouter()
DbSession = Annotated[AsyncSession, Depends(get_db_session)]


@router.get("/session", response_model=MiniAppSessionRead)
async def miniapp_session(
    db: DbSession,
    max_user_id: Annotated[int, Query(gt=0)],
    tenant_slug: str | None = None,
) -> MiniAppSessionRead:
    settings = get_settings()
    return await get_miniapp_session(
        db,
        max_user_id=max_user_id,
        tenant_slug=tenant_slug or settings.default_tenant_slug,
    )


@router.get("/catalog", response_model=MiniAppCatalogRead)
async def miniapp_catalog(
    db: DbSession,
    tenant_slug: str | None = None,
) -> MiniAppCatalogRead:
    settings = get_settings()
    return await list_miniapp_catalog(
        db,
        tenant_slug=tenant_slug or settings.default_tenant_slug,
    )


@router.post("/products/import", response_model=MiniAppProductImportRead)
async def miniapp_import_products(
    db: DbSession,
    max_user_id: Annotated[int, Form(gt=0)],
    file: Annotated[UploadFile, File()],
    tenant_slug: Annotated[str | None, Form()] = None,
) -> MiniAppProductImportRead:
    settings = get_settings()
    content = await file.read()
    try:
        return await import_miniapp_products(
            db,
            max_user_id=max_user_id,
            tenant_slug=tenant_slug or settings.default_tenant_slug,
            filename=file.filename or "products.csv",
            content=content,
        )
    except MiniAppStoreError as exc:
        raise HTTPException(status_code=exc.status_code, detail=str(exc)) from exc


@router.post(
    "/orders",
    response_model=MiniAppOrderCreatedRead,
    status_code=status.HTTP_201_CREATED,
)
async def miniapp_create_order(
    payload: MiniAppOrderCreate,
    db: DbSession,
) -> MiniAppOrderCreatedRead:
    settings = get_settings()
    try:
        return await create_miniapp_order(
            db,
            payload=payload,
            default_tenant_slug=settings.default_tenant_slug,
        )
    except MiniAppStoreError as exc:
        raise HTTPException(status_code=exc.status_code, detail=str(exc)) from exc


@router.post("/coins/accrue", response_model=MiniAppAccrualRead)
async def miniapp_accrue_coins(
    payload: MiniAppAccrualCreate,
    db: DbSession,
) -> MiniAppAccrualRead:
    settings = get_settings()
    try:
        return await accrue_miniapp_astrocoins(
            db,
            payload=payload,
            default_tenant_slug=settings.default_tenant_slug,
        )
    except MiniAppStoreError as exc:
        raise HTTPException(status_code=exc.status_code, detail=str(exc)) from exc
