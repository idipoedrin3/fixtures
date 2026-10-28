from dataclasses import replace
from django.db import models
from django.utils import timezone
from django.core.exceptions import ValidationError
from utilities.utility_base_model import SoftDeletableTimeStampedModel
from utilities.email_client import EmailClient
from utilities.common_models import BaseTimeStamp
from utilities.helpers import (
    format_currency_numbers_in_text,
    get_due_date_based_on_payment_terms,
    get_fiscal_year,
    validation_error,
)
from approval.models import Approval, BaseApprovableModel
from django.db import transaction
from reports.mixins import ReportableModelMixin
from decimal import ROUND_HALF_UP, Decimal
from django.contrib.contenttypes.models import ContentType
from django.contrib.contenttypes.fields import GenericForeignKey
from system.models import ForeignExchange, GenderChoice
from django.contrib.contenttypes.fields import GenericRelation
from taxation.models import TaxApplicationBreakDown
from django.db.models import Sum
from decimal import Decimal


class Vendor(ReportableModelMixin, BaseApprovableModel):
    reference_prefix = "VEN"

    VENDOR_TYPE_CHOICES = [
        ("individual", "Individual"),
        ("business", "Business"),
    ]

    institution = models.ForeignKey(
        "institution.Institution",
        on_delete=models.CASCADE,
        related_name="vendors",
    )

    vendor_name = models.CharField(
        max_length=100,
        blank=False,
        null=False,
        help_text="The official name of the vendor.",
    )

    tax_identification_number = models.CharField(
        max_length=50,
        blank=True,
        null=True,
        help_text="Tax Identification Number (TIN) for the vendor.",
    )

    payment_term = models.ForeignKey(
        "customers.PaymentTerm",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        help_text="Select payment terms applicable to this vendor.",
    )
    vendor_type = models.CharField(max_length=20, choices=VENDOR_TYPE_CHOICES)

    default_account_payable = models.ForeignKey(
        "accounts.Account",
        on_delete=models.CASCADE,
        null=True,
        blank=True,
        related_name="vendors",
        help_text="The default Accounts Payable account used for this vendor.",
    )
    address = models.CharField(max_length=255, blank=True, null=True)
    phone_number = models.CharField(max_length=15, blank=True, null=True)
    email = models.EmailField(max_length=254, blank=True, null=True)
    website = models.URLField(max_length=200, blank=True, null=True)
    gender = models.CharField(
        max_length=10,
        choices=GenderChoice.choices,
        default="OTHER",
        null=True,
        blank=True,
    )
    currency = models.ForeignKey(
        "system.SystemCurrency", on_delete=models.CASCADE, null=True, blank=True
    )
    vendor_payment_options = models.ManyToManyField(
        "VendorPaymentOption", blank=True, related_name="vendors"
    )

    opening_balance = models.DecimalField(
        max_digits=50,
        decimal_places=20,
        default=0.00,
    )
    opening_balance_received_date = models.DateField(null=True, blank=True)
    opening_balance_account = models.ForeignKey(
        "accounts.Account",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="vendor_opening_balances",
        help_text="The account used to record the opening balance for this vendor. If not specified, the system will use the default opening account.",
    )
    deposit_balance = models.DecimalField(
        max_digits=50, decimal_places=20, default=0.00
    )
    outstanding_payables = models.DecimalField(
        max_digits=50, decimal_places=20, default=0.00
    )

    requisition_beneficiary = models.OneToOneField(
        "requisitions.RequisitionBeneficiary",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="vendor",
    )

    are_initial_transactions_processed = models.BooleanField(default=False)

    search_fields = [
        "vendor_name",
        "email",
        "phone_number",
        "vendor_type",
        "tax_identification_number",
    ]

    ordering_fields = [
        "vendor_name",
        "outstanding_payables",
        "deposit_balance",
        "created_at",
    ]

    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=["institution", "tax_identification_number"],
                name="vendor_unique_tin_per_institution",
                condition=models.Q(tax_identification_number__isnull=False),
            )
        ]
        ordering = ["created_at"]
        verbose_name = "Vendor"
        verbose_name_plural = "Vendors"

    def clean(self):
        if (
            self.default_account_payable
            and self.currency != self.default_account_payable.get_account_currency()
        ):
            raise validation_error(
                "The default account payable currency must match the vendor currency."
            )

        if (
            self.opening_balance != Decimal("0")
            and not self.opening_balance_received_date
        ):
            raise validation_error(
                "You must specify the date for which this opening balance was created."
            )

    def __str__(self):
        return f"Vendor {self.vendor_name} ({self.reference_code})"

    def get_institution(self):
        return self.institution

    def get_gender_and_name(self):
        full_name = self.vendor_name

        if self.vendor_type == "business":
            return full_name

        if self.gender == "MALE":
            title = "Mr."
        elif self.gender == "FEMALE":
            title = "Mrs."
        else:
            return full_name

        return f"{title} {full_name}"

    @transaction.atomic
    def _process_financial_events(self):
        from accounts.utils import get_or_create_default_account
        from django.contrib.contenttypes.models import ContentType
        from transactions.services import JournalLine, JournalPostingService
        from utilities.helpers import format_2dp

        if self.are_initial_transactions_processed:
            return

        if self.opening_balance == 0:
            return

        institution = self.get_institution()
        opening_balance_date = self.opening_balance_received_date or (
            self.created_at.date() if self.created_at else timezone.localdate()
        )

        fiscal_year = get_fiscal_year(
            institution,
            opening_balance_date,
        )

        journal_owner = (
            self._create_opening_balance_bill()
            if self.opening_balance > 0
            else self._create_opening_balance_prepayment(opening_balance_date)
        )

        if journal_owner is None:
            raise validation_error(
                "An active branch is required to process the vendor opening balance."
            )

        opening_balance_account = (
            self.opening_balance_account
            or get_or_create_default_account(
                institution, "opening_balance_account", self.currency
            )
        )

        payable_account = self.default_account_payable or get_or_create_default_account(
            institution, "payable_account", self.currency
        )

        document_currency, document_rate = journal_owner.determine_rate_currency_used()
        amount = abs(self.opening_balance)

        if self.opening_balance > 0:
            journal_lines = [
                JournalLine(
                    account=payable_account,
                    entry_type="credit",
                    transaction_amount=amount,
                    transaction_currency=document_currency,
                    exchange_rate=document_rate,
                    description=f"Accounts payable: {self.vendor_name}",
                ),
                JournalLine(
                    account=opening_balance_account,
                    entry_type="debit",
                    transaction_amount=amount,
                    transaction_currency=document_currency,
                    exchange_rate=document_rate,
                    description="Opening vendor balance offset",
                ),
            ]
        else:
            journal_lines = [
                JournalLine(
                    account=payable_account,
                    entry_type="debit",
                    transaction_amount=amount,
                    transaction_currency=document_currency,
                    exchange_rate=document_rate,
                    description=f"Vendor prepayment: {self.vendor_name}",
                ),
                JournalLine(
                    account=opening_balance_account,
                    entry_type="credit",
                    transaction_amount=amount,
                    transaction_currency=document_currency,
                    exchange_rate=document_rate,
                    description="Opening vendor prepayment offset",
                ),
            ]

        JournalPostingService.post(
            fiscal_year=fiscal_year,
            title=f"Opening Balance for {self.vendor_name}",
            description=(
                f"Vendor recorded with opening balance of "
                f"{self.currency.code} {format_2dp(self.opening_balance)}"
            ),
            transaction_date=opening_balance_date,
            lines=journal_lines,
            content_type=ContentType.objects.get_for_model(
                journal_owner.__class__,
                for_concrete_model=False,
            ),
            object_id=journal_owner.id,
            source=journal_owner,
        )

        self.apply_opening_balance()

        Vendor.objects.filter(pk=self.pk).update(
            are_initial_transactions_processed=True
        )
        self.are_initial_transactions_processed = True

    @transaction.atomic
    def apply_opening_balance(self):
        if self.opening_balance == 0:
            return

        from django.db.models import F

        amount = abs(self.opening_balance)

        if self.opening_balance > 0:
            before = self.outstanding_payables

            Vendor.objects.filter(pk=self.pk).update(
                outstanding_payables=F("outstanding_payables") + amount
            )

            self.refresh_from_db(fields=["outstanding_payables"])
            after = self.outstanding_payables
            balance_type = "OUTSTANDING_PAYABLE_BALANCE"

        else:
            before = self.deposit_balance

            Vendor.objects.filter(pk=self.pk).update(
                deposit_balance=F("deposit_balance") + amount
            )

            self.refresh_from_db(fields=["deposit_balance"])
            after = self.deposit_balance
            balance_type = "DEPOSIT_BALANCE"

        VendorOutstandingBalanceAdjustment.objects.create(
            vendor=self,
            amount=amount,
            amount_before_adjustment=before,
            amount_after_adjustment=after,
            balance_adjusted=balance_type,
            reason="Opening Balance Applied",
        )

    def _create_opening_balance_bill(self):

        institution = self.get_institution()
        branch = (
            institution.branches.filter(
                is_active=True,
                deleted_at__isnull=True,
            )
            .order_by("created_at")
            .first()
        )
        if not branch:
            return

        bill_date = self.opening_balance_received_date or timezone.now().date()
        amount = abs(self.opening_balance)

        bill = VendorBill(
            vendor=self,
            branch=branch,
            received_date=bill_date,
            due_date=bill_date,
            status="approved",
            payment_status="unpaid",
            are_initial_journal_entries_made=True,  # SUPPRESS FURTHER LEDGER ENTRIES
            total_amount=amount,
            balance_due=amount,
            total_net_amount=amount,
            adjusted_total=amount,
            description=f"Balance forward as of {bill_date}. Initial opening balance recorded on vendor creation.",
            goods_received_note_status="full_received",
        )
        bill.save()

        if self.currency != institution.currency:
            from system.services import FxRateService

            _, opening_balance_rate = self.determine_rate_currency_used()
            FxRateService.create_document_snapshot(
                source=bill,
                institution=institution,
                currency=self.currency,
                supplied_rate=opening_balance_rate,
            )

        bill.confirm_create()
        return bill

    def _create_opening_balance_prepayment(self, payment_date):
        institution = self.get_institution()

        branch = (
            institution.branches.filter(
                is_active=True,
                deleted_at__isnull=True,
            )
            .order_by("created_at")
            .first()
        )
        if not branch:
            return

        amount = abs(self.opening_balance)

        payment = VendorPayment.objects.create(
            branch=branch,
            vendor=self,
            bill=None,
            amount=amount,
            amount_reconciled=Decimal("0"),
            remaining_balance=amount,
            payment_date=payment_date,
            payment_status="PAID",
            approval_status="active",
            is_active=True,
            are_initial_journal_entries_made=True,
        )

        if self.currency != institution.currency:
            from system.services import FxRateService

            _, opening_balance_rate = self.determine_rate_currency_used()
            FxRateService.create_document_snapshot(
                source=payment,
                institution=institution,
                currency=self.currency,
                supplied_rate=opening_balance_rate,
            )

        return payment

    def save(self, *args, **kwargs):
        with transaction.atomic():
            outstanding_payables_balance_change_reason = kwargs.pop(
                "outstanding_payables_balance_change_reason", None
            )
            deposit_balance_change_reason = kwargs.pop(
                "deposit_balance_change_reason", None
            )

            self.full_clean()
            is_new = self._state.adding

            previous_payables_balance = None
            previous_deposits_balance = None

            if not is_new and self.pk:
                previous_payables_balance = (
                    Vendor.objects.filter(pk=self.pk)
                    .values_list("outstanding_payables", flat=True)
                    .first()
                )
                previous_deposits_balance = (
                    Vendor.objects.filter(pk=self.pk)
                    .values_list("deposit_balance", flat=True)
                    .first()
                )

            super().save(*args, **kwargs)

            if (
                previous_payables_balance is not None
                and previous_payables_balance != self.outstanding_payables
            ):
                VendorOutstandingBalanceAdjustment.objects.create(
                    vendor=self,
                    balance_adjusted="OUTSTANDING_PAYABLE_BALANCE",
                    amount=self.outstanding_payables - previous_payables_balance,
                    amount_before_adjustment=previous_payables_balance,
                    amount_after_adjustment=self.outstanding_payables,
                    reason=outstanding_payables_balance_change_reason
                    or "Outstanding payable updated via vendor record save.",
                )

            if (
                previous_deposits_balance is not None
                and previous_deposits_balance != self.deposit_balance
            ):
                VendorOutstandingBalanceAdjustment.objects.create(
                    vendor=self,
                    balance_adjusted="DEPOSIT_BALANCE",
                    amount=self.deposit_balance - previous_deposits_balance,
                    amount_before_adjustment=previous_deposits_balance,
                    amount_after_adjustment=self.deposit_balance,
                    reason=deposit_balance_change_reason
                    or "Deposit balance updated via vendor record save.",
                )

    @transaction.atomic
    def finish_workflow(self, approval: Approval):
        if approval.status == "completed":
            if approval.action.name in ["create", "update"]:
                self.is_active = True

                if not self.are_initial_transactions_processed:
                    self._process_financial_events()

                if approval.action.name == "create":
                    self._ensure_requisition_beneficiary()

            elif approval.action.name == "delete":
                self.is_active = False
                self.deleted_at = timezone.now()
        elif approval.status == "rejected":
            if approval.action.name == "create":
                self.is_active = False
                self.deleted_at = timezone.now()

            elif approval.action.name in ["update", "delete"]:
                self.is_active = False
                self.deleted_at = None

        self.save()

    def determine_rate_currency_used(self):
        institution_currency = self.get_institution().currency

        foreign_exchange_record = (
            ForeignExchange.objects.filter(
                content_type=ContentType.objects.get_for_model(self),
                object_id=self.pk,
            )
            .order_by("-created_at")
            .first()
        )
        return (
            (
                foreign_exchange_record.from_currency,
                foreign_exchange_record.rate,
            )
            if foreign_exchange_record
            else (
                institution_currency,
                1,
            )
        )

    def get_currency(self):
        return self.currency, True

    @transaction.atomic
    def _ensure_requisition_beneficiary(self):
        from requisitions.models import RequisitionBeneficiary

        if self.requisition_beneficiary_id:
            return self.requisition_beneficiary

        beneficiary = RequisitionBeneficiary.objects.create(
            institution=self.institution,
            name=self.vendor_name,
            contact_phone_number=self.phone_number,
            email=self.email,
            created_by=self.created_by,
            updated_by=self.updated_by,
        )
        self.requisition_beneficiary = beneficiary
        self.save(update_fields=["requisition_beneficiary"])
        return beneficiary


