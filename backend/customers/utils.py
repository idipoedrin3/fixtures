from django.conf import settings
from django.http import HttpResponse
from weasyprint import HTML
from decimal import Decimal
import os
import base64
import logging
from django.template.loader import render_to_string
from utilities.helpers import (
    format_currency as format_money,
    validation_error,
)
from .models import Invoice
from django.contrib.contenttypes.models import ContentType
from taxation.models import TaxApplicationBreakDown

logger = logging.getLogger(__name__)


##################################INVOICE################################################


def get_invoice_customer_details(invoice):
    customer = invoice.get_invoice_customer()
    if not customer:
        return {
            "name": "No Customer",
            "email": "",
            "phone": "",
            "address": "",
            "tax_id": "",
        }

    return {
        "name": customer.customer_name,
        "email": customer.email or "",
        "phone": customer.phone_number or "",
        "address": customer.address or "",
        "tax_id": getattr(customer, "tax_id", "") or "",
    }


def get_institution_details_for_invoice(invoice, request=None):
    institution = invoice.get_institution()

    if not institution:
        return {
            "name": "",
            "email": "",
            "phone": "",
            "address": "",
            "logo_url": "",
            "tax_id": "",
            "website": "",
            "theme_color": "",
            "supported_payment_options": {},
        }

    # Get logo URL
    logo_url = ""
    if getattr(institution, "institution_logo", None):
        try:
            if request:
                logo_url = request.build_absolute_uri(institution.institution_logo.url)
            else:
                logo_url = institution.institution_logo.url
        except Exception:
            logo_url = ""

    # Fetch supported payment options
    supported_payment_qs = (
        institution.supported_payment_options.select_related("content_type")
        .filter(is_active=True, is_deleted=False)
        .all()
    )

    grouped_by_currency = {}
    payment_type_map = {
        "bankaccount": "BANK",
        "mobilemoneyaccount": "MOBILE_MONEY",
        "digitalwalletaccount": "DIGITAL_WALLET",
        "cashathandaccount": "CASH_AT_HAND",
    }

    for supported_option in supported_payment_qs:
        payment_option = supported_option.payment_option
        if not payment_option:
            continue

        supported_currency = getattr(payment_option, "currency", None)
        currency = getattr(supported_currency, "currency", None)
        currency_code = (
            getattr(currency, "code", None)
            or getattr(institution.currency, "code", None)
            or "N/A"
        )

        details = {
            "type": payment_type_map.get(
                supported_option.content_type.model,
                supported_option.content_type.model.upper(),
            ),
            "account_name": getattr(payment_option, "account_name", ""),
            "bank_name": getattr(payment_option, "bank_name", ""),
            "account_number": getattr(payment_option, "account_number", ""),
            "provider_name": getattr(payment_option, "provider_name", ""),
            "phone_number": getattr(payment_option, "phone_number", ""),
            "platform_name": getattr(payment_option, "platform_name", ""),
            "email": getattr(payment_option, "email", ""),
            "responsible_person": getattr(payment_option, "responsible_person", ""),
        }

        if currency_code not in grouped_by_currency:
            grouped_by_currency[currency_code] = []

        grouped_by_currency[currency_code].append({"details": details})

    return {
        "name": institution.institution_name,
        "email": institution.institution_email or "",
        "phone": institution.first_phone_number
        or institution.second_phone_number
        or "",
        "address": institution.location or "",
        "tax_id": getattr(institution, "tax_id", "") or "",
        "logo_url": logo_url,
        "website": getattr(institution, "website", "") or "",
        "theme_color": institution.theme_color or "#2151ff",
        "supported_payment_options": grouped_by_currency,
    }


