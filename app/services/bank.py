from __future__ import annotations

import calendar
import hashlib
import json
import logging
from dataclasses import dataclass
from datetime import UTC, date, datetime, timedelta
from decimal import ROUND_HALF_UP, Decimal
from uuid import UUID, uuid4
from zoneinfo import ZoneInfo

from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import get_settings
from app.models.account import MaxAccount
from app.models.audit import AuditLog
from app.models.bank import BankDailyAccrual, BankDeposit, BankOperation, BankRateHistory
from app.models.enums import (
    BankDepositStatus,
    BankOperationType,
    LedgerCategory,
    LedgerDirection,
    StaffRole,
    StudentAccessRole,
    StudentAccessStatus,
    StudentStatus,
)
from app.models.student import AstrocoinLedgerEntry, Student, StudentAccessLink, Wallet
from app.models.tenant import Tenant
from app.schemas.miniapp import (
    MiniAppBankDepositEarlyClose,
    MiniAppBankDepositOpen,
    MiniAppBankDepositPreview,
    MiniAppBankDepositPreviewRead,
    MiniAppBankDepositRead,
    MiniAppBankDepositTopUp,
    MiniAppBankHistoryEntryRead,
    MiniAppBankReportEntryRead,
    MiniAppBankReportRead,
    MiniAppBankSettingsRead,
    MiniAppBankSettingsUpdate,
    MiniAppBankSummaryRead,
)
from app.services.staff import (
    active_staff_roles_for_tenant,
    staff_names_match,
    staff_venue_scope_ids,
    teacher_staff_name,
)
from app.services.student_access_policy import student_access_window

INTEREST_SCALE = Decimal("0.000000000001")
ONE_AC = Decimal("1")
MAX_DEPOSIT_DAYS = 365
BANK_ADMIN_ROLES = {
    StaffRole.SUPERADMIN,
    StaffRole.PARTNER_DIRECTOR,
    StaffRole.ADMIN,
}
BANK_STAFF_ROLES = BANK_ADMIN_ROLES | {StaffRole.CURATOR, StaffRole.TEACHER}

logger = logging.getLogger(__name__)


class BankServiceError(RuntimeError):
    def __init__(self, message: str, *, status_code: int = 400) -> None:
        super().__init__(message)
        self.status_code = status_code


@dataclass(frozen=True)
class BankProcessingResult:
    processing_date: date
    processed_deposits: int
    processed_days: int
    capitalizations: int
    matured_deposits: int
    inactive_deposits: int


@dataclass(frozen=True)
class BankDepositProjection:
    accrual_days: int
    projected_interest: int
    projected_balance: int


def bank_local_date(at: datetime | None = None) -> date:
    timezone = ZoneInfo(get_settings().app_timezone)
    value = at or datetime.now(UTC)
    if value.tzinfo is None:
        value = value.replace(tzinfo=UTC)
    return value.astimezone(timezone).date()


def calculate_daily_interest(minimum_balance: int, annual_rate_bps: int) -> Decimal:
    if minimum_balance < 0:
        raise ValueError("minimum_balance must be non-negative")
    if not 0 <= annual_rate_bps <= 10_000:
        raise ValueError("annual_rate_bps must be between 0 and 10000")
    value = Decimal(minimum_balance) * Decimal(annual_rate_bps) / Decimal(10_000 * 365)
    return value.quantize(INTEREST_SCALE, rounding=ROUND_HALF_UP)


def round_interest(value: Decimal) -> int:
    return max(0, int(value.quantize(ONE_AC, rounding=ROUND_HALF_UP)))


def is_last_day_of_month(day: date) -> bool:
    return day.day == calendar.monthrange(day.year, day.month)[1]


def project_bank_deposit(
    *,
    amount: int,
    annual_rate_bps: int,
    opened_on: date,
    maturity_on: date,
) -> BankDepositProjection:
    if amount < 1:
        raise ValueError("amount must be positive")
    if maturity_on <= opened_on:
        raise ValueError("maturity_on must be after opened_on")

    capitalized_interest = 0
    pending_interest = Decimal("0")
    accrual_days = 0
    cursor = opened_on + timedelta(days=1)
    final_accrual_day = maturity_on - timedelta(days=1)
    while cursor <= final_accrual_day:
        balance = amount + capitalized_interest
        pending_interest = (
            pending_interest + calculate_daily_interest(balance, annual_rate_bps)
        ).quantize(INTEREST_SCALE, rounding=ROUND_HALF_UP)
        if is_last_day_of_month(cursor):
            posted_interest = round_interest(pending_interest)
            capitalized_interest += posted_interest
            pending_interest = (pending_interest - Decimal(posted_interest)).quantize(
                INTEREST_SCALE,
                rounding=ROUND_HALF_UP,
            )
        accrual_days += 1
        cursor += timedelta(days=1)

    projected_interest = capitalized_interest + round_interest(pending_interest)
    return BankDepositProjection(
        accrual_days=accrual_days,
        projected_interest=projected_interest,
        projected_balance=amount + projected_interest,
    )


def _request_fingerprint(payload: dict[str, object]) -> str:
    encoded = json.dumps(payload, sort_keys=True, ensure_ascii=False, separators=(",", ":"))
    return hashlib.sha256(encoded.encode("utf-8")).hexdigest()


def _operation_key(*, account_id: UUID, action: str, request_key: str) -> str:
    return f"bank:{action}:{account_id}:{request_key.strip()}"


def _ledger_key(operation_key: str) -> str:
    return f"bank-ledger:{hashlib.sha256(operation_key.encode()).hexdigest()}"


def _operation_title(operation_type: BankOperationType) -> str:
    return {
        BankOperationType.OPENED: "Открытие вклада",
        BankOperationType.TOPPED_UP: "Пополнение вклада",
        BankOperationType.INTEREST_CAPITALIZED: "Начисление процентов",
        BankOperationType.RATE_CHANGED: "Изменение процентной ставки",
        BankOperationType.MATURED: "Вклад завершен",
        BankOperationType.EARLY_CLOSED: "Досрочное закрытие вклада",
        BankOperationType.STUDENT_INACTIVE_CLOSED: "Вклад закрыт после завершения обучения",
    }[operation_type]


def _operation_direction(operation_type: BankOperationType) -> LedgerDirection | None:
    if operation_type in {BankOperationType.OPENED, BankOperationType.TOPPED_UP}:
        return LedgerDirection.DEBIT
    if operation_type == BankOperationType.RATE_CHANGED:
        return None
    return LedgerDirection.CREDIT


async def _tenant_and_account(
    db: AsyncSession,
    *,
    tenant_slug: str,
    max_user_id: int,
) -> tuple[Tenant, MaxAccount]:
    tenant = await db.scalar(select(Tenant).where(Tenant.slug == tenant_slug.strip().lower()))
    if tenant is None:
        raise BankServiceError("Город или партнер не найден", status_code=404)
    account = await db.scalar(select(MaxAccount).where(MaxAccount.max_user_id == max_user_id))
    if account is None:
        raise BankServiceError("MAX-аккаунт не найден", status_code=403)
    return tenant, account


