import logging
from decimal import Decimal

from django.contrib.contenttypes.models import ContentType
from django.http import HttpResponse
from django.template.loader import render_to_string
from django.utils import timezone

from weasyprint import HTML

from .models import ItemReturn
from customers.models import CreditDebitNote
from institution.serializers import InstitutionSupportedPaymentOptionSerializer
from transactions.models import Transaction
from utilities.helpers import format_currency

logger = logging.getLogger(__name__)


################################## ITEM RETURN ################################################


def get_item_return_customer_details(item_return):
    """
    Get customer details for the item return
    """
    if not item_return or not item_return.invoice:
        return {
            "name": "No Customer",
            "email": "",
            "phone": "",
            "address": "",
        }

    invoice = item_return.invoice
    customer = invoice.get_invoice_customer()

    if not customer:
        return {
            "name": "No Customer",
            "email": "",
            "phone": "",
            "address": "",
        }

    return {
        "name": customer.customer_name,
        "email": customer.email or "",
        "phone": customer.phone_number or "",
        "address": customer.address or "",
        "tax_id": getattr(customer, "tax_id", "") or "",
    }


def get_institution_details_for_item_return(item_return, request=None):
    """
    Get institution details for the item return
    """
    institution = item_return.get_institution() if item_return else None

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
        except Exception as e:
            logger.debug(f"Error getting institution logo: {str(e)}")
            logo_url = ""

    # Fetch supported payment options
    supported_payment_qs = (
        institution.supported_payment_options.select_related("content_type")
        .filter(is_active=True, is_deleted=False)
        .all()
    )

    from institution.serializers import InstitutionSupportedPaymentOptionSerializer

    serialized_options = []
    if supported_payment_qs.exists():
        try:
            serialized_options = InstitutionSupportedPaymentOptionSerializer(
                supported_payment_qs, many=True
            ).data
        except Exception as e:
            logger.debug(f"Error serializing payment options: {str(e)}")

    # Group by currency code
    grouped_by_currency = {}
    for po in serialized_options:
        details = po.get("details", {})
        currency = details.get("currency")
        currency_code = currency.get("code") if currency else institution.currency.code

        if currency_code not in grouped_by_currency:
            grouped_by_currency[currency_code] = []

        grouped_by_currency[currency_code].append(po)

    return {
        "name": institution.institution_name,
        "email": institution.institution_email or "",
        "phone": institution.first_phone_number
        or institution.second_phone_number
        or "",
        "address": institution.location or "",
        "logo_url": logo_url,
        "website": getattr(institution, "website", "") or "",
        "tax_id": getattr(institution, "tax_id", "") or "",
        "theme_color": institution.theme_color or "#2151ff",
        "supported_payment_options": grouped_by_currency,
    }


def get_item_return_line_items_details(item_return):
    """
    Get returned line items details with optimized queries
    """
    if not item_return:
        return []

    # Prefetch related data efficiently
    line_items_qs = item_return.item_return_items.select_related(
        "goods_issued_note_line__line_item__inventory_item__item_category",
        "return_reason",
    ).all()

    # Get invoice line items in one query
    invoice_line_items = {}
    if item_return.invoice:
        invoice_line_items = {
            item.line_item_id: item
            for item in item_return.invoice.line_items.select_related(
                "unit_of_measure__unit_of_measure"
            ).all()
        }

    line_items = []

    for item in line_items_qs:
        # Base item data
        item_data = {
            "item_name": "Unknown Item",
            "reference_code": "",
            "description": "",
            "quantity": float(item.quantity),
            "unit": "unit",
            "unit_abbreviation": "",
            "unit_price": 0.00,
            "line_total": 0.00,
            "return_reason": "",
            "return_reason_description": "",
            "return_reason_code": "",
        }

        # Get item details from inventory
        if item.item and hasattr(item.item, "inventory_item"):
            inventory_item = item.item.inventory_item
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
                        "sku": getattr(inventory_item, "sku", "") or "",
                    }
                )

        # Get pricing from original invoice line item
        invoice_line_item = invoice_line_items.get(item.item.pk)
        if invoice_line_item:
            unit_price = float(invoice_line_item.unit_price or 0)
            item_data.update(
                {
                    "unit_price": unit_price,
                    "line_total": unit_price * float(item.quantity),
                    "unit": (
                        invoice_line_item.unit_of_measure.unit_of_measure.unit_name
                        if invoice_line_item.unit_of_measure
                        else "unit"
                    ),
                    "unit_abbreviation": (
                        invoice_line_item.unit_of_measure.unit_of_measure.unit_abbreviation
                        if invoice_line_item.unit_of_measure
                        else ""
                    ),
                }
            )

        # Get return reason
        if item.return_reason:
            item_data.update(
                {
                    "return_reason": item.return_reason.return_reason_name,
                    "return_reason_description": item.return_reason.return_reason_description
                    or "",
                }
            )

        line_items.append(item_data)

    return line_items