def get_invoice_line_items_details(invoice):
    """
    Returns structured invoice line item data including accurate tax breakdown
    (single tax per line item).
    """

    line_items_qs = invoice.line_items.all().select_related(
        "line_item__inventory_item",
        "unit_of_measure__unit_of_measure",
    )

    line_item_ct = ContentType.objects.get_for_model(line_items_qs.model)
    line_item_ids = list(line_items_qs.values_list("id", flat=True))

    breakdowns = TaxApplicationBreakDown.objects.filter(
        content_type=line_item_ct,
        object_id__in=line_item_ids,
    ).select_related("tax")

    breakdown_map = {b.object_id: b for b in breakdowns}

    line_items = []

    for item in line_items_qs:
        inventory_item = (
            item.line_item.inventory_item
            if item.line_item and item.line_item.inventory_item
            else None
        )

        line_total = item.line_total or Decimal("0.00")

        item_data = {
            "item_name": inventory_item.item_name if inventory_item else "Unknown Item",
            "reference_code": inventory_item.reference_code if inventory_item else "",
            "quantity": float(item.quantity),
            "unit_price": float(item.unit_price),
            "line_total": float(line_total),
            "unit": "unit",
            "unit_abbreviation": "",
            "tax": None,
            "net_amount": float(line_total),
            "gross_amount": float(line_total),
            "tax_amount_total": 0.0,
        }

        if item.unit_of_measure and item.unit_of_measure.unit_of_measure:
            uom = item.unit_of_measure.unit_of_measure
            item_data["unit"] = uom.unit_name
            item_data["unit_abbreviation"] = uom.unit_abbreviation or ""

        breakdown = breakdown_map.get(item.id)

        if breakdown and breakdown.tax:
            tax_amount = breakdown.tax_amount or Decimal("0.00")
            net_amount = breakdown.net_amount or line_total
            gross_amount = breakdown.gross_amount or line_total

            item_data["tax"] = {
                "name": breakdown.tax.tax_name,
                "rate": (
                    float(breakdown.tax.total_rate_value)
                    if breakdown.tax.total_rate_value is not None
                    else None
                ),
                "amount": float(tax_amount),
                "is_inclusive": breakdown.tax.is_inclusive,
            }

            item_data["net_amount"] = float(net_amount)
            item_data["gross_amount"] = float(gross_amount)
            item_data["tax_amount_total"] = float(tax_amount)

        line_items.append(item_data)

    return line_items


def get_invoice_tax_breakdown(invoice):

    tax_breakdowns = invoice.get_all_tax_breakdowns().select_related("tax")

    tax_map = {}

    for tb in tax_breakdowns:
        if not tb.tax:
            continue

        tax_name = tb.tax.tax_name
        rate = tb.tax.total_rate_value

        tax_amount = tb.tax_amount or Decimal("0.00")
        net_amount = tb.net_amount or Decimal("0.00")

        if tax_name not in tax_map:
            tax_map[tax_name] = {
                "name": tax_name,
                "rate": float(rate) if rate is not None else None,
                "amount": Decimal("0.00"),
                "taxable_amount": Decimal("0.00"),
            }

        tax_map[tax_name]["amount"] += tax_amount
        tax_map[tax_name]["taxable_amount"] += net_amount

    return [
        {
            "name": t["name"],
            "rate": t["rate"],
            "amount": float(t["amount"]),
            "taxable_amount": float(t["taxable_amount"]),
        }
        for t in tax_map.values()
    ]


def calculate_invoice_totals(invoice, tax_details=None, currency_prefix=""):
    subtotal = Decimal(str(invoice.net_total or 0))
    total_tax = Decimal(str(invoice.tax_total or 0))
    grand_total = Decimal(str(invoice.total_amount or 0))
    amount_paid = Decimal(str(invoice.partial_amount_paid or 0))
    amount_due = Decimal(str(invoice.amount_due or 0))

    return {
        "subtotal": subtotal,
        "formatted_subtotal": format_money(subtotal, currency_prefix),
        "total_tax": total_tax,
        "formatted_total_tax": format_money(total_tax, currency_prefix),
        "tax_details": tax_details or [],
        "grand_total": grand_total,
        "formatted_grand_total": format_money(grand_total, currency_prefix),
        "amount_paid": amount_paid,
        "formatted_amount_paid": format_money(amount_paid, currency_prefix),
        "amount_due": amount_due,
        "formatted_amount_due": format_money(amount_due, currency_prefix),
    }


