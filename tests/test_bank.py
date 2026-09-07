from datetime import UTC, date, datetime, timedelta
from decimal import Decimal

import pytest
from sqlalchemy import func, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

import app.db.base  # noqa: F401
from app.models.account import MaxAccount, StaffRoleAssignment
from app.models.audit import AuditLog
from app.models.bank import BankDailyAccrual, BankDeposit, BankOperation, BankRateHistory
from app.models.base import Base
from app.models.enums import (
    AssignmentStatus,
    BankDepositStatus,
    BankOperationType,
    StaffRole,
    StudentAccessRole,
    StudentAccessSource,
    StudentAccessStatus,
    StudentStatus,
)
from app.models.student import Student, StudentAccessLink, Wallet
from app.models.tenant import City, Partner, Tenant
from app.schemas.miniapp import (
    MiniAppBankDepositEarlyClose,
    MiniAppBankDepositOpen,
    MiniAppBankDepositPreview,
    MiniAppBankDepositTopUp,
    MiniAppBankSettingsUpdate,
)
from app.services.bank import (
    BankServiceError,
    calculate_daily_interest,
    close_bank_deposit_for_inactive_student,
    early_close_bank_deposit,
    get_bank_report,
    get_bank_summary,
    is_last_day_of_month,
    open_bank_deposit,
    preview_bank_deposit,
    process_bank_accounts,
    project_bank_deposit,
    round_interest,
    top_up_bank_deposit,
    update_bank_settings,
)


@pytest.fixture
async def db_session():
    engine = create_async_engine("sqlite+aiosqlite:///:memory:")
    async with engine.begin() as connection:
        await connection.run_sync(Base.metadata.create_all)
    session_factory = async_sessionmaker(engine, expire_on_commit=False)
    async with session_factory() as session:
        yield session
    await engine.dispose()


@pytest.fixture(autouse=True)
def disable_bank_notifications(monkeypatch):
    async def noop(*args, **kwargs):
        return None

    monkeypatch.setattr(
        "app.services.max_notifications.schedule_bank_top_up_notification",
        noop,
    )
    monkeypatch.setattr(
        "app.services.max_notifications.schedule_bank_rate_change_notification",
        noop,
    )
    monkeypatch.setattr(
        "app.services.max_notifications.schedule_bank_early_close_notification",
        noop,
    )


async def seed_bank_context(db_session, *, rate_bps: int = 3650):
    city = City(slug="nizhniy-novgorod", name="Нижний Новгород")
    partner = Partner(slug="algo-max", name="Algo MAX")
    db_session.add_all([city, partner])
    await db_session.flush()
    tenant = Tenant(
        city_id=city.id,
        partner_id=partner.id,
        slug="nizhniy-novgorod-algo-max",
        name="Нижний Новгород / Algo MAX",
        bank_annual_rate_bps=rate_bps,
    )
    student = Student(
        tenant=tenant,
        student_access_code="BANK-STUDENT-1",
        first_name="Алиса",
        last_name="Васильева",
        group_name="Python, вс 10:00",
        teacher_name="Ольга Пушкарева",
    )
    student_account = MaxAccount(max_user_id=1001, display_name="Алиса")
    parent_account = MaxAccount(max_user_id=1002, display_name="Родитель")
    admin_account = MaxAccount(max_user_id=1003, display_name="Администратор")
    db_session.add_all([tenant, student, student_account, parent_account, admin_account])
    await db_session.flush()
    wallet = Wallet(tenant_id=tenant.id, student_id=student.id, balance=2000)
    db_session.add_all(
        [
            wallet,
            StudentAccessLink(
                tenant_id=tenant.id,
                account_id=student_account.id,
                student_id=student.id,
                role=StudentAccessRole.STUDENT,
                status=StudentAccessStatus.ACTIVE,
                source=StudentAccessSource.ADMIN,
            ),
            StudentAccessLink(
                tenant_id=tenant.id,
                account_id=parent_account.id,
                student_id=student.id,
                role=StudentAccessRole.PARENT,
                status=StudentAccessStatus.ACTIVE,
                source=StudentAccessSource.ADMIN,
            ),
            StaffRoleAssignment(
                tenant_id=tenant.id,
                account_id=admin_account.id,
                role=StaffRole.ADMIN,
                status=AssignmentStatus.ACTIVE,
            ),
        ]
    )
    await db_session.commit()
    return tenant, student, wallet, student_account, parent_account, admin_account


