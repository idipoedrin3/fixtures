from weasyprint import HTML
from io import BytesIO
from decimal import Decimal
from django.contrib.contenttypes.models import ContentType
from approval.models import Approval, ApprovalTask
from utilities.helpers import has_access


def get_latest_approval(content_type, object_id):
    return (
        Approval.objects.filter(content_type=content_type, object_id=object_id)
        .order_by("-id")
        .first()
    )