def get_invoice_payment_info(invoice):
    """
    Get payment information for the invoice
    """
    payment_info = {
        "status": invoice.get_invoice_payment_status_display(),
        "status_code": invoice.invoice_payment_status,
        "due_date": (
            invoice.due_date.strftime("%d/%m/%Y") if invoice.due_date else "N/A"
        ),
        "issue_date": (
            invoice.issue_date.strftime("%d/%m/%Y") if invoice.issue_date else "N/A"
        ),
        "terms": (
            getattr(invoice.customer.payment_term, "description", "Standard Terms")
            if invoice.customer and invoice.customer.payment_term
            else "Standard Terms"
        ),
    }

    payments = invoice.customer_payments.filter(
        payment_status="APPROVED",
        is_active=True,
        deleted_at__isnull=True,
    )
    if payments.exists():
        payment_info["payment_methods"] = [
            {
                "method": "Customer receipt",
                "amount": float(payment.amount),
                "date": payment.payment_date.strftime("%d/%m/%Y"),
            }
            for payment in payments
        ]

    return payment_info


def get_currency_info(invoice):
    institution_currency = invoice.get_institution().currency
    currency = institution_currency
    exchange_rate = Decimal("1.00")

    try:
        rate_info = invoice.determine_rate_currency_used()
        if isinstance(rate_info, tuple):
            selected_currency, selected_rate = rate_info
            if selected_currency:
                currency = selected_currency
            if selected_rate:
                exchange_rate = Decimal(str(selected_rate))
    except Exception as e:
        logger.debug(f"Error getting currency info: {str(e)}")

    return {
        "code": getattr(currency, "code", "UGX"),
        "symbol": getattr(currency, "symbol", "UGX"),
        "name": getattr(currency, "name", "Uganda Shilling"),
        "exchange_rate": exchange_rate,
    }


def get_complete_invoice_data_for_pdf(invoice: Invoice, request=None):
    try:
        institution_data = get_institution_details_for_invoice(invoice, request=request)
        customer_data = get_invoice_customer_details(invoice)
        currency_info = get_currency_info(invoice)
        currency_prefix = f"{currency_info['code']} "

        line_items = get_invoice_line_items_details(invoice)
        tax_details = get_invoice_tax_breakdown(invoice)
        totals = calculate_invoice_totals(
            invoice,
            tax_details,
            currency_prefix,
        )
        payment_info = get_invoice_payment_info(invoice)

        for item in line_items:
            item["formatted_unit_price"] = format_money(
                item.get("unit_price"), currency_prefix
            )
            item["formatted_net_amount"] = format_money(
                item.get("net_amount"), currency_prefix
            )
            item["formatted_tax_amount"] = format_money(
                item.get("tax_amount_total"), currency_prefix
            )
            item["formatted_gross_amount"] = format_money(
                item.get("gross_amount"), currency_prefix
            )

        for tax in tax_details:
            tax["formatted_amount"] = format_money(tax.get("amount"), currency_prefix)
            tax["formatted_taxable_amount"] = format_money(
                tax.get("taxable_amount"), currency_prefix
            )

        for method in payment_info.get("payment_methods", []):
            method["formatted_amount"] = format_money(
                method.get("amount"), currency_prefix
            )

        invoice_data = {
            "invoice_info": {
                "number": invoice.reference_code,
                "date": (
                    invoice.issue_date.strftime("%d/%m/%Y")
                    if invoice.issue_date
                    else ""
                ),
                "status": invoice.get_invoice_status_display(),
                "status_code": invoice.invoice_status,
                "currency": currency_info,
                "payment_status": payment_info["status"],
                "payment_status_code": payment_info["status_code"],
                "description": invoice.description or "",
            },
            "institution": institution_data,
            "customer": customer_data,
            "line_items": line_items,
            "totals": totals,
            "payment": payment_info,
            "metadata": {
                "created_at": (
                    invoice.created_at.strftime("%d/%m/%Y %H:%M")
                    if invoice.created_at
                    else ""
                ),
                "created_by": str(invoice.created_by) if invoice.created_by else "",
                "approval_status": (
                    invoice.approval_status
                    if hasattr(invoice, "approval_status")
                    else ""
                ),
            },
        }

        return invoice_data

    except Exception as e:
        logger.error(
            f"Error getting complete invoice data for PDF: {str(e)}", exc_info=True
        )
        raise


