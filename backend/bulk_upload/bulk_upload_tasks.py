from decimal import Decimal
from uuid import UUID
from celery import shared_task
from django.conf import settings
from django.contrib.contenttypes.models import ContentType
from django.db import transaction
from django.db.models import Exists, OuterRef, Q
from utilities.helpers import normalize_url
from fixed_assets.models import AssetCategory, FixedAsset
from institution.models import Institution
from accounts.models import Account

CHUNK_SIZE = getattr(settings, "BULK_UPLOAD_CHUNK_SIZE", 50)


def _chunked(lst, n):
    for i in range(0, len(lst), n):
        yield lst[i : i + n]


def _coerce_decimal(value, default=Decimal("0.00")) -> Decimal:
    if value is None or value == "":
        return default
    try:
        return Decimal(str(value))
    except Exception:
        return default


def _resolve_currency(currency_code: str | None):

    if not currency_code:
        return None
    from system.models import SystemCurrency

    return SystemCurrency.objects.filter(code__iexact=currency_code.strip()).first()


def _maybe_create_foreign_exchange(
    instance, opening_balance: Decimal, institution, row: dict
):
    from system.models import ForeignExchange

    target_currency = instance.currency
    if not target_currency:
        return

    institution_base_currency = institution.currency
    if target_currency == institution_base_currency:
        return

    if opening_balance == Decimal("0.00"):
        return

    institution_target_currency = institution.institution_supported_currencies.filter(
        currency=target_currency
    ).first()
    if not institution_target_currency:
        return

    raw_rate = row.get("foreign_exchange_rate")
    provided_rate = _coerce_decimal(raw_rate) if raw_rate else Decimal("0")
    rate_to_use = (
        provided_rate
        if provided_rate > Decimal("0")
        else institution_target_currency.rate
    )

    ForeignExchange.objects.create(
        from_currency=target_currency,
        to_currency=institution_base_currency,
        rate=rate_to_use,
        description=(
            f"{target_currency.code} → {institution_base_currency.code} "
            f"at rate {rate_to_use}"
        ),
        content_type=ContentType.objects.get_for_model(instance.__class__),
        object_id=instance.pk,
        content_object=instance,
    )


@shared_task(bind=True, name="bulk_upload.create_customers")
def bulk_create_customers(
    self, institution_id: int, rows: list[dict], requested_by_id: int
):
    from institution.models import Institution
    from customers.models import Customer
    from utilities.helpers import generate_unique_code

    try:
        institution = Institution.objects.get(pk=institution_id)
    except Institution.DoesNotExist:
        return {"status": "failed", "error": "Institution not found."}

    total = len(rows)
    created_pks = []
    errors = []
    customers_to_create = []
    customer_rows = {}
    seen_tins = set()

    for row_number, row in enumerate(rows, start=1):
        try:
            customer_name = str(row.get("customer_name") or "").strip()
            if not customer_name:
                raise ValueError("Customer name is required.")

            tin = str(row.get("tin") or "").strip() or None
            normalized_tin = tin.lower() if tin else None
            if normalized_tin and normalized_tin in seen_tins:
                raise ValueError(f"Duplicate customer TIN '{tin}' in upload.")
            if normalized_tin:
                seen_tins.add(normalized_tin)

            currency = (
                _resolve_currency(row.get("currency_code")) or institution.currency
            )
            opening_balance = _coerce_decimal(row.get("opening_balance"))
            customer = Customer(
                institution=institution,
                customer_name=customer_name,
                customer_type=row.get("customer_type", "individual"),
                credit_limit=_coerce_decimal(row.get("credit_limit")),
                gender=row.get("gender") or "OTHER",
                address=row.get("address") or None,
                phone_number=row.get("phone_number") or None,
                email=row.get("email") or None,
                tin=tin,
                currency=currency,
                opening_balance=opening_balance,
                opening_balance_received_date=(
                    row.get("opening_balance_received_date") or None
                ),
                reference_code=generate_unique_code(Customer.reference_prefix),
                created_by_id=requested_by_id,
                updated_by_id=requested_by_id,
                is_active=False,
                are_initial_transactions_processed=False,
            )
            customer.full_clean()

            customer_index = len(customers_to_create)
            customers_to_create.append(customer)
            customer_rows[customer_index] = {
                "row_number": row_number,
                "row": row,
                "opening_balance": opening_balance,
            }

        except Exception as exc:
            errors.append({"row": row_number, "data": row, "error": str(exc)})

    indexed_customers = list(enumerate(customers_to_create))

    for chunk in _chunked(indexed_customers, CHUNK_SIZE):
        chunk_customers = [customer for _, customer in chunk]

        try:
            with transaction.atomic():
                created_customers = Customer.objects.bulk_create(
                    chunk_customers,
                    batch_size=CHUNK_SIZE,
                )

                for (customer_index, _), customer in zip(chunk, created_customers):
                    metadata = customer_rows[customer_index]
                    _maybe_create_foreign_exchange(
                        customer,
                        metadata["opening_balance"],
                        institution,
                        metadata["row"],
                    )
                    customer.confirm_create()

                created_pks.extend(customer.pk for customer in created_customers)

        except Exception as exc:
            for customer_index, _ in chunk:
                metadata = customer_rows[customer_index]
                errors.append(
                    {
                        "row": metadata["row_number"],
                        "data": metadata["row"],
                        "error": str(exc),
                    }
                )

    return {
        "status": "completed",
        "total": total,
        "created": len(created_pks),
        "failed": len(errors),
        "created_ids": created_pks,
        "errors": errors,
    }