async def _active_customer_link(
    db: AsyncSession,
    *,
    tenant_id: UUID,
    account_id: UUID,
    student_id: UUID,
    required_role: StudentAccessRole | None = None,
) -> StudentAccessLink | None:
    query = select(StudentAccessLink).where(
        StudentAccessLink.tenant_id == tenant_id,
        StudentAccessLink.account_id == account_id,
        StudentAccessLink.student_id == student_id,
        StudentAccessLink.status == StudentAccessStatus.ACTIVE,
    )
    if required_role is not None:
        query = query.where(StudentAccessLink.role == required_role)
    return await db.scalar(query)


async def _staff_can_view_student(
    db: AsyncSession,
    *,
    tenant: Tenant,
    account: MaxAccount,
    student: Student,
) -> bool:
    roles = await active_staff_roles_for_tenant(
        db,
        tenant_id=tenant.id,
        account_id=account.id,
        allowed_roles=BANK_STAFF_ROLES,
    )
    if roles.intersection({StaffRole.SUPERADMIN, StaffRole.ADMIN, StaffRole.CURATOR}):
        return True
    if StaffRole.PARTNER_DIRECTOR in roles:
        venue_ids = await staff_venue_scope_ids(
            db,
            tenant_id=tenant.id,
            account_id=account.id,
            role=StaffRole.PARTNER_DIRECTOR,
        )
        if venue_ids is None or student.venue_id in venue_ids:
            return True
    return StaffRole.TEACHER in roles and staff_names_match(
        teacher_staff_name(account),
        student.teacher_name,
    )


async def _require_student_read_access(
    db: AsyncSession,
    *,
    tenant: Tenant,
    account: MaxAccount,
    student: Student,
) -> StudentAccessLink | None:
    link = await _active_customer_link(
        db,
        tenant_id=tenant.id,
        account_id=account.id,
        student_id=student.id,
    )
    if link is not None and student_access_window(student, tenant).allowed:
        return link
    if await _staff_can_view_student(db, tenant=tenant, account=account, student=student):
        return None
    raise BankServiceError("Нет доступа к банковским данным ученика", status_code=403)


async def _require_student_mutation_access(
    db: AsyncSession,
    *,
    tenant: Tenant,
    account: MaxAccount,
    student: Student,
) -> None:
    link = await _active_customer_link(
        db,
        tenant_id=tenant.id,
        account_id=account.id,
        student_id=student.id,
        required_role=StudentAccessRole.STUDENT,
    )
    if link is None:
        raise BankServiceError("Операции по вкладу выполняет только ученик", status_code=403)
    if student.status != StudentStatus.ACTIVE:
        raise BankServiceError("Вклад недоступен после завершения обучения", status_code=409)
    access = student_access_window(student, tenant)
    if not access.allowed or access.paused:
        raise BankServiceError("Операции по вкладу временно недоступны", status_code=403)


async def _require_bank_admin(
    db: AsyncSession,
    *,
    tenant: Tenant,
    account: MaxAccount,
) -> set[StaffRole]:
    roles = await active_staff_roles_for_tenant(
        db,
        tenant_id=tenant.id,
        account_id=account.id,
        allowed_roles=BANK_ADMIN_ROLES,
    )
    if not roles:
        raise BankServiceError(
            "Настройка банка доступна директору и администратору",
            status_code=403,
        )
    return roles


async def _rate_for_day(db: AsyncSession, *, tenant: Tenant, day: date) -> int:
    value = await db.scalar(
        select(BankRateHistory.annual_rate_bps)
        .where(
            BankRateHistory.tenant_id == tenant.id,
            BankRateHistory.effective_on <= day,
        )
        .order_by(BankRateHistory.effective_on.desc())
        .limit(1)
    )
    return int(value if value is not None else tenant.bank_annual_rate_bps)


async def _ensure_rate_history(db: AsyncSession, *, tenant: Tenant, effective_on: date) -> None:
    existing = await db.scalar(
        select(BankRateHistory.id).where(
            BankRateHistory.tenant_id == tenant.id,
            BankRateHistory.effective_on <= effective_on,
        )
    )
    if existing is None:
        db.add(
            BankRateHistory(
                tenant_id=tenant.id,
                annual_rate_bps=tenant.bank_annual_rate_bps,
                effective_on=effective_on,
            )
        )
        await db.flush()


def _add_operation(
    db: AsyncSession,
    *,
    deposit: BankDeposit,
    operation_type: BankOperationType,
    idempotency_key: str,
    amount: int,
    principal_before: int,
    principal_after: int,
    interest_before: int,
    interest_after: int,
    actor_account_id: UUID | None = None,
    correlation_key: str | None = None,
    wallet_before: int | None = None,
    wallet_after: int | None = None,
    annual_rate_bps: int | None = None,
    effective_on: date | None = None,
    comment: str | None = None,
    details: dict[str, object] | None = None,
) -> BankOperation:
    resolved_correlation_key = correlation_key or idempotency_key
    operation_details = details or {}
    operation_created_at = datetime.now(UTC)
    operation = BankOperation(
        tenant_id=deposit.tenant_id,
        deposit_id=deposit.id,
        student_id=deposit.student_id,
        actor_account_id=actor_account_id,
        operation_type=operation_type.value,
        idempotency_key=idempotency_key,
        correlation_key=resolved_correlation_key,
        amount=amount,
        principal_before=principal_before,
        principal_after=principal_after,
        interest_before=interest_before,
        interest_after=interest_after,
        wallet_before=wallet_before,
        wallet_after=wallet_after,
        annual_rate_bps=annual_rate_bps,
        effective_on=effective_on,
        comment=comment,
        details=operation_details,
        created_at=operation_created_at,
        updated_at=operation_created_at,
    )
    db.add(operation)
    db.add(
        AuditLog(
            tenant_id=deposit.tenant_id,
            actor_account_id=actor_account_id,
            action=f"bank.operation.{operation_type.value}",
            entity_type="bank_deposit",
            entity_id=str(deposit.id),
            payload={
                "student_id": str(deposit.student_id),
                "idempotency_key": idempotency_key,
                "correlation_key": resolved_correlation_key,
                "amount": amount,
                "principal_before": principal_before,
                "principal_after": principal_after,
                "interest_before": interest_before,
                "interest_after": interest_after,
                "wallet_before": wallet_before,
                "wallet_after": wallet_after,
                "annual_rate_bps": annual_rate_bps,
                "effective_on": effective_on.isoformat() if effective_on else None,
                "comment": comment,
                "source": "user" if actor_account_id else "system",
                "details": operation_details,
            },
        )
    )
    return operation


