import json
from datetime import date
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
    Response,
    UploadFile,
    status,
)
from pydantic import ValidationError
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.dependencies import (
    get_miniapp_identity,
    require_matching_miniapp_identity,
)
from app.core.config import get_settings
from app.core.miniapp_auth import MiniAppIdentity
from app.db.session import get_db_session
from app.models.enums import ProductFulfillmentType, ProductStatus, StudentStatus
from app.models.store import Product
from app.models.tenant import Tenant
from app.schemas.broadcasts import (
    BroadcastAudiencePreviewRead,
    BroadcastAudienceRequest,
    BroadcastTargetOptionsRead,
    BroadcastVenueRuleRead,
    BroadcastVenueRuleUpsert,
    SchoolBroadcastRead,
)
from app.schemas.miniapp import (
    MiniAppAccessStatusRead,
    MiniAppAccessStatusUpdate,
    MiniAppAccrualCreate,
    MiniAppAccrualRead,
    MiniAppAccrualReportRead,
    MiniAppAccrualRuleRead,
    MiniAppAccrualRulesUpdate,
    MiniAppAccrualUndoCreate,
    MiniAppAdminHistoryRead,
    MiniAppCartRead,
    MiniAppCartWrite,
    MiniAppCatalogRead,
    MiniAppCrmImportRead,
    MiniAppInventoryAdjustmentCreate,
    MiniAppInventoryAdjustmentRead,
    MiniAppInventoryTransferCreate,
    MiniAppInventoryTransferRead,
    MiniAppLedgerRead,
    MiniAppOpsSummaryRead,
    MiniAppOrderActionCreate,
    MiniAppOrderActionRead,
    MiniAppOrderCancelCreate,
    MiniAppOrderCreate,
    MiniAppOrderCreatedRead,
    MiniAppOrderItemPickBatchRead,
    MiniAppOrderItemPickBatchUpdate,
    MiniAppOrderWarehouseAssignmentCreate,
    MiniAppProductImportRead,
    MiniAppProductRead,
    MiniAppProductUpsert,
    MiniAppSessionRead,
    MiniAppStaffAssignmentRead,
    MiniAppStaffAssignmentUpdate,
    MiniAppStaffInvitationCreate,
    MiniAppStaffInvitationRead,
    MiniAppStaffInvitationRedeem,
    MiniAppStaffInvitationRedeemedRead,
    MiniAppStaffNotificationSettingsRead,
    MiniAppStaffNotificationSettingsUpdate,
    MiniAppStaffOnboardingOptionsRead,
    MiniAppStudentAccessPolicyRead,
    MiniAppStudentAccessPolicyUpdate,
    MiniAppStudentBalanceUpdate,
    MiniAppStudentBirthDateUpdate,
    MiniAppStudentCreate,
    MiniAppStudentInvitationRead,
    MiniAppStudentRegistryRead,
    MiniAppStudentStatusUpdate,
    MiniAppTeacherProfileRead,
    MiniAppTeacherProfileUpdate,
    MiniAppTenantCreate,
    MiniAppTenantCreatedRead,
    MiniAppWarehousePreferenceRead,
    MiniAppWarehousePreferenceUpdate,
    MiniAppWarehouseRead,
    MiniAppWarehouseUpsert,
)
from app.services.broadcasts import (
    BroadcastServiceError,
    get_broadcast_target_options,
    list_school_broadcasts,
    preview_school_broadcast,
    send_school_broadcast,
    upsert_broadcast_venue_rule,
)
from app.services.crm_import import CRM_TEMPLATE_SHEET_NAME
from app.services.miniapp import (
    MiniAppStoreError,
    accrue_miniapp_astrocoins,
    adjust_miniapp_inventory,
    assign_miniapp_order_warehouses,
    cancel_miniapp_order,
    create_miniapp_order,
    create_miniapp_staff_invitation,
    create_miniapp_student,
    create_miniapp_tenant,
    delete_miniapp_product,
    delete_miniapp_warehouse,
    get_miniapp_accrual_report,
    get_miniapp_cart,
    get_miniapp_ops_summary,
    get_miniapp_session,
    get_miniapp_staff_notification_settings,
    get_miniapp_student_invitation,
    import_miniapp_crm_students,
    import_miniapp_products,
    issue_miniapp_order,
    list_miniapp_admin_history,
    list_miniapp_catalog,
    list_miniapp_staff_onboarding_options,
    list_miniapp_student_ledger,
    list_miniapp_student_registry,
    list_miniapp_teacher_invitations,
    mark_miniapp_order_delivered_to_venue,
    redeem_miniapp_staff_invitation,
    replace_miniapp_cart,
    set_miniapp_order_items_picked,
    set_miniapp_student_balance,
    set_miniapp_warehouse_preference,
    transfer_miniapp_inventory,
    transfer_miniapp_order_to_teacher,
    undo_miniapp_astrocoins,
    update_miniapp_access_link_status,
    update_miniapp_accrual_rules,
    update_miniapp_staff_assignment,
    update_miniapp_staff_notification_settings,
    update_miniapp_student_access_policy,
    update_miniapp_student_birth_date,
    update_miniapp_student_status,
    update_miniapp_teacher_profile,
    upsert_miniapp_product,
    upsert_miniapp_warehouse,
)
from app.services.product_import import build_product_import_template
from app.services.product_media import (
    ProductMediaError,
    remove_product_image,
    remove_product_image_url,
    save_product_image,
)