@shared_task(bind=True, name="bulk_upload.create_vendors")
def bulk_create_vendors(
    self, institution_id: int, rows: list[dict], requested_by_id: int
):
    from institution.models import Institution
    from vendors.models import Vendor
    from utilities.helpers import generate_unique_code

    try:
        institution = Institution.objects.get(pk=institution_id)
    except Institution.DoesNotExist:
        return {"status": "failed", "error": "Institution not found."}

    total = len(rows)
    created_pks = []
    errors = []
    vendors_to_create = []
    vendor_rows = {}
    seen_tins = set()

    for row_number, row in enumerate(rows, start=1):
        try:
            vendor_name = str(row.get("vendor_name") or "").strip()
            if not vendor_name:
                raise ValueError("Vendor name is required.")

            vendor_type = str(row.get("vendor_type") or "").strip()
            if not vendor_type:
                raise ValueError("Vendor type is required.")

            tax_identification_number = (
                str(row.get("tax_identification_number") or "").strip() or None
            )
            normalized_tin = (
                tax_identification_number.lower() if tax_identification_number else None
            )
            if normalized_tin and normalized_tin in seen_tins:
                raise ValueError(
                    "Duplicate vendor tax identification number "
                    f"'{tax_identification_number}' in upload."
                )
            if normalized_tin:
                seen_tins.add(normalized_tin)

            currency = (
                _resolve_currency(row.get("currency_code")) or institution.currency
            )
            opening_balance = _coerce_decimal(row.get("opening_balance"))
            website = row.get("website")
            vendor = Vendor(
                institution=institution,
                vendor_name=vendor_name,
                vendor_type=vendor_type,
                gender=row.get("gender") or "OTHER",
                email=row.get("email") or None,
                phone_number=row.get("phone_number") or None,
                address=row.get("address") or None,
                website=normalize_url(website) if website else None,
                tax_identification_number=tax_identification_number,
                currency=currency,
                opening_balance=opening_balance,
                opening_balance_received_date=(
                    row.get("opening_balance_received_date") or None
                ),
                reference_code=generate_unique_code(Vendor.reference_prefix),
                created_by_id=requested_by_id,
                updated_by_id=requested_by_id,
                is_active=False,
                are_initial_transactions_processed=False,
            )
            vendor.full_clean()

            vendor_index = len(vendors_to_create)
            vendors_to_create.append(vendor)
            vendor_rows[vendor_index] = {
                "row_number": row_number,
                "row": row,
                "opening_balance": opening_balance,
            }

        except Exception as exc:
            errors.append({"row": row_number, "data": row, "error": str(exc)})

    indexed_vendors = list(enumerate(vendors_to_create))

    for chunk in _chunked(indexed_vendors, CHUNK_SIZE):
        chunk_vendors = [vendor for _, vendor in chunk]

        try:
            with transaction.atomic():
                created_vendors = Vendor.objects.bulk_create(
                    chunk_vendors,
                    batch_size=CHUNK_SIZE,
                )

                for (vendor_index, _), vendor in zip(chunk, created_vendors):
                    metadata = vendor_rows[vendor_index]
                    _maybe_create_foreign_exchange(
                        vendor,
                        metadata["opening_balance"],
                        institution,
                        metadata["row"],
                    )
                    vendor.confirm_create()

                created_pks.extend(vendor.pk for vendor in created_vendors)

        except Exception as exc:
            for vendor_index, _ in chunk:
                metadata = vendor_rows[vendor_index]
                errors.append(
                    {
                        "row": metadata["row_number"],
                        "data": metadata["row"],
                        "error": str(exc),
                    }
                )

    return {
        "status": "completed",
        "total": total,
        "created": len(created_pks),
        "failed": len(errors),
        "created_ids": created_pks,
        "errors": errors,
    }