@pytest.mark.parametrize(
    ("balance", "rate_bps", "expected"),
    [
        (1000, 0, Decimal("0")),
        (1000, 1, Decimal("0.000273972603")),
        (1000, 3650, Decimal("1.000000000000")),
        (365, 10000, Decimal("1.000000000000")),
    ],
)
def test_daily_interest_uses_decimal_and_fixed_365_divisor(balance, rate_bps, expected):
    assert calculate_daily_interest(balance, rate_bps) == expected


@pytest.mark.parametrize(
    ("value", "expected"),
    [
        (Decimal("0.49"), 0),
        (Decimal("0.50"), 1),
        (Decimal("1.50"), 2),
        (Decimal("-0.49"), 0),
    ],
)
def test_interest_rounding_is_half_up(value, expected):
    assert round_interest(value) == expected


@pytest.mark.parametrize(
    ("day", "expected"),
    [
        (date(2025, 2, 28), True),
        (date(2026, 2, 28), True),
        (date(2028, 2, 29), True),
        (date(2026, 4, 30), True),
        (date(2026, 1, 31), True),
        (date(2026, 12, 31), True),
        (date(2027, 1, 1), False),
        (date(2026, 2, 27), False),
    ],
)
def test_last_day_of_month_handles_calendar_boundaries(day, expected):
    assert is_last_day_of_month(day) is expected


@pytest.mark.parametrize(
    ("opened_on", "maturity_on", "expected_days", "expected_interest"),
    [
        (date(2026, 1, 1), date(2026, 1, 20), 18, 18),
        (date(2026, 1, 1), date(2026, 2, 1), 30, 30),
        (date(2026, 1, 1), date(2026, 3, 1), 58, 59),
    ],
)
def test_deposit_projection_uses_daily_interest_and_monthly_capitalization(
    opened_on,
    maturity_on,
    expected_days,
    expected_interest,
):
    projection = project_bank_deposit(
        amount=1000,
        annual_rate_bps=3650,
        opened_on=opened_on,
        maturity_on=maturity_on,
    )

    assert projection.accrual_days == expected_days
    assert projection.projected_interest == expected_interest
    assert projection.projected_balance == 1000 + expected_interest


async def test_student_can_preview_deposit_income_without_changing_balances(db_session):
    tenant, student, wallet, *_ = await seed_bank_context(db_session)
    today = date.today()

    preview = await preview_bank_deposit(
        db_session,
        tenant_slug=tenant.slug,
        payload=MiniAppBankDepositPreview(
            max_user_id=1001,
            tenant_slug=tenant.slug,
            student_id=student.id,
            amount=1000,
            maturity_on=today + timedelta(days=30),
        ),
    )

    assert preview.amount == 1000
    assert preview.annual_rate_bps == 3650
    assert preview.projected_interest > 0
    assert preview.projected_balance == preview.amount + preview.projected_interest
    assert wallet.balance == 2000
    assert await db_session.scalar(select(func.count(BankDeposit.id))) == 0


