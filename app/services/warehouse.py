from collections.abc import Iterable
from dataclasses import dataclass
from uuid import UUID

from app.models.enums import StockMovementType, WarehouseType
from app.models.store import StockMovement, WarehouseInventory


class WarehouseServiceError(RuntimeError):
    pass


@dataclass(frozen=True)
class ReservationResult:
    inventory: WarehouseInventory
    available_before: int
    reserved_after: int


def available_for_reservation(inventory: WarehouseInventory) -> int:
    return inventory.available_quantity - inventory.reserved_quantity


def _warehouse_priority(inventory: WarehouseInventory, venue_id: UUID | None) -> tuple[int, str]:
    warehouse = inventory.warehouse
    if venue_id is not None and warehouse.venue_id == venue_id:
        return (0, warehouse.name)
    if warehouse.warehouse_type == WarehouseType.COMMON:
        return (1, warehouse.name)
    if warehouse.warehouse_type == WarehouseType.PARTNER:
        return (2, warehouse.name)
    return (3, warehouse.name)


def choose_inventory_for_reservation(
    inventories: Iterable[WarehouseInventory],
    *,
    quantity: int,
    venue_id: UUID | None,
) -> WarehouseInventory | None:
    candidates = [
        inventory
        for inventory in inventories
        if inventory.product is not None
        and getattr(inventory, "is_active", True)
        and available_for_reservation(inventory) >= quantity
    ]
    if not candidates:
        return None
    return sorted(candidates, key=lambda item: _warehouse_priority(item, venue_id))[0]


def reserve_inventory(inventory: WarehouseInventory, quantity: int) -> ReservationResult:
    if quantity <= 0:
        raise WarehouseServiceError("Quantity must be positive")

    available_before = available_for_reservation(inventory)
    if available_before < quantity:
        raise WarehouseServiceError("Not enough stock to reserve")

    inventory.reserved_quantity += quantity
    return ReservationResult(
        inventory=inventory,
        available_before=available_before,
        reserved_after=inventory.reserved_quantity,
    )


def release_reservation(inventory: WarehouseInventory, quantity: int) -> None:
    if quantity <= 0:
        raise WarehouseServiceError("Quantity must be positive")
    if inventory.reserved_quantity < quantity:
        raise WarehouseServiceError("Cannot release more than reserved")
    inventory.reserved_quantity -= quantity


def issue_reserved_inventory(inventory: WarehouseInventory, quantity: int) -> None:
    if quantity <= 0:
        raise WarehouseServiceError("Quantity must be positive")
    if inventory.reserved_quantity < quantity:
        raise WarehouseServiceError("Cannot issue more than reserved")
    if inventory.available_quantity < quantity:
        raise WarehouseServiceError("Cannot issue more than available")

    inventory.reserved_quantity -= quantity
    inventory.available_quantity -= quantity
    inventory.issued_quantity += quantity


def return_inventory(inventory: WarehouseInventory, quantity: int) -> None:
    if quantity <= 0:
        raise WarehouseServiceError("Quantity must be positive")
    inventory.available_quantity += quantity
    inventory.returned_quantity += quantity


def transfer_inventory(
    *,
    source: WarehouseInventory,
    target: WarehouseInventory,
    quantity: int,
) -> None:
    if quantity <= 0:
        raise WarehouseServiceError("Quantity must be positive")
    if source.tenant_id != target.tenant_id:
        raise WarehouseServiceError("Cannot transfer stock between tenants")
    if source.product_id != target.product_id:
        raise WarehouseServiceError("Cannot transfer different products")
    if available_for_reservation(source) < quantity:
        raise WarehouseServiceError("Not enough available stock to transfer")

    source.available_quantity -= quantity
    target.available_quantity += quantity


def build_stock_movement(
    *,
    inventory: WarehouseInventory,
    movement_type: StockMovementType,
    quantity: int,
    actor_account_id: UUID | None = None,
    order_id: UUID | None = None,
    from_warehouse_id: UUID | None = None,
    to_warehouse_id: UUID | None = None,
    comment: str | None = None,
) -> StockMovement:
    if quantity <= 0:
        raise WarehouseServiceError("Quantity must be positive")

    return StockMovement(
        tenant_id=inventory.tenant_id,
        product_id=inventory.product_id,
        from_warehouse_id=from_warehouse_id,
        to_warehouse_id=to_warehouse_id,
        order_id=order_id,
        actor_account_id=actor_account_id,
        movement_type=movement_type,
        quantity=quantity,
        comment=comment,
    )