router = APIRouter()
DbSession = Annotated[AsyncSession, Depends(get_db_session)]
MiniAppIdentityDep = Annotated[MiniAppIdentity | None, Depends(get_miniapp_identity)]
MAX_IMPORT_FILE_BYTES = 20 * 1024 * 1024


async def _read_import_file(upload: UploadFile) -> bytes:
    try:
        content = await upload.read(MAX_IMPORT_FILE_BYTES + 1)
    finally:
        await upload.close()
    if not content:
        raise HTTPException(status_code=400, detail="Выбранный файл пуст")
    if len(content) > MAX_IMPORT_FILE_BYTES:
        raise HTTPException(status_code=413, detail="Файл импорта должен быть не больше 20 МБ")
    return content


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
        discover_tenant=tenant_slug is None,
    )


@router.post(
    "/broadcasts/preview",
    response_model=BroadcastAudiencePreviewRead,
)
async def miniapp_broadcast_preview(
    payload: BroadcastAudienceRequest,
    db: DbSession,
    identity: MiniAppIdentityDep,
) -> BroadcastAudiencePreviewRead:
    settings = get_settings()
    resolved_tenant = _authorized_tenant_slug(
        identity,
        max_user_id=payload.max_user_id,
        tenant_slug=payload.tenant_slug,
    )
    try:
        return await preview_school_broadcast(
            db,
            payload=payload.model_copy(update={"tenant_slug": resolved_tenant}),
            default_tenant_slug=settings.default_tenant_slug,
        )
    except BroadcastServiceError as exc:
        raise HTTPException(status_code=exc.status_code, detail=str(exc)) from exc


@router.get(
    "/broadcasts/options",
    response_model=BroadcastTargetOptionsRead,
)
async def miniapp_broadcast_options(
    db: DbSession,
    identity: MiniAppIdentityDep,
    max_user_id: Annotated[int, Query(gt=0)],
    tenant_slug: str | None = None,
) -> BroadcastTargetOptionsRead:
    settings = get_settings()
    resolved_tenant = _authorized_tenant_slug(
        identity,
        max_user_id=max_user_id,
        tenant_slug=tenant_slug,
    )
    try:
        return await get_broadcast_target_options(
            db,
            max_user_id=max_user_id,
            tenant_slug=resolved_tenant or settings.default_tenant_slug,
        )
    except BroadcastServiceError as exc:
        raise HTTPException(status_code=exc.status_code, detail=str(exc)) from exc


async def _save_broadcast_venue_rule(
    *,
    payload: BroadcastVenueRuleUpsert,
    db: AsyncSession,
    identity: MiniAppIdentity | None,
    venue_id: UUID | None,
) -> BroadcastVenueRuleRead:
    settings = get_settings()
    resolved_tenant = _authorized_tenant_slug(
        identity,
        max_user_id=payload.max_user_id,
        tenant_slug=payload.tenant_slug,
    )
    try:
        return await upsert_broadcast_venue_rule(
            db,
            payload=payload.model_copy(update={"tenant_slug": resolved_tenant}),
            default_tenant_slug=settings.default_tenant_slug,
            venue_id=venue_id,
        )
    except BroadcastServiceError as exc:
        raise HTTPException(status_code=exc.status_code, detail=str(exc)) from exc


@router.post(
    "/broadcasts/venues",
    response_model=BroadcastVenueRuleRead,
    status_code=status.HTTP_201_CREATED,
)
async def miniapp_broadcast_venue_create(
    payload: BroadcastVenueRuleUpsert,
    db: DbSession,
    identity: MiniAppIdentityDep,
) -> BroadcastVenueRuleRead:
    return await _save_broadcast_venue_rule(
        payload=payload,
        db=db,
        identity=identity,
        venue_id=None,
    )


@router.put(
    "/broadcasts/venues/{venue_id}",
    response_model=BroadcastVenueRuleRead,
)
async def miniapp_broadcast_venue_update(
    venue_id: UUID,
    payload: BroadcastVenueRuleUpsert,
    db: DbSession,
    identity: MiniAppIdentityDep,
) -> BroadcastVenueRuleRead:
    return await _save_broadcast_venue_rule(
        payload=payload,
        db=db,
        identity=identity,
        venue_id=venue_id,
    )