@shared_task(bind=True, name="bulk_upload.create_fixed_asset_categories")
def bulk_create_fixed_asset_categories(self, institution_id, rows, requested_by_id):
    try:
        institution = Institution.objects.get(pk=institution_id)
    except Institution.DoesNotExist:
        return {"status": "failed", "error": "Institution not found."}

    total = len(rows)
    created_pks = []
    errors = []

    def leaf_account_queryset():
        active_children = Account.objects.filter(
            parent_id=OuterRef("pk"),
            deleted_at__isnull=True,
        )
        return (
            Account.objects.filter(institution=institution, deleted_at__isnull=True)
            .select_related("account_role__role_group")
            .annotate(has_children=Exists(active_children))
            .filter(has_children=False)
        )

    def resolve_leaf_account(name, label, *, role_codes=None, group_type=None):
        if not name:
            raise ValueError(f"{label} is required.")

        account = (
            leaf_account_queryset()
            .filter(account_name__iexact=str(name).strip())
            .first()
        )
        if not account:
            raise ValueError(
                f"{label} must be an existing account with no child accounts."
            )

        role = account.account_role
        role_group = getattr(role, "role_group", None)
        if role_codes and getattr(role, "role_code", None) not in role_codes:
            raise ValueError(
                f"{label} must use one of these roles: {', '.join(role_codes)}."
            )
        if (
            group_type
            and getattr(role_group, "group_type_name", "").lower() != group_type
        ):
            raise ValueError(f"{label} must be a {group_type} account.")
        return account

    for chunk in _chunked(rows, CHUNK_SIZE):
        for idx, row in enumerate(chunk, start=len(created_pks) + 1):
            try:
                with transaction.atomic():

                    fixed_asset_account = resolve_leaf_account(
                        row.get("fixed_asset_account"),
                        "Fixed Asset Account",
                        role_codes=("fixed_asset_account",),
                    )
                    depreciation_expense_account = resolve_leaf_account(
                        row.get("depreciation_expense_account"),
                        "Depreciation Expense Account",
                        group_type="expense",
                    )
                    accumulated_depreciation_account = resolve_leaf_account(
                        row.get("accumulated_depreciation_account"),
                        "Accumulated Depreciation Account",
                        role_codes=("contra_asset_account",),
                    )

                    from fixed_assets.models import AssetClass

                    asset_class_name = row.get("asset_class", "").strip()
                    asset_class_obj = None
                    if asset_class_name:
                        asset_class_obj = AssetClass.objects.filter(
                            institution=institution,
                            asset_class_name__iexact=asset_class_name,
                        ).first()
                        if not asset_class_obj:
                            raise ValueError(
                                "Asset class must be selected from the institution asset classes."
                            )

                    category = AssetCategory.objects.create(
                        institution=institution,
                        reference_code=row["reference_code"],
                        category_name=row["category_name"],
                        asset_class=asset_class_obj,
                        asset_type=row.get("asset_type", "TANGIBLE"),
                        is_capitalizable=row.get("is_capitalizable", True),
                        is_depreciable=row.get("is_depreciable", True),
                        depreciation_frequency=row.get("depreciation_frequency"),
                        fixed_asset_account=fixed_asset_account,
                        depreciation_expense_account=depreciation_expense_account,
                        accumulated_depreciation_account=accumulated_depreciation_account,
                    )
                    created_pks.append(category.pk)

            except Exception as exc:
                errors.append(
                    {
                        "row": idx,
                        "data": row,
                        "error": str(exc),
                    }
                )

        return {
            "status": "completed",
            "total": total,
            "created": len(created_pks),
            "failed": len(errors),
            "created_ids": created_pks,
            "errors": errors,
        }


def _chunked(iterable, size):
    for i in range(0, len(iterable), size):
        yield iterable[i : i + size]


@shared_task(bind=True, name="bulk_upload.create_salespersons")
def bulk_create_salespersons(self, institution_id, rows, requested_by_id):
    from customers.models import SalesPerson
    from utilities.helpers import generate_unique_code

    try:
        institution = Institution.objects.get(pk=institution_id)
    except Institution.DoesNotExist:
        return {"status": "failed", "error": "Institution not found."}

    total = len(rows)
    created_pks = []
    errors = []
    salespersons_to_create = []
    salesperson_rows = {}

    for row_number, row in enumerate(rows, start=1):
        try:
            name = str(row.get("name") or "").strip()
            if not name:
                raise ValueError("Salesperson name is required.")

            salesperson = SalesPerson(
                institution=institution,
                name=name,
                email=row.get("email") or None,
                contact=row.get("contact") or None,
                address=row.get("address") or None,
                balance=_coerce_decimal(row.get("balance")),
                reference_code=generate_unique_code(SalesPerson.reference_prefix),
                created_by_id=requested_by_id,
                updated_by_id=requested_by_id,
                is_active=False,
            )
            salesperson.full_clean()

            salesperson_index = len(salespersons_to_create)
            salespersons_to_create.append(salesperson)
            salesperson_rows[salesperson_index] = {
                "row_number": row_number,
                "row": row,
            }

        except Exception as exc:
            errors.append({"row": row_number, "data": row, "error": str(exc)})

    indexed_salespersons = list(enumerate(salespersons_to_create))

    for chunk in _chunked(indexed_salespersons, CHUNK_SIZE):
        chunk_salespersons = [salesperson for _, salesperson in chunk]

        try:
            with transaction.atomic():
                created_salespersons = SalesPerson.objects.bulk_create(
                    chunk_salespersons,
                    batch_size=CHUNK_SIZE,
                )

                for salesperson in created_salespersons:
                    salesperson.confirm_create()

                created_pks.extend(
                    salesperson.pk for salesperson in created_salespersons
                )

        except Exception as exc:
            for salesperson_index, _ in chunk:
                metadata = salesperson_rows[salesperson_index]
                errors.append(
                    {
                        "row": metadata["row_number"],
                        "data": metadata["row"],
                        "error": str(exc),
                    }
                )

    return {
        "status": "completed",
        "total": total,
        "created": len(created_pks),
        "failed": len(errors),
        "created_ids": created_pks,
        "errors": errors,
    }


