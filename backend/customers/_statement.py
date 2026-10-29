from __future__ import annotations

import logging
from dataclasses import dataclass, field
from datetime import date, datetime
from decimal import Decimal
from enum import Enum
from typing import Optional

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Constants / Enums
# ---------------------------------------------------------------------------

ZERO = Decimal("0.00")
TWO_DP = Decimal("0.01")


class ActivityType(str, Enum):
    OPENING_BALANCE = "Opening Balance"
    INVOICE = "Invoice"
    PAYMENT = "Payment"
    ADVANCE_DEPOSIT = "Advance Deposit"
    DEPOSIT_APPLIED = "Deposit Applied"
    CREDIT_NOTE = "Credit Note"
    DEBIT_NOTE = "Debit Note"
    JOURNAL_ENTRY = "Journal Entry"


@dataclass
class StatementLine:
    """A single line on the customer statement."""

    date: date
    activity_type: ActivityType
    reference: str
    description: str
    debit: Decimal  # amount that increases what customer owes
    credit: Decimal  # amount that reduces what customer owes
    running_balance: Decimal
    affects_balance: bool = True  # False for informational-only rows

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
    line_count: int  # excludes informational-only rows

    def as_dict(self) -> dict:
        return {
            "opening_balance": _fmt(self.opening_balance),
            "total_debits": _fmt(self.total_debits),
            "total_credits": _fmt(self.total_credits),
            "net_movement": _fmt(self.total_debits - self.total_credits),
            "closing_balance": _fmt(self.closing_balance),
            "line_count": self.line_count,
        }


