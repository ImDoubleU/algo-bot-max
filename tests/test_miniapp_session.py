from dataclasses import replace
from datetime import date

import pytest
from sqlalchemy import select
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

import app.db.base  # noqa: F401
from app.models.account import MaxAccount, StaffRoleAssignment, StaffVenueScope
from app.models.base import Base
from app.models.enums import (
    AssignmentStatus,
    LedgerDirection,
    OrderStatus,
    ProductCodeStatus,
    ProductFulfillmentType,
    StaffRole,
    StudentAccessRole,
    StudentAccessSource,
    StudentAccessStatus,
    StudentStatus,
)
from app.models.store import Order, OrderItem, OrderStatusHistory, Product, ProductCode
from app.models.student import (
    AstrocoinLedgerEntry,
    Contact,
    ContactStudentLink,
    Student,
    StudentAccessLink,
    StudentHistoryEvent,
    Wallet,
)
from app.models.tenant import City, Tenant
from app.schemas.access import AccessLinkCreate
from app.schemas.miniapp import (
    MiniAppAccessStatusUpdate,
    MiniAppAccrualRulesUpdate,
    MiniAppAccrualRuleWrite,
    MiniAppStaffAssignmentUpdate,
    MiniAppStudentBalanceUpdate,
    MiniAppStudentCreate,
    MiniAppStudentStatusUpdate,
    MiniAppTeacherProfileUpdate,
)
from app.services.access import create_contact_access_links
from app.services.birthday_rewards import grant_birthday_rewards
from app.services.crm_import import CrmStudentRow
from app.services.crm_sync import CrmSyncDefaults, upsert_crm_student_rows
from app.services.max_notifications import (
    _recipient_user_ids,
    _tenant_customer_user_ids,
)
from app.services.miniapp import (
    MiniAppStoreError,
    create_miniapp_student,
    get_miniapp_session,
    list_miniapp_student_ledger,
    list_miniapp_student_registry,
    set_miniapp_student_balance,
    update_miniapp_access_link_status,
    update_miniapp_accrual_rules,
    update_miniapp_managed_staff_profile,
    update_miniapp_staff_assignment,
    update_miniapp_student_status,
    update_miniapp_teacher_profile,
)


@pytest.fixture
async def db_session():
    engine = create_async_engine("sqlite+aiosqlite:///:memory:")
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    session_factory = async_sessionmaker(engine, expire_on_commit=False)
    async with session_factory() as session:
        yield session
    await engine.dispose()


def crm_row() -> CrmStudentRow:
    return CrmStudentRow(
        row_number=2,
        deal_id="1357",
        uuid="uuid-1",
        lms_student_id="ST-001",
        first_name="Алиса",
        last_name="Васильева",
        group_name="Python Start, вс 10:00",
        course_name="Python Start",
        venue_name="Союзный 45",
        teacher_name="Олейник Д",
        city="Нижний Новгород",
        status_name="Активен",
        contact_ids="681",
        contact_names="Мама Алисы",
    )


async def test_get_miniapp_session_returns_linked_students_wallet_orders_and_ledger(
    db_session,
) -> None:
    defaults = CrmSyncDefaults(partner_slug="partner-a", partner_name="Партнер A")
    await upsert_crm_student_rows(db_session, [crm_row()], defaults=defaults)
    links = await create_contact_access_links(
        db_session,
        AccessLinkCreate(
            tenant_slug="nizhniy-novgorod-partner-a",
            contact_id="681",
            max_user_id=53364725,
            role=StudentAccessRole.PARENT,
            username="parent_user",
            display_name="Родитель",
        ),
    )
    student = await db_session.scalar(select(Student).where(Student.id == links[0].student_id))
    assert student is not None

    wallet = await db_session.scalar(select(Wallet).where(Wallet.student_id == student.id))
    assert wallet is not None
    wallet.balance = 1240
    product = Product(
        tenant_id=student.tenant_id,
        sku="PEN-LOGO",
        name="Ручка",
        price_astrocoins=120,
    )
    db_session.add(product)
    await db_session.flush()
    order = Order(
        tenant_id=student.tenant_id,
        student_id=student.id,
        order_number=1,
        status=OrderStatus.CREATED,
        total_astrocoins=120,
        teacher_name=student.teacher_name,
        venue_name=student.venue_name,
    )
    db_session.add(order)
    await db_session.flush()
    db_session.add(
        OrderItem(
            tenant_id=student.tenant_id,
            order_id=order.id,
            product_id=product.id,
            quantity=1,
            unit_price_astrocoins=120,
            total_price_astrocoins=120,
        )
    )
    db_session.add(
        AstrocoinLedgerEntry(
            tenant_id=student.tenant_id,
            wallet_id=wallet.id,
            student_id=student.id,
            idempotency_key="test-ledger-1",
            direction=LedgerDirection.CREDIT,
            amount=120,
            reason="Начисление за проект",
        )
    )
    db_session.add(
        OrderStatusHistory(
            tenant_id=student.tenant_id,
            order_id=order.id,
            from_status=None,
            to_status=OrderStatus.CREATED,
            comment="created in test",
        )
    )
    await db_session.commit()

    session = await get_miniapp_session(
        db_session,
        max_user_id=53364725,
        tenant_slug="nizhniy-novgorod-partner-a",
    )

    assert session.account is not None
    assert session.account.username == "parent_user"
    assert session.student_roles == [StudentAccessRole.PARENT]
    assert len(session.students) == 1
    assert session.students[0].display_name == "Васильева Алиса"
    assert session.students[0].access_status == StudentAccessStatus.ACTIVE
    assert session.students[0].balance == 1240
    assert len(session.access_links) == 1
    assert session.access_links[0].max_user_id == 53364725
    assert len(session.orders) == 1
    assert session.orders[0].order_number == 1
    assert len(session.orders[0].items) == 1
    assert session.orders[0].items[0].product_name == "Ручка"
    assert session.orders[0].items[0].quantity == 1
    assert session.orders[0].items[0].total_price_astrocoins == 120
    assert len(session.orders[0].status_history) == 1
    assert session.orders[0].status_history[0].to_status == OrderStatus.CREATED
    assert session.orders[0].status_history[0].comment == "created in test"
    assert len(session.ledger) == 1
    assert session.ledger[0].amount == 120