def _add_wallet_ledger(
    db: AsyncSession,
    *,
    deposit: BankDeposit,
    wallet: Wallet,
    actor_account_id: UUID | None,
    operation_key: str,
    direction: LedgerDirection,
    amount: int,
    reason: str,
    comment: str | None = None,
) -> None:
    db.add(
        AstrocoinLedgerEntry(
            tenant_id=deposit.tenant_id,
            wallet_id=wallet.id,
            student_id=deposit.student_id,
            actor_account_id=actor_account_id,
            idempotency_key=_ledger_key(operation_key),
            direction=direction,
            category=LedgerCategory.BANK.value,
            amount=amount,
            reason=reason,
            comment=comment,
        )
    )


async def _settle_through(
    db: AsyncSession,
    *,
    deposit: BankDeposit,
    tenant: Tenant,
    through_date: date,
) -> tuple[int, int]:
    if deposit.status != BankDepositStatus.ACTIVE.value:
        return 0, 0
    final_date = min(through_date, deposit.maturity_on - timedelta(days=1))
    cursor = deposit.last_processed_on + timedelta(days=1)
    processed_days = 0
    capitalizations = 0
    while cursor <= final_date:
        minimum_balance = (
            int(deposit.minimum_balance_amount or 0)
            if deposit.minimum_balance_on == cursor
            else deposit.principal_amount + deposit.capitalized_interest
        )
        rate_bps = await _rate_for_day(db, tenant=tenant, day=cursor)
        daily_interest = calculate_daily_interest(minimum_balance, rate_bps)
        db.add(
            BankDailyAccrual(
                tenant_id=deposit.tenant_id,
                deposit_id=deposit.id,
                accrual_date=cursor,
                minimum_balance=minimum_balance,
                annual_rate_bps=rate_bps,
                exact_interest=daily_interest,
            )
        )
        deposit.pending_interest = (Decimal(deposit.pending_interest) + daily_interest).quantize(
            INTEREST_SCALE, rounding=ROUND_HALF_UP
        )
        if is_last_day_of_month(cursor):
            posted = round_interest(Decimal(deposit.pending_interest))
            if posted:
                interest_before = deposit.capitalized_interest
                deposit.capitalized_interest += posted
                _add_operation(
                    db,
                    deposit=deposit,
                    operation_type=BankOperationType.INTEREST_CAPITALIZED,
                    idempotency_key=f"bank:capitalize:{deposit.id}:{cursor.isoformat()}",
                    amount=posted,
                    principal_before=deposit.principal_amount,
                    principal_after=deposit.principal_amount,
                    interest_before=interest_before,
                    interest_after=deposit.capitalized_interest,
                    annual_rate_bps=rate_bps,
                    effective_on=cursor,
                    comment=f"Проценты за {cursor.strftime('%m.%Y')}",
                )
                capitalizations += 1
            deposit.pending_interest = (
                Decimal(deposit.pending_interest) - Decimal(posted)
            ).quantize(INTEREST_SCALE, rounding=ROUND_HALF_UP)
        deposit.last_processed_on = cursor
        if deposit.minimum_balance_on == cursor:
            deposit.minimum_balance_on = None
            deposit.minimum_balance_amount = None
        processed_days += 1
        cursor += timedelta(days=1)
    return processed_days, capitalizations


def _record_daily_minimum_before_top_up(deposit: BankDeposit, *, operation_day: date) -> None:
    if deposit.last_processed_on >= operation_day:
        return
    current_balance = deposit.principal_amount + deposit.capitalized_interest
    if deposit.minimum_balance_on != operation_day:
        deposit.minimum_balance_on = operation_day
        deposit.minimum_balance_amount = current_balance
    else:
        deposit.minimum_balance_amount = min(
            int(deposit.minimum_balance_amount or current_balance),
            current_balance,
        )


async def _close_matured_deposit(
    db: AsyncSession,
    *,
    tenant: Tenant,
    deposit: BankDeposit,
    wallet: Wallet,
    closed_at: datetime,
) -> None:
    if deposit.status != BankDepositStatus.ACTIVE.value:
        return
    await _settle_through(
        db,
        deposit=deposit,
        tenant=tenant,
        through_date=deposit.maturity_on - timedelta(days=1),
    )
    final_interest = round_interest(Decimal(deposit.pending_interest))
    closing_rate_bps = await _rate_for_day(
        db,
        tenant=tenant,
        day=deposit.maturity_on - timedelta(days=1),
    )
    interest_before = deposit.capitalized_interest
    deposit.capitalized_interest += final_interest
    payout = deposit.principal_amount + deposit.capitalized_interest
    wallet_before = wallet.balance
    wallet.balance += payout
    operation_key = f"bank:mature:{deposit.id}"
    _add_wallet_ledger(
        db,
        deposit=deposit,
        wallet=wallet,
        actor_account_id=None,
        operation_key=operation_key,
        direction=LedgerDirection.CREDIT,
        amount=payout,
        reason="Возврат вклада по окончании срока",
        comment=f"В том числе процентов: {deposit.capitalized_interest} AC",
    )
    _add_operation(
        db,
        deposit=deposit,
        operation_type=BankOperationType.MATURED,
        idempotency_key=operation_key,
        correlation_key=operation_key,
        amount=payout,
        principal_before=deposit.principal_amount,
        principal_after=0,
        interest_before=interest_before,
        interest_after=0,
        wallet_before=wallet_before,
        wallet_after=wallet.balance,
        annual_rate_bps=closing_rate_bps,
        effective_on=deposit.maturity_on,
        details={"final_interest": final_interest},
    )
    deposit.status = BankDepositStatus.MATURED.value
    deposit.closed_at = closed_at
    deposit.close_reason = "maturity"
    deposit.returned_amount = payout
    deposit.forfeited_interest = 0
    deposit.pending_interest = Decimal("0")
    deposit.minimum_balance_on = None
    deposit.minimum_balance_amount = None


