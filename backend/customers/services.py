from decimal import Decimal, ROUND_HALF_UP, localcontext
from django.db import transaction
from django.contrib.contenttypes.models import ContentType
from django.db.models import Q, Sum
from django.utils import timezone
from itertools import chain
from utilities.helpers import validation_error
from accounts.utils import get_or_create_default_account
from institution.models import DepositDistributionStrategy
from django.db import models
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from approval.models import Approval
    from customers.models import CustomerPurchaseOrder, Invoice
    from customers.models import InvoiceLineItem
    from vendors.models import VendorBillLineItem


class ItemReturnQuantityService:
    @staticmethod
    def _decimal(value):
        return Decimal(str(value or 0))

    @classmethod
    def processed_quantity(
        cls,
        *,
        goods_issued_note_line,
        exclude_item_return=None,
    ) -> Decimal:
        from customers.models import ItemReturnItem

        queryset = ItemReturnItem.objects.filter(
            goods_issued_note_line=goods_issued_note_line,
            item_return__return_status="APPROVED",
            item_return__are_initial_journal_entries_made=True,
            item_return__deleted_at__isnull=True,
            deleted_at__isnull=True,
        )

        if exclude_item_return is not None:
            queryset = queryset.exclude(item_return=exclude_item_return)

        total = queryset.aggregate(total=Sum("quantity"))["total"]
        return cls._decimal(total)

    @classmethod
    def returnable_quantity(
        cls,
        *,
        goods_issued_note_line,
        exclude_item_return=None,
    ) -> Decimal:
        issued = cls._decimal(goods_issued_note_line.quantity)
        returned = cls.processed_quantity(
            goods_issued_note_line=goods_issued_note_line,
            exclude_item_return=exclude_item_return,
        )
        return max(issued - returned, Decimal("0"))

    @classmethod
    def validate_requested_quantity(
        cls,
        *,
        goods_issued_note_line,
        requested_quantity,
        exclude_item_return=None,
    ):
        requested = cls._decimal(requested_quantity)

        if requested <= 0:
            raise validation_error("Return quantity must be greater than zero.")

        returnable = cls.returnable_quantity(
            goods_issued_note_line=goods_issued_note_line,
            exclude_item_return=exclude_item_return,
        )

        if requested > returnable:
            raise validation_error(
                f"Cannot return {requested} units from GIN line "
                f"{goods_issued_note_line.pk}. Only {returnable} units remain "
                "returnable."
            )

        return returnable

    @classmethod
    def invoiced_returnable_quantity(
        cls,
        *,
        goods_issued_note_line,
        exclude_item_return=None,
    ) -> Decimal:
        physically_returnable = cls.returnable_quantity(
            goods_issued_note_line=goods_issued_note_line,
            exclude_item_return=exclude_item_return,
        )
        invoiced_quantity = ItemReturnProcessingService._recognized_quantity(
            goods_issued_note_line
        )
        return min(physically_returnable, invoiced_quantity)

    @classmethod
    def validate_cash_refund_quantity(
        cls,
        *,
        goods_issued_note_line,
        requested_quantity,
        exclude_item_return=None,
    ):
        requested = cls._decimal(requested_quantity)
        available = cls.invoiced_returnable_quantity(
            goods_issued_note_line=goods_issued_note_line,
            exclude_item_return=exclude_item_return,
        )

        if requested > available:
            raise validation_error(
                f"Cannot request a cash refund for {requested} units from "
                f"GIN line {goods_issued_note_line.pk}. Only {available} "
                "units are both invoiced and physically returnable."
            )

        return available


class ItemReturnCreditNoteService:
    @staticmethod
    def _decimal(value):
        return Decimal(str(value or 0))

    @classmethod
    def _previously_credited_quantity(cls, invoice_line):
        from customers.models import CreditDebitNoteLineItem

        credited = CreditDebitNoteLineItem.objects.filter(
            invoice_line_item=invoice_line,
            credit_debit_note__type="CREDIT",
            credit_debit_note__falls_under="SALES",
            credit_debit_note__status__in=["APPROVED", "RESOLVED"],
            credit_debit_note__is_active=True,
            credit_debit_note__deleted_at__isnull=True,
            deleted_at__isnull=True,
        ).aggregate(total=Sum("quantity"))["total"] or Decimal("0")

        return cls._decimal(credited)

    @classmethod
    def _add_allocation(
        cls,
        *,
        allocations,
        invoice_line,
        quantity,
    ):
        quantity = cls._decimal(quantity)

        if quantity <= 0:
            return

        invoice_allocations = allocations.setdefault(
            invoice_line.invoice_id,
            {
                "invoice": invoice_line.invoice,
                "lines": {},
            },
        )

        current = invoice_allocations["lines"].get(
            invoice_line.pk,
            {
                "invoice_line": invoice_line,
                "quantity": Decimal("0"),
            },
        )
        current["quantity"] += quantity
        invoice_allocations["lines"][invoice_line.pk] = current

    @classmethod
    def _allocate_direct_invoice_line(
        cls,
        *,
        return_item,
        gin_line,
        allocations,
    ):
        invoice_line = gin_line.source_invoice_line

        if not invoice_line:
            raise validation_error(
                f"GIN line {gin_line.pk} has no originating invoice line."
            )

        invoice = invoice_line.invoice
        if (
            not invoice.is_active
            or invoice.deleted_at is not None
            or not invoice.are_initial_journal_entries_made
        ):
            raise validation_error(
                f"Invoice {invoice.reference_code} is not posted and cannot "
                "receive a Credit Note."
            )

        already_planned = (
            allocations.get(invoice.pk, {})
            .get("lines", {})
            .get(invoice_line.pk, {})
            .get("quantity", Decimal("0"))
        )
        available = max(
            cls._decimal(invoice_line.quantity)
            - cls._previously_credited_quantity(invoice_line)
            - cls._decimal(already_planned),
            Decimal("0"),
        )
        requested = cls._decimal(return_item.quantity)

        if requested > available:
            raise validation_error(
                f"Returned quantity for invoice line {invoice_line.reference_code} "
                f"is {requested}, but only {available} remains creditable."
            )

        cls._add_allocation(
            allocations=allocations,
            invoice_line=invoice_line,
            quantity=requested,
        )

    @classmethod
    def _allocate_purchase_order_line(
        cls,
        *,
        return_item,
        gin_line,
        allocations,
    ):
        from customers.models import InvoiceLineItem
        from items.unit_converter import get_conversion_factor

        purchase_order_line = gin_line.source_purchase_order_line
        if not purchase_order_line:
            raise validation_error(
                f"GIN line {gin_line.pk} has no commercial source line."
            )

        branch_item = gin_line.line_item
        gin_uom = gin_line.unit_of_measure.unit_of_measure
        gin_factor = cls._decimal(get_conversion_factor(branch_item, gin_uom))
        quantity_to_allocate_base = cls._decimal(return_item.quantity) * gin_factor

        invoice_lines = list(
            InvoiceLineItem.objects.select_for_update()
            .filter(
                source_purchase_order_line=purchase_order_line,
                invoice__is_active=True,
                invoice__deleted_at__isnull=True,
                invoice__are_initial_journal_entries_made=True,
                deleted_at__isnull=True,
            )
            .select_related(
                "invoice",
                "unit_of_measure__unit_of_measure",
            )
            .order_by("invoice__issue_date", "invoice_id", "id")
        )

        for invoice_line in invoice_lines:
            already_planned = (
                allocations.get(invoice_line.invoice_id, {})
                .get("lines", {})
                .get(invoice_line.pk, {})
                .get("quantity", Decimal("0"))
            )
            available_invoice_quantity = max(
                cls._decimal(invoice_line.quantity)
                - cls._previously_credited_quantity(invoice_line)
                - cls._decimal(already_planned),
                Decimal("0"),
            )

            if available_invoice_quantity <= 0:
                continue

            invoice_factor = cls._decimal(
                get_conversion_factor(
                    branch_item,
                    invoice_line.unit_of_measure.unit_of_measure,
                )
            )
            available_base = available_invoice_quantity * invoice_factor
            allocated_base = min(
                quantity_to_allocate_base,
                available_base,
            )
            allocated_invoice_quantity = allocated_base / invoice_factor

            if (
                allocated_invoice_quantity
                != allocated_invoice_quantity.to_integral_value()
            ):
                raise validation_error(
                    f"Return quantity for GIN line {gin_line.reference_code} "
                    "cannot be represented as a whole quantity in invoice line "
                    f"{invoice_line.reference_code}'s unit of measure."
                )

            cls._add_allocation(
                allocations=allocations,
                invoice_line=invoice_line,
                quantity=allocated_invoice_quantity,
            )
            quantity_to_allocate_base -= allocated_base

            if quantity_to_allocate_base <= 0:
                break

        if quantity_to_allocate_base > 0:
            raise validation_error(
                f"The invoiced product lines for GIN line "
                f"{gin_line.reference_code} cannot support the returned quantity."
            )

    @classmethod
    def _build_allocations(cls, *, return_items, locked_gin_lines):
        allocations = {}

        for return_item in return_items:
            gin_line = locked_gin_lines[return_item.goods_issued_note_line_id]

            if gin_line.source_invoice_line_id:
                cls._allocate_direct_invoice_line(
                    return_item=return_item,
                    gin_line=gin_line,
                    allocations=allocations,
                )
            else:
                cls._allocate_purchase_order_line(
                    return_item=return_item,
                    gin_line=gin_line,
                    allocations=allocations,
                )

        return allocations

    @classmethod
    def create_for_item_return(
        cls,
        *,
        item_return,
        return_items,
        locked_gin_lines,
    ):
        from customers.models import (
            CreditDebitNote,
            CreditDebitNoteLineItem,
            Invoice,
        )

        if item_return.return_type != "CASH_REFUND":
            return []

        if not item_return.coa_cash_account:
            raise validation_error(
                "A cash or bank account is required for a cash refund."
            )

        allocations = cls._build_allocations(
            return_items=return_items,
            locked_gin_lines=locked_gin_lines,
        )
        credit_notes = []

        for invoice_id in sorted(allocations):
            allocation = allocations[invoice_id]
            invoice = Invoice.objects.select_for_update().get(pk=invoice_id)
            invoice_currency = invoice.determine_rate_currency_used()[0]
            cash_currency = item_return.coa_cash_account.get_account_currency()

            if cash_currency.pk != invoice_currency.pk:
                raise validation_error(
                    f"Refund account currency does not match invoice "
                    f"{invoice.reference_code}'s currency."
                )

            credit_note = CreditDebitNote.objects.create(
                branch=invoice.branch or item_return.get_branch(),
                invoice=invoice,
                coa_cash_account=item_return.coa_cash_account,
                type="CREDIT",
                falls_under="SALES",
                status="PENDING",
                amount=Decimal("0.00"),
                issue_date=timezone.localdate(item_return.return_date),
                description=(
                    f"Credit for products received through Item Return "
                    f"{item_return.reference_code}."
                ),
            )

            note_total = Decimal("0")
            line_allocations = allocation["lines"]

            for invoice_line_id in sorted(line_allocations):
                line_allocation = line_allocations[invoice_line_id]
                credit_line = CreditDebitNoteLineItem.objects.create(
                    credit_debit_note=credit_note,
                    invoice_line_item=line_allocation["invoice_line"],
                    quantity=int(line_allocation["quantity"]),
                    label=(
                        f"Returned through Item Return " f"{item_return.reference_code}"
                    ),
                )
                note_total += credit_line.amount_to_deduct

            CreditDebitNote.objects.filter(pk=credit_note.pk).update(amount=note_total)
            credit_note.amount = note_total

            # This begins the Credit Note's own approval workflow. It does not
            # inherit or alter the Item Return approval or original Invoice.
            credit_note.confirm_create()
            credit_notes.append(credit_note)

        return credit_notes