class VendorPaymentOption(SoftDeletableTimeStampedModel):
    vendor = models.ForeignKey(
        Vendor, on_delete=models.CASCADE, related_name="payment_options"
    )

    title = models.CharField(
        max_length=100, help_text="The name of the payment option."
    )

    def __str__(self):
        return f"{self.vendor.vendor_name} - {self.title}"


class VendorPurchaseOrder(ReportableModelMixin, BaseApprovableModel):
    reference_prefix = "VPO"

    PURCHASE_ORDER_STATUS_CHOICES = [
        ("draft", "Draft"),
        ("approved", "Approved"),
        ("delivered", "Delivered"),
        ("billed", "Billed"),
        ("canceled", "Canceled"),
    ]

    institution = models.ForeignKey(
        "institution.Institution",
        on_delete=models.CASCADE,
        related_name="vendor_purchase_orders",
        blank=True,
        null=True,
    )

    vendor = models.ForeignKey(
        "vendors.Vendor", on_delete=models.CASCADE, related_name="purchase_orders"
    )

    request_requisition = models.ForeignKey(
        "requisitions.Requisition",
        on_delete=models.SET_NULL,
        related_name="vendor_purchase_orders",
        null=True,
        blank=True,
        help_text="Optional link to the requisition that led to this purchase order.",
    )

    status = models.CharField(
        max_length=20, choices=PURCHASE_ORDER_STATUS_CHOICES, default="draft"
    )

    goods_received_note_status = models.CharField(
        max_length=100,
        choices=[
            ("full_received", "Full Received"),
            ("not_received", "Not Received"),
            ("partially_received", "Partially Received"),
        ],
        default="not_received",
    )

    bill_status = models.CharField(
        max_length=20,
        choices=[
            ("not_billed", "Not Billed"),
            ("partially_billed", "Partially Billed"),
            ("fully_billed", "Fully Billed"),
        ],
        default="not_billed",
    )

    issue_date = models.DateField(default=timezone.now)

    expected_delivery_date = models.DateField(blank=True, null=True)
    expected_delivery_time = models.TimeField(blank=True, null=True)

    supporting_document_file = models.FileField(
        upload_to="vendors/supporting_documents/", blank=True, null=True
    )

    branch = models.ForeignKey(
        "institution.Branch",
        on_delete=models.CASCADE,
        related_name="vendor_purchase_orders",
        blank=True,
        null=True,
    )

    currency = models.ForeignKey(
        "system.SystemCurrency",
        on_delete=models.CASCADE,
        null=True,
        blank=True,
        related_name="vendor_purchase_orders",
    )

    search_fields = [
        "vendor__vendor_name",
        "vendor__email",
        "status",
        "currency__code",
    ]

    ordering_fields = [
        "reference_code",
        "branch__branch_name",
        "vendor__vendor_name",
        "issue_date",
        "status",
        "bill_status",
        "goods_received_note_status",
    ]

    filterset_fields = [
        "vendor__base_uuid",
        "status",
        "bill_status",
        "goods_received_note_status",
    ]

    class Meta:
        ordering = ["-created_at"]
        verbose_name = "Vendor Purchase Order"
        verbose_name_plural = "Vendor Purchase Orders"

    def get_vendor_purchase_order_vendor(self):
        return self.vendor if self.vendor is not None else None

    def mark_as_delivered(self):
        if self.status != "approved":
            raise ValidationError(
                "Can't update quotation status to delivered unless it is currently approved."
            )
        self.status = "delivered"
        self.save()

    def update_status_from_vendor_bill(self):
        if self.status == "approved":
            self.mark_as_delivered()
        else:
            raise ValidationError(
                "Purchase Order cannot be marked delivered unless approved."
            )

    def __str__(self):
        return f"Purchase Order {self.reference_code} for {self.vendor.vendor_name}"

    def get_institution(self):
        return self.vendor.get_institution()

    @classmethod
    def get_institution_filter_field(cls):
        return "vendor__institution"

    def finish_workflow(self, approval: Approval):
        if approval.status == "completed":
            if approval.action.name == "create":
                self.approval_status = "active"
                self.is_active = True
                self.status = "approved"

                institution = self.get_institution()
                if institution.inventory_increment_timing == "ON_GRN":
                    from vendors.services import AutoGRNCreationService

                    AutoGRNCreationService.start(
                        source=self,
                        inventory_increment_timing=(
                            institution.inventory_increment_timing
                        ),
                        source_approval=approval,
                    )

            elif approval.action.name == "update":
                self.approval_status = "active"
                self.is_active = True
                self.deleted_at = None
                self.original_data = None
                self.status = "approved"

            elif approval.action.name == "delete":
                self.is_active = False
                self.deleted_at = timezone.now()
                self.status = "canceled"

        elif approval.status == "rejected":
            if approval.action.name == "create":
                self.is_active = False
                self.deleted_at = timezone.now()

            elif approval.action.name in ["update", "delete"]:
                self.is_active = False
                self.deleted_at = None

        self.save()

    def save(self, *args, **kwargs):
        self.full_clean()

        super().save(*args, **kwargs)

    def determine_rate_currency_used(self):
        from system.services import FxRateService

        institution = self.get_institution()

        document_currency = (
            self.currency
            or (
                self.vendor.currency
                if self.vendor and self.vendor.currency_id
                else None
            )
            or institution.currency
        )
        rate = FxRateService.resolve_base_rate(
            institution=institution,
            currency=document_currency,
            source=(
                self
                if self.currency_id
                else (self.vendor if self.vendor and self.vendor.currency_id else self)
            ),
        )
        return document_currency, rate

    def get_currency(self):
        target_currency, _ = self.determine_rate_currency_used()
        return target_currency, False if target_currency else True

    def send_vendor_purchase_order_email(self):
        if self.get_vendor_purchase_order_vendor() is None:
            return

        vendor = self.get_vendor_purchase_order_vendor()

        if vendor.email is None:
            return

        institution = self.get_institution()

        total_amount = self.get_total_amount()

        context = {
            "reference_code": self.reference_code,
            "issue_date": self.created_at.strftime("%B %d, %Y"),
            "institution_name": institution.institution_name,
            "institution_email": institution.institution_email,
            "salutation_line": f"Dear {vendor.get_gender_and_name()}",
            "vendor_name": vendor.vendor_name,
            "vendor_email": vendor.email,
            "line_items": self.get_line_items(),
            "total_amount": f"{total_amount:.2f}",
        }

        EmailClient.send(
            subject=f"Purchase Order {self.reference_code} from {institution.institution_name}",
            recipients=[vendor.email],
            template_html="emails/vendor_purchase_order_email.html",
            context=context,
        )

    def get_line_items(self):
        items = []

        for item in self.line_items.filter(item_type="inventory"):
            items.append(
                {
                    "type": "inventory",
                    "name": item.inventory_item.item_name,
                    "quantity": item.quantity,
                    "unit_price": f"{item.unit_price:.2f}",
                    "line_total": f"{item.line_total:.2f}",
                    "unit_of_measure": (
                        item.unit_of_measure.unit_of_measure.unit_name
                        if item.unit_of_measure
                        else None
                    ),
                }
            )

        for item in self.line_items.filter(item_type="other"):
            items.append(
                {
                    "type": "other",
                    "name": item.line_item_name,
                    "quantity": item.quantity,
                    "unit_price": f"{item.unit_price:.2f}",
                    "line_total": f"{item.line_total:.2f}",
                    "unit_of_measure": item.other_unit_of_measure,
                }
            )

        for item in self.line_items.filter(item_type="fixed_asset"):
            items.append(
                {
                    "type": "fixed_asset",
                    "name": item.line_item_name,
                    "quantity": item.quantity,
                    "unit_price": f"{item.unit_price:.2f}",
                    "line_total": f"{item.line_total:.2f}",
                    "asset_category": (
                        item.asset_category.category_name
                        if item.asset_category
                        else None
                    ),
                    "unit_of_measure": item.other_unit_of_measure,
                }
            )

        return items

    ZERO = Decimal("0.00")

    def get_net_total(self):
        return sum(
            (
                item.line_total
                - sum(
                    (
                        breakdown.tax_amount
                        for breakdown in item.get_tax_breakdowns()
                        if (
                            breakdown.is_inclusive
                            if breakdown.is_inclusive is not None
                            else breakdown.tax.is_inclusive
                        )
                    ),
                    self.ZERO,
                )
                for item in self.line_items.all()
            ),
            self.ZERO,
        )

    def get_tax_total(self):
        return sum(
            (
                breakdown.tax_amount
                for item in self.line_items.all()
                for breakdown in item.get_tax_breakdowns()
            ),
            self.ZERO,
        )

    def get_total_amount(self):
        return sum(
            (
                item.line_total
                + sum(
                    (
                        breakdown.tax_amount
                        for breakdown in item.get_tax_breakdowns()
                        if not (
                            breakdown.is_inclusive
                            if breakdown.is_inclusive is not None
                            else breakdown.tax.is_inclusive
                        )
                    ),
                    self.ZERO,
                )
                for item in self.line_items.all()
            ),
            self.ZERO,
        )


