import pytest
from sqlalchemy import func, select
from test_miniapp_store import db_session as _db_session
from test_miniapp_store import digital_issuer, seed_linked_student

from app.models.audit import AuditLog
from app.models.enums import OrderStatus, ProductFulfillmentType
from app.models.store import Order, OrderStatusHistory, Product, ProductCode
from app.models.student import Wallet
from app.schemas.miniapp import (
    MiniAppDigitalOrderIssue,
    MiniAppDigitalOrderItemIssue,
    MiniAppOrderCreate,
    MiniAppOrderItemCreate,
)
from app.services.max_notifications import _order_message
from app.services.miniapp import (
    MiniAppStoreError,
    create_miniapp_order,
    issue_miniapp_digital_order,
)

db_session = _db_session
SCHOOL = "nizhniy-novgorod-partner-a"


@pytest.mark.parametrize("field,value", [
    ("steam_login", "player_one"), ("roblox_username", "Child_2026"),
    ("phone", "+79991234567"),
])
@pytest.mark.parametrize("mixed", [False, True])
async def test_account_fulfillment_without_codes_is_idempotent(db_session, field, value, mixed):
    student = await seed_linked_student(db_session)
    director = await digital_issuer(db_session, student)
    account_product = Product(tenant_id=student.tenant_id, sku="ACCOUNT", name="Пополнение",
                              price_astrocoins=100,
                              fulfillment_type=ProductFulfillmentType.DIGITAL_MANUAL,
                              recipient_field=field)
    db_session.add(account_product)
    await db_session.flush()
    items = [MiniAppOrderItemCreate(product_id=account_product.id, quantity=1,
                                    recipient_value=value)]
    if mixed:
        code_product = Product(tenant_id=student.tenant_id, sku="CODE", name="Код",
                               price_astrocoins=100,
                               fulfillment_type=ProductFulfillmentType.DIGITAL_MANUAL)
        db_session.add(code_product)
        await db_session.flush()
        items.append(MiniAppOrderItemCreate(product_id=code_product.id, quantity=1))
    await db_session.commit()
    created = await create_miniapp_order(db_session, payload=MiniAppOrderCreate(
        max_user_id=53364725, tenant_slug=SCHOOL, student_id=student.id, items=items,
    ), default_tenant_slug=SCHOOL)
    issue_items = [MiniAppDigitalOrderItemIssue(
        order_item_id=item.id, codes=[] if item.recipient_field else ["UNIQUE-CODE"],
    ) for item in created.items]
    bad_items = [item.model_copy(deep=True) for item in issue_items]
    next(item for item in bad_items if not item.codes).codes = ["UNWANTED-CODE"]
    with pytest.raises(MiniAppStoreError, match="не требуется"):
        await issue_miniapp_digital_order(db_session, order_id=created.order.id,
            payload=MiniAppDigitalOrderIssue(max_user_id=director.max_user_id,
                tenant_slug=SCHOOL, items=bad_items), default_tenant_slug=SCHOOL)
    assert (await db_session.get(Order, created.order.id)).status == OrderStatus.CREATED
    payload = MiniAppDigitalOrderIssue(max_user_id=director.max_user_id,
                                      tenant_slug=SCHOOL, items=issue_items)
    result = await issue_miniapp_digital_order(db_session, order_id=created.order.id,
                                              payload=payload, default_tenant_slug=SCHOOL)
    assert result.order.status == OrderStatus.ISSUED_TO_STUDENT
    account_item = next(item for item in result.order.items if item.recipient_field)
    assert account_item.recipient_value == value
    assert account_item.issued_codes == []
    wallet = await db_session.scalar(select(Wallet).where(Wallet.student_id == student.id))
    assert wallet.balance == created.balance_after
    assert await db_session.scalar(select(func.count()).select_from(ProductCode)) == int(mixed)
    await issue_miniapp_digital_order(db_session, order_id=created.order.id,
                                      payload=payload, default_tenant_slug=SCHOOL)
    assert await db_session.scalar(select(func.count()).select_from(OrderStatusHistory).where(
        OrderStatusHistory.order_id == created.order.id,
        OrderStatusHistory.to_status == OrderStatus.ISSUED_TO_STUDENT,
    )) == 1
    assert await db_session.scalar(select(func.count()).select_from(AuditLog).where(
        AuditLog.action == "miniapp_order.digital_issued",
    )) == 1
    order = await db_session.get(Order, created.order.id)
    await db_session.refresh(order, ["items"])
    message = _order_message(order=order, student=student, balance_after=None,
                             issued_codes=["UNIQUE-CODE"] if mixed else [])
    assert "выполнен" in message
    if not mixed:
        assert "код" not in message.casefold()