@router.get(
    "/broadcasts",
    response_model=list[SchoolBroadcastRead],
)
async def miniapp_broadcast_history(
    db: DbSession,
    identity: MiniAppIdentityDep,
    max_user_id: Annotated[int, Query(gt=0)],
    tenant_slug: str | None = None,
) -> list[SchoolBroadcastRead]:
    settings = get_settings()
    resolved_tenant = _authorized_tenant_slug(
        identity,
        max_user_id=max_user_id,
        tenant_slug=tenant_slug,
    )
    try:
        return await list_school_broadcasts(
            db,
            max_user_id=max_user_id,
            tenant_slug=resolved_tenant or settings.default_tenant_slug,
        )
    except BroadcastServiceError as exc:
        raise HTTPException(status_code=exc.status_code, detail=str(exc)) from exc


@router.post(
    "/broadcasts",
    response_model=SchoolBroadcastRead,
    status_code=status.HTTP_201_CREATED,
)
async def miniapp_broadcast_send(
    request: Request,
    db: DbSession,
    identity: MiniAppIdentityDep,
    max_user_id: Annotated[int, Form(gt=0)],
    message: Annotated[str, Form(min_length=1, max_length=3500)],
    tenant_slug: Annotated[str | None, Form()] = None,
    title: Annotated[str | None, Form(max_length=160)] = None,
    recipient_category: Annotated[str, Form()] = "all",
    audience_filter: Annotated[str, Form()] = "all",
    group_names: Annotated[list[str] | None, Form()] = None,
    venue_names: Annotated[list[str] | None, Form()] = None,
    lesson_modes: Annotated[list[str] | None, Form()] = None,
    balance_threshold: Annotated[int | None, Form(ge=0, le=1_000_000)] = None,
    photo: Annotated[UploadFile | None, File()] = None,
) -> SchoolBroadcastRead:
    settings = get_settings()
    resolved_tenant = _authorized_tenant_slug(
        identity,
        max_user_id=max_user_id,
        tenant_slug=tenant_slug,
    )
    try:
        payload = BroadcastAudienceRequest(
            max_user_id=max_user_id,
            tenant_slug=resolved_tenant,
            recipient_category=recipient_category,
            audience_filter=audience_filter,
            group_names=group_names or [],
            venue_names=venue_names or [],
            lesson_modes=lesson_modes or [],
            balance_threshold=balance_threshold,
        )
    except ValidationError as exc:
        raise HTTPException(
            status_code=422,
            detail="Проверьте параметры аудитории",
        ) from exc

    saved_image = None
    image_url = None
    if photo is not None:
        try:
            saved_image = await save_product_image(
                photo,
                media_root=settings.product_media_root,
                subject="Изображение",
            )
        except ProductMediaError as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc
        image_url = f"{str(request.base_url).rstrip('/')}{saved_image.url_path}"

    try:
        return await send_school_broadcast(
            db,
            payload=payload,
            title=title,
            message=message,
            image_url=image_url,
            default_tenant_slug=settings.default_tenant_slug,
        )
    except BroadcastServiceError as exc:
        await remove_product_image(saved_image)
        raise HTTPException(status_code=exc.status_code, detail=str(exc)) from exc
    except Exception:
        await remove_product_image(saved_image)
        raise


@router.get(
    "/students/registry",
    response_model=MiniAppStudentRegistryRead,
)
async def miniapp_student_registry(
    db: DbSession,
    identity: MiniAppIdentityDep,
    max_user_id: Annotated[int, Query(gt=0)],
    tenant_slug: str | None = None,
) -> MiniAppStudentRegistryRead:
    resolved_tenant = _authorized_tenant_slug(
        identity,
        max_user_id=max_user_id,
        tenant_slug=tenant_slug,
    )
    if not resolved_tenant:
        raise HTTPException(status_code=400, detail="Не выбран город или партнер")
    try:
        return await list_miniapp_student_registry(
            db,
            max_user_id=max_user_id,
            tenant_slug=resolved_tenant,
        )
    except MiniAppStoreError as exc:
        raise HTTPException(status_code=exc.status_code, detail=str(exc)) from exc


@router.get(
    "/students/{student_id}/ledger",
    response_model=list[MiniAppLedgerRead],
)
async def miniapp_student_ledger(
    student_id: UUID,
    db: DbSession,
    identity: MiniAppIdentityDep,
    max_user_id: Annotated[int, Query(gt=0)],
    tenant_slug: str | None = None,
    limit: Annotated[int, Query(ge=1, le=200)] = 100,
) -> list[MiniAppLedgerRead]:
    resolved_tenant = _authorized_tenant_slug(
        identity,
        max_user_id=max_user_id,
        tenant_slug=tenant_slug,
    )
    if not resolved_tenant:
        raise HTTPException(status_code=400, detail="Не выбран город или партнер")
    try:
        return await list_miniapp_student_ledger(
            db,
            max_user_id=max_user_id,
            tenant_slug=resolved_tenant,
            student_id=student_id,
            limit=limit,
        )
    except MiniAppStoreError as exc:
        raise HTTPException(status_code=exc.status_code, detail=str(exc)) from exc


