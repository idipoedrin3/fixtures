from decimal import Decimal

from django.contrib.contenttypes.models import ContentType
from django.db import transaction
from django.db.models import Q
from rest_framework import serializers

from accounts.models import Account
from customers.models import PaymentTerm
from institution.models import Branch
from items.models import InventoryItem, InventoryItemUnitOfMeasure
from taxation.models import Tax
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
    "other_expense": "other_expense",
    "other_expenses": "other_expense",
    "expense": "other_expense",
    "expenses": "other_expense",
}

VALID_TYPES = {"inventory", "service", "other", "other_expense"}

PAYMENT_STATUS_ALIASES = {
    "paid": "paid",
    "unpaid": "unpaid",
    "partially_paid": "partially_paid",
    "partiallypaid": "partially_paid",
    "partial": "partially_paid",
}

HEADER_LABELS = {
    "vendor": "vendor",
    "branch": "branch",
    "payment_terms": "payment terms",
    "due_date": "due date",
}


def _flatten(detail):
    if isinstance(detail, dict):
        return "; ".join(f"{key}: {_flatten(value)}" for key, value in detail.items())
    if isinstance(detail, (list, tuple)):
        return " ".join(_flatten(item) for item in detail)
    return str(detail)


def _error_message(exc):
    if isinstance(exc, serializers.ValidationError):
        return _flatten(exc.detail)
    return str(exc)


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