def calculate_item_return_totals(item_return):
    """
    Calculate totals for the item return with accurate financial calculations
    """
    total_refund_amount = Decimal("0.00")
    total_items = 0
    subtotal_before_tax = Decimal("0.00")
    tax_amount = Decimal("0.00")

    # Get invoice line items in one query
    invoice_line_items = {}
    if item_return.invoice:
        invoice_line_items = {
            item.line_item_id: item for item in item_return.invoice.line_items.all()
        }

    for item in item_return.item_return_items.all():
        quantity = Decimal(str(item.quantity))
        total_items += int(quantity)

        # Get unit price from invoice
        invoice_line_item = invoice_line_items.get(item.item.pk)
        if invoice_line_item and invoice_line_item.unit_price:
            unit_price = Decimal(str(invoice_line_item.unit_price))
            line_total = quantity * unit_price
            total_refund_amount += line_total

            # Calculate tax if applicable
            if hasattr(invoice_line_item, "tax_breakdowns"):
                for tax_breakdown in invoice_line_item.tax_breakdowns.all():
                    tax_amount += Decimal(str(tax_breakdown.tax_amount or 0))

            subtotal_before_tax += line_total

    # Get credit note if exists for CASH_REFUND
    credit_note = None
    if (
        item_return.return_type == "CASH_REFUND"
        and item_return.return_status == "APPROVED"
    ):
        credit_note = (
            CreditDebitNote.objects.filter(
                invoice=item_return.invoice,
                type="CREDIT",
                falls_under="SALES",
                line_items__type="ITEM_RETURN",
                line_items__deleted_at__isnull=True,
            )
            .distinct()
            .first()
        )

    return {
        "subtotal": float(subtotal_before_tax),
        "tax_amount": float(tax_amount),
        "total_refund": float(total_refund_amount),
        "total_items": total_items,
        "credit_note_reference": credit_note.reference_code if credit_note else None,
        "credit_note_amount": float(credit_note.amount) if credit_note else 0.00,
        "credit_note_date": (
            credit_note.issue_date.strftime("%d/%m/%Y")
            if credit_note and credit_note.issue_date
            else None
        ),
        "discount": 0.00,
    }


def get_item_return_invoice_info(item_return):
    """
    Get original invoice information for the return
    """
    invoice = item_return.invoice

    if not invoice:
        return {
            "number": "N/A",
            "date": "N/A",
            "status": "N/A",
            "status_display": "N/A",
            "total_amount": 0.00,
            "customer_reference": "",
            "payment_status": "",
            "payment_status_display": "",
        }

    return {
        "number": invoice.reference_code,
        "date": (
            invoice.issue_date.strftime("%d/%m/%Y") if invoice.issue_date else "N/A"
        ),
        "status": invoice.invoice_status if hasattr(invoice, "invoice_status") else "",
        "status_display": (
            invoice.get_invoice_status_display()
            if hasattr(invoice, "get_invoice_status_display")
            else "N/A"
        ),
        "total_amount": float(invoice.total_amount or 0),
        "net_total": float(invoice.net_total or 0),
        "tax_total": float(invoice.tax_total or 0),
        "customer_reference": getattr(invoice, "customer_reference", "") or "",
        "payment_status": (
            invoice.invoice_payment_status
            if hasattr(invoice, "invoice_payment_status")
            else ""
        ),
        "payment_status_display": (
            invoice.get_invoice_payment_status_display()
            if hasattr(invoice, "get_invoice_payment_status_display")
            else ""
        ),
    }


def get_item_return_payment_info(item_return):
    """
    Get payment information related to the return
    """
    invoice = item_return.invoice

    payment_info = {
        "original_payment_status": "",
        "original_payment_status_display": "",
        "original_amount_paid": 0.00,
        "original_balance": 0.00,
        "refund_method": (
            "Credit Note" if item_return.return_type == "CASH_REFUND" else "Replacement"
        ),
        "refund_method_code": item_return.return_type,
        "credit_note_reference": None,
        "credit_note_date": None,
        "credit_note_amount": 0.00,
        "replacement_transaction_reference": None,
    }

    if invoice:
        payment_info.update(
            {
                "original_payment_status": (
                    invoice.invoice_payment_status
                    if hasattr(invoice, "invoice_payment_status")
                    else ""
                ),
                "original_payment_status_display": (
                    invoice.get_invoice_payment_status_display()
                    if hasattr(invoice, "get_invoice_payment_status_display")
                    else ""
                ),
                "original_amount_paid": (
                    float(invoice.partial_amount_paid)
                    if invoice.partial_amount_paid
                    else 0.00
                ),
                "original_balance": (
                    float(invoice.amount_due) if invoice.amount_due else 0.00
                ),
            }
        )

    # Get credit note if exists for CASH_REFUND
    if (
        item_return.return_type == "CASH_REFUND"
        and item_return.return_status == "APPROVED"
    ):
        credit_note = (
            CreditDebitNote.objects.filter(
                invoice=item_return.invoice,
                type="CREDIT",
                falls_under="SALES",
                line_items__type="ITEM_RETURN",
                line_items__deleted_at__isnull=True,
            )
            .distinct()
            .first()
        )

        if credit_note:
            payment_info.update(
                {
                    "credit_note_reference": credit_note.reference_code,
                    "credit_note_date": (
                        credit_note.issue_date.strftime("%d/%m/%Y")
                        if credit_note.issue_date
                        else None
                    ),
                    "credit_note_amount": float(credit_note.amount or 0),
                }
            )

    # Get replacement transaction if exists
    elif (
        item_return.return_type == "REPLACEMENT"
        and item_return.return_status == "APPROVED"
    ):
        try:
            content_type = ContentType.objects.get_for_model(item_return.__class__)
            replacement_txn = Transaction.objects.filter(
                content_type=content_type,
                object_id=item_return.id,
                transaction_type__type_name="Replacement Issue",
            ).first()

            if replacement_txn:
                payment_info["replacement_transaction_reference"] = (
                    replacement_txn.transaction_reference
                )
        except Exception as e:
            logger.debug(f"Error getting replacement transaction: {str(e)}")

    return payment_info


def get_item_return_currency_info(item_return):
    """
    Get currency information for the item return (from the original invoice)
    """
    currency_info = {
        "code": "UGX",
        "symbol": "UGX",
        "exchange_rate": 1.0,
        "name": "Uganda Shilling",
    }

    try:
        if item_return and item_return.invoice:
            invoice = item_return.invoice
            institution = invoice.get_institution()

            if (
                institution
                and hasattr(institution, "currency")
                and institution.currency
            ):
                currency = institution.currency
                currency_info = {
                    "code": getattr(currency, "code", "UGX"),
                    "symbol": getattr(currency, "symbol", "UGX"),
                    "name": getattr(currency, "name", "Uganda Shilling"),
                    "exchange_rate": 1.0,
                }

            # Check for exchange rate
            rate_info = invoice.determine_rate_currency_used()
            if isinstance(rate_info, tuple) and len(rate_info) > 1 and rate_info[1]:
                currency_info["exchange_rate"] = float(rate_info[1])

    except Exception as e:
        logger.debug(f"Error getting currency info for item return: {str(e)}")

    return currency_info


