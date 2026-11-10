import pytest
from sqlalchemy import select
from test_miniapp_session import db_session as _db_session

from app.models.account import MaxAccount, StaffRoleAssignment, StaffVenueScope
from app.models.enums import AssignmentStatus, OrderStatus, StaffRole
from app.models.store import Order
from app.models.student import Student, Wallet
from app.models.tenant import City, Partner, Tenant, Venue
from app.services.miniapp import get_miniapp_session

db_session = _db_session


@pytest.mark.parametrize("superadmin", [False, True])
async def test_orders_span_managed_cities_but_other_sections_do_not(
    db_session, monkeypatch, superadmin,
):
    monkeypatch.setattr("app.services.staff.configured_superadmin_max_user_id", lambda: 88001)
    account = MaxAccount(max_user_id=88001, display_name="Директор")
    db_session.add(account)
    partner = Partner(slug="partner", name="Партнёр")
    db_session.add(partner)
    await db_session.flush()
    schools, assignments, children, receipts = [], [], [], []
    for index in range(3):
        city = City(slug=f"city-{index}", name=f"Город {index}")
        db_session.add(city)
        await db_session.flush()
        school = Tenant(slug=f"school-{index}", name=f"Школа {index}", city_id=city.id,
                        partner_id=partner.id)
        db_session.add(school)
        await db_session.flush()
        child = Student(tenant_id=school.id, first_name=f"Ученик {index}",
                        student_access_code=f"child-{index}", group_name=f"Группа {index}")
        db_session.add(child)
        await db_session.flush()
        db_session.add(Wallet(tenant_id=school.id, student_id=child.id, balance=100))
        assignment = StaffRoleAssignment(tenant_id=school.id, account_id=account.id,
            role=StaffRole.SUPERADMIN if superadmin and index == 0 else StaffRole.PARTNER_DIRECTOR,
            status=AssignmentStatus.ACTIVE if index < 2 else AssignmentStatus.REVOKED)
        db_session.add(assignment)
        order = Order(tenant_id=school.id, student_id=child.id, order_number=1,
                      status=OrderStatus.CREATED, total_astrocoins=10)
        db_session.add(order)
        schools.append(school)
        assignments.append(assignment)
        children.append(child)
        receipts.append(order)
    await db_session.commit()
    session = await get_miniapp_session(db_session, max_user_id=88001, tenant_slug=schools[0].slug)
    expected = receipts if superadmin else receipts[:2]
    assert {order.id for order in session.orders} == {order.id for order in expected}
    assert all(order.management_visible for order in session.orders)
    assert {order.tenant_slug for order in session.orders} == {
        school.slug for school in (schools if superadmin else schools[:2])
    }
    assert {student.student_id for student in session.students} == {children[0].id}
    assert session.students[0].balance == 100
    assert all(order.school_name and order.group_name for order in session.orders)
    # A director's venue restriction also applies in another managed city.
    venue = Venue(tenant_id=schools[1].id, slug="restricted", name="Площадка")
    db_session.add(venue)
    await db_session.flush()
    db_session.add(StaffVenueScope(assignment_id=assignments[1].id, venue_id=venue.id))
    await db_session.commit()
    session = await get_miniapp_session(db_session, max_user_id=88001, tenant_slug=schools[0].slug)
    assert {order.id for order in session.orders} == {
        order.id for order in (receipts if superadmin else receipts[:1])
    }
    assert await db_session.scalar(select(Wallet.balance).where(
        Wallet.student_id == children[1].id,
    )) == 100