class ItemReturnProcessingService:
    ISSUE_MOVEMENT_TYPES = ("GIN_ISSUE", "NEGATIVE_SALE")
    JOURNAL_TITLE_PREFIX = "Physical Inventory Return "

    @staticmethod
    def _decimal(value):
        return Decimal(str(value or 0))

    @classmethod
    def _existing_journal(cls, item_return):
        from transactions.models import Transaction

        content_type = ContentType.objects.get_for_model(
            item_return.__class__,
            for_concrete_model=False,
        )
        return Transaction.objects.filter(
            content_type=content_type,
            object_id=item_return.pk,
            transaction_title=cls.JOURNAL_TITLE_PREFIX + item_return.reference_code,
            deleted_at__isnull=True,
        ).first()

    @classmethod
    def _lock_return_lines(cls, item_return):
        from customers.models import GoodsIssuedNoteLineItem, ItemReturnItem

        return_items = list(
            ItemReturnItem.objects.select_for_update(of=("self",))
            .filter(item_return=item_return, deleted_at__isnull=True)
            .select_related(
                "goods_issued_note_line",
                "goods_issued_note_line__line_item",
                "goods_issued_note_line__line_item__inventory_item",
                "goods_issued_note_line__unit_of_measure",
                "goods_issued_note_line__unit_of_measure__unit_of_measure",
                "goods_issued_note_line__source_invoice_line",
                "goods_issued_note_line__source_purchase_order_line",
            )
            .order_by("goods_issued_note_line_id", "id")
        )
        if not return_items:
            raise validation_error(
                "An Item Return must contain at least one active line."
            )

        gin_line_ids = [
            line.goods_issued_note_line_id
            for line in return_items
            if line.goods_issued_note_line_id
        ]

        if len(gin_line_ids) != len(return_items):
            raise validation_error(
                "Every Item Return line requires exact GIN-line provenance."
            )

        locked_lines = {
            line.pk: line
            for line in (
                GoodsIssuedNoteLineItem.objects.select_for_update()
                .filter(pk__in=gin_line_ids)
                .order_by("pk")
            )
        }

        if len(locked_lines) != len(gin_line_ids):
            raise validation_error("One or more originating GIN lines no longer exist.")
        return return_items, locked_lines

    @classmethod
    def _issue_movements(cls, gin_line):
        from items.models import StockMovementLog

        movements = list(
            StockMovementLog.objects.select_for_update(of=("self",))
            .filter(
                goods_issued_note_line=gin_line,
                movement_type__in=cls.ISSUE_MOVEMENT_TYPES,
                quantity_change__lt=0,
                deleted_at__isnull=True,
            )
            .select_related("unit_of_measure")
            .order_by("movement_date", "id")
        )
        if not movements:
            raise validation_error(
                f"No historical issue movements exist for GIN line {gin_line.pk}."
            )
        return movements

    @classmethod
    def _historical_slices(cls, *, return_item, gin_line, previously_returned):
        quantity_to_skip = cls._decimal(previously_returned)
        quantity_to_restore = cls._decimal(return_item.quantity)
        expected_uom_id = gin_line.unit_of_measure.unit_of_measure_id
        slices = []

        for movement in cls._issue_movements(gin_line):
            if movement.unit_of_measure_id != expected_uom_id:
                raise validation_error(
                    "Historical issue movement UOM does not match its GIN line."
                )

            issued_quantity = abs(cls._decimal(movement.quantity_change))
            if quantity_to_skip >= issued_quantity:
                quantity_to_skip -= issued_quantity
                continue

            available = issued_quantity - quantity_to_skip
            quantity_to_skip = Decimal("0")
            restored = min(available, quantity_to_restore)

            if restored > 0:
                unit_cost = cls._decimal(movement.unit_cost)
                slices.append(
                    {
                        "return_item": return_item,
                        "gin_line": gin_line,
                        "issue_movement": movement,
                        "quantity": restored,
                        "unit_cost": unit_cost,
                        "total_cost": restored * unit_cost,
                    }
                )
                quantity_to_restore -= restored

            if quantity_to_restore <= 0:
                break

        if quantity_to_restore > 0:
            raise validation_error(
                "Historical issue movements cannot support the requested return "
                f"quantity for GIN line {gin_line.pk}."
            )
        return slices

    @classmethod
    def _recognized_quantity(cls, gin_line):
        if gin_line.source_invoice_line_id:
            invoice_line = gin_line.source_invoice_line
            invoice = invoice_line.invoice
            if (
                invoice.is_active
                and invoice.deleted_at is None
                and invoice.are_initial_journal_entries_made
            ):
                return min(
                    cls._decimal(invoice_line.quantity),
                    cls._decimal(gin_line.quantity),
                )
            return Decimal("0")

        if not gin_line.source_purchase_order_line_id:
            return Decimal("0")

        from customers.models import InvoiceLineItem
        from items.unit_converter import get_conversion_factor

        source_uom = gin_line.unit_of_measure.unit_of_measure
        branch_item = gin_line.line_item
        source_factor = cls._decimal(get_conversion_factor(branch_item, source_uom))
        recognized_base = Decimal("0")

        invoice_lines = (
            InvoiceLineItem.objects.filter(
                source_purchase_order_line=gin_line.source_purchase_order_line,
                invoice__is_active=True,
                invoice__deleted_at__isnull=True,
                invoice__are_initial_journal_entries_made=True,
                deleted_at__isnull=True,
            )
            .select_related("unit_of_measure__unit_of_measure")
            .order_by("invoice__issue_date", "invoice_id", "id")
        )
        for invoice_line in invoice_lines:
            factor = cls._decimal(
                get_conversion_factor(
                    branch_item,
                    invoice_line.unit_of_measure.unit_of_measure,
                )
            )
            recognized_base += cls._decimal(invoice_line.quantity) * factor

        return min(
            recognized_base / source_factor,
            cls._decimal(gin_line.quantity),
        )

    @classmethod
    def _classify_slice_costs(cls, *, slices, recognized_quantity, previously_returned):
        recognized_remaining = max(
            cls._decimal(recognized_quantity) - cls._decimal(previously_returned),
            Decimal("0"),
        )
        cogs_cost = Decimal("0")
        interim_cost = Decimal("0")

        for slice_data in slices:
            quantity = slice_data["quantity"]
            unit_cost = slice_data["unit_cost"]
            recognized_slice = min(quantity, recognized_remaining)
            unrecognized_slice = quantity - recognized_slice
            cogs_cost += recognized_slice * unit_cost
            interim_cost += unrecognized_slice * unit_cost
            recognized_remaining -= recognized_slice

        return cogs_cost, interim_cost

    @classmethod
    def _restore_slice(cls, *, item_return, slice_data):
        from items.models import BranchInventoryItemStockLayer
        from items.stock_logger import log_stock_movement

        return_item = slice_data["return_item"]
        gin_line = slice_data["gin_line"]
        movement = slice_data["issue_movement"]
        quantity = slice_data["quantity"]
        branch_item = gin_line.line_item

        quantity_before = (
            BranchInventoryItemStockLayer.objects.select_for_update()
            .filter(
                branch_inventory_item=branch_item,
                unit_of_measure=movement.unit_of_measure,
                deleted_at__isnull=True,
            )
            .aggregate(total=Sum("quantity_remaining"))["total"]
            or Decimal("0")
        )

        BranchInventoryItemStockLayer.objects.create(
            branch_inventory_item=branch_item,
            unit_of_measure=movement.unit_of_measure,
            quantity_remaining=quantity,
            unit_cost=slice_data["unit_cost"],
            received_date=item_return.return_date,
            restored_from_movement=movement,
            restored_by_return_item=return_item,
        )
        log_stock_movement(
            movement_type="RETURN_RESTOCK",
            inventory_item=branch_item.inventory_item,
            unit_of_measure=movement.unit_of_measure,
            quantity_change=quantity,
            quantity_before=cls._decimal(quantity_before),
            unit_cost=slice_data["unit_cost"],
            branch=branch_item.branch,
            source_document=item_return,
            source_reference=item_return.reference_code,
            item_return_item=return_item,
            reverses_movement=movement,
        )

    @classmethod
    def _post_journal(cls, *, item_return, inventory_cost, cogs_cost, interim_cost):
        from transactions.services import JournalLine, JournalPostingService
        from utilities.helpers import get_fiscal_year

        institution = item_return.get_institution()
        inventory_account = get_or_create_default_account(
            institution, "inventory_account", None
        )
        lines = [
            JournalLine(
                account=inventory_account,
                entry_type="debit",
                transaction_amount=inventory_cost,
                transaction_currency=institution.currency,
                exchange_rate=Decimal("1"),
                description=(
                    f"Inventory restored by Item Return {item_return.reference_code}"
                ),
            )
        ]

        if cogs_cost > 0:
            lines.append(
                JournalLine(
                    account=get_or_create_default_account(
                        institution, "cogs_account", None
                    ),
                    entry_type="credit",
                    transaction_amount=cogs_cost,
                    transaction_currency=institution.currency,
                    exchange_rate=Decimal("1"),
                    description=(
                        "Recognized COGS reversed by Item Return "
                        f"{item_return.reference_code}"
                    ),
                )
            )
        if interim_cost > 0:
            lines.append(
                JournalLine(
                    account=get_or_create_default_account(
                        institution, "stock_interim_account", None
                    ),
                    entry_type="credit",
                    transaction_amount=interim_cost,
                    transaction_currency=institution.currency,
                    exchange_rate=Decimal("1"),
                    description=(
                        "Uninvoiced GIN interim cost reversed by Item Return "
                        f"{item_return.reference_code}"
                    ),
                )
            )

        return JournalPostingService.post(
            fiscal_year=get_fiscal_year(institution, item_return.return_date.date()),
            title=cls.JOURNAL_TITLE_PREFIX + item_return.reference_code,
            description=(
                f"Historical-cost physical return {item_return.reference_code}"
            ),
            transaction_date=item_return.return_date,
            lines=lines,
            branch=item_return.get_branch(),
            content_type=ContentType.objects.get_for_model(
                item_return.__class__, for_concrete_model=False
            ),
            object_id=item_return.pk,
            source=item_return,
        )

    @classmethod
    @transaction.atomic
    def process(cls, *, item_return):
        from customers.models import ItemReturn

        item_return = (
            ItemReturn.objects.select_for_update(of=("self",))
            .select_related("goods_issued_note", "institution")
            .get(pk=item_return.pk)
        )

        if item_return.return_status != "APPROVED":
            raise validation_error(
                "Only an approved Item Return can restore inventory."
            )

        existing_journal = cls._existing_journal(item_return)

        if item_return.are_initial_journal_entries_made:
            if existing_journal is None:
                raise validation_error(
                    "The Item Return is marked processed but its journal cannot be found."
                )
            return existing_journal

        if existing_journal is not None:
            raise validation_error(
                "An Item Return journal already exists while the return is not "
                "marked processed. Manual reconciliation is required."
            )

        return_items, locked_gin_lines = cls._lock_return_lines(item_return)
        all_slices = []
        cogs_cost = Decimal("0")
        interim_cost = Decimal("0")

        for return_item in return_items:
            gin_line = locked_gin_lines[return_item.goods_issued_note_line_id]
            if gin_line.goods_issued_note_id != item_return.goods_issued_note_id:
                raise validation_error(
                    "An Item Return line belongs to a different GIN."
                )

            previously_returned = ItemReturnQuantityService.processed_quantity(
                goods_issued_note_line=gin_line,
                exclude_item_return=item_return,
            )
            ItemReturnQuantityService.validate_requested_quantity(
                goods_issued_note_line=gin_line,
                requested_quantity=return_item.quantity,
                exclude_item_return=item_return,
            )
            slices = cls._historical_slices(
                return_item=return_item,
                gin_line=gin_line,
                previously_returned=previously_returned,
            )
            line_cogs, line_interim = cls._classify_slice_costs(
                slices=slices,
                recognized_quantity=cls._recognized_quantity(gin_line),
                previously_returned=previously_returned,
            )
            cogs_cost += line_cogs
            interim_cost += line_interim
            all_slices.extend(slices)

        for slice_data in all_slices:
            cls._restore_slice(item_return=item_return, slice_data=slice_data)

        inventory_cost = cogs_cost + interim_cost
        if inventory_cost <= 0:
            raise validation_error(
                "The historical return inventory cost must be positive."
            )

        journal = cls._post_journal(
            item_return=item_return,
            inventory_cost=inventory_cost,
            cogs_cost=cogs_cost,
            interim_cost=interim_cost,
        )

        ItemReturnCreditNoteService.create_for_item_return(
            item_return=item_return,
            return_items=return_items,
            locked_gin_lines=locked_gin_lines,
        )

        ItemReturn.objects.filter(pk=item_return.pk).update(
            are_initial_journal_entries_made=True
        )
        item_return.are_initial_journal_entries_made = True
        return journal