def get_complete_item_return_data_for_pdf(item_return: ItemReturn, request=None):
    """
    Return complete item return data for PDF generation
    """
    try:
        if not item_return:
            raise ValueError("ItemReturn object is required")

        # Gather all data components
        institution_data = get_institution_details_for_item_return(
            item_return, request=request
        )
        customer_data = get_item_return_customer_details(item_return)
        line_items = get_item_return_line_items_details(item_return)
        totals = calculate_item_return_totals(item_return)
        invoice_info = get_item_return_invoice_info(item_return)
        payment_info = get_item_return_payment_info(item_return)
        currency_info = get_item_return_currency_info(item_return)

        # Get display values for choices
        return_type_display = dict(ItemReturn.RETURN_TYPE_CHOICES).get(
            item_return.return_type, item_return.return_type
        )
        return_status_display = dict(ItemReturn.RETURN_STATUS_CHOICES).get(
            item_return.return_status, item_return.return_status
        )

        # Build complete data structure
        item_return_data = {
            "return_info": {
                "id": item_return.id,
                "number": item_return.return_reference_code or f"IR-{item_return.id}",
                "date": (
                    item_return.return_date.strftime("%d/%m/%Y")
                    if item_return.return_date
                    else timezone.now().strftime("%d/%m/%Y")
                ),
                "datetime": (
                    item_return.return_date.strftime("%d/%m/%Y %H:%M")
                    if item_return.return_date
                    else ""
                ),
                "return_type": item_return.return_type,
                "return_type_display": return_type_display,
                "return_status": item_return.return_status,
                "return_status_display": return_status_display,
                "is_inventory_reversed": item_return.is_inventory_reversed,
                "notes": item_return.notes or "",
            },
            "currency": currency_info,
            "institution": institution_data,
            "customer": customer_data,
            "original_invoice": invoice_info,
            "line_items": line_items,
            "totals": totals,
            "payment": payment_info,
            "metadata": {
                "created_at": (
                    item_return.created_at.strftime("%d/%m/%Y %H:%M")
                    if item_return.created_at
                    else ""
                ),
                "created_by": (
                    str(item_return.created_by) if item_return.created_by else ""
                ),
                "updated_at": (
                    item_return.updated_at.strftime("%d/%m/%Y %H:%M")
                    if hasattr(item_return, "updated_at") and item_return.updated_at
                    else ""
                ),
                "updated_by": (
                    str(item_return.updated_by)
                    if hasattr(item_return, "updated_by") and item_return.updated_by
                    else ""
                ),
                "is_active": getattr(item_return, "is_active", True),
                "is_deleted": getattr(item_return, "is_deleted", False),
            },
        }

        return item_return_data

    except Exception as e:
        logger.error(
            f"Error getting complete item return data for PDF: {str(e)}", exc_info=True
        )
        raise


def generate_item_return_pdf_response(item_return_data, request=None):
    """
    Generate PDF response for item return
    """
    try:
        html = render_to_string("_item_return.html", item_return_data, request=request)
        pdf = HTML(string=html).write_pdf()

        response = HttpResponse(pdf, content_type="application/pdf")

        # Clean filename
        number = (
            item_return_data["return_info"]["number"]
            .replace("/", "-")
            .replace("\\", "-")
        )
        filename = f"Item_Return_{number}.pdf"
        response["Content-Disposition"] = f'attachment; filename="{filename}"'

        # Cache control headers
        response["Cache-Control"] = "no-cache, no-store, must-revalidate"
        response["Pragma"] = "no-cache"
        response["Expires"] = "0"

        return response

    except Exception as e:
        logger.error(f"Error generating item return PDF: {str(e)}", exc_info=True)
        raise


################################## CREDIT/DEBIT NOTE ################################################


def get_credit_debit_note_customer_details(credit_debit_note):
    """
    Get customer details for credit/debit note (SALES) using invoice relationship
    """
    if credit_debit_note.falls_under == "SALES" and credit_debit_note.invoice:
        invoice = credit_debit_note.invoice

        # Check if invoice has customer data in the serializer representation
        if hasattr(invoice, "customer") and invoice.customer:
            customer = invoice.customer
            return {
                "name": (
                    customer.customer_name
                    if hasattr(customer, "customer_name")
                    else str(customer)
                ),
                "email": getattr(customer, "email", "") or "",
                "phone": getattr(customer, "phone_number", "") or "",
                "address": getattr(customer, "address", "") or "",
                "tax_id": getattr(customer, "tax_id", "") or "",
                "customer_type": "Customer",
            }
        else:
            # Try to get customer via get_invoice_customer method
            try:
                customer = invoice.get_invoice_customer()
                if customer:
                    return {
                        "name": customer.customer_name,
                        "email": customer.email or "",
                        "phone": customer.phone_number or "",
                        "address": customer.address or "",
                        "tax_id": getattr(customer, "tax_id", "") or "",
                        "customer_type": "Customer",
                    }
            except:
                pass

    return {
        "name": "No Customer",
        "email": "",
        "phone": "",
        "address": "",
        "tax_id": "",
        "customer_type": "N/A",
    }