async def _close_inactive_locked(
    db: AsyncSession,
    *,
    tenant: Tenant,
    student: Student,
    deposit: BankDeposit,
    wallet: Wallet,
    closed_on: date,
    close_reason: str,
) -> None:
    if deposit.status != BankDepositStatus.ACTIVE.value:
        return
    await _settle_through(
        db,
        deposit=deposit,
        tenant=tenant,
        through_date=closed_on - timedelta(days=1),
    )
    payout = deposit.principal_amount + deposit.capitalized_interest
    closing_rate_bps = await _rate_for_day(
        db,
        tenant=tenant,
        day=max(deposit.opened_on, closed_on - timedelta(days=1)),
    )
    wallet_before = wallet.balance
    wallet.balance += payout
    operation_key = f"bank:inactive-close:{deposit.id}"
    _add_wallet_ledger(
        db,
        deposit=deposit,
        wallet=wallet,
        actor_account_id=None,
        operation_key=operation_key,
        direction=LedgerDirection.CREDIT,
        amount=payout,
        reason="Возврат вклада после завершения обучения",
        comment="Непричисленные проценты не выплачены",
    )
    _add_operation(
        db,
        deposit=deposit,
        operation_type=BankOperationType.STUDENT_INACTIVE_CLOSED,
        idempotency_key=operation_key,
        correlation_key=operation_key,
        amount=payout,
        principal_before=deposit.principal_amount,
        principal_after=0,
        interest_before=deposit.capitalized_interest,
        interest_after=0,
        wallet_before=wallet_before,
        wallet_after=wallet.balance,
        annual_rate_bps=closing_rate_bps,
        effective_on=closed_on,
        comment=close_reason,
        details={
            "student_status": student.status.value,
            "forfeited_pending_interest": str(deposit.pending_interest),
        },
    )
    deposit.status = BankDepositStatus.STUDENT_INACTIVE_CLOSED.value
    deposit.closed_at = datetime.now(UTC)
    deposit.close_reason = close_reason
    deposit.returned_amount = payout
    deposit.forfeited_interest = 0
    deposit.pending_interest = Decimal("0")
    deposit.minimum_balance_on = None
    deposit.minimum_balance_amount = None


async def close_bank_deposit_for_inactive_student(
    db: AsyncSession,
    *,
    tenant: Tenant,
    student: Student,
    closed_on: date | None = None,
    close_reason: str = "student_inactive",
) -> bool:
    if student.status == StudentStatus.ACTIVE:
        return False
    wallet = await db.scalar(
        select(Wallet)
        .where(Wallet.tenant_id == tenant.id, Wallet.student_id == student.id)
        .with_for_update()
    )
    if wallet is None:
        return False
    deposit = await db.scalar(
        select(BankDeposit)
        .where(
            BankDeposit.tenant_id == tenant.id,
            BankDeposit.student_id == student.id,
            BankDeposit.status == BankDepositStatus.ACTIVE.value,
        )
        .with_for_update()
    )
    if deposit is None:
        return False
    await _close_inactive_locked(
        db,
        tenant=tenant,
        student=student,
        deposit=deposit,
        wallet=wallet,
        closed_on=closed_on or bank_local_date(),
        close_reason=close_reason,
    )
    return True


async def _history_for_student(
    db: AsyncSession,
    *,
    tenant_id: UUID,
    student_id: UUID,
    limit: int = 100,
) -> list[MiniAppBankHistoryEntryRead]:
    operations = list(
        (
            await db.scalars(
                select(BankOperation)
                .where(
                    BankOperation.tenant_id == tenant_id,
                    BankOperation.student_id == student_id,
                )
                .order_by(BankOperation.created_at.desc(), BankOperation.id.desc())
                .limit(limit)
            )
        ).all()
    )
    result: list[MiniAppBankHistoryEntryRead] = []
    for operation in operations:
        operation_type = BankOperationType(operation.operation_type)
        result.append(
            MiniAppBankHistoryEntryRead(
                id=UUID(str(operation.id)),
                operation_type=operation_type,
                title=_operation_title(operation_type),
                amount=operation.amount,
                direction=_operation_direction(operation_type),
                principal_after=operation.principal_after,
                interest_after=operation.interest_after,
                bank_balance_after=operation.principal_after + operation.interest_after,
                wallet_after=operation.wallet_after,
                annual_rate_bps=operation.annual_rate_bps,
                effective_on=operation.effective_on,
                comment=operation.comment,
                created_at=operation.created_at,
            )
        )
    return result


def _deposit_to_read(deposit: BankDeposit, *, today: date) -> MiniAppBankDepositRead:
    active = deposit.status == BankDepositStatus.ACTIVE.value
    bank_balance = deposit.principal_amount + deposit.capitalized_interest if active else 0
    pending = Decimal(deposit.pending_interest) if active else Decimal("0")
    return MiniAppBankDepositRead(
        id=UUID(str(deposit.id)),
        status=BankDepositStatus(deposit.status),
        opened_on=deposit.opened_on,
        maturity_on=deposit.maturity_on,
        closed_at=deposit.closed_at,
        close_reason=deposit.close_reason,
        principal_amount=deposit.principal_amount,
        capitalized_interest=deposit.capitalized_interest,
        pending_interest=pending,
        pending_interest_rounded=round_interest(pending),
        bank_balance=bank_balance,
        returned_amount=deposit.returned_amount,
        forfeited_interest=deposit.forfeited_interest,
        days_remaining=max(0, (deposit.maturity_on - today).days) if active else 0,
    )


async def _build_summary(
    db: AsyncSession,
    *,
    tenant: Tenant,
    student: Student,
    customer_link: StudentAccessLink | None,
    history_limit: int = 100,
) -> MiniAppBankSummaryRead:
    wallet = await db.scalar(
        select(Wallet).where(Wallet.tenant_id == tenant.id, Wallet.student_id == student.id)
    )
    personal_balance = wallet.balance if wallet else 0
    deposit = await db.scalar(
        select(BankDeposit)
        .where(BankDeposit.tenant_id == tenant.id, BankDeposit.student_id == student.id)
        .order_by(
            (BankDeposit.status == BankDepositStatus.ACTIVE.value).desc(),
            BankDeposit.opened_at.desc(),
        )
        .limit(1)
    )
    active = bool(deposit and deposit.status == BankDepositStatus.ACTIVE.value)
    bank_balance = (
        deposit.principal_amount + deposit.capitalized_interest if active and deposit else 0
    )
    is_student = bool(customer_link and customer_link.role == StudentAccessRole.STUDENT)
    can_mutate = (
        is_student
        and student.status == StudentStatus.ACTIVE
        and student_access_window(student, tenant).allowed
        and not student_access_window(student, tenant).paused
    )
    return MiniAppBankSummaryRead(
        tenant_slug=tenant.slug,
        student_id=UUID(str(student.id)),
        student_name=student.display_name,
        student_status=student.status,
        personal_balance=personal_balance,
        bank_balance=bank_balance,
        total_balance=personal_balance + bank_balance,
        annual_rate_bps=tenant.bank_annual_rate_bps,
        can_open=can_mutate and not active,
        can_top_up=can_mutate and active,
        can_close_early=can_mutate and active,
        deposit=_deposit_to_read(deposit, today=bank_local_date()) if deposit else None,
        history=await _history_for_student(
            db,
            tenant_id=tenant.id,
            student_id=student.id,
            limit=history_limit,
        ),
    )