async def test_staff_session_returns_tenant_students_sorted_by_group(db_session) -> None:
    defaults = CrmSyncDefaults(partner_slug="partner-a", partner_name="Партнер A")
    second_row = replace(
        crm_row(),
        row_number=3,
        deal_id="2468",
        uuid="uuid-2",
        lms_student_id="ST-002",
        first_name="Борис",
        last_name="Петров",
        group_name="Scratch, сб 12:00",
        course_name="Scratch",
        venue_name="Гагарина 64",
        teacher_name="Другой Педагог",
        contact_ids="682",
    )
    await upsert_crm_student_rows(db_session, [second_row, crm_row()], defaults=defaults)
    links = await create_contact_access_links(
        db_session,
        AccessLinkCreate(
            tenant_slug="nizhniy-novgorod-partner-a",
            contact_id="681",
            max_user_id=53364725,
            role=StudentAccessRole.PARENT,
        ),
    )
    await create_contact_access_links(
        db_session,
        AccessLinkCreate(
            tenant_slug="nizhniy-novgorod-partner-a",
            contact_id="682",
            max_user_id=53364725,
            role=StudentAccessRole.PARENT,
        ),
    )
    student = await db_session.scalar(select(Student).where(Student.id == links[0].student_id))
    account = await db_session.scalar(select(MaxAccount).where(MaxAccount.max_user_id == 53364725))
    assert student is not None
    assert account is not None
    account.display_name = "Олейник Д"
    db_session.add(
        StaffRoleAssignment(
            tenant_id=student.tenant_id,
            account_id=account.id,
            role=StaffRole.TEACHER,
            status=AssignmentStatus.ACTIVE,
        )
    )
    await db_session.commit()

    session = await get_miniapp_session(
        db_session,
        max_user_id=53364725,
        tenant_slug="nizhniy-novgorod-partner-a",
    )

    assert session.staff_roles == [StaffRole.TEACHER]
    assert session.student_roles == [StudentAccessRole.PARENT]
    assert [student.display_name for student in session.students] == [
        "Васильева Алиса",
        "Петров Борис",
    ]
    assert [student.group_name for student in session.students] == [
        "Python Start, вс 10:00",
        "Scratch, сб 12:00",
    ]
    assert [student.staff_visible for student in session.students] == [True, False]
    assert len(session.access_links) == 2

    teacher_registry = await list_miniapp_student_registry(
        db_session,
        max_user_id=53364725,
        tenant_slug="nizhniy-novgorod-partner-a",
    )
    assert [item.display_name for item in teacher_registry.students] == ["Васильева Алиса"]
    assert teacher_registry.students[0].linked_teacher_names == ["Олейник Д"]
    assert (
        await list_miniapp_student_ledger(
            db_session,
            max_user_id=53364725,
            tenant_slug="nizhniy-novgorod-partner-a",
            student_id=teacher_registry.students[0].student_id,
        )
        == []
    )

    foreign_student = await db_session.scalar(
        select(Student).where(Student.teacher_name == "Другой Педагог")
    )
    assert foreign_student is not None
    with pytest.raises(MiniAppStoreError, match="другой группы"):
        await list_miniapp_student_ledger(
            db_session,
            max_user_id=53364725,
            tenant_slug="nizhniy-novgorod-partner-a",
            student_id=foreign_student.id,
        )

    curator = MaxAccount(max_user_id=53364726, display_name="Куратор")
    db_session.add(curator)
    await db_session.flush()
    db_session.add(
        StaffRoleAssignment(
            tenant_id=student.tenant_id,
            account_id=curator.id,
            role=StaffRole.CURATOR,
            status=AssignmentStatus.ACTIVE,
        )
    )
    await db_session.commit()
    curator_registry = await list_miniapp_student_registry(
        db_session,
        max_user_id=53364726,
        tenant_slug="nizhniy-novgorod-partner-a",
    )
    assert {item.display_name for item in curator_registry.students} == {
        "Васильева Алиса",
        "Петров Борис",
    }
    curator_students = {item.display_name: item for item in curator_registry.students}
    assert curator_students["Васильева Алиса"].linked_teacher_names == ["Олейник Д"]
    assert curator_students["Петров Борис"].linked_teacher_names == []


async def test_scoped_director_sees_access_links_only_for_own_venue(db_session) -> None:
    defaults = CrmSyncDefaults(partner_slug="partner-a", partner_name="Партнер A")
    second_row = replace(
        crm_row(),
        row_number=3,
        deal_id="2468",
        uuid="uuid-2",
        lms_student_id="ST-002",
        first_name="Борис",
        last_name="Петров",
        group_name="Scratch, сб 12:00",
        course_name="Scratch",
        venue_name="Гагарина 64",
        teacher_name="Другой Педагог",
        contact_ids="682",
    )
    await upsert_crm_student_rows(db_session, [crm_row(), second_row], defaults=defaults)
    await create_contact_access_links(
        db_session,
        AccessLinkCreate(
            tenant_slug="nizhniy-novgorod-partner-a",
            contact_id="681",
            max_user_id=7001,
            role=StudentAccessRole.PARENT,
        ),
    )
    await create_contact_access_links(
        db_session,
        AccessLinkCreate(
            tenant_slug="nizhniy-novgorod-partner-a",
            contact_id="682",
            max_user_id=7002,
            role=StudentAccessRole.PARENT,
        ),
    )
    first_student = await db_session.scalar(
        select(Student).where(Student.lms_student_id == "ST-001")
    )
    assert first_student is not None
    director = MaxAccount(max_user_id=7003, display_name="Директор площадки")
    assignment = StaffRoleAssignment(
        tenant_id=first_student.tenant_id,
        account=director,
        role=StaffRole.PARTNER_DIRECTOR,
        status=AssignmentStatus.ACTIVE,
    )
    db_session.add_all([director, assignment])
    await db_session.flush()
    db_session.add(StaffVenueScope(assignment_id=assignment.id, venue_id=first_student.venue_id))
    await db_session.commit()

    session = await get_miniapp_session(
        db_session,
        max_user_id=7003,
        tenant_slug="nizhniy-novgorod-partner-a",
    )

    assert {student.student_id for student in session.students} == {first_student.id}
    assert {link.max_user_id for link in session.access_links} == {7001}
    foreign_link = await db_session.scalar(
        select(StudentAccessLink)
        .join(MaxAccount, MaxAccount.id == StudentAccessLink.account_id)
        .where(MaxAccount.max_user_id == 7002)
    )
    assert foreign_link is not None
    with pytest.raises(MiniAppStoreError, match="другой площадки"):
        await update_miniapp_access_link_status(
            db_session,
            link_id=foreign_link.id,
            payload=MiniAppAccessStatusUpdate(
                max_user_id=7003,
                tenant_slug="nizhniy-novgorod-partner-a",
                status=StudentAccessStatus.REVOKED,
            ),
            default_tenant_slug="nizhniy-novgorod-partner-a",
        )