def get_credit_debit_note_vendor_details(credit_debit_note):
    """
    Get vendor details for credit/debit note (PURCHASE)
    """
    if credit_debit_note.falls_under == "PURCHASE" and credit_debit_note.bill:
        bill = credit_debit_note.bill
        vendor = bill.vendor if hasattr(bill, "vendor") and bill.vendor else None

        if vendor:
            return {
                "name": (
                    vendor.vendor_name
                    if hasattr(vendor, "vendor_name")
                    else str(vendor)
                ),
                "email": getattr(vendor, "email", "") or "",
                "phone": getattr(vendor, "phone_number", "") or "",
                "address": getattr(vendor, "address", "") or "",
                "tax_id": getattr(vendor, "tax_id", "") or "",
                "vendor_type": "Vendor",
            }

    return {
        "name": "No Vendor",
        "email": "",
        "phone": "",
        "address": "",
        "tax_id": "",
        "vendor_type": "N/A",
    }


def get_credit_debit_note_counterparty_details(credit_debit_note):
    """
    Get appropriate counterparty details based on falls_under
    """
    if credit_debit_note.falls_under == "SALES":
        return get_credit_debit_note_customer_details(credit_debit_note)
    else:
        return get_credit_debit_note_vendor_details(credit_debit_note)


def get_institution_details_for_credit_debit_note(credit_debit_note, request=None):
    """
    Get institution details for credit/debit note
    """
    institution = credit_debit_note.get_institution()

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

    serialized_options = []
    if supported_payment_qs.exists():
        try:
            serialized_options = InstitutionSupportedPaymentOptionSerializer(
                supported_payment_qs, many=True
            ).data
        except Exception as e:
            logger.debug(f"Error serializing payment options: {str(e)}")

    # Group by currency code
    grouped_by_currency = {}
    for po in serialized_options:
        details = po.get("details", {})
        currency = details.get("currency")
        currency_code = currency.get("code") if currency else institution.currency.code

        if currency_code not in grouped_by_currency:
            grouped_by_currency[currency_code] = []

        grouped_by_currency[currency_code].append(po)

    return {
        "name": institution.institution_name,
        "email": institution.institution_email or "",
        "phone": institution.first_phone_number
        or institution.second_phone_number
        or "",
        "address": institution.location or "",
        "logo_url": logo_url,
        "website": getattr(institution, "website", "") or "",
        "tax_id": getattr(institution, "tax_id", "") or "",
        "theme_color": institution.theme_color or "#2151ff",
        "supported_payment_options": grouped_by_currency,
    }


def get_credit_debit_note_line_items_details(credit_debit_note):
    """
    Get line items from the original invoice for credit/debit note
    with full details including taxes, discounts, and pricing
    """
    line_items = []

    if credit_debit_note.falls_under == "SALES" and credit_debit_note.invoice:
        invoice = credit_debit_note.invoice

        # Access line_items from the invoice
        if hasattr(invoice, "line_items") and invoice.line_items.exists():
            for item in invoice.line_items.all():
                # Base item data
                item_data = {
                    "id": item.id if hasattr(item, "id") else None,
                    "reference_code": getattr(item, "reference_code", ""),
                    "item_name": "Unknown Item",
                    "reference_code": "",
                    "description": "",
                    "quantity": (
                        float(item.quantity) if hasattr(item, "quantity") else 0
                    ),
                    "unit": "unit",
                    "unit_abbreviation": "",
                    "unit_price": (
                        float(item.unit_price) if hasattr(item, "unit_price") else 0
                    ),
                    "line_total": (
                        float(item.line_total) if hasattr(item, "line_total") else 0
                    ),
                    "discount_amount": 0.00,
                    "discount_percentage": 0.00,
                    "taxes": [],
                    "tax_total": 0.00,
                    "net_line_total": 0.00,
                    "item_type": "",
                    "item_category": "",
                    "sku": "",
                }

                # Get branch item details
                if hasattr(item, "line_item") and item.line_item:
                    branch_item = item.line_item

                    # Handle BranchInventoryItem
                    if (
                        hasattr(branch_item, "inventory_item")
                        and branch_item.inventory_item
                    ):
                        inventory_item = branch_item.inventory_item
                        item_data.update(
                            {
                                "item_name": getattr(
                                    inventory_item, "item_name", "Unknown Item"
                                ),
                                "reference_code": getattr(
                                    inventory_item, "reference_code", ""
                                )
                                or "",
                                "item_type": getattr(inventory_item, "item_type", ""),
                                "sku": getattr(inventory_item, "sku", "") or "",
                                "item_category": (
                                    getattr(inventory_item.item_category, "name", "")
                                    if hasattr(inventory_item, "item_category")
                                    and inventory_item.item_category
                                    else ""
                                ),
                            }
                        )

                    # Handle when branch_item is a dict (from serializer)
                    elif isinstance(branch_item, dict):
                        item_data.update(
                            {
                                "item_name": branch_item.get(
                                    "item_name", "Unknown Item"
                                ),
                                "reference_code": branch_item.get("reference_code", ""),
                                "item_type": branch_item.get("item_type", ""),
                            }
                        )

                # Get unit of measure details
                if hasattr(item, "unit_of_measure") and item.unit_of_measure:
                    uom = item.unit_of_measure

                    # Handle UnitOfMeasure model instance
                    if hasattr(uom, "unit_of_measure"):
                        unit = uom.unit_of_measure
                        item_data.update(
                            {
                                "unit": getattr(unit, "unit_name", "unit"),
                                "unit_abbreviation": getattr(
                                    unit, "unit_abbreviation", ""
                                )
                                or "",
                            }
                        )
                    # Handle direct unit_of_measure object
                    elif hasattr(uom, "unit_name"):
                        item_data.update(
                            {
                                "unit": uom.unit_name,
                                "unit_abbreviation": getattr(
                                    uom, "unit_abbreviation", ""
                                )
                                or "",
                            }
                        )
                    # Handle dict from serializer
                    elif isinstance(uom, dict):
                        item_data.update(
                            {
                                "unit": uom.get("unit_name", "unit"),
                                "unit_abbreviation": uom.get("unit_abbreviation", ""),
                            }
                        )

                # Get discount information
                if hasattr(item, "discount_amount") and item.discount_amount:
                    item_data["discount_amount"] = float(item.discount_amount)
                if hasattr(item, "discount_percentage") and item.discount_percentage:
                    item_data["discount_percentage"] = float(item.discount_percentage)

                # Get tax breakdowns
                tax_total = 0.00
                if hasattr(item, "tax_breakdowns"):
                    try:
                        for tax_breakdown in item.tax_breakdowns.all():
                            if hasattr(tax_breakdown, "tax") and tax_breakdown.tax:
                                tax = tax_breakdown.tax
                                tax_amount = float(tax_breakdown.tax_amount or 0)
                                tax_total += tax_amount

                                item_data["taxes"].append(
                                    {
                                        "name": getattr(tax, "tax_name", "Tax"),
                                        "rate": (
                                            float(tax.total_rate_value)
                                            if tax.total_rate_value is not None
                                            else None
                                        ),
                                        "amount": tax_amount,
                                        "tax_code": getattr(tax, "tax_code", ""),
                                    }
                                )
                    except Exception as e:
                        logger.debug(f"Error getting tax breakdowns: {str(e)}")

                item_data["tax_total"] = tax_total

                # Calculate net line total (after discounts, before tax)
                if hasattr(item, "net_line_total") and item.net_line_total:
                    item_data["net_line_total"] = float(item.net_line_total)
                else:
                    # Calculate if not available
                    discount_amount = item_data["discount_amount"]
                    item_data["net_line_total"] = (
                        item_data["line_total"] - discount_amount
                    )

                line_items.append(item_data)

    return line_items


