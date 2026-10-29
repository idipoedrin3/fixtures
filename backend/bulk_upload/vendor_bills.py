from decimal import Decimal, InvalidOperation

from django.db import transaction
from django.db.models import Q
from rest_framework import serializers

from customers.models import PaymentTerm
from institution.models import Branch
from items.models import InventoryItem, InventoryItemUnitOfMeasure
from utilities.helpers import validation_error
from vendors.models import Vendor, VendorBill
from vendors.serializers import BulkVendorBillRowSerializer, VendorBillSerializer

TYPE_ALIASES = {
    "inventory": "inventory",
    "inventory_item": "inventory",
    "goods": "inventory",
    "service": "service",
    "services": "service",
    "other": "other",
    "other_item": "other",
}

PAYMENT_STATUS_ALIASES = {
    "paid": "paid",
    "unpaid": "unpaid",
    "partially_paid": "partially_paid",
    "partiallypaid": "partially_paid",
    "partial": "partially_paid",
}


def _resolve(queryset, value, name_field, label):
    if not value:
        return None

    value = str(value).strip()
    matches = list(queryset.filter(reference_code__iexact=value)[:2])
    if not matches:
        matches = list(queryset.filter(**{f"{name_field}__iexact": value})[:2])

    if len(matches) != 1:
        raise serializers.ValidationError(
            f"'{value}' must identify exactly one active {label}."
        )

    return matches[0]


def _resolve_item(institution, value, row_type):
    value = str(value or "").strip()
    if not value:
        raise serializers.ValidationError("Item is required.")

    matches = list(
        InventoryItem.objects.active()
        .filter(institution=institution)
        .filter(Q(reference_code__iexact=value) | Q(item_name__iexact=value))[:2]
    )
    if len(matches) != 1:
        raise serializers.ValidationError(
            f"'{value}' must identify exactly one active inventory item or service."
        )

    item = matches[0]
    if row_type == "inventory" and item.item_type != "GOODS":
        raise serializers.ValidationError(
            f"'{value}' is a service. Use type 'service'."
        )
    if row_type == "service" and item.item_type != "SERVICES":
        raise serializers.ValidationError(
            f"'{value}' is an inventory item. Use type 'inventory'."
        )

    return item


def _resolve_uom(item, value):
    queryset = InventoryItemUnitOfMeasure.objects.filter(
        inventory_item=item,
        deleted_at__isnull=True,
    ).select_related("unit_of_measure")

    if value:
        value = str(value).strip()
        matches = list(
            queryset.filter(
                Q(unit_of_measure__unit_name__iexact=value)
                | Q(unit_of_measure__unit_abbreviation__iexact=value)
                | Q(reference_code__iexact=value)
            )[:2]
        )
        if len(matches) != 1:
            raise serializers.ValidationError(
                f"'{value}' must identify exactly one unit of measure "
                f"for item '{item.item_name}'."
            )
        return matches[0]

    base_unit = queryset.filter(is_base_unit_of_measure=True).first()
    if base_unit is None:
        base_unit = queryset.order_by("id").first()

    if base_unit is None:
        raise serializers.ValidationError(
            f"Item '{item.item_name}' has no unit of measure configured."
        )

    return base_unit


def _to_decimal(value, default=None):
    if value is None or value == "":
        return default

    try:
        return Decimal(str(value))
    except (InvalidOperation, TypeError, ValueError):
        raise serializers.ValidationError(f"Invalid number '{value}'.")


def _normalize_type(value):
    normalized = (
        str(value or "").strip().lower().replace(" ", "_").replace("-", "_")
    )
    return TYPE_ALIASES.get(normalized, normalized)


def _normalize_payment_status(value):
    normalized = (
        str(value or "").strip().lower().replace(" ", "_").replace("-", "_")
    )
    return PAYMENT_STATUS_ALIASES.get(normalized, normalized)


