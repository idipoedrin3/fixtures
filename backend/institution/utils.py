import string
import secrets
from django.utils.text import camel_case_to_spaces
from django.db import transaction
from utilities.helpers import get_institution
from items.models import (
    BranchInventoryItemUnitOfMeasure,
    InventoryItem,
    BranchInventoryItem,
    InventoryItemUnitOfMeasure,
)
from .models import Branch, BranchSupportedCurrency
from django.db.models import Q
import json
from rest_framework.parsers import MultiPartParser
from collections import defaultdict
from datetime import datetime


class InstitutionCreationParser(MultiPartParser):
    json_fields = {"supported_currencies"}

    def parse(self, stream, media_type=None, parser_context=None):
        data_and_files = super().parse(stream, media_type, parser_context)
        data = data_and_files.data.copy()

        for field in self.json_fields:
            if field in data:
                value = data.get(field)
                if isinstance(value, str):
                    value = json.loads(value)
                # Flatten if it's [[...]]
                if (
                    isinstance(value, list)
                    and len(value) == 1
                    and isinstance(value[0], list)
                ):
                    value = value[0]
                data[field] = value

        data_and_files.data = data
        return data_and_files


def parse_kyc_documents(request_data, request_files):
    kyc_docs = defaultdict(dict)

    for key, value in request_data.items():
        if key.startswith("kyc_documents["):
            index = int(key.split("[")[1].split("]")[0])
            field = key.split("[")[2].split("]")[0]

            if isinstance(value, list):
                val = value[0]
            else:
                val = value

            if isinstance(val, str):
                val = val.strip()

            if field in ("issue_date", "expiry_date") and val:
                try:
                    val = datetime.strptime(val, "%Y-%m-%d").date()
                except ValueError:
                    pass

            kyc_docs[index][field] = val

    for key, file in request_files.items():
        if key.startswith("kyc_documents["):
            index = int(key.split("[")[1].split("]")[0])
            kyc_docs[index]["file"] = file

    return list(kyc_docs.values())


def generate_compliant_password(length=12):
    if length < 8:
        raise ValueError("Password must be at least 8 characters long.")

    lower = secrets.choice(string.ascii_lowercase)
    upper = secrets.choice(string.ascii_uppercase)
    digit = secrets.choice(string.digits)
    special = secrets.choice("!@#$%^&*()-_=+[]{};:,.<>?")

    all_chars = string.ascii_letters + string.digits + "!@#$%^&*()-_=+[]{};:,.<>?"
    remaining = [secrets.choice(all_chars) for _ in range(length - 4)]

    password_list = [lower, upper, digit, special] + remaining
    secrets.SystemRandom().shuffle(password_list)

    return "".join(password_list)


_model_name_cache = {}


def humanize_model_name(content_type):
    if not content_type:
        return ""

    model = content_type.model_class()
    if not model:
        return content_type.model.title()

    key = f"{model._meta.app_label}.{model._meta.object_name}"
    if key in _model_name_cache:
        return _model_name_cache[key]

    raw = model._meta.object_name
    pretty = camel_case_to_spaces(raw).title()
    _model_name_cache[key] = pretty
    return pretty


def create_branch_currency_as_branch_supported_currency(branch: Branch):
    if branch.currency is None:
        return

    BranchSupportedCurrency.objects.create(
        branch=branch,
        currency=branch.currency,
        rate=1,
    )


def give_branch_all_inventory_from_institution(branch: Branch):
    institution = branch.institution

    institution_inventory = InventoryItem.objects.filter(
        Q(item_category__institution=institution) | Q(institution=institution)
    )

    existing_product_ids = set(
        BranchInventoryItem.objects.filter(branch=branch).values_list(
            "inventory_item_id", flat=True
        )
    )

    products_to_add = [
        product
        for product in institution_inventory
        if product.id not in existing_product_ids
    ]

    branch_items_to_create = [
        BranchInventoryItem(
            branch=branch,
            inventory_item=product,
        )
        for product in products_to_add
    ]

    if not branch_items_to_create:
        return

    with transaction.atomic():
        created_branch_items = BranchInventoryItem.objects.bulk_create(
            branch_items_to_create, batch_size=1000
        )

        branch_units_to_create = []

        inventory_units = InventoryItemUnitOfMeasure.objects.filter(
            inventory_item__in=products_to_add,
            deleted_at__isnull=True,
        )

        units_by_item = {}

        for unit in inventory_units:
            units_by_item.setdefault(unit.inventory_item_id, []).append(unit)

        for branch_item in created_branch_items:
            item_units = units_by_item.get(branch_item.inventory_item_id, [])
            for unit in item_units:
                branch_units_to_create.append(
                    BranchInventoryItemUnitOfMeasure(
                        branch_inventory_item=branch_item,
                        unit_of_measure=unit.unit_of_measure,
                        conversion_factor=unit.conversion_factor,
                        selling_price=unit.selling_price,
                        is_base_unit_of_measure=unit.is_base_unit_of_measure,
                    )
                )

        if branch_units_to_create:
            BranchInventoryItemUnitOfMeasure.objects.bulk_create(
                branch_units_to_create,
                batch_size=1000,
            )