class VendorPurchaseOrderLineItem(SoftDeletableTimeStampedModel):
    search_fields = [
        "inventory_item__item_name",
        "inventory_item__item_code",
        "line_item_name",
        "asset_category__category_name",
    ]

    ordering_fields = [
        "created_at",
        "quantity",
        "unit_price",
        "line_total",
        "item_type",
    ]

    ITEM_TYPE_CHOICES = [
        ("inventory", "Inventory Item"),
        ("fixed_asset", "Fixed Asset"),
        ("other", "Other Item"),
    ]
    item_type = models.CharField(
        max_length=20,
        choices=ITEM_TYPE_CHOICES,
    )
    purchase_order = models.ForeignKey(
        "vendors.VendorPurchaseOrder",
        on_delete=models.CASCADE,
        related_name="line_items",
    )
    inventory_item = models.ForeignKey(
        "items.InventoryItem",
        on_delete=models.CASCADE,
        related_name="purchase_order_line_items",
        null=True,
        blank=True,
    )
    unit_of_measure = models.ForeignKey(
        "items.InventoryItemUnitOfMeasure",
        on_delete=models.CASCADE,
        null=True,
        blank=True,
    )
    asset_category = models.ForeignKey(
        "fixed_assets.AssetCategory",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
    )
    line_item_name = models.CharField(max_length=255, blank=True, null=True)
    other_unit_of_measure = models.CharField(max_length=100, blank=True, null=True)
    quantity = models.PositiveIntegerField(default=1)
    unit_price = models.DecimalField(max_digits=50, decimal_places=20, default=0.00)
    line_total = models.DecimalField(max_digits=50, decimal_places=20, default=0.00)

    qty_ordered = models.PositiveIntegerField(default=0)
    qty_received = models.PositiveIntegerField(default=0)
    qty_to_receive = models.PositiveIntegerField(default=0)

    assets_created = models.BooleanField(default=False)

    tax_breakdowns = GenericRelation(TaxApplicationBreakDown)

    def __str__(self):
        name = (
            self.inventory_item.item_name
            if self.inventory_item
            else self.line_item_name if self.line_item_name else "Unnamed Item"
        )
        return f"{name} x {self.quantity} @ {self.unit_price}"

    def clean(self):
        super().clean()

        if self.item_type == "fixed_asset":
            if not self.asset_category:
                raise ValidationError(
                    {
                        "asset_category": "Asset category is required for fixed asset line items."
                    }
                )

        if self.item_type != "fixed_asset" and self.asset_category:
            raise ValidationError(
                {
                    "asset_category": "Asset category should only be set for fixed asset items."
                }
            )

    def save(self, *args, **kwargs):
        self.full_clean()
        super().save(*args, **kwargs)

    def get_tax_breakdowns(self):
        return self.tax_breakdowns.all()