async def get_bank_summary(
    db: AsyncSession,
    *,
    max_user_id: int,
    tenant_slug: str,
    student_id: UUID,
    history_limit: int = 100,
) -> MiniAppBankSummaryRead:
    tenant, account = await _tenant_and_account(
        db,
        tenant_slug=tenant_slug,
        max_user_id=max_user_id,
    )
    student = await db.scalar(
        select(Student).where(Student.tenant_id == tenant.id, Student.id == student_id)
    )
    if student is None:
        raise BankServiceError("Ученик не найден", status_code=404)
    customer_link = await _require_student_read_access(
        db,
        tenant=tenant,
        account=account,
        student=student,
    )
    return await _build_summary(
        db,
        tenant=tenant,
        student=student,
        customer_link=customer_link,
        history_limit=history_limit,
    )


async def _existing_request_operation(
    db: AsyncSession,
    *,
    idempotency_key: str,
    request_payload: dict[str, object],
) -> BankOperation | None:
    operation = await db.scalar(
        select(BankOperation).where(BankOperation.idempotency_key == idempotency_key)
    )
    if operation is None:
        return None
    if operation.details.get("request_fingerprint") != _request_fingerprint(request_payload):
        raise BankServiceError(
            "Этот ключ запроса уже использован с другими данными",
            status_code=409,
        )
    return operation


def _validate_maturity_on(*, today: date, maturity_on: date) -> None:
    if maturity_on <= today or maturity_on > today + timedelta(days=MAX_DEPOSIT_DAYS):
        raise BankServiceError("Выберите дату от завтра до одного года вперед")


async def preview_bank_deposit(
    db: AsyncSession,
    *,
    payload: MiniAppBankDepositPreview,
    tenant_slug: str,
) -> MiniAppBankDepositPreviewRead:
    tenant, account = await _tenant_and_account(
        db,
        tenant_slug=tenant_slug,
        max_user_id=payload.max_user_id,
    )
    student = await db.scalar(
        select(Student).where(Student.tenant_id == tenant.id, Student.id == payload.student_id)
    )
    if student is None:
        raise BankServiceError("Ученик не найден", status_code=404)
    await _require_student_mutation_access(db, tenant=tenant, account=account, student=student)

    today = bank_local_date()
    _validate_maturity_on(today=today, maturity_on=payload.maturity_on)
    wallet = await db.scalar(
        select(Wallet).where(Wallet.tenant_id == tenant.id, Wallet.student_id == student.id)
    )
    if wallet is None:
        raise BankServiceError("Личный счет ученика не найден", status_code=409)
    if wallet.balance < payload.amount:
        raise BankServiceError("На личном счете недостаточно AC", status_code=409)
    active_deposit = await db.scalar(
        select(BankDeposit.id).where(
            BankDeposit.student_id == student.id,
            BankDeposit.status == BankDepositStatus.ACTIVE.value,
        )
    )
    if active_deposit is not None:
        raise BankServiceError("У ученика уже есть действующий вклад", status_code=409)

    projection = project_bank_deposit(
        amount=payload.amount,
        annual_rate_bps=tenant.bank_annual_rate_bps,
        opened_on=today,
        maturity_on=payload.maturity_on,
    )
    return MiniAppBankDepositPreviewRead(
        opened_on=today,
        maturity_on=payload.maturity_on,
        amount=payload.amount,
        annual_rate_bps=tenant.bank_annual_rate_bps,
        accrual_days=projection.accrual_days,
        projected_interest=projection.projected_interest,
        projected_balance=projection.projected_balance,
    )


async def open_bank_deposit(
    db: AsyncSession,
    *,
    payload: MiniAppBankDepositOpen,
    tenant_slug: str,
) -> MiniAppBankSummaryRead:
    tenant, account = await _tenant_and_account(
        db,
        tenant_slug=tenant_slug,
        max_user_id=payload.max_user_id,
    )
    student = await db.scalar(
        select(Student)
        .where(Student.tenant_id == tenant.id, Student.id == payload.student_id)
        .with_for_update()
    )
    if student is None:
        raise BankServiceError("Ученик не найден", status_code=404)
    await _require_student_mutation_access(db, tenant=tenant, account=account, student=student)
    today = bank_local_date()
    _validate_maturity_on(today=today, maturity_on=payload.maturity_on)

    request_payload = {
        "student_id": str(student.id),
        "amount": payload.amount,
        "maturity_on": payload.maturity_on.isoformat(),
    }
    operation_key = _operation_key(
        account_id=account.id,
        action="open",
        request_key=payload.request_key,
    )
    existing = await _existing_request_operation(
        db,
        idempotency_key=operation_key,
        request_payload=request_payload,
    )
    if existing is not None:
        return await _build_summary(
            db,
            tenant=tenant,
            student=student,
            customer_link=await _active_customer_link(
                db,
                tenant_id=tenant.id,
                account_id=account.id,
                student_id=student.id,
            ),
        )

    wallet = await db.scalar(
        select(Wallet)
        .where(Wallet.tenant_id == tenant.id, Wallet.student_id == student.id)
        .with_for_update()
    )
    if wallet is None:
        raise BankServiceError("Личный счет ученика не найден", status_code=409)
    active_deposit = await db.scalar(
        select(BankDeposit)
        .where(
            BankDeposit.student_id == student.id,
            BankDeposit.status == BankDepositStatus.ACTIVE.value,
        )
        .with_for_update()
    )
    if active_deposit is not None:
        raise BankServiceError("У ученика уже есть действующий вклад", status_code=409)
    if wallet.balance < payload.amount:
        raise BankServiceError("На личном счете недостаточно AC", status_code=409)

    await _ensure_rate_history(db, tenant=tenant, effective_on=today)
    wallet_before = wallet.balance
    wallet.balance -= payload.amount
    deposit = BankDeposit(
        tenant_id=tenant.id,
        student_id=student.id,
        wallet_id=wallet.id,
        status=BankDepositStatus.ACTIVE.value,
        opened_on=today,
        maturity_on=payload.maturity_on,
        principal_amount=payload.amount,
        capitalized_interest=0,
        pending_interest=Decimal("0"),
        last_processed_on=today,
    )
    db.add(deposit)
    await db.flush()
    _add_wallet_ledger(
        db,
        deposit=deposit,
        wallet=wallet,
        actor_account_id=account.id,
        operation_key=operation_key,
        direction=LedgerDirection.DEBIT,
        amount=payload.amount,
        reason="Перевод на вклад",
        comment=f"Срок до {payload.maturity_on.strftime('%d.%m.%Y')}",
    )
    _add_operation(
        db,
        deposit=deposit,
        operation_type=BankOperationType.OPENED,
        idempotency_key=operation_key,
        correlation_key=operation_key,
        amount=payload.amount,
        principal_before=0,
        principal_after=payload.amount,
        interest_before=0,
        interest_after=0,
        wallet_before=wallet_before,
        wallet_after=wallet.balance,
        actor_account_id=account.id,
        annual_rate_bps=tenant.bank_annual_rate_bps,
        effective_on=today,
        details={
            "request_fingerprint": _request_fingerprint(request_payload),
            "request": request_payload,
        },
    )
    try:
        await db.commit()
    except IntegrityError as exc:
        await db.rollback()
        raise BankServiceError("У ученика уже есть действующий вклад", status_code=409) from exc
    return await get_bank_summary(
        db,
        max_user_id=payload.max_user_id,
        tenant_slug=tenant.slug,
        student_id=student.id,
    )


