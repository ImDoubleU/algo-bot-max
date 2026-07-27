from typing import Annotated
from uuid import UUID

from fastapi import (
    APIRouter,
    Depends,
    File,
    Form,
    HTTPException,
    Query,
    Request,
    UploadFile,
    status,
)
from pydantic import ValidationError
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.dependencies import (
    get_miniapp_identity,
    require_matching_miniapp_identity,
)
from app.core.config import get_settings
from app.core.miniapp_auth import MiniAppIdentity
from app.db.session import get_db_session
from app.models.enums import ProductStatus, StudentStatus
from app.schemas.miniapp import (
    MiniAppAccessStatusRead,
    MiniAppAccessStatusUpdate,
    MiniAppAccrualCreate,
    MiniAppAccrualRead,
    MiniAppCatalogRead,
    MiniAppCrmImportRead,
    MiniAppInventoryAdjustmentCreate,
    MiniAppInventoryAdjustmentRead,
    MiniAppInventoryTransferCreate,
    MiniAppInventoryTransferRead,
    MiniAppOpsSummaryRead,
    MiniAppOrderActionCreate,
    MiniAppOrderActionRead,
    MiniAppOrderCreate,
    MiniAppOrderCreatedRead,
    MiniAppOrderWarehouseAssignmentCreate,
    MiniAppProductImportRead,
    MiniAppProductRead,
    MiniAppProductUpsert,
    MiniAppSessionRead,
    MiniAppStaffAssignmentRead,
    MiniAppStaffAssignmentUpdate,
    MiniAppStaffOnboardingOptionsRead,
    MiniAppWarehouseRead,
    MiniAppWarehouseUpsert,
)
from app.services.miniapp import (
    MiniAppStoreError,
    accrue_miniapp_astrocoins,
    adjust_miniapp_inventory,
    assign_miniapp_order_warehouses,
    cancel_miniapp_order,
    create_miniapp_order,
    get_miniapp_ops_summary,
    get_miniapp_session,
    import_miniapp_crm_students,
    import_miniapp_products,
    issue_miniapp_order,
    list_miniapp_catalog,
    list_miniapp_staff_onboarding_options,
    return_miniapp_order,
    transfer_miniapp_inventory,
    update_miniapp_access_link_status,
    update_miniapp_staff_assignment,
    upsert_miniapp_product,
    upsert_miniapp_warehouse,
)
from app.services.product_media import (
    ProductMediaError,
    remove_product_image,
    save_product_image,
)

router = APIRouter()
DbSession = Annotated[AsyncSession, Depends(get_db_session)]
MiniAppIdentityDep = Annotated[MiniAppIdentity | None, Depends(get_miniapp_identity)]


def _authorized_tenant_slug(
    identity: MiniAppIdentity | None,
    *,
    max_user_id: int | None,
    tenant_slug: str | None,
) -> str:
    resolved_tenant = tenant_slug or get_settings().default_tenant_slug
    if identity is not None:
        require_matching_miniapp_identity(
            identity,
            max_user_id=max_user_id or identity.max_user_id,
            tenant_slug=resolved_tenant,
        )
    return resolved_tenant


@router.get("/session", response_model=MiniAppSessionRead)
async def miniapp_session(
    db: DbSession,
    identity: MiniAppIdentityDep,
    max_user_id: Annotated[int, Query(gt=0)],
    tenant_slug: str | None = None,
) -> MiniAppSessionRead:
    resolved_tenant = _authorized_tenant_slug(
        identity,
        max_user_id=max_user_id,
        tenant_slug=tenant_slug,
    )
    return await get_miniapp_session(
        db,
        max_user_id=max_user_id,
        tenant_slug=resolved_tenant,
    )


@router.get("/catalog", response_model=MiniAppCatalogRead)
async def miniapp_catalog(
    db: DbSession,
    identity: MiniAppIdentityDep,
    tenant_slug: str | None = None,
    max_user_id: Annotated[int | None, Query(gt=0)] = None,
    include_inactive: bool = False,
) -> MiniAppCatalogRead:
    resolved_tenant = _authorized_tenant_slug(
        identity,
        max_user_id=max_user_id,
        tenant_slug=tenant_slug,
    )
    try:
        return await list_miniapp_catalog(
            db,
            tenant_slug=resolved_tenant,
            max_user_id=max_user_id,
            include_inactive=include_inactive,
        )
    except MiniAppStoreError as exc:
        raise HTTPException(status_code=exc.status_code, detail=str(exc)) from exc