class VendorBill(ReportableModelMixin, BaseApprovableModel):
    reference_prefix = "VB"

    BILL_STATUS_CHOICES = [
        ("draft", "Draft"),
        ("approved", "Approved"),
        ("cancelled", "Cancelled"),
    ]

    PAYMENT_STATUS_CHOICES = [
        ("unpaid", "Unpaid"),
        ("paid", "Paid"),
        ("partially_paid", "Partially Paid"),
    ]

    institution = models.ForeignKey(
        "institution.Institution",
        on_delete=models.CASCADE,
        related_name="vendor_bills",
        blank=True,
        null=True,
    )

    branch = models.ForeignKey(
        "institution.Branch",
        on_delete=models.CASCADE,
        related_name="vendor_bills",
        blank=True,
        null=True,
    )

    purchase_order = models.ForeignKey(
        "vendors.VendorPurchaseOrder",
        on_delete=models.CASCADE,
        related_name="bills",
        null=True,
        blank=True,
    )

    vendor = models.ForeignKey(
        Vendor,
        on_delete=models.CASCADE,
        null=True,
        blank=True,
    )

    received_date = models.DateField(default=timezone.now)

    due_date = models.DateField(blank=True, null=True)

    payment_terms = models.ForeignKey(
        "customers.PaymentTerm",
        on_delete=models.CASCADE,
        null=True,
        blank=True,
    )

    total_amount = models.DecimalField(max_digits=50, decimal_places=20, default=0.00)

    balance_due = models.DecimalField(max_digits=50, decimal_places=20, default=0.00)

    status = models.CharField(
        max_length=100,
        choices=BILL_STATUS_CHOICES,
        default="draft",
    )

    goods_received_note_status = models.CharField(
        max_length=100,
        choices=[
            ("full_received", "Full Received"),
            ("not_received", "Not Received"),
            ("partially_received", "Partially Received"),
        ],
        default="not_received",
    )

    payment_status = models.CharField(
        max_length=100,
        choices=PAYMENT_STATUS_CHOICES,
        default="unpaid",
    )

    are_initial_journal_entries_made = models.BooleanField(default=False)

    total_net_amount = models.DecimalField(
        max_digits=50,
        decimal_places=20,
        default=0.00,
        help_text="Total amount before taxes",
    )

    total_tax_amount = models.DecimalField(
        max_digits=50,
        decimal_places=20,
        default=0.00,
        help_text="Total tax amount applied to this bill",
    )

    debit_note_total = models.DecimalField(
        max_digits=50,
        decimal_places=20,
        default=Decimal("0.00"),
        help_text="Sum of all approved DEBIT note amounts against this bill.",
    )

    adjusted_total = models.DecimalField(
        max_digits=50,
        decimal_places=20,
        default=Decimal("0.00"),
        help_text="Effective bill total after debit note adjustments.",
    )

    currency = models.ForeignKey(
        "system.SystemCurrency",
        on_delete=models.PROTECT,
        null=True,
        blank=True,
        related_name="vendor_bills",
    )

    search_fields = [
        "purchase_order__vendor__vendor_name",
        "purchase_order__vendor__email",
        "purchase_order__vendor__phone_number",
        "purchase_order__vendor__vendor_type",
        "vendor__vendor_name",
        "vendor__email",
        "vendor__phone_number",
        "vendor__vendor_type",
        "payment_status",
        "status",
    ]

    ordering_fields = [
        "reference_code",
        "branch__branch_name",
        "due_date",
        "received_date",
        "total_amount",
        "balance_due",
        "status",
        "payment_status",
        "goods_received_note_status",
    ]

    filterset_fields = [
        *BaseApprovableModel.filterset_fields,
        "vendor__base_uuid",
        "status",
        "payment_status",
        "payment_terms__base_uuid",
        "goods_received_note_status",
    ]

    class Meta:
        ordering = ["-created_at"]
        verbose_name = "Vendor Bill"
        verbose_name_plural = "Vendor Bills"

    def __str__(self):
        return f"Bill {self.reference_code} for {self.vendor.vendor_name if self.vendor else self.purchase_order.vendor.vendor_name if self.purchase_order else 'Unknown Vendor'}"

    @classmethod
    def get_foreign_key_display_fields(cls):
        return {
            "purchase_order": "reference_code",
            "vendor": "vendor_name",
            "branch": "branch_name",
            "payment_terms": "term_name",
        }

    @classmethod
    def get_filter_serializer_class(cls):
        from vendors.filters import VendorBillFilterSerializer

        return VendorBillFilterSerializer

    def clean(self):
        if self.purchase_order and self.vendor:
            raise validation_error(
                "A vendor bill cannot have both a purchase order and a vendor. Choose one."
            )

        if not self.purchase_order and not self.vendor:
            raise validation_error(
                "A vendor bill must have either a purchase order or a vendor."
            )

    def get_institution(self):
        institution = None
        if self.purchase_order is not None:
            institution = self.purchase_order.get_institution()

        if institution is None:
            institution = self.vendor.get_institution()

        return institution

    def get_bill_vendor(self):
        return (
            self.vendor
            if self.vendor
            else self.purchase_order.vendor if self.purchase_order else None
        )

    def _get_payment_terms(self):
        return (
            self.payment_terms
            if self.payments is not None
            else (
                self.get_bill_vendor().payment_term
                if self.get_bill_vendor() is not None
                else None
            )
        )

    @transaction.atomic
    def finish_workflow(self, approval: Approval):
        if approval.status == "completed":
            if approval.action.name in ["create", "update"]:
                self.is_active = True

                if not self.are_initial_journal_entries_made:
                    self._process_financial_events()

                self.status = "approved"

                if approval.action.name == "create":
                    from vendors.services import AutoGRNCreationService

                    institution = self.get_institution()

                    AutoGRNCreationService.start(
                        source=self,
                        source_approval=approval,
                        inventory_increment_timing=(
                            institution.inventory_increment_timing
                        ),
                    )

            elif approval.action.name == "delete":
                self.is_active = False
                self.deleted_at = timezone.now()
        elif approval.status == "rejected":
            if approval.action.name == "create":
                self.is_active = False
                self.deleted_at = timezone.now()

            elif approval.action.name in ["update", "delete"]:
                self.is_active = False
                self.deleted_at = None

        self.save()

    def save(self, *args, **kwargs):
        self.full_clean()

        if not self.due_date:
            payment_terms = self._get_payment_terms()
            self.due_date = get_due_date_based_on_payment_terms(
                payment_terms, self.received_date
            )

        super().save(*args, **kwargs)

    def determine_rate_currency_used(self):
        institution = self.get_institution()
        source = self.purchase_order or self.vendor
        source_currency, _ = source.determine_rate_currency_used()
        document_currency = self.currency or source_currency or institution.currency

        from system.services import FxRateService

        rate = FxRateService.resolve_base_rate(
            institution=institution,
            currency=document_currency,
            source=self if self.currency_id else source,
        )
        return document_currency, rate

    @transaction.atomic
    def _process_financial_events(self):
        if self.are_initial_journal_entries_made:
            return None

        from accounts.utils import get_or_create_default_account
        from transactions.services import JournalLine, JournalPostingService

        institution = self.get_institution()
        fiscal_year = get_fiscal_year(institution, self.received_date)
        bill_vendor = self.get_bill_vendor()
        document_currency, _ = self.determine_rate_currency_used()
        account_currency = (
            None if document_currency == institution.currency else document_currency
        )

        accounts_payable = (
            bill_vendor.default_account_payable
            or get_or_create_default_account(
                institution,
                "payable_account",
                account_currency,
            )
        )

        journal_lines = [
            JournalLine(
                account=accounts_payable,
                entry_type="credit",
                transaction_amount=self.total_amount,
                transaction_currency=document_currency,
                description=f"Accounts payable for {bill_vendor.vendor_name}",
            )
        ]

        inventory_total = Decimal("0.00")
        expense_total = Decimal("0.00")

        for item in self.line_items.undeleted():
            base_amount = Decimal(str(item.line_total or 0)).quantize(
                Decimal("0.01"),
                rounding=ROUND_HALF_UP,
            )
            breakdowns = list(item.get_tax_breakdowns())
            inclusive_tax = sum(
                (
                    breakdown.tax_amount
                    for breakdown in breakdowns
                    if breakdown.net_amount < base_amount
                ),
                Decimal("0"),
            )
            line_net = base_amount - inclusive_tax

            if item.item_type == "inventory":
                if item.inventory_item.item_type == "SERVICES":
                    service = item.inventory_item
                    if line_net != Decimal("0.00"):
                        if line_net < 0:
                            service_account = (
                                service.revenue_account
                                or service.item_category.revenue_account
                                or get_or_create_default_account(
                                    institution, "income_account", None
                                )
                            )
                        else:
                            service_account = (
                                service.expense_account
                                or service.item_category.expense_account
                                or get_or_create_default_account(
                                    institution, "sgna_account", None
                                )
                            )
                        journal_lines.append(
                            JournalLine(
                                account=service_account,
                                entry_type="credit" if line_net < 0 else "debit",
                                transaction_amount=abs(line_net),
                                transaction_currency=document_currency,
                                description=(
                                    f"Service {service.item_name} "
                                    f"on bill {self.reference_code}"
                                ),
                            )
                        )
                else:
                    inventory_total += line_net

            if item.item_type == "other":
                expense_total += line_net

            if item.item_type == "fixed_asset":
                if line_net > Decimal("0.00"):
                    fixed_asset_account = (
                        item.asset_category.fixed_asset_account
                        or get_or_create_default_account(
                            institution, "fixed_asset_account", None
                        )
                    )
                    journal_lines.append(
                        JournalLine(
                            account=fixed_asset_account,
                            entry_type="debit",
                            transaction_amount=line_net,
                            transaction_currency=document_currency,
                            description=(
                                f"Fixed asset acquisition via bill "
                                f"{self.reference_code}"
                            ),
                        )
                    )

        if inventory_total > Decimal("0.00"):
            stock_interim_account = get_or_create_default_account(
                institution,
                "stock_interim_account",
                None,
            )
            journal_lines.append(
                JournalLine(
                    account=stock_interim_account,
                    entry_type="debit",
                    transaction_amount=inventory_total,
                    transaction_currency=document_currency,
                    description=(
                        f"Inventory goods recognized through Stock Interim "
                        f"for bill {self.reference_code}"
                    ),
                )
            )

        if expense_total > Decimal("0.00"):
            sgna = get_or_create_default_account(institution, "sgna_account", None)
            journal_lines.append(
                JournalLine(
                    account=sgna,
                    entry_type="debit",
                    transaction_amount=expense_total,
                    transaction_currency=document_currency,
                    description=f"Expenses for {bill_vendor.vendor_name}",
                )
            )

        for expense in self.order_expenses.filter(deleted_at__isnull=True):
            account = (
                expense.account_to_record_expense
                or get_or_create_default_account(institution, "sgna_account", None)
            )

            base_amount = Decimal(str(expense.amount or 0)).quantize(
                Decimal("0.01"),
                rounding=ROUND_HALF_UP,
            )
            breakdowns = list(expense.get_tax_breakdowns())
            inclusive_tax = sum(
                (
                    breakdown.tax_amount
                    for breakdown in breakdowns
                    if breakdown.net_amount < base_amount
                ),
                Decimal("0"),
            )
            net_amount = base_amount - inclusive_tax

            if net_amount > Decimal("0.00"):
                journal_lines.append(
                    JournalLine(
                        account=account,
                        entry_type="debit",
                        transaction_amount=net_amount,
                        transaction_currency=document_currency,
                        description=expense.expense_name,
                    )
                )

        for tb in self.get_all_tax_breakdowns():
            tax_account = tb.tax.tax_account or get_or_create_default_account(
                institution, "vat_controlled_account", None
            )

            if tb.tax_amount > Decimal("0.00"):
                journal_lines.append(
                    JournalLine(
                        account=tax_account,
                        entry_type="debit",
                        transaction_amount=tb.tax_amount,
                        transaction_currency=document_currency,
                        description=(
                            f"{tb.tax.tax_name} input tax, "
                            f"for {bill_vendor.vendor_name}"
                        ),
                    )
                )

        debit_total = sum(
            (
                line.transaction_amount
                for line in journal_lines
                if line.entry_type == "debit"
            ),
            Decimal("0"),
        )
        credit_total = sum(
            (
                line.transaction_amount
                for line in journal_lines
                if line.entry_type == "credit"
            ),
            Decimal("0"),
        )
        rounding_difference = credit_total - debit_total

        if rounding_difference:
            if abs(rounding_difference) > Decimal("0.05"):
                raise validation_error(
                    "Vendor bill journal components do not match the bill total."
                )

            debit_index = next(
                (
                    index
                    for index in range(len(journal_lines) - 1, -1, -1)
                    if journal_lines[index].entry_type == "debit"
                ),
                None,
            )
            if debit_index is None:
                raise validation_error(
                    "Vendor bill requires at least one debit journal line."
                )

            debit_line = journal_lines[debit_index]
            journal_lines[debit_index] = replace(
                debit_line,
                transaction_amount=(
                    debit_line.transaction_amount + rounding_difference
                ),
            )

        transaction, _ = JournalPostingService.post(
            fiscal_year=fiscal_year,
            title=f"Vendor Bill {self.reference_code}",
            description=f"Bill from {bill_vendor.vendor_name}",
            transaction_date=self.received_date,
            lines=journal_lines,
            branch=self.branch,
            content_type=ContentType.objects.get_for_model(
                self.__class__,
                for_concrete_model=False,
            ),
            object_id=self.id,
            source=self,
        )

        VendorBill.objects.filter(pk=self.pk).update(
            are_initial_journal_entries_made=True
        )
        self.are_initial_journal_entries_made = True

        if bill_vendor is not None:
            bill_vendor.__class__.objects.filter(pk=bill_vendor.pk).update(
                outstanding_payables=models.F("outstanding_payables")
                + self.total_amount
            )
            bill_vendor.refresh_from_db(fields=["outstanding_payables"])

            VendorOutstandingBalanceAdjustment.objects.create(
                vendor=bill_vendor,
                balance_adjusted="OUTSTANDING_PAYABLE_BALANCE",
                amount=self.total_amount,
                amount_before_adjustment=bill_vendor.outstanding_payables
                - self.total_amount,
                amount_after_adjustment=bill_vendor.outstanding_payables,
                reason=f"Bill {self.reference_code} created",
            )

        fixed_asset_items = self.line_items.filter(
            item_type="fixed_asset", deleted_at__isnull=True
        )
        if fixed_asset_items.exists():
            self._record_fixed_asset(fixed_asset_items)

        return transaction

    @transaction.atomic
    def _record_fixed_asset(self, fixed_asset_items):
        from fixed_assets.serializers import FixedAssetSerializer

        request = getattr(self, "_request_context", None)

        for item in fixed_asset_items:
            if item.item_type != "fixed_asset":
                raise ValidationError("Item type must be a fixed asset")

            unit_price = item.unit_price

            for _ in range(item.quantity):
                asset_data = {
                    "institution": self.get_institution().id,
                    "category": (
                        str(item.asset_category.base_uuid)
                        if item.asset_category
                        else None
                    ),
                    "asset_name": (
                        item.line_item_name or item.asset_category.category_name
                        if item.asset_category
                        else "UnNamed"
                    ),
                    "unit_of_measure": item.other_asset_unit_of_measure or None,
                    "purchase_price": unit_price,
                    "current_value": unit_price,
                    "purchase_date": (
                        self.created_at.date() if hasattr(self, "created_at") else None
                    ),
                    "asset_addition_type": "VIA_BILL",
                }
                serializer = FixedAssetSerializer(
                    data=asset_data, context={"request": request}
                )
                serializer.is_valid(raise_exception=True)
                fixed_asset = serializer.save()
                fixed_asset.confirm_create()

    def recompute_note_totals(self):
        from customers.models import CreditDebitNote

        from django.db.models import Sum

        approved_notes = CreditDebitNote.objects.filter(
            bill=self,
            falls_under="PURCHASE",
            deleted_at__isnull=True,
        )

        debit_total = approved_notes.filter(type="DEBIT").aggregate(t=Sum("amount"))[
            "t"
        ] or Decimal("0.00")

        adjusted = (self.total_amount - debit_total).quantize(Decimal("0.01"))

        adjusted = max(adjusted, Decimal("0.00"))

        total_paid = self._total_confirmed_payments()
        new_amount_due = max(adjusted - total_paid, Decimal("0.00"))

        VendorBill.objects.filter(pk=self.pk).update(
            debit_note_total=debit_total,
            adjusted_total=adjusted,
            balance_due=new_amount_due,
        )

        self.refresh_from_db(
            fields=[
                "debit_note_total",
                "adjusted_total",
                "balance_due",
            ]
        )
        self._sync_payment_status()

    def _total_confirmed_payments(self) -> Decimal:

        return VendorPayment.objects.filter(
            bill=self,
            payment_status="PAID",
            deleted_at__isnull=True,
        ).aggregate(t=Sum("amount"))["t"] or Decimal("0.00")

    def _sync_payment_status(self):
        self.refresh_from_db(fields=["balance_due", "adjusted_total"])
        if self.adjusted_total == Decimal("0.00") or self.balance_due == Decimal(
            "0.00"
        ):
            new_status = "paid"
        elif self.balance_due < self.adjusted_total:
            new_status = "partially_paid"
        else:
            new_status = "unpaid"
        VendorBill.objects.filter(pk=self.pk).update(payment_status=new_status)
        self.payment_status = new_status

    def send_vendor_bill_email(self):
        institution = self.get_institution()
        vendor = self.get_bill_vendor()

        if not institution or not institution.institution_email:
            return

        subject = (
            f"Vendor Bill #{self.reference_code} from {institution.institution_name}"
        )

        line_items = []
        for item in self.line_items.all():
            if item.item_type == "inventory" and item.inventory_item:
                name = item.inventory_item.item_name
                uom = (
                    item.unit_of_measure.unit_of_measure.unit_name
                    if item.unit_of_measure
                    else None
                )
            elif item.item_type == "fixed_asset":
                name = item.line_item_name or "Fixed Asset"
                uom = None
            else:
                name = item.line_item_name or "Other Item"
                uom = item.other_asset_unit_of_measure

            line_items.append(
                {
                    "type": item.item_type,
                    "name": name,
                    "quantity": item.quantity,
                    "unit_price": f"{item.unit_price:.2f}",
                    "line_total": f"{item.line_total:.2f}",
                    "unit_of_measure": uom,
                    "asset_category": getattr(
                        item.asset_category, "category_name", None
                    ),
                }
            )

        context = {
            "reference_code": self.reference_code,
            "vendor_name": vendor.vendor_name if vendor else "Unknown Vendor",
            "vendor_email": vendor.email if vendor else None,
            "institution_name": institution.institution_name,
            "institution_email": institution.institution_email,
            "issue_date": self.received_date.strftime("%B %d, %Y"),
            "due_date": self.due_date.strftime("%B %d, %Y") if self.due_date else None,
            "salutation_line": f"Dear {institution.institution_name}",
            "line_items": line_items,
            "total_amount": f"{self.total_amount:.2f}",
            "payment_status": self.payment_status,
        }

        recipients = [institution.institution_email]

        EmailClient.send(
            subject=subject,
            recipients=recipients,
            template_html="emails/vendor_bill_email.html",
            context=context,
        )

    @transaction.atomic
    def apply_taxation(self):
        breakdowns = []

        line_item_ct = ContentType.objects.get_for_model(VendorBillLineItem)
        expense_item_ct = ContentType.objects.get_for_model(VendorBillOtherExpenses)

        for expense in self.order_expenses.all():
            tax = expense.tax

            if not tax or not tax.is_active:
                continue

            line_total = expense.amount

            if tax.is_inclusive:
                _, _, tax_amount = tax.calculate_tax_amount(line_total)
                net_amount = (line_total - tax_amount).quantize(Decimal("0.01"))
                gross_amount = line_total
            else:
                _, _, tax_amount = tax.calculate_tax_amount(line_total)
                net_amount = line_total
                gross_amount = (net_amount + tax_amount).quantize(Decimal("0.01"))

            breakdown = TaxApplicationBreakDown.objects.update_or_create(
                tax=tax,
                content_type=expense_item_ct,
                object_id=expense.id,
                defaults={
                    "gross_amount": gross_amount,
                    "net_amount": net_amount,
                    "tax_amount": tax_amount,
                },
            )
            breakdowns.append(breakdown)

        for item in self.line_items.all():
            inventory_item = item.inventory_item
            tax = inventory_item.purchase_tax if inventory_item else None

            if not tax or not tax.is_active:
                continue

            line_total = item.line_total or (item.quantity * item.unit_price).quantize(
                Decimal("0.01")
            )

            if tax.is_inclusive:
                _, _, tax_amount = tax.calculate_tax_amount(line_total)
                net_amount = (line_total - tax_amount).quantize(Decimal("0.01"))
                gross_amount = line_total
            else:
                _, _, tax_amount = tax.calculate_tax_amount(line_total)
                net_amount = line_total
                gross_amount = (net_amount + tax_amount).quantize(Decimal("0.01"))

            breakdown = TaxApplicationBreakDown.objects.update_or_create(
                tax=tax,
                content_type=line_item_ct,
                object_id=item.id,
                defaults={
                    "gross_amount": gross_amount,
                    "net_amount": net_amount,
                    "tax_amount": tax_amount,
                },
            )

            breakdowns.append(breakdown)

        return breakdowns

    def get_all_tax_breakdowns(self):
        from django.contrib.contenttypes.models import ContentType
        from django.db.models import Q

        line_item_ct = ContentType.objects.get_for_model(VendorBillLineItem)
        expense_ct = ContentType.objects.get_for_model(VendorBillOtherExpenses)
        line_item_ids = self.line_items.values_list("id", flat=True)
        expense_ids = self.order_expenses.values_list("id", flat=True)

        return TaxApplicationBreakDown.objects.filter(
            Q(content_type=line_item_ct, object_id__in=line_item_ids)
            | Q(content_type=expense_ct, object_id__in=expense_ids)
        )

    def compute_totals(self):
        for item in self.line_items.all():
            if item.line_total is None:
                item.line_total = (item.quantity * item.unit_price).quantize(
                    Decimal("0.01")
                )
                item.save(update_fields=["line_total"])

        total_net = Decimal("0.00")
        total_tax = Decimal("0.00")
        total_gross = Decimal("0.00")

        taxable_objects = [
            *(
                (item, item.line_total or Decimal("0.00"))
                for item in self.line_items.all()
            ),
            *(
                (expense, expense.amount or Decimal("0.00"))
                for expense in self.order_expenses.all()
            ),
        ]

        for taxable_object, base_amount in taxable_objects:
            base_amount = Decimal(str(base_amount)).quantize(Decimal("0.01"))
            breakdowns = taxable_object.get_tax_breakdowns()

            if not breakdowns.exists():
                total_net += base_amount
                total_gross += base_amount
                continue

            inclusive_tax = Decimal("0.00")
            exclusive_tax = Decimal("0.00")

            for breakdown in breakdowns:
                tax_amount = breakdown.tax_amount or Decimal("0.00")
                total_tax += tax_amount

                if breakdown.net_amount < base_amount:
                    inclusive_tax += tax_amount
                else:
                    exclusive_tax += tax_amount

            total_net += base_amount - inclusive_tax
            total_gross += base_amount + exclusive_tax

        self.total_net_amount = total_net.quantize(Decimal("0.01"))
        self.total_tax_amount = total_tax.quantize(Decimal("0.01"))
        self.total_amount = total_gross.quantize(Decimal("0.01"))
        self.adjusted_total = self.total_amount
        self.debit_note_total = Decimal("0.00")

        self.save(
            update_fields=[
                "total_net_amount",
                "total_tax_amount",
                "total_amount",
                "adjusted_total",
                "debit_note_total",
            ]
        )