@shared_task(bind=True, name="bulk_upload.create_fixed_asset_items")
def bulk_create_fixed_asset_items(
    self,
    institution_id,
    rows,
    requested_by_id,
    should_notify=False,
    profile_institution_id=None,
):
    try:
        institution = Institution.objects.get(pk=institution_id)
    except Institution.DoesNotExist:
        return {"status": "failed", "error": "Institution not found."}

    total = len(rows)
    created_pks = []
    errors = []

    for chunk in _chunked(rows, CHUNK_SIZE):
        for idx, row in enumerate(chunk, start=len(created_pks) + 1):
            try:
                with transaction.atomic():

                    category_value = str(row.get("category") or "").strip()
                    if not category_value:
                        raise ValueError("category is required.")

                    category_code = None
                    if category_value.endswith(")") and "(" in category_value:
                        category_code = category_value.rsplit("(", 1)[1][:-1].strip()

                    asset_category = (
                        AssetCategory.objects.filter(
                            institution=institution,
                            deleted_at__isnull=True,
                            is_active=True,
                        )
                        .filter(
                            Q(category_name__iexact=category_value)
                            | Q(reference_code__iexact=category_value)
                            | Q(reference_code__iexact=category_code)
                        )
                        .order_by("id")
                        .first()
                    )
                    if not asset_category:
                        raise ValueError(
                            "category must be selected from existing active asset categories."
                        )

                    purchase_price = _coerce_decimal(row.get("purchase_price"))

                    asset = FixedAsset(
                        institution=institution,
                        reference_code=row["reference_code"],
                        asset_name=(row.get("asset_name") or "").strip(),
                        category=asset_category,
                        asset_addition_type=(
                            row.get("asset_addition_type") or "EXISTING_ASSET"
                        ),
                        purchase_date=row.get("purchase_date"),
                        purchase_price=purchase_price,
                        salvage_value=_coerce_decimal(row.get("salvage_value")),
                        useful_life=(
                            Decimal(str(row["useful_life"]))
                            if row.get("useful_life") not in (None, "")
                            else None
                        ),
                        created_by_id=requested_by_id,
                        are_initial_journal_entries_made=False,
                    )
                    asset.save()
                    asset.confirm_create()
                    created_pks.append(asset.pk)

                    if should_notify and profile_institution_id:
                        from system.tasks import notify_external_system_task

                        payload = {
                            "asset_name": asset.asset_name,
                            "serial_number": asset.reference_code,
                            "batch_number": asset.reference_code,
                            "external_base_uuid": str(asset.base_uuid),
                        }

                        transaction.on_commit(
                            lambda payload=payload: (
                                notify_external_system_task.delay(
                                    profile_institution_id=profile_institution_id,
                                    resource_type="fixed_assets",
                                    action="create",
                                    payload=payload,
                                )
                            )
                        )

            except Exception as exc:
                errors.append({"row": idx, "data": row, "error": str(exc)})

    return {
        "status": "completed",
        "total": total,
        "created": len(created_pks),
        "failed": len(errors),
        "created_ids": created_pks,
        "errors": errors,
    }