async def top_up_bank_deposit(
    db: AsyncSession,
    *,
    deposit_id: UUID,
    payload: MiniAppBankDepositTopUp,
    tenant_slug: str,
) -> MiniAppBankSummaryRead:
    tenant, account = await _tenant_and_account(
        db,
        tenant_slug=tenant_slug,
        max_user_id=payload.max_user_id,
    )
    initial_deposit = await db.scalar(
        select(BankDeposit).where(
            BankDeposit.id == deposit_id,
            BankDeposit.tenant_id == tenant.id,
        )
    )
    if initial_deposit is None:
        raise BankServiceError("Вклад не найден", status_code=404)
    student = await db.scalar(
        select(Student)
        .where(Student.id == initial_deposit.student_id, Student.tenant_id == tenant.id)
        .with_for_update()
    )
    if student is None:
        raise BankServiceError("Ученик не найден", status_code=404)
    await _require_student_mutation_access(db, tenant=tenant, account=account, student=student)
    request_payload = {"deposit_id": str(deposit_id), "amount": payload.amount}
    operation_key = _operation_key(
        account_id=account.id,
        action="topup",
        request_key=payload.request_key,
    )
    existing = await _existing_request_operation(
        db,
        idempotency_key=operation_key,
        request_payload=request_payload,
    )
    if existing is not None:
        return await get_bank_summary(
            db,
            max_user_id=payload.max_user_id,
            tenant_slug=tenant.slug,
            student_id=student.id,
        )

    wallet = await db.scalar(
        select(Wallet)
        .where(Wallet.tenant_id == tenant.id, Wallet.student_id == student.id)
        .with_for_update()
    )
    deposit = await db.scalar(
        select(BankDeposit)
        .where(BankDeposit.id == deposit_id, BankDeposit.tenant_id == tenant.id)
        .with_for_update()
    )
    if wallet is None or deposit is None:
        raise BankServiceError("Вклад или личный счет не найден", status_code=404)
    today = bank_local_date()
    await _settle_through(
        db,
        deposit=deposit,
        tenant=tenant,
        through_date=today - timedelta(days=1),
    )
    if deposit.status != BankDepositStatus.ACTIVE.value or deposit.maturity_on <= today:
        if deposit.status == BankDepositStatus.ACTIVE.value:
            await _close_matured_deposit(
                db,
                tenant=tenant,
                deposit=deposit,
                wallet=wallet,
                closed_at=datetime.now(UTC),
            )
            await db.commit()
        raise BankServiceError("Срок вклада уже завершен", status_code=409)
    if wallet.balance < payload.amount:
        raise BankServiceError("На личном счете недостаточно AC", status_code=409)

    _record_daily_minimum_before_top_up(deposit, operation_day=today)
    principal_before = deposit.principal_amount
    wallet_before = wallet.balance
    deposit.principal_amount += payload.amount
    wallet.balance -= payload.amount
    _add_wallet_ledger(
        db,
        deposit=deposit,
        wallet=wallet,
        actor_account_id=account.id,
        operation_key=operation_key,
        direction=LedgerDirection.DEBIT,
        amount=payload.amount,
        reason="Пополнение вклада",
    )
    _add_operation(
        db,
        deposit=deposit,
        operation_type=BankOperationType.TOPPED_UP,
        idempotency_key=operation_key,
        correlation_key=operation_key,
        amount=payload.amount,
        principal_before=principal_before,
        principal_after=deposit.principal_amount,
        interest_before=deposit.capitalized_interest,
        interest_after=deposit.capitalized_interest,
        wallet_before=wallet_before,
        wallet_after=wallet.balance,
        actor_account_id=account.id,
        annual_rate_bps=tenant.bank_annual_rate_bps,
        effective_on=today,
        details={
            "request_fingerprint": _request_fingerprint(request_payload),
            "request": request_payload,
        },
    )
    await db.commit()
    from app.services.max_notifications import schedule_bank_top_up_notification

    try:
        await schedule_bank_top_up_notification(
            db,
            tenant=tenant,
            student=student,
            amount=payload.amount,
            personal_balance=wallet.balance,
            bank_balance=deposit.principal_amount + deposit.capitalized_interest,
            maturity_on=deposit.maturity_on,
        )
    except Exception as exc:
        logger.warning("Не удалось подготовить уведомление о пополнении вклада: %s", exc)
    return await get_bank_summary(
        db,
        max_user_id=payload.max_user_id,
        tenant_slug=tenant.slug,
        student_id=student.id,
    )


