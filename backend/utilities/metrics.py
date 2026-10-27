# import datetime
from django.db.models import Sum, Count, F, Q

# from django.db.models.functions import TruncMonth
from customers.models import Invoice, InvoiceLineItem, Customer


from decimal import Decimal
from typing import Dict, List, Any
from django.db.models import Sum, F
from django.db.models.functions import ExtractMonth

from vendors.models import VendorBillLineItem, VendorBill, VendorPayment, Vendor


def get_total_revenue(start_date=None, end_date=None):
    """
    Calculates the total revenue from all paid invoices within a given date range.

    Args:
        start_date (datetime.date, optional): The start date for the range.
        end_date (datetime.date, optional): The end date for the range.

    Returns:
        decimal.Decimal: The total revenue amount. Returns 0 if no paid invoices are found.
    """
    queryset = Invoice.objects.filter(status="paid")

    # Use issue_date for date filtering
    if start_date:
        queryset = queryset.filter(issue_date__gte=start_date)
    if end_date:
        queryset = queryset.filter(issue_date__lte=end_date)

    total_revenue = queryset.aggregate(total=Sum("line_items__line_total"))

    return total_revenue["total"] or 0