class VendorBillLineItem(SoftDeletableTimeStampedModel):
    search_fields = [
        "inventory_item__item_name",
        "inventory_item__item_code",
        "line_item_name",
        "asset_category__category_name",
    ]

    ordering_fields = [
        "created_at",
        "quantity",
        "unit_price",
        "line_total",
        "item_type",
    ]

    ITEM_TYPE_CHOICES = [
        ("inventory", "Inventory Item"),
        ("fixed_asset", "Fixed Asset"),
        ("other", "Other Item"),
    ]

    item_type = models.CharField(
        max_length=20, choices=ITEM_TYPE_CHOICES, default="inventory"
    )

    bill = models.ForeignKey(
        "vendors.VendorBill", on_delete=models.CASCADE, related_name="line_items"
    )

    # Inventory-Specific Fields
    inventory_item = models.ForeignKey(
        "items.InventoryItem",
        on_delete=models.CASCADE,
        related_name="vendor_bill_line_items",
        null=True,
        blank=True,
    )

    unit_of_measure = models.ForeignKey(
        "items.InventoryItemUnitOfMeasure",
        on_delete=models.CASCADE,
        null=True,
        blank=True,
    )

    # Fixed-asset-specific fields
    asset_category = models.ForeignKey(
        "fixed_assets.AssetCategory",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
    )

    # other_asset_fields
    line_item_name = models.CharField(max_length=255, blank=True, null=True)
    other_asset_unit_of_measure = models.CharField(
        max_length=100, blank=True, null=True
    )

    # General Fields
    quantity = models.PositiveIntegerField(default=1)
    unit_price = models.DecimalField(max_digits=50, decimal_places=20, default=0.00)
    line_total = models.DecimalField(max_digits=50, decimal_places=20, default=0.00)

    quantity_ordered = models.PositiveIntegerField(
        default=0,
        help_text="Quantity ordered for this line item. Used to track GRN status based on received quantity vs ordered quantity.",
    )
    quantity_received = models.PositiveIntegerField(
        default=0,
        help_text="Quantity received for this line item. Used to track GRN status based on received quantity vs ordered quantity.",
    )
    quantity_pending = models.PositiveIntegerField(
        default=0,
        help_text="Quantity pending for this line item. Used to track GRN status based on pending quantity vs ordered quantity.",
    )

    tax_breakdowns = GenericRelation(TaxApplicationBreakDown)

    def __str__(self):
        name = (
            self.inventory_item.item_name
            if self.inventory_item
            else self.line_item_name if self.line_item_name else "Unnamed Item"
        )
        return f"{name} x {self.quantity} @ {self.unit_price}"

    def get_tax_breakdowns(self):
        return self.tax_breakdowns.all()