@dataclass
class CustomerStatement:
    customer_id: int
    customer_name: str
    currency_code: str
    statement_date: date
    start_date: Optional[date]
    end_date: Optional[date]
    lines: list[StatementLine] = field(default_factory=list)
    summary: Optional[StatementSummary] = None

    def as_dict(self) -> dict:
        return {
            "customer": {
                "id": self.customer_id,
                "name": self.customer_name,
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
    """Safely coerce datetime / date / None to date."""
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
# Raw-event fetchers  (one per activity type)
# ---------------------------------------------------------------------------


def _fetch_opening_balance_line(
    customer,
    running_balance: Decimal,
) -> Optional[tuple[StatementLine, Decimal]]:
    ob = customer.opening_balance
    if ob == ZERO:
        return None

    ob_date = _to_date(customer.opening_balance_received_date) or date.today()

    if ob > ZERO:
        # Customer owes us → debit
        debit, credit = ob, ZERO
    else:
        # We owe customer (deposit) → credit
        debit, credit = ZERO, abs(ob)

    running_balance = running_balance + debit - credit

    line = StatementLine(
        date=ob_date,
        activity_type=ActivityType.OPENING_BALANCE,
        reference=customer.reference_code,
        description="Opening Balance",
        debit=debit,
        credit=credit,
        running_balance=running_balance,
    )
    return line, running_balance


def _fetch_invoice_lines(
    customer,
    start_date: Optional[date],
    end_date: Optional[date],
    running_balance: Decimal,
) -> tuple[list[StatementLine], Decimal]:

    from customers.models import Invoice

    qs = (
        Invoice.objects.filter(
            customer=customer,
            is_active=True,
            invoice_status="sent",
            deleted_at__isnull=True,
        )
        .exclude(
            are_initial_journal_entries_made=True,
            description__startswith="Balance forward",
        )
        .select_related("customer")
        .order_by("issue_date", "created_at")
    )

    lines: list[StatementLine] = []

    for invoice in qs:
        d = _to_date(invoice.issue_date)
        if not _date_in_range(d, start_date, end_date):
            continue

        amount = invoice.total_amount.quantize(TWO_DP)
        running_balance = running_balance + amount  # debit → owed increases

        lines.append(
            StatementLine(
                date=d,
                activity_type=ActivityType.INVOICE,
                reference=invoice.reference_code,
                description=(
                    f"Invoice"
                    + (f" – {invoice.description}" if invoice.description else "")
                ),
                debit=amount,
                credit=ZERO,
                running_balance=running_balance,
            )
        )

    return lines, running_balance


def _fetch_customer_payment_lines(
    customer,
    start_date: Optional[date],
    end_date: Optional[date],
    running_balance: Decimal,
) -> tuple[list[StatementLine], Decimal]:
    from django.db.models import Q
    from customers.models import CustomerPayment

    qs = (
        CustomerPayment.objects.filter(
            Q(customer=customer)
            | Q(invoice__customer=customer)
            | Q(invoice__quotation__customer=customer)
            | Q(invoice__purchase_order__quotation__customer=customer)
            | Q(invoice__recurring_invoice__customer=customer),
            payment_status="APPROVED",
            is_active=True,
            deleted_at__isnull=True,
        )
        .select_related("customer", "invoice", "invoice__customer")
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
        running_balance = running_balance - amount  # credit → owed decreases
        is_prepayment = payment.invoice_id is None

        if is_prepayment:
            description = "Customer Prepayment Received"
            activity_type = ActivityType.ADVANCE_DEPOSIT
        else:
            description = f"Payment – {payment.invoice.reference_code}"
            activity_type = ActivityType.PAYMENT

        lines.append(
            StatementLine(
                date=d,
                activity_type=activity_type,
                reference=payment.reference_code,
                description=description,
                debit=ZERO,
                credit=amount,
                running_balance=running_balance,
            )
        )

    return lines, running_balance


def _fetch_credit_note_lines(
    customer,
    start_date: Optional[date],
    end_date: Optional[date],
    running_balance: Decimal,
) -> tuple[list[StatementLine], Decimal]:
    from customers.models import CreditDebitNote

    qs = (
        CreditDebitNote.objects.filter(
            invoice__customer=customer,
            type="CREDIT",
            falls_under="SALES",
            status="APPROVED",
            is_active=True,
            deleted_at__isnull=True,
        )
        .select_related("invoice")
        .order_by("issue_date", "created_at")
    )

    lines: list[StatementLine] = []

    for note in qs:
        d = _to_date(note.issue_date)
        if not _date_in_range(d, start_date, end_date):
            continue

        amount = note.amount.quantize(TWO_DP)
        running_balance = running_balance - amount  # credit

        lines.append(
            StatementLine(
                date=d,
                activity_type=ActivityType.CREDIT_NOTE,
                reference=note.reference_code,
                description=(
                    f"Credit Note"
                    + (f" – {note.invoice.reference_code}" if note.invoice else "")
                ),
                debit=ZERO,
                credit=amount,
                running_balance=running_balance,
            )
        )

    return lines, running_balance


def _fetch_debit_note_lines(
    customer,
    start_date: Optional[date],
    end_date: Optional[date],
    running_balance: Decimal,
) -> tuple[list[StatementLine], Decimal]:
    from customers.models import CreditDebitNote

    qs = (
        CreditDebitNote.objects.filter(
            invoice__customer=customer,
            type="DEBIT",
            falls_under="SALES",
            status="APPROVED",
            is_active=True,
            deleted_at__isnull=True,
        )
        .select_related("invoice")
        .order_by("issue_date", "created_at")
    )

    lines: list[StatementLine] = []

    for note in qs:
        d = _to_date(note.issue_date)
        if not _date_in_range(d, start_date, end_date):
            continue

        amount = note.amount.quantize(TWO_DP)
        running_balance = running_balance + amount  # debit

        lines.append(
            StatementLine(
                date=d,
                activity_type=ActivityType.DEBIT_NOTE,
                reference=note.reference_code,
                description=(
                    f"Debit Note"
                    + (f" – {note.invoice.reference_code}" if note.invoice else "")
                ),
                debit=amount,
                credit=ZERO,
                running_balance=running_balance,
            )
        )

    return lines, running_balance


def _fetch_journal_entry_lines(
    customer,
    start_date: Optional[date],
    end_date: Optional[date],
    running_balance: Decimal,
) -> tuple[list[StatementLine], Decimal]:
    from django.contrib.contenttypes.models import ContentType
    from customers.models import CustomerPayment
    from transactions.models import TransactionEntry

    customer_payment_content_type = ContentType.objects.get_for_model(CustomerPayment)

    qs = (
        TransactionEntry.objects.filter(
            partner_uuid=customer.base_uuid,
        )
        .exclude(
            transaction__content_type=customer_payment_content_type,
        )
        .select_related("transaction")
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
            running_balance = running_balance + debit_amount
        else:
            debit_amount = ZERO
            credit_amount = entry.entry_amount.quantize(TWO_DP)
            running_balance = running_balance - credit_amount

        lines.append(
            StatementLine(
                date=d,
                activity_type=ActivityType.JOURNAL_ENTRY,
                reference=entry.reference_code,
                description=entry.description or "Journal Entry",
                debit=debit_amount,
                credit=credit_amount,
                running_balance=running_balance,
                affects_balance=True,
            )
        )

    return lines, running_balance


def _sort_key(line: StatementLine):
    type_order = {
        ActivityType.OPENING_BALANCE: 0,
        ActivityType.INVOICE: 1,
        ActivityType.ADVANCE_DEPOSIT: 2,
        ActivityType.PAYMENT: 3,
        ActivityType.DEPOSIT_APPLIED: 4,
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
            balance = balance + line.debit - line.credit
        line.running_balance = balance.quantize(TWO_DP)
    return lines


def build_customer_statement(
    customer,
    start_date: Optional[date] = None,
    end_date: Optional[date] = None,
) -> CustomerStatement:

    currency_code = customer.currency.code if customer.currency else "N/A"

    ob_result = _fetch_opening_balance_line(customer, ZERO)
    ob_line: Optional[StatementLine] = None

    if ob_result is not None:
        ob_line, _ = ob_result

    activity_lines: list[StatementLine] = []

    dummy = ZERO

    inv_lines, dummy = _fetch_invoice_lines(customer, start_date, end_date, dummy)
    payment_lines, dummy = _fetch_customer_payment_lines(
        customer,
        start_date,
        end_date,
        dummy,
    )
    cn_lines, dummy = _fetch_credit_note_lines(customer, start_date, end_date, dummy)
    dn_lines, dummy = _fetch_debit_note_lines(customer, start_date, end_date, dummy)
    je_lines, dummy = _fetch_journal_entry_lines(customer, start_date, end_date, dummy)

    activity_lines = inv_lines + payment_lines + cn_lines + dn_lines + je_lines
    activity_lines.sort(key=_sort_key)

    all_lines = ([ob_line] if ob_line else []) + activity_lines

    opening_balance = customer.opening_balance.quantize(TWO_DP)
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

    return CustomerStatement(
        customer_id=customer.pk,
        customer_name=customer.customer_name,
        currency_code=currency_code,
        statement_date=date.today(),
        start_date=start_date,
        end_date=end_date,
        lines=all_lines,
        summary=summary,
    )