def prepare_vendor_bills(rows, request):
    institution = request.institution
    groups = {}
    errors = []

    for index, row in enumerate(rows, start=1):
        try:
            normalized_row = dict(row)
            normalized_row["type"] = _normalize_type(row.get("type"))
            normalized_row["payment_status"] = _normalize_payment_status(
                row.get("payment_status")
            )

            serializer = BulkVendorBillRowSerializer(data=normalized_row)
            serializer.is_valid(raise_exception=True)
            data = serializer.validated_data

            row_type = normalized_row["type"]
            if row_type not in {"inventory", "service", "other"}:
                raise serializers.ValidationError(
                    "Type must be one of: inventory, service, other."
                )

            payment_status = normalized_row["payment_status"]
            if payment_status not in {"paid", "unpaid", "partially_paid"}:
                raise serializers.ValidationError(
                    "Payment status must be one of: paid, unpaid, partially paid."
                )

            reference = str(data["reference_code"]).strip()
            vendor = _resolve(
                Vendor.objects.active().filter(institution=institution),
                data.get("vendor"),
                "vendor_name",
                "vendor",
            )
            if vendor is None:
                raise serializers.ValidationError("Vendor is required.")

            branch = _resolve(
                Branch.objects.active().filter(institution=institution),
                data.get("branch"),
                "branch_name",
                "branch",
            )
            payment_terms = _resolve(
                PaymentTerm.objects.active().filter(institution=institution),
                data.get("payment_terms"),
                "term_name",
                "payment term",
            )

            quantity = data["qty"]
            unit_price = data["unit_price"]

            if row_type in {"inventory", "service"}:
                item = _resolve_item(institution, data.get("item"), row_type)
                unit_of_measure = _resolve_uom(item, data.get("uom"))
                line = {
                    "line_item": str(item.base_uuid),
                    "unit_of_measure": str(unit_of_measure.base_uuid),
                    "quantity": quantity,
                    "unit_price": str(unit_price),
                }
                line_bucket = "inventory_line_items"
            else:
                line = {
                    "line_item": str(data.get("item") or "").strip(),
                    "unit_of_measure": str(data.get("uom") or "").strip(),
                    "quantity": quantity,
                    "unit_price": str(unit_price),
                }
                line_bucket = "other_line_items"

            gross_amount = _to_decimal(data.get("gross_amount"))
            if gross_amount is None:
                gross_amount = unit_price * quantity

            header = {
                "vendor": str(vendor.base_uuid),
                "branch": str(branch.base_uuid) if branch else None,
                "payment_terms": str(payment_terms.base_uuid) if payment_terms else None,
                "received_date": data.get("received_date"),
                "due_date": data.get("due_date"),
            }

            key = reference.casefold()
            if key not in groups:
                payload = {
                    "reference_code": reference,
                    "vendor": header["vendor"],
                    "inventory_line_items": [],
                    "other_line_items": [],
                }
                if header["branch"]:
                    payload["branch"] = header["branch"]
                if header["payment_terms"]:
                    payload["payment_terms"] = header["payment_terms"]
                if header["received_date"]:
                    payload["received_date"] = header["received_date"].isoformat()
                if header["due_date"]:
                    payload["due_date"] = header["due_date"].isoformat()

                groups[key] = {
                    "reference_code": reference,
                    "rows": [],
                    "payload": payload,
                    "header": header,
                    "raw_total": Decimal("0"),
                    "paid_raw": Decimal("0"),
                    "statuses": set(),
                }

            group = groups[key]
            if any(group["header"][field] != value for field, value in header.items()):
                raise serializers.ValidationError(
                    "Rows sharing a reference must have the same vendor, branch, "
                    "payment terms, received date, and due date."
                )

            group["rows"].append(index)
            group["payload"][line_bucket].append(line)
            group["raw_total"] += gross_amount

            if payment_status == "paid":
                group["paid_raw"] += gross_amount
            elif payment_status == "partially_paid":
                group["paid_raw"] += gross_amount / Decimal("2")

            group["statuses"].add(payment_status)

        except Exception as exc:
            errors.append({"data_row": index, "error": str(exc)})

    for group in groups.values():
        try:
            reference = group["reference_code"]
            if VendorBill.objects.filter(
                institution=institution,
                reference_code__iexact=reference,
            ).exists():
                raise serializers.ValidationError(
                    f"Vendor bill reference '{reference}' already exists."
                )

            with transaction.atomic():
                serializer = VendorBillSerializer(
                    data=group["payload"],
                    context={"request": request},
                )
                serializer.is_valid(raise_exception=True)
                transaction.set_rollback(True)

            statuses = group.pop("statuses")
            if statuses == {"paid"}:
                group["payment_status"] = "paid"
            elif statuses == {"unpaid"}:
                group["payment_status"] = "unpaid"
            else:
                group["payment_status"] = "partially_paid"

            group["raw_total"] = str(group["raw_total"])
            group["paid_raw"] = str(group["paid_raw"])
        except Exception as exc:
            errors.append({"data_rows": group["rows"], "error": str(exc)})

    if errors:
        raise validation_error(
            {
                "detail": "Vendor bill upload validation failed. Nothing was queued.",
                "errors": errors,
            }
        )

    return list(groups.values())
