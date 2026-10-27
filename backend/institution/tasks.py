from celery import shared_task
from django.utils import timezone
from datetime import timedelta
from django.db.models import Q

from institution.models import BusinessFinancialDocuments
from institution.models import Institution


@shared_task(name="check_document_expiry_and_notify")
def check_document_expiry_and_notify():
    """
    Checks for business financial documents nearing expiry based on institution settings
    and triggers notifications for the institution owner.
    """
    institutions = Institution.objects.all()

    for institution in institutions:
        threshold_days = institution.financial_document_expiry_notification_days

        # Calculate the date range for documents nearing expiry
        today = timezone.localdate()
        expiry_date_start = today + timedelta(days=1)
        expiry_date_end = today + timedelta(days=threshold_days)

        # Documents Nearing Expiry (within the threshold)
        nearing_expiry_docs = BusinessFinancialDocuments.objects.filter(
            category__institution=institution,
            is_active=True,
            deleted_at__isnull=True,
            expiry_date__range=[expiry_date_start, expiry_date_end],
        ).select_related("category", "branch")

        if nearing_expiry_docs.exists():
            doc_count = nearing_expiry_docs.count()

            nearing_expiry_doc_names = [doc.name for doc in nearing_expiry_docs]
            names_list_str = ", ".join(nearing_expiry_doc_names)

            message = (
                f"{doc_count} business financial document(s) are nearing their expiry date "
                f"within the next {threshold_days} days. "
                f"Documents: {names_list_str}"
            )

            print(f"[{institution.institution_name}] ALERT: {message}")

        expired_docs = BusinessFinancialDocuments.objects.filter(
            category__institution=institution,
            is_active=True,
            deleted_at__isnull=True,
            expiry_date__lt=today,
        ).select_related("category", "branch")

        if expired_docs.exists():
            expired_count = expired_docs.count()

            expired_doc_names = [doc.name for doc in expired_docs]
            names_list_str = ", ".join(expired_doc_names)

            message = (
                f"{expired_count} business financial document(s) have EXPIRED. Action required. "
                f"Documents: {names_list_str}"
            )

            print(f"[{institution.institution_name}] CRITICAL ALERT: {message}")