@router.post(
    "/students",
    response_model=MiniAppStudentRegistryRead,
    status_code=status.HTTP_201_CREATED,
)
async def miniapp_student_create(
    payload: MiniAppStudentCreate,
    db: DbSession,
    identity: MiniAppIdentityDep,
) -> MiniAppStudentRegistryRead:
    _authorized_tenant_slug(
        identity,
        max_user_id=payload.max_user_id,
        tenant_slug=payload.tenant_slug,
    )
    try:
        return await create_miniapp_student(
            db,
            payload=payload,
            default_tenant_slug=get_settings().default_tenant_slug,
        )
    except MiniAppStoreError as exc:
        raise HTTPException(status_code=exc.status_code, detail=str(exc)) from exc


@router.patch(
    "/students/{student_id}/birth-date",
    response_model=MiniAppStudentRegistryRead,
)
async def miniapp_student_birth_date_update(
    student_id: UUID,
    payload: MiniAppStudentBirthDateUpdate,
    db: DbSession,
    identity: MiniAppIdentityDep,
) -> MiniAppStudentRegistryRead:
    _authorized_tenant_slug(
        identity,
        max_user_id=payload.max_user_id,
        tenant_slug=payload.tenant_slug,
    )
    try:
        return await update_miniapp_student_birth_date(
            db,
            student_id=student_id,
            payload=payload,
            default_tenant_slug=get_settings().default_tenant_slug,
        )
    except MiniAppStoreError as exc:
        raise HTTPException(status_code=exc.status_code, detail=str(exc)) from exc


@router.patch(
    "/students/{student_id}/status",
    response_model=MiniAppStudentRegistryRead,
)
async def miniapp_student_status_update(
    student_id: UUID,
    payload: MiniAppStudentStatusUpdate,
    db: DbSession,
    identity: MiniAppIdentityDep,
) -> MiniAppStudentRegistryRead:
    _authorized_tenant_slug(
        identity,
        max_user_id=payload.max_user_id,
        tenant_slug=payload.tenant_slug,
    )
    try:
        return await update_miniapp_student_status(
            db,
            student_id=student_id,
            payload=payload,
            default_tenant_slug=get_settings().default_tenant_slug,
        )
    except MiniAppStoreError as exc:
        raise HTTPException(status_code=exc.status_code, detail=str(exc)) from exc


@router.put(
    "/students/{student_id}/balance",
    response_model=MiniAppStudentRegistryRead,
)
async def miniapp_student_balance_update(
    student_id: UUID,
    payload: MiniAppStudentBalanceUpdate,
    db: DbSession,
    identity: MiniAppIdentityDep,
) -> MiniAppStudentRegistryRead:
    _authorized_tenant_slug(
        identity,
        max_user_id=payload.max_user_id,
        tenant_slug=payload.tenant_slug,
    )
    try:
        return await set_miniapp_student_balance(
            db,
            student_id=student_id,
            payload=payload,
            default_tenant_slug=get_settings().default_tenant_slug,
        )
    except MiniAppStoreError as exc:
        raise HTTPException(status_code=exc.status_code, detail=str(exc)) from exc


@router.get(
    "/admin/history",
    response_model=MiniAppAdminHistoryRead,
)
async def miniapp_admin_history(
    db: DbSession,
    identity: MiniAppIdentityDep,
    max_user_id: Annotated[int, Query(gt=0)],
    tenant_slug: str | None = None,
    kind: Annotated[str, Query(pattern="^(actions|amocrm)$")] = "actions",
    period_days: Annotated[int, Query(ge=1, le=365)] = 30,
    limit: Annotated[int, Query(ge=1, le=300)] = 100,
) -> MiniAppAdminHistoryRead:
    resolved_tenant = _authorized_tenant_slug(
        identity,
        max_user_id=max_user_id,
        tenant_slug=tenant_slug,
    )
    try:
        return await list_miniapp_admin_history(
            db,
            max_user_id=max_user_id,
            tenant_slug=resolved_tenant,
            kind=kind,
            period_days=period_days,
            limit=limit,
        )
    except MiniAppStoreError as exc:
        raise HTTPException(status_code=exc.status_code, detail=str(exc)) from exc


@router.get("/students/invitations", response_model=list[MiniAppStudentInvitationRead])
async def miniapp_teacher_invitations(
    db: DbSession,
    identity: MiniAppIdentityDep,
    max_user_id: Annotated[int, Query(gt=0)],
    tenant_slug: str | None = None,
) -> list[MiniAppStudentInvitationRead]:
    resolved_tenant = _authorized_tenant_slug(
        identity,
        max_user_id=max_user_id,
        tenant_slug=tenant_slug,
    )
    try:
        return await list_miniapp_teacher_invitations(
            db,
            max_user_id=max_user_id,
            tenant_slug=resolved_tenant,
        )
    except MiniAppStoreError as exc:
        raise HTTPException(status_code=exc.status_code, detail=str(exc)) from exc


