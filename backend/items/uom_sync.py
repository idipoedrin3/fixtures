from decimal import Decimal
from django.core.exceptions import ValidationError
from .models import InventoryItemUnitOfMeasure


def sync_inventory_item_uom_conversion_factors(inventory_item_id: int):
    units = list(
        InventoryItemUnitOfMeasure.objects.active()
        .filter(
            inventory_item_id=inventory_item_id,
        )
        .select_related("unit_of_measure", "other_uom")
    )

    if not units:
        return

    base_units = [u for u in units if u.is_base_unit_of_measure]
    if len(base_units) != 1:
        raise ValidationError(
            f"Expected exactly one base unit for item {inventory_item_id}, found {len(base_units)}."
        )

    base_unit = base_units[0]
    base_uom_id = base_unit.unit_of_measure_id

    all_uom_ids = {u.unit_of_measure_id for u in units}
    for u in units:
        if u.other_uom_id and u.other_uom_id not in all_uom_ids:
            raise ValidationError(
                f"Unit '{u.unit_of_measure.unit_name}' references other_uom "
                f"'{u.other_uom.unit_name}' which does not belong to this inventory item."
            )
        if u.other_uom_id and u.other_uom_id == u.unit_of_measure_id:
            raise ValidationError(
                f"Unit '{u.unit_of_measure.unit_name}' references itself as other_uom."
            )

    resolved: dict[int, Decimal] = {base_uom_id: Decimal("1")}
    base_unit.conversion_factor = Decimal("1")

    unresolved = [u for u in units if not u.is_base_unit_of_measure]

    max_iterations = len(unresolved) + 1
    iteration = 0

    while unresolved:
        if iteration >= max_iterations:
            unresolved_names = [u.unit_of_measure.unit_name for u in unresolved]
            raise ValidationError(
                f"Cannot resolve UOM conversion factors — cycle or missing dependency detected. "
                f"Unresolved units: {unresolved_names}"
            )

        progress = False

        still_unresolved = []
        for u in unresolved:
            if u.other_uom_id is None or u.other_quantity is None:
                raise ValidationError(
                    f"Non-base unit '{u.unit_of_measure.unit_name}' must have both "
                    f"other_uom and other_quantity set."
                )

            if u.other_uom_id in resolved:
                u.conversion_factor = u.other_quantity * resolved[u.other_uom_id]
                resolved[u.unit_of_measure_id] = u.conversion_factor
                progress = True
            else:
                still_unresolved.append(u)

        if not progress and still_unresolved:
            unresolved_names = [u.unit_of_measure.unit_name for u in still_unresolved]
            raise ValidationError(
                f"Cannot resolve UOM conversion factors — cycle or missing dependency detected. "
                f"Unresolved units: {unresolved_names}"
            )

        unresolved = still_unresolved
        iteration += 1

    InventoryItemUnitOfMeasure.objects.bulk_update(units, ["conversion_factor"])
