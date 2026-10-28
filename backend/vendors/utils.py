from decimal import Decimal

from .models import VendorBillLineItem, VendorBillOtherExpenses
from taxation.service import SalesDocumentTaxService


def apply_taxes(
    line_item_instance,
    applicable_taxes,
    gross_amount,
    source_line=None,
):
    base_amount = Decimal(str(gross_amount)).quantize(Decimal("0.01"))
    inherited_source_line = source_line if not applicable_taxes else None
    explicit_taxes = applicable_taxes or None
    breakdowns = SalesDocumentTaxService.apply_line_taxes(
        line=line_item_instance,
        source_line=inherited_source_line,
        applicable_taxes=(None if inherited_source_line else explicit_taxes),
        default_tax_field="purchase_tax",
    )

    inclusive_tax = sum(
        (breakdown.tax_amount for breakdown in breakdowns if breakdown.is_inclusive),
        Decimal("0.00"),
    )
    exclusive_tax = sum(
        (
            breakdown.tax_amount
            for breakdown in breakdowns
            if not breakdown.is_inclusive
        ),
        Decimal("0.00"),
    )

    total_tax = inclusive_tax + exclusive_tax
    net_amount = base_amount - inclusive_tax
    gross_total = base_amount + exclusive_tax

    return (
        total_tax.quantize(Decimal("0.01")),
        net_amount.quantize(Decimal("0.01")),
        gross_total.quantize(Decimal("0.01")),
    )


def create_line_items(
    vendor_bill, inventory_items, fixed_asset_items, other_items, canonical_rate
):
    total_net = Decimal("0.00")
    total_tax = Decimal("0.00")
    total_gross = Decimal("0.00")

    def find_source_line(item_type, item_data):
        if not vendor_bill.purchase_order_id:
            return None

        source_lines = vendor_bill.purchase_order.line_items.filter(item_type=item_type)

        if item_type == "inventory":
            return source_lines.filter(
                inventory_item=item_data["line_item"],
                unit_of_measure=item_data["unit_of_measure"],
            ).first()

        if item_type == "fixed_asset":
            return source_lines.filter(
                asset_category=item_data["asset_category"],
                line_item_name=item_data["line_item"],
            ).first()

        return source_lines.filter(
            line_item_name=item_data["line_item"],
            other_unit_of_measure=item_data["unit_of_measure"],
        ).first()

    for item_data in inventory_items:
        unit_price = item_data["unit_price"]
        line_total = unit_price * item_data["quantity"]
        line_item = VendorBillLineItem.objects.create(
            bill=vendor_bill,
            item_type="inventory",
            inventory_item=item_data["line_item"],
            unit_of_measure=item_data["unit_of_measure"],
            quantity=item_data["quantity"],
            unit_price=unit_price,
            line_total=line_total,
        )
        tax_amount, net_amount, gross_amount = apply_taxes(
            line_item,
            None,
            line_total,
        )
        total_tax += tax_amount
        total_net += net_amount
        total_gross += gross_amount

    for item_data in fixed_asset_items:
        applicable_taxes = item_data.pop("applicable_taxes", [])
        unit_price = item_data["unit_price"]
        line_total = unit_price * item_data["quantity"]
        line_item = VendorBillLineItem.objects.create(
            bill=vendor_bill,
            item_type="fixed_asset",
            asset_category=item_data["asset_category"],
            line_item_name=item_data["line_item"],
            quantity=item_data["quantity"],
            unit_price=unit_price,
            line_total=line_total,
        )
        tax_amount, net_amount, gross_amount = apply_taxes(
            line_item,
            applicable_taxes,
            line_total,
            source_line=find_source_line("fixed_asset", item_data),
        )
        total_tax += tax_amount
        total_net += net_amount
        total_gross += gross_amount

    for item_data in other_items:
        applicable_taxes = item_data.pop("applicable_taxes", [])
        unit_price = item_data["unit_price"]
        line_total = unit_price * item_data["quantity"]
        line_item = VendorBillLineItem.objects.create(
            bill=vendor_bill,
            item_type="other",
            line_item_name=item_data["line_item"],
            other_asset_unit_of_measure=item_data["unit_of_measure"],
            quantity=item_data["quantity"],
            unit_price=unit_price,
            line_total=line_total,
        )
        tax_amount, net_amount, gross_amount = apply_taxes(
            line_item,
            applicable_taxes,
            line_total,
            source_line=find_source_line("other", item_data),
        )
        total_tax += tax_amount
        total_net += net_amount
        total_gross += gross_amount

    return total_net, total_tax, total_gross


def create_other_expenses(vendor_bill, expenses_data, canonical_rate):
    total_net = Decimal("0.00")
    total_tax = Decimal("0.00")
    total_gross = Decimal("0.00")

    for expense_data in expenses_data:
        applicable_taxes = expense_data.pop("applicable_taxes", [])
        amount = expense_data["amount"]
        expense = VendorBillOtherExpenses.objects.create(
            bill=vendor_bill,
            expense_name=expense_data["expense_name"],
            amount=amount,
            account_to_record_expense=expense_data.get("account_to_record_expense"),
        )
        tax_amount, net_amount, gross_amount = apply_taxes(
            expense, applicable_taxes, amount
        )
        total_tax += tax_amount
        total_net += net_amount
        total_gross += gross_amount

    return total_net, total_tax, total_gross


def recalculate_and_save_bill_totals(
    vendor_bill, line_net, line_tax, line_gross, exp_net, exp_tax, exp_gross
):
    vendor_bill.total_net_amount = (line_net + exp_net).quantize(Decimal("0.01"))
    vendor_bill.total_tax_amount = (line_tax + exp_tax).quantize(Decimal("0.01"))
    vendor_bill.total_amount = (line_gross + exp_gross).quantize(Decimal("0.01"))
    vendor_bill.adjusted_total = vendor_bill.total_amount
    vendor_bill.balance_due = vendor_bill.total_amount
    vendor_bill.save(
        update_fields=[
            "total_net_amount",
            "total_tax_amount",
            "total_amount",
            "adjusted_total",
            "balance_due",
        ]
    )