@shared_task(bind=True, name="bulk_upload.create_charts_of_accounts")
def bulk_create_charts_of_accounts(
    self, institution_id: int, rows: list[dict], requested_by_id: int
):
    from accounts.models import Account
    from system.models import SystemAccountRole, SystemCurrency
    from transactions.services import JournalLine, JournalPostingService
    from django.contrib.contenttypes.models import ContentType
    from utilities.helpers import get_fiscal_year
    import django.utils.timezone as tz

    try:
        institution = Institution.objects.get(pk=institution_id)
    except Institution.DoesNotExist:
        return {"status": "failed", "error": "Institution not found."}

    total = len(rows)
    created_pks = []
    errors = []

    for chunk in _chunked(rows, CHUNK_SIZE):
        for idx, row in enumerate(chunk, start=len(created_pks) + 1):
            try:
                with transaction.atomic():

                    role_val = row.get("account_role")
                    if isinstance(role_val, int):
                        role = SystemAccountRole.objects.get(pk=role_val)
                    elif isinstance(role_val, str):
                        role = SystemAccountRole.objects.get(role_name__iexact=role_val)
                    else:
                        role = role_val

                    parent = (
                        Account.objects.filter(pk=row["parent_account"]).first()
                        if row.get("parent_account")
                        else None
                    )

                    currency = (
                        SystemCurrency.objects.get(pk=row["currency_code"])
                        if row.get("currency_code")
                        else None
                    )

                    account = Account(
                        institution=institution,
                        account_name=row["account_name"].strip(),
                        account_role=role,
                        parent=parent,
                        currency=currency,
                        description=row.get("description") or "",
                    )
                    account.save()
                    account.confirm_create()

                    debit_amount = _coerce_decimal(
                        row.get("opening_balance_debit"), Decimal("0.00")
                    )
                    credit_amount = _coerce_decimal(
                        row.get("opening_balance_credit"), Decimal("0.00")
                    )

                    if debit_amount > 0 or credit_amount > 0:
                        from accounts.utils import get_or_create_default_account

                        ob_amount = debit_amount if debit_amount > 0 else credit_amount

                        opening_balance_account = get_or_create_default_account(
                            institution, "opening_balance_account"
                        )

                        today = tz.now().date()
                        fiscal_year = get_fiscal_year(
                            institution=institution, date=today
                        )

                        transaction_currency = currency or institution.currency
                        is_debit = debit_amount > 0

                        JournalPostingService.post(
                            fiscal_year=fiscal_year,
                            title=f"Opening balance – {account.account_name}",
                            description=(
                                f"Bulk-uploaded opening balance for account {account.account_name}"
                            ),
                            lines=[
                                JournalLine(
                                    account=(
                                        account if is_debit else opening_balance_account
                                    ),
                                    entry_type="debit",
                                    transaction_amount=ob_amount,
                                    transaction_currency=transaction_currency,
                                    description=(
                                        f"Opening balance debit for {account.account_name}"
                                        if is_debit
                                        else "Opening balance opening_balance_account debit"
                                    ),
                                ),
                                JournalLine(
                                    account=(
                                        opening_balance_account if is_debit else account
                                    ),
                                    entry_type="credit",
                                    transaction_amount=ob_amount,
                                    transaction_currency=transaction_currency,
                                    description=f"Opening balance credit for {account.account_name}",
                                ),
                            ],
                            content_type=ContentType.objects.get_for_model(Account),
                            object_id=account.pk,
                            transaction_date=today,
                        )

                    created_pks.append(account.pk)

            except Exception as exc:
                errors.append({"row": idx, "data": row, "error": str(exc)})

    return {
        "status": "completed",
        "total": total,
        "created": len(created_pks),
        "failed": len(errors),
        "created_ids": created_pks,
        "errors": errors,
    }