async def test_student_opens_and_tops_up_with_idempotent_request_keys(db_session):
    tenant, student, wallet, *_ = await seed_bank_context(db_session)
    today = date.today()
    opened = await open_bank_deposit(
        db_session,
        tenant_slug=tenant.slug,
        payload=MiniAppBankDepositOpen(
            max_user_id=1001,
            tenant_slug=tenant.slug,
            student_id=student.id,
            amount=600,
            maturity_on=today + timedelta(days=90),
            request_key="open-request-0001",
        ),
    )
    assert opened.personal_balance == 1400
    assert opened.bank_balance == 600
    assert opened.total_balance == 2000
    assert opened.deposit is not None

    repeated = await open_bank_deposit(
        db_session,
        tenant_slug=tenant.slug,
        payload=MiniAppBankDepositOpen(
            max_user_id=1001,
            tenant_slug=tenant.slug,
            student_id=student.id,
            amount=600,
            maturity_on=today + timedelta(days=90),
            request_key="open-request-0001",
        ),
    )
    assert repeated.personal_balance == 1400

    topped_up = await top_up_bank_deposit(
        db_session,
        deposit_id=opened.deposit.id,
        tenant_slug=tenant.slug,
        payload=MiniAppBankDepositTopUp(
            max_user_id=1001,
            tenant_slug=tenant.slug,
            amount=250,
            request_key="topup-request-01",
        ),
    )
    assert topped_up.personal_balance == 1150
    assert topped_up.deposit is not None
    assert topped_up.deposit.principal_amount == 850
    assert topped_up.history[0].operation_type == BankOperationType.TOPPED_UP
    assert topped_up.history[0].title == "Пополнение вклада"
    assert topped_up.history[0].amount == 250

    repeated_top_up = await top_up_bank_deposit(
        db_session,
        deposit_id=opened.deposit.id,
        tenant_slug=tenant.slug,
        payload=MiniAppBankDepositTopUp(
            max_user_id=1001,
            tenant_slug=tenant.slug,
            amount=250,
            request_key="topup-request-01",
        ),
    )
    assert repeated_top_up.personal_balance == 1150
    assert wallet.balance == 1150

    with pytest.raises(BankServiceError, match="другими данными") as conflict:
        await top_up_bank_deposit(
            db_session,
            deposit_id=opened.deposit.id,
            tenant_slug=tenant.slug,
            payload=MiniAppBankDepositTopUp(
                max_user_id=1001,
                tenant_slug=tenant.slug,
                amount=251,
                request_key="topup-request-01",
            ),
        )
    assert conflict.value.status_code == 409
    operation_audits = list(
        (
            await db_session.scalars(
                select(AuditLog)
                .where(AuditLog.action.like("bank.operation.%"))
                .order_by(AuditLog.created_at)
            )
        ).all()
    )
    assert [audit.action for audit in operation_audits] == [
        "bank.operation.opened",
        "bank.operation.topped_up",
    ]
    assert operation_audits[0].payload["idempotency_key"].startswith("bank:open:")
    assert operation_audits[1].payload["wallet_before"] == 1400
    assert operation_audits[1].payload["wallet_after"] == 1150


async def test_parent_is_read_only_and_can_view_summary(db_session):
    tenant, student, *_ = await seed_bank_context(db_session)
    summary = await get_bank_summary(
        db_session,
        max_user_id=1002,
        tenant_slug=tenant.slug,
        student_id=student.id,
    )
    assert summary.can_open is False
    assert summary.can_top_up is False
    assert summary.can_close_early is False

    with pytest.raises(BankServiceError, match="только ученик") as denied:
        await open_bank_deposit(
            db_session,
            tenant_slug=tenant.slug,
            payload=MiniAppBankDepositOpen(
                max_user_id=1002,
                tenant_slug=tenant.slug,
                student_id=student.id,
                amount=100,
                maturity_on=date.today() + timedelta(days=30),
                request_key="parent-open-0001",
            ),
        )
    assert denied.value.status_code == 403


@pytest.mark.parametrize("days_from_today", [0, 366])
async def test_open_rejects_maturity_outside_allowed_window(
    db_session,
    days_from_today,
):
    tenant, student, *_ = await seed_bank_context(db_session)
    with pytest.raises(BankServiceError) as invalid_date:
        await open_bank_deposit(
            db_session,
            tenant_slug=tenant.slug,
            payload=MiniAppBankDepositOpen(
                max_user_id=1001,
                tenant_slug=tenant.slug,
                student_id=student.id,
                amount=100,
                maturity_on=date.today() + timedelta(days=days_from_today),
                request_key=f"invalid-date-{days_from_today:03d}",
            ),
        )
    assert invalid_date.value.status_code == 400


async def test_open_rejects_insufficient_balance_and_inactive_student(db_session):
    tenant, student, wallet, *_ = await seed_bank_context(db_session)
    with pytest.raises(BankServiceError) as insufficient:
        await open_bank_deposit(
            db_session,
            tenant_slug=tenant.slug,
            payload=MiniAppBankDepositOpen(
                max_user_id=1001,
                tenant_slug=tenant.slug,
                student_id=student.id,
                amount=wallet.balance + 1,
                maturity_on=date.today() + timedelta(days=30),
                request_key="insufficient-001",
            ),
        )
    assert insufficient.value.status_code == 409
    assert wallet.balance == 2000

    student.status = StudentStatus.DEPARTED
    await db_session.commit()
    with pytest.raises(BankServiceError) as inactive:
        await open_bank_deposit(
            db_session,
            tenant_slug=tenant.slug,
            payload=MiniAppBankDepositOpen(
                max_user_id=1001,
                tenant_slug=tenant.slug,
                student_id=student.id,
                amount=100,
                maturity_on=date.today() + timedelta(days=30),
                request_key="inactive-open-01",
            ),
        )
    assert inactive.value.status_code == 409
    assert wallet.balance == 2000