async def test_staff_session_keeps_departed_student_with_order_visible(db_session) -> None:
    defaults = CrmSyncDefaults(partner_slug="partner-a", partner_name="Партнер A")
    await upsert_crm_student_rows(db_session, [crm_row()], defaults=defaults)
    student = await db_session.scalar(select(Student).where(Student.lms_student_id == "ST-001"))
    assert student is not None
    student.status = StudentStatus.DEPARTED

    teacher = MaxAccount(max_user_id=53364727, display_name="Олейник Д")
    db_session.add(teacher)
    await db_session.flush()
    db_session.add(
        StaffRoleAssignment(
            tenant_id=student.tenant_id,
            account_id=teacher.id,
            role=StaffRole.TEACHER,
            status=AssignmentStatus.ACTIVE,
        )
    )
    product = Product(
        tenant_id=student.tenant_id,
        sku="OLD-ORDER",
        name="Товар старого заказа",
        price_astrocoins=50,
    )
    db_session.add(product)
    await db_session.flush()
    order = Order(
        tenant_id=student.tenant_id,
        student_id=student.id,
        order_number=7,
        status=OrderStatus.TRANSFERRED_TO_TEACHER,
        total_astrocoins=50,
        teacher_name=student.teacher_name,
        venue_name=student.venue_name,
    )
    db_session.add(order)
    await db_session.flush()
    student.teacher_name = "Новый Педагог"
    db_session.add(
        OrderItem(
            tenant_id=student.tenant_id,
            order_id=order.id,
            product_id=product.id,
            quantity=1,
            unit_price_astrocoins=50,
            total_price_astrocoins=50,
        )
    )
    await db_session.commit()

    session = await get_miniapp_session(
        db_session,
        max_user_id=53364727,
        tenant_slug="nizhniy-novgorod-partner-a",
    )

    assert len(session.students) == 1
    assert session.students[0].student_status == StudentStatus.DEPARTED
    assert session.students[0].staff_visible is False
    assert session.students[0].staff_order_visible is True
    assert [item.order_number for item in session.orders] == [7]

    new_teacher = MaxAccount(max_user_id=53364728, display_name="Новый Педагог")
    db_session.add(new_teacher)
    await db_session.flush()
    db_session.add(
        StaffRoleAssignment(
            tenant_id=student.tenant_id,
            account_id=new_teacher.id,
            role=StaffRole.TEACHER,
            status=AssignmentStatus.ACTIVE,
        )
    )
    await db_session.commit()
    new_teacher_session = await get_miniapp_session(
        db_session,
        max_user_id=53364728,
        tenant_slug="nizhniy-novgorod-partner-a",
    )
    assert new_teacher_session.students[0].staff_visible is True
    assert new_teacher_session.students[0].staff_order_visible is False
    assert new_teacher_session.orders == []


async def test_digital_code_is_visible_to_family_but_hidden_from_teacher(db_session) -> None:
    defaults = CrmSyncDefaults(partner_slug="partner-a", partner_name="Партнер A")
    await upsert_crm_student_rows(db_session, [crm_row()], defaults=defaults)
    links = await create_contact_access_links(
        db_session,
        AccessLinkCreate(
            tenant_slug="nizhniy-novgorod-partner-a",
            contact_id="681",
            max_user_id=7101,
            role=StudentAccessRole.PARENT,
        ),
    )
    student = await db_session.scalar(select(Student).where(Student.id == links[0].student_id))
    assert student is not None
    teacher = MaxAccount(max_user_id=7102, display_name=student.teacher_name)
    product = Product(
        tenant_id=student.tenant_id,
        sku="DIGITAL-SECRET",
        name="Цифровой подарок",
        price_astrocoins=100,
        fulfillment_type=ProductFulfillmentType.DIGITAL_CODE,
    )
    db_session.add_all([teacher, product])
    await db_session.flush()
    db_session.add(
        StaffRoleAssignment(
            tenant_id=student.tenant_id,
            account_id=teacher.id,
            role=StaffRole.TEACHER,
            status=AssignmentStatus.ACTIVE,
        )
    )
    order = Order(
        tenant_id=student.tenant_id,
        student_id=student.id,
        order_number=8,
        status=OrderStatus.ISSUED_TO_STUDENT,
        total_astrocoins=100,
        teacher_name=student.teacher_name,
        venue_name=student.venue_name,
    )
    db_session.add(order)
    await db_session.flush()
    order_item = OrderItem(
        tenant_id=student.tenant_id,
        order_id=order.id,
        product_id=product.id,
        quantity=1,
        unit_price_astrocoins=100,
        total_price_astrocoins=100,
    )
    db_session.add(order_item)
    await db_session.flush()
    db_session.add(
        ProductCode(
            tenant_id=student.tenant_id,
            product_id=product.id,
            code="SECRET-CODE",
            status=ProductCodeStatus.ISSUED,
            order_item_id=order_item.id,
            issued_to_student_id=student.id,
        )
    )
    await db_session.commit()

    parent_session = await get_miniapp_session(
        db_session,
        max_user_id=7101,
        tenant_slug="nizhniy-novgorod-partner-a",
    )
    teacher_session = await get_miniapp_session(
        db_session,
        max_user_id=7102,
        tenant_slug="nizhniy-novgorod-partner-a",
    )

    assert parent_session.orders[0].items[0].issued_codes == ["SECRET-CODE"]
    assert teacher_session.orders[0].items[0].issued_codes == []


async def test_admin_can_revoke_student_access_link(db_session) -> None:
    defaults = CrmSyncDefaults(partner_slug="partner-a", partner_name="Партнер A")
    await upsert_crm_student_rows(db_session, [crm_row()], defaults=defaults)
    links = await create_contact_access_links(
        db_session,
        AccessLinkCreate(
            tenant_slug="nizhniy-novgorod-partner-a",
            contact_id="681",
            max_user_id=53364725,
            role=StudentAccessRole.PARENT,
        ),
    )
    student = await db_session.scalar(select(Student).where(Student.id == links[0].student_id))
    assert student is not None
    admin = MaxAccount(max_user_id=999, username="admin_user")
    db_session.add(admin)
    await db_session.flush()
    db_session.add(
        StaffRoleAssignment(
            tenant_id=student.tenant_id,
            account_id=admin.id,
            role=StaffRole.ADMIN,
            status=AssignmentStatus.ACTIVE,
        )
    )
    child_account = MaxAccount(max_user_id=1001, username="student_user")
    db_session.add(child_account)
    await db_session.flush()
    child_link = StudentAccessLink(
        tenant_id=student.tenant_id,
        account_id=child_account.id,
        student_id=student.id,
        role=StudentAccessRole.STUDENT,
        status=StudentAccessStatus.ACTIVE,
        source=StudentAccessSource.PARENT_QR,
        sponsor_access_link_id=links[0].id,
    )
    db_session.add(child_link)
    await db_session.commit()

    result = await update_miniapp_access_link_status(
        db_session,
        link_id=links[0].id,
        payload=MiniAppAccessStatusUpdate(
            max_user_id=999,
            tenant_slug="nizhniy-novgorod-partner-a",
            status=StudentAccessStatus.REVOKED,
        ),
        default_tenant_slug="nizhniy-novgorod-partner-a",
    )

    session = await get_miniapp_session(
        db_session,
        max_user_id=999,
        tenant_slug="nizhniy-novgorod-partner-a",
    )
    assert result.status == StudentAccessStatus.REVOKED
    tenant = await db_session.scalar(select(Tenant).where(Tenant.id == student.tenant_id))
    assert tenant is not None
    assert (
        await _recipient_user_ids(
            db_session,
            tenant=tenant,
            student=student,
        )
        == set()
    )
    assert await _tenant_customer_user_ids(db_session, tenant_id=tenant.id) == set()
    assert session.access_links[0].status == StudentAccessStatus.REVOKED
    await db_session.refresh(child_link)
    assert child_link.status == StudentAccessStatus.REVOKED