@shared_task(bind=True, name="bulk_upload.create_requisition_items")
def bulk_create_requisition_items(self, institution_id, rows, requested_by_id):
    from types import SimpleNamespace

    from audit.models import AuditLog
    from requisitions.models import RequisitionItem
    from requisitions.serializers import (
        RequisitionItemSerializer,
        RequisitionTypeLineItemSerializer,
    )
    from users.models import CustomUser
    from utilities.helpers import generate_unique_code

    try:
        institution = Institution.objects.get(pk=institution_id)
    except Institution.DoesNotExist:
        return {"status": "failed", "error": "Institution not found."}

    try:
        requested_by = CustomUser.objects.get(pk=requested_by_id)
    except CustomUser.DoesNotExist:
        return {"status": "failed", "error": "Requesting user not found."}

    total = len(rows)
    errors = []
    seen_names = set()
    items_to_create = []
    type_settings_by_index = {}
    task_request = SimpleNamespace(institution=institution, user=requested_by)

    for row_number, row in enumerate(rows, start=1):
        try:
            serializer = RequisitionItemSerializer(
                data=row,
                context={"request": task_request},
            )
            serializer.is_valid(raise_exception=True)
            validated_data = dict(serializer.validated_data)
            type_settings = validated_data.pop("requisition_type_settings", {})
            validated_data.pop("institution", None)

            name = str(validated_data.get("name") or "").strip()
            normalized_name = name.lower()
            if normalized_name in seen_names:
                raise ValueError(f"Duplicate requisition item '{name}' in upload.")

            seen_names.add(normalized_name)
            reference_code = validated_data.pop("reference_code", None)
            item_index = len(items_to_create)
            items_to_create.append(
                RequisitionItem(
                    institution=institution,
                    reference_code=(
                        reference_code
                        or generate_unique_code(RequisitionItem.reference_prefix)
                    ),
                    created_by=requested_by,
                    updated_by=requested_by,
                    **validated_data,
                )
            )
            if type_settings:
                type_settings_by_index[item_index] = type_settings

        except Exception as exc:
            errors.append({"row": row_number, "data": row, "error": str(exc)})

    with transaction.atomic():
        created_items = RequisitionItem.objects.bulk_create(
            items_to_create,
            batch_size=CHUNK_SIZE,
        )
        content_type = ContentType.objects.get_for_model(RequisitionItem)
        AuditLog.objects.bulk_create(
            [
                AuditLog(
                    content_type=content_type,
                    object_id=item.pk,
                    action="CREATE",
                    user=requested_by,
                    description=f"Created Requisition Item: {item.name}",
                )
                for item in created_items
            ],
            batch_size=CHUNK_SIZE,
        )

        for item_index, type_settings in type_settings_by_index.items():
            item = created_items[item_index]
            settings = dict(type_settings)
            requisition_type = settings.pop("requisition_type")
            beneficiaries = settings.pop("beneficiaries", [])
            taxes = settings.pop("taxes_that_apply", [])

            line_item_serializer = RequisitionTypeLineItemSerializer(
                data={
                    **settings,
                    "item": item.base_uuid,
                    "description": settings.get("description", item.description),
                    "unit_of_measure": settings.get(
                        "unit_of_measure", item.unit_of_measure
                    ),
                    "unit_price": settings.get(
                        "unit_price", item.unit_price or Decimal("0.00")
                    ),
                    "beneficiaries": [
                        {"beneficiary": entry["beneficiary"].base_uuid}
                        for entry in beneficiaries
                    ],
                    "taxes_that_apply": [
                        {
                            "tax": entry["tax"].base_uuid,
                            "withhold_tax_amount": entry.get(
                                "withhold_tax_amount", False
                            ),
                        }
                        for entry in taxes
                    ],
                },
                context={
                    "request": task_request,
                    "requisition_type": requisition_type,
                },
            )
            line_item_serializer.is_valid(raise_exception=True)
            line_item_serializer.save()

        for item in created_items:
            item.confirm_create()

    return {
        "status": "completed",
        "total": total,
        "created": len(created_items),
        "failed": len(errors),
        "created_ids": [item.pk for item in created_items],
        "errors": errors,
    }


@shared_task(bind=True, name="bulk_upload.create_inventory_units_of_measure")
def bulk_create_inventory_units_of_measure(
    self,
    institution_id,
    rows,
    requested_by_id,
):
    from audit.models import AuditLog
    from django.db.models.functions import Lower
    from items.models import ItemUnitOfMeasure
    from utilities.helpers import generate_unique_code

    try:
        institution = Institution.objects.get(pk=institution_id)
    except Institution.DoesNotExist:
        return {
            "status": "failed",
            "error": "Institution not found.",
        }

    total = len(rows)
    errors = []
    normalized_rows = []
    seen_names = set()

    for row_number, row in enumerate(rows, start=1):
        unit_name = str(row.get("unit_name") or "").strip()
        unit_abbreviation = str(row.get("unit_abbreviation") or "").strip()

        if not unit_name:
            errors.append(
                {"row": row_number, "data": row, "error": "Unit name is required."}
            )
            continue
        if not unit_abbreviation:
            errors.append(
                {
                    "row": row_number,
                    "data": row,
                    "error": "Unit abbreviation is required.",
                }
            )
            continue

        normalized_name = unit_name.lower()
        if normalized_name in seen_names:
            errors.append(
                {
                    "row": row_number,
                    "data": row,
                    "error": f"Duplicate unit of measure '{unit_name}' in upload.",
                }
            )
            continue

        seen_names.add(normalized_name)
        normalized_rows.append(
            {
                "row_number": row_number,
                "data": row,
                "normalized_name": normalized_name,
                "unit_name": unit_name,
                "unit_abbreviation": unit_abbreviation,
                "description": row.get("description") or None,
            }
        )

    existing_units = {
        unit.unit_name.lower(): unit
        for unit in ItemUnitOfMeasure.objects.filter(institution=institution)
        .annotate(normalized_name=Lower("unit_name"))
        .filter(normalized_name__in=[row["normalized_name"] for row in normalized_rows])
    }
    units_to_create = []
    units_to_restore = []

    for row in normalized_rows:
        existing_unit = existing_units.get(row["normalized_name"])
        if existing_unit and existing_unit.deleted_at is None:
            errors.append(
                {
                    "row": row["row_number"],
                    "data": row["data"],
                    "error": f"Unit of measure '{row['unit_name']}' already exists.",
                }
            )
            continue

        if existing_unit:
            existing_unit.deleted_at = None
            existing_unit.is_active = True
            existing_unit.approval_status = "under_creation"
            existing_unit.unit_abbreviation = row["unit_abbreviation"]
            existing_unit.description = row["description"]
            existing_unit.updated_by_id = requested_by_id
            units_to_restore.append(existing_unit)
            continue

        units_to_create.append(
            ItemUnitOfMeasure(
                institution=institution,
                unit_name=row["unit_name"],
                unit_abbreviation=row["unit_abbreviation"],
                description=row["description"],
                reference_code=generate_unique_code(ItemUnitOfMeasure.reference_prefix),
                created_by_id=requested_by_id,
                updated_by_id=requested_by_id,
            )
        )

    with transaction.atomic():
        created_units = ItemUnitOfMeasure.objects.bulk_create(
            units_to_create,
            batch_size=CHUNK_SIZE,
        )

        if units_to_restore:
            ItemUnitOfMeasure.objects.bulk_update(
                units_to_restore,
                [
                    "deleted_at",
                    "is_active",
                    "approval_status",
                    "unit_abbreviation",
                    "description",
                    "updated_by",
                ],
                batch_size=CHUNK_SIZE,
            )

        processed_units = [*created_units, *units_to_restore]
        content_type = ContentType.objects.get_for_model(ItemUnitOfMeasure)
        AuditLog.objects.bulk_create(
            [
                AuditLog(
                    content_type=content_type,
                    object_id=unit.pk,
                    action="CREATE",
                    user_id=requested_by_id,
                    description=f"Created ItemUnitOfMeasure: {unit.unit_name}",
                )
                for unit in created_units
            ]
            + [
                AuditLog(
                    content_type=content_type,
                    object_id=unit.pk,
                    action="RESTORE",
                    user_id=requested_by_id,
                    description=f"Restored ItemUnitOfMeasure: {unit.unit_name}",
                )
                for unit in units_to_restore
            ],
            batch_size=CHUNK_SIZE,
        )

        for unit in processed_units:
            unit.confirm_create()

    return {
        "status": "completed",
        "total": total,
        "created": len(created_units),
        "restored": len(units_to_restore),
        "failed": len(errors),
        "created_ids": [unit.pk for unit in [*created_units, *units_to_restore]],
        "errors": errors,
    }