class _CustomerPaymentAllocationMethods:

    @staticmethod
    def _settlement_currency(payment):
        if payment.settlement_currency_id:
            return payment.settlement_currency

        customer = payment.get_customer()
        institution = payment.get_institution()
        return (
            customer.currency
            if customer and customer.currency_id
            else institution.currency
        )

    @staticmethod
    def _currencies_match(prepayment, invoice):
        prepayment_currency = CustomerPaymentService._settlement_currency(prepayment)
        invoice_currency = invoice.determine_rate_currency_used()[0]
        return (
            prepayment_currency is not None
            and invoice_currency is not None
            and prepayment_currency.pk == invoice_currency.pk
        )

    @staticmethod
    def _eligible_customer_invoices(*, customer, prepayment):
        from .models import Invoice

        direct_invoices = Invoice.objects.select_for_update().filter(
            customer=customer,
            invoice_payment_status__in=["unpaid", "partially_paid"],
            deleted_at__isnull=True,
            is_active=True,
        )
        quotation_invoices = Invoice.objects.select_for_update().filter(
            customer__isnull=True,
            quotation__customer=customer,
            invoice_payment_status__in=["unpaid", "partially_paid"],
            deleted_at__isnull=True,
            is_active=True,
        )
        purchase_order_invoices = Invoice.objects.select_for_update().filter(
            customer__isnull=True,
            purchase_order__quotation__customer=customer,
            invoice_payment_status__in=["unpaid", "partially_paid"],
            deleted_at__isnull=True,
            is_active=True,
        )
        recurring_invoices = Invoice.objects.select_for_update().filter(
            customer__isnull=True,
            recurring_invoice__customer=customer,
            invoice_payment_status__in=["unpaid", "partially_paid"],
            deleted_at__isnull=True,
            is_active=True,
        )

        invoices_by_pk = {
            invoice.pk: invoice
            for invoice in chain(
                direct_invoices,
                quotation_invoices,
                purchase_order_invoices,
                recurring_invoices,
            )
            if (
                invoice.invoice_status != "canceled"
                and invoice.amount_due > 0
                and CustomerPaymentService._currencies_match(
                    prepayment,
                    invoice,
                )
            )
        }
        return list(invoices_by_pk.values())

    @staticmethod
    @transaction.atomic
    def _auto_settle_prepayment(
        *,
        prepayment,
        customer,
    ):
        institution = prepayment.institution
        auto_settle_enabled = institution.support_auto_settlement_of_invoices
        strategy = (
            prepayment.distribution_strategy
            or customer.deposit_distribution_strategy
            or institution.deposit_distribution_strategy
        )

        if (
            not auto_settle_enabled
            or strategy == DepositDistributionStrategy.HOLD_AS_CREDIT
        ):
            return Decimal(str(prepayment.remaining_balance))

        invoices = CustomerPaymentService._eligible_customer_invoices(
            customer=customer,
            prepayment=prepayment,
        )

        if strategy == DepositDistributionStrategy.PAY_LAST_INVOICE_FIRST:
            invoices.sort(key=lambda invoice: invoice.issue_date, reverse=True)
        elif strategy == DepositDistributionStrategy.PAY_OLDEST_INVOICE_FIRST:
            invoices.sort(key=lambda invoice: invoice.issue_date)
        for invoice in invoices:
            prepayment.refresh_from_db(fields=["remaining_balance"])
            if prepayment.remaining_balance <= 0:
                break
            if invoice.amount_due <= 0:
                continue

            CustomerPaymentService._allocate_prepayment_to_invoice(
                prepayment=prepayment,
                invoice=invoice,
                amount=min(prepayment.remaining_balance, invoice.amount_due),
                reduce_deposit_balance=False,
            )

        prepayment.refresh_from_db(fields=["remaining_balance"])
        return Decimal(str(prepayment.remaining_balance))

    @staticmethod
    def _resolve_original_credit_account(prepayment):
        from django.contrib.contenttypes.models import ContentType
        from transactions.models import Transaction, TransactionEntry

        journal_owner = prepayment.originating_payment or prepayment
        content_type = ContentType.objects.get_for_model(journal_owner.__class__)

        original_transaction_id = (
            Transaction.objects.filter(
                content_type=content_type,
                object_id=journal_owner.pk,
                deleted_at__isnull=True,
            )
            .order_by("created_at", "pk")
            .values_list("pk", flat=True)
            .first()
        )
        if original_transaction_id is None:
            raise validation_error(
                f"Cannot find the original receipt journal for prepayment "
                f"{prepayment.reference_code}. Manual review is required."
            )

        credit_entries = (
            TransactionEntry.objects.filter(
                transaction_id=original_transaction_id,
                entry_type="credit",
                deleted_at__isnull=True,
            )
            .select_related("account__account_role__role_group")
            .order_by("pk")
        )

        accounts = {
            entry.account_id: entry.account
            for entry in credit_entries
            if entry.account_id
        }

        if len(accounts) != 1:
            raise validation_error(
                f"Cannot determine one original credited account for prepayment "
                f"{prepayment.reference_code}. Manual review is required."
            )

        return next(iter(accounts.values()))

    @staticmethod
    def _post_allocation_journal(
        *,
        prepayment,
        invoice,
        customer,
        amount,
        allocation,
    ):
        from django.contrib.contenttypes.models import ContentType
        from django.utils import timezone
        from system.services import FxRateService
        from transactions.services import JournalLine, JournalPostingService
        from utilities.helpers import get_fiscal_year

        institution = customer.get_institution()
        settlement_currency = (
            prepayment.settlement_currency
            or customer.get_currency()
            or institution.currency
        )
        account_currency = (
            None if settlement_currency == institution.currency else settlement_currency
        )

        ar_account = (
            invoice.accounts_receivable_account
            or customer.default_account
            or get_or_create_default_account(
                institution,
                "receivable_account",
                account_currency,
            )
        )
        original_credit_account = (
            CustomerPaymentService._resolve_original_credit_account(prepayment)
        )
        _, deposit_rate = prepayment.determine_settlement_rate_currency_used()
        invoice_currency, invoice_rate = invoice.determine_rate_currency_used()
        deposit_base_amount = FxRateService.translate(amount, deposit_rate)
        invoice_base_amount = FxRateService.translate(amount, invoice_rate)
        journal_lines = [
            JournalLine(
                account=original_credit_account,
                entry_type="debit",
                transaction_amount=amount,
                transaction_currency=settlement_currency,
                exchange_rate=deposit_rate,
                description=(
                    f"Customer prepayment released for invoice "
                    f"{invoice.reference_code}"
                ),
            ),
            JournalLine(
                account=ar_account,
                entry_type="credit",
                transaction_amount=amount,
                transaction_currency=invoice_currency,
                exchange_rate=invoice_rate,
                description=(
                    f"Accounts receivable reduced for invoice {invoice.reference_code}"
                ),
            ),
        ]
        realized_difference = deposit_base_amount - invoice_base_amount
        if realized_difference > Decimal("0"):
            journal_lines.append(
                JournalLine(
                    account=get_or_create_default_account(
                        institution, "fx_gain_loss_account"
                    ),
                    entry_type="credit",
                    transaction_amount=realized_difference,
                    transaction_currency=institution.currency,
                    exchange_rate=Decimal("1"),
                    description=(
                        f"Realized foreign-exchange gain on allocation "
                        f"{allocation.pk}"
                    ),
                )
            )
        elif realized_difference < Decimal("0"):
            journal_lines.append(
                JournalLine(
                    account=get_or_create_default_account(
                        institution, "fx_gain_loss_account"
                    ),
                    entry_type="debit",
                    transaction_amount=abs(realized_difference),
                    transaction_currency=institution.currency,
                    exchange_rate=Decimal("1"),
                    description=(
                        f"Realized foreign-exchange loss on allocation "
                        f"{allocation.pk}"
                    ),
                )
            )

        allocation_date = timezone.localdate()
        transaction_record, _ = JournalPostingService.post(
            fiscal_year=get_fiscal_year(institution, allocation_date),
            title=(
                f"Prepayment {prepayment.reference_code} applied to "
                f"invoice {invoice.reference_code}"
            ),
            description=(
                f"Apply customer deposit {prepayment.reference_code} to "
                f"invoice {invoice.reference_code}"
            ),
            transaction_date=allocation_date,
            lines=journal_lines,
            branch=prepayment.branch or invoice.branch,
            content_type=ContentType.objects.get_for_model(allocation.__class__),
            object_id=allocation.pk,
            source=None,
        )
        return transaction_record

    @staticmethod
    def _verify_allocation_state(*, prepayment, invoice, customer):
        prepayment.refresh_from_db(
            fields=["amount", "amount_reconciled", "remaining_balance"]
        )
        invoice.refresh_from_db(fields=["amount_due"])
        customer.refresh_from_db(
            fields=[
                "deposit_balance",
                "outstanding_receivables_balance",
            ]
        )

        if prepayment.amount_reconciled + prepayment.remaining_balance != (
            prepayment.settlement_amount or prepayment.amount
        ):
            raise validation_error(
                f"Prepayment {prepayment.reference_code} has inconsistent "
                f"reconciled and remaining amounts."
            )

        if invoice.amount_due < 0:
            raise validation_error("Invoice amount due cannot be negative.")

        if customer.deposit_balance < 0:
            raise validation_error("Customer deposit balance cannot be negative.")

    @staticmethod
    @transaction.atomic
    def _allocate_prepayment_to_invoice(
        *,
        prepayment,
        invoice,
        amount,
        reduce_deposit_balance=True,
    ):
        from django.contrib.contenttypes.models import ContentType
        from .models import (
            Customer,
            CustomerBalanceAdjustment,
            CustomerDepositAllocation,
            CustomerPayment,
            Invoice,
        )

        prepayment = (
            CustomerPayment.objects.select_for_update(of=("self",))
            .select_related("customer", "originating_payment")
            .get(pk=prepayment.pk)
        )
        invoice = Invoice.objects.select_for_update().get(pk=invoice.pk)
        customer = Customer.objects.select_for_update().get(pk=prepayment.customer_id)

        invoice_customer = invoice.get_invoice_customer()
        if invoice_customer is None or invoice_customer.pk != customer.pk:
            raise validation_error(
                "The prepayment and invoice must belong to the same customer."
            )

        if (
            not invoice.is_active
            or invoice.deleted_at is not None
            or invoice.invoice_status == "canceled"
            or invoice.invoice_payment_status not in {"unpaid", "partially_paid"}
            or invoice.amount_due <= 0
        ):
            raise validation_error(
                f"Invoice {invoice.reference_code} is not eligible "
                f"for prepayment allocation."
            )

        if not CustomerPaymentService._currencies_match(
            prepayment,
            invoice,
        ):
            raise validation_error("The prepayment and invoice currencies must match.")

        amount = min(
            Decimal(str(amount)),
            Decimal(str(prepayment.remaining_balance)),
            Decimal(str(invoice.amount_due)),
        )
        if amount <= 0:
            return None

        if reduce_deposit_balance and customer.deposit_balance < amount:
            raise validation_error(
                "Customer deposit balance is insufficient for this allocation."
            )

        CustomerDepositAllocation.objects.select_for_update().filter(
            prepayment=prepayment,
            invoice=invoice,
            deleted_at__isnull=True,
        ).first()

        allocation, created = CustomerDepositAllocation.objects.get_or_create(
            prepayment=prepayment,
            invoice=invoice,
            defaults={"amount_applied": amount},
        )
        if not created:
            allocation.amount_applied += amount
            allocation.save(update_fields=["amount_applied"])

        CustomerPayment.objects.filter(pk=prepayment.pk).update(
            amount_reconciled=models.F("amount_reconciled") + amount,
            remaining_balance=models.F("remaining_balance") - amount,
        )

        invoice.amount_due = max(
            Decimal("0"),
            Decimal(str(invoice.amount_due)) - amount,
        )
        invoice.invoice_payment_status = (
            "paid" if invoice.amount_due == Decimal("0") else "partially_paid"
        )
        invoice.save(update_fields=["amount_due", "invoice_payment_status"])

        if customer is None:
            return

        receivable_before = Decimal(customer.outstanding_receivables_balance)
        receivable_after = max(
            Decimal("0"),
            receivable_before - amount,
        )
        updates = {
            "outstanding_receivables_balance": receivable_after,
        }

        deposit_before = Decimal(customer.deposit_balance)
        if reduce_deposit_balance:
            updates["deposit_balance"] = max(
                Decimal("0"),
                deposit_before - amount,
            )

        Customer.objects.filter(pk=customer.pk).update(**updates)

        CustomerBalanceAdjustment.objects.create(
            customer=customer,
            balance_adjusted="OUTSTANDING_RECEIVABLE_BALANCE",
            amount=-amount,
            amount_before_adjustment=receivable_before,
            amount_after_adjustment=receivable_after,
            reason=(
                f"Prepayment {prepayment.reference_code} allocated to "
                f"invoice {invoice.reference_code}"
            ),
            content_type=ContentType.objects.get_for_model(CustomerPayment),
            object_id=prepayment.pk,
        )

        if reduce_deposit_balance:
            CustomerBalanceAdjustment.objects.create(
                customer=customer,
                balance_adjusted="DEPOSIT_BALANCE",
                amount=-amount,
                amount_before_adjustment=deposit_before,
                amount_after_adjustment=updates["deposit_balance"],
                reason=(
                    f"Prepayment {prepayment.reference_code} allocated to "
                    f"invoice {invoice.reference_code}"
                ),
                content_type=ContentType.objects.get_for_model(CustomerPayment),
                object_id=prepayment.pk,
            )

        CustomerPaymentService._post_allocation_journal(
            prepayment=prepayment,
            invoice=invoice,
            customer=customer,
            amount=amount,
            allocation=allocation,
        )

        CustomerPaymentService._verify_allocation_state(
            prepayment=prepayment,
            invoice=invoice,
            customer=customer,
        )
        return allocation