async def test_admin_can_assign_teacher_staff_role(db_session) -> None:
    defaults = CrmSyncDefaults(partner_slug="partner-a", partner_name="Партнер A")
    await upsert_crm_student_rows(db_session, [crm_row()], defaults=defaults)
    student = await db_session.scalar(select(Student))
    assert student is not None
    admin = MaxAccount(max_user_id=999, username="admin_user")
    db_session.add(admin)
    await db_session.flush()
    db_session.add(
        StaffRoleAssignment(
            tenant_id=student.tenant_id,
            account_id=admin.id,
            role=StaffRole.ADMIN,
            status=AssignmentStatus.ACTIVE,
        )
    )
    await db_session.commit()

    result = await update_miniapp_staff_assignment(
        db_session,
        payload=MiniAppStaffAssignmentUpdate(
            max_user_id=999,
            tenant_slug="nizhniy-novgorod-partner-a",
            target_max_user_id=1001,
            display_name="Педагог",
            role=StaffRole.TEACHER,
        ),
        default_tenant_slug="nizhniy-novgorod-partner-a",
    )

    session = await get_miniapp_session(
        db_session,
        max_user_id=999,
        tenant_slug="nizhniy-novgorod-partner-a",
    )
    assert result.status == AssignmentStatus.ACTIVE
    assert result.role == StaffRole.TEACHER
    assert any(
        assignment.max_user_id == 1001 and assignment.role == StaffRole.TEACHER
        for assignment in session.staff_assignments
    )


async def test_admin_can_add_second_role_to_existing_staff_account(db_session) -> None:
    defaults = CrmSyncDefaults(partner_slug="partner-a", partner_name="Партнер A")
    await upsert_crm_student_rows(db_session, [crm_row()], defaults=defaults)
    student = await db_session.scalar(select(Student))
    assert student is not None
    admin = MaxAccount(max_user_id=1010, username="admin_user")
    employee = MaxAccount(max_user_id=1011, display_name="Сотрудник")
    db_session.add_all([admin, employee])
    await db_session.flush()
    db_session.add_all(
        [
            StaffRoleAssignment(
                tenant_id=student.tenant_id,
                account_id=admin.id,
                role=StaffRole.ADMIN,
                status=AssignmentStatus.ACTIVE,
            ),
            StaffRoleAssignment(
                tenant_id=student.tenant_id,
                account_id=employee.id,
                role=StaffRole.CURATOR,
                status=AssignmentStatus.ACTIVE,
            ),
        ]
    )
    await db_session.commit()

    added = await update_miniapp_staff_assignment(
        db_session,
        payload=MiniAppStaffAssignmentUpdate(
            max_user_id=admin.max_user_id,
            tenant_slug="nizhniy-novgorod-partner-a",
            target_max_user_id=employee.max_user_id,
            role=StaffRole.TEACHER,
        ),
        default_tenant_slug="nizhniy-novgorod-partner-a",
    )
    session = await get_miniapp_session(
        db_session,
        max_user_id=admin.max_user_id,
        tenant_slug="nizhniy-novgorod-partner-a",
    )

    employee_assignments = [
        assignment
        for assignment in session.staff_assignments
        if assignment.account_id == employee.id
    ]
    assert added.account_id == employee.id
    assert {assignment.role for assignment in employee_assignments} == {
        StaffRole.CURATOR,
        StaffRole.TEACHER,
    }
    assert (
        len(
            list(
                await db_session.scalars(
                    select(MaxAccount).where(MaxAccount.max_user_id == employee.max_user_id)
                )
            )
        )
        == 1
    )


async def test_superadmin_role_takes_priority_over_combined_director_role(db_session) -> None:
    defaults = CrmSyncDefaults(partner_slug="partner-a", partner_name="Партнер A")
    await upsert_crm_student_rows(db_session, [crm_row()], defaults=defaults)
    student = await db_session.scalar(select(Student))
    assert student is not None
    actor = MaxAccount(max_user_id=1020, username="combined_manager")
    db_session.add(actor)
    await db_session.flush()
    db_session.add_all(
        [
            StaffRoleAssignment(
                tenant_id=student.tenant_id,
                account_id=actor.id,
                role=StaffRole.SUPERADMIN,
                status=AssignmentStatus.ACTIVE,
            ),
            StaffRoleAssignment(
                tenant_id=student.tenant_id,
                account_id=actor.id,
                role=StaffRole.PARTNER_DIRECTOR,
                status=AssignmentStatus.ACTIVE,
            ),
        ]
    )
    await db_session.commit()

    assigned = await update_miniapp_staff_assignment(
        db_session,
        payload=MiniAppStaffAssignmentUpdate(
            max_user_id=actor.max_user_id,
            tenant_slug="nizhniy-novgorod-partner-a",
            target_max_user_id=1021,
            display_name="Новый администратор",
            role=StaffRole.ADMIN,
        ),
        default_tenant_slug="nizhniy-novgorod-partner-a",
    )

    assert assigned.role == StaffRole.ADMIN
    assert assigned.status == AssignmentStatus.ACTIVE


async def test_teacher_profile_automatically_links_imported_groups(db_session) -> None:
    defaults = CrmSyncDefaults(partner_slug="partner-a", partner_name="Партнер A")
    first_group = replace(
        crm_row(),
        teacher_name="Иванова Анна",
        group_name="Python, понедельник",
    )
    await upsert_crm_student_rows(db_session, [first_group], defaults=defaults)
    student = await db_session.scalar(select(Student).where(Student.lms_student_id == "ST-001"))
    assert student is not None

    teacher = MaxAccount(max_user_id=8801, display_name="max_nickname")
    db_session.add(teacher)
    await db_session.flush()
    db_session.add(
        StaffRoleAssignment(
            tenant_id=student.tenant_id,
            account_id=teacher.id,
            role=StaffRole.TEACHER,
            status=AssignmentStatus.ACTIVE,
        )
    )
    await db_session.commit()

    initial_session = await get_miniapp_session(
        db_session,
        max_user_id=8801,
        tenant_slug="nizhniy-novgorod-partner-a",
    )
    assert initial_session.teacher_profile is not None
    assert initial_session.teacher_profile.completed is False
    assert initial_session.students == []

    profile = await update_miniapp_teacher_profile(
        db_session,
        payload=MiniAppTeacherProfileUpdate(
            max_user_id=8801,
            tenant_slug="nizhniy-novgorod-partner-a",
            first_name="Анна",
            last_name="Иванова",
        ),
        default_tenant_slug="nizhniy-novgorod-partner-a",
    )
    assert profile.completed is True
    assert profile.matched_group_names == ["Python, понедельник"]
    assert profile.matched_student_count == 1

    second_group = replace(
        crm_row(),
        row_number=3,
        deal_id="second-group-deal",
        uuid="second-group-uuid",
        lms_student_id="ST-002",
        first_name="Борис",
        last_name="Петров",
        group_name="Scratch, вторник",
        teacher_name="Анна Иванова",
        contact_ids="682",
    )
    await upsert_crm_student_rows(db_session, [second_group], defaults=defaults)

    linked_session = await get_miniapp_session(
        db_session,
        max_user_id=8801,
        tenant_slug="nizhniy-novgorod-partner-a",
    )
    assert linked_session.teacher_profile is not None
    assert linked_session.teacher_profile.matched_group_names == [
        "Python, понедельник",
        "Scratch, вторник",
    ]
    assert linked_session.teacher_profile.matched_student_count == 2
    assert {item.group_name for item in linked_session.students} == {
        "Python, понедельник",
        "Scratch, вторник",
    }