@shared_task(bind=True, name="bulk_upload.create_inventory_item_categories")
def bulk_create_inventory_item_categories(
    self,
    institution_id,
    rows,
    requested_by_id,
):
    from audit.models import AuditLog
    from items.models import ItemCategory
    from accounts.models import Account
    from utilities.helpers import generate_unique_code

    try:
        institution = Institution.objects.get(pk=institution_id)
    except Institution.DoesNotExist:
        return {
            "status": "failed",
            "error": "Institution not found.",
        }

    total = len(rows)
    errors = []
    normalized_rows = []
    seen_names = set()

    def leaf_account_queryset():
        active_children = Account.objects.filter(
            parent_id=OuterRef("pk"),
            deleted_at__isnull=True,
        )

        return (
            Account.objects.filter(
                institution=institution,
                deleted_at__isnull=True,
            )
            .select_related("account_role__role_group")
            .annotate(has_children=Exists(active_children))
            .filter(has_children=False)
        )

    def resolve_account(
        value,
        label,
        *,
        group_type=None,
        required=False,
    ):
        value = str(value or "").strip()

        if not value:
            if required:
                raise ValueError(f"{label} is required.")
            return None

        lookup = Q(account_name__iexact=value) | Q(reference_code__iexact=value)
        try:
            account_uuid = UUID(value)
        except ValueError:
            account_uuid = None
        if account_uuid is not None:
            lookup |= Q(base_uuid=account_uuid)
        if value.isascii() and value.isdecimal():
            account_id = int(value)
            if 0 < account_id <= 9223372036854775807:
                lookup |= Q(pk=account_id)

        matches = list(leaf_account_queryset().filter(lookup)[:2])
        if len(matches) > 1:
            raise ValueError(
                f"{label} '{value}' matches multiple accounts. "
                "Use a unique reference code or UUID."
            )
        account = matches[0] if matches else None

        if not account:
            raise ValueError(
                f"{label} '{value}' must be an existing account "
                "with no child accounts."
            )

        if group_type:
            role = account.account_role
            role_group = getattr(role, "role_group", None)
            actual_group_type = getattr(
                role_group,
                "group_type_name",
                "",
            ).lower()

            if actual_group_type != group_type.lower():
                raise ValueError(f"{label} must be a {group_type} account.")

        return account

    for row_number, row in enumerate(rows, start=1):
        name = str(row.get("name") or "").strip()
        if not name:
            errors.append(
                {"row": row_number, "data": row, "error": "Category name is required."}
            )
            continue

        normalized_name = name.lower()
        if normalized_name in seen_names:
            errors.append(
                {
                    "row": row_number,
                    "data": row,
                    "error": f"Duplicate item category '{name}' in upload.",
                }
            )
            continue

        seen_names.add(normalized_name)
        normalized_rows.append(
            {
                "row_number": row_number,
                "data": row,
                "name": name,
                "normalized_name": normalized_name,
            }
        )

    existing_names = {
        name.lower()
        for name in ItemCategory.objects.filter(
            institution=institution,
            name__in=[row["name"] for row in normalized_rows],
        ).values_list("name", flat=True)
    }
    categories_to_create = []

    for row in normalized_rows:
        try:
            if row["normalized_name"] in existing_names:
                raise ValueError(f"Item category '{row['name']}' already exists.")

            data = row["data"]
            inventory_account = resolve_account(
                data.get("inventory_account"),
                "Inventory Account",
                group_type="asset",
            )
            revenue_account = resolve_account(
                data.get("revenue_account"),
                "Revenue Account",
                group_type="revenue",
            )
            expense_account = resolve_account(
                data.get("expense_account"),
                "Expense Account",
                group_type="expense",
            )

            categories_to_create.append(
                ItemCategory(
                    institution=institution,
                    name=row["name"],
                    description=data.get("description") or None,
                    inventory_account=inventory_account,
                    revenue_account=revenue_account,
                    expense_account=expense_account,
                    reference_code=generate_unique_code(ItemCategory.reference_prefix),
                    created_by_id=requested_by_id,
                    updated_by_id=requested_by_id,
                )
            )
        except Exception as exc:
            errors.append(
                {
                    "row": row["row_number"],
                    "data": row["data"],
                    "error": str(exc),
                }
            )

    with transaction.atomic():
        created_categories = ItemCategory.objects.bulk_create(
            categories_to_create,
            batch_size=CHUNK_SIZE,
        )
        content_type = ContentType.objects.get_for_model(ItemCategory)
        AuditLog.objects.bulk_create(
            [
                AuditLog(
                    content_type=content_type,
                    object_id=category.pk,
                    action="CREATE",
                    user_id=requested_by_id,
                    description=f"Created Item Category: {category.name}",
                )
                for category in created_categories
            ],
            batch_size=CHUNK_SIZE,
        )

        for category in created_categories:
            category.confirm_create()

    return {
        "status": "completed",
        "total": total,
        "created": len(created_categories),
        "failed": len(errors),
        "created_ids": [category.pk for category in created_categories],
        "errors": errors,
    }