############################QUOTATION######################################################


def get_quotation_customer_details(quotation):
    customer = quotation.customer
    if not customer:
        return {
            "name": "No Customer",
            "email": "",
            "phone": "",
            "address": "",
            "tax_id": "",
        }

    return {
        "name": customer.customer_name,
        "email": customer.email or "",
        "phone": customer.phone_number or "",
        "address": customer.address or "",
        "tax_id": getattr(customer, "tax_id", "") or "",
    }


def get_institution_details_for_quotation(quotation, request=None):
    institution = quotation.get_institution()

    if not institution:
        return {
            "name": "",
            "email": "",
            "phone": "",
            "address": "",
            "logo_url": "",
            "tax_id": "",
            "website": "",
            "theme_color": "",
            "supported_payment_options": {},
        }

    # Logo URL
    logo_url = ""
    if getattr(institution, "institution_logo", None):
        try:
            if request:
                logo_url = request.build_absolute_uri(institution.institution_logo.url)
            else:
                logo_url = institution.institution_logo.url
        except Exception:
            logo_url = ""

    # Payment options grouped by currency
    supported_payment_qs = (
        institution.supported_payment_options.select_related("content_type")
        .filter(is_active=True, is_deleted=False)
        .all()
    )

    grouped_by_currency = {}
    payment_type_map = {
        "bankaccount": "BANK",
        "mobilemoneyaccount": "MOBILE_MONEY",
        "digitalwalletaccount": "DIGITAL_WALLET",
        "cashathandaccount": "CASH_AT_HAND",
    }

    for supported_option in supported_payment_qs:
        payment_option = supported_option.payment_option
        if not payment_option:
            continue

        supported_currency = getattr(payment_option, "currency", None)
        currency = getattr(supported_currency, "currency", None)
        currency_code = (
            getattr(currency, "code", None)
            or getattr(institution.currency, "code", None)
            or "N/A"
        )

        details = {
            "type": payment_type_map.get(
                supported_option.content_type.model,
                supported_option.content_type.model.upper(),
            ),
            "account_name": getattr(payment_option, "account_name", ""),
            "bank_name": getattr(payment_option, "bank_name", ""),
            "account_number": getattr(payment_option, "account_number", ""),
            "provider_name": getattr(payment_option, "provider_name", ""),
            "phone_number": getattr(payment_option, "phone_number", ""),
            "platform_name": getattr(payment_option, "platform_name", ""),
            "email": getattr(payment_option, "email", ""),
            "responsible_person": getattr(payment_option, "responsible_person", ""),
        }

        if currency_code not in grouped_by_currency:
            grouped_by_currency[currency_code] = []

        grouped_by_currency[currency_code].append({"details": details})

    return {
        "name": institution.institution_name,
        "email": institution.institution_email or "",
        "phone": institution.first_phone_number
        or institution.second_phone_number
        or "",
        "address": institution.location or "",
        "logo_url": logo_url,
        "tax_id": getattr(institution, "tax_id", "") or "",
        "website": getattr(institution, "website", "") or "",
        "theme_color": institution.theme_color or "#2151ff",
        "supported_payment_options": grouped_by_currency,
    }