@router.get("/ops/summary", response_model=MiniAppOpsSummaryRead)
async def miniapp_ops_summary(
    db: DbSession,
    identity: MiniAppIdentityDep,
    max_user_id: Annotated[int, Query(gt=0)],
    tenant_slug: str | None = None,
    low_stock_threshold: Annotated[int, Query(ge=0, le=999)] = 5,
) -> MiniAppOpsSummaryRead:
    resolved_tenant = _authorized_tenant_slug(
        identity,
        max_user_id=max_user_id,
        tenant_slug=tenant_slug,
    )
    try:
        return await get_miniapp_ops_summary(
            db,
            max_user_id=max_user_id,
            tenant_slug=resolved_tenant,
            low_stock_threshold=low_stock_threshold,
        )
    except MiniAppStoreError as exc:
        raise HTTPException(status_code=exc.status_code, detail=str(exc)) from exc


@router.post("/products/import", response_model=MiniAppProductImportRead)
async def miniapp_import_products(
    db: DbSession,
    identity: MiniAppIdentityDep,
    max_user_id: Annotated[int, Form(gt=0)],
    file: Annotated[UploadFile, File()],
    tenant_slug: Annotated[str | None, Form()] = None,
) -> MiniAppProductImportRead:
    resolved_tenant = _authorized_tenant_slug(
        identity,
        max_user_id=max_user_id,
        tenant_slug=tenant_slug,
    )
    content = await file.read()
    try:
        return await import_miniapp_products(
            db,
            max_user_id=max_user_id,
            tenant_slug=resolved_tenant,
            filename=file.filename or "products.csv",
            content=content,
        )
    except MiniAppStoreError as exc:
        raise HTTPException(status_code=exc.status_code, detail=str(exc)) from exc


@router.post("/students/import", response_model=MiniAppCrmImportRead)
async def miniapp_import_crm_students(
    db: DbSession,
    identity: MiniAppIdentityDep,
    max_user_id: Annotated[int, Form(gt=0)],
    file: Annotated[UploadFile, File()],
    tenant_slug: Annotated[str | None, Form()] = None,
    sheet_name: Annotated[str, Form()] = "Сделки",
    dry_run: Annotated[bool, Form()] = True,
    student_status: Annotated[StudentStatus, Form()] = StudentStatus.ACTIVE,
) -> MiniAppCrmImportRead:
    resolved_tenant = _authorized_tenant_slug(
        identity,
        max_user_id=max_user_id,
        tenant_slug=tenant_slug,
    )
    content = await file.read()
    try:
        return await import_miniapp_crm_students(
            db,
            max_user_id=max_user_id,
            tenant_slug=resolved_tenant,
            filename=file.filename or "students.xlsx",
            content=content,
            sheet_name=sheet_name,
            dry_run=dry_run,
            student_status=student_status,
        )
    except MiniAppStoreError as exc:
        raise HTTPException(status_code=exc.status_code, detail=str(exc)) from exc


@router.post("/products", response_model=MiniAppProductRead)
async def miniapp_upsert_product(
    payload: MiniAppProductUpsert,
    db: DbSession,
    identity: MiniAppIdentityDep,
) -> MiniAppProductRead:
    settings = get_settings()
    _authorized_tenant_slug(
        identity,
        max_user_id=payload.max_user_id,
        tenant_slug=payload.tenant_slug,
    )
    try:
        return await upsert_miniapp_product(
            db,
            payload=payload,
            default_tenant_slug=settings.default_tenant_slug,
        )
    except MiniAppStoreError as exc:
        raise HTTPException(status_code=exc.status_code, detail=str(exc)) from exc


@router.post("/products/save", response_model=MiniAppProductRead)
async def miniapp_save_product(
    request: Request,
    db: DbSession,
    identity: MiniAppIdentityDep,
    max_user_id: Annotated[int, Form(gt=0)],
    sku: Annotated[str, Form(min_length=2, max_length=120)],
    name: Annotated[str, Form(min_length=2, max_length=200)],
    category_name: Annotated[str, Form(min_length=2, max_length=160)],
    price_astrocoins: Annotated[int, Form(ge=0, le=1_000_000)],
    tenant_slug: Annotated[str | None, Form()] = None,
    product_id: Annotated[UUID | None, Form()] = None,
    category_slug: Annotated[str | None, Form()] = None,
    status_value: Annotated[ProductStatus, Form(alias="status")] = ProductStatus.ACTIVE,
    description: Annotated[str | None, Form(max_length=1000)] = None,
    existing_photo_url: Annotated[str | None, Form(max_length=500)] = None,
    photo: Annotated[UploadFile | None, File()] = None,
) -> MiniAppProductRead:
    settings = get_settings()
    resolved_tenant = _authorized_tenant_slug(
        identity,
        max_user_id=max_user_id,
        tenant_slug=tenant_slug,
    )
    try:
        payload = MiniAppProductUpsert(
            max_user_id=max_user_id,
            tenant_slug=resolved_tenant,
            product_id=product_id,
            sku=sku,
            name=name,
            category_name=category_name,
            category_slug=category_slug,
            price_astrocoins=price_astrocoins,
            description=description or None,
            photo_url=existing_photo_url or None,
            status=status_value,
        )
    except ValidationError as exc:
        raise HTTPException(status_code=422, detail="Проверьте поля товара") from exc

    saved_image = None
    if photo is not None:
        try:
            saved_image = await save_product_image(
                photo,
                media_root=settings.product_media_root,
            )
        except ProductMediaError as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc
        absolute_photo_url = (
            f"{str(request.base_url).rstrip('/')}{saved_image.url_path}"
        )
        payload = payload.model_copy(update={"photo_url": absolute_photo_url})

    try:
        return await upsert_miniapp_product(
            db,
            payload=payload,
            default_tenant_slug=settings.default_tenant_slug,
        )
    except MiniAppStoreError as exc:
        await remove_product_image(saved_image)
        raise HTTPException(status_code=exc.status_code, detail=str(exc)) from exc
    except Exception:
        await remove_product_image(saved_image)
        raise