# -------------------------------------------------------------------------------------------------

SUPPORTED_CURRENCY_MODELS = {
    "customer": "customers.Customer",
    "quotation": "customers.Quotation",
    "customer_purchase_order": "customers.CustomerPurchaseOrder",
    "invoice": "customers.Invoice",
    "vendor_purchase_order": "vendors.VendorPurchaseOrder",
    "vendors": "vendors.Vendor",
}

# -------------------------------------------------------------------------------------------------

from django.apps import apps
from rest_framework import serializers
from rest_framework.exceptions import ValidationError
from decimal import Decimal
from system.models import SystemCurrency
from system.serializers import ExchangeRateInputSerializer


def get_model_from_name(model_name: str):
    if model_name not in SUPPORTED_CURRENCY_MODELS:
        raise ValidationError(f"Model '{model_name}' is not supported.")
    app_label, model_class = SUPPORTED_CURRENCY_MODELS[model_name].split(".")
    return apps.get_model(app_label, model_class)


class CurrencyConversionSerializer(serializers.Serializer):
    model_name = serializers.ChoiceField(
        choices=[(k, k) for k in SUPPORTED_CURRENCY_MODELS.keys()],
        required=False,
        allow_null=True,
    )
    object_uuid = serializers.UUIDField(required=False, allow_null=True)
    amount = serializers.DecimalField(max_digits=50, decimal_places=20)
    override_rate = serializers.DecimalField(
        max_digits=50, decimal_places=20, required=False, allow_null=True
    )
    exchange_rate = ExchangeRateInputSerializer(
        required=False,
        allow_null=True,
    )
    currency = serializers.PrimaryKeyRelatedField(
        queryset=SystemCurrency.objects.all(), required=False, allow_null=True
    )
    target_currency = serializers.PrimaryKeyRelatedField(
        queryset=SystemCurrency.objects.all(),
        required=False,
        allow_null=True,
    )

    def validate(self, attrs):
        if (
            attrs.get("override_rate") is not None
            and attrs.get("exchange_rate") is not None
        ):
            raise validation_error(
                "Provide either 'exchange_rate' or the legacy 'override_rate', not both."
            )

        return attrs


def convert_to_object_currency(
    *,
    institution,
    obj=None,
    amount: Decimal,
    override_rate: Decimal = None,
    currency=None,
):
    institution_currency = institution.currency

    if obj and currency:
        raise ValidationError("Cannot specify both obj and currency.")

    target_currency = None
    continue_converting = False

    if obj:
        target_currency, continue_converting = obj.get_currency()
    elif currency:
        target_currency = currency
        continue_converting = True
    else:
        raise ValidationError("Either obj or currency must be specified.")

    if not institution_currency:
        raise ValidationError("Institution base currency is not configured.")

    if not continue_converting:
        return {
            "converted_amount": amount,
            "exchange_rate": Decimal("1.000000"),
            "from_currency": institution_currency.code,
            "to_currency": target_currency.code,
        }

    if not target_currency or (institution_currency == target_currency):
        return {
            "converted_amount": amount,
            "exchange_rate": Decimal("1.000000"),
            "from_currency": institution_currency.code,
            "to_currency": (
                target_currency.code if target_currency else institution_currency.code
            ),
        }

    rate = (
        Decimal(override_rate)
        if (override_rate is not None and override_rate > Decimal("0.000001"))
        else None
    )

    if rate is None:
        try:
            rate = (
                obj.get_institution()
                .institution_supported_currencies.get(currency=target_currency)
                .rate
            )
        except Exception:
            raise ValidationError(
                f"{target_currency.code} is not supported by this institution."
            )

    operation = (
        target_currency.institution_currencies.filter(institution=obj.get_institution())
        .first()
        .determine_operation(direction="from_base")
    )

    if operation == "multiply":
        converted_amount = (Decimal(amount) * Decimal(rate)).quantize(
            Decimal("0.000001")
        )
    elif operation == "divide":
        converted_amount = (Decimal(amount) / Decimal(rate)).quantize(
            Decimal("0.000001")
        )
    else:
        raise ValidationError("Invalid operation.")

    return {
        "converted_amount": converted_amount,
        "exchange_rate": Decimal(rate),
        "from_currency": institution_currency.code,
        "to_currency": (target_currency.code),
    }


def filter_queryset_by_branches(
    queryset,
    request,
    branch_lookup_field: str = "branch__base_uuid",
    additional_branch_filter=None,
):
    branch_uuids = request.query_params.get("branch_uuids") or request.query_params.get(
        "branch_base_uuid"
    )

    institution = get_institution(request)

    if branch_uuids:
        uuids_list = [uuid.strip() for uuid in branch_uuids.split(",") if uuid.strip()]

        from .models import Branch

        valid_branch_uuids = set(
            Branch.objects.filter(
                base_uuid__in=uuids_list, institution=institution
            ).values_list("base_uuid", flat=True)
        )

        if not valid_branch_uuids:
            return queryset

        branch_filter = Q(**{f"{branch_lookup_field}__in": valid_branch_uuids})

        if additional_branch_filter is not None:
            branch_filter |= additional_branch_filter

        return queryset.filter(branch_filter).distinct()

    else:
        return queryset