def get_quotation_line_items_details(quotation):
    line_items_qs = quotation.line_items.all().select_related(
        "line_item__inventory_item", "unit_of_measure"
    )

    line_items = []

    for item in line_items_qs:
        item_data = {
            "item_name": "Unknown Item",
            "reference_code": "",
            "description": "",
            "quantity": float(item.quantity),
            "unit": "unit",
            "unit_abbreviation": "",
            "unit_price": float(item.unit_price),
            "line_total": float(item.line_total),
        }

        if item.line_item and hasattr(item.line_item, "inventory_item"):
            inventory_item = item.line_item.inventory_item
            if inventory_item:
                item_data.update(
                    {
                        "item_name": inventory_item.item_name,
                        "reference_code": inventory_item.reference_code or "",
                        "item_type": inventory_item.item_type,
                        "item_category": (
                            getattr(inventory_item.item_category, "name", "")
                            if inventory_item.item_category
                            else ""
                        ),
                    }
                )

        if item.unit_of_measure:
            item_data.update(
                {
                    "unit": item.unit_of_measure.unit_of_measure.unit_name,
                    "unit_abbreviation": item.unit_of_measure.unit_of_measure.unit_abbreviation
                    or "",
                }
            )

        line_items.append(item_data)

    return line_items


def get_sales_document_tax_breakdown(document, currency_prefix=""):
    grouped_taxes = {}

    for line in document.line_items.all():
        for breakdown in line.get_tax_breakdowns():
            key = (
                breakdown.tax.reference_code,
                breakdown.tax.tax_name,
            )
            grouped_taxes[key] = grouped_taxes.get(key, Decimal("0.00")) + Decimal(
                str(breakdown.tax_amount or 0)
            )

    return [
        {
            "reference_code": reference_code,
            "name": name,
            "amount": amount,
            "formatted_amount": format_money(amount, currency_prefix),
        }
        for (reference_code, name), amount in grouped_taxes.items()
    ]


def calculate_quotation_totals(quotation, currency_prefix=""):
    legacy_subtotal = sum(
        (Decimal(str(item.line_total or 0)) for item in quotation.line_items.all()),
        Decimal("0.00"),
    )
    subtotal = Decimal(str(quotation.net_total or legacy_subtotal))
    tax_total = Decimal(str(quotation.tax_total or 0))
    grand_total = Decimal(str(quotation.gross_total or legacy_subtotal))
    discount = Decimal("0.00")

    return {
        "subtotal": subtotal,
        "formatted_subtotal": format_money(subtotal, currency_prefix),
        "tax_total": tax_total,
        "formatted_tax_total": format_money(tax_total, currency_prefix),
        "tax_breakdown": get_sales_document_tax_breakdown(
            quotation,
            currency_prefix,
        ),
        "grand_total": grand_total,
        "formatted_grand_total": format_money(grand_total, currency_prefix),
        "discount": discount,
        "formatted_discount": format_money(discount, currency_prefix),
    }


def get_quotation_payment_info(quotation):
    return {
        "status": quotation.get_status_display(),
        "due_date": (
            quotation.expiry_date.strftime("%d/%m/%Y")
            if quotation.expiry_date
            else "N/A"
        ),
        "issue_date": (
            quotation.issue_date.strftime("%d/%m/%Y") if quotation.issue_date else "N/A"
        ),
        "terms": "Standard Terms",
    }


def get_quotation_currency_info(quotation):
    institution_currency = quotation.get_institution().currency
    currency = institution_currency
    exchange_rate = Decimal("1.00")

    try:
        rate_info = quotation.determine_rate_currency_used()
        if isinstance(rate_info, tuple):
            selected_currency, selected_rate = rate_info
            if selected_currency:
                currency = selected_currency
            if selected_rate:
                exchange_rate = Decimal(str(selected_rate))
    except Exception as e:
        logger.debug(f"Error getting currency info: {str(e)}")

    return {
        "code": getattr(currency, "code", "UGX"),
        "symbol": getattr(currency, "symbol", "UGX"),
        "name": getattr(currency, "name", "Uganda Shilling"),
        "exchange_rate": exchange_rate,
    }