class VendorBillOtherExpenses(SoftDeletableTimeStampedModel):
    bill = models.ForeignKey(
        "VendorBill", on_delete=models.CASCADE, related_name="order_expenses"
    )
    expense_name = models.CharField(max_length=255)
    amount = models.DecimalField(max_digits=50, decimal_places=20, default=0.00)

    account_to_record_expense = models.ForeignKey(
        "accounts.Account",
        on_delete=models.CASCADE,
        related_name="vendor_bill_other_expenses",
        null=True,
        blank=True,
    )

    tax = models.ForeignKey(
        "taxation.Tax",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
    )

    tax_breakdowns = GenericRelation(TaxApplicationBreakDown)

    def __str__(self):
        return f"{self.expense_name} - {self.amount}"

    def get_institution(self):
        return self.bill.get_institution()

    def get_tax_breakdowns(self):
        return self.tax_breakdowns.all()


class VendorOutstandingBalanceAdjustment(BaseTimeStamp):
    BALANCE_ADJUSTED_CHOICES = [
        ("OUTSTANDING_PAYABLE_BALANCE", "Outstanding Payable Balance"),
        ("DEPOSIT_BALANCE", "Deposit Balance"),
    ]
    vendor = models.ForeignKey(
        Vendor, on_delete=models.CASCADE, related_name="outstanding_balance_adjustments"
    )
    balance_adjusted = models.CharField(
        max_length=50,
        choices=BALANCE_ADJUSTED_CHOICES,
        default="OUTSTANDING_PAYABLE_BALANCE",
    )
    adjustment_date = models.DateField(default=timezone.now)
    amount = models.DecimalField(max_digits=50, decimal_places=20)
    amount_before_adjustment = models.DecimalField(max_digits=50, decimal_places=20)
    amount_after_adjustment = models.DecimalField(max_digits=50, decimal_places=20)
    reason = models.CharField(max_length=255)

    content_type = models.ForeignKey(
        ContentType, on_delete=models.CASCADE, null=True, blank=True
    )
    object_id = models.PositiveIntegerField(null=True, blank=True)
    content_object = GenericForeignKey("content_type", "object_id")

    def save(self, *args, **kwargs):
        if self.reason:
            self.reason = format_currency_numbers_in_text(self.reason)

        super().save(*args, **kwargs)

    def __str__(self):
        return f"{self.vendor.vendor_name} - {self.amount} - {self.adjustment_date}"