@router.get("/students/{student_id}/invitation", response_model=MiniAppStudentInvitationRead)
async def miniapp_student_invitation(
    student_id: UUID,
    db: DbSession,
    identity: MiniAppIdentityDep,
    max_user_id: Annotated[int, Query(gt=0)],
    tenant_slug: str | None = None,
) -> MiniAppStudentInvitationRead:
    resolved_tenant = _authorized_tenant_slug(
        identity,
        max_user_id=max_user_id,
        tenant_slug=tenant_slug,
    )
    try:
        return await get_miniapp_student_invitation(
            db,
            max_user_id=max_user_id,
            tenant_slug=resolved_tenant,
            student_id=student_id,
        )
    except MiniAppStoreError as exc:
        raise HTTPException(status_code=exc.status_code, detail=str(exc)) from exc


@router.put(
    "/students/access-policy",
    response_model=MiniAppStudentAccessPolicyRead,
)
async def miniapp_update_student_access_policy(
    payload: MiniAppStudentAccessPolicyUpdate,
    db: DbSession,
    identity: MiniAppIdentityDep,
) -> MiniAppStudentAccessPolicyRead:
    settings = get_settings()
    _authorized_tenant_slug(
        identity,
        max_user_id=payload.max_user_id,
        tenant_slug=payload.tenant_slug,
    )
    try:
        return await update_miniapp_student_access_policy(
            db,
            payload=payload,
            default_tenant_slug=settings.default_tenant_slug,
        )
    except MiniAppStoreError as exc:
        raise HTTPException(status_code=exc.status_code, detail=str(exc)) from exc


@router.post("/tenants", response_model=MiniAppTenantCreatedRead)
async def miniapp_create_tenant(
    payload: MiniAppTenantCreate,
    db: DbSession,
    identity: MiniAppIdentityDep,
) -> MiniAppTenantCreatedRead:
    _authorized_tenant_slug(
        identity,
        max_user_id=payload.max_user_id,
        tenant_slug=payload.tenant_slug,
    )
    try:
        return await create_miniapp_tenant(db, payload=payload)
    except MiniAppStoreError as exc:
        raise HTTPException(status_code=exc.status_code, detail=str(exc)) from exc


@router.get("/catalog", response_model=MiniAppCatalogRead)
async def miniapp_catalog(
    db: DbSession,
    identity: MiniAppIdentityDep,
    max_user_id: Annotated[int, Query(gt=0)],
    tenant_slug: str | None = None,
    include_inactive: bool = False,
) -> MiniAppCatalogRead:
    effective_max_user_id = max_user_id
    resolved_tenant = _authorized_tenant_slug(
        identity,
        max_user_id=effective_max_user_id,
        tenant_slug=tenant_slug,
    )
    try:
        return await list_miniapp_catalog(
            db,
            tenant_slug=resolved_tenant,
            max_user_id=effective_max_user_id,
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
    request: Request,
    max_user_id: Annotated[int, Form(gt=0)],
    file: Annotated[UploadFile, File()],
    tenant_slug: Annotated[str | None, Form()] = None,
) -> MiniAppProductImportRead:
    resolved_tenant = _authorized_tenant_slug(
        identity,
        max_user_id=max_user_id,
        tenant_slug=tenant_slug,
    )
    filename = file.filename or "products.csv"
    content = await _read_import_file(file)
    try:
        return await import_miniapp_products(
            db,
            max_user_id=max_user_id,
            tenant_slug=resolved_tenant,
            filename=filename,
            content=content,
            media_root=get_settings().product_media_root,
            media_base_url=str(request.base_url).rstrip("/"),
        )
    except MiniAppStoreError as exc:
        raise HTTPException(status_code=exc.status_code, detail=str(exc)) from exc


@router.get("/products/import-template")
async def miniapp_product_import_template() -> Response:
    return Response(
        content=build_product_import_template(),
        media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        headers={
            "Content-Disposition": 'attachment; filename="algo-max-products-template.xlsx"'
        },
    )