def get_complete_quotation_data_for_pdf(quotation, request=None):
    try:
        institution_data = get_institution_details_for_quotation(
            quotation, request=request
        )
        customer_data = get_quotation_customer_details(quotation)
        currency_info = get_quotation_currency_info(quotation)
        currency_prefix = f"{currency_info['code']} "

        line_items = get_quotation_line_items_details(quotation)
        totals = calculate_quotation_totals(quotation, currency_prefix)
        payment_info = get_quotation_payment_info(quotation)

        for item in line_items:
            item["formatted_unit_price"] = format_money(
                item.get("unit_price"), currency_prefix
            )
            item["formatted_line_total"] = format_money(
                item.get("line_total"), currency_prefix
            )

        quotation_data = {
            "quotation_info": {
                "number": quotation.reference_code,
                "date": (
                    quotation.issue_date.strftime("%d/%m/%Y")
                    if quotation.issue_date
                    else ""
                ),
                "status": quotation.get_status_display(),
                "status_code": quotation.status,
                "currency": currency_info,
            },
            "institution": institution_data,
            "customer": customer_data,
            "line_items": line_items,
            "totals": totals,
            "payment": payment_info,
            "currency": currency_info,
            "metadata": {
                "created_at": (
                    quotation.created_at.strftime("%d/%m/%Y %H:%M")
                    if quotation.created_at
                    else ""
                ),
                "created_by": str(quotation.created_by) if quotation.created_by else "",
                "approval_status": quotation.status,
            },
        }

        return quotation_data
    except Exception as e:
        logger.error(
            f"Error getting complete quotation data for PDF: {str(e)}", exc_info=True
        )
        raise


#########################################INCOMING PURCHASE ORDER##########################
from decimal import Decimal
from django.utils import timezone
from django.conf import settings
import logging

logger = logging.getLogger(__name__)


def get_purchase_order_customer_details(po):
    """
    Get customer information for the purchase order
    """
    customer = po.get_purchase_order_customer()
    if not customer:
        return {
            "name": "No Customer",
            "email": "",
            "phone": "",
            "address": "",
            "tax_id": "",
        }

    return {
        "name": customer.customer_name,
        "email": customer.email or "",
        "phone": customer.phone_number or "",
        "address": customer.address or "",
        "tax_id": getattr(customer, "tax_id", "") or "",
    }


def get_institution_details_for_purchase_order(po, request=None):
    """
    Get institution information for the purchase order
    """
    institution = po.get_institution()

    if not institution:
        return {
            "name": "",
            "email": "",
            "phone": "",
            "address": "",
            "logo_url": "",
            "tax_id": "",
            "website": "",
            "theme_color": "",
        }

    # Get logo URL
    logo_url = ""
    if getattr(institution, "institution_logo", None):
        try:
            if request:
                logo_url = request.build_absolute_uri(institution.institution_logo.url)
            else:
                logo_url = institution.institution_logo.url
        except Exception:
            logo_url = ""

    return {
        "name": institution.institution_name,
        "email": institution.institution_email or "",
        "phone": institution.first_phone_number
        or institution.second_phone_number
        or "",
        "address": institution.location or "",
        "logo_url": logo_url,
        "tax_id": getattr(institution, "tax_id", "") or "",
        "website": getattr(institution, "website", "") or "",
        "theme_color": institution.theme_color or "#2151ff",
    }


def get_purchase_order_line_items_details(po):
    """
    Get line items details for the purchase order
    """
    line_items_qs = po.line_items.all().select_related(
        "line_item__inventory_item", "unit_of_measure"
    )

    line_items = []

    for item in line_items_qs:
        item_data = {
            "item_name": "Unknown Item",
            "reference_code": "",
            "description": "",
            "quantity": float(item.quantity),
            "unit": "unit",
            "unit_abbreviation": "",
            "unit_price": float(item.unit_price),
            "line_total": float(item.line_total),
            "taxes": [],  # If you have taxes, populate like invoice helper
        }

        if item.line_item and hasattr(item.line_item, "inventory_item"):
            inventory_item = item.line_item.inventory_item
            if inventory_item:
                item_data.update(
                    {
                        "item_name": inventory_item.item_name,
                        "reference_code": inventory_item.reference_code or "",
                        "item_type": inventory_item.item_type,
                        "item_category": (
                            getattr(inventory_item.item_category, "name", "")
                            if inventory_item.item_category
                            else ""
                        ),
                    }
                )

        if item.unit_of_measure:
            item_data.update(
                {
                    "unit": item.unit_of_measure.unit_of_measure.unit_name,
                    "unit_abbreviation": item.unit_of_measure.unit_of_measure.unit_abbreviation
                    or "",
                }
            )

            try:
                branch_unit = (
                    item.unit_of_measure.branchinventoryitemunitofmeasure_set.filter(
                        branch_inventory_item=item.line_item
                    ).first()
                )
                if branch_unit:
                    item_data["conversion_factor"] = float(
                        branch_unit.conversion_factor
                    )
                    item_data["branch_selling_price"] = float(branch_unit.selling_price)
            except Exception:
                pass

        line_items.append(item_data)

    return line_items


