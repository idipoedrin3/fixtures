from __future__ import annotations

import logging
from dataclasses import dataclass, field
from datetime import date, datetime
from decimal import Decimal
from enum import Enum
from typing import Optional

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

ZERO = Decimal("0.00")
TWO_DP = Decimal("0.01")


class ActivityType(str, Enum):
    OPENING_BALANCE = "Opening Balance"  # we owe vendor (credit)
    OPENING_ADVANCE = "Opening Advance"  # vendor owes us (debit)
    VENDOR_BILL = "Vendor Bill"  # credit — increases what we owe
    BILL_PAYMENT = "Bill Payment"  # debit  — reduces what we owe
    ADVANCE_PAYMENT = "Advance Payment"  # debit  — prepayment, asset to us
    ADVANCE_APPLIED = "Advance Applied"  # informational only, no balance effect
    CREDIT_NOTE = "Vendor Credit Note"  # debit  — vendor reduces our liability
    DEBIT_NOTE = "Vendor Debit Note"  # credit — vendor increases our liability
    JOURNAL_ENTRY = "Journal Entry"


# ---------------------------------------------------------------------------
# Data classes  (identical structure to customer statement)
# ---------------------------------------------------------------------------


@dataclass
class StatementLine:
    """A single line on the vendor statement."""

    date: date
    activity_type: ActivityType
    reference: str
    description: str
    debit: Decimal  # reduces what we owe vendor
    credit: Decimal  # increases what we owe vendor
    running_balance: Decimal
    affects_balance: bool = True

    def as_dict(self) -> dict:
        return {
            "date": self.date.isoformat() if self.date else None,
            "activity_type": self.activity_type.value,
            "reference": self.reference,
            "description": self.description,
            "debit": _fmt(self.debit),
            "credit": _fmt(self.credit),
            "running_balance": _fmt(self.running_balance),
        }


@dataclass
class StatementSummary:
    opening_balance: Decimal
    total_debits: Decimal
    total_credits: Decimal
    closing_balance: Decimal
    line_count: int

    def as_dict(self) -> dict:
        return {
            "opening_balance": _fmt(self.opening_balance),
            "total_debits": _fmt(self.total_debits),
            "total_credits": _fmt(self.total_credits),
            "net_movement": _fmt(self.total_credits - self.total_debits),
            "closing_balance": _fmt(self.closing_balance),
            "line_count": self.line_count,
        }


@dataclass
class VendorStatement:
    vendor_id: int
    vendor_name: str
    currency_code: str
    statement_date: date
    start_date: Optional[date]
    end_date: Optional[date]
    lines: list[StatementLine] = field(default_factory=list)
    summary: Optional[StatementSummary] = None

    def as_dict(self) -> dict:
        return {
            "vendor": {
                "id": self.vendor_id,
                "name": self.vendor_name,
                "currency": self.currency_code,
            },
            "period": {
                "start_date": self.start_date.isoformat() if self.start_date else None,
                "end_date": self.end_date.isoformat() if self.end_date else None,
                "statement_date": self.statement_date.isoformat(),
            },
            "lines": [line.as_dict() for line in self.lines],
            "summary": self.summary.as_dict() if self.summary else None,
        }


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------


def _fmt(value: Decimal) -> str:
    return str(value.quantize(TWO_DP))


def _to_date(value) -> Optional[date]:
    if value is None:
        return None
    if isinstance(value, datetime):
        return value.date()
    return value


def _date_in_range(
    d: Optional[date],
    start: Optional[date],
    end: Optional[date],
) -> bool:
    if d is None:
        return True
    if start and d < start:
        return False
    if end and d > end:
        return False
    return True


# ---------------------------------------------------------------------------
# Raw-event fetchers
# ---------------------------------------------------------------------------