def get_credit_debit_note_affected_line_items(credit_debit_note):
    """
    Get only the line items that are affected by this credit/debit note
    For product returns, this would be the specific returned items
    """
    affected_items = []

    # Product returns are represented by active ITEM_RETURN note lines.
    if (
        credit_debit_note.falls_under == "SALES"
        and credit_debit_note.type == "CREDIT"
        and credit_debit_note._has_item_line_items()
    ):

        # Check if this credit note was created from an item return
        try:
            item_return = ItemReturn.objects.filter(
                invoice=credit_debit_note.invoice,
                return_type="CASH_REFUND",
                return_status="APPROVED",
            ).first()

            if item_return:
                # Get the specific returned items
                for return_item in item_return.item_return_items.all():
                    # Find corresponding invoice line item
                    invoice_line = credit_debit_note.invoice.line_items.filter(
                        line_item=return_item.item
                    ).first()

                    if invoice_line:
                        item_data = {
                            "id": (
                                invoice_line.id if hasattr(invoice_line, "id") else None
                            ),
                            "item_name": "Unknown Item",
                            "reference_code": "",
                            "quantity_invoiced": (
                                float(invoice_line.quantity)
                                if hasattr(invoice_line, "quantity")
                                else 0
                            ),
                            "quantity_returned": float(return_item.quantity),
                            "unit_price": (
                                float(invoice_line.unit_price)
                                if hasattr(invoice_line, "unit_price")
                                else 0
                            ),
                            "refund_amount": (
                                float(invoice_line.unit_price * return_item.quantity)
                                if hasattr(invoice_line, "unit_price")
                                else 0
                            ),
                            "return_reason": getattr(
                                return_item.return_reason, "return_reason_name", ""
                            ),
                            "return_reason_description": getattr(
                                return_item.return_reason,
                                "return_reason_description",
                                "",
                            ),
                            "unit": "unit",
                            "unit_abbreviation": "",
                        }

                        # Get inventory item details
                        if (
                            hasattr(return_item.item, "inventory_item")
                            and return_item.item.inventory_item
                        ):
                            inventory_item = return_item.item.inventory_item
                            item_data.update(
                                {
                                    "item_name": getattr(
                                        inventory_item, "item_name", "Unknown Item"
                                    ),
                                    "reference_code": getattr(
                                        inventory_item, "reference_code", ""
                                    )
                                    or "",
                                    "item_type": getattr(
                                        inventory_item, "item_type", ""
                                    ),
                                    "sku": getattr(inventory_item, "sku", "") or "",
                                }
                            )

                        # Get unit details
                        if (
                            hasattr(invoice_line, "unit_of_measure")
                            and invoice_line.unit_of_measure
                        ):
                            uom = invoice_line.unit_of_measure
                            if hasattr(uom, "unit_of_measure"):
                                unit = uom.unit_of_measure
                                item_data.update(
                                    {
                                        "unit": getattr(unit, "unit_name", "unit"),
                                        "unit_abbreviation": getattr(
                                            unit, "unit_abbreviation", ""
                                        )
                                        or "",
                                    }
                                )
                            elif hasattr(uom, "unit_name"):
                                item_data.update(
                                    {
                                        "unit": uom.unit_name,
                                        "unit_abbreviation": getattr(
                                            uom, "unit_abbreviation", ""
                                        )
                                        or "",
                                    }
                                )

                        affected_items.append(item_data)
        except Exception as e:
            logger.debug(f"Error getting item return details: {str(e)}")

    # If no specific affected items found, return all line items
    if not affected_items:
        return get_credit_debit_note_line_items_details(credit_debit_note)

    return affected_items


