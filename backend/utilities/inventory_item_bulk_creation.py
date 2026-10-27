import pandas as pd
import uuid
from django.db import transaction
from django.core.exceptions import ObjectDoesNotExist
from utilities.helpers import get_institution
from items.models import InventoryItem, ItemCategory, ItemUnitOfMeasure
from items.serializers import InventoryItemSerializer
from fixed_assets.models import AssetCategory, FixedAsset
from fixed_assets.serializers import FixedAssetSerializer
from decimal import Decimal
from django.contrib.contenttypes.models import ContentType
from audit.models import AuditLog
from items.serializers import ItemUnitOfMeasureSerializer


def run_initial_stock_journal_entries(inventory_items):
    """
    Manually triggers financial transaction processing
    for bulk-created inventory items (bypassed by bulk_create).
    """
    for item in inventory_items:
        try:
            if item.quantity_on_hand > 0 and not item.are_initial_journal_entries_made:
                item._process_financial_events()
                item.are_initial_journal_entries_made = True
                item.save(update_fields=["are_initial_journal_entries_made"])
        except Exception as e:
            print(
                f"Error processing journal entries for item {item.reference_code}: {e}"
            )
            continue


def run_initial_asset_journal_entries(assets):
    """
    Manually triggers financial journal processing for bulk-created fixed assets.
    Ensures _process_financial_events() runs exactly once.
    """
    for asset in assets:
        try:
            if not asset.are_initial_journal_entries_made:
                asset._process_financial_events()
                asset.are_initial_journal_entries_made = True
                asset.save(update_fields=["are_initial_journal_entries_made"])
        except Exception as e:
            print(f"Error processing journal entries for asset {asset.asset_code}: {e}")
            continue


def process_bulk_inventory_upload(data_list, request):
    """
    Handles bulk creation of inventory items from JSON data.
    If item_category or unit_of_measure does not exist, they are created automatically.
    """
    validated_data_list = []
    errors = []

    institution = get_institution(request)

    for i, row in enumerate(data_list):
        try:
            item_category_name = row.get("item_category")
            if item_category_name is None:
                raise ValueError("Item category is required.")
            item_category_name = str(item_category_name).strip()
            if item_category_name.lower() == "nan" or item_category_name == "":
                raise ValueError("Item category is required and must be valid.")

            item_unit_of_measure_name = row.get("unit_of_measure")
            if item_unit_of_measure_name is not None:
                item_unit_of_measure_name = str(item_unit_of_measure_name).strip()
                if (
                    item_unit_of_measure_name.lower() == "nan"
                    or item_unit_of_measure_name == ""
                ):
                    item_unit_of_measure_name = None

            item_category_obj = ItemCategory.objects.filter(
                name__iexact=item_category_name, institution=institution
            ).first()

            if not item_category_obj:
                item_category_obj = ItemCategory.objects.create(
                    name=item_category_name, institution=institution
                )

            item_unit_of_measure_obj = None
            if item_unit_of_measure_name:
                item_unit_of_measure_obj = ItemUnitOfMeasure.objects.filter(
                    unit_name__iexact=item_unit_of_measure_name, institution=institution
                ).first()
            if not item_unit_of_measure_obj:
                item_unit_of_measure_obj = ItemUnitOfMeasure.objects.create(
                    unit_name=item_unit_of_measure_name, institution=institution
                )

            serializer_data = {
                "reference_code": row.get("reference_code"),
                "item_name": row.get("item_name"),
                "item_type": row.get("item_type", "GOODS"),
                "buying_price": row.get("buying_price", 0.00),
                "selling_price": row.get("selling_price", 0.00),
                "quantity_on_hand": row.get("quantity_on_hand", 0),
                "reorder_point": row.get("reorder_point", 0),
                "item_category": item_category_obj.pk,
                "unit_of_measure": (
                    item_unit_of_measure_obj.pk if item_unit_of_measure_obj else None
                ),
            }

            serializer = InventoryItemSerializer(
                data=serializer_data, context={"request": request}
            )

            if serializer.is_valid():
                instance_data = serializer.validated_data
                instance_data["item_category"] = item_category_obj
                instance_data["unit_of_measure"] = item_unit_of_measure_obj
                validated_data_list.append(instance_data)
            else:
                errors.append({"row": i + 1, "errors": serializer.errors})

        except ValueError as e:
            errors.append({"row": i + 1, "error": f"Invalid data: {e}"})
        except Exception as e:
            errors.append({"row": i + 1, "errors": f"Unexpected error: {str(e)}"})

    if errors:
        return {"status": "validation_failed", "errors": errors}

    total_created = 0
    chunk_size = 100
    all_created_instances = []
    try:
        with transaction.atomic():
            for i in range(0, len(validated_data_list), chunk_size):
                chunk = validated_data_list[i : i + chunk_size]
                instances_to_create = [InventoryItem(**data) for data in chunk]
                new_instances = InventoryItem.objects.bulk_create(instances_to_create)
                all_created_instances.extend(new_instances)
                total_created += len(new_instances)

            InventoryItem.bulk_assign_to_branches(all_created_instances)

            run_initial_stock_journal_entries(all_created_instances)

        return {
            "status": "success",
            "message": f"Successfully created {total_created} inventory items.",
        }
    except Exception as e:
        return {
            "status": "failed",
            "message": f"Database error during creation: {str(e)}",
        }