def _fetch_opening_balance_line(
    vendor,
) -> Optional[StatementLine]:
    """
    Opening balance from vendor.opening_balance field.

    Positive opening_balance → we owe vendor → credit side
    Negative opening_balance → vendor owes us (advance asset) → debit side

    The auto-created stub bill (are_initial_journal_entries_made=True, no line items)
    is excluded from the bill fetcher, so we rely solely on this field as the anchor.
    """
    ob = vendor.opening_balance
    if not ob or ob == ZERO:
        return None

    ob_date = _to_date(vendor.opening_balance_received_date) or date.today()

    if ob > ZERO:
        # We owe vendor → credit
        debit, credit = ZERO, ob
        activity_type = ActivityType.OPENING_BALANCE
        description = "Opening Balance – amount owed to vendor"
    else:
        # Vendor owes us → debit
        debit, credit = abs(ob), ZERO
        activity_type = ActivityType.OPENING_ADVANCE
        description = "Opening Advance – amount vendor owed us"

    # Running balance will be recomputed later; use ZERO as placeholder
    return StatementLine(
        date=ob_date,
        activity_type=activity_type,
        reference=vendor.reference_code,
        description=description,
        debit=debit,
        credit=credit,
        running_balance=ZERO,
    )


def _fetch_bill_lines(
    vendor,
    start_date: Optional[date],
    end_date: Optional[date],
) -> list[StatementLine]:
    from vendors.models import VendorBill

    qs = (
        VendorBill.objects.filter(
            status="approved",
            is_active=True,
            deleted_at__isnull=True,
        )
        .filter(models_q(vendor, "purchase_order__vendor") | models_q(vendor, "vendor"))
        .exclude(
            are_initial_journal_entries_made=True,
            line_items__isnull=True,
        )
        .select_related("purchase_order", "purchase_order__vendor", "vendor")
        .order_by("received_date", "created_at")
    )

    lines: list[StatementLine] = []

    for bill in qs:
        d = _to_date(bill.received_date)
        if not _date_in_range(d, start_date, end_date):
            continue

        amount = bill.total_amount.quantize(TWO_DP)
        bill_vendor = bill.get_bill_vendor()
        vendor_name = bill_vendor.vendor_name if bill_vendor else "Unknown Vendor"

        lines.append(
            StatementLine(
                date=d,
                activity_type=ActivityType.VENDOR_BILL,
                reference=bill.reference_code,
                description=(
                    f"Bill from {vendor_name}"
                    + (f" – {bill.description}" if bill.description else "")
                ),
                debit=ZERO,
                credit=amount,
                running_balance=ZERO,
            )
        )

    return lines


def _fetch_payment_lines(
    vendor,
    start_date: Optional[date],
    end_date: Optional[date],
) -> list[StatementLine]:
    from vendors.models import VendorPayment

    qs = (
        VendorPayment.objects.filter(
            payment_status="PAID",
            is_active=True,
            deleted_at__isnull=True,
        )
        .filter(
            models_q(vendor, "vendor")
            | models_q(vendor, "bill__vendor")
            | models_q(vendor, "bill__purchase_order__vendor")
        )
        .select_related("bill", "bill__purchase_order", "vendor")
        .order_by("payment_date", "created_at")
    )

    lines: list[StatementLine] = []

    for payment in qs:
        d = _to_date(payment.payment_date)
        if not _date_in_range(d, start_date, end_date):
            continue

        amount = Decimal(str(payment.settlement_amount or payment.amount)).quantize(
            TWO_DP
        )

        is_prepayment = payment.bill is None

        if is_prepayment:
            activity_type = ActivityType.ADVANCE_PAYMENT
            description = "Advance Payment to Vendor (Prepayment)"
            ref = payment.reference_code
        else:
            activity_type = ActivityType.BILL_PAYMENT
            description = f"Payment – {payment.bill.reference_code}"
            ref = payment.reference_code

        print("\n\n\nVendor Payment Date", d)
        lines.append(
            StatementLine(
                date=d,
                activity_type=activity_type,
                reference=ref,
                description=description,
                debit=amount,
                credit=ZERO,
                running_balance=ZERO,
            )
        )

    return lines