def get_credit_debit_note_reference_document_info(credit_debit_note):
    """
    Get original reference document information (Invoice or Bill)
    using serializer data structure
    """
    reference_info = {
        "type": "",
        "number": "",
        "date": "",
        "total_amount": 0.00,
        "subtotal": 0.00,
        "tax_total": 0.00,
        "status": "",
        "status_display": "",
        "type_code": "",
        "payment_status": "",
        "payment_status_display": "",
        "line_items": [],
        "total_line_items": 0,
    }

    if credit_debit_note.falls_under == "SALES" and credit_debit_note.invoice:
        invoice = credit_debit_note.invoice

        # Handle invoice date formatting
        issue_date = ""
        if hasattr(invoice, "issue_date") and invoice.issue_date:
            if hasattr(invoice.issue_date, "strftime"):
                issue_date = invoice.issue_date.strftime("%d/%m/%Y")
            else:
                issue_date = str(invoice.issue_date)

        # Get invoice status display
        status_display = ""
        if hasattr(invoice, "get_invoice_status_display"):
            try:
                status_display = invoice.get_invoice_status_display()
            except:
                status_display = (
                    invoice.invoice_status if hasattr(invoice, "invoice_status") else ""
                )
        else:
            status_display = getattr(invoice, "invoice_status", "")

        # Get payment status display
        payment_status_display = ""
        if hasattr(invoice, "get_invoice_payment_status_display"):
            try:
                payment_status_display = invoice.get_invoice_payment_status_display()
            except:
                payment_status_display = (
                    invoice.invoice_payment_status
                    if hasattr(invoice, "invoice_payment_status")
                    else ""
                )
        else:
            payment_status_display = getattr(invoice, "invoice_payment_status", "")

        reference_info.update(
            {
                "type": "Invoice",
                "type_code": "INVOICE",
                "number": (
                    invoice.reference_code if hasattr(invoice, "reference_code") else ""
                ),
                "date": issue_date,
                "total_amount": (
                    float(invoice.total_amount or 0)
                    if hasattr(invoice, "total_amount")
                    else 0
                ),
                "subtotal": (
                    float(invoice.net_total or 0)
                    if hasattr(invoice, "net_total")
                    else 0
                ),
                "tax_total": (
                    float(invoice.tax_total or 0)
                    if hasattr(invoice, "tax_total")
                    else 0
                ),
                "status": (
                    invoice.invoice_status if hasattr(invoice, "invoice_status") else ""
                ),
                "status_display": status_display,
                "payment_status": (
                    invoice.invoice_payment_status
                    if hasattr(invoice, "invoice_payment_status")
                    else ""
                ),
                "payment_status_display": payment_status_display,
                "due_date": (
                    invoice.due_date.strftime("%d/%m/%Y")
                    if hasattr(invoice, "due_date") and invoice.due_date
                    else ""
                ),
                "customer_reference": getattr(invoice, "customer_reference", "") or "",
            }
        )

    elif credit_debit_note.falls_under == "PURCHASE" and credit_debit_note.bill:
        bill = credit_debit_note.bill

        # Handle bill date formatting
        issue_date = ""
        if hasattr(bill, "issue_date") and bill.issue_date:
            if hasattr(bill.issue_date, "strftime"):
                issue_date = bill.issue_date.strftime("%d/%m/%Y")
            else:
                issue_date = str(bill.issue_date)

        # Get bill status display
        status_display = ""
        if hasattr(bill, "get_status_display"):
            try:
                status_display = bill.get_status_display()
            except:
                status_display = bill.status if hasattr(bill, "status") else ""
        else:
            status_display = getattr(bill, "status", "")

        reference_info.update(
            {
                "type": "Bill",
                "type_code": "BILL",
                "number": (
                    bill.bill_reference if hasattr(bill, "bill_reference") else ""
                ),
                "date": issue_date,
                "total_amount": (
                    float(bill.total_amount or 0)
                    if hasattr(bill, "total_amount")
                    else 0
                ),
                "subtotal": (
                    float(bill.subtotal or 0) if hasattr(bill, "subtotal") else 0
                ),
                "tax_total": (
                    float(bill.tax_total or 0) if hasattr(bill, "tax_total") else 0
                ),
                "status": bill.status if hasattr(bill, "status") else "",
                "status_display": status_display,
                "due_date": (
                    bill.due_date.strftime("%d/%m/%Y")
                    if hasattr(bill, "due_date") and bill.due_date
                    else ""
                ),
            }
        )

    return reference_info


def get_credit_debit_note_price_effect_details(credit_debit_note):
    """
    Get price effect details for credit/debit note
    """
    price_effect = credit_debit_note.price_effects.first()

    if price_effect:
        return {
            "amount_before": float(price_effect.amount_before),
            "amount_after": float(price_effect.amount_after),
            "difference": float(price_effect.amount_after - price_effect.amount_before),
            "difference_percentage": (
                round(
                    (price_effect.amount_after - price_effect.amount_before)
                    / price_effect.amount_before
                    * 100,
                    2,
                )
                if price_effect.amount_before and price_effect.amount_before != 0
                else 0
            ),
            "description": price_effect.description or "",
        }

    return {
        "amount_before": 0.00,
        "amount_after": 0.00,
        "difference": 0.00,
        "difference_percentage": 0.00,
        "description": "",
    }