async def early_close_bank_deposit(
    db: AsyncSession,
    *,
    deposit_id: UUID,
    payload: MiniAppBankDepositEarlyClose,
    tenant_slug: str,
) -> MiniAppBankSummaryRead:
    tenant, account = await _tenant_and_account(
        db,
        tenant_slug=tenant_slug,
        max_user_id=payload.max_user_id,
    )
    initial_deposit = await db.scalar(
        select(BankDeposit).where(
            BankDeposit.id == deposit_id,
            BankDeposit.tenant_id == tenant.id,
        )
    )
    if initial_deposit is None:
        raise BankServiceError("Вклад не найден", status_code=404)
    student = await db.scalar(
        select(Student)
        .where(Student.id == initial_deposit.student_id, Student.tenant_id == tenant.id)
        .with_for_update()
    )
    if student is None:
        raise BankServiceError("Ученик не найден", status_code=404)
    await _require_student_mutation_access(db, tenant=tenant, account=account, student=student)
    request_payload = {
        "deposit_id": str(deposit_id),
        "expected_return_amount": payload.expected_return_amount,
    }
    operation_key = _operation_key(
        account_id=account.id,
        action="early-close",
        request_key=payload.request_key,
    )
    existing = await _existing_request_operation(
        db,
        idempotency_key=operation_key,
        request_payload=request_payload,
    )
    if existing is not None:
        return await get_bank_summary(
            db,
            max_user_id=payload.max_user_id,
            tenant_slug=tenant.slug,
            student_id=student.id,
        )

    wallet = await db.scalar(
        select(Wallet)
        .where(Wallet.tenant_id == tenant.id, Wallet.student_id == student.id)
        .with_for_update()
    )
    deposit = await db.scalar(
        select(BankDeposit)
        .where(BankDeposit.id == deposit_id, BankDeposit.tenant_id == tenant.id)
        .with_for_update()
    )
    if wallet is None or deposit is None:
        raise BankServiceError("Вклад или личный счет не найден", status_code=404)
    today = bank_local_date()
    await _settle_through(
        db,
        deposit=deposit,
        tenant=tenant,
        through_date=today - timedelta(days=1),
    )
    if deposit.status != BankDepositStatus.ACTIVE.value:
        raise BankServiceError("Вклад уже закрыт", status_code=409)
    if deposit.maturity_on <= today:
        await _close_matured_deposit(
            db,
            tenant=tenant,
            deposit=deposit,
            wallet=wallet,
            closed_at=datetime.now(UTC),
        )
        await db.commit()
        raise BankServiceError("Вклад завершен по плановой дате", status_code=409)
    if payload.expected_return_amount != deposit.principal_amount:
        raise BankServiceError(
            "Сумма вклада изменилась. Обновите данные и подтвердите закрытие снова",
            status_code=409,
        )

    principal = deposit.principal_amount
    forfeited = deposit.capitalized_interest
    wallet_before = wallet.balance
    wallet.balance += principal
    _add_wallet_ledger(
        db,
        deposit=deposit,
        wallet=wallet,
        actor_account_id=account.id,
        operation_key=operation_key,
        direction=LedgerDirection.CREDIT,
        amount=principal,
        reason="Возврат взноса при досрочном закрытии",
        comment=f"Аннулировано причисленных процентов: {forfeited} AC",
    )
    _add_operation(
        db,
        deposit=deposit,
        operation_type=BankOperationType.EARLY_CLOSED,
        idempotency_key=operation_key,
        correlation_key=operation_key,
        amount=principal,
        principal_before=principal,
        principal_after=0,
        interest_before=forfeited,
        interest_after=0,
        wallet_before=wallet_before,
        wallet_after=wallet.balance,
        actor_account_id=account.id,
        annual_rate_bps=tenant.bank_annual_rate_bps,
        effective_on=today,
        details={
            "request_fingerprint": _request_fingerprint(request_payload),
            "request": request_payload,
            "forfeited_pending_interest": str(deposit.pending_interest),
        },
    )
    deposit.status = BankDepositStatus.EARLY_CLOSED.value
    deposit.closed_at = datetime.now(UTC)
    deposit.close_reason = "early_close"
    deposit.returned_amount = principal
    deposit.forfeited_interest = forfeited
    deposit.pending_interest = Decimal("0")
    deposit.minimum_balance_on = None
    deposit.minimum_balance_amount = None
    await db.commit()
    from app.services.max_notifications import schedule_bank_early_close_notification

    try:
        await schedule_bank_early_close_notification(
            db,
            tenant=tenant,
            student=student,
            returned_principal=principal,
            forfeited_interest=forfeited,
            personal_balance=wallet.balance,
        )
    except Exception as exc:
        logger.warning("Не удалось подготовить уведомление о закрытии вклада: %s", exc)
    return await get_bank_summary(
        db,
        max_user_id=payload.max_user_id,
        tenant_slug=tenant.slug,
        student_id=student.id,
    )


async def get_bank_settings(
    db: AsyncSession,
    *,
    max_user_id: int,
    tenant_slug: str,
) -> MiniAppBankSettingsRead:
    tenant, account = await _tenant_and_account(
        db,
        tenant_slug=tenant_slug,
        max_user_id=max_user_id,
    )
    await _require_bank_admin(db, tenant=tenant, account=account)
    latest = await db.scalar(
        select(BankRateHistory)
        .where(BankRateHistory.tenant_id == tenant.id)
        .order_by(BankRateHistory.effective_on.desc())
        .limit(1)
    )
    return MiniAppBankSettingsRead(
        tenant_slug=tenant.slug,
        annual_rate_bps=tenant.bank_annual_rate_bps,
        effective_on=latest.effective_on if latest else bank_local_date(),
        updated_at=latest.updated_at if latest else tenant.updated_at,
    )


async def update_bank_settings(
    db: AsyncSession,
    *,
    payload: MiniAppBankSettingsUpdate,
    tenant_slug: str,
) -> MiniAppBankSettingsRead:
    tenant, account = await _tenant_and_account(
        db,
        tenant_slug=tenant_slug,
        max_user_id=payload.max_user_id,
    )
    await _require_bank_admin(db, tenant=tenant, account=account)
    today = bank_local_date()
    old_rate = tenant.bank_annual_rate_bps
    if old_rate == payload.annual_rate_bps:
        return await get_bank_settings(
            db,
            max_user_id=payload.max_user_id,
            tenant_slug=tenant.slug,
        )
    deposit_refs = list(
        (
            await db.execute(
                select(BankDeposit.id, BankDeposit.wallet_id)
                .where(
                    BankDeposit.tenant_id == tenant.id,
                    BankDeposit.status == BankDepositStatus.ACTIVE.value,
                )
                .order_by(BankDeposit.wallet_id, BankDeposit.id)
            )
        ).all()
    )
    deposits: list[BankDeposit] = []
    for deposit_id, wallet_id in deposit_refs:
        await db.scalar(select(Wallet.id).where(Wallet.id == wallet_id).with_for_update())
        deposit = await db.scalar(
            select(BankDeposit)
            .where(
                BankDeposit.id == deposit_id,
                BankDeposit.status == BankDepositStatus.ACTIVE.value,
            )
            .with_for_update()
        )
        if deposit is None:
            continue
        await _settle_through(
            db,
            deposit=deposit,
            tenant=tenant,
            through_date=today - timedelta(days=1),
        )
        deposits.append(deposit)

    rate_row = await db.scalar(
        select(BankRateHistory)
        .where(
            BankRateHistory.tenant_id == tenant.id,
            BankRateHistory.effective_on == today,
        )
        .with_for_update()
    )
    if rate_row is None:
        rate_row = BankRateHistory(
            tenant_id=tenant.id,
            effective_on=today,
            annual_rate_bps=payload.annual_rate_bps,
            changed_by_account_id=account.id,
        )
        db.add(rate_row)
    else:
        rate_row.annual_rate_bps = payload.annual_rate_bps
        rate_row.changed_by_account_id = account.id
    tenant.bank_annual_rate_bps = payload.annual_rate_bps

    change_id = uuid4().hex
    for deposit in deposits:
        _add_operation(
            db,
            deposit=deposit,
            operation_type=BankOperationType.RATE_CHANGED,
            idempotency_key=f"bank:rate:{tenant.id}:{today}:{deposit.id}:{change_id}",
            amount=0,
            principal_before=deposit.principal_amount,
            principal_after=deposit.principal_amount,
            interest_before=deposit.capitalized_interest,
            interest_after=deposit.capitalized_interest,
            actor_account_id=account.id,
            annual_rate_bps=payload.annual_rate_bps,
            effective_on=today,
            details={"old_rate_bps": old_rate, "new_rate_bps": payload.annual_rate_bps},
        )
    db.add(
        AuditLog(
            tenant_id=tenant.id,
            actor_account_id=account.id,
            action="bank.rate_changed",
            entity_type="tenant",
            entity_id=str(tenant.id),
            payload={
                "old_rate_bps": old_rate,
                "new_rate_bps": payload.annual_rate_bps,
                "effective_on": today.isoformat(),
                "active_deposits": len(deposits),
            },
        )
    )
    await db.commit()
    from app.services.max_notifications import schedule_bank_rate_change_notification

    try:
        await schedule_bank_rate_change_notification(
            db,
            tenant=tenant,
            students=list(
                (
                    await db.scalars(
                        select(Student).where(
                            Student.id.in_({deposit.student_id for deposit in deposits})
                        )
                    )
                ).all()
            )
            if deposits
            else [],
            old_rate_bps=old_rate,
            new_rate_bps=payload.annual_rate_bps,
            effective_on=today,
        )
    except Exception as exc:
        logger.warning("Не удалось подготовить уведомление об изменении ставки: %s", exc)
    return await get_bank_settings(
        db,
        max_user_id=payload.max_user_id,
        tenant_slug=tenant.slug,
    )


