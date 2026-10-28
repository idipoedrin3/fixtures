import json

from django.db import transaction
from rest_framework import serializers

from accounts.models import Account
from institution.models import Branch
from requisitions.models import Expense, RequisitionBeneficiary
from requisitions.serializers import ExpenseSerializer, BulkExpenseUploadSerializer
from system.models import SystemCurrency
from system.services import FxRateService
from utilities.helpers import validation_error


def resolve_reference(queryset, value, name_field):
    if not value:
        return None
    matches = list(queryset.filter(reference_code__iexact=value)[:2])
    if not matches:
        matches = list(queryset.filter(**{f"{name_field}__iexact": value})[:2])
    if len(matches) != 1:
        raise serializers.ValidationError(
            f"'{value}' must identify exactly one active {queryset.model._meta.verbose_name}."
        )
    return str(matches[0].base_uuid)


def prepare_expenses(rows, request):
    institution = request.institution
    groups = {}
    errors = []
    for index, row in enumerate(rows, start=1):
        try:
            serializer = BulkExpenseUploadSerializer(data=row)
            serializer.is_valid(raise_exception=True)
            data = serializer.validated_data
            reference = data.get("reference_code") or ""
            key = ("reference", reference.casefold()) if reference else ("row", index)
            currency = SystemCurrency.objects.get(code__iexact=data["currency_code"])
            FxRateService.resolve_base_rate(institution=institution, currency=currency)
            branch = resolve_reference(
                Branch.objects.active().filter(institution=institution),
                data.get("branch"),
                "branch_name",
            )
            taxes = json.loads(data.get("applicable_taxes") or "[]")
            if not isinstance(taxes, list):
                raise serializers.ValidationError(
                    "applicable_taxes must be a JSON array."
                )
            line = {
                "amount": str(data["amount"]),
                "description": data.get("description") or "",
                "cash_account": resolve_reference(
                    Account.objects.active().filter(institution=institution),
                    data["cash_account"],
                    "account_name",
                ),
                "expense_account": resolve_reference(
                    Account.objects.active().filter(institution=institution),
                    data.get("expense_account"),
                    "account_name",
                ),
                "payee": resolve_reference(
                    RequisitionBeneficiary.objects.active().filter(
                        institution=institution
                    ),
                    data.get("payee"),
                    "name",
                ),
                "applicable_taxes": taxes,
            }
            header = {
                "expense_date": data["date"].isoformat(),
                "branch": branch,
                "currency": currency.pk,
            }
            if key not in groups:
                groups[key] = {
                    "reference_code": reference,
                    "rows": [],
                    "payload": {**header, "line_items": []},
                }
            group = groups[key]
            if any(group["payload"][field] != value for field, value in header.items()):
                raise serializers.ValidationError(
                    "Rows sharing a reference must have the same date, branch, and currency."
                )
            group["rows"].append(index)
            group["payload"]["line_items"].append(line)
        except Exception as exc:
            errors.append({"data_row": index, "error": str(exc)})
    for group in groups.values():
        try:
            reference = group["reference_code"]
            if (
                reference
                and Expense.objects.filter(
                    institution=institution, reference_code__iexact=reference
                ).exists()
            ):
                raise serializers.ValidationError(
                    f"Expense reference '{reference}' already exists."
                )
            with transaction.atomic():
                serializer = ExpenseSerializer(
                    data=group["payload"], context={"request": request}
                )
                serializer.is_valid(raise_exception=True)
                transaction.set_rollback(True)
        except Exception as exc:
            errors.append({"data_rows": group["rows"], "error": str(exc)})
    if errors:
        raise validation_error(
            {
                "detail": "Expense upload validation failed. Nothing was queued.",
                "errors": errors,
            }
        )
    return list(groups.values())