def _resolve_item(institution, value):
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
            f"'{value}' must identify exactly one active inventory item or service. "
            "Use type 'Other' for anything not in inventory."
        )

    return matches[0]


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
            available = (
                ", ".join(queryset.values_list("unit_of_measure__unit_name", flat=True))
                or "none configured"
            )
            raise serializers.ValidationError(
                f"'{value}' does not match exactly one unit of measure of "
                f"'{item.item_name}'. Available units: {available}. "
                "Leave UOM blank to use the base unit."
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


def _build_taxes(institution, value):
    tax = _resolve(
        Tax.objects.active().filter(institution=institution),
        value,
        "tax_name",
        "tax",
    )
    if tax is None:
        return []
    return [
        {
            "tax": str(tax.base_uuid),
            "is_inclusive": bool(getattr(tax, "is_inclusive", False)),
        }
    ]


def _cash_account_models():
    from bank_management.models import (
        BankAccount,
        CashAtHandAccount,
        DigitalWalletAccount,
        MobileMoneyAccount,
    )

    return (BankAccount, MobileMoneyAccount, DigitalWalletAccount, CashAtHandAccount)


def _cash_account_label(account):
    reference = account.get_chart_of_account_reference()
    return getattr(reference, "account_name", None) or account.reference_code or ""


def _institution_cash_accounts(institution):
    accounts = []
    for model in _cash_account_models():
        accounts.extend(
            model.objects.filter(institution=institution, deleted_at__isnull=True)
        )
    return accounts


def cash_account_options(institution):
    return sorted(
        {
            label
            for label in (
                _cash_account_label(account)
                for account in _institution_cash_accounts(institution)
            )
            if label
        }
    )


class _CashAccountDirectory:
    def __init__(self, institution):
        self.institution = institution
        self._entries = None

    def _load(self):
        if self._entries is None:
            self._entries = [
                (account, _cash_account_label(account))
                for account in _institution_cash_accounts(self.institution)
            ]
        return self._entries

    def resolve(self, value):
        raw = str(value or "").strip()
        if not raw:
            return None

        needle = raw.casefold()
        matches = [
            account
            for account, label in self._load()
            if needle
            in {
                label.casefold(),
                str(account.reference_code or "").casefold(),
                str(account.base_uuid).casefold(),
            }
        ]
        if len(matches) != 1:
            raise serializers.ValidationError(
                f"'{raw}' must identify exactly one cash or bank account."
            )
        return matches[0]


def _cash_account_payload(account):
    return {
        "content_type": ContentType.objects.get_for_model(
            account, for_concrete_model=False
        ).id,
        "content_object_uuid": str(account.base_uuid),
    }


def _ensure_base_currency_payment(institution, vendor, cash_account):
    base_currency = institution.currency
    vendor_currency = vendor.currency if vendor.currency_id else base_currency
    account_currency = (
        cash_account.currency.currency if cash_account.currency_id else base_currency
    )
    if vendor_currency != base_currency or account_currency != base_currency:
        raise serializers.ValidationError(
            "Payments in a bulk upload are only supported when the vendor and the "
            "cash account both use the institution's base currency. Mark these "
            "rows Unpaid and record the payment from the bill."
        )


def _paid_portion(payment_status, row_amount, amount_paid):
    if payment_status == "partially_paid":
        if amount_paid is None:
            raise serializers.ValidationError(
                "Amount Paid is required for 'partially paid' rows."
            )
        if amount_paid <= 0 or amount_paid >= row_amount:
            raise serializers.ValidationError(
                "Amount Paid must be greater than zero and less than the row "
                "amount (Unit Price x Qty)."
            )
        return amount_paid

    if amount_paid is not None:
        raise serializers.ValidationError(
            "Amount Paid can only be set on 'partially paid' rows."
        )

    return row_amount if payment_status == "paid" else Decimal("0")


def _normalize(value):
    return str(value or "").strip().lower().replace(" ", "_").replace("-", "_")


def _normalize_type(value):
    normalized = _normalize(value)
    return TYPE_ALIASES.get(normalized, normalized)


def _normalize_payment_status(value):
    normalized = _normalize(value)
    return PAYMENT_STATUS_ALIASES.get(normalized, normalized)


def prepare_vendor_bills(rows, request):
    institution = request.institution
    routes_through_requisitions = bool(
        getattr(institution, "should_vendor_payments_go_through_requisitions", False)
    )
    cash_accounts = _CashAccountDirectory(institution)
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
            if row_type not in VALID_TYPES:
                raise serializers.ValidationError(
                    "Type must be one of: inventory, service, other, other expense."
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
            row_amount = unit_price * quantity
            expense_account_value = data.get("expense_account")
            tax_value = data.get("tax")

            paid_portion = _paid_portion(
                payment_status, row_amount, data.get("amount_paid")
            )

            payment_account = None
            if payment_status != "unpaid":
                if routes_through_requisitions:
                    raise serializers.ValidationError(
                        "This institution pays vendors through requisitions, so "
                        "payments cannot be recorded from a bulk upload. Mark the "
                        "rows Unpaid and pay the bill from its page."
                    )
                cash_value = data.get("cash_account")
                if not cash_value:
                    raise serializers.ValidationError(
                        "Cash Account is required for 'paid' and 'partially paid' rows."
                    )
                payment_account = cash_accounts.resolve(cash_value)
                _ensure_base_currency_payment(institution, vendor, payment_account)

            if row_type in {"inventory", "service"}:
                if expense_account_value or tax_value:
                    raise serializers.ValidationError(
                        "Expense account and tax can only be set for 'other' and "
                        "'other expense' rows. Inventory and service rows use the "
                        "tax configured on the item."
                    )
                item = _resolve_item(institution, data.get("item"))
                unit_of_measure = _resolve_uom(item, data.get("uom"))
                line = {
                    "line_item": str(item.base_uuid),
                    "unit_of_measure": str(unit_of_measure.base_uuid),
                    "quantity": quantity,
                    "unit_price": str(unit_price),
                }
                line_bucket = "inventory_line_items"
            elif row_type == "other":
                if expense_account_value:
                    raise serializers.ValidationError(
                        "Expense account can only be set for 'other expense' rows."
                    )
                line = {
                    "line_item": str(data.get("item") or "").strip(),
                    "unit_of_measure": str(data.get("uom") or "").strip(),
                    "quantity": quantity,
                    "unit_price": str(unit_price),
                    "applicable_taxes": _build_taxes(institution, tax_value),
                }
                line_bucket = "other_line_items"
            else:
                expense_account = _resolve(
                    Account.objects.active().filter(institution=institution),
                    expense_account_value,
                    "account_name",
                    "account",
                )
                line = {
                    "expense_name": str(data.get("item") or "").strip(),
                    "amount": str(row_amount),
                    "applicable_taxes": _build_taxes(institution, tax_value),
                }
                if expense_account is not None:
                    line["account_to_record_expense"] = str(expense_account.base_uuid)
                line_bucket = "other_expenses"

            header = {
                "vendor": str(vendor.base_uuid),
                "branch": str(branch.base_uuid) if branch else None,
                "payment_terms": (
                    str(payment_terms.base_uuid) if payment_terms else None
                ),
                "due_date": data.get("due_date"),
            }
            account_payload = (
                _cash_account_payload(payment_account) if payment_account else None
            )

            key = reference.casefold()
            if key not in groups:
                payload = {
                    "reference_code": reference,
                    "vendor": header["vendor"],
                    "inventory_line_items": [],
                    "other_line_items": [],
                    "other_expenses": [],
                }
                if header["branch"]:
                    payload["branch"] = header["branch"]
                if header["payment_terms"]:
                    payload["payment_terms"] = header["payment_terms"]

                groups[key] = {
                    "reference_code": reference,
                    "rows": [],
                    "payload": payload,
                    "header": header,
                    "cash_account": None,
                    "raw_total": Decimal("0"),
                    "paid_raw": Decimal("0"),
                }

            group = groups[key]
            differences = [
                HEADER_LABELS[field]
                for field, value in header.items()
                if group["header"][field] != value
            ]
            if differences:
                raise serializers.ValidationError(
                    f"Rows sharing the reference '{reference}' must have the same "
                    f"{', '.join(differences)}. This row differs from row "
                    f"{group['rows'][0]}."
                )

            if account_payload:
                if group["cash_account"] is None:
                    group["cash_account"] = account_payload
                elif group["cash_account"] != account_payload:
                    raise serializers.ValidationError(
                        f"Rows sharing the reference '{reference}' must be paid "
                        "from the same cash account."
                    )

            group["rows"].append(index)
            group["payload"][line_bucket].append(line)
            group["raw_total"] += row_amount
            group["paid_raw"] += paid_portion

        except Exception as exc:
            errors.append(f"Data row {index}: {_error_message(exc)}")

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

            header = group.pop("header")
            group["due_date"] = (
                header["due_date"].isoformat() if header["due_date"] else None
            )
            group["raw_total"] = str(group["raw_total"])
            group["paid_raw"] = str(group["paid_raw"])
        except Exception as exc:
            rows_label = ", ".join(str(number) for number in group["rows"])
            errors.append(f"Data rows {rows_label}: {_error_message(exc)}")

    if errors:
        raise validation_error(
            {
                "detail": "Vendor bill upload validation failed. Nothing was queued.",
                "errors": errors,
            }
        )

    return list(groups.values())