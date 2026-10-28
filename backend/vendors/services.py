from collections import defaultdict
from decimal import Decimal
from typing import TYPE_CHECKING
from vendors.models import VendorPayment
from items.models import (
    InventoryItemStockLayer,
    BranchInventoryItemStockLayer,
    BranchInventoryItem,
)
from items.stock_logger import log_stock_movement
from django.db import transaction
from django.utils import timezone
from utilities.helpers import validation_error
from django.contrib.contenttypes.models import ContentType

if TYPE_CHECKING:
    from approval.models import Approval
    from vendors.models import VendorBill, VendorPurchaseOrder


class PurchaseInventoryAccountingService:
    RECEIPT_MOVEMENT_TYPES = (
        "GRN_RECEIPT",
        "NEGATIVE_SETTLEMENT",
    )

    @classmethod
    def get_receipt_movements(cls, grn):
        from items.models import StockMovementLog

        content_type = ContentType.objects.get_for_model(grn.__class__)

        return StockMovementLog.objects.filter(
            content_type=content_type,
            object_id=grn.pk,
            movement_type__in=cls.RECEIPT_MOVEMENT_TYPES,
            quantity_change__gt=0,
            deleted_at__isnull=True,
        ).order_by("movement_date", "id")

    @classmethod
    def get_actual_received_cost(cls, grn):
        return sum(
            (Decimal(str(movement.quantity_change)) * Decimal(str(movement.unit_cost)))
            for movement in cls.get_receipt_movements(grn)
        )


class AutoGRNCreationService:
    @staticmethod
    @transaction.atomic
    def start(
        *,
        source: "VendorBill | VendorPurchaseOrder",
        inventory_increment_timing: str,
        source_approval: "Approval | None" = None,
    ):
        from vendors.models import VendorBill, VendorPurchaseOrder
        from vendors.serializers import GoodsReceivedNoteSerializer

        if not isinstance(source, (VendorBill, VendorPurchaseOrder)):
            raise validation_error(
                "GRN source must be a vendor bill or vendor purchase order."
            )

        if isinstance(source, VendorBill):
            if source.purchase_order_id:
                VendorPurchaseOrder.objects.select_for_update(
                    of=("self",),
                ).get(pk=source.purchase_order_id)

            source = VendorBill.objects.select_for_update(
                of=("self",),
            ).get(pk=source.pk)
        else:
            source = VendorPurchaseOrder.objects.select_for_update(
                of=("self",),
            ).get(pk=source.pk)

        if source_approval and source_approval.status != "completed":
            raise validation_error("The supplied source approval must be completed.")

        if (
            isinstance(source, VendorPurchaseOrder)
            and inventory_increment_timing == "ON_BILL_RECEIPT"
        ):
            return None

        existing_grn = (
            source.goods_received_notes.filter(
                is_automated=True,
                deleted_at__isnull=True,
            )
            .exclude(status="REJECTED")
            .first()
        )

        if existing_grn:
            return existing_grn

        if isinstance(source, VendorBill) and source.purchase_order_id:
            purchase_order_grn = (
                source.purchase_order.goods_received_notes.filter(
                    deleted_at__isnull=True,
                )
                .exclude(status="REJECTED")
                .first()
            )

            if purchase_order_grn:
                return purchase_order_grn

        inventory_lines = source.line_items.filter(
            inventory_item__isnull=False,
            inventory_item__item_type="GOODS",
            deleted_at__isnull=True,
        ).select_related("inventory_item", "unit_of_measure")

        if not inventory_lines.exists():
            return None

        institution = source.get_institution()
        source_field = "bill" if isinstance(source, VendorBill) else "purchase_order"

        payload = {
            "institution": institution.id,
            source_field: str(source.base_uuid),
            "branch": str(source.branch.base_uuid) if source.branch else None,
            "is_automated": True,
            "inventory_line_items": [
                {
                    "line_item": str(line.inventory_item.base_uuid),
                    "unit_of_measure": (
                        str(line.unit_of_measure.base_uuid)
                        if line.unit_of_measure
                        else None
                    ),
                    "quantity": line.quantity,
                }
                for line in inventory_lines
            ],
        }

        serializer = GoodsReceivedNoteSerializer(
            data=payload,
            context={"institution": institution},
        )
        serializer.is_valid(raise_exception=True)
        grn = serializer.save()

        if (
            isinstance(source, VendorBill)
            and inventory_increment_timing == "ON_BILL_RECEIPT"
            and source_approval
        ):
            grn.status = "PENDING"
            grn.save(update_fields=["status"])
            grn.confirm_create(
                inherit_from=source_approval,
                completion_reason=(
                    f"Automatically approved from vendor bill "
                    f"{source.reference_code}."
                ),
            )
        else:
            grn.status = "DRAFT"
            grn.save(update_fields=["status"])

        return grn


class StockService:

    @staticmethod
    @transaction.atomic
    def apply_stock_increment(
        item,
        unit_of_measure,
        unit_cost,
        quantity,
        branch=None,
        movement_type="BILL_RECEIPT",
        source_document=None,
        source_reference="",
    ):

        if item.item_type == "SERVICES":
            return

        quantity = Decimal(quantity)
        unit_cost = Decimal(unit_cost).quantize(Decimal("0.0001"))

        if unit_cost <= 0:
            raise validation_error(
                f"Cannot receive '{item.item_name}' because its unit cost "
                "is zero or negative at the receipt's cost precision. "
                "Provide a positive cost on the source document before receiving stock."
            )

        if branch:
            try:
                branch_inventory_item = BranchInventoryItem.objects.get(
                    inventory_item=item,
                    branch=branch,
                    deleted_at__isnull=True,
                )
            except BranchInventoryItem.DoesNotExist:
                raise validation_error(
                    f"Item '{item.item_name}' is not assigned to branch '{branch.branch_name}'"
                )

            remaining_quantity = StockService._settle_negative_branch_layers(
                branch_inventory_item=branch_inventory_item,
                unit_of_measure=unit_of_measure,
                unit_cost=unit_cost,
                quantity=quantity,
                movement_type=movement_type,
                source_document=source_document,
                source_reference=source_reference,
            )

            if remaining_quantity <= 0:
                return

            stock_layer, _ = BranchInventoryItemStockLayer.objects.get_or_create(
                branch_inventory_item=branch_inventory_item,
                unit_of_measure=unit_of_measure,
                unit_cost=unit_cost,
                deleted_at__isnull=True,
                defaults={"quantity_remaining": 0},
            )

            qty_before = Decimal(stock_layer.quantity_remaining)
            stock_layer.quantity_remaining += remaining_quantity
            stock_layer.save(update_fields=["quantity_remaining"])

            log_stock_movement(
                movement_type=movement_type,
                inventory_item=item,
                unit_of_measure=unit_of_measure,
                quantity_change=remaining_quantity,
                quantity_before=qty_before,
                unit_cost=unit_cost,
                branch=branch,
                source_document=source_document,
                source_reference=source_reference,
            )

        else:
            stock_layer, _ = InventoryItemStockLayer.objects.get_or_create(
                inventory_item=item,
                unit_of_measure=unit_of_measure,
                unit_cost=unit_cost,
                deleted_at__isnull=True,
                defaults={"quantity_remaining": 0},
            )

            qty_before = Decimal(stock_layer.quantity_remaining)
            stock_layer.quantity_remaining += quantity
            stock_layer.save(update_fields=["quantity_remaining"])

            log_stock_movement(
                movement_type=movement_type,
                inventory_item=item,
                unit_of_measure=unit_of_measure,
                quantity_change=quantity,
                quantity_before=qty_before,
                unit_cost=unit_cost,
                institution=item.get_institution(),
                source_document=source_document,
                source_reference=source_reference,
            )

    @staticmethod
    def _settle_negative_branch_layers(
        branch_inventory_item,
        unit_of_measure,
        unit_cost,
        quantity,
        movement_type,
        source_document,
        source_reference,
    ):
        from items.unit_converter import get_conversion_factor

        remaining_receipt_qty = Decimal(quantity)
        receipt_cf = (
            get_conversion_factor(branch_inventory_item, unit_of_measure)
            if unit_of_measure
            else Decimal("1")
        )

        negative_layers = (
            BranchInventoryItemStockLayer.objects.select_for_update()
            .filter(
                branch_inventory_item=branch_inventory_item,
                deleted_at__isnull=True,
                quantity_remaining__lt=0,
            )
            .order_by("received_date", "created_at")
        )

        for negative_layer in negative_layers:
            if remaining_receipt_qty <= 0:
                break

            negative_cf = (
                get_conversion_factor(
                    branch_inventory_item, negative_layer.unit_of_measure
                )
                if negative_layer.unit_of_measure
                else Decimal("1")
            )
            available_base = remaining_receipt_qty * receipt_cf
            negative_base = (
                abs(Decimal(negative_layer.quantity_remaining)) * negative_cf
            )
            settle_base = min(available_base, negative_base)

            settle_negative_qty = settle_base / negative_cf
            receipt_qty_used = settle_base / receipt_cf

            qty_before = Decimal(negative_layer.quantity_remaining)
            estimated_unit_cost = Decimal(negative_layer.unit_cost).quantize(
                Decimal("0.0001")
            )
            actual_unit_cost = ((unit_cost / receipt_cf) * negative_cf).quantize(
                Decimal("0.0001")
            )
            variance_total = (
                actual_unit_cost - estimated_unit_cost
            ) * settle_negative_qty

            negative_layer.quantity_remaining += settle_negative_qty
            if negative_layer.quantity_remaining == 0:
                negative_layer.deleted_at = timezone.now()

            negative_layer.save(
                update_fields=[
                    "quantity_remaining",
                    "deleted_at",
                    "updated_at",
                ]
            )

            log_stock_movement(
                movement_type="NEGATIVE_SETTLEMENT",
                inventory_item=branch_inventory_item.inventory_item,
                unit_of_measure=negative_layer.unit_of_measure,
                quantity_change=settle_negative_qty,
                quantity_before=qty_before,
                unit_cost=actual_unit_cost,
                branch=branch_inventory_item.branch,
                source_document=source_document,
                source_reference=source_reference,
                notes=f"Settled negative stock from {movement_type}.",
            )

            if variance_total != 0:
                StockService._post_inventory_cost_variance(
                    branch_inventory_item=branch_inventory_item,
                    negative_layer=negative_layer,
                    variance_total=variance_total,
                    source_document=source_document,
                    source_reference=source_reference,
                )

            remaining_receipt_qty -= receipt_qty_used

        return remaining_receipt_qty

    @staticmethod
    def _get_cogs_account(institution, item):
        from accounts.utils import get_or_create_default_account

        return (
            item.expense_account
            or getattr(item.item_category, "expense_account", None)
            or get_or_create_default_account(institution, "cogs_account")
        )

    @staticmethod
    def _post_inventory_cost_variance(
        branch_inventory_item,
        negative_layer,
        variance_total,
        source_document,
        source_reference,
    ):
        from accounts.utils import get_or_create_default_account
        from django.contrib.contenttypes.models import ContentType
        from transactions.services import JournalPostingService, JournalLine
        from utilities.helpers import get_fiscal_year

        item = branch_inventory_item.inventory_item
        branch = branch_inventory_item.branch
        institution = branch.institution
        amount = abs(Decimal(variance_total))

        if amount <= 0:
            return

        inventory_account = (
            item.inventory_account
            or getattr(item.item_category, "inventory_account", None)
            or get_or_create_default_account(institution, "inventory_account")
        )
        variance_account = (
            branch.inventory_cost_variance_account
            or StockService._get_cogs_account(institution, item)
        )

        if variance_total > 0:
            debit_account = variance_account
            credit_account = inventory_account
            debit_description = "Unfavorable inventory cost variance"
            credit_description = "Inventory value adjustment for unfavorable variance"
        else:
            debit_account = inventory_account
            credit_account = variance_account
            debit_description = "Inventory value adjustment for favorable variance"
            credit_description = "Favorable inventory cost variance"

        JournalPostingService.post(
            fiscal_year=get_fiscal_year(institution, timezone.now().date()),
            title=f"Inventory Cost Variance - {item.item_name}",
            description=(
                f"Cost variance while settling negative stock for {item.item_name} "
                f"from {source_reference}."
            ),
            branch=branch,
            content_type=ContentType.objects.get_for_model(source_document.__class__),
            object_id=source_document.id,
            transaction_date=timezone.now().date(),
            lines=[
                JournalLine(
                    account=debit_account,
                    entry_type="debit",
                    transaction_amount=amount,
                    transaction_currency=institution.currency,
                    description=debit_description,
                ),
                JournalLine(
                    account=credit_account,
                    entry_type="credit",
                    transaction_amount=amount,
                    transaction_currency=institution.currency,
                    description=credit_description,
                ),
            ],
        )

        log_stock_movement(
            movement_type="COST_VARIANCE",
            inventory_item=item,
            unit_of_measure=negative_layer.unit_of_measure,
            quantity_change=Decimal("0"),
            quantity_before=Decimal("0"),
            unit_cost=amount,
            branch=branch,
            source_document=source_document,
            source_reference=source_reference,
            notes=f"Inventory cost variance posted: {amount}.",
        )


class VendorPaymentService:

    @staticmethod
    def _apply_payment_state(payment):
        from django.contrib.contenttypes.models import ContentType
        from vendors.models import (
            Vendor,
            VendorBill,
            VendorOutstandingBalanceAdjustment,
        )

        vendor = Vendor.objects.select_for_update().get(pk=payment.get_vendor().pk)
        settlement_amount = Decimal(str(payment.settlement_amount or payment.amount))

        if settlement_amount <= Decimal("0"):
            raise validation_error(
                "The vendor payment settlement amount must be greater than zero."
            )

        if payment.is_prepayment:
            balance_before = Decimal(str(vendor.deposit_balance))
            balance_after = balance_before + settlement_amount

            Vendor.objects.filter(pk=vendor.pk).update(deposit_balance=balance_after)
            balance_adjusted = "DEPOSIT_BALANCE"
            adjustment_amount = settlement_amount
        else:
            bill = VendorBill.objects.select_for_update().get(pk=payment.bill_id)

            if settlement_amount > Decimal(str(bill.balance_due)):
                raise validation_error(
                    "Vendor payment settlement amount cannot exceed the "
                    "bill balance due."
                )

            balance_before = Decimal(str(vendor.outstanding_payables))
            balance_after = balance_before - settlement_amount

            Vendor.objects.filter(pk=vendor.pk).update(
                outstanding_payables=balance_after
            )

            bill.balance_due = max(
                Decimal("0"),
                Decimal(str(bill.balance_due)) - settlement_amount,
            )
            bill.payment_status = (
                "paid" if bill.balance_due == Decimal("0") else "partially_paid"
            )
            bill.save(update_fields=["balance_due", "payment_status"])

            balance_adjusted = "OUTSTANDING_PAYABLE_BALANCE"
            adjustment_amount = -settlement_amount

        VendorOutstandingBalanceAdjustment.objects.create(
            vendor=vendor,
            balance_adjusted=balance_adjusted,
            amount=adjustment_amount,
            amount_before_adjustment=balance_before,
            amount_after_adjustment=balance_after,
            reason=f"Vendor payment {payment.reference_code}",
            content_type=ContentType.objects.get_for_model(VendorPayment),
            object_id=payment.pk,
        )

    @staticmethod
    @transaction.atomic
    def sync_requisition_payment(vendor_payment):
        payment = (
            VendorPayment.objects.select_for_update(of=("self",))
            .select_related("vendor", "bill", "bill__vendor")
            .get(pk=vendor_payment.pk)
        )

        if payment.are_initial_journal_entries_made:
            vendor_payment.payment_status = payment.payment_status
            vendor_payment.are_initial_journal_entries_made = True
            return

        requisition = payment.cash_requisition
        if requisition is None or requisition.payment_status != "fully_paid":
            return

        VendorPaymentService._apply_payment_state(payment)

        VendorPayment.objects.filter(pk=payment.pk).update(
            payment_status="PAID",
            are_initial_journal_entries_made=True,
        )
        vendor_payment.payment_status = "PAID"
        vendor_payment.are_initial_journal_entries_made = True

    @staticmethod
    @transaction.atomic
    def process_financial_events(vendor_payment):
        from accounts.utils import get_or_create_default_account
        from bank_management.services import CashAccountService
        from django.contrib.contenttypes.models import ContentType
        from system.services import FxRateService
        from transactions.services import JournalLine, JournalPostingService
        from utilities.helpers import get_fiscal_year
        from vendors.models import Vendor, VendorBill

        payment = (
            VendorPayment.objects.select_for_update(of=("self",))
            .select_related("vendor", "bill", "bill__vendor")
            .get(pk=vendor_payment.pk)
        )

        if payment.are_initial_journal_entries_made:
            vendor_payment.are_initial_journal_entries_made = True
            return None

        if payment.cash_requisition_id:
            raise validation_error(
                "A vendor payment linked to a requisition cannot create its own journal."
            )

        institution = payment.get_institution()
        payment_vendor = payment.get_vendor()

        if not institution or not payment_vendor:
            raise validation_error(
                "The institution and vendor are required to process this payment."
            )

        vendor = Vendor.objects.select_for_update().get(pk=payment_vendor.pk)
        payment_amount = Decimal(str(payment.amount))
        settlement_amount = Decimal(str(payment.settlement_amount or payment.amount))

        if payment_amount <= Decimal("0") or settlement_amount <= Decimal("0"):
            raise validation_error(
                "Payment and settlement amounts must be greater than zero."
            )

        cash_account = payment.cash_account
        cash_coa = payment._resolve_cash_account_coa()
        payment_currency, payment_rate = payment.determine_rate_currency_used()
        settlement_currency, settlement_rate = (
            payment.determine_settlement_rate_currency_used()
        )
        account_currency = (
            None if settlement_currency == institution.currency else settlement_currency
        )

        bill = None

        if payment.is_prepayment:
            debit_account = get_or_create_default_account(
                institution,
                "prepaid_account",
                account_currency,
            )
            transaction_title = f"Vendor prepayment {payment.reference_code}"
            debit_description = f"Vendor prepayment for {vendor.vendor_name}"
        else:
            bill = VendorBill.objects.select_for_update().get(pk=payment.bill_id)

            if settlement_amount > Decimal(str(bill.balance_due)):
                raise validation_error(
                    "Vendor payment settlement amount cannot exceed the "
                    "bill balance due."
                )

            debit_account = (
                vendor.default_account_payable
                or get_or_create_default_account(
                    institution,
                    "payable_account",
                    account_currency,
                )
            )
            transaction_title = (
                f"Vendor payment {payment.reference_code} " f"for {bill.reference_code}"
            )
            debit_description = f"Accounts payable reduced for {bill.reference_code}"

        CashAccountService.outflow(
            instance=cash_account,
            amount=payment_amount,
            source=payment,
            source_reference_code=payment.reference_code,
            source_reference_name=transaction_title,
        )

        payment_base_amount = FxRateService.translate(
            payment_amount,
            payment_rate,
        )
        settlement_base_amount = FxRateService.translate(
            settlement_amount,
            settlement_rate,
        )

        journal_lines = [
            JournalLine(
                account=debit_account,
                entry_type="debit",
                transaction_amount=settlement_amount,
                transaction_currency=settlement_currency,
                exchange_rate=settlement_rate,
                description=debit_description,
            ),
            JournalLine(
                account=cash_coa,
                entry_type="credit",
                transaction_amount=payment_amount,
                transaction_currency=payment_currency,
                exchange_rate=payment_rate,
                description=f"Cash paid to {vendor.vendor_name}",
            ),
        ]

        realized_difference = settlement_base_amount - payment_base_amount

        if realized_difference > Decimal("0"):
            journal_lines.append(
                JournalLine(
                    account=get_or_create_default_account(
                        institution,
                        "fx_gain_loss_account",
                    ),
                    entry_type="credit",
                    transaction_amount=realized_difference,
                    transaction_currency=institution.currency,
                    exchange_rate=Decimal("1"),
                    description=(
                        f"Realized foreign-exchange gain on "
                        f"{payment.reference_code}"
                    ),
                )
            )
        elif realized_difference < Decimal("0"):
            journal_lines.append(
                JournalLine(
                    account=get_or_create_default_account(
                        institution,
                        "fx_gain_loss_account",
                    ),
                    entry_type="debit",
                    transaction_amount=abs(realized_difference),
                    transaction_currency=institution.currency,
                    exchange_rate=Decimal("1"),
                    description=(
                        f"Realized foreign-exchange loss on "
                        f"{payment.reference_code}"
                    ),
                )
            )

        transaction_record, _ = JournalPostingService.post(
            fiscal_year=get_fiscal_year(
                institution,
                payment.payment_date,
            ),
            title=transaction_title,
            description=(
                f"Payment of {payment_amount} {payment_currency.code} "
                f"to {vendor.vendor_name}"
            ),
            transaction_date=payment.payment_date,
            lines=journal_lines,
            branch=payment.branch,
            content_type=ContentType.objects.get_for_model(VendorPayment),
            object_id=payment.pk,
            source=payment,
        )

        VendorPaymentService._apply_payment_state(payment)

        VendorPayment.objects.filter(pk=payment.pk).update(
            are_initial_journal_entries_made=True
        )
        vendor_payment.are_initial_journal_entries_made = True

        return transaction_record

    @staticmethod
    @transaction.atomic
    def create_requisition(
        vendor_payment,
        *,
        source_approval=None,
    ):
        from accounts.utils import get_or_create_default_account
        from django.contrib.contenttypes.models import ContentType
        from institution.models import InstitutionSupportedCurrency
        from requisitions.models import RequisitionType
        from requisitions.serializers import (
            RequisitionSerializer,
            RequisitionTypeLineItemSerializer,
            RequisitionTypeSerializer,
        )
        from utilities.helpers import validation_error

        institution = vendor_payment.get_institution()

        if vendor_payment.cash_requisition:
            vendor_payment_content_type = ContentType.objects.get_for_model(
                vendor_payment.__class__
            )

            if (
                vendor_payment.cash_requisition.content_type_id is None
                and vendor_payment.cash_requisition.object_id is None
            ):
                vendor_payment.cash_requisition.content_type = (
                    vendor_payment_content_type
                )
                vendor_payment.cash_requisition.object_id = vendor_payment.id
                vendor_payment.cash_requisition.save(
                    update_fields=["content_type", "object_id"]
                )
                return

            if (
                vendor_payment.cash_requisition.content_type_id
                != vendor_payment_content_type.id
                or vendor_payment.cash_requisition.object_id != vendor_payment.id
            ):
                raise validation_error(
                    {
                        "cash_requisition": (
                            "The linked requisition does not belong to this "
                            "vendor payment."
                        )
                    }
                )

            return

        vendor = vendor_payment.get_vendor()

        payment_currency = vendor_payment.currency or institution.currency
        supported_currency = (
            InstitutionSupportedCurrency.objects.active()
            .filter(institution=institution, currency=payment_currency)
            .first()
        )
        if supported_currency is None:
            raise validation_error(
                {
                    "currency": (
                        f"Cannot create the payment requisition: currency "
                        f'"{payment_currency.code}" is not configured as an active '
                        "supported currency for this institution. Ask an "
                        "administrator to enable it in institution settings."
                    )
                }
            )

        settlement_currency, _ = (
            vendor_payment.determine_settlement_rate_currency_used()
        )
        account_currency = (
            None if settlement_currency == institution.currency else settlement_currency
        )

        debit_account = (
            get_or_create_default_account(
                institution,
                "prepaid_account",
                account_currency,
            )
            if vendor_payment.is_prepayment
            else (
                vendor.default_account_payable
                or get_or_create_default_account(
                    institution,
                    "payable_account",
                    account_currency,
                )
            )
        )

        requisition_type_name = (
            "Vendor Prepayment Requisition Type"
            if vendor_payment.is_prepayment
            else "Vendor Payment Requisition Type"
        )

        cash_account_content_type = ContentType.objects.get_for_model(
            vendor_payment.cash_account,
            for_concrete_model=False,
        )

        requisition_type = RequisitionType.objects.filter(
            institution=institution,
            name=requisition_type_name,
        ).first()

        beneficiary = vendor.requisition_beneficiary

        if not requisition_type:
            requisition_type_serializer = RequisitionTypeSerializer(
                data={
                    "name": requisition_type_name,
                    "allowed_currencies": [str(supported_currency.base_uuid)],
                    "description": "Request for Cash to pay or prepay Vendor",
                    "is_allowed_to_all_users": True,
                    "debit_account": str(debit_account.base_uuid),
                    "cash_account": {
                        "content_type": cash_account_content_type.id,
                        "content_object_uuid": str(
                            vendor_payment.cash_account.base_uuid
                        ),
                    },
                    "line_items": [
                        {
                            "description": "Cash needed to pay vendor",
                            "should_unit_price_be_edited": True,
                            "price_change_direction": "both",
                            "max_quantity": 1,
                            "allow_unconfigured_beneficiaries": True,
                        }
                    ],
                },
                context={"request": None, "institution": institution},
            )
            requisition_type_serializer.is_valid(raise_exception=True)
            requisition_type = requisition_type_serializer.save()
            requisition_type.confirm_create()

        line_item = requisition_type.line_items.filter(
            description="Cash needed to pay vendor",
            is_active=True,
            deleted_at__isnull=True,
        ).first()

        if line_item is None:
            line_item_serializer = RequisitionTypeLineItemSerializer(
                data={
                    "description": "Cash needed to pay vendor",
                    "should_unit_price_be_edited": True,
                    "price_change_direction": "both",
                    "max_quantity": 1,
                    "allow_unconfigured_beneficiaries": True,
                },
                context={"requisition_type": requisition_type},
            )
            line_item_serializer.is_valid(raise_exception=True)
            line_item = line_item_serializer.save()

        serializer = RequisitionSerializer(
            data={
                "requisition_type": requisition_type.base_uuid,
                "currency": str(supported_currency.base_uuid),
                "description": (
                    "Requisition for Vendor Payment " f"{vendor_payment.reference_code}"
                ),
                "content_type": ContentType.objects.get_for_model(vendor_payment).id,
                "object_id": vendor_payment.id,
                "branch": (
                    vendor_payment.branch.base_uuid if vendor_payment.branch else None
                ),
                "line_items": [
                    {
                        "line_item": str(line_item.base_uuid),
                        "quantity": 1,
                        "unit_price": vendor_payment.amount,
                        "beneficiary": (beneficiary.base_uuid if beneficiary else None),
                    }
                ],
            },
            context={
                "request": None,
                "institution": institution,
            },
        )

        serializer.is_valid(raise_exception=True)
        requisition = serializer.save()

        vendor_payment.cash_requisition = requisition
        vendor_payment.save(update_fields=["cash_requisition"])

        requisition.confirm_create(
            inherit_from=source_approval,
            completion_reason=(
                f"Requisition inherited the completed approval for vendor "
                f"payment {vendor_payment.reference_code}."
            ),
        )

        return requisition

    @staticmethod
    def _resolve_requisition_cash_account(requisition):
        from bank_management.models import CashAccount
        from utilities.helpers import validation_error

        requisition_payment = getattr(requisition, "payment", None)

        if requisition_payment:
            content_type = requisition_payment.content_type
            account_uuid = requisition_payment.object_uuid
            source_name = "requisition payment"
        else:
            content_type = requisition.requisition_type.content_type
            account_uuid = requisition.requisition_type.object_uuid
            source_name = "requisition template"

        if bool(content_type) != bool(account_uuid):
            raise validation_error(
                f"The cash account configuration on the {source_name} is incomplete."
            )

        if not content_type or not account_uuid:
            raise validation_error(
                f"No cash account is configured on the {source_name}."
            )

        model_class = content_type.model_class()

        if not model_class or not issubclass(model_class, CashAccount):
            raise validation_error(
                f"The cash account configured on the {source_name} is invalid."
            )

        cash_account = model_class.objects.filter(
            base_uuid=account_uuid,
            deleted_at__isnull=True,
        ).first()

        if not cash_account:
            raise validation_error(
                f"The cash account configured on the {source_name} was not found."
            )

        if cash_account.institution_id != requisition.get_institution().id:
            raise validation_error(
                "The cash account must belong to the requisition's institution."
            )

        return cash_account

    @staticmethod
    def _group_requisition_line_items_by_vendor(requisition):
        from utilities.helpers import validation_error

        requisition_payment = getattr(requisition, "payment", None)

        payment_beneficiary = (
            requisition_payment.beneficiary if requisition_payment else None
        )

        grouped_line_items = defaultdict(list)

        line_items = requisition.line_items.filter(
            is_removed=False,
        ).select_related("beneficiary__vendor")

        for line_item in line_items:
            beneficiary = line_item.beneficiary or payment_beneficiary

            if not beneficiary:
                raise validation_error(
                    {
                        "line_items": (
                            f"No beneficiary is configured for requisition line "
                            f"item {line_item.reference_code}."
                        )
                    }
                )

            vendor = getattr(beneficiary, "vendor", None)

            if not vendor:
                raise validation_error(
                    {
                        "line_items": (
                            f"The beneficiary for requisition line item "
                            f"{line_item.reference_code} is not linked to a vendor."
                        )
                    }
                )

            grouped_line_items[vendor].append(line_item)

        if not grouped_line_items:
            raise validation_error(
                "The requisition has no active line items to create vendor payments from."
            )

        return grouped_line_items

    @staticmethod
    @transaction.atomic
    def create_vendor_payment_from_requisition(
        requisition,
        source_approval,
    ):
        from django.contrib.contenttypes.models import ContentType
        from utilities.helpers import validation_error

        requisition_payment = getattr(requisition, "payment", None)

        if requisition.status != "approved":
            raise validation_error(
                "A vendor payment can only be created from an approved requisition."
            )

        cash_account = VendorPaymentService._resolve_requisition_cash_account(
            requisition
        )
        grouped_line_items = (
            VendorPaymentService._group_requisition_line_items_by_vendor(requisition)
        )

        vendor_subtotals = {
            vendor: sum(
                Decimal(line_item.quantity) * line_item.unit_price
                for line_item in line_items
            )
            for vendor, line_items in grouped_line_items.items()
        }
        subtotal = sum(vendor_subtotals.values(), Decimal("0.00"))

        if subtotal <= 0:
            raise validation_error(
                "The requisition line item total must be greater than zero."
            )

        target_amount = Decimal(
            requisition_payment.amount_paid
            if requisition_payment
            else requisition.total_payable_amount
        )
        cent = Decimal("0.01")
        allocated_amount = Decimal("0.00")
        vendors = list(vendor_subtotals)
        allocations = {}

        for index, vendor in enumerate(vendors):
            if index == len(vendors) - 1:
                amount = target_amount - allocated_amount
            else:
                amount = (target_amount * vendor_subtotals[vendor] / subtotal).quantize(
                    cent
                )
                allocated_amount += amount

            allocations[vendor] = amount

        cash_account_content_type = ContentType.objects.get_for_model(
            cash_account,
            for_concrete_model=False,
        )
        existing_payments = {
            payment.vendor_id: payment
            for payment in VendorPayment.objects.filter(
                cash_requisition=requisition,
                vendor_id__in=[vendor.pk for vendor in vendors],
                deleted_at__isnull=True,
            )
        }
        vendor_payments = []

        for vendor in vendors:
            vendor_payment = existing_payments.get(vendor.pk)

            if vendor_payment:
                vendor_payment.amount = allocations[vendor]
                vendor_payment.branch = requisition.branch
                vendor_payment.content_type = cash_account_content_type
                vendor_payment.object_id = cash_account.pk
                vendor_payment.save(
                    update_fields=[
                        "amount",
                        "branch",
                        "content_type",
                        "object_id",
                    ]
                )
            else:
                vendor_payment = VendorPayment.objects.create(
                    cash_requisition=requisition,
                    amount=allocations[vendor],
                    payment_status="DRAFT",
                    vendor=vendor,
                    branch=requisition.branch,
                    content_type=cash_account_content_type,
                    object_id=cash_account.pk,
                )

                vendor_payment.confirm_create(
                    inherit_from=source_approval,
                    completion_reason=(
                        f"Vendor payment inherited approval from requisition "
                        f"{requisition.reference_code}."
                    ),
                )

            if requisition.payment_status == "fully_paid":
                vendor_payment.on_requisition_paid(requisition)
            else:
                vendor_payment.on_requisition_approved(requisition)

            vendor_payments.append(vendor_payment)

        return vendor_payments
