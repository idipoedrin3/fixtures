import logging

from celery import shared_task
from django.contrib.auth import get_user_model
from utilities.email_client import EmailClient

logger = logging.getLogger(__name__)
User = get_user_model()


class _RequestProxy:
    def __init__(self, user, institution):
        self.user = user
        self.institution = institution


@shared_task(
    bind=True,
    acks_late=True,
    reject_on_worker_lost=True,
)
def bulk_inventory_upload_task(
    self, file_bytes: bytes, filename: str, user_id: int, institution_id: int
):
    from django.apps import apps
    from .helpers.inventory_item_bulk_creation import process_bulk_inventory_upload

    Institution = apps.get_model("institution", "Institution")

    try:
        user = User.objects.get(pk=user_id)
        institution = Institution.objects.get(pk=institution_id)
    except Exception as exc:
        logger.error("bulk_inventory_upload_task setup failed: %s", exc)
        return

    request_proxy = _RequestProxy(user=user, institution=institution)

    logger.info(
        "bulk_inventory_upload started | task=%s user=%s institution=%s file=%s",
        self.request.id,
        user_id,
        institution_id,
        filename,
    )

    result = process_bulk_inventory_upload(
        file_bytes=file_bytes,
        filename=filename,
        request=request_proxy,
    )

    logger.info(
        "bulk_inventory_upload finished | task=%s status=%s created=%s layers=%s message=%s",
        self.request.id,
        result.get("status"),
        result.get("created", 0),
        result.get("stock_layers_created", 0),
        result.get("message", ""),
    )


@shared_task(
    bind=True,
    acks_late=True,
    reject_on_worker_lost=True,
)
def stock_movement_report_email_task(
    self,
    institution_id: int,
    recipient: str,
    file_type: str = "pdf",
    filters: dict = None,
):
    from institution.models import Institution
    from .utils import (
        build_stock_movement_queryset,
        generate_stock_movement_file,
    )

    try:
        institution = Institution.objects.get(pk=institution_id)
    except Institution.DoesNotExist:
        return {"status": "error", "message": "Institution not found."}

    filters = filters or {}
    logs = build_stock_movement_queryset(
        institution=institution,
        **filters,
    )
    report = generate_stock_movement_file(
        institution=institution,
        logs=logs,
        file_type=file_type,
        start_date=filters.get("start_date"),
        end_date=filters.get("end_date"),
        filters=filters,
    )

    EmailClient.send(
        subject=f"{institution.institution_name} Stock Movement Report",
        recipients=recipient,
        template_html="emails/stock_movement_report.html",
        context={
            "institution": institution.institution_name,
            "file_type": file_type.upper(),
        },
        attachments=[report.as_attachment()],
    )

    return {"status": "sent", "recipient": recipient}
