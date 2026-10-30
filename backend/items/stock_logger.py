from decimal import Decimal
from django.contrib.contenttypes.models import ContentType
from django.utils import timezone


def log_stock_movement(
    *,
    movement_type: str,
    inventory_item,
    quantity_change: Decimal,
    quantity_before: Decimal,
    unit_cost: Decimal = Decimal("0"),
    unit_of_measure=None,
    institution=None,
    branch=None,
    source_document=None,
    source_reference: str = "",
    notes: str = "",
    movement_date=None,
    goods_issued_note_line=None,
    item_return_item=None,
    reverses_movement=None,
):
    from items.models import StockMovementLog

    if institution is None and branch is None:
        raise ValueError("Either institution or branch must be provided.")

    if branch is not None:
        branch_institution = branch.institution

        if institution is not None and institution.pk != branch_institution.pk:
            raise ValueError(
                "The supplied institution does not match the branch institution."
            )

        institution = branch_institution

    stock_level = "branch" if branch else "institution"
    quantity_after = quantity_before + quantity_change

    content_type = None
    object_id = None
    if source_document is not None:
        content_type = ContentType.objects.get_for_model(source_document.__class__)
        object_id = source_document.pk

    StockMovementLog.objects.create(
        movement_type=movement_type,
        stock_level=stock_level,
        inventory_item=inventory_item,
        unit_of_measure=unit_of_measure,
        quantity_change=quantity_change,
        quantity_before=quantity_before,
        quantity_after=quantity_after,
        unit_cost=unit_cost,
        institution=institution,
        branch=branch,
        content_type=content_type,
        object_id=object_id,
        source_reference=source_reference,
        description=notes,
        movement_date=movement_date or timezone.now(),
        goods_issued_note_line=goods_issued_note_line,
        item_return_item=item_return_item,
        reverses_movement=reverses_movement,
    )