class CreditNoteLineAmountService:
    MONEY_PRECISION = Decimal("0.01")

    @classmethod
    def _money(cls, value) -> Decimal:
        return Decimal(str(value or 0)).quantize(
            cls.MONEY_PRECISION,
            rounding=ROUND_HALF_UP,
        )

    @classmethod
    def components(
        cls,
        quantity: Decimal,
        invoice_line_item: "InvoiceLineItem",
    ) -> dict:
        requested_quantity = Decimal(str(quantity or 0))
        invoiced_quantity = Decimal(str(invoice_line_item.quantity or 0))

        if requested_quantity <= 0:
            raise validation_error("Credit quantity must be greater than zero.")

        if invoiced_quantity <= 0:
            raise validation_error(
                "The originating invoice line has no creditable quantity."
            )

        ratio = requested_quantity / invoiced_quantity
        source_line_total = cls._money(
            invoice_line_item.line_total
            or (
                Decimal(str(invoice_line_item.quantity))
                * Decimal(str(invoice_line_item.unit_price))
            )
        )
        line_amount = cls._money(source_line_total * ratio)

        inclusive_tax = Decimal("0.00")
        exclusive_tax = Decimal("0.00")
        tax_components = []

        for breakdown in invoice_line_item.get_tax_breakdowns().select_related(
            "tax",
            "tax__tax_account",
        ):
            tax_amount = cls._money(Decimal(str(breakdown.tax_amount or 0)) * ratio)
            is_inclusive = (
                breakdown.is_inclusive
                if breakdown.is_inclusive is not None
                else breakdown.tax.is_inclusive
            )

            if is_inclusive:
                inclusive_tax += tax_amount
            else:
                exclusive_tax += tax_amount

            tax_components.append(
                {
                    "breakdown": breakdown,
                    "amount": tax_amount,
                }
            )

        revenue_amount = cls._money(line_amount - inclusive_tax)
        gross_amount = cls._money(line_amount + exclusive_tax)

        return {
            "revenue_amount": revenue_amount,
            "tax_components": tax_components,
            "gross_amount": gross_amount,
        }

    @staticmethod
    def compute(
        quantity: Decimal,
        invoice_line_item: "InvoiceLineItem",
    ) -> Decimal:
        return CreditNoteLineAmountService.components(
            quantity=quantity,
            invoice_line_item=invoice_line_item,
        )["gross_amount"]


class DebitNoteLineAmountService:
    @staticmethod
    def compute(
        quantity: Decimal,
        bill_line_item: "VendorBillLineItem",
    ) -> Decimal:
        return DebitNoteLineAmountService._compute_item_return(quantity, bill_line_item)

    @staticmethod
    def _compute_item_return(quantity: Decimal, bill_line_item) -> Decimal:
        unit_price = Decimal(str(bill_line_item.unit_price))
        return (quantity * unit_price).quantize(Decimal("0.01"))


class DemandNoticeService:
    def __init__(self, institution):
        self.institution = institution

    def get_validated_customer_and_invoices(self, invoice_uuids):

        from customers.models import Invoice
        from django.db.models import QuerySet

        queryset: QuerySet = Invoice.objects.filter(
            base_uuid__in=invoice_uuids,
            customer__institution=self.institution,
        ).select_related("customer")

        found_uuids = set(queryset.values_list("base_uuid", flat=True))
        missing = set(invoice_uuids) - found_uuids

        if missing:
            raise validation_error(f"Some invoices not found: {missing}")

        customers = {inv.customer for inv in queryset}

        if len(customers) > 1:
            raise validation_error(
                "All selected invoices must belong to the same customer."
            )

        customer = next(iter(customers), None)

        if not customer:
            raise validation_error("Customer could not be resolved.")

        if not customer.email:
            raise validation_error("Customer has no email attached.")

        return customer, list(queryset)


class AutoGINCreationService:

    @staticmethod
    @transaction.atomic
    def start(
        *,
        source: "Invoice | CustomerPurchaseOrder",
        inventory_reduction_timing: str,
        source_approval: "Approval | None" = None,
    ):
        from customers.models import CustomerPurchaseOrder, Invoice
        from customers.serializers import GoodsIssuedNoteSerializer

        if not isinstance(source, (Invoice, CustomerPurchaseOrder)):
            raise validation_error("GIN source must be an invoice or sales order.")

        if isinstance(source, Invoice):
            if source.purchase_order_id:
                CustomerPurchaseOrder.objects.select_for_update(
                    of=("self",),
                ).get(pk=source.purchase_order_id)

            source = Invoice.objects.select_for_update(
                of=("self",),
            ).get(pk=source.pk)
        else:
            source = CustomerPurchaseOrder.objects.select_for_update(
                of=("self",),
            ).get(pk=source.pk)

        if source_approval and source_approval.status != "completed":
            raise validation_error("The supplied source approval must be completed.")

        if (
            isinstance(source, CustomerPurchaseOrder)
            and inventory_reduction_timing == "ON_INVOICE"
        ):
            return

        existing_gin = source.goods_issued_notes.filter(
            is_automated=True,
            deleted_at__isnull=True,
        ).first()

        if existing_gin:
            return

        if isinstance(source, Invoice) and source.purchase_order_id:
            purchase_order_gin = source.purchase_order.goods_issued_notes.filter(
                deleted_at__isnull=True,
            ).first()

            if purchase_order_gin:
                return

        line_items = (
            source.line_items.undeleted()
            .select_related(
                "line_item",
                "line_item__inventory_item",
                "unit_of_measure",
            )
            .filter(
                line_item__inventory_item__item_type="GOODS",
            )
        )

        if not line_items.exists():
            source.goods_issued_note_status = "not_required"
            source.save(update_fields=["goods_issued_note_status"])
            return

        source_field = "invoice" if isinstance(source, Invoice) else "purchase_order"

        payload = {
            source_field: source.base_uuid,
            "is_automated": True,
            "line_items": [
                {
                    "line_item": line.line_item.base_uuid,
                    "unit_of_measure": line.unit_of_measure.base_uuid,
                    "quantity": line.quantity,
                }
                for line in line_items
            ],
        }

        serializer = GoodsIssuedNoteSerializer(
            data=payload,
            context={
                "institution": source.get_institution(),
            },
        )

        serializer.is_valid(raise_exception=True)

        gin = serializer.save()

        if (
            isinstance(source, Invoice)
            and inventory_reduction_timing == "ON_INVOICE"
            and source_approval
        ):
            gin.status = "pending"
            gin.save(update_fields=["status"])

            gin.confirm_create(
                inherit_from=source_approval,
                completion_reason=(
                    "Automatically approved from invoice " f"{source.reference_code}."
                ),
            )
        else:
            gin.status = "draft"
            gin.save(update_fields=["status"])

            # ON_GIN creates an editable draft only. The frontend updates the
            # actual quantities being issued and submits the GIN through the
            # existing update approval flow. Stock consumption and inventory
            # journals occur only when that approval completes.

        return gin