def process_bulk_item_units(records, request, institution):
    seen = set()
    duplicate_rows = []

    for idx, row in enumerate(records, start=1):
        unit_name = str(row.get("unit_name", "")).strip()
        if not unit_name:
            continue

        key = unit_name.lower()

        if key in seen:
            duplicate_rows.append(
                {
                    "row": idx,
                    "unit_name": unit_name,
                }
            )
        else:
            seen.add(key)

    if duplicate_rows:
        return {
            "status": "validation_failed",
            "message": "Duplicate unit names detected in uploaded file.",
            "duplicates_in_file": duplicate_rows,
        }

    existing_active = ItemUnitOfMeasure.objects.filter(
        institution=institution, is_active=True, deleted_at__isnull=True
    ).values_list("unit_name", flat=True)

    existing_active_map = {name.lower(): name for name in existing_active}

    duplicates_in_db = []
    for idx, row in enumerate(records, start=1):
        unit_name = str(row.get("unit_name", "")).strip()
        if not unit_name:
            continue

        key = unit_name.lower()

        if key in existing_active_map:
            duplicates_in_db.append(
                {
                    "row": idx,
                    "unit_name": unit_name,
                }
            )

    if duplicates_in_db:
        return {
            "status": "validation_failed",
            "message": f"Some units already exist in the institution,:{duplicates_in_db}",
        }

    created = []
    restored = []

    existing_deleted = {
        u.unit_name.lower(): u
        for u in ItemUnitOfMeasure.objects.filter(
            institution=institution, deleted_at__isnull=False
        )
    }

    with transaction.atomic():
        for row in records:
            unit_name = str(row.get("unit_name", "")).strip()
            if not unit_name:
                continue

            key = unit_name.lower()
            abbreviation = str(row.get("unit_abbreviation", "")).strip()
            description = row.get("description")

            existing = existing_deleted.get(key)
            if existing:
                existing.deleted_at = None
                existing.is_active = True
                existing.unit_abbreviation = abbreviation or existing.unit_abbreviation
                existing.description = description
                existing.updated_by = request.user
                existing.approval_status = "under_creation"
                existing.save()

                AuditLog.objects.create(
                    content_type=ContentType.objects.get_for_model(ItemUnitOfMeasure),
                    object_id=existing.pk,
                    action="RESTORE",
                    user=request.user,
                    description=f"Restored ItemUnitOfMeasure: {existing.unit_name}",
                )

                existing.confirm_create()
                restored.append(existing)
                continue

            unit = ItemUnitOfMeasure.objects.create(
                institution=institution,
                unit_name=unit_name,
                unit_abbreviation=abbreviation,
                description=description,
                created_by=request.user,
                updated_by=request.user,
            )

            AuditLog.objects.create(
                content_type=ContentType.objects.get_for_model(ItemUnitOfMeasure),
                object_id=unit.pk,
                action="CREATE",
                user=request.user,
                description=f"Created ItemUnitOfMeasure: {unit.unit_name}",
            )

            unit.confirm_create()
            created.append(unit)

    all_units = created + restored

    return {
        "status": "success",
        "summary": {
            "created": len(created),
            "restored": len(restored),
        },
        "data": ItemUnitOfMeasureSerializer(
            all_units, many=True, context={"request": request}
        ).data,
    }
