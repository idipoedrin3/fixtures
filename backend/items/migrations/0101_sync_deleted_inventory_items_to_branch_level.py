from django.db import migrations
from django.utils import timezone


def sync_deleted_inventory_items_to_branch_level(apps, schema_editor):
    InventoryItem = apps.get_model("items", "InventoryItem")
    BranchInventoryItem = apps.get_model("items", "BranchInventoryItem")
    BranchInventoryItemUnitOfMeasure = apps.get_model(
        "items", "BranchInventoryItemUnitOfMeasure"
    )
    BranchInventoryItemStockLayer = apps.get_model(
        "items", "BranchInventoryItemStockLayer"
    )

    deleted_inventory_items = InventoryItem.objects.filter(
        deleted_at__isnull=False,
    ).only("id", "deleted_at")

    for inventory_item in deleted_inventory_items.iterator():
        deleted_at = inventory_item.deleted_at or timezone.now()

        branch_item_ids = list(
            BranchInventoryItem.objects.filter(
                inventory_item_id=inventory_item.id,
                deleted_at__isnull=True,
            ).values_list("id", flat=True)
        )

        if not branch_item_ids:
            continue

        BranchInventoryItemUnitOfMeasure.objects.filter(
            branch_inventory_item_id__in=branch_item_ids,
            deleted_at__isnull=True,
        ).update(
            deleted_at=deleted_at,
            is_active=False,
        )

        BranchInventoryItemStockLayer.objects.filter(
            branch_inventory_item_id__in=branch_item_ids,
            deleted_at__isnull=True,
        ).update(
            deleted_at=deleted_at,
            is_active=False,
        )

        BranchInventoryItem.objects.filter(id__in=branch_item_ids).update(
            deleted_at=deleted_at,
            is_active=False,
        )


class Migration(migrations.Migration):

    dependencies = [
        ("items", "0100_branchtobranchstockmovement_b2b_from_status_date_idx_and_more"),
    ]

    operations = [
        migrations.RunPython(
            sync_deleted_inventory_items_to_branch_level,
            reverse_code=migrations.RunPython.noop,
        ),
    ]