async def test_admin_and_teacher_roles_combine_visibility_and_group_matching(db_session) -> None:
    defaults = CrmSyncDefaults(partner_slug="partner-a", partner_name="Партнер A")
    own_group = replace(crm_row(), teacher_name="Китова Татьяна")
    other_group = replace(
        crm_row(),
        row_number=3,
        deal_id="combined-role-other-deal",
        uuid="combined-role-other-uuid",
        lms_student_id="ST-002",
        first_name="Борис",
        last_name="Петров",
        group_name="Scratch, вторник",
        venue_name="Гагарина 64",
        teacher_name="Другой Педагог",
        contact_ids="682",
    )
    await upsert_crm_student_rows(db_session, [own_group, other_group], defaults=defaults)
    student = await db_session.scalar(select(Student).where(Student.lms_student_id == "ST-001"))
    assert student is not None

    account = MaxAccount(max_user_id=8810, display_name="max_nickname")
    db_session.add(account)
    await db_session.flush()
    db_session.add_all(
        [
            StaffRoleAssignment(
                tenant_id=student.tenant_id,
                account_id=account.id,
                role=StaffRole.ADMIN,
                status=AssignmentStatus.ACTIVE,
            ),
            StaffRoleAssignment(
                tenant_id=student.tenant_id,
                account_id=account.id,
                role=StaffRole.TEACHER,
                status=AssignmentStatus.ACTIVE,
            ),
        ]
    )
    await db_session.commit()

    await update_miniapp_teacher_profile(
        db_session,
        payload=MiniAppTeacherProfileUpdate(
            max_user_id=8810,
            tenant_slug="nizhniy-novgorod-partner-a",
            first_name="Татьяна",
            last_name="Китова",
        ),
        default_tenant_slug="nizhniy-novgorod-partner-a",
    )
    session = await get_miniapp_session(
        db_session,
        max_user_id=8810,
        tenant_slug="nizhniy-novgorod-partner-a",
    )
    registry = await list_miniapp_student_registry(
        db_session,
        max_user_id=8810,
        tenant_slug="nizhniy-novgorod-partner-a",
    )

    assert session.staff_roles == [StaffRole.ADMIN, StaffRole.TEACHER]
    assert session.account is not None
    assert session.account.display_name == "Китова Татьяна"
    assert session.teacher_profile is not None
    assert session.teacher_profile.matched_student_count == 1
    students_by_lms_id = {item.lms_student_id: item for item in session.students}
    assert students_by_lms_id["ST-001"].staff_visible is True
    assert students_by_lms_id["ST-001"].teacher_visible is True
    assert students_by_lms_id["ST-002"].staff_visible is True
    assert students_by_lms_id["ST-002"].teacher_visible is False
    assert {item.lms_student_id for item in registry.students} == {"ST-001", "ST-002"}


async def test_curator_and_teacher_keep_curator_groups_when_teacher_role_is_added_later(
    db_session,
) -> None:
    defaults = CrmSyncDefaults(partner_slug="partner-a", partner_name="Партнер A")
    first_group = replace(crm_row(), teacher_name="Матвеева Анастасия")
    second_group = replace(
        crm_row(),
        row_number=3,
        deal_id="curator-second-group-deal",
        uuid="curator-second-group-uuid",
        lms_student_id="ST-002",
        first_name="Борис",
        last_name="Петров",
        group_name="Scratch, вторник",
        teacher_name="Елисейкина Екатерина",
        contact_ids="682",
    )
    await upsert_crm_student_rows(db_session, [first_group, second_group], defaults=defaults)
    student = await db_session.scalar(select(Student).where(Student.lms_student_id == "ST-001"))
    assert student is not None

    account = MaxAccount(max_user_id=8815, display_name="Пушкарева Ольга")
    db_session.add(account)
    await db_session.flush()
    db_session.add(
        StaffRoleAssignment(
            tenant_id=student.tenant_id,
            account_id=account.id,
            role=StaffRole.CURATOR,
            status=AssignmentStatus.ACTIVE,
        )
    )
    await db_session.commit()

    db_session.add(
        StaffRoleAssignment(
            tenant_id=student.tenant_id,
            account_id=account.id,
            role=StaffRole.TEACHER,
            status=AssignmentStatus.ACTIVE,
        )
    )
    await db_session.commit()
    await update_miniapp_teacher_profile(
        db_session,
        payload=MiniAppTeacherProfileUpdate(
            max_user_id=8815,
            tenant_slug="nizhniy-novgorod-partner-a",
            first_name="Ольга",
            last_name="Пушкарева",
        ),
        default_tenant_slug="nizhniy-novgorod-partner-a",
    )

    session = await get_miniapp_session(
        db_session,
        max_user_id=8815,
        tenant_slug="nizhniy-novgorod-partner-a",
    )

    assert session.staff_roles == [StaffRole.CURATOR, StaffRole.TEACHER]
    assert {item.group_name for item in session.students} == {
        "Python Start, вс 10:00",
        "Scratch, вторник",
    }
    assert all(item.staff_visible for item in session.students)
    assert not any(item.teacher_visible for item in session.students)
    assert session.teacher_profile is not None
    assert session.teacher_profile.matched_group_names == []