class VendorPayment(ReportableModelMixin, BaseApprovableModel):
    reference_prefix = "V-PAY"

    PAYMENT_STATUS_CHOICES = [
        ("DRAFT", "Draft"),
        ("APPROVED", "Approved"),
        ("CANCELLED", "Cancelled"),
        ("AWAITING_PAYMENT", "Awaiting Payment"),
        ("PAID", "Paid"),
    ]

    institution = models.ForeignKey(
        "institution.Institution",
        on_delete=models.CASCADE,
        related_name="vendor_payments",
        blank=True,
        null=True,
    )

    currency = models.ForeignKey(
        "system.SystemCurrency",
        on_delete=models.PROTECT,
        blank=True,
        null=True,
        related_name="vendor_payment_documents",
    )

    branch = models.ForeignKey(
        "institution.Branch",
        on_delete=models.CASCADE,
        related_name="vendor_payments",
        null=True,
        blank=True,
    )

    vendor = models.ForeignKey(
        "vendors.Vendor",
        on_delete=models.SET_NULL,
        related_name="payments",
        null=True,
        blank=True,
    )

    bill = models.ForeignKey(
        "VendorBill",
        on_delete=models.SET_NULL,
        related_name="payments",
        null=True,
        blank=True,
        default=None,
    )

    cash_requisition = models.ForeignKey(
        "requisitions.Requisition",
        on_delete=models.SET_NULL,
        related_name="payments",
        null=True,
        blank=True,
    )

    amount = models.DecimalField(max_digits=50, decimal_places=20, default=0.00)

    payment_status = models.CharField(
        max_length=30, choices=PAYMENT_STATUS_CHOICES, default="DRAFT"
    )
    payment_date = models.DateField(default=timezone.now)

    content_type = models.ForeignKey(
        ContentType, on_delete=models.CASCADE, null=True, blank=True
    )
    object_id = models.PositiveIntegerField(null=True, blank=True)
    cash_account = GenericForeignKey("content_type", "object_id")

    are_initial_journal_entries_made = models.BooleanField(default=False)

    amount_reconciled = models.DecimalField(
        max_digits=50, decimal_places=20, default=Decimal("0.00")
    )
    remaining_balance = models.DecimalField(
        max_digits=50,
        decimal_places=20,
        default=Decimal("0.00"),
        help_text="Unallocated balance remaining on this prepayment. Only meaningful when bill=None.",
    )

    settlement_currency = models.ForeignKey(
        "system.SystemCurrency",
        on_delete=models.PROTECT,
        related_name="vendor_payment_settlements",
        null=True,
        blank=True,
    )

    settlement_amount = models.DecimalField(
        max_digits=50,
        decimal_places=20,
        default=Decimal("0.00"),
    )

    originating_payment = models.ForeignKey(
        "self",
        on_delete=models.CASCADE,
        related_name="generated_prepayments",
        null=True,
        blank=True,
    )

    search_fields = [
        "vendor__vendor_name",
        "vendor__email",
        "vendor__phone_number",
        "vendor__vendor_type",
        "bill__vendor__vendor_name",
        "bill__vendor__phone_number",
        "bill__vendor__vendor_type",
        "bill__vendor__email",
    ]

    ordering_fields = [
        "payment_date",
        "amount_reconciled",
        "remaining_balance",
        "amount",
    ]

    filterset_fields = [
        "bill_base_uuid",
        "vendor_base_uuid",
        "cash_requisition__base_uuid",
        "branch__base_uuid",
    ]

    def clean(self):
        if self.bill and self.vendor:
            raise validation_error(
                "A vendor payment cannot have both a bill and a vendor. Choose one."
            )

        if not self.bill and not self.vendor:
            raise validation_error(
                "A vendor payment must have either a bill or a vendor."
            )

        from bank_management.models import (
            BankAccount,
            MobileMoneyAccount,
            DigitalWalletAccount,
            CashAtHandAccount,
        )

        super().clean()

        allowed_models = [
            BankAccount,
            MobileMoneyAccount,
            DigitalWalletAccount,
            CashAtHandAccount,
        ]

        allowed_content_types = ContentType.objects.get_for_models(
            *allowed_models
        ).values()

        if self.content_type and self.content_type not in allowed_content_types:
            raise ValidationError(
                f"Vendor Payments can only be linked to a cash account. Must be one of: {', '.join([model.__name__ for model in allowed_models])}"
            )

    def get_payment_vendor(self):
        return (
            self.vendor
            if self.vendor
            else self.bill.get_bill_vendor() if self.bill else None
        )

    def __str__(self):
        kind = (
            f"Prepayment {self.reference_code}"
            if not self.bill
            else f"Payment {self.reference_code} for {self.bill.reference_code}"
        )

        vendor = self.get_vendor()

        return (
            f'{kind} – {vendor.vendor_name if vendor else "No Vendor"} – {self.amount}'
        )

    def get_vendor(self):
        return (
            self.vendor
            if self.vendor
            else self.bill.get_bill_vendor() if self.bill else None
        )

    class Meta:
        ordering = ["-created_at"]
        verbose_name = "Vendor Payment"
        verbose_name_plural = "Vendor Payments"

    def get_institution(self):
        if self.institution_id:
            return self.institution

        if self.branch:
            institution = self.branch.get_institution()

            if institution is not None:
                return institution

        if self.vendor:
            return self.vendor.get_institution()

        if self.bill:
            return self.bill.get_institution()

        if self.cash_requisition:
            return self.cash_requisition.get_institution()

        return None

    @classmethod
    def get_institution_filter_field(cls):
        return "institution"

    @property
    def is_prepayment(self):
        return self.bill is None

    @property
    def is_bill_payment(self):
        return self.bill is not None

    @property
    def is_standalone_prepayment(self):
        return (
            self.bill_id is None
            and self.vendor_id is not None
            and self.originating_payment_id is None
        )

    @property
    def is_generated_overpayment(self):
        return (
            self.bill_id is None
            and self.vendor_id is not None
            and self.originating_payment_id is not None
        )

    @transaction.atomic
    def finish_workflow(self, approval: Approval):
        if approval.status == "completed":
            if approval.action.name in ["create", "update"]:
                self.is_active = True

                if self.cash_requisition_id:
                    self.payment_status = (
                        "PAID"
                        if self.cash_requisition.payment_status == "fully_paid"
                        else "AWAITING_PAYMENT"
                    )
                    self.save()
                    return

                institution = self.get_institution()

                if (
                    institution
                    and institution.should_vendor_payments_go_through_requisitions
                ):
                    self.payment_status = "APPROVED"
                    self.save()

                    from .services import VendorPaymentService

                    VendorPaymentService.create_requisition(
                        self, source_approval=approval
                    )
                else:
                    from .services import VendorPaymentService

                    self.payment_status = "PAID"
                    self.save()
                    VendorPaymentService.process_financial_events(self)

                return

            elif approval.action.name == "delete":
                self.is_active = False
                self.deleted_at = timezone.now()
        elif approval.status == "rejected":
            if approval.action.name == "create":
                self.is_active = False
                self.deleted_at = timezone.now()
            elif approval.action.name in ["update", "delete"]:
                self.is_active = False
                self.deleted_at = None

        self.save()

    def _resolve_cash_account_coa(self):
        from bank_management.models import CashAccount
        from accounts.utils import get_or_create_default_account

        institution = self.get_institution()

        if not institution:
            raise ValidationError("Cannot determine institution for this payment.")

        account = self.cash_account

        if not isinstance(account, CashAccount):
            raise ValidationError("Linked cash account must be a valid CashAccount.")

        if account.institution != institution:
            raise ValidationError(
                "Cash account must belong to the same institution as the payment."
            )

        coa = account.get_chart_of_account_reference()

        return (
            coa if coa else get_or_create_default_account(institution, "cash_account")
        )

    def determine_rate_currency_used(self):
        from system.services import FxRateService

        institution = self.get_institution()
        if institution is None:
            raise ValidationError("Cannot determine institution for this payment.")

        payment_currency = self.currency or institution.currency
        rate = FxRateService.resolve_base_rate(
            institution=institution,
            currency=payment_currency,
            source=self,
        )
        return payment_currency, rate

    def determine_settlement_rate_currency_used(self):
        from system.services import FxRateService

        institution = self.get_institution()
        if institution is None:
            raise ValidationError("Cannot determine institution for this payment.")

        settlement_currency = self.settlement_currency

        if settlement_currency is None and self.bill_id:
            settlement_currency = self.bill.determine_rate_currency_used()[0]

        if settlement_currency is None:
            vendor = self.get_vendor()
            settlement_currency = (
                vendor.currency
                if vendor and vendor.currency_id
                else institution.currency
            )

        rate = FxRateService.resolve_base_rate(
            institution=institution,
            currency=settlement_currency,
            source=self,
        )
        return settlement_currency, rate

    def save(self, *args, **kwargs):
        is_new = self._state.adding

        if is_new and self.is_prepayment:
            self.remaining_balance = (
                self.settlement_amount
                if self.settlement_amount is not None
                else self.amount
            )

        super().save(*args, **kwargs)

    def on_requisition_approved(self, requisition=None):

        if self.payment_status == "AWAITING_PAYMENT":
            return

        VendorPayment.objects.filter(pk=self.pk).update(
            payment_status="AWAITING_PAYMENT"
        )
        self.refresh_from_db(fields=["payment_status"])

    def on_requisition_paid(self, requisition=None):
        from vendors.services import VendorPaymentService

        VendorPaymentService.sync_requisition_payment(self)


class PrepaymentAllocation(SoftDeletableTimeStampedModel):
    reference_prefix = "V-PrA"

    prepayment = models.ForeignKey(
        "vendors.VendorPayment",
        on_delete=models.CASCADE,
        related_name="allocations",
    )
    bill = models.ForeignKey(
        "vendors.VendorBill",
        on_delete=models.CASCADE,
        related_name="prepayment_allocations",
    )
    amount_applied = models.DecimalField(max_digits=50, decimal_places=20)

    class Meta:
        verbose_name = "Prepayment Allocation"
        verbose_name_plural = "Prepayment Allocations"
        ordering = ["-created_at"]
        constraints = [
            models.UniqueConstraint(
                fields=["prepayment", "bill"],
                condition=models.Q(deleted_at__isnull=True),
                name="unique_active_vendor_prepayment_per_bill",
            )
        ]

    def __str__(self):
        return f"{self.prepayment.reference_code} → {self.bill.reference_code}: {self.amount_applied}"