def calculate_purchase_order_totals(po, currency_prefix=""):
    """
    Calculate totals for the purchase order
    """
    legacy_subtotal = sum(
        (Decimal(str(item.line_total or 0)) for item in po.line_items.all()),
        Decimal("0.00"),
    )
    subtotal = Decimal(str(po.net_total or legacy_subtotal))
    tax_total = Decimal(str(po.tax_total or 0))
    grand_total = Decimal(str(po.gross_total or legacy_subtotal))

    return {
        "subtotal": subtotal,
        "formatted_subtotal": format_money(subtotal, currency_prefix),
        "tax_total": tax_total,
        "formatted_tax_total": format_money(tax_total, currency_prefix),
        "tax_breakdown": get_sales_document_tax_breakdown(
            po,
            currency_prefix,
        ),
        "grand_total": grand_total,
        "formatted_grand_total": format_money(grand_total, currency_prefix),
    }


def get_purchase_order_currency_info(po):
    """
    Get currency information for the purchase order
    """
    institution_currency = po.get_institution().currency
    currency = institution_currency
    exchange_rate = Decimal("1.00")

    try:
        target_currency, rate = po.determine_rate_currency_used()
        if target_currency:
            currency = target_currency
        if rate:
            exchange_rate = Decimal(str(rate))
    except Exception as e:
        logger.debug(f"Error getting currency info: {str(e)}")

    return {
        "code": getattr(currency, "code", "UGX"),
        "symbol": getattr(currency, "symbol", "UGX"),
        "name": getattr(currency, "name", "Uganda Shilling"),
        "exchange_rate": exchange_rate,
    }


def get_complete_purchase_order_data_for_pdf(po, request=None):
    """
    Return complete purchase order data matching the invoice structure
    """
    try:
        institution_data = get_institution_details_for_purchase_order(
            po, request=request
        )
        customer_data = get_purchase_order_customer_details(po)
        currency_info = get_purchase_order_currency_info(po)
        currency_prefix = f"{currency_info['code']} "

        line_items = get_purchase_order_line_items_details(po)
        totals = calculate_purchase_order_totals(po, currency_prefix)

        for item in line_items:
            item["formatted_unit_price"] = format_money(
                item.get("unit_price"), currency_prefix
            )
            item["formatted_line_total"] = format_money(
                item.get("line_total"), currency_prefix
            )

        po_data = {
            "purchase_order_info": {
                "number": po.reference_code,
                "date": po.issue_date.strftime("%d/%m/%Y") if po.issue_date else "",
                "status": po.get_status_display(),
                "status_code": po.status,
                "currency": currency_info,
                "goods_issue_status": (po.get_goods_issued_note_status_display()),
                "invoice_status": po.get_invoice_status_display(),
            },
            "institution": institution_data,
            "customer": customer_data,
            "line_items": line_items,
            "totals": totals,
            "metadata": {
                "created_at": (
                    po.created_at.strftime("%d/%m/%Y %H:%M") if po.created_at else ""
                ),
                "created_by": str(po.created_by) if po.created_by else "",
                "approval_status": (
                    po.approval_status if hasattr(po, "approval_status") else ""
                ),
            },
        }

        return po_data

    except Exception as e:
        logger.error(
            f"Error getting complete purchase order data: {str(e)}", exc_info=True
        )
        raise


####################################END#####################################