def calculate_credit_debit_note_totals(credit_debit_note, currency_prefix=""):
    """
    Calculate and format credit/debit note totals.
    """
    amount = Decimal(str(credit_debit_note.amount or 0))

    # Get original document amount
    original_amount = Decimal("0.00")
    original_subtotal = Decimal("0.00")
    original_tax_total = Decimal("0.00")

    if credit_debit_note.falls_under == "SALES" and credit_debit_note.invoice:
        invoice = credit_debit_note.invoice
        if hasattr(invoice, "total_amount"):
            original_amount = Decimal(str(invoice.total_amount or 0))
        if hasattr(invoice, "net_total"):
            original_subtotal = Decimal(str(invoice.net_total or 0))
        if hasattr(invoice, "tax_total"):
            original_tax_total = Decimal(str(invoice.tax_total or 0))

    elif credit_debit_note.falls_under == "PURCHASE" and credit_debit_note.bill:
        bill = credit_debit_note.bill
        if hasattr(bill, "total_amount"):
            original_amount = Decimal(str(bill.total_amount or 0))
        if hasattr(bill, "subtotal"):
            original_subtotal = Decimal(str(bill.subtotal or 0))
        if hasattr(bill, "tax_total"):
            original_tax_total = Decimal(str(bill.tax_total or 0))

    # Calculate new balance
    if credit_debit_note.type == "CREDIT":
        new_balance = original_amount - amount
        effect = "Reduction"
        effect_sign = "-"
    else:  # DEBIT
        new_balance = original_amount + amount
        effect = "Increase"
        effect_sign = "+"

    return {
        "amount": amount,
        "formatted_amount": format_currency(amount, currency_prefix),
        "original_amount": original_amount,
        "formatted_original": format_currency(original_amount, currency_prefix),
        "original_subtotal": original_subtotal,
        "formatted_original_subtotal": format_currency(
            original_subtotal, currency_prefix
        ),
        "original_tax_total": original_tax_total,
        "formatted_original_tax_total": format_currency(
            original_tax_total, currency_prefix
        ),
        "new_balance": new_balance,
        "formatted_new_balance": format_currency(new_balance, currency_prefix),
        "effect": effect,
        "effect_sign": effect_sign,
        "effect_type": credit_debit_note.type,
    }


def get_credit_debit_note_currency_info(credit_debit_note):
    """
    Get currency information from the reference document or institution
    """
    currency_info = {
        "code": "UGX",
        "symbol": "UGX",
        "exchange_rate": 1.0,
        "name": "Uganda Shilling",
    }

    try:
        # Check if invoice has currency field
        if credit_debit_note.falls_under == "SALES" and credit_debit_note.invoice:
            invoice = credit_debit_note.invoice

            # Check for currency attribute
            if hasattr(invoice, "currency"):
                if isinstance(invoice.currency, dict):
                    currency_info = {
                        "code": invoice.currency.get("code", "UGX"),
                        "symbol": invoice.currency.get("symbol", "UGX"),
                        "name": invoice.currency.get("name", "Uganda Shilling"),
                        "exchange_rate": (
                            float(invoice.currency.get("rate", 1.0))
                            if invoice.currency.get("rate")
                            else 1.0
                        ),
                    }
                else:
                    currency_info["code"] = str(invoice.currency)
                    currency_info["symbol"] = str(invoice.currency)

            # Get exchange rate
            if hasattr(invoice, "rate") and invoice.rate:
                currency_info["exchange_rate"] = float(invoice.rate)
            elif hasattr(invoice, "determine_rate_currency_used"):
                try:
                    rate_info = invoice.determine_rate_currency_used()
                    if (
                        isinstance(rate_info, tuple)
                        and len(rate_info) > 1
                        and rate_info[1]
                    ):
                        currency_info["exchange_rate"] = float(rate_info[1])
                except:
                    pass

        # For purchase, check bill currency
        elif credit_debit_note.falls_under == "PURCHASE" and credit_debit_note.bill:
            bill = credit_debit_note.bill
            if hasattr(bill, "currency") and bill.currency:
                currency_info["code"] = str(bill.currency)
                currency_info["symbol"] = str(bill.currency)
            if hasattr(bill, "exchange_rate") and bill.exchange_rate:
                currency_info["exchange_rate"] = float(bill.exchange_rate)

        # Fallback to institution currency
        else:
            institution = credit_debit_note.get_institution()
            if (
                institution
                and hasattr(institution, "currency")
                and institution.currency
            ):
                currency = institution.currency
                currency_info = {
                    "code": getattr(currency, "code", "UGX"),
                    "symbol": getattr(currency, "symbol", "UGX"),
                    "name": getattr(currency, "name", "Uganda Shilling"),
                    "exchange_rate": 1.0,
                }

    except Exception as e:
        logger.debug(f"Error getting currency info for credit/debit note: {str(e)}")

    return currency_info


