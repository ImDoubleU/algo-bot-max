from types import SimpleNamespace
from uuid import uuid4

import pytest

from app.models.enums import WarehouseType
from app.services.warehouse import (
    WarehouseServiceError,
    available_for_reservation,
    choose_inventory_for_reservation,
    issue_reserved_inventory,
    release_reservation,
    reserve_inventory,
    return_inventory,
    transfer_inventory,
)


def inventory(
    *,
    tenant_id=None,
    product_id=None,
    warehouse_type=WarehouseType.COMMON,
    venue_id=None,
    available=0,
    reserved=0,
):
    tenant_id = tenant_id or uuid4()
    product_id = product_id or uuid4()
    warehouse = SimpleNamespace(
        id=uuid4(),
        venue_id=venue_id,
        warehouse_type=warehouse_type,
        name="w",
    )
    return SimpleNamespace(
        tenant_id=tenant_id,
        product_id=product_id,
        warehouse=warehouse,
        product=SimpleNamespace(id=product_id),
        available_quantity=available,
        reserved_quantity=reserved,
        issued_quantity=0,
        returned_quantity=0,
    )


def test_choose_inventory_prefers_student_venue_warehouse() -> None:
    tenant_id = uuid4()
    product_id = uuid4()
    venue_id = uuid4()
    common = inventory(
        tenant_id=tenant_id,
        product_id=product_id,
        warehouse_type=WarehouseType.COMMON,
        available=10,
    )
    venue = inventory(
        tenant_id=tenant_id,
        product_id=product_id,
        warehouse_type=WarehouseType.VENUE,
        venue_id=venue_id,
        available=10,
    )

    selected = choose_inventory_for_reservation([common, venue], quantity=1, venue_id=venue_id)

    assert selected is venue


def test_choose_inventory_falls_back_to_common_warehouse() -> None:
    venue_id = uuid4()
    venue = inventory(warehouse_type=WarehouseType.VENUE, venue_id=venue_id, available=0)
    common = inventory(
        tenant_id=venue.tenant_id,
        product_id=venue.product_id,
        warehouse_type=WarehouseType.COMMON,
        available=2,
    )

    selected = choose_inventory_for_reservation([venue, common], quantity=1, venue_id=venue_id)

    assert selected is common


def test_reserve_release_issue_and_return_inventory() -> None:
    item = inventory(available=5)

    reserve_inventory(item, 2)
    assert item.reserved_quantity == 2
    assert available_for_reservation(item) == 3

    release_reservation(item, 1)
    assert item.reserved_quantity == 1

    issue_reserved_inventory(item, 1)
    assert item.available_quantity == 4
    assert item.issued_quantity == 1

    return_inventory(item, 1)
    assert item.available_quantity == 5
    assert item.returned_quantity == 1


def test_transfer_inventory_rejects_cross_tenant_transfer() -> None:
    source = inventory(available=5)
    target = inventory(product_id=source.product_id, available=0)

    with pytest.raises(WarehouseServiceError):
        transfer_inventory(source=source, target=target, quantity=1)
