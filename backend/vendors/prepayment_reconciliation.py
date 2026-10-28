from decimal import Decimal

from django.db import transaction
from django.contrib.contenttypes.models import ContentType
from django.utils import timezone

from accounts.utils import get_or_create_default_account
from system.services import FxRateService
from transactions.services import JournalLine, JournalPostingService
from utilities.helpers import get_fiscal_year
from utilities.helpers import validation_error
from vendors.models import (
    Vendor,
    VendorPayment,
    VendorBill,
    PrepaymentAllocation,
    VendorOutstandingBalanceAdjustment,
)


def _get_settlement_currency(prepayment):
    currency, _ = prepayment.determine_settlement_rate_currency_used()
    return currency


def _currencies_match(prepayment, bill):
    prepayment_currency = _get_settlement_currency(prepayment)
    bill_currency, _ = bill.determine_rate_currency_used()

    return (
        prepayment_currency is not None
        and bill_currency is not None
        and prepayment_currency.pk == bill_currency.pk
    )


def _post_allocation_journal(
    *,
    prepayment,
    bill,
    vendor,
    amount,
    allocation,
):
    institution = prepayment.institution
    settlement_currency, prepayment_rate = (
        prepayment.determine_settlement_rate_currency_used()
    )
    bill_currency, bill_rate = bill.determine_rate_currency_used()

    prepaid_account_currency = (
        None if settlement_currency == institution.currency else settlement_currency
    )
    payable_account_currency = (
        None if bill_currency == institution.currency else bill_currency
    )

    prepaid_account = get_or_create_default_account(
        institution,
        "prepaid_account",
        prepaid_account_currency,
    )
    payable_account = vendor.default_account_payable or get_or_create_default_account(
        institution,
        "payable_account",
        payable_account_currency,
    )

    prepaid_base_amount = FxRateService.translate(amount, prepayment_rate)
    payable_base_amount = FxRateService.translate(amount, bill_rate)

    journal_lines = [
        JournalLine(
            account=payable_account,
            entry_type="debit",
            transaction_amount=amount,
            transaction_currency=bill_currency,
            exchange_rate=bill_rate,
            description=f"Accounts payable reduced for bill {bill.reference_code}",
        ),
        JournalLine(
            account=prepaid_account,
            entry_type="credit",
            transaction_amount=amount,
            transaction_currency=settlement_currency,
            exchange_rate=prepayment_rate,
            description=f"Vendor prepayment {prepayment.reference_code} released",
        ),
    ]

    realized_difference = payable_base_amount - prepaid_base_amount

    if realized_difference > Decimal("0"):
        journal_lines.append(
            JournalLine(
                account=get_or_create_default_account(
                    institution,
                    "fx_gain_loss_account",
                ),
                entry_type="credit",
                transaction_amount=realized_difference,
                transaction_currency=institution.currency,
                exchange_rate=Decimal("1"),
                description=(
                    f"Realized foreign-exchange gain on allocation {allocation.pk}"
                ),
            )
        )
    elif realized_difference < Decimal("0"):
        journal_lines.append(
            JournalLine(
                account=get_or_create_default_account(
                    institution,
                    "fx_gain_loss_account",
                ),
                entry_type="debit",
                transaction_amount=abs(realized_difference),
                transaction_currency=institution.currency,
                exchange_rate=Decimal("1"),
                description=(
                    f"Realized foreign-exchange loss on allocation {allocation.pk}"
                ),
            )
        )

    allocation_date = timezone.localdate()
    transaction_record, _ = JournalPostingService.post(
        fiscal_year=get_fiscal_year(institution, allocation_date),
        title=(
            f"Prepayment {prepayment.reference_code} applied to "
            f"bill {bill.reference_code}"
        ),
        description=(
            f"Apply vendor prepayment {prepayment.reference_code} to "
            f"bill {bill.reference_code}"
        ),
        transaction_date=allocation_date,
        lines=journal_lines,
        branch=prepayment.branch or bill.branch,
        content_type=ContentType.objects.get_for_model(
            PrepaymentAllocation,
            for_concrete_model=False,
        ),
        object_id=allocation.pk,
        source=None,
    )
    return transaction_record


