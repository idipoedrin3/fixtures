from decimal import Decimal
from typing import List, Tuple

SMALLEST_ONLY = "SMALLEST_ONLY"
LARGEST_FIRST = "LARGEST_FIRST"


def get_branch_uom_map(branch_item) -> dict:
    from items.models import BranchInventoryItemUnitOfMeasure

    records = BranchInventoryItemUnitOfMeasure.objects.filter(
        branch_inventory_item=branch_item,
        deleted_at__isnull=True,
    ).select_related("unit_of_measure")

    return {r.unit_of_measure: r for r in records}


def get_warehouse_uom_map(inventory_item) -> dict:
    from items.models import InventoryItemUnitOfMeasure

    records = (
        InventoryItemUnitOfMeasure.objects.active()
        .filter(
            inventory_item=inventory_item,
        )
        .select_related("unit_of_measure")
    )

    return {r.unit_of_measure: r for r in records}


def get_conversion_factor(branch_item, item_uom) -> Decimal:
    from items.models import InventoryItemUnitOfMeasure

    uom_map = get_branch_uom_map(branch_item)
    record = uom_map.get(item_uom)
    if record:
        return Decimal(record.conversion_factor)

    inv_uom = (
        InventoryItemUnitOfMeasure.objects.active()
        .filter(
            inventory_item=branch_item.inventory_item,
            unit_of_measure=item_uom,
        )
        .first()
    )

    if inv_uom:
        return Decimal(inv_uom.conversion_factor)

    raise ValueError(
        f"No conversion factor found for unit '{item_uom.unit_name}' "
        f"on item '{branch_item.inventory_item.item_name}'"
    )


def get_conversion_factor_warehouse_level(inventory_item, item_uom) -> Decimal:
    from items.models import InventoryItemUnitOfMeasure

    uom_map = get_warehouse_uom_map(inventory_item)
    record = uom_map.get(item_uom)
    if record:
        return Decimal(record.conversion_factor)

    inv_uom = (
        InventoryItemUnitOfMeasure.objects.active()
        .filter(
            inventory_item=inventory_item,
            unit_of_measure=item_uom,
        )
        .first()
    )

    if inv_uom:
        return Decimal(inv_uom.conversion_factor)

    raise ValueError(
        f"No conversion factor found for unit '{item_uom.unit_name}' "
        f"on item '{inventory_item.item_name}'"
    )


def get_smallest_unit(branch_item):
    uom_map = get_branch_uom_map(branch_item)
    if not uom_map:
        return None, Decimal("1")

    return min(
        ((uom, Decimal(record.conversion_factor)) for uom, record in uom_map.items()),
        key=lambda x: x[1],
    )


def get_smallest_unit_warehouse_level(inventory_item):
    uom_map = get_warehouse_uom_map(inventory_item)
    if not uom_map:
        return None, Decimal("1")

    return min(
        ((uom, Decimal(record.conversion_factor)) for uom, record in uom_map.items()),
        key=lambda x: x[1],
    )


def get_units_sorted_by_size(branch_item, descending: bool = True) -> List[Tuple]:
    uom_map = get_branch_uom_map(branch_item)
    result = [
        (item_uom, Decimal(record.conversion_factor))
        for item_uom, record in uom_map.items()
    ]
    result.sort(key=lambda x: x[1], reverse=descending)
    return result


def get_units_sorted_by_size_warehouse_level(
    inventory_item,
    descending: bool = True,
) -> List[Tuple]:
    uom_map = get_warehouse_uom_map(inventory_item)
    result = [
        (item_uom, Decimal(record.conversion_factor))
        for item_uom, record in uom_map.items()
    ]
    result.sort(key=lambda x: x[1], reverse=descending)
    return result


def decompose_base_units(
    base_quantity: Decimal,
    branch_item,
    strategy: str = SMALLEST_ONLY,
) -> List[Tuple]:

    if strategy == SMALLEST_ONLY:
        return _decompose_smallest_only(base_quantity, branch_item)

    if strategy == LARGEST_FIRST:
        return _decompose_largest_first(base_quantity, branch_item)

    raise ValueError(
        f"Unknown breakdown strategy '{strategy}'. "
        f"Use SMALLEST_ONLY or LARGEST_FIRST."
    )


def decompose_base_units_warehouse_level(
    base_quantity: Decimal,
    inventory_item,
    strategy: str = SMALLEST_ONLY,
) -> List[Tuple]:

    if strategy == SMALLEST_ONLY:
        return _decompose_smallest_only_warehouse_level(base_quantity, inventory_item)

    if strategy == LARGEST_FIRST:
        return _decompose_largest_first_warehouse_level(base_quantity, inventory_item)

    raise ValueError(
        f"Unknown breakdown strategy '{strategy}'. "
        f"Use SMALLEST_ONLY or LARGEST_FIRST."
    )


def _decompose_smallest_only(base_quantity: Decimal, branch_item) -> List[Tuple]:
    smallest_uom, smallest_cf = get_smallest_unit(branch_item)

    if smallest_uom is None:
        return []

    qty = base_quantity / smallest_cf
    return [(smallest_uom, qty)] if qty > Decimal("0") else []


def _decompose_smallest_only_warehouse_level(
    base_quantity: Decimal, inventory_item
) -> List[Tuple]:
    smallest_uom, smallest_cf = get_smallest_unit_warehouse_level(inventory_item)

    if smallest_uom is None:
        return []

    qty = base_quantity / smallest_cf
    return [(smallest_uom, qty)] if qty > Decimal("0") else []


def _decompose_largest_first(base_quantity: Decimal, branch_item) -> List[Tuple]:
    units_desc = get_units_sorted_by_size(branch_item, descending=True)
    remaining = base_quantity
    result = []

    for item_uom, cf in units_desc:
        if remaining <= Decimal("0"):
            break
        count = remaining // cf
        if count > Decimal("0"):
            result.append((item_uom, count))
            remaining -= count * cf

    return result


def _decompose_largest_first_warehouse_level(
    base_quantity: Decimal, inventory_item
) -> List[Tuple]:
    units_desc = get_units_sorted_by_size_warehouse_level(
        inventory_item,
        descending=True,
    )
    remaining = base_quantity
    result = []

    for item_uom, cf in units_desc:
        if remaining <= Decimal("0"):
            break
        count = remaining // cf
        if count > Decimal("0"):
            result.append((item_uom, count))
            remaining -= count * cf

    return result