@router.post("/students/import", response_model=MiniAppCrmImportRead)
async def miniapp_import_crm_students(
    db: DbSession,
    identity: MiniAppIdentityDep,
    max_user_id: Annotated[int, Form(gt=0)],
    file: Annotated[UploadFile, File()],
    tenant_slug: Annotated[str | None, Form()] = None,
    sheet_name: Annotated[str, Form()] = CRM_TEMPLATE_SHEET_NAME,
    dry_run: Annotated[bool, Form()] = True,
    student_status: Annotated[StudentStatus, Form()] = StudentStatus.ACTIVE,
) -> MiniAppCrmImportRead:
    resolved_tenant = _authorized_tenant_slug(
        identity,
        max_user_id=max_user_id,
        tenant_slug=tenant_slug,
    )
    filename = file.filename or "students.xlsx"
    content = await _read_import_file(file)
    try:
        return await import_miniapp_crm_students(
            db,
            max_user_id=max_user_id,
            tenant_slug=resolved_tenant,
            filename=filename,
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
    name: Annotated[str, Form(min_length=2, max_length=200)],
    category_name: Annotated[str, Form(min_length=2, max_length=160)],
    price_astrocoins: Annotated[int, Form(ge=0, le=1_000_000)],
    sku: Annotated[str | None, Form(max_length=120)] = None,
    tenant_slug: Annotated[str | None, Form()] = None,
    product_id: Annotated[UUID | None, Form()] = None,
    category_slug: Annotated[str | None, Form()] = None,
    status_value: Annotated[ProductStatus, Form(alias="status")] = ProductStatus.ACTIVE,
    description: Annotated[str | None, Form(max_length=1000)] = None,
    existing_photo_url: Annotated[str | None, Form(max_length=500)] = None,
    fulfillment_type: Annotated[
        ProductFulfillmentType,
        Form(),
    ] = ProductFulfillmentType.WAREHOUSE,
    new_codes: Annotated[str | None, Form(max_length=250000)] = None,
    inventories: Annotated[str | None, Form(max_length=250000)] = None,
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
            fulfillment_type=fulfillment_type,
            new_codes=(new_codes or "").splitlines(),
            inventories=json.loads(inventories) if inventories is not None else None,
        )
    except (json.JSONDecodeError, TypeError, ValidationError) as exc:
        raise HTTPException(status_code=422, detail="Проверьте поля товара") from exc

    previous_photo_url = None
    if photo is not None:
        tenant = await db.scalar(select(Tenant).where(Tenant.slug == resolved_tenant))
        if tenant is not None:
            existing_product = None
            if product_id is not None:
                existing_product = await db.scalar(
                    select(Product).where(
                        Product.tenant_id == tenant.id,
                        Product.id == product_id,
                    )
                )
            elif sku:
                existing_product = await db.scalar(
                    select(Product).where(
                        Product.tenant_id == tenant.id,
                        Product.sku == sku.strip().upper(),
                    )
                )
            if existing_product is not None:
                previous_photo_url = existing_product.photo_url

    saved_image = None
    if photo is not None:
        try:
            saved_image = await save_product_image(
                photo,
                media_root=settings.product_media_root,
            )
        except ProductMediaError as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc
        absolute_photo_url = f"{str(request.base_url).rstrip('/')}{saved_image.url_path}"
        payload = payload.model_copy(update={"photo_url": absolute_photo_url})

    try:
        result = await upsert_miniapp_product(
            db,
            payload=payload,
            default_tenant_slug=settings.default_tenant_slug,
        )
        if saved_image is not None and previous_photo_url != result.photo_url:
            await remove_product_image_url(
                previous_photo_url,
                media_root=settings.product_media_root,
            )
        return result
    except MiniAppStoreError as exc:
        await remove_product_image(saved_image)
        raise HTTPException(status_code=exc.status_code, detail=str(exc)) from exc
    except Exception:
        await remove_product_image(saved_image)
        raise


@router.delete("/products/{product_id}", status_code=status.HTTP_204_NO_CONTENT)
async def miniapp_delete_product(
    product_id: UUID,
    db: DbSession,
    identity: MiniAppIdentityDep,
    max_user_id: Annotated[int, Query(gt=0)],
    tenant_slug: Annotated[str | None, Query()] = None,
) -> Response:
    settings = get_settings()
    resolved_tenant = _authorized_tenant_slug(
        identity,
        max_user_id=max_user_id,
        tenant_slug=tenant_slug,
    )
    try:
        photo_url = await delete_miniapp_product(
            db,
            product_id=product_id,
            max_user_id=max_user_id,
            tenant_slug=resolved_tenant,
            default_tenant_slug=settings.default_tenant_slug,
        )
    except MiniAppStoreError as exc:
        raise HTTPException(status_code=exc.status_code, detail=str(exc)) from exc
    await remove_product_image_url(photo_url, media_root=settings.product_media_root)
    return Response(status_code=status.HTTP_204_NO_CONTENT)


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


@router.put("/teacher/profile", response_model=MiniAppTeacherProfileRead)
async def miniapp_update_teacher_profile(
    payload: MiniAppTeacherProfileUpdate,
    db: DbSession,
    identity: MiniAppIdentityDep,
) -> MiniAppTeacherProfileRead:
    settings = get_settings()
    _authorized_tenant_slug(
        identity,
        max_user_id=payload.max_user_id,
        tenant_slug=payload.tenant_slug,
    )
    try:
        return await update_miniapp_teacher_profile(
            db,
            payload=payload,
            default_tenant_slug=settings.default_tenant_slug,
        )
    except MiniAppStoreError as exc:
        raise HTTPException(status_code=exc.status_code, detail=str(exc)) from exc