@shared_task(bind=True, name="bulk_upload.create_expenses")
def bulk_create_expenses(
    self,
    institution_id,
    rows,
    requested_by_id,
    profile_institution_id=None,
    external_identity_id=None,
):
    from types import SimpleNamespace
    from django.contrib.auth import get_user_model
    from requisitions.models import Expense
    from requisitions.serializers import ExpenseSerializer
    from users.models import ProfileInstitution, ExternalIdentity

    institution = Institution.objects.get(pk=institution_id)
    user = get_user_model().objects.get(pk=requested_by_id)
    profile = ProfileInstitution.objects.filter(
        pk=profile_institution_id,
        institution=institution,
        profile__user=user,
        is_active=True,
    ).first()
    identity = ExternalIdentity.objects.filter(
        pk=external_identity_id,
        institution=institution,
        user=user,
        is_active=True,
    ).first()
    if profile_institution_id and profile is None:
        raise ValueError("The requesting institution profile is no longer active.")
    if external_identity_id and identity is None:
        raise ValueError("The requesting external identity is no longer active.")
    request = SimpleNamespace(
        institution=institution,
        user=user,
        profile_institution=profile,
        external_identity=identity,
    )
    created_ids = []
    errors = []
    for group in rows:
        try:
            with transaction.atomic():
                Institution.objects.select_for_update().get(pk=institution_id)
                reference = group["reference_code"]
                if (
                    reference
                    and Expense.objects.filter(
                        institution=institution, reference_code__iexact=reference
                    ).exists()
                ):
                    raise ValueError(f"Expense reference '{reference}' already exists.")
                serializer = ExpenseSerializer(
                    data=group["payload"], context={"request": request}
                )
                serializer.is_valid(raise_exception=True)
                expense = serializer.save(
                    **({"reference_code": reference} if reference else {})
                )
                expense.confirm_create(
                    profile_institution=profile, external_identity=identity
                )
            created_ids.append(expense.pk)
        except Exception as exc:
            errors.append(
                {
                    "data_rows": group["rows"],
                    "reference_code": group["reference_code"],
                    "error": str(exc),
                }
            )
    return {
        "status": "completed",
        "total": len(rows),
        "created": len(created_ids),
        "failed": len(errors),
        "created_ids": created_ids,
        "errors": errors,
    }