async def test_staff_member_can_switch_between_tenants_with_different_active_roles(
    db_session,
) -> None:
    defaults = CrmSyncDefaults(partner_slug="partner-a", partner_name="Партнер A")
    await upsert_crm_student_rows(db_session, [crm_row()], defaults=defaults)
    nizhny_tenant = await db_session.scalar(select(Tenant))
    assert nizhny_tenant is not None

    bor_city = City(slug="bor", name="Бор")
    bor_tenant = Tenant(
        city=bor_city,
        partner_id=nizhny_tenant.partner_id,
        slug="bor",
        name="Бор / Партнер A",
    )
    kirov_city = City(slug="kirov", name="Киров")
    kirov_tenant = Tenant(
        city=kirov_city,
        partner_id=nizhny_tenant.partner_id,
        slug="kirov",
        name="Киров / Партнер A",
    )
    account = MaxAccount(max_user_id=8816, display_name="Пушкарева Ольга")
    db_session.add_all([bor_tenant, kirov_tenant, account])
    await db_session.flush()
    db_session.add_all(
        [
            StaffRoleAssignment(
                tenant_id=nizhny_tenant.id,
                account_id=account.id,
                role=StaffRole.ADMIN,
                status=AssignmentStatus.ACTIVE,
            ),
            StaffRoleAssignment(
                tenant_id=bor_tenant.id,
                account_id=account.id,
                role=StaffRole.CURATOR,
                status=AssignmentStatus.ACTIVE,
            ),
            StaffRoleAssignment(
                tenant_id=bor_tenant.id,
                account_id=account.id,
                role=StaffRole.TEACHER,
                status=AssignmentStatus.ACTIVE,
            ),
        ]
    )
    await db_session.commit()

    nizhny_session = await get_miniapp_session(
        db_session,
        max_user_id=8816,
        tenant_slug="nizhniy-novgorod-partner-a",
    )
    bor_session = await get_miniapp_session(
        db_session,
        max_user_id=8816,
        tenant_slug="bor",
    )

    assert nizhny_session.staff_roles == [StaffRole.ADMIN]
    assert bor_session.staff_roles == [StaffRole.CURATOR, StaffRole.TEACHER]
    assert {tenant.tenant_slug for tenant in nizhny_session.available_tenants} == {
        "bor",
        "nizhniy-novgorod-partner-a",
    }
    assert nizhny_session.can_manage_tenants is True
    assert {tenant.tenant_slug for tenant in bor_session.available_tenants} == {
        "bor",
        "nizhniy-novgorod-partner-a",
    }
    assert bor_session.can_manage_tenants is True


async def test_scoped_director_and_teacher_roles_union_their_students(db_session) -> None:
    defaults = CrmSyncDefaults(partner_slug="partner-a", partner_name="Партнер A")
    scoped_group = replace(crm_row(), teacher_name="Другой Педагог")
    teacher_group = replace(
        crm_row(),
        row_number=3,
        deal_id="director-teacher-own-deal",
        uuid="director-teacher-own-uuid",
        lms_student_id="ST-002",
        first_name="Борис",
        last_name="Петров",
        group_name="Scratch, вторник",
        venue_name="Гагарина 64",
        teacher_name="Китова Татьяна",
        contact_ids="682",
    )
    hidden_group = replace(
        crm_row(),
        row_number=4,
        deal_id="director-teacher-hidden-deal",
        uuid="director-teacher-hidden-uuid",
        lms_student_id="ST-003",
        first_name="Вера",
        last_name="Смирнова",
        group_name="Roblox, среда",
        venue_name="Онлайн",
        teacher_name="Третий Педагог",
        contact_ids="683",
    )
    await upsert_crm_student_rows(
        db_session,
        [scoped_group, teacher_group, hidden_group],
        defaults=defaults,
    )
    scoped_student = await db_session.scalar(
        select(Student).where(Student.lms_student_id == "ST-001")
    )
    assert scoped_student is not None
    assert scoped_student.venue_id is not None

    account = MaxAccount(max_user_id=8811, display_name="max_nickname")
    director_assignment = StaffRoleAssignment(
        tenant_id=scoped_student.tenant_id,
        account=account,
        role=StaffRole.PARTNER_DIRECTOR,
        status=AssignmentStatus.ACTIVE,
    )
    teacher_assignment = StaffRoleAssignment(
        tenant_id=scoped_student.tenant_id,
        account=account,
        role=StaffRole.TEACHER,
        status=AssignmentStatus.ACTIVE,
    )
    db_session.add_all([account, director_assignment, teacher_assignment])
    await db_session.flush()
    db_session.add(
        StaffVenueScope(
            assignment_id=director_assignment.id,
            venue_id=scoped_student.venue_id,
        )
    )
    await db_session.commit()

    await update_miniapp_teacher_profile(
        db_session,
        payload=MiniAppTeacherProfileUpdate(
            max_user_id=8811,
            tenant_slug="nizhniy-novgorod-partner-a",
            first_name="Татьяна",
            last_name="Китова",
        ),
        default_tenant_slug="nizhniy-novgorod-partner-a",
    )
    session = await get_miniapp_session(
        db_session,
        max_user_id=8811,
        tenant_slug="nizhniy-novgorod-partner-a",
    )
    registry = await list_miniapp_student_registry(
        db_session,
        max_user_id=8811,
        tenant_slug="nizhniy-novgorod-partner-a",
    )

    assert session.staff_roles == [StaffRole.PARTNER_DIRECTOR, StaffRole.TEACHER]
    assert {item.lms_student_id for item in session.students} == {"ST-001", "ST-002"}
    students_by_lms_id = {item.lms_student_id: item for item in session.students}
    assert students_by_lms_id["ST-001"].teacher_visible is False
    assert students_by_lms_id["ST-002"].teacher_visible is True
    assert {item.lms_student_id for item in registry.students} == {"ST-001", "ST-002"}


async def test_non_teacher_staff_can_update_own_fio(db_session) -> None:
    defaults = CrmSyncDefaults(partner_slug="partner-a", partner_name="Партнер A")
    await upsert_crm_student_rows(db_session, [crm_row()], defaults=defaults)
    student = await db_session.scalar(select(Student))
    assert student is not None
    curator = MaxAccount(max_user_id=8812, display_name="old_name")
    db_session.add(curator)
    await db_session.flush()
    db_session.add(
        StaffRoleAssignment(
            tenant_id=student.tenant_id,
            account_id=curator.id,
            role=StaffRole.CURATOR,
            status=AssignmentStatus.ACTIVE,
        )
    )
    await db_session.commit()

    profile = await update_miniapp_teacher_profile(
        db_session,
        payload=MiniAppTeacherProfileUpdate(
            max_user_id=8812,
            tenant_slug="nizhniy-novgorod-partner-a",
            first_name="Мария",
            last_name="Соколова",
        ),
        default_tenant_slug="nizhniy-novgorod-partner-a",
    )

    await db_session.refresh(curator)
    assert profile.completed is True
    assert curator.display_name == "Соколова Мария"
    assert curator.staff_first_name == "Мария"
    assert curator.staff_last_name == "Соколова"