async def test_service_and_database_reject_second_active_deposit(db_session):
    tenant, student, wallet, *_ = await seed_bank_context(db_session)
    opened = await open_bank_deposit(
        db_session,
        tenant_slug=tenant.slug,
        payload=MiniAppBankDepositOpen(
            max_user_id=1001,
            tenant_slug=tenant.slug,
            student_id=student.id,
            amount=100,
            maturity_on=date.today() + timedelta(days=30),
            request_key="first-active-001",
        ),
    )
    assert opened.deposit is not None
    with pytest.raises(BankServiceError) as duplicate:
        await open_bank_deposit(
            db_session,
            tenant_slug=tenant.slug,
            payload=MiniAppBankDepositOpen(
                max_user_id=1001,
                tenant_slug=tenant.slug,
                student_id=student.id,
                amount=100,
                maturity_on=date.today() + timedelta(days=60),
                request_key="second-active-01",
            ),
        )
    assert duplicate.value.status_code == 409
    assert wallet.balance == 1900

    db_session.add(
        BankDeposit(
            tenant_id=tenant.id,
            student_id=student.id,
            wallet_id=wallet.id,
            status=BankDepositStatus.ACTIVE.value,
            opened_on=date.today(),
            maturity_on=date.today() + timedelta(days=10),
            principal_amount=1,
            capitalized_interest=0,
            pending_interest=Decimal("0"),
            last_processed_on=date.today(),
        )
    )
    with pytest.raises(IntegrityError):
        await db_session.commit()
    await db_session.rollback()


@pytest.mark.parametrize(
    "role",
    [
        StaffRole.TEACHER,
        StaffRole.CURATOR,
        StaffRole.ADMIN,
        StaffRole.PARTNER_DIRECTOR,
    ],
)
async def test_staff_roles_cannot_open_deposit_for_student(db_session, role):
    (
        tenant,
        student,
        _wallet,
        _student_account,
        _parent_account,
        staff_account,
    ) = await seed_bank_context(db_session)
    assignment = await db_session.scalar(
        select(StaffRoleAssignment).where(
            StaffRoleAssignment.account_id == staff_account.id,
        )
    )
    assert assignment is not None
    assignment.role = role
    await db_session.commit()

    with pytest.raises(BankServiceError) as denied:
        await open_bank_deposit(
            db_session,
            tenant_slug=tenant.slug,
            payload=MiniAppBankDepositOpen(
                max_user_id=staff_account.max_user_id,
                tenant_slug=tenant.slug,
                student_id=student.id,
                amount=100,
                maturity_on=date.today() + timedelta(days=30),
                request_key=f"staff-open-{role.value}",
            ),
        )
    assert denied.value.status_code == 403


async def test_teacher_scope_and_tenant_isolation_apply_to_bank_summary(db_session):
    tenant, student, _wallet, *_ = await seed_bank_context(db_session)
    teacher = MaxAccount(max_user_id=1004, display_name=student.teacher_name)
    other_student = Student(
        tenant_id=tenant.id,
        student_access_code="BANK-STUDENT-2",
        first_name="Other",
        last_name="Student",
        teacher_name="Different Teacher",
    )
    db_session.add_all([teacher, other_student])
    await db_session.flush()
    db_session.add_all(
        [
            StaffRoleAssignment(
                tenant_id=tenant.id,
                account_id=teacher.id,
                role=StaffRole.TEACHER,
                status=AssignmentStatus.ACTIVE,
            ),
            Wallet(tenant_id=tenant.id, student_id=other_student.id, balance=100),
        ]
    )
    await db_session.commit()

    visible = await get_bank_summary(
        db_session,
        max_user_id=teacher.max_user_id,
        tenant_slug=tenant.slug,
        student_id=student.id,
    )
    assert visible.student_id == student.id
    with pytest.raises(BankServiceError) as unscoped:
        await get_bank_summary(
            db_session,
            max_user_id=teacher.max_user_id,
            tenant_slug=tenant.slug,
            student_id=other_student.id,
        )
    assert unscoped.value.status_code == 403

    second_city = City(slug="bor", name="Bor")
    db_session.add(second_city)
    await db_session.flush()
    second_tenant = Tenant(
        city_id=second_city.id,
        partner_id=tenant.partner_id,
        slug="bor-algo-max",
        name="Bor / Algo MAX",
    )
    foreign_student = Student(
        tenant=second_tenant,
        student_access_code="BOR-STUDENT-1",
        first_name="Foreign",
        last_name="Student",
        teacher_name=teacher.display_name,
    )
    db_session.add_all([second_tenant, foreign_student])
    await db_session.flush()
    db_session.add(Wallet(tenant_id=second_tenant.id, student_id=foreign_student.id, balance=100))
    await db_session.commit()

    with pytest.raises(BankServiceError) as foreign_tenant:
        await get_bank_summary(
            db_session,
            max_user_id=teacher.max_user_id,
            tenant_slug=second_tenant.slug,
            student_id=foreign_student.id,
        )
    assert foreign_tenant.value.status_code == 403