class SalesInventoryAccountingService:
    """
    Match approved invoice quantities to historical GIN issue movements.

    Sales Order movement lots are ordered by GIN date/id and movement date/id.
    Approved invoices are ordered by issue date/id. Each (branch, inventory item)
    stream is allocated FIFO across invoice demand, reserving earlier lots for
    earlier invoices as additional GINs are approved.
    """

    COGS_TRANSACTION_TITLE_PREFIX = "Sales inventory COGS recognition for invoice "
    ISSUE_MOVEMENT_TYPES = ("GIN_ISSUE", "NEGATIVE_SALE")
    ACCOUNTING_QUANTUM = Decimal("0.00000000000000000001")

    @classmethod
    def _quantize_accounting_amount(cls, amount):
        """
        Fit calculated amounts into the application's DecimalField precision.

        Stock quantity and unit-cost fields both allow 20 decimal places, so
        multiplying or proportionally allocating them can produce more than 20
        fractional digits. Keep full precision during allocation and round only
        when producing an accounting amount.
        """
        with localcontext() as context:
            context.prec = 70
            return Decimal(amount).quantize(
                cls.ACCOUNTING_QUANTUM,
                rounding=ROUND_HALF_UP,
            )

    @staticmethod
    def _branch_item_key(branch_id, inventory_item_id):
        return branch_id, inventory_item_id

    @staticmethod
    def get_related_gins(invoice):
        from customers.models import GoodsIssuedNote

        relation_filter = Q(invoice=invoice)
        if invoice.purchase_order_id:
            relation_filter |= Q(purchase_order_id=invoice.purchase_order_id)

        return (
            GoodsIssuedNote.objects.filter(
                relation_filter,
                status="approved",
                is_active=True,
                deleted_at__isnull=True,
                is_inventory_removed=True,
            )
            .distinct()
            .order_by("date_issued", "id")
        )

    @classmethod
    def get_issue_movements(cls, gin):
        from items.models import StockMovementLog

        gin_content_type = ContentType.objects.get_for_model(gin.__class__)
        return (
            StockMovementLog.objects.filter(
                content_type=gin_content_type,
                object_id=gin.pk,
                movement_type__in=cls.ISSUE_MOVEMENT_TYPES,
                quantity_change__lt=0,
                deleted_at__isnull=True,
            )
            .select_related("inventory_item", "unit_of_measure", "branch")
            .order_by("movement_date", "id")
        )

    @classmethod
    def get_actual_issued_cost(cls, gin):
        """Value the GIN exactly from persisted issue and oversell movements."""
        movement_cost = sum(
            (abs(Decimal(movement.quantity_change)) * Decimal(movement.unit_cost))
            for movement in cls.get_issue_movements(gin)
        )
        return cls._quantize_accounting_amount(movement_cost)

    @staticmethod
    def _quantity_in_base_units(branch_item, unit_of_measure, quantity):
        from items.unit_converter import get_conversion_factor

        factor = get_conversion_factor(branch_item, unit_of_measure)
        return Decimal(quantity) * Decimal(factor)

    @classmethod
    def _branch_items_for_invoice_group(cls, invoice):
        from items.models import BranchInventoryItem

        if invoice.purchase_order_id:
            invoice_filter = Q(
                customer_line_items__purchase_order_id=invoice.purchase_order_id,
                customer_line_items__deleted_at__isnull=True,
            ) | Q(
                invoicelineitem__invoice__purchase_order_id=invoice.purchase_order_id,
                invoicelineitem__deleted_at__isnull=True,
            )
        else:
            invoice_filter = Q(
                invoicelineitem__invoice=invoice,
                invoicelineitem__deleted_at__isnull=True,
            )

        branch_items = (
            BranchInventoryItem.objects.filter(
                invoice_filter,
                inventory_item__item_type="GOODS",
                deleted_at__isnull=True,
            )
            .select_related("branch", "inventory_item")
            .distinct()
        )
        return {
            cls._branch_item_key(
                branch_item.branch_id,
                branch_item.inventory_item_id,
            ): branch_item
            for branch_item in branch_items
        }

    @classmethod
    def _movement_lots_for_invoice(cls, invoice):
        branch_items = cls._branch_items_for_invoice_group(invoice)
        lots_by_key = {}

        for gin in cls.get_related_gins(invoice):
            for movement in cls.get_issue_movements(gin):
                key = cls._branch_item_key(
                    movement.branch_id,
                    movement.inventory_item_id,
                )
                branch_item = branch_items.get(key)
                if branch_item is None:
                    continue

                movement_quantity = abs(Decimal(movement.quantity_change))
                base_quantity = cls._quantity_in_base_units(
                    branch_item,
                    movement.unit_of_measure,
                    movement_quantity,
                )
                if base_quantity <= 0:
                    continue

                lots_by_key.setdefault(key, []).append(
                    {
                        "quantity": base_quantity,
                        "cost": movement_quantity * Decimal(movement.unit_cost),
                    }
                )

        return lots_by_key

    @classmethod
    def _approved_invoices_for_allocation(cls, invoice):
        from customers.models import Invoice

        if not invoice.purchase_order_id:
            return [invoice]

        return list(
            Invoice.objects.filter(
                purchase_order_id=invoice.purchase_order_id,
                is_active=True,
                deleted_at__isnull=True,
                invoice_status="sent",
                are_initial_journal_entries_made=True,
            ).order_by("issue_date", "id")
        )

    @classmethod
    def _invoice_goods_quantities(cls, invoice):
        quantities = {}
        lines = invoice.line_items.filter(
            line_item__inventory_item__item_type="GOODS",
            deleted_at__isnull=True,
        ).select_related(
            "line_item",
            "line_item__inventory_item",
            "unit_of_measure__unit_of_measure",
        )

        for line in lines:
            key = cls._branch_item_key(
                line.line_item.branch_id,
                line.line_item.inventory_item_id,
            )
            quantity = cls._quantity_in_base_units(
                line.line_item,
                line.unit_of_measure.unit_of_measure,
                line.quantity,
            )
            quantities[key] = quantities.get(key, Decimal("0")) + quantity
        return quantities

    @staticmethod
    def _fifo_cost_for_slice(lots, quantity_to_skip, quantity_to_match):
        """Price a quantity slice from immutable FIFO movement lots."""
        remaining_skip = Decimal(quantity_to_skip)
        remaining_match = Decimal(quantity_to_match)
        matched_cost = Decimal("0")

        for lot in lots:
            if remaining_match <= 0:
                break

            lot_quantity = Decimal(lot["quantity"])
            lot_cost = Decimal(lot["cost"])
            if lot_quantity <= 0:
                continue
            if remaining_skip >= lot_quantity:
                remaining_skip -= lot_quantity
                continue

            available_quantity = lot_quantity - remaining_skip
            available_cost = lot_cost * available_quantity / lot_quantity
            remaining_skip = Decimal("0")
            quantity_taken = min(available_quantity, remaining_match)
            matched_cost += available_cost * quantity_taken / available_quantity
            remaining_match -= quantity_taken

        return matched_cost

    @classmethod
    def _target_cost_for_invoice(cls, invoice):
        lots_by_key = cls._movement_lots_for_invoice(invoice)
        invoices = cls._approved_invoices_for_allocation(invoice)
        quantities_by_invoice = {
            candidate.pk: cls._invoice_goods_quantities(candidate)
            for candidate in invoices
        }
        target_cost = Decimal("0")
        prior_invoice_demand = {}

        for candidate in invoices:
            for key, invoiced_quantity in quantities_by_invoice[candidate.pk].items():
                issued_quantity = sum(
                    (Decimal(lot["quantity"]) for lot in lots_by_key.get(key, [])),
                    Decimal("0"),
                )
                quantity_before = prior_invoice_demand.get(key, Decimal("0"))
                matched_quantity = min(
                    invoiced_quantity,
                    max(issued_quantity - quantity_before, Decimal("0")),
                )
                if candidate.pk == invoice.pk and matched_quantity > 0:
                    target_cost += cls._fifo_cost_for_slice(
                        lots_by_key.get(key, []),
                        quantity_before,
                        matched_quantity,
                    )
                prior_invoice_demand[key] = quantity_before + invoiced_quantity

        return cls._quantize_accounting_amount(target_cost)

    @classmethod
    def _find_cogs_transactions(cls, invoice):
        from transactions.models import Transaction

        invoice_content_type = ContentType.objects.get_for_model(invoice.__class__)
        title = cls.COGS_TRANSACTION_TITLE_PREFIX + invoice.reference_code
        return Transaction.objects.filter(
            content_type=invoice_content_type,
            object_id=invoice.pk,
            transaction_title=title,
            deleted_at__isnull=True,
        )

    @classmethod
    @transaction.atomic
    def recognize_for_invoice(cls, invoice):
        from customers.models import Invoice
        from transactions.models import TransactionEntry
        from transactions.services import JournalLine, JournalPostingService
        from utilities.helpers import get_fiscal_year

        invoice = Invoice.objects.select_for_update().get(pk=invoice.pk)
        if (
            not invoice.is_active
            or invoice.deleted_at is not None
            or not invoice.are_initial_journal_entries_made
        ):
            return Decimal("0")

        target_cost = cls._target_cost_for_invoice(invoice)
        if target_cost <= 0:
            return Decimal("0")

        institution = invoice.get_institution()
        cogs_account = get_or_create_default_account(institution, "cogs_account", None)
        interim_account = get_or_create_default_account(
            institution, "stock_interim_account", None
        )
        recognized_cost = TransactionEntry.objects.filter(
            transaction__in=cls._find_cogs_transactions(invoice),
            account=cogs_account,
            entry_type="debit",
            deleted_at__isnull=True,
        ).aggregate(total=Sum("entry_amount"))["total"] or Decimal("0")

        incremental_cost = cls._quantize_accounting_amount(
            target_cost - recognized_cost
        )
        if incremental_cost <= 0:
            return Decimal("0")

        JournalPostingService.post(
            fiscal_year=get_fiscal_year(institution, date=invoice.issue_date),
            title=cls.COGS_TRANSACTION_TITLE_PREFIX + invoice.reference_code,
            description=(
                "Incremental COGS recognition from actual GIN stock movements "
                f"for invoice {invoice.reference_code}"
            ),
            lines=[
                JournalLine(
                    account=cogs_account,
                    entry_type="debit",
                    transaction_amount=incremental_cost,
                    transaction_currency=institution.currency,
                    exchange_rate=Decimal("1"),
                    description=f"Incremental actual COGS for invoice {invoice.reference_code}",
                ),
                JournalLine(
                    account=interim_account,
                    entry_type="credit",
                    transaction_amount=incremental_cost,
                    transaction_currency=institution.currency,
                    exchange_rate=Decimal("1"),
                    description=(
                        "Stock Interim clearing for actual goods matched to invoice "
                        f"{invoice.reference_code}"
                    ),
                ),
            ],
            branch=invoice.branch,
            content_type=ContentType.objects.get_for_model(invoice.__class__),
            object_id=invoice.pk,
            transaction_date=invoice.issue_date,
        )
        return incremental_cost

    @classmethod
    def recognize_for_gin(cls, gin):
        from customers.models import Invoice

        if gin.invoice_id:
            cls.recognize_for_invoice(gin.invoice)
            return
        if not gin.purchase_order_id:
            return

        invoices = Invoice.objects.filter(
            purchase_order_id=gin.purchase_order_id,
            is_active=True,
            deleted_at__isnull=True,
            invoice_status="sent",
            are_initial_journal_entries_made=True,
        ).order_by("issue_date", "id")
        for invoice in invoices:
            cls.recognize_for_invoice(invoice)