@router.post("/staff/invitations", response_model=MiniAppStaffInvitationRead)
async def miniapp_create_staff_invitation(
    payload: MiniAppStaffInvitationCreate,
    db: DbSession,
    identity: MiniAppIdentityDep,
) -> MiniAppStaffInvitationRead:
    settings = get_settings()
    _authorized_tenant_slug(
        identity,
        max_user_id=payload.max_user_id,
        tenant_slug=payload.tenant_slug,
    )
    try:
        return await create_miniapp_staff_invitation(
            db,
            payload=payload,
            default_tenant_slug=settings.default_tenant_slug,
        )
    except MiniAppStoreError as exc:
        raise HTTPException(status_code=exc.status_code, detail=str(exc)) from exc


@router.post(
    "/staff/invitations/redeem",
    response_model=MiniAppStaffInvitationRedeemedRead,
)
async def miniapp_redeem_staff_invitation(
    payload: MiniAppStaffInvitationRedeem,
    db: DbSession,
    identity: MiniAppIdentityDep,
) -> MiniAppStaffInvitationRedeemedRead:
    if identity is not None and identity.max_user_id != payload.max_user_id:
        raise HTTPException(status_code=403, detail="MAX-профиль не совпадает с приглашением")
    try:
        return await redeem_miniapp_staff_invitation(db, payload=payload)
    except MiniAppStoreError as exc:
        raise HTTPException(status_code=exc.status_code, detail=str(exc)) from exc


@router.get(
    "/staff/{target_account_id}/notifications",
    response_model=MiniAppStaffNotificationSettingsRead,
)
async def miniapp_staff_notification_settings(
    target_account_id: UUID,
    db: DbSession,
    identity: MiniAppIdentityDep,
    max_user_id: Annotated[int, Query(gt=0)],
    tenant_slug: str | None = None,
) -> MiniAppStaffNotificationSettingsRead:
    settings = get_settings()
    resolved_tenant = _authorized_tenant_slug(
        identity,
        max_user_id=max_user_id,
        tenant_slug=tenant_slug,
    )
    try:
        return await get_miniapp_staff_notification_settings(
            db,
            actor_max_user_id=max_user_id,
            tenant_slug=resolved_tenant or settings.default_tenant_slug,
            target_account_id=target_account_id,
        )
    except MiniAppStoreError as exc:
        raise HTTPException(status_code=exc.status_code, detail=str(exc)) from exc