def _fetch_advance_applied_lines(
    vendor,
    start_date: Optional[date],
    end_date: Optional[date],
) -> list[StatementLine]:
    from vendors.models import PrepaymentAllocation

    qs = (
        PrepaymentAllocation.objects.filter(
            prepayment__is_active=True,
            prepayment__deleted_at__isnull=True,
        )
        .filter(
            models_q(vendor, "prepayment__vendor")
            | models_q(vendor, "prepayment__bill__vendor")
            | models_q(vendor, "prepayment__bill__purchase_order__vendor")
        )
        .select_related("prepayment", "bill")
        .order_by("created_at")
    )

    lines: list[StatementLine] = []

    for allocation in qs:
        d = _to_date(allocation.created_at)
        if not _date_in_range(d, start_date, end_date):
            continue

        lines.append(
            StatementLine(
                date=d,
                activity_type=ActivityType.ADVANCE_APPLIED,
                reference=(
                    allocation.reference_code
                    if hasattr(allocation, "reference_code")
                    else f"ALLOC-{allocation.pk}"
                ),
                description=(
                    f"Advance {allocation.prepayment.reference_code} "
                    f"applied to {allocation.bill.reference_code} "
                    f"({_fmt(allocation.amount_applied)})"
                ),
                debit=ZERO,
                credit=ZERO,
                running_balance=ZERO,
                affects_balance=False,
            )
        )

    return lines


def _fetch_credit_note_lines(
    vendor,
    start_date: Optional[date],
    end_date: Optional[date],
) -> list[StatementLine]:
    from customers.models import CreditDebitNote

    qs = (
        CreditDebitNote.objects.filter(
            bill__is_active=True,
            type="DEBIT",
            falls_under="PURCHASE",
            status="APPROVED",
            is_active=True,
            deleted_at__isnull=True,
        )
        .filter(
            models_q(vendor, "bill__vendor")
            | models_q(vendor, "bill__purchase_order__vendor")
        )
        .select_related("bill", "bill__vendor", "bill__purchase_order__vendor")
        .order_by("issue_date", "created_at")
    )

    lines: list[StatementLine] = []

    for note in qs:
        d = _to_date(note.issue_date)
        if not _date_in_range(d, start_date, end_date):
            continue

        amount = note.amount.quantize(TWO_DP)

        lines.append(
            StatementLine(
                date=d,
                activity_type=ActivityType.CREDIT_NOTE,
                reference=note.reference_code,
                description=(
                    f"Vendor Credit Note"
                    + (f" – {note.bill.reference_code}" if note.bill else "")
                ),
                debit=amount,
                credit=ZERO,
                running_balance=ZERO,
            )
        )

    return lines


def _fetch_journal_entry_lines(
    vendor,
    start_date: Optional[date],
    end_date: Optional[date],
) -> list[StatementLine]:
    from django.contrib.contenttypes.models import ContentType
    from django.db.models import Q
    from requisitions.models import RequisitionPayment
    from transactions.models import TransactionEntry
    from vendors.models import VendorPayment

    represented_requisition_ids = (
        VendorPayment.objects.filter(
            payment_status="PAID",
            is_active=True,
            deleted_at__isnull=True,
            cash_requisition__isnull=False,
        )
        .filter(
            models_q(vendor, "vendor")
            | models_q(vendor, "bill__vendor")
            | models_q(vendor, "bill__purchase_order__vendor")
        )
        .values_list("cash_requisition_id", flat=True)
    )

    direct_requisition_payment_ids = (
        RequisitionPayment.objects.filter(
            is_active=True,
            deleted_at__isnull=True,
        )
        .exclude(
            requisition_id__in=represented_requisition_ids,
        )
        .values_list("pk", flat=True)
    )

    requisition_payment_content_type = ContentType.objects.get_for_model(
        RequisitionPayment
    )

    qs = (
        TransactionEntry.objects.filter(
            partner_uuid=vendor.base_uuid,
            is_active=True,
            deleted_at__isnull=True,
            transaction__is_active=True,
            transaction__deleted_at__isnull=True,
            transaction__transaction_status="posted",
            account__account_role__role_code__in=[
                "payable_account",
                "prepaid_account",
            ],
        )
        .filter(
            Q(transaction__is_originating_from_manual_entry=True)
            | Q(
                transaction__content_type=requisition_payment_content_type,
                transaction__object_id__in=direct_requisition_payment_ids,
            )
        )
        .select_related("transaction", "account", "account__account_role")
        .order_by("transaction__transaction_date", "created_at")
    )

    lines: list[StatementLine] = []

    for entry in qs:
        d = _to_date(entry.transaction.transaction_date)

        if not _date_in_range(d, start_date, end_date):
            continue

        if entry.entry_type == "debit":
            debit_amount = entry.entry_amount.quantize(TWO_DP)
            credit_amount = ZERO
        else:
            debit_amount = ZERO
            credit_amount = entry.entry_amount.quantize(TWO_DP)

        lines.append(
            StatementLine(
                date=d,
                activity_type=ActivityType.JOURNAL_ENTRY,
                reference=entry.reference_code,
                description=entry.description or "Journal Entry",
                debit=debit_amount,
                credit=credit_amount,
                running_balance=ZERO,
                affects_balance=True,
            )
        )

    return lines