class CustomerPaymentService(_CustomerPaymentAllocationMethods):

    @staticmethod
    @transaction.atomic
    def reconcile_prepayments(
        *,
        prepayment_uuids,
        invoice_uuids,
        institution,
    ):
        from .models import (
            CustomerDepositAllocation,
            CustomerPayment,
            Invoice,
        )

        prepayments = list(
            CustomerPayment.objects.select_for_update(of=("self",))
            .select_related("customer", "originating_payment")
            .filter(
                base_uuid__in=prepayment_uuids,
                institution=institution,
                payment_status="APPROVED",
                customer__isnull=False,
                invoice__isnull=True,
                deleted_at__isnull=True,
            )
        )

        found_prepayment_uuids = {
            str(prepayment.base_uuid) for prepayment in prepayments
        }

        missing_prepayments = {
            str(value) for value in prepayment_uuids
        } - found_prepayment_uuids

        if missing_prepayments:
            raise validation_error(
                "The following prepayment UUIDs were not found or are "
                f"not eligible: {', '.join(sorted(missing_prepayments))}"
            )

        customer_ids = {prepayment.customer_id for prepayment in prepayments}

        if len(customer_ids) != 1:
            raise validation_error("All prepayments must belong to the same customer.")

        invalid_prepayments = [
            prepayment
            for prepayment in prepayments
            if prepayment.remaining_balance <= 0
        ]

        if invalid_prepayments:
            refs = ", ".join(
                prepayment.reference_code for prepayment in invalid_prepayments
            )

            raise validation_error(f"Prepayments with no remaining balance: {refs}")

        invoice_ids = list(
            Invoice.objects.filter(
                base_uuid__in=invoice_uuids,
                deleted_at__isnull=True,
            )
            .filter(
                models.Q(branch__institution=institution)
                | models.Q(customer__institution=institution)
                | models.Q(quotation__branch__institution=institution)
                | models.Q(quotation__customer__institution=institution)
                | models.Q(purchase_order__branch__institution=institution)
                | models.Q(purchase_order__customer__institution=institution)
                | models.Q(recurring_invoice__branch__institution=institution)
                | models.Q(recurring_invoice__customer__institution=institution)
                | models.Q(sales_person__institution=institution)
            )
            .values_list("id", flat=True)
            .distinct()
        )

        invoices = list(
            Invoice.objects.select_for_update(of=("self",)).filter(id__in=invoice_ids)
        )

        found_invoice_uuids = {str(invoice.base_uuid) for invoice in invoices}

        missing_invoices = {str(value) for value in invoice_uuids} - found_invoice_uuids

        if missing_invoices:
            raise validation_error(
                "The following invoice UUIDs were not found: "
                f"{', '.join(sorted(missing_invoices))}"
            )

        prepayments.sort(key=lambda item: item.created_at)
        invoices.sort(key=lambda item: item.created_at)

        allocations: list[CustomerDepositAllocation] = []

        for invoice in invoices:
            for prepayment in prepayments:
                prepayment.refresh_from_db(fields=["remaining_balance"])

                invoice.refresh_from_db(fields=["amount_due"])

                if prepayment.remaining_balance <= 0:
                    continue

                if invoice.amount_due <= 0:
                    break

                allocation = CustomerPaymentService._allocate_prepayment_to_invoice(
                    prepayment=prepayment,
                    invoice=invoice,
                    amount=min(
                        prepayment.remaining_balance,
                        invoice.amount_due,
                    ),
                    reduce_deposit_balance=True,
                )

                if allocation:
                    allocations.append(allocation)

        return allocations

    @staticmethod
    def calculate_payment_split(payment, invoice=None):
        amount = Decimal(str(payment.settlement_amount or payment.amount))

        if amount <= 0:
            raise validation_error("Payment amount must be greater than zero.")

        if invoice is None:
            invoice_applied_amount = Decimal("0")
            excess_amount = amount
        else:
            invoice_due = Decimal(str(invoice.amount_due))
            if invoice_due < 0:
                raise validation_error("Invoice amount due cannot be negative.")

            invoice_applied_amount = min(amount, invoice_due)
            excess_amount = amount - invoice_applied_amount

        if invoice_applied_amount < 0 or excess_amount < 0:
            raise validation_error("The payment split produced a negative amount.")

        if invoice_applied_amount + excess_amount != amount:
            raise validation_error(
                "The invoice-applied amount and excess amount must equal "
                "the receipt amount."
            )

        return {
            "invoice_applied_amount": invoice_applied_amount,
            "excess_amount": excess_amount,
        }

    @staticmethod
    def create_generated_overpayment(
        *,
        originating_payment,
        customer,
        excess_amount,
    ):
        from .models import CustomerPayment

        if excess_amount <= 0:
            return None

        existing = (
            originating_payment.generated_prepayments.select_for_update()
            .filter(deleted_at__isnull=True)
            .first()
        )
        if existing:
            return existing

        settlement_currency, _ = (
            originating_payment.determine_settlement_rate_currency_used()
        )

        generated = CustomerPayment.objects.create(
            invoice=None,
            customer=customer,
            originating_payment=originating_payment,
            amount=excess_amount,
            currency=settlement_currency,
            settlement_currency=settlement_currency,
            settlement_amount=excess_amount,
            amount_reconciled=Decimal("0"),
            remaining_balance=excess_amount,
            institution=originating_payment.institution,
            branch=originating_payment.branch,
            payment_date=originating_payment.payment_date,
            coa_cash_account=None,
            payment_status="APPROVED",
            are_initial_journal_entries_made=True,
            is_active=True,
            description=(
                f"Overpayment generated from receipt "
                f"{originating_payment.reference_code}"
            ),
        )

        from system.services import FxRateService

        payment_currency, payment_rate = (
            originating_payment.determine_rate_currency_used()
        )
        settlement_amount = Decimal(
            str(originating_payment.settlement_amount or originating_payment.amount)
        )
        effective_settlement_rate = (
            FxRateService.translate(
                originating_payment.amount,
                payment_rate,
            )
            / settlement_amount
        )

        FxRateService.create_document_snapshot(
            source=generated,
            institution=generated.institution,
            currency=settlement_currency,
            supplied_rate=effective_settlement_rate,
        )

        return generated

    @staticmethod
    def apply_invoice_portion(
        *,
        payment,
        invoice,
        customer,
        amount,
    ):
        from django.contrib.contenttypes.models import ContentType
        from .models import CustomerBalanceAdjustment, CustomerPayment

        if amount <= 0:
            return

        invoice.amount_due = max(
            Decimal("0"),
            Decimal(str(invoice.amount_due)) - amount,
        )
        invoice.invoice_payment_status = (
            "paid" if invoice.amount_due == Decimal("0") else "partially_paid"
        )
        invoice.save(update_fields=["amount_due", "invoice_payment_status"])

        if customer is None:
            return

        receivable_before = Decimal(customer.outstanding_receivables_balance)
        receivable_after = max(
            Decimal("0"),
            receivable_before - amount,
        )

        customer.__class__.objects.filter(pk=customer.pk).update(
            outstanding_receivables_balance=receivable_after
        )
        customer.outstanding_receivables_balance = receivable_after

        CustomerBalanceAdjustment.objects.create(
            customer=customer,
            balance_adjusted="OUTSTANDING_RECEIVABLE_BALANCE",
            amount=-amount,
            amount_before_adjustment=receivable_before,
            amount_after_adjustment=receivable_after,
            reason=(
                f"Payment {payment.reference_code} applied to "
                f"invoice {invoice.reference_code}"
            ),
            content_type=ContentType.objects.get_for_model(CustomerPayment),
            object_id=payment.pk,
        )

    @staticmethod
    def apply_standalone_prepayment(
        *,
        payment,
        customer,
        transaction_record,
        create_receipt_journal=False,
    ):
        from django.contrib.contenttypes.models import ContentType
        from .models import CustomerBalanceAdjustment, CustomerPayment

        remaining = CustomerPaymentService._auto_settle_prepayment(
            prepayment=payment,
            customer=customer,
        )

        deposit_before = Decimal(customer.deposit_balance)
        deposit_after = deposit_before + remaining

        if remaining > 0:
            customer.__class__.objects.filter(pk=customer.pk).update(
                deposit_balance=deposit_after
            )
            customer.deposit_balance = deposit_after

            CustomerBalanceAdjustment.objects.create(
                customer=customer,
                balance_adjusted="DEPOSIT_BALANCE",
                amount=remaining,
                amount_before_adjustment=deposit_before,
                amount_after_adjustment=deposit_after,
                reason=f"Available prepayment {payment.reference_code}",
                content_type=ContentType.objects.get_for_model(CustomerPayment),
                object_id=payment.pk,
            )

        payment.refresh_from_db(fields=["amount_reconciled", "remaining_balance"])
        return remaining

    @staticmethod
    def process_overpayment_or_prepayment(
        *,
        payment,
        transaction_record,
        customer,
        invoice,
        invoice_applied_amount,
        excess_amount,
    ):
        from .models import CustomerPayment

        if invoice is not None:
            CustomerPaymentService.apply_invoice_portion(
                payment=payment,
                invoice=invoice,
                customer=customer,
                amount=invoice_applied_amount,
            )

            CustomerPayment.objects.filter(pk=payment.pk).update(
                amount_reconciled=invoice_applied_amount,
                remaining_balance=Decimal("0"),
            )

            if excess_amount <= 0:
                return None

            if customer is None:
                raise validation_error(
                    "Overpayment cannot be stored without a customer."
                )

            generated = CustomerPaymentService.create_generated_overpayment(
                originating_payment=payment,
                customer=customer,
                excess_amount=excess_amount,
            )

            CustomerPaymentService.apply_standalone_prepayment(
                payment=generated,
                customer=customer,
                transaction_record=transaction_record,
                create_receipt_journal=False,
            )
            return generated

        CustomerPaymentService.apply_standalone_prepayment(
            payment=payment,
            customer=customer,
            transaction_record=transaction_record,
            create_receipt_journal=False,
        )
        return payment

    @staticmethod
    @transaction.atomic
    def process_financial_events(customer_payment, *, merchant_fee=Decimal("0")):
        from accounts.utils import get_or_create_default_account
        from django.contrib.contenttypes.models import ContentType
        from system.services import FxRateService
        from transactions.services import JournalLine, JournalPostingService
        from utilities.helpers import get_fiscal_year
        from .models import (
            Customer,
            Invoice,
            CustomerPayment,
        )

        payment = (
            CustomerPayment.objects.select_for_update(of=("self",))
            .select_related(
                "customer",
                "invoice",
                "originating_payment",
                "coa_cash_account",
            )
            .get(pk=customer_payment.pk)
        )

        if payment.are_initial_journal_entries_made:
            return None

        if payment.is_generated_overpayment:
            CustomerPayment.objects.filter(pk=payment.pk).update(
                are_initial_journal_entries_made=True
            )
            return None

        institution = payment.get_institution()
        payment_customer = payment.get_customer()

        customer = None
        if payment_customer is not None:
            customer = Customer.objects.select_for_update().get(pk=payment_customer.pk)
        elif not payment.is_invoice_payment:
            raise validation_error(
                "A customer is required for a standalone prepayment."
            )

        payment_amount = Decimal(str(payment.amount))
        merchant_fee = Decimal(str(merchant_fee))

        if (
            not merchant_fee.is_finite()
            or merchant_fee < Decimal("0")
            or merchant_fee >= payment_amount
        ):
            raise validation_error("Invalid merchant collection fee.")

        cash_received = payment_amount - merchant_fee
        cash_account = payment.coa_cash_account
        if cash_account is None:
            raise validation_error(
                "A cash or bank account is required to process this receipt."
            )

        linked_cash_account = cash_account.get_cash_account_reference()
        if linked_cash_account is None:
            raise validation_error(
                "The selected COA cash account is not linked to an "
                "operational cash or bank account."
            )

        invoice = None
        if payment.is_invoice_payment:
            invoice = Invoice.objects.select_for_update().get(pk=payment.invoice_id)

        settlement_amount = Decimal(str(payment.settlement_amount or payment.amount))
        settlement_currency = payment.settlement_currency

        if settlement_currency is None and invoice is not None:
            settlement_currency = invoice.determine_rate_currency_used()[0]

        if settlement_currency is None:
            settlement_currency = (
                customer.currency
                if customer is not None and customer.currency_id
                else institution.currency
            )

        split = CustomerPaymentService.calculate_payment_split(
            payment,
            invoice=invoice,
        )

        if (
            invoice is not None
            and customer is None
            and split["excess_amount"] > Decimal("0")
        ):
            raise validation_error(
                "Overpayment is not allowed for an invoice without a customer."
            )

        payment_currency, payment_rate = payment.determine_rate_currency_used()
        payment_base_amount = FxRateService.translate(
            payment_amount,
            payment_rate,
        )
        effective_settlement_rate = payment_base_amount / settlement_amount

        account_currency = (
            None if settlement_currency == institution.currency else settlement_currency
        )

        if invoice is not None:
            credit_account = (
                invoice.accounts_receivable_account
                or (
                    customer.default_account
                    if customer is not None and customer.default_account
                    else None
                )
                or get_or_create_default_account(
                    institution,
                    "receivable_account",
                    account_currency,
                )
            )
        else:
            credit_account = customer.default_account or get_or_create_default_account(
                institution,
                "receivable_account",
                account_currency,
            )

        if payment.is_standalone_prepayment:
            transaction_title = f"Customer prepayment {payment.reference_code}"
            debit_description = f"Customer prepayment for {customer.customer_name}"
        else:
            transaction_title = (
                f"Customer payment {payment.reference_code} "
                f"for invoice {invoice.reference_code}"
            )
            debit_description = f"Payment received for invoice {invoice.reference_code}"

        party_name = (
            customer.customer_name
            if customer is not None
            else f"invoice {invoice.reference_code}"
        )

        from bank_management.services import CashAccountService

        CashAccountService.inflow(
            instance=linked_cash_account,
            amount=cash_received,
            source=payment,
            source_reference_code=payment.reference_code,
            source_reference_name=transaction_title,
        )

        journal_lines = [
            JournalLine(
                account=cash_account,
                entry_type="debit",
                transaction_amount=cash_received,
                transaction_currency=payment_currency,
                exchange_rate=payment_rate,
                description=debit_description,
            )
        ]

        if merchant_fee:
            journal_lines.append(
                JournalLine(
                    account=get_or_create_default_account(
                        institution,
                        "other_expense_account",
                    ),
                    entry_type="debit",
                    transaction_amount=merchant_fee,
                    transaction_currency=payment_currency,
                    exchange_rate=payment_rate,
                    description=f"BaisoftPay fee for {payment.reference_code}",
                )
            )

        invoice_applied_amount = split["invoice_applied_amount"]
        excess_amount = split["excess_amount"]
        credit_base_amount = Decimal("0")

        if invoice is not None and invoice_applied_amount > 0:
            invoice_currency, invoice_historical_rate = (
                invoice.determine_rate_currency_used()
            )
            journal_lines.append(
                JournalLine(
                    account=credit_account,
                    entry_type="credit",
                    transaction_amount=invoice_applied_amount,
                    transaction_currency=invoice_currency,
                    exchange_rate=invoice_historical_rate,
                    description=(f"Accounts receivable credited for {party_name}"),
                )
            )
            credit_base_amount += FxRateService.translate(
                invoice_applied_amount,
                invoice_historical_rate,
            )

        if invoice is None or excess_amount > 0:
            deposit_amount = settlement_amount if invoice is None else excess_amount
            journal_lines.append(
                JournalLine(
                    account=credit_account,
                    entry_type="credit",
                    transaction_amount=deposit_amount,
                    transaction_currency=settlement_currency,
                    exchange_rate=effective_settlement_rate,
                    description=(f"Customer deposit credited for {party_name}"),
                )
            )
            credit_base_amount += FxRateService.translate(
                deposit_amount,
                effective_settlement_rate,
            )

        realized_difference = payment_base_amount - credit_base_amount

        if realized_difference > Decimal("0"):
            gain_account = get_or_create_default_account(
                institution,
                "fx_gain_loss_account",
            )
            journal_lines.append(
                JournalLine(
                    account=gain_account,
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
            loss_account = get_or_create_default_account(
                institution,
                "fx_gain_loss_account",
            )
            journal_lines.append(
                JournalLine(
                    account=loss_account,
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
                f"for {party_name}"
            ),
            transaction_date=payment.payment_date,
            lines=journal_lines,
            branch=payment.branch,
            content_type=ContentType.objects.get_for_model(CustomerPayment),
            object_id=payment.pk,
            source=payment,
        )

        CustomerPaymentService.process_overpayment_or_prepayment(
            payment=payment,
            transaction_record=transaction_record,
            customer=customer,
            invoice=invoice,
            invoice_applied_amount=split["invoice_applied_amount"],
            excess_amount=split["excess_amount"],
        )

        CustomerPayment.objects.filter(pk=payment.pk).update(
            are_initial_journal_entries_made=True
        )
        customer_payment.are_initial_journal_entries_made = True

        return transaction_record