@router.put(
    "/staff/{target_account_id}/notifications",
    response_model=MiniAppStaffNotificationSettingsRead,
)
async def miniapp_update_staff_notification_settings(
    target_account_id: UUID,
    payload: MiniAppStaffNotificationSettingsUpdate,
    db: DbSession,
    identity: MiniAppIdentityDep,
) -> MiniAppStaffNotificationSettingsRead:
    settings = get_settings()
    _authorized_tenant_slug(
        identity,
        max_user_id=payload.max_user_id,
        tenant_slug=payload.tenant_slug,
    )
    try:
        return await update_miniapp_staff_notification_settings(
            db,
            target_account_id=target_account_id,
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


@router.delete("/warehouses/{warehouse_id}", status_code=status.HTTP_204_NO_CONTENT)
async def miniapp_delete_warehouse(
    warehouse_id: UUID,
    db: DbSession,
    identity: MiniAppIdentityDep,
    max_user_id: Annotated[int, Query(gt=0)],
    tenant_slug: Annotated[str | None, Query()] = None,
) -> Response:
    settings = get_settings()
    resolved_tenant = _authorized_tenant_slug(
        identity,
        max_user_id=max_user_id,
        tenant_slug=tenant_slug,
    )
    try:
        await delete_miniapp_warehouse(
            db,
            warehouse_id=warehouse_id,
            max_user_id=max_user_id,
            tenant_slug=resolved_tenant,
            default_tenant_slug=settings.default_tenant_slug,
        )
    except MiniAppStoreError as exc:
        raise HTTPException(status_code=exc.status_code, detail=str(exc)) from exc
    return Response(status_code=status.HTTP_204_NO_CONTENT)


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


@router.get(
    "/students/{student_id}/cart",
    response_model=MiniAppCartRead,
)
async def miniapp_cart(
    student_id: UUID,
    db: DbSession,
    identity: MiniAppIdentityDep,
    max_user_id: Annotated[int, Query(gt=0)],
    tenant_slug: str | None = None,
) -> MiniAppCartRead:
    resolved_tenant = _authorized_tenant_slug(
        identity,
        max_user_id=max_user_id,
        tenant_slug=tenant_slug,
    )
    try:
        return await get_miniapp_cart(
            db,
            max_user_id=max_user_id,
            tenant_slug=resolved_tenant,
            student_id=student_id,
        )
    except MiniAppStoreError as exc:
        raise HTTPException(status_code=exc.status_code, detail=str(exc)) from exc


@router.put(
    "/students/{student_id}/cart",
    response_model=MiniAppCartRead,
)
async def miniapp_replace_cart(
    student_id: UUID,
    payload: MiniAppCartWrite,
    db: DbSession,
    identity: MiniAppIdentityDep,
) -> MiniAppCartRead:
    resolved_tenant = _authorized_tenant_slug(
        identity,
        max_user_id=payload.max_user_id,
        tenant_slug=payload.tenant_slug,
    )
    try:
        return await replace_miniapp_cart(
            db,
            student_id=student_id,
            payload=payload,
            tenant_slug=resolved_tenant,
        )
    except MiniAppStoreError as exc:
        raise HTTPException(status_code=exc.status_code, detail=str(exc)) from exc


@router.post("/orders/{order_id}/cancel", response_model=MiniAppOrderActionRead)
async def miniapp_cancel_order(
    order_id: UUID,
    payload: MiniAppOrderCancelCreate,
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


@router.post("/orders/{order_id}/transfer-to-teacher", response_model=MiniAppOrderActionRead)
async def miniapp_transfer_order_to_teacher(
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
        return await transfer_miniapp_order_to_teacher(
            db,
            order_id=order_id,
            payload=payload,
            default_tenant_slug=settings.default_tenant_slug,
        )
    except MiniAppStoreError as exc:
        raise HTTPException(status_code=exc.status_code, detail=str(exc)) from exc


@router.post("/orders/{order_id}/delivered-to-venue", response_model=MiniAppOrderActionRead)
async def miniapp_mark_order_delivered_to_venue(
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
        return await mark_miniapp_order_delivered_to_venue(
            db,
            order_id=order_id,
            payload=payload,
            default_tenant_slug=settings.default_tenant_slug,
        )
    except MiniAppStoreError as exc:
        raise HTTPException(status_code=exc.status_code, detail=str(exc)) from exc


@router.post("/orders/picks", response_model=MiniAppOrderItemPickBatchRead)
async def miniapp_set_order_items_picked(
    payload: MiniAppOrderItemPickBatchUpdate,
    db: DbSession,
    identity: MiniAppIdentityDep,
) -> MiniAppOrderItemPickBatchRead:
    settings = get_settings()
    _authorized_tenant_slug(
        identity,
        max_user_id=payload.max_user_id,
        tenant_slug=payload.tenant_slug,
    )
    try:
        return await set_miniapp_order_items_picked(
            db,
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


@router.put("/coins/rules", response_model=list[MiniAppAccrualRuleRead])
async def miniapp_update_accrual_rules(
    payload: MiniAppAccrualRulesUpdate,
    db: DbSession,
    identity: MiniAppIdentityDep,
) -> list[MiniAppAccrualRuleRead]:
    settings = get_settings()
    _authorized_tenant_slug(
        identity,
        max_user_id=payload.max_user_id,
        tenant_slug=payload.tenant_slug,
    )
    try:
        return await update_miniapp_accrual_rules(
            db,
            payload=payload,
            default_tenant_slug=settings.default_tenant_slug,
        )
    except MiniAppStoreError as exc:
        raise HTTPException(status_code=exc.status_code, detail=str(exc)) from exc


@router.post("/coins/accrue/undo", response_model=MiniAppAccrualRead)
async def miniapp_undo_accrual(
    payload: MiniAppAccrualUndoCreate,
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
        return await undo_miniapp_astrocoins(
            db,
            payload=payload,
            default_tenant_slug=settings.default_tenant_slug,
        )
    except MiniAppStoreError as exc:
        raise HTTPException(status_code=exc.status_code, detail=str(exc)) from exc


@router.get("/coins/report", response_model=MiniAppAccrualReportRead)
async def miniapp_accrual_report(
    db: DbSession,
    identity: MiniAppIdentityDep,
    max_user_id: Annotated[int, Query(gt=0)],
    date_from: date,
    date_to: date,
    tenant_slug: str | None = None,
) -> MiniAppAccrualReportRead:
    resolved_tenant = _authorized_tenant_slug(
        identity,
        max_user_id=max_user_id,
        tenant_slug=tenant_slug,
    )
    try:
        return await get_miniapp_accrual_report(
            db,
            max_user_id=max_user_id,
            tenant_slug=resolved_tenant,
            date_from=date_from,
            date_to=date_to,
        )
    except MiniAppStoreError as exc:
        raise HTTPException(status_code=exc.status_code, detail=str(exc)) from exc


@router.put("/warehouse-preference", response_model=MiniAppWarehousePreferenceRead)
async def miniapp_warehouse_preference(
    payload: MiniAppWarehousePreferenceUpdate,
    db: DbSession,
    identity: MiniAppIdentityDep,
) -> MiniAppWarehousePreferenceRead:
    settings = get_settings()
    _authorized_tenant_slug(
        identity,
        max_user_id=payload.max_user_id,
        tenant_slug=payload.tenant_slug,
    )
    try:
        return await set_miniapp_warehouse_preference(
            db,
            payload=payload,
            default_tenant_slug=settings.default_tenant_slug,
        )
    except MiniAppStoreError as exc:
        raise HTTPException(status_code=exc.status_code, detail=str(exc)) from exc