def _verify_allocation_state(*, prepayment, bill, vendor):
    prepayment.refresh_from_db(
        fields=[
            "settlement_amount",
            "amount_reconciled",
            "remaining_balance",
        ]
    )
    bill.refresh_from_db(fields=["balance_due"])
    vendor.refresh_from_db(fields=["deposit_balance", "outstanding_payables"])

    expected_total = Decimal(str(prepayment.settlement_amount or prepayment.amount))
    actual_total = Decimal(str(prepayment.amount_reconciled)) + Decimal(
        str(prepayment.remaining_balance)
    )

    if actual_total != expected_total:
        raise validation_error(
            f"Prepayment {prepayment.reference_code} has inconsistent "
            "reconciled and remaining amounts."
        )

    if prepayment.remaining_balance < Decimal("0"):
        raise validation_error(
            "Vendor prepayment remaining balance cannot be negative."
        )

    if bill.balance_due < Decimal("0"):
        raise validation_error("Vendor bill balance due cannot be negative.")

    if vendor.deposit_balance < Decimal("0"):
        raise validation_error("Vendor deposit balance cannot be negative.")


@transaction.atomic
def reconcile_prepayments(
    prepayment_uuids: list,
    bill_uuids: list,
    institution,
) -> list[PrepaymentAllocation]:
    prepayments_qs = VendorPayment.objects.active().filter(
        base_uuid__in=prepayment_uuids,
        institution=institution,
        bill__isnull=True,
        payment_status="PAID",
        deleted_at__isnull=True,
    )

    prepayments = list(
        prepayments_qs.select_for_update(of=("self",))
        .select_related(
            "vendor",
            "institution",
            "settlement_currency",
        )
        .order_by("created_at", "pk")
    )

    _assert_all_found(
        found_uuids=[str(p.base_uuid) for p in prepayments],
        requested_uuids=[str(u) for u in prepayment_uuids],
        label="prepayment",
    )

    prepayments_without_vendor = [p for p in prepayments if not p.vendor_id]
    if prepayments_without_vendor:
        refs = ", ".join(p.reference_code for p in prepayments_without_vendor)
        raise validation_error(
            f"The following prepayments are not attached to a vendor: {refs}"
        )

    vendor_ids = {p.vendor_id for p in prepayments}
    if len(vendor_ids) > 1:
        raise validation_error(
            "All prepayments must belong to the same vendor. "
            "Multiple vendors were found across the provided prepayment UUIDs."
        )

    vendor = prepayments[0].vendor

    invalid_prepayments = [
        p for p in prepayments if p.remaining_balance <= Decimal("0")
    ]
    if invalid_prepayments:
        refs = ", ".join(p.reference_code for p in invalid_prepayments)
        raise validation_error(
            f"The following prepayments have no remaining balance and cannot be applied: {refs}"
        )

    bills = list(
        VendorBill.objects.select_for_update()
        .filter(
            base_uuid__in=bill_uuids,
            institution=institution,
            status="approved",
            deleted_at__isnull=True,
            payment_status__in=["unpaid", "partially_paid"],
        )
        .select_related(
            "vendor",
            "purchase_order__vendor",
            "currency",
        )
        .order_by("created_at", "pk")
    )

    _assert_all_found(
        found_uuids=[str(b.base_uuid) for b in bills],
        requested_uuids=[str(u) for u in bill_uuids],
        label="bill",
    )

    wrong_vendor_bills = [b for b in bills if b.get_bill_vendor() != vendor]
    if wrong_vendor_bills:
        refs = ", ".join(b.reference_code for b in wrong_vendor_bills)
        raise validation_error(
            f"The following bills do not belong to vendor {vendor.vendor_name}: {refs}"
        )

    invalid_bills = [b for b in bills if b.balance_due <= Decimal("0")]
    if invalid_bills:
        refs = ", ".join(b.reference_code for b in invalid_bills)
        raise validation_error(
            f"The following bills have no outstanding balance: {refs}"
        )

    currency_mismatches = [
        (prepayment, bill)
        for prepayment in prepayments
        for bill in bills
        if not _currencies_match(prepayment, bill)
    ]
    if currency_mismatches:
        pairs = ", ".join(
            f"{prepayment.reference_code} → {bill.reference_code}"
            for prepayment, bill in currency_mismatches
        )
        raise validation_error(
            "A vendor prepayment can only be allocated to a bill in the "
            f"same settlement currency. Invalid pairs: {pairs}"
        )

    created_allocations: list[PrepaymentAllocation] = []

    for bill in bills:
        if Decimal(str(bill.balance_due)) <= Decimal("0"):
            continue

        for prepayment in prepayments:
            prepayment.refresh_from_db(
                fields=["remaining_balance", "amount_reconciled"]
            )
            bill.refresh_from_db(fields=["balance_due"])
            vendor.refresh_from_db(fields=["deposit_balance", "outstanding_payables"])

            remaining_balance = Decimal(str(prepayment.remaining_balance))
            balance_due = Decimal(str(bill.balance_due))

            if remaining_balance <= Decimal("0"):
                continue

            if balance_due <= Decimal("0"):
                break

            amount_to_apply = min(remaining_balance, balance_due)

            if Decimal(str(vendor.deposit_balance)) < amount_to_apply:
                raise validation_error(
                    f"Vendor deposit balance is insufficient to allocate "
                    f"prepayment {prepayment.reference_code}."
                )

            allocation = (
                PrepaymentAllocation.objects.select_for_update()
                .filter(
                    prepayment=prepayment,
                    bill=bill,
                    deleted_at__isnull=True,
                )
                .first()
            )

            if allocation is None:
                allocation = PrepaymentAllocation.objects.create(
                    prepayment=prepayment,
                    bill=bill,
                    amount_applied=amount_to_apply,
                )
            else:
                allocation.amount_applied = (
                    Decimal(str(allocation.amount_applied)) + amount_to_apply
                )
                allocation.save(update_fields=["amount_applied"])

            VendorPayment.objects.filter(pk=prepayment.pk).update(
                amount_reconciled=(
                    Decimal(str(prepayment.amount_reconciled)) + amount_to_apply
                ),
                remaining_balance=remaining_balance - amount_to_apply,
            )

            new_bill_balance = balance_due - amount_to_apply
            VendorBill.objects.filter(pk=bill.pk).update(balance_due=new_bill_balance)
            bill.balance_due = new_bill_balance
            bill._sync_payment_status()

            deposit_before = Decimal(str(vendor.deposit_balance))
            deposit_after = deposit_before - amount_to_apply
            payables_before = Decimal(str(vendor.outstanding_payables))
            payables_after = payables_before - amount_to_apply

            Vendor.objects.filter(pk=vendor.pk).update(
                deposit_balance=deposit_after,
                outstanding_payables=payables_after,
            )

            adjustment_content_type = ContentType.objects.get_for_model(
                PrepaymentAllocation,
                for_concrete_model=False,
            )

            VendorOutstandingBalanceAdjustment.objects.create(
                vendor=vendor,
                balance_adjusted="DEPOSIT_BALANCE",
                amount=-amount_to_apply,
                amount_before_adjustment=deposit_before,
                amount_after_adjustment=deposit_after,
                reason=(
                    f"Prepayment {prepayment.reference_code} allocated "
                    f"to bill {bill.reference_code}"
                ),
                content_type=adjustment_content_type,
                object_id=allocation.pk,
            )
            VendorOutstandingBalanceAdjustment.objects.create(
                vendor=vendor,
                balance_adjusted="OUTSTANDING_PAYABLE_BALANCE",
                amount=-amount_to_apply,
                amount_before_adjustment=payables_before,
                amount_after_adjustment=payables_after,
                reason=(
                    f"Bill {bill.reference_code} settled via "
                    f"prepayment {prepayment.reference_code}"
                ),
                content_type=adjustment_content_type,
                object_id=allocation.pk,
            )

            _post_allocation_journal(
                prepayment=prepayment,
                bill=bill,
                vendor=vendor,
                amount=amount_to_apply,
                allocation=allocation,
            )

            created_allocations.append(allocation)

            _verify_allocation_state(
                prepayment=prepayment,
                bill=bill,
                vendor=vendor,
            )

    return created_allocations


def _assert_all_found(found_uuids: list[str], requested_uuids: list[str], label: str):
    missing = set(requested_uuids) - set(found_uuids)
    if missing:
        raise validation_error(
            f"The following {label} UUIDs were not found or are not eligible "
            f"for reconciliation: {', '.join(missing)}"
        )
