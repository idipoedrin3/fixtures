from rest_framework import serializers

from utilities.helpers import BaseReportFilterSerializer


class CustomerReportFilterSerializer(BaseReportFilterSerializer):
    customer_type = serializers.ChoiceField(
        choices=["individual", "business"], required=False
    )
    is_active = serializers.BooleanField(required=False)


class QuotationReportFilterSerializer(BaseReportFilterSerializer):
    status = serializers.ChoiceField(
        choices=["pending", "draft", "sent", "accepted", "rejected"], required=False
    )
    is_active = serializers.BooleanField(required=False)


class CustomerPurchaseOrderReportFilterSerializer(BaseReportFilterSerializer):
    status = serializers.ChoiceField(
        choices=["pending", "draft", "confirmed", "shipped", "delivered", "canceled"],
        required=False,
    )
    is_active = serializers.BooleanField(required=False)
    reference_code = serializers.CharField(required=False)


class InvoiceReportFilterSerializer(BaseReportFilterSerializer):
    invoice_status = serializers.ChoiceField(
        choices=["not_sent", "sent", "canceled"], required=False
    )
    invoice_payment_status = serializers.ChoiceField(
        choices=["unpaid", "partially_paid", "paid"], required=False
    )
    is_active = serializers.BooleanField(required=False)

    date_fields = {
        "created_at": ("Created date", "created_at__date"),
        "issue_date": ("Issue date", "issue_date"),
        "due_date": ("Due date", "due_date"),
    }


class ItemReturnFilterSerializer(BaseReportFilterSerializer):
    return_status = serializers.ChoiceField(
        choices=["PENDING", "APPROVED", "REJECTED"], required=False
    )
    return_type = serializers.ChoiceField(
        choices=["REPLACEMENT", "CASH_REFUND"], required=False
    )

    is_active = serializers.BooleanField(required=False)

    date_fields = {
        "return_date": ("Return date", "return_date"),
        "created_at": ("Created date", "created_at__date"),
    }