async def test_month_end_capitalization_and_job_are_idempotent(db_session):
    tenant, student, wallet, *_ = await seed_bank_context(db_session)
    wallet.balance = 1000
    deposit = BankDeposit(
        tenant_id=tenant.id,
        student_id=student.id,
        wallet_id=wallet.id,
        status=BankDepositStatus.ACTIVE.value,
        opened_on=date(2026, 1, 1),
        maturity_on=date(2026, 2, 20),
        principal_amount=1000,
        capitalized_interest=0,
        pending_interest=Decimal("0"),
        last_processed_on=date(2026, 1, 1),
    )
    db_session.add_all(
        [
            deposit,
            BankRateHistory(
                tenant_id=tenant.id,
                annual_rate_bps=3650,
                effective_on=date(2026, 1, 1),
            ),
        ]
    )
    await db_session.commit()

    first = await process_bank_accounts(db_session, processing_date=date(2026, 2, 1))
    assert first.processed_days == 30
    await db_session.refresh(deposit)
    assert deposit.capitalized_interest == 30
    assert deposit.pending_interest == Decimal("0")
    assert await db_session.scalar(select(func.count(BankDailyAccrual.id))) == 30
    assert (
        await db_session.scalar(
            select(func.count(BankOperation.id)).where(
                BankOperation.operation_type == BankOperationType.INTEREST_CAPITALIZED.value
            )
        )
        == 1
    )
    assert (
        await db_session.scalar(
            select(func.count(AuditLog.id)).where(
                AuditLog.action == "bank.operation.interest_capitalized"
            )
        )
        == 1
    )

    second = await process_bank_accounts(db_session, processing_date=date(2026, 2, 1))
    assert second.processed_days == 0
    assert await db_session.scalar(select(func.count(BankDailyAccrual.id))) == 30


async def test_fractional_carry_survives_monthly_rounding_and_compounds(db_session):
    tenant, student, wallet, *_ = await seed_bank_context(db_session)
    wallet.balance = 0
    deposit = BankDeposit(
        tenant_id=tenant.id,
        student_id=student.id,
        wallet_id=wallet.id,
        status=BankDepositStatus.ACTIVE.value,
        opened_on=date(2026, 1, 1),
        maturity_on=date(2026, 4, 1),
        principal_amount=1000,
        capitalized_interest=0,
        pending_interest=Decimal("-0.4"),
        last_processed_on=date(2026, 1, 1),
    )
    db_session.add_all(
        [
            deposit,
            BankRateHistory(
                tenant_id=tenant.id,
                annual_rate_bps=3650,
                effective_on=date(2026, 1, 1),
            ),
        ]
    )
    await db_session.commit()

    await process_bank_accounts(db_session, processing_date=date(2026, 2, 1))
    await db_session.refresh(deposit)
    assert deposit.capitalized_interest == 30
    assert deposit.pending_interest == Decimal("-0.400000000000")

    await process_bank_accounts(db_session, processing_date=date(2026, 3, 1))
    await db_session.refresh(deposit)
    assert deposit.capitalized_interest == 58
    assert deposit.pending_interest == Decimal("0.440000000000")


async def test_maturity_accrues_through_previous_day_and_returns_interest(db_session):
    tenant, student, wallet, *_ = await seed_bank_context(db_session)
    wallet.balance = 0
    deposit = BankDeposit(
        tenant_id=tenant.id,
        student_id=student.id,
        wallet_id=wallet.id,
        status=BankDepositStatus.ACTIVE.value,
        opened_on=date(2026, 1, 1),
        maturity_on=date(2026, 1, 20),
        principal_amount=1000,
        capitalized_interest=0,
        pending_interest=Decimal("0"),
        last_processed_on=date(2026, 1, 1),
    )
    db_session.add_all(
        [
            deposit,
            BankRateHistory(
                tenant_id=tenant.id,
                annual_rate_bps=3650,
                effective_on=date(2026, 1, 1),
            ),
        ]
    )
    await db_session.commit()

    result = await process_bank_accounts(db_session, processing_date=date(2026, 1, 20))
    await db_session.refresh(deposit)
    assert result.processed_days == 18
    assert result.matured_deposits == 1
    assert deposit.status == BankDepositStatus.MATURED.value
    assert deposit.capitalized_interest == 18
    assert deposit.returned_amount == 1018
    assert deposit.pending_interest == Decimal("0")
    assert wallet.balance == 1018
    maturity_audit = await db_session.scalar(
        select(AuditLog).where(AuditLog.action == "bank.operation.matured")
    )
    assert maturity_audit is not None
    assert maturity_audit.payload["source"] == "system"
    assert maturity_audit.payload["wallet_after"] == 1018


