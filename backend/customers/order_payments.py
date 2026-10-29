from django.db import transaction
from accounts.utils import get_or_create_default_account
from customers.models import (
    CustomerPurchaseOrderPayment,
    Invoice,
)
from transactions.services import JournalLine, JournalPostingService
from utilities.helpers import get_fiscal_year
from decimal import Decimal

from django.contrib.contenttypes.models import ContentType


@transaction.atomic
def transfer_sales_order_payments_to_invoice(invoice: Invoice):
    if not invoice.purchase_order_id:
        return

    invoice = Invoice.objects.select_for_update().get(pk=invoice.pk)

    payments = (
        CustomerPurchaseOrderPayment.objects.select_for_update()
        .undeleted()
        .filter(
            sales_order=invoice.purchase_order,
            invoice__isnull=True,
            payment_status="approved",
        )
        .order_by("payment_date", "created_at")
    )

    remaining_due = Decimal(invoice.amount_due)

    for payment in payments:
        if remaining_due <= Decimal("0.0"):
            break

        amount_to_apply = min(
            Decimal(payment.amount_paid),
            remaining_due,
        )

        if amount_to_apply <= Decimal(0.0):
            continue

        institution = invoice.get_institution()
        invoice_currency, invoice_rate = invoice.determine_rate_currency_used()
        account_currency = (
            None if invoice_currency == institution.currency else invoice_currency
        )

        advance_liability = get_or_create_default_account(
            institution,
            "misc_liability_account",
            account_currency,
        )

        customer = invoice.get_invoice_customer()

        receivable_account = (
            invoice.accounts_receivable_account
            or (
                customer.default_account
                if customer is not None and customer.default_account is not None
                else None
            )
            or get_or_create_default_account(
                institution,
                "receivable_account",
                account_currency,
            )
        )

        journal_lines = [
            JournalLine(
                account=advance_liability,
                entry_type="debit",
                transaction_amount=amount_to_apply,
                transaction_currency=invoice_currency,
                exchange_rate=invoice_rate,
                description=(
                    f"Customer deposit applied from Sales Order "
                    f"{invoice.purchase_order.reference_code}"
                ),
            ),
            JournalLine(
                account=receivable_account,
                entry_type="credit",
                transaction_amount=amount_to_apply,
                transaction_currency=invoice_currency,
                exchange_rate=invoice_rate,
                description=(
                    f"Sales Order payment applied to Invoice "
                    f"{invoice.reference_code}"
                ),
            ),
        ]

        JournalPostingService.post(
            fiscal_year=get_fiscal_year(
                institution,
                invoice.issue_date,
            ),
            title=f"Apply Sales Order payment {payment.reference_code}",
            description=(
                f"Applied Sales Order payment {payment.reference_code} "
                f"to Invoice {invoice.reference_code}"
            ),
            transaction_date=invoice.issue_date,
            lines=journal_lines,
            branch=invoice.branch,
            content_type=ContentType.objects.get_for_model(
                CustomerPurchaseOrderPayment,
                for_concrete_model=False,
            ),
            object_id=payment.pk,
            source=invoice,
        )

        remaining_due -= amount_to_apply

        payment.invoice = invoice
        payment.amount_applied = amount_to_apply
        payment.payment_status = "transferred"
        payment.is_transfer_processed = True
        payment.save(
            update_fields=[
                "invoice",
                "amount_applied",
                "payment_status",
                "is_transfer_processed",
            ]
        )

        invoice.amount_due = max(remaining_due, Decimal("0"))

        if invoice.amount_due == 0:
            invoice.invoice_payment_status = "paid"
        elif invoice.amount_due < invoice.gross_total:
            invoice.invoice_payment_status = "partially_paid"
        else:
            invoice.invoice_payment_status = "unpaid"

        invoice.save(
            update_fields=[
                "amount_due",
                "invoice_payment_status",
            ]
        )
