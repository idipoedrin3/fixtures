import logging
from celery import shared_task
from django.db import transaction
from django.utils import timezone

logger = logging.getLogger(__name__)


@shared_task(bind=True, autoretry_for=(Exception,), retry_backoff=True, max_retries=2)
def create_invoices_from_recurring_invoices(self):

    from customers.models import RecurringInvoice, Invoice

    today = timezone.now().date()

    created = 0
    skipped = 0

    queryset = RecurringInvoice.objects.filter(
        is_active=True,
        next_recurring_date__isnull=False,
        next_recurring_date__lte=today,
    )

    for recurring_invoice in queryset:
        try:
            with transaction.atomic():

                ri = RecurringInvoice.objects.select_for_update().get(
                    pk=recurring_invoice.pk
                )

                if ri.has_reached_occurrence_limit():
                    ri.next_recurring_date = None
                    ri.save(update_fields=["next_recurring_date"])
                    skipped += 1
                    continue

                period_start = ri.next_recurring_date

                exists = Invoice.objects.filter(
                    recurring_invoice=ri,
                    billing_start_date=period_start,
                ).exists()

                if exists:
                    skipped += 1
                    ri.advance_next_date()
                    ri.save(update_fields=["next_recurring_date"])
                    continue

                invoice = ri.create_invoice_for_recurring_invoice()

                if ri.has_reached_occurrence_limit():
                    ri.next_recurring_date = None
                else:
                    ri.advance_next_date()

                ri.save(update_fields=["next_recurring_date"])

                if invoice is None:
                    skipped += 1
                else:
                    created += 1
        except Exception as e:
            logger.error(
                f"Error generating invoice for RecurringInvoice {recurring_invoice.id}: {str(e)}"
            )
            continue

    return {
        "created": created,
        "skipped": skipped,
    }


@shared_task(bind=True, autoretry_for=(Exception,), retry_backoff=True, max_retries=2)
def send_demand_notice_task(self, customer_id, invoice_ids):
    from customers.models import Customer, Invoice
    from utilities.email_client import EmailClient
    from decimal import Decimal

    customer = Customer.objects.get(id=customer_id)
    institution = customer.institution

    invoices = Invoice.objects.filter(id__in=invoice_ids).order_by("due_date")

    total_balance = Decimal("0.00")
    invoice_list = []

    for inv in invoices:
        balance = inv.amount_due
        total_balance += balance

        invoice_list.append(
            {
                "reference_code": inv.reference_code,
                "issue_date": (
                    inv.issue_date.strftime("%B %d, %Y") if inv.issue_date else "N/A"
                ),
                "due_date": (
                    inv.due_date.strftime("%B %d, %Y") if inv.due_date else "N/A"
                ),
                "total_amount": inv.total_amount,
                "balance": balance,
            }
        )

    currency = customer.currency or institution.currency

    context = {
        "institution_name": institution.institution_name,
        "institution_email": institution.institution_email,
        "customer_name": customer.customer_name,
        "invoices": invoice_list,
        "total_balance": total_balance,
        "currency_symbol": currency.symbol if currency else "",
        "current_year": timezone.now().year,
        "payment_instructions": getattr(institution, "payment_instructions", ""),
    }

    EmailClient.send(
        subject=f"Demand Notice: Outstanding Balance with {institution.institution_name}",
        recipients=[customer.email],
        template_html="emails/demand_notice_email.html",
        context=context,
    )

    return f"Demand notice sent to {customer.customer_name}"