async def test_last_rate_change_of_day_applies_to_that_day_without_recalculation(
    db_session,
    monkeypatch,
):
    tenant, student, wallet, *_ = await seed_bank_context(db_session)
    wallet.balance = 0
    deposit = BankDeposit(
        tenant_id=tenant.id,
        student_id=student.id,
        wallet_id=wallet.id,
        status=BankDepositStatus.ACTIVE.value,
        opened_on=date(2026, 1, 1),
        maturity_on=date(2026, 3, 1),
        principal_amount=1000,
        capitalized_interest=0,
        pending_interest=Decimal("0"),
        last_processed_on=date(2026, 1, 1),
    )
    db_session.add_all(
        [
            deposit,
            BankRateHistory(
                tenant_id=tenant.id,
                annual_rate_bps=3650,
                effective_on=date(2026, 1, 1),
            ),
        ]
    )
    await db_session.commit()
    monkeypatch.setattr("app.services.bank.bank_local_date", lambda at=None: date(2026, 1, 20))

    for rate_bps in (5000, 7300):
        await update_bank_settings(
            db_session,
            tenant_slug=tenant.slug,
            payload=MiniAppBankSettingsUpdate(
                max_user_id=1003,
                tenant_slug=tenant.slug,
                annual_rate_bps=rate_bps,
            ),
        )

    await process_bank_accounts(db_session, processing_date=date(2026, 1, 21))
    await db_session.refresh(deposit)
    jan_20 = await db_session.scalar(
        select(BankDailyAccrual).where(
            BankDailyAccrual.deposit_id == deposit.id,
            BankDailyAccrual.accrual_date == date(2026, 1, 20),
        )
    )
    assert jan_20 is not None
    assert jan_20.annual_rate_bps == 7300
    assert jan_20.exact_interest == Decimal("2.000000000000")
    assert deposit.pending_interest == Decimal("20.000000000000")
    assert (
        await db_session.scalar(
            select(func.count(BankRateHistory.id)).where(
                BankRateHistory.tenant_id == tenant.id,
                BankRateHistory.effective_on == date(2026, 1, 20),
            )
        )
        == 1
    )


async def test_top_up_keeps_original_balance_as_daily_minimum(db_session, monkeypatch):
    tenant, student, wallet, *_ = await seed_bank_context(db_session)
    current_day = [date(2026, 1, 1)]
    monkeypatch.setattr(
        "app.services.bank.bank_local_date",
        lambda at=None: current_day[0],
    )
    opened = await open_bank_deposit(
        db_session,
        tenant_slug=tenant.slug,
        payload=MiniAppBankDepositOpen(
            max_user_id=1001,
            tenant_slug=tenant.slug,
            student_id=student.id,
            amount=1000,
            maturity_on=date(2026, 3, 1),
            request_key="minimum-open-01",
        ),
    )
    assert opened.deposit is not None
    current_day[0] = date(2026, 1, 15)
    await top_up_bank_deposit(
        db_session,
        deposit_id=opened.deposit.id,
        tenant_slug=tenant.slug,
        payload=MiniAppBankDepositTopUp(
            max_user_id=1001,
            tenant_slug=tenant.slug,
            amount=500,
            request_key="minimum-topup-1",
        ),
    )
    deposit = await db_session.get(BankDeposit, opened.deposit.id)
    assert deposit is not None
    assert deposit.minimum_balance_on == date(2026, 1, 15)
    assert deposit.minimum_balance_amount == 1000
    assert deposit.principal_amount == 1500
    assert wallet.balance == 500

    await top_up_bank_deposit(
        db_session,
        deposit_id=opened.deposit.id,
        tenant_slug=tenant.slug,
        payload=MiniAppBankDepositTopUp(
            max_user_id=1001,
            tenant_slug=tenant.slug,
            amount=100,
            request_key="minimum-topup-2",
        ),
    )
    await db_session.refresh(deposit)
    assert deposit.minimum_balance_amount == 1000
    assert deposit.principal_amount == 1600
    assert wallet.balance == 400