@router.patch("/access-links/{link_id}", response_model=MiniAppAccessStatusRead)
async def miniapp_update_access_link(
    link_id: UUID,
    payload: MiniAppAccessStatusUpdate,
    db: DbSession,
    identity: MiniAppIdentityDep,
) -> MiniAppAccessStatusRead:
    settings = get_settings()
    _authorized_tenant_slug(
        identity,
        max_user_id=payload.max_user_id,
        tenant_slug=payload.tenant_slug,
    )
    try:
        return await update_miniapp_access_link_status(
            db,
            link_id=link_id,
            payload=payload,
            default_tenant_slug=settings.default_tenant_slug,
        )
    except MiniAppStoreError as exc:
        raise HTTPException(status_code=exc.status_code, detail=str(exc)) from exc


@router.post("/staff/assignments", response_model=MiniAppStaffAssignmentRead)
async def miniapp_update_staff_assignment(
    payload: MiniAppStaffAssignmentUpdate,
    db: DbSession,
    identity: MiniAppIdentityDep,
) -> MiniAppStaffAssignmentRead:
    settings = get_settings()
    _authorized_tenant_slug(
        identity,
        max_user_id=payload.max_user_id,
        tenant_slug=payload.tenant_slug,
    )
    try:
        return await update_miniapp_staff_assignment(
            db,
            payload=payload,
            default_tenant_slug=settings.default_tenant_slug,
        )
    except MiniAppStoreError as exc:
        raise HTTPException(status_code=exc.status_code, detail=str(exc)) from exc


@router.get("/staff/onboarding/options", response_model=MiniAppStaffOnboardingOptionsRead)
async def miniapp_staff_onboarding_options(
    db: DbSession,
    identity: MiniAppIdentityDep,
    max_user_id: Annotated[int, Query(gt=0)],
    tenant_slug: str | None = None,
) -> MiniAppStaffOnboardingOptionsRead:
    _authorized_tenant_slug(
        identity,
        max_user_id=max_user_id,
        tenant_slug=tenant_slug,
    )
    try:
        return await list_miniapp_staff_onboarding_options(
            db,
            max_user_id=max_user_id,
        )
    except MiniAppStoreError as exc:
        raise HTTPException(status_code=exc.status_code, detail=str(exc)) from exc


@router.post("/inventory/adjust", response_model=MiniAppInventoryAdjustmentRead)
async def miniapp_adjust_inventory(
    payload: MiniAppInventoryAdjustmentCreate,
    db: DbSession,
    identity: MiniAppIdentityDep,
) -> MiniAppInventoryAdjustmentRead:
    settings = get_settings()
    _authorized_tenant_slug(
        identity,
        max_user_id=payload.max_user_id,
        tenant_slug=payload.tenant_slug,
    )
    try:
        return await adjust_miniapp_inventory(
            db,
            payload=payload,
            default_tenant_slug=settings.default_tenant_slug,
        )
    except MiniAppStoreError as exc:
        raise HTTPException(status_code=exc.status_code, detail=str(exc)) from exc


@router.post("/inventory/transfer", response_model=MiniAppInventoryTransferRead)
async def miniapp_transfer_inventory(
    payload: MiniAppInventoryTransferCreate,
    db: DbSession,
    identity: MiniAppIdentityDep,
) -> MiniAppInventoryTransferRead:
    settings = get_settings()
    _authorized_tenant_slug(
        identity,
        max_user_id=payload.max_user_id,
        tenant_slug=payload.tenant_slug,
    )
    try:
        return await transfer_miniapp_inventory(
            db,
            payload=payload,
            default_tenant_slug=settings.default_tenant_slug,
        )
    except MiniAppStoreError as exc:
        raise HTTPException(status_code=exc.status_code, detail=str(exc)) from exc