def get_logo_base64(logo_url):
    if not logo_url:
        return None

    if logo_url.startswith("data:image/"):
        return logo_url

    try:
        path = os.path.join(settings.MEDIA_ROOT, logo_url.replace("/media/", ""))
        if os.path.exists(path):
            with open(path, "rb") as f:
                encoded = base64.b64encode(f.read()).decode("utf-8")
            return f"data:image/png;base64,{encoded}"
    except Exception:
        pass

    return logo_url


def format_currency(amount, symbol=""):
    try:
        return f"{symbol} {float(amount):,.2f}"
    except Exception:
        return f"{symbol} 0.00"


def generate_invoice_pdf_response(invoice_data):
    html = render_to_string("_invoice.html", invoice_data)
    pdf = HTML(string=html).write_pdf()

    response = HttpResponse(pdf, content_type="application/pdf")
    number = invoice_data["invoice_info"]["number"].replace("/", "-")
    response["Content-Disposition"] = f'attachment; filename="Invoice_{number}.pdf"'
    return response


def generate_quotation_pdf_response(quotation_data, request=None):
    """
    Generate PDF response for quotation
    """
    html = render_to_string("_quotation.html", quotation_data, request=request)
    pdf = HTML(string=html).write_pdf()

    response = HttpResponse(pdf, content_type="application/pdf")
    number = quotation_data["quotation_info"]["number"].replace("/", "-")
    response["Content-Disposition"] = f'attachment; filename="Quotation_{number}.pdf"'

    return response


def generate_purchase_order_pdf_response(po_data, request=None):
    """
    Generate PDF response for purchase order
    """
    html = render_to_string("_incoming_order.html", po_data, request=request)
    pdf = HTML(string=html).write_pdf()

    response = HttpResponse(pdf, content_type="application/pdf")
    number = po_data["purchase_order_info"]["number"].replace("/", "-")
    response["Content-Disposition"] = (
        f'attachment; filename="Purchase_Order_{number}.pdf"'
    )

    return response


def preview_taxes(amount, applicable_taxes=None):
    amount = Decimal(str(amount)).quantize(Decimal("0.01"))
    applicable_taxes = applicable_taxes or []

    inclusive_tax_total = Decimal("0.00")
    exclusive_tax_total = Decimal("0.00")
    tax_details = []

    for tax_entry in applicable_taxes:
        tax = tax_entry["tax"]

        if not tax or not tax.is_active:
            continue

        is_inclusive = tax_entry.get("is_inclusive", tax.is_inclusive)
        _, _, tax_amount = tax.calculate_tax_amount(amount)
        tax_amount = Decimal(str(tax_amount)).quantize(Decimal("0.01"))

        if is_inclusive:
            inclusive_tax_total += tax_amount
        else:
            exclusive_tax_total += tax_amount

        tax_details.append(
            {
                "base_uuid": str(tax.base_uuid),
                "name": tax.tax_name,
                "rate": (
                    float(tax.total_rate_value)
                    if tax.total_rate_value is not None
                    else None
                ),
                "is_inclusive": is_inclusive,
                "tax_amount": tax_amount,
            }
        )

    tax_total = (inclusive_tax_total + exclusive_tax_total).quantize(Decimal("0.01"))
    net_amount = (amount - inclusive_tax_total).quantize(Decimal("0.01"))
    gross_amount = (amount + exclusive_tax_total).quantize(Decimal("0.01"))

    return {
        "net_amount": net_amount,
        "tax_amount": tax_total,
        "gross_amount": gross_amount,
        "taxes": tax_details,
        "original_amount": amount,
    }


def preview_tax_for_item(item, tax_type, amount):

    if not item:
        raise validation_error("No item provided.")

    if not tax_type:
        raise validation_error("Please provide type of tax (sales or purchase).")

    amount = Decimal(str(amount)).quantize(Decimal("0.01"))

    if tax_type == "sales":
        tax = item.inventory_item.sales_tax
    elif tax_type == "purchase":
        tax = item.purchase_tax
    else:
        raise validation_error("Invalid tax type. Must be 'sales' or 'purchase'.")

    return preview_taxes(
        amount,
        [{"tax": tax, "is_inclusive": tax.is_inclusive}] if tax else [],
    )