async def test_notification_failure_does_not_rollback_or_duplicate_top_up(
    db_session,
    monkeypatch,
):
    tenant, student, wallet, *_ = await seed_bank_context(db_session)
    opened = await open_bank_deposit(
        db_session,
        tenant_slug=tenant.slug,
        payload=MiniAppBankDepositOpen(
            max_user_id=1001,
            tenant_slug=tenant.slug,
            student_id=student.id,
            amount=1000,
            maturity_on=date.today() + timedelta(days=60),
            request_key="notify-open-0001",
        ),
    )
    assert opened.deposit is not None

    async def fail_notification(*args, **kwargs):
        raise RuntimeError("notification transport failed")

    monkeypatch.setattr(
        "app.services.max_notifications.schedule_bank_top_up_notification",
        fail_notification,
    )
    payload = MiniAppBankDepositTopUp(
        max_user_id=1001,
        tenant_slug=tenant.slug,
        amount=100,
        request_key="notify-topup-001",
    )
    completed = await top_up_bank_deposit(
        db_session,
        deposit_id=opened.deposit.id,
        tenant_slug=tenant.slug,
        payload=payload,
    )
    assert completed.personal_balance == 900
    assert completed.deposit is not None
    assert completed.deposit.principal_amount == 1100
    deposit = await db_session.get(BankDeposit, opened.deposit.id)
    assert deposit is not None
    assert wallet.balance == 900
    assert deposit.principal_amount == 1100

    async def noop_notification(*args, **kwargs):
        return None

    monkeypatch.setattr(
        "app.services.max_notifications.schedule_bank_top_up_notification",
        noop_notification,
    )
    repeated = await top_up_bank_deposit(
        db_session,
        deposit_id=opened.deposit.id,
        tenant_slug=tenant.slug,
        payload=payload,
    )
    assert repeated.personal_balance == 900
    assert repeated.deposit is not None
    assert repeated.deposit.principal_amount == 1100


async def test_year_end_capitalization_uses_december_31(db_session):
    tenant, student, wallet, *_ = await seed_bank_context(db_session)
    wallet.balance = 0
    deposit = BankDeposit(
        tenant_id=tenant.id,
        student_id=student.id,
        wallet_id=wallet.id,
        status=BankDepositStatus.ACTIVE.value,
        opened_on=date(2026, 12, 30),
        maturity_on=date(2027, 2, 1),
        principal_amount=3650,
        capitalized_interest=0,
        pending_interest=Decimal("0"),
        last_processed_on=date(2026, 12, 30),
    )
    db_session.add_all(
        [
            deposit,
            BankRateHistory(
                tenant_id=tenant.id,
                annual_rate_bps=1000,
                effective_on=date(2026, 12, 30),
            ),
        ]
    )
    await db_session.commit()

    result = await process_bank_accounts(db_session, processing_date=date(2027, 1, 1))
    await db_session.refresh(deposit)
    accrual = await db_session.scalar(
        select(BankDailyAccrual).where(
            BankDailyAccrual.deposit_id == deposit.id,
            BankDailyAccrual.accrual_date == date(2026, 12, 31),
        )
    )
    assert result.processed_days == 1
    assert result.capitalizations == 1
    assert accrual is not None
    assert accrual.exact_interest == Decimal("1.000000000000")
    assert deposit.capitalized_interest == 1
    assert deposit.pending_interest == Decimal("0")


async def test_early_close_returns_principal_and_forfeits_all_interest(db_session):
    tenant, student, wallet, *_ = await seed_bank_context(db_session)
    opened = await open_bank_deposit(
        db_session,
        tenant_slug=tenant.slug,
        payload=MiniAppBankDepositOpen(
            max_user_id=1001,
            tenant_slug=tenant.slug,
            student_id=student.id,
            amount=1000,
            maturity_on=date.today() + timedelta(days=60),
            request_key="close-open-0001",
        ),
    )
    assert opened.deposit is not None
    deposit = await db_session.get(BankDeposit, opened.deposit.id)
    assert deposit is not None
    deposit.capitalized_interest = 30
    deposit.pending_interest = Decimal("4.75")
    await db_session.commit()

    result = await early_close_bank_deposit(
        db_session,
        deposit_id=deposit.id,
        tenant_slug=tenant.slug,
        payload=MiniAppBankDepositEarlyClose(
            max_user_id=1001,
            tenant_slug=tenant.slug,
            expected_return_amount=1000,
            request_key="close-request-01",
        ),
    )
    await db_session.refresh(deposit)
    assert wallet.balance == 2000
    assert result.bank_balance == 0
    assert deposit.status == BankDepositStatus.EARLY_CLOSED.value
    assert deposit.returned_amount == 1000
    assert deposit.forfeited_interest == 30
    assert deposit.pending_interest == Decimal("0")
    assert deposit.minimum_balance_on is None
    assert deposit.minimum_balance_amount is None