def _sort_key(line: StatementLine):
    type_order = {
        ActivityType.OPENING_BALANCE: 0,
        ActivityType.OPENING_ADVANCE: 0,
        ActivityType.VENDOR_BILL: 1,
        ActivityType.ADVANCE_PAYMENT: 2,
        ActivityType.BILL_PAYMENT: 3,
        ActivityType.ADVANCE_APPLIED: 4,
        ActivityType.CREDIT_NOTE: 5,
        ActivityType.DEBIT_NOTE: 6,
        ActivityType.JOURNAL_ENTRY: 7,
    }
    d = line.date or date.min
    return (d, type_order.get(line.activity_type, 99))


def _recompute_running_balances(
    lines: list[StatementLine],
    opening_balance: Decimal,
) -> list[StatementLine]:

    balance = opening_balance
    for line in lines:
        if line.affects_balance:
            balance = balance + line.credit - line.debit
        line.running_balance = balance.quantize(TWO_DP)
    return lines


def models_q(vendor, field_path: str):
    """Return a Django Q object filtering on field_path=vendor.pk."""
    from django.db.models import Q

    return Q(**{field_path: vendor.pk})


def build_vendor_statement(
    vendor,
    start_date: Optional[date] = None,
    end_date: Optional[date] = None,
) -> VendorStatement:

    currency_code = vendor.currency.code if vendor.currency else "N/A"

    ob_line = _fetch_opening_balance_line(vendor)

    bill_lines = _fetch_bill_lines(vendor, start_date, end_date)
    payment_lines = _fetch_payment_lines(vendor, start_date, end_date)
    advance_lines = _fetch_advance_applied_lines(vendor, start_date, end_date)
    credit_lines = _fetch_credit_note_lines(vendor, start_date, end_date)
    journal_lines = _fetch_journal_entry_lines(vendor, start_date, end_date)

    activity_lines = (
        bill_lines + payment_lines + advance_lines + credit_lines + journal_lines
    )
    activity_lines.sort(key=_sort_key)

    all_lines = ([ob_line] if ob_line else []) + activity_lines

    opening_balance = Decimal(str(vendor.opening_balance)).quantize(TWO_DP)
    all_lines = _recompute_running_balances(all_lines, ZERO)

    closing_balance = all_lines[-1].running_balance if all_lines else opening_balance

    total_debits = sum(
        (ln.debit for ln in all_lines if ln.affects_balance), ZERO
    ).quantize(TWO_DP)

    total_credits = sum(
        (ln.credit for ln in all_lines if ln.affects_balance), ZERO
    ).quantize(TWO_DP)

    summary = StatementSummary(
        opening_balance=opening_balance,
        total_debits=total_debits,
        total_credits=total_credits,
        closing_balance=closing_balance,
        line_count=sum(1 for ln in all_lines if ln.affects_balance),
    )

    return VendorStatement(
        vendor_id=vendor.pk,
        vendor_name=vendor.vendor_name,
        currency_code=currency_code,
        statement_date=date.today(),
        start_date=start_date,
        end_date=end_date,
        lines=all_lines,
        summary=summary,
    )