def get_complete_credit_debit_note_data_for_pdf(
    credit_debit_note: CreditDebitNote, request=None
):
    """
    Return complete credit/debit note data for PDF generation
    Matches the structure shown in your sample response
    """
    try:
        if not credit_debit_note:
            raise ValueError("CreditDebitNote object is required")

        # Gather all data components
        institution_data = get_institution_details_for_credit_debit_note(
            credit_debit_note, request=request
        )
        counterparty_data = get_credit_debit_note_counterparty_details(
            credit_debit_note
        )
        reference_document = get_credit_debit_note_reference_document_info(
            credit_debit_note
        )
        currency_info = get_credit_debit_note_currency_info(credit_debit_note)
        currency_prefix = f"{currency_info['code']} "
        totals = calculate_credit_debit_note_totals(credit_debit_note, currency_prefix)
        price_effect = get_credit_debit_note_price_effect_details(credit_debit_note)

        reference_document["formatted_total_amount"] = format_currency(
            reference_document.get("total_amount"), currency_prefix
        )
        price_effect["formatted_amount_before"] = format_currency(
            price_effect.get("amount_before"), currency_prefix
        )
        price_effect["formatted_amount_after"] = format_currency(
            price_effect.get("amount_after"), currency_prefix
        )
        price_effect["formatted_difference"] = format_currency(
            price_effect.get("difference"), currency_prefix
        )

        is_product_return = credit_debit_note._has_item_line_items()

        # Get line items - use affected items for product returns, otherwise all items
        if (
            credit_debit_note.falls_under == "SALES"
            and credit_debit_note.type == "CREDIT"
            and is_product_return
        ):
            line_items = get_credit_debit_note_affected_line_items(credit_debit_note)
        else:
            line_items = get_credit_debit_note_line_items_details(credit_debit_note)

        for item in line_items:
            item["formatted_unit_price"] = format_currency(
                item.get("unit_price"), currency_prefix
            )
            item["formatted_amount"] = format_currency(
                item.get("refund_amount", item.get("line_total", 0)),
                currency_prefix,
            )

        # Add line items to reference document
        reference_document["line_items"] = line_items
        reference_document["total_line_items"] = len(line_items)

        # Get display values for choices
        type_display = dict(CreditDebitNote.CREDIT_DEBIT_TYPE_CHOICES).get(
            credit_debit_note.type, credit_debit_note.type
        )
        falls_under_display = dict(CreditDebitNote.FALLS_UNDER_CHOICES).get(
            credit_debit_note.falls_under, credit_debit_note.falls_under
        )
        status_display = dict(CreditDebitNote.STATUS_CHOICES).get(
            credit_debit_note.status, credit_debit_note.status
        )

        reason = "PRODUCT_RETURN" if is_product_return else "GENERAL_ADJUSTMENT"
        reason_display = "Product Return" if is_product_return else "General Adjustment"

        # Format date fields
        issue_date = ""
        issue_datetime = ""
        if credit_debit_note.issue_date:
            if hasattr(credit_debit_note.issue_date, "strftime"):
                issue_date = credit_debit_note.issue_date.strftime("%d/%m/%Y")
                issue_datetime = credit_debit_note.issue_date.strftime("%d/%m/%Y %H:%M")
            else:
                issue_date = str(credit_debit_note.issue_date)
                issue_datetime = str(credit_debit_note.issue_date)

        created_at = ""
        if credit_debit_note.created_at:
            if hasattr(credit_debit_note.created_at, "strftime"):
                created_at = credit_debit_note.created_at.strftime("%d/%m/%Y %H:%M")
            else:
                created_at = str(credit_debit_note.created_at)[:16].replace("-", "/")

        updated_at = ""
        if hasattr(credit_debit_note, "updated_at") and credit_debit_note.updated_at:
            if hasattr(credit_debit_note.updated_at, "strftime"):
                updated_at = credit_debit_note.updated_at.strftime("%d/%m/%Y %H:%M")
            else:
                updated_at = str(credit_debit_note.updated_at)[:16].replace("-", "/")

        # Calculate summary statistics
        total_quantity = 0
        subtotal = 0
        tax_total = 0
        discount_total = 0

        for item in line_items:
            total_quantity += item.get("quantity", 0) or item.get(
                "quantity_returned", 0
            )
            subtotal += item.get("line_total", 0) or item.get("refund_amount", 0)
            tax_total += item.get("tax_total", 0)
            discount_total += item.get("discount_amount", 0)

        # Build complete data structure matching your sample
        credit_debit_note_data = {
            "document_type": "credit_debit_note",
            "document_type_display": f"{type_display} Note",
            "note_info": {
                "id": credit_debit_note.id,
                "number": credit_debit_note.reference_code
                or f"CD-N-{credit_debit_note.id}",
                "date": issue_date,
                "datetime": issue_datetime,
                "type": credit_debit_note.type,
                "type_display": type_display,
                "falls_under": credit_debit_note.falls_under,
                "falls_under_display": falls_under_display,
                "status": credit_debit_note.status,
                "status_display": status_display,
                "reason": reason,
                "reason_display": reason_display,
                "amount": float(credit_debit_note.amount or 0),
                "formatted_amount": totals["formatted_amount"],
                "description": credit_debit_note.description or "",
            },
            "currency": currency_info,
            "institution": institution_data,
            "counterparty": counterparty_data,
            "reference_document": reference_document,
            "price_effect": price_effect,
            "totals": totals,
            "line_items": line_items,
            "metadata": {
                "created_at": created_at,
                "created_by": (
                    str(credit_debit_note.created_by)
                    if credit_debit_note.created_by
                    else ""
                ),
                "updated_at": updated_at,
                "updated_by": (
                    str(credit_debit_note.updated_by)
                    if hasattr(credit_debit_note, "updated_by")
                    and credit_debit_note.updated_by
                    else ""
                ),
                "is_active": getattr(credit_debit_note, "is_active", True),
                "is_deleted": getattr(credit_debit_note, "is_deleted", False),
            },
            # Summary statistics
            "summary": {
                "total_items": len(line_items),
                "total_quantity": total_quantity,
                "subtotal": subtotal,
                "tax_total": tax_total,
                "discount_total": discount_total,
                "formatted_subtotal": format_currency(subtotal, currency_prefix),
                "formatted_tax_total": format_currency(tax_total, currency_prefix),
            },
        }

        return credit_debit_note_data

    except Exception as e:
        logger.error(
            f"Error getting complete credit/debit note data for PDF: {str(e)}",
            exc_info=True,
        )
        raise


def generate_credit_debit_note_pdf_response(credit_debit_note_data, request=None):
    """
    Generate PDF response for credit/debit note
    """
    try:
        html = render_to_string(
            "_credit_note.html", credit_debit_note_data, request=request
        )
        pdf = HTML(string=html).write_pdf()

        response = HttpResponse(pdf, content_type="application/pdf")

        # Clean filename
        note_type = credit_debit_note_data["note_info"]["type_display"]
        number = (
            credit_debit_note_data["note_info"]["number"]
            .replace("/", "-")
            .replace("\\", "-")
        )
        filename = f"{note_type}_Note_{number}.pdf"
        response["Content-Disposition"] = f'attachment; filename="{filename}"'

        # Cache control headers
        response["Cache-Control"] = "no-cache, no-store, must-revalidate"
        response["Pragma"] = "no-cache"
        response["Expires"] = "0"

        return response

    except Exception as e:
        logger.error(f"Error generating credit/debit note PDF: {str(e)}", exc_info=True)
        raise