async def test_inactive_close_returns_capitalized_interest_but_not_pending(db_session):
    tenant, student, wallet, *_ = await seed_bank_context(db_session)
    wallet.balance = 0
    student.status = StudentStatus.DEPARTED
    deposit = BankDeposit(
        tenant_id=tenant.id,
        student_id=student.id,
        wallet_id=wallet.id,
        status=BankDepositStatus.ACTIVE.value,
        opened_on=date.today() - timedelta(days=40),
        maturity_on=date.today() + timedelta(days=40),
        principal_amount=1000,
        capitalized_interest=30,
        pending_interest=Decimal("4.75"),
        last_processed_on=date.today() - timedelta(days=1),
    )
    db_session.add(deposit)
    await db_session.commit()

    closed = await close_bank_deposit_for_inactive_student(
        db_session,
        tenant=tenant,
        student=student,
        closed_on=date.today(),
        close_reason="student_departed",
    )
    await db_session.commit()
    assert closed is True
    assert wallet.balance == 1030
    assert deposit.status == BankDepositStatus.STUDENT_INACTIVE_CLOSED.value
    assert deposit.returned_amount == 1030
    assert deposit.pending_interest == Decimal("0")


async def test_safety_scan_uses_status_change_date_across_month_boundary(db_session):
    tenant, student, wallet, *_ = await seed_bank_context(db_session)
    wallet.balance = 0
    student.status = StudentStatus.DEPARTED
    student.status_updated_at = datetime(2026, 1, 20, 8, tzinfo=UTC)
    student.departed_at = student.status_updated_at
    deposit = BankDeposit(
        tenant_id=tenant.id,
        student_id=student.id,
        wallet_id=wallet.id,
        status=BankDepositStatus.ACTIVE.value,
        opened_on=date(2026, 1, 1),
        maturity_on=date(2026, 4, 1),
        principal_amount=1000,
        capitalized_interest=0,
        pending_interest=Decimal("0"),
        last_processed_on=date(2026, 1, 1),
    )
    db_session.add_all(
        [
            deposit,
            BankRateHistory(
                tenant_id=tenant.id,
                annual_rate_bps=3650,
                effective_on=date(2026, 1, 1),
            ),
        ]
    )
    await db_session.commit()

    result = await process_bank_accounts(db_session, processing_date=date(2026, 2, 5))
    await db_session.refresh(deposit)
    assert result.inactive_deposits == 1
    assert deposit.status == BankDepositStatus.STUDENT_INACTIVE_CLOSED.value
    assert deposit.last_processed_on == date(2026, 1, 19)
    assert deposit.capitalized_interest == 0
    assert deposit.returned_amount == 1000
    assert deposit.pending_interest == Decimal("0")
    assert wallet.balance == 1000


async def test_admin_changes_rate_and_reads_report_without_mutating_deposits(db_session):
    tenant, student, _wallet, *_ = await seed_bank_context(db_session)
    opened = await open_bank_deposit(
        db_session,
        tenant_slug=tenant.slug,
        payload=MiniAppBankDepositOpen(
            max_user_id=1001,
            tenant_slug=tenant.slug,
            student_id=student.id,
            amount=750,
            maturity_on=date.today() + timedelta(days=90),
            request_key="report-open-001",
        ),
    )
    assert opened.deposit is not None
    settings = await update_bank_settings(
        db_session,
        tenant_slug=tenant.slug,
        payload=MiniAppBankSettingsUpdate(
            max_user_id=1003,
            tenant_slug=tenant.slug,
            annual_rate_bps=7300,
        ),
    )
    assert settings.annual_rate_bps == 7300
    report = await get_bank_report(
        db_session,
        max_user_id=1003,
        tenant_slug=tenant.slug,
    )
    assert report.active_deposits == 1
    assert report.total_principal == 750
    assert report.entries[0].student_name == "Васильева Алиса"
    assert report.entries[0].annual_rate_bps == 7300