async def test_admin_can_update_managed_staff_fio_for_all_assignments(db_session) -> None:
    defaults = CrmSyncDefaults(partner_slug="partner-a", partner_name="Партнер A")
    await upsert_crm_student_rows(db_session, [crm_row()], defaults=defaults)
    student = await db_session.scalar(select(Student))
    assert student is not None
    admin = MaxAccount(max_user_id=8813, display_name="Администратор")
    employee = MaxAccount(max_user_id=8814, display_name="Старое имя")
    db_session.add_all([admin, employee])
    await db_session.flush()
    db_session.add_all(
        [
            StaffRoleAssignment(
                tenant_id=student.tenant_id,
                account_id=admin.id,
                role=StaffRole.ADMIN,
                status=AssignmentStatus.ACTIVE,
            ),
            StaffRoleAssignment(
                tenant_id=student.tenant_id,
                account_id=employee.id,
                role=StaffRole.CURATOR,
                status=AssignmentStatus.ACTIVE,
            ),
            StaffRoleAssignment(
                tenant_id=student.tenant_id,
                account_id=employee.id,
                role=StaffRole.TEACHER,
                status=AssignmentStatus.ACTIVE,
            ),
        ]
    )
    await db_session.commit()

    profile = await update_miniapp_managed_staff_profile(
        db_session,
        target_account_id=employee.id,
        payload=MiniAppTeacherProfileUpdate(
            max_user_id=8813,
            tenant_slug="nizhniy-novgorod-partner-a",
            first_name="Ольга",
            last_name="Иванова",
        ),
        default_tenant_slug="nizhniy-novgorod-partner-a",
    )
    session = await get_miniapp_session(
        db_session,
        max_user_id=8813,
        tenant_slug="nizhniy-novgorod-partner-a",
    )

    employee_assignments = [
        assignment
        for assignment in session.staff_assignments
        if assignment.account_id == employee.id
    ]
    assert profile.completed is True
    assert {assignment.role for assignment in employee_assignments} == {
        StaffRole.CURATOR,
        StaffRole.TEACHER,
    }
    assert all(assignment.display_name == "Иванова Ольга" for assignment in employee_assignments)
    assert all(assignment.first_name == "Ольга" for assignment in employee_assignments)
    assert all(assignment.last_name == "Иванова" for assignment in employee_assignments)


async def test_admin_cannot_assign_elevated_staff_role(db_session) -> None:
    defaults = CrmSyncDefaults(partner_slug="partner-a", partner_name="Партнер A")
    await upsert_crm_student_rows(db_session, [crm_row()], defaults=defaults)
    student = await db_session.scalar(select(Student))
    assert student is not None
    admin = MaxAccount(max_user_id=999, username="admin_user")
    db_session.add(admin)
    await db_session.flush()
    db_session.add(
        StaffRoleAssignment(
            tenant_id=student.tenant_id,
            account_id=admin.id,
            role=StaffRole.ADMIN,
            status=AssignmentStatus.ACTIVE,
        )
    )
    await db_session.commit()

    with pytest.raises(MiniAppStoreError, match="суперадминистратор"):
        await update_miniapp_staff_assignment(
            db_session,
            payload=MiniAppStaffAssignmentUpdate(
                max_user_id=999,
                tenant_slug="nizhniy-novgorod-partner-a",
                target_max_user_id=1001,
                role=StaffRole.ADMIN,
            ),
            default_tenant_slug="nizhniy-novgorod-partner-a",
        )


async def test_director_can_revoke_and_restore_existing_admin(db_session) -> None:
    defaults = CrmSyncDefaults(partner_slug="partner-a", partner_name="Партнер A")
    await upsert_crm_student_rows(db_session, [crm_row()], defaults=defaults)
    student = await db_session.scalar(select(Student))
    assert student is not None
    director = MaxAccount(max_user_id=2001, username="director")
    admin = MaxAccount(max_user_id=2002, username="admin")
    db_session.add_all([director, admin])
    await db_session.flush()
    db_session.add_all(
        [
            StaffRoleAssignment(
                tenant_id=student.tenant_id,
                account_id=director.id,
                role=StaffRole.PARTNER_DIRECTOR,
                status=AssignmentStatus.ACTIVE,
            ),
            StaffRoleAssignment(
                tenant_id=student.tenant_id,
                account_id=admin.id,
                role=StaffRole.ADMIN,
                status=AssignmentStatus.ACTIVE,
            ),
        ]
    )
    await db_session.commit()

    revoked = await update_miniapp_staff_assignment(
        db_session,
        payload=MiniAppStaffAssignmentUpdate(
            max_user_id=director.max_user_id,
            tenant_slug="nizhniy-novgorod-partner-a",
            target_max_user_id=admin.max_user_id,
            role=StaffRole.ADMIN,
            status=AssignmentStatus.REVOKED,
        ),
        default_tenant_slug="nizhniy-novgorod-partner-a",
    )
    restored = await update_miniapp_staff_assignment(
        db_session,
        payload=MiniAppStaffAssignmentUpdate(
            max_user_id=director.max_user_id,
            tenant_slug="nizhniy-novgorod-partner-a",
            target_max_user_id=admin.max_user_id,
            role=StaffRole.ADMIN,
            status=AssignmentStatus.ACTIVE,
        ),
        default_tenant_slug="nizhniy-novgorod-partner-a",
    )

    assert revoked.status == AssignmentStatus.REVOKED
    assert restored.status == AssignmentStatus.ACTIVE


async def test_superadmin_cannot_revoke_own_last_manager_role(db_session) -> None:
    defaults = CrmSyncDefaults(partner_slug="partner-a", partner_name="Партнер A")
    await upsert_crm_student_rows(db_session, [crm_row()], defaults=defaults)
    student = await db_session.scalar(select(Student))
    assert student is not None
    superadmin = MaxAccount(max_user_id=999, username="admin_user")
    db_session.add(superadmin)
    await db_session.flush()
    db_session.add(
        StaffRoleAssignment(
            tenant_id=student.tenant_id,
            account_id=superadmin.id,
            role=StaffRole.SUPERADMIN,
            status=AssignmentStatus.ACTIVE,
        )
    )
    await db_session.commit()

    with pytest.raises(MiniAppStoreError, match="последнюю"):
        await update_miniapp_staff_assignment(
            db_session,
            payload=MiniAppStaffAssignmentUpdate(
                max_user_id=999,
                tenant_slug="nizhniy-novgorod-partner-a",
                target_max_user_id=999,
                role=StaffRole.SUPERADMIN,
                status=AssignmentStatus.REVOKED,
            ),
            default_tenant_slug="nizhniy-novgorod-partner-a",
        )