@router.post("/warehouses", response_model=MiniAppWarehouseRead)
async def miniapp_upsert_warehouse(
    payload: MiniAppWarehouseUpsert,
    db: DbSession,
    identity: MiniAppIdentityDep,
) -> MiniAppWarehouseRead:
    settings = get_settings()
    _authorized_tenant_slug(
        identity,
        max_user_id=payload.max_user_id,
        tenant_slug=payload.tenant_slug,
    )
    try:
        return await upsert_miniapp_warehouse(
            db,
            payload=payload,
            default_tenant_slug=settings.default_tenant_slug,
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
    identity: MiniAppIdentityDep,
) -> MiniAppOrderCreatedRead:
    settings = get_settings()
    _authorized_tenant_slug(
        identity,
        max_user_id=payload.max_user_id,
        tenant_slug=payload.tenant_slug,
    )
    try:
        return await create_miniapp_order(
            db,
            payload=payload,
            default_tenant_slug=settings.default_tenant_slug,
        )
    except MiniAppStoreError as exc:
        raise HTTPException(status_code=exc.status_code, detail=str(exc)) from exc


@router.post("/orders/{order_id}/cancel", response_model=MiniAppOrderActionRead)
async def miniapp_cancel_order(
    order_id: UUID,
    payload: MiniAppOrderActionCreate,
    db: DbSession,
    identity: MiniAppIdentityDep,
) -> MiniAppOrderActionRead:
    settings = get_settings()
    _authorized_tenant_slug(
        identity,
        max_user_id=payload.max_user_id,
        tenant_slug=payload.tenant_slug,
    )
    try:
        return await cancel_miniapp_order(
            db,
            order_id=order_id,
            payload=payload,
            default_tenant_slug=settings.default_tenant_slug,
        )
    except MiniAppStoreError as exc:
        raise HTTPException(status_code=exc.status_code, detail=str(exc)) from exc


@router.post("/orders/{order_id}/assign-warehouses", response_model=MiniAppOrderActionRead)
async def miniapp_assign_order_warehouses(
    order_id: UUID,
    payload: MiniAppOrderWarehouseAssignmentCreate,
    db: DbSession,
    identity: MiniAppIdentityDep,
) -> MiniAppOrderActionRead:
    settings = get_settings()
    _authorized_tenant_slug(
        identity,
        max_user_id=payload.max_user_id,
        tenant_slug=payload.tenant_slug,
    )
    try:
        return await assign_miniapp_order_warehouses(
            db,
            order_id=order_id,
            payload=payload,
            default_tenant_slug=settings.default_tenant_slug,
        )
    except MiniAppStoreError as exc:
        raise HTTPException(status_code=exc.status_code, detail=str(exc)) from exc


@router.post("/orders/{order_id}/issue", response_model=MiniAppOrderActionRead)
async def miniapp_issue_order(
    order_id: UUID,
    payload: MiniAppOrderActionCreate,
    db: DbSession,
    identity: MiniAppIdentityDep,
) -> MiniAppOrderActionRead:
    settings = get_settings()
    _authorized_tenant_slug(
        identity,
        max_user_id=payload.max_user_id,
        tenant_slug=payload.tenant_slug,
    )
    try:
        return await issue_miniapp_order(
            db,
            order_id=order_id,
            payload=payload,
            default_tenant_slug=settings.default_tenant_slug,
        )
    except MiniAppStoreError as exc:
        raise HTTPException(status_code=exc.status_code, detail=str(exc)) from exc


@router.post("/orders/{order_id}/return", response_model=MiniAppOrderActionRead)
async def miniapp_return_order(
    order_id: UUID,
    payload: MiniAppOrderActionCreate,
    db: DbSession,
    identity: MiniAppIdentityDep,
) -> MiniAppOrderActionRead:
    settings = get_settings()
    _authorized_tenant_slug(
        identity,
        max_user_id=payload.max_user_id,
        tenant_slug=payload.tenant_slug,
    )
    try:
        return await return_miniapp_order(
            db,
            order_id=order_id,
            payload=payload,
            default_tenant_slug=settings.default_tenant_slug,
        )
    except MiniAppStoreError as exc:
        raise HTTPException(status_code=exc.status_code, detail=str(exc)) from exc


@router.post("/coins/accrue", response_model=MiniAppAccrualRead)
async def miniapp_accrue_coins(
    payload: MiniAppAccrualCreate,
    db: DbSession,
    identity: MiniAppIdentityDep,
) -> MiniAppAccrualRead:
    settings = get_settings()
    _authorized_tenant_slug(
        identity,
        max_user_id=payload.max_user_id,
        tenant_slug=payload.tenant_slug,
    )
    try:
        return await accrue_miniapp_astrocoins(
            db,
            payload=payload,
            default_tenant_slug=settings.default_tenant_slug,
        )
    except MiniAppStoreError as exc:
        raise HTTPException(status_code=exc.status_code, detail=str(exc)) from exc