async def get_bank_report(
    db: AsyncSession,
    *,
    max_user_id: int,
    tenant_slug: str,
) -> MiniAppBankReportRead:
    tenant, account = await _tenant_and_account(
        db,
        tenant_slug=tenant_slug,
        max_user_id=max_user_id,
    )
    roles = await _require_bank_admin(db, tenant=tenant, account=account)
    rows = list(
        (
            await db.execute(
                select(BankDeposit, Student, Wallet)
                .join(Student, Student.id == BankDeposit.student_id)
                .join(Wallet, Wallet.id == BankDeposit.wallet_id)
                .where(BankDeposit.tenant_id == tenant.id)
                .order_by(
                    Student.group_name,
                    Student.last_name,
                    Student.first_name,
                    (BankDeposit.status == BankDepositStatus.ACTIVE.value).desc(),
                    BankDeposit.opened_at.desc(),
                )
            )
        ).all()
    )
    if StaffRole.PARTNER_DIRECTOR in roles and not roles.intersection(
        {StaffRole.SUPERADMIN, StaffRole.ADMIN}
    ):
        venue_ids = await staff_venue_scope_ids(
            db,
            tenant_id=tenant.id,
            account_id=account.id,
            role=StaffRole.PARTNER_DIRECTOR,
        )
        if venue_ids is not None:
            rows = [row for row in rows if row[1].venue_id in venue_ids]
    latest_rows: list[tuple[BankDeposit, Student, Wallet]] = []
    seen_student_ids: set[UUID] = set()
    for row in rows:
        student_id = UUID(str(row[1].id))
        if student_id in seen_student_ids:
            continue
        seen_student_ids.add(student_id)
        latest_rows.append(row)
    entries = [
        MiniAppBankReportEntryRead(
            student_id=UUID(str(student.id)),
            student_name=student.display_name,
            group_name=student.group_name,
            teacher_name=student.teacher_name,
            personal_balance=wallet.balance,
            principal_amount=deposit.principal_amount,
            capitalized_interest=deposit.capitalized_interest,
            pending_interest=(
                Decimal(deposit.pending_interest)
                if deposit.status == BankDepositStatus.ACTIVE.value
                else Decimal("0")
            ),
            bank_balance=(
                deposit.principal_amount + deposit.capitalized_interest
                if deposit.status == BankDepositStatus.ACTIVE.value
                else 0
            ),
            total_balance=wallet.balance
            + (
                deposit.principal_amount + deposit.capitalized_interest
                if deposit.status == BankDepositStatus.ACTIVE.value
                else 0
            ),
            annual_rate_bps=tenant.bank_annual_rate_bps,
            opened_on=deposit.opened_on,
            maturity_on=deposit.maturity_on,
            status=BankDepositStatus(deposit.status),
        )
        for deposit, student, wallet in latest_rows
    ]
    active_entries = [entry for entry in entries if entry.status == BankDepositStatus.ACTIVE]
    return MiniAppBankReportRead(
        tenant_slug=tenant.slug,
        annual_rate_bps=tenant.bank_annual_rate_bps,
        active_deposits=len(active_entries),
        total_principal=sum(entry.principal_amount for entry in active_entries),
        total_capitalized_interest=sum(entry.capitalized_interest for entry in active_entries),
        total_bank_balance=sum(entry.bank_balance for entry in active_entries),
        entries=entries,
    )


async def process_bank_accounts(
    db: AsyncSession,
    *,
    processing_date: date,
) -> BankProcessingResult:
    deposit_rows = list(
        (
            await db.execute(
                select(BankDeposit.id, BankDeposit.wallet_id)
                .where(BankDeposit.status == BankDepositStatus.ACTIVE.value)
                .order_by(BankDeposit.id)
            )
        ).all()
    )
    processed_deposits = 0
    processed_days = 0
    capitalizations = 0
    matured = 0
    inactive = 0
    for deposit_id, wallet_id in deposit_rows:
        wallet = await db.scalar(select(Wallet).where(Wallet.id == wallet_id).with_for_update())
        deposit = await db.scalar(
            select(BankDeposit).where(BankDeposit.id == deposit_id).with_for_update()
        )
        if wallet is None or deposit is None or deposit.status != BankDepositStatus.ACTIVE.value:
            continue
        tenant = await db.scalar(select(Tenant).where(Tenant.id == deposit.tenant_id))
        student = await db.scalar(select(Student).where(Student.id == deposit.student_id))
        if tenant is None or student is None:
            continue
        if student.status != StudentStatus.ACTIVE:
            status_changed_on = bank_local_date(student.status_updated_at)
            await _close_inactive_locked(
                db,
                tenant=tenant,
                student=student,
                deposit=deposit,
                wallet=wallet,
                closed_on=min(processing_date, status_changed_on),
                close_reason=f"student_{student.status.value}",
            )
            inactive += 1
        else:
            days, postings = await _settle_through(
                db,
                deposit=deposit,
                tenant=tenant,
                through_date=processing_date - timedelta(days=1),
            )
            processed_days += days
            capitalizations += postings
            if deposit.maturity_on <= processing_date:
                await _close_matured_deposit(
                    db,
                    tenant=tenant,
                    deposit=deposit,
                    wallet=wallet,
                    closed_at=datetime.now(UTC),
                )
                matured += 1
        processed_deposits += 1
        await db.commit()
    return BankProcessingResult(
        processing_date=processing_date,
        processed_deposits=processed_deposits,
        processed_days=processed_days,
        capitalizations=capitalizations,
        matured_deposits=matured,
        inactive_deposits=inactive,
    )