async def test_admin_can_create_student_change_status_and_set_exact_balance(db_session) -> None:
    defaults = CrmSyncDefaults(partner_slug="partner-a", partner_name="Партнер A")
    await upsert_crm_student_rows(db_session, [crm_row()], defaults=defaults)
    existing_student = await db_session.scalar(select(Student))
    assert existing_student is not None

    admin = MaxAccount(max_user_id=9191, username="student_admin")
    db_session.add(admin)
    await db_session.flush()
    db_session.add(
        StaffRoleAssignment(
            tenant_id=existing_student.tenant_id,
            account_id=admin.id,
            role=StaffRole.ADMIN,
            status=AssignmentStatus.ACTIVE,
        )
    )
    await db_session.commit()

    registry = await create_miniapp_student(
        db_session,
        payload=MiniAppStudentCreate(
            max_user_id=9191,
            tenant_slug="nizhniy-novgorod-partner-a",
            first_name="Мария",
            last_name="Соколова",
            lms_student_id="MANUAL-001",
            group_name="Python Start",
            course_name="Python",
            venue_name="Союзный 45",
            teacher_name="Олейник Д",
        ),
        default_tenant_slug="nizhniy-novgorod-partner-a",
    )
    created = next(item for item in registry.students if item.lms_student_id == "MANUAL-001")

    registry = await update_miniapp_student_status(
        db_session,
        student_id=created.student_id,
        payload=MiniAppStudentStatusUpdate(
            max_user_id=9191,
            tenant_slug="nizhniy-novgorod-partner-a",
            status=StudentStatus.DEPARTED,
        ),
        default_tenant_slug="nizhniy-novgorod-partner-a",
    )
    updated = next(item for item in registry.students if item.student_id == created.student_id)
    assert updated.status == StudentStatus.DEPARTED
    assert updated.departed_at is not None

    registry = await set_miniapp_student_balance(
        db_session,
        student_id=created.student_id,
        payload=MiniAppStudentBalanceUpdate(
            max_user_id=9191,
            tenant_slug="nizhniy-novgorod-partner-a",
            balance=275,
            comment="Перенос подтвержденного остатка",
        ),
        default_tenant_slug="nizhniy-novgorod-partner-a",
    )
    updated = next(item for item in registry.students if item.student_id == created.student_id)
    assert updated.balance == 275

    history_types = set(
        (
            await db_session.scalars(
                select(StudentHistoryEvent.event_type).where(
                    StudentHistoryEvent.student_id == created.student_id
                )
            )
        ).all()
    )
    ledger = await db_session.scalar(
        select(AstrocoinLedgerEntry).where(AstrocoinLedgerEntry.student_id == created.student_id)
    )
    assert history_types == {"created", "status_changed"}
    assert ledger is not None
    assert ledger.direction == LedgerDirection.CREDIT
    assert ledger.amount == 275


async def test_create_student_with_parent_and_grant_birthday_reward_once(db_session) -> None:
    defaults = CrmSyncDefaults(partner_slug="partner-a", partner_name="Партнер A")
    await upsert_crm_student_rows(db_session, [crm_row()], defaults=defaults)
    existing_student = await db_session.scalar(select(Student))
    assert existing_student is not None

    admin = MaxAccount(max_user_id=9292, username="student_admin")
    db_session.add(admin)
    await db_session.flush()
    db_session.add(
        StaffRoleAssignment(
            tenant_id=existing_student.tenant_id,
            account_id=admin.id,
            role=StaffRole.ADMIN,
            status=AssignmentStatus.ACTIVE,
        )
    )
    await db_session.commit()

    registry = await create_miniapp_student(
        db_session,
        payload=MiniAppStudentCreate(
            max_user_id=9292,
            tenant_slug="nizhniy-novgorod-partner-a",
            first_name="Иван",
            last_name="Петров",
            birth_date=date(2015, 8, 16),
            lms_student_id="MANUAL-BIRTHDAY",
            crm_deal_id="MANUAL-DEAL-1",
            group_name="Python Start",
            parent_contact_id="PARENT-100",
            parent_name="Петрова Анна",
            parent_max_user_id=777001,
            parent_max_username="petrova_parent",
            initial_balance=25,
        ),
        default_tenant_slug="nizhniy-novgorod-partner-a",
    )
    created = next(item for item in registry.students if item.lms_student_id == "MANUAL-BIRTHDAY")
    assert created.birth_date == date(2015, 8, 16)
    assert created.parent_contact_ids == ["PARENT-100"]
    assert created.parent_names == ["Петрова Анна"]
    assert created.parent_max_user_ids == [777001]
    assert created.balance == 25

    contact_link = await db_session.scalar(
        select(ContactStudentLink)
        .join(Contact, Contact.id == ContactStudentLink.contact_id)
        .where(
            ContactStudentLink.student_id == created.student_id,
            Contact.external_contact_id == "PARENT-100",
        )
    )
    parent_link = await db_session.scalar(
        select(StudentAccessLink)
        .join(MaxAccount, MaxAccount.id == StudentAccessLink.account_id)
        .where(
            StudentAccessLink.student_id == created.student_id,
            StudentAccessLink.role == StudentAccessRole.PARENT,
            MaxAccount.max_user_id == 777001,
        )
    )
    assert contact_link is not None
    assert parent_link is not None

    first_reward = await grant_birthday_rewards(
        db_session,
        reward_date=date(2026, 8, 16),
    )
    second_reward = await grant_birthday_rewards(
        db_session,
        reward_date=date(2026, 8, 16),
    )
    wallet = await db_session.scalar(select(Wallet).where(Wallet.student_id == created.student_id))
    assert wallet is not None
    assert wallet.balance == 75
    assert first_reward.credited_students == 1
    assert second_reward.credited_students == 0
    assert second_reward.already_credited_students == 1


async def test_birthday_reward_uses_tenant_accrual_setting(db_session) -> None:
    defaults = CrmSyncDefaults(partner_slug="partner-a", partner_name="Партнер A")
    birthday_student_row = replace(crm_row(), birth_date=date(2015, 9, 4))
    await upsert_crm_student_rows(db_session, [birthday_student_row], defaults=defaults)
    student = await db_session.scalar(select(Student))
    assert student is not None

    admin = MaxAccount(max_user_id=9293, username="birthday_admin")
    db_session.add(admin)
    await db_session.flush()
    db_session.add(
        StaffRoleAssignment(
            tenant_id=student.tenant_id,
            account_id=admin.id,
            role=StaffRole.ADMIN,
            status=AssignmentStatus.ACTIVE,
        )
    )
    await db_session.commit()

    with pytest.raises(MiniAppStoreError, match="обязательна"):
        await update_miniapp_accrual_rules(
            db_session,
            payload=MiniAppAccrualRulesUpdate(
                max_user_id=9293,
                tenant_slug="nizhniy-novgorod-partner-a",
                rules=[MiniAppAccrualRuleWrite(reason="Активность на уроке", amount=10)],
            ),
            default_tenant_slug="nizhniy-novgorod-partner-a",
        )

    rules = await update_miniapp_accrual_rules(
        db_session,
        payload=MiniAppAccrualRulesUpdate(
            max_user_id=9293,
            tenant_slug="nizhniy-novgorod-partner-a",
            rules=[
                MiniAppAccrualRuleWrite(
                    reason="С днем рождения",
                    amount=125,
                    system_key="birthday",
                ),
                MiniAppAccrualRuleWrite(reason="Активность на уроке", amount=10),
            ],
        ),
        default_tenant_slug="nizhniy-novgorod-partner-a",
    )
    birthday_rule = next(rule for rule in rules if rule.system_key == "birthday")
    assert birthday_rule.reason == "С днем рождения"
    assert birthday_rule.amount == 125

    reward = await grant_birthday_rewards(db_session, reward_date=date(2026, 9, 4))
    wallet = await db_session.scalar(select(Wallet).where(Wallet.student_id == student.id))
    ledger_entry = await db_session.scalar(
        select(AstrocoinLedgerEntry).where(
            AstrocoinLedgerEntry.student_id == student.id,
            AstrocoinLedgerEntry.idempotency_key == f"birthday_reward:2026:{student.id}",
        )
    )

    assert reward.credited_students == 1
    assert wallet is not None
    assert wallet.balance == 125
    assert ledger_entry is not None
    assert ledger_entry.amount == 125
    assert ledger_entry.reason == "С днем рождения"