class GoodsReceivedNote(ReportableModelMixin, BaseApprovableModel):
    reference_prefix = "V-GRN"

    STATUS_CHOICES = [
        ("DRAFT", "Draft"),
        ("PENDING", "Pending"),
        ("APPROVED", "Approved"),
        ("REJECTED", "Rejected"),
    ]

    purchase_order = models.ForeignKey(
        "vendors.VendorPurchaseOrder",
        on_delete=models.CASCADE,
        related_name="goods_received_notes",
        blank=True,
        null=True,
    )

    bill = models.ForeignKey(
        "vendors.VendorBill",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="goods_received_notes",
        help_text="Bill that auto-created this GRN (ON_BILL_RECEIPT mode only).",
    )

    status = models.CharField(
        max_length=10,
        choices=STATUS_CHOICES,
        default="DRAFT",
    )

    are_financial_events_processed = models.BooleanField(default=False)
    is_inventory_moved = models.BooleanField(default=False)

    date_received = models.DateField(default=timezone.now)

    branch = models.ForeignKey(
        "institution.Branch",
        related_name="goods_received_notes",
        on_delete=models.CASCADE,
        null=True,
        blank=True,
    )

    institution = models.ForeignKey(
        "institution.Institution",
        related_name="goods_received_notes",
        on_delete=models.CASCADE,
        null=True,
        blank=True,
    )

    is_automated = models.BooleanField(
        default=False,
        help_text=(
            "True when this GRN was auto-created by the system on bill approval "
            "(ON_BILL_RECEIPT mode). False means it was created manually."
        ),
    )

    create_back_order = models.BooleanField(
        default=False,
        help_text=(
            "When True, if this GRN is linked to a purchase order and the received quantity is less than the ordered quantity, an incoming back order will be automatically created for the remaining quantity."
        ),
    )

    search_fields = [
        "purchase_order__reference_code",
        "bill__reference_code",
        "purchase_order__vendor__vendor_name",
        "bill__vendor__vendor_name",
        "status",
        "branch__branch_name",
    ]

    ordering_fields = [
        "purchase_order__reference_code",
        "bill__reference_code",
        "purchase_order__vendor__vendor_name",
        "bill__vendor__vendor_name",
        "status",
        "branch__branch_name",
        "date_received",
    ]

    filterset_fields = [
        "bill__base_uuid",
        "purchase_order__base_uuid",
        "bill__vendor__base_uuid",
        "purchase_order__vendor__base_uuid",
        "branch__base_uuid",
    ]

    class Meta:
        ordering = ["-created_at"]
        verbose_name = "Goods Received Note"
        verbose_name_plural = "Goods Received Notes"

    def __str__(self):
        po_ref = self.purchase_order.reference_code if self.purchase_order else "No PO"
        return f"GRN {self.reference_code} for purchase order {po_ref}"

    def get_institution(self):
        if self.purchase_order:
            return self.purchase_order.get_institution()

        if self.bill:
            return self.bill.get_institution()

        if self.branch_id:
            return self.branch.get_institution()

        return self.institution

    def clean(self):
        institution = self.get_institution()

        if self.pk:
            original = GoodsReceivedNote.objects.get(pk=self.pk)
            if original.status == "APPROVED":
                raise validation_error(
                    "Cannot edit a GRN once it's approved. Create a new GRN instead."
                )

        if institution and institution.inventory_increment_timing == "ON_BILL_RECEIPT":

            if not self.is_automated:
                raise validation_error(
                    "Cannot create a manual GRN when inventory increment timing is "
                    "'On Bill Receipt'. Inventory is recorded when the bill is approved."
                )

        if self.purchase_order and self.bill:
            raise validation_error(
                "A GRN cannot be linked to both a purchase order and a bill."
            )

        if not self.purchase_order and not self.bill:
            raise validation_error(
                "A GRN must be linked to either a purchase order or a bill."
            )

    @transaction.atomic
    def finish_workflow(self, approval: Approval):
        if approval.status == "completed":
            self.is_active = True
            if approval.action.name in ["create", "update"] and self.status in [
                "DRAFT",
                "PENDING",
            ]:
                self.status = "APPROVED"
                if not self.are_financial_events_processed:
                    self._process_financial_events()
            elif approval.action.name == "delete":
                self.status = "REJECTED"
                self.deleted_at = timezone.now()
        elif approval.status == "rejected":
            if approval.action.name == "create":
                self.status = "REJECTED"
            elif approval.action.name in ["update", "delete"]:
                self.status = "REJECTED"
                self.deleted_at = None

        self.save()

    @transaction.atomic
    def _process_financial_events(self):
        if self.are_financial_events_processed:
            return

        from accounts.utils import get_or_create_default_account
        from transactions.services import JournalLine, JournalPostingService
        from vendors.services import PurchaseInventoryAccountingService
        from utilities.helpers import quantize_decimal

        institution = self.get_institution()
        fiscal_year = get_fiscal_year(institution, self.date_received)

        if not self.is_inventory_moved:
            self._record_inventory_increment()

        total_line_item_cost = quantize_decimal(
            PurchaseInventoryAccountingService.get_actual_received_cost(self)
        )

        if total_line_item_cost > Decimal("0.00"):
            interim_inventory_account = get_or_create_default_account(
                institution,
                "stock_interim_account",
                None,
            )
            actual_inventory_account = get_or_create_default_account(
                institution,
                "inventory_account",
                None,
            )

            JournalPostingService.post(
                fiscal_year=fiscal_year,
                title=f"GRN {self.reference_code}",
                description="Stock received",
                transaction_date=self.date_received,
                lines=[
                    JournalLine(
                        account=interim_inventory_account,
                        entry_type="credit",
                        transaction_amount=total_line_item_cost,
                        transaction_currency=institution.currency,
                        exchange_rate=Decimal("1"),
                        description=(
                            f"Stock Interim cleared through GRN "
                            f"{self.reference_code}"
                        ),
                    ),
                    JournalLine(
                        account=actual_inventory_account,
                        entry_type="debit",
                        transaction_amount=total_line_item_cost,
                        transaction_currency=institution.currency,
                        exchange_rate=Decimal("1"),
                        description=(
                            f"Actual inventory received through GRN "
                            f"{self.reference_code}"
                        ),
                    ),
                ],
                branch=self.branch,
                content_type=ContentType.objects.get_for_model(
                    self.__class__,
                    for_concrete_model=False,
                ),
                object_id=self.id,
                source=self,
            )

        GoodsReceivedNote.objects.filter(pk=self.pk).update(
            are_financial_events_processed=True,
            is_inventory_moved=True,
        )
        self.are_financial_events_processed = True
        self.is_inventory_moved = True

    @transaction.atomic
    def _record_inventory_increment(self):
        from .services import StockService
        from procurement.incoming_back_order_automation import (
            sync_grn_fulfillment_status,
            sync_bill_fulfillment_status,
            sync_vpo_fulfillment_status,
            maybe_create_incoming_back_order_for_grn,
        )

        branch = (
            self.purchase_order.branch
            if self.purchase_order and self.purchase_order.branch
            else self.branch
        )

        for item in self.line_items.all():

            if item.inventory_item.item_type == "SERVICES":
                continue

            unit_cost = self._resolve_unit_price_for_grn_item(item)
            # tab = (
            #     item.get_tax_breakdowns().first()
            #     if hasattr(item, "get_tax_breakdowns")
            #     else None
            # )
            StockService.apply_stock_increment(
                item=item.inventory_item,
                unit_of_measure=(
                    item.unit_of_measure.unit_of_measure
                    if item.unit_of_measure
                    else None
                ),
                unit_cost=unit_cost,
                quantity=item.quantity,
                branch=branch,
                movement_type="GRN_RECEIPT",
                source_document=self,
                source_reference=self.reference_code,
            )

        sync_grn_fulfillment_status(self)

        if self.bill:
            sync_bill_fulfillment_status(self.bill)
            sync_vpo_fulfillment_status(self.bill)
        elif self.purchase_order:
            for bill in self.purchase_order.bills.filter(is_active=True):
                sync_bill_fulfillment_status(bill)
                sync_vpo_fulfillment_status(bill)

        maybe_create_incoming_back_order_for_grn(self)

    def _resolve_unit_price_for_grn_item(self, grn_line_item) -> Decimal:
        if not grn_line_item.inventory_item_id:
            return Decimal("0.00")

        def matching_bill_line_items(bill):
            line_items = bill.line_items.filter(
                item_type="inventory",
                inventory_item=grn_line_item.inventory_item,
                deleted_at__isnull=True,
            )

            if grn_line_item.unit_of_measure_id:
                line_items = line_items.filter(
                    unit_of_measure_id=grn_line_item.unit_of_measure_id
                )

            return line_items

        def matching_purchase_order_line_items(purchase_order):
            line_items = purchase_order.line_items.filter(
                item_type="inventory",
                inventory_item=grn_line_item.inventory_item,
                deleted_at__isnull=True,
            )

            if grn_line_item.unit_of_measure_id:
                line_items = line_items.filter(
                    unit_of_measure_id=grn_line_item.unit_of_measure_id
                )

            return line_items

        def last_used_unit_price():
            line_items = VendorBillLineItem.objects.filter(
                item_type="inventory",
                inventory_item=grn_line_item.inventory_item,
                deleted_at__isnull=True,
                bill__is_active=True,
                bill__deleted_at__isnull=True,
            )

            if grn_line_item.unit_of_measure_id:
                line_items = line_items.filter(
                    unit_of_measure_id=grn_line_item.unit_of_measure_id
                )

            last_line_item = line_items.order_by("-created_at").first()
            return last_line_item.unit_price if last_line_item else None

        if self.bill:
            match = matching_bill_line_items(self.bill).first()
            if match:
                return match.unit_price

        if self.purchase_order:
            for bill in self.purchase_order.bills.filter(is_active=True):
                match = matching_bill_line_items(bill).first()
                if match:
                    return match.unit_price

            match = matching_purchase_order_line_items(self.purchase_order).first()
            if match:
                return match.unit_price

        raise ValidationError(
            f"No Bill or Purchase Order cost is available for "
            f"'{grn_line_item.inventory_item.item_name}'."
        )

    def save(self, *args, **kwargs):
        is_new = self._state.adding
        self.full_clean()
        super().save(*args, **kwargs)

        if is_new:
            self.send_goods_received_note_email()

    from decimal import Decimal, ROUND_HALF_UP

    def send_goods_received_note_email(self):
        institution = self.get_institution()

        if not institution or not institution.institution_email:
            return

        subject = (
            f"Goods Received Note #{self.reference_code} "
            f"from {institution.institution_name}"
        )

        line_items = []
        total_amount = Decimal("0.00")

        for item in self.line_items.all():

            name = item.line_item_name or "Other Item"
            unit_of_measure = getattr(item, "other_asset_unit_of_measure", None)

            if item.item_type == "inventory" and item.inventory_item:
                name = item.inventory_item.item_name
                unit_of_measure = (
                    item.unit_of_measure.unit_of_measure.unit_name
                    if item.unit_of_measure
                    else None
                )
                unit_price = self._resolve_unit_price_for_grn_item(item)
            else:
                unit_price = getattr(item, "unit_price", Decimal("0.00")) or Decimal(
                    "0.00"
                )

            unit_price = unit_price.quantize(Decimal("0.00"), rounding=ROUND_HALF_UP)

            line_total = ((item.quantity or 0) * unit_price).quantize(
                Decimal("0.00"), rounding=ROUND_HALF_UP
            )

            total_amount += line_total

            line_items.append(
                {
                    "type": item.item_type,
                    "name": name,
                    "quantity": item.quantity,
                    "unit_of_measure": unit_of_measure,
                    "unit_price": unit_price,
                    "line_total": line_total,
                    "asset_category": getattr(
                        item.asset_category, "category_name", None
                    ),
                }
            )

        context = {
            "reference_code": self.reference_code,
            "institution_name": institution.institution_name,
            "institution_email": institution.institution_email,
            "issue_date": (
                self.created_at.strftime("%B %d, %Y")
                if hasattr(self, "created_at")
                else ""
            ),
            "status": self.status,
            "salutation_line": f"Dear {institution.institution_name}",
            "line_items": line_items,
            "purchase_order_reference": (
                self.purchase_order.reference_code if self.purchase_order else None
            ),
            "total_amount": total_amount,
        }

        from utilities.email_client import EmailClient

        EmailClient.send(
            subject=subject,
            recipients=[institution.institution_email],
            template_html="emails/goods_received_notes_email.html",
            context=context,
        )


class GoodsReceivedNoteLineItem(SoftDeletableTimeStampedModel):
    goods_received_note = models.ForeignKey(
        GoodsReceivedNote,
        on_delete=models.CASCADE,
        related_name="line_items",
    )

    inventory_item = models.ForeignKey(
        "items.InventoryItem",
        on_delete=models.CASCADE,
        related_name="grn_line_items",
    )
    unit_of_measure = models.ForeignKey(
        "items.InventoryItemUnitOfMeasure",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
    )
    quantity = models.PositiveIntegerField(default=1)

    class Meta:
        ordering = ["created_at"]
        verbose_name = "GRN Line Item"
        verbose_name_plural = "GRN Line Items"

    def __str__(self):
        return f"{self.inventory_item.item_name} x{self.quantity}"
