from django.db import models
from approval.models import Approval, BaseApprovableModel
from utilities.utility_base_model import SoftDeletableTimeStampedModel
from utilities.email_client import EmailClient
from items.services import StockValuationService
from system.models import ForeignExchange
from utilities.common_models import BaseTimeStamp
from datetime import date
from datetime import timedelta
from dateutil.relativedelta import relativedelta
from django.core.exceptions import ValidationError
from django.utils import timezone
from utilities.helpers import (
    AccountGroupTypes,
    format_currency_numbers_in_text,
    get_fiscal_year,
    get_quotation_expiry_date,
    validation_error,
)
from django.db import transaction
from django.conf import settings
from decimal import Decimal, ROUND_HALF_UP
from accounts.models import Account
from institution.models import Branch
from reports.mixins import ReportableModelMixin
from decimal import Decimal
from django.core.exceptions import ValidationError
from django.db.models import Sum, Q
from django.utils import timezone
from django.contrib.contenttypes.models import ContentType
from django.contrib.contenttypes.fields import GenericForeignKey, GenericRelation
from core.mixins import ReversibleFinancialMixin
from institution.models import DepositDistributionStrategy
from taxation.models import TaxApplicationBreakDown
from system.models import GenderChoice
from decimal import Decimal
from django.core.validators import MinValueValidator, MaxValueValidator


class Customer(ReportableModelMixin, BaseApprovableModel):
    reference_prefix = "CUS"

    CUSTOMER_TYPE_CHOICES = [
        ("individual", "Individual"),
        ("business", "Business"),
    ]
    institution = models.ForeignKey("institution.Institution", on_delete=models.CASCADE)
    customer_name = models.CharField(max_length=100, blank=False, null=False)
    customer_type = models.CharField(
        max_length=30, choices=CUSTOMER_TYPE_CHOICES, default="individual"
    )
    credit_limit = models.DecimalField(
        max_digits=50, decimal_places=20, null=True, blank=True
    )

    deposit_balance = models.DecimalField(
        max_digits=50,
        decimal_places=20,
        default=Decimal("0.00"),
        help_text="Amount the company owes the customer. Always stored as a positive value.",
    )
    salesperson = models.ForeignKey(
        "customers.SalesPerson",
        on_delete=models.CASCADE,
        null=True,
        blank=True,
    )
    address = models.CharField(max_length=255, blank=True, null=True)
    phone_number = models.CharField(
        max_length=15,
        blank=True,
        null=True,
    )
    email = models.EmailField(
        max_length=254,
        blank=True,
        null=True,
    )
    default_account = models.ForeignKey(
        Account,
        on_delete=models.CASCADE,
        null=True,
        blank=True,
        related_name="customers",
        help_text="The default receivable account for this customer",
    )
    gender = models.CharField(
        max_length=10,
        choices=GenderChoice.choices,
        default="OTHER",
        null=True,
        blank=True,
    )

    payment_term = models.ForeignKey(
        "customers.PaymentTerm",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
    )

    currency = models.ForeignKey(
        "system.SystemCurrency",
        on_delete=models.CASCADE,
        null=True,
        blank=True,
    )

    opening_balance = models.DecimalField(
        max_digits=50,
        decimal_places=20,
        default=Decimal("0.00"),
        help_text="(+) means customer owes company (receivable), (-) means company owes customer (deposit/liability).",
    )
    opening_balance_received_date = models.DateTimeField(null=True, blank=True)
    opening_balance_account = models.ForeignKey(
        Account,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="customer_opening_balances",
        help_text="The account used to record the opening balance for this customer. If not specified, the system will use the default opening account.",
    )

    outstanding_receivables_balance = models.DecimalField(
        max_digits=50,
        decimal_places=20,
        default=Decimal("0.00"),
        help_text="Total amount of unpaid invoices for this customer. Always stored as a positive value.",
    )

    deposit_distribution_strategy = models.CharField(
        max_length=50,
        choices=DepositDistributionStrategy.choices,
        default=DepositDistributionStrategy.PAY_OLDEST_INVOICE_FIRST,
    )

    profile_photo = models.ImageField(
        upload_to="customer_photos/",
        null=True,
        blank=True,
        help_text="Optional profile photo for the customer",
    )

    tin = models.CharField(
        max_length=40,
        null=True,
        blank=True,
        help_text="Tax Identification Number (unique per institution, optional)",
    )

    are_initial_transactions_processed = models.BooleanField(default=False)

    search_fields = [
        "customer_name",
        "email",
        "phone_number",
        "customer_type",
    ]
    ordering_fields = [
        "customer_name",
        "credit_limit",
        "outstanding_receivables_balance",
        "deposit_balance",
    ]

    filterset_fields = [
        *BaseApprovableModel.filterset_fields,
        "currency_id",
        "is_active",
    ]

    def get_available_credit(self):

        if self.credit_limit is None:
            return None
        return self.credit_limit - self.outstanding_receivables_balance

    def check_credit_limit(self, additional_amount):

        if self.credit_limit is None:
            return

        available_credit = self.get_available_credit()
        if additional_amount > available_credit:
            from utilities.helpers import validation_error, format_currency

            validation_error(
                f"Credit limit breached for {self.customer_name}. "
                f"Credit Limit: {format_currency(self.credit_limit)}, "
                f"Available Credit: {format_currency(available_credit)}, "
                f"Attempted Amount: {format_currency(additional_amount)}."
            )

    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=["institution", "tin"],
                name="unique_tin_per_institution",
                condition=models.Q(tin__isnull=False),
            )
        ]

    def clean(self):
        if (
            self.default_account
            and self.default_account.currency
            and self.currency != self.default_account.currency
        ):
            raise validation_error(
                "The default account currency must match the customer currency."
            )

        if (
            self.opening_balance != Decimal("0")
            and not self.opening_balance_received_date
        ):
            raise validation_error(
                "You must specify the date for which this opening balance was created."
            )

    @classmethod
    def get_foreign_key_display_fields(cls):
        return {
            "currency": "code",
            "payment_term": "name",
            "default_account": "account_name",
            "opening_balance_account": "account_name",
        }

    @classmethod
    def get_excluded_report_fields(cls):
        return super().get_excluded_report_fields() + [
            "profile_photo",
            "salesperson",
        ]

    @classmethod
    def get_additional_filters(cls):
        return ["customer_type", "is_active"]

    @classmethod
    def get_filter_serializer_class(cls):
        from customers.filters import CustomerReportFilterSerializer

        return CustomerReportFilterSerializer

    def get_institution(self):
        return self.institution

    def get_deposit_strategy(self):
        return (
            self.deposit_distribution_strategy
            or self.get_institution().deposit_distribution_strategy
        )

    def save(self, *args, **kwargs):
        outstanding_receivables_balance_change_reason = kwargs.pop(
            "outstanding_receivables_balance_change_reason", None
        )
        deposit_balance_change_reason = kwargs.pop(
            "deposit_balance_change_reason", None
        )
        self.full_clean()
        is_new = self._state.adding

        previous_recievable_balance = None
        previous_deposit_balance = None

        if not is_new and self.pk:
            previous_recievable_balance = (
                Customer.objects.filter(pk=self.pk)
                .values_list("outstanding_receivables_balance", flat=True)
                .first()
            )
            previous_deposit_balance = (
                Customer.objects.filter(pk=self.pk)
                .values_list("deposit_balance", flat=True)
                .first()
            )

        super().save(*args, **kwargs)

        if (
            previous_recievable_balance is not None
            and previous_recievable_balance != self.outstanding_receivables_balance
        ):
            CustomerBalanceAdjustment.objects.create(
                customer=self,
                balance_adjusted="OUTSTANDING_RECEIVABLE_BALANCE",
                amount=self.outstanding_receivables_balance
                - previous_recievable_balance,
                amount_before_adjustment=previous_recievable_balance,
                amount_after_adjustment=self.outstanding_receivables_balance,
                reason=outstanding_receivables_balance_change_reason
                or "Customer Outstanding Receivables Balance Update",
            )

        if (
            previous_deposit_balance is not None
            and previous_deposit_balance != self.deposit_balance
        ):
            CustomerBalanceAdjustment.objects.create(
                customer=self,
                balance_adjusted="DEPOSIT_BALANCE",
                amount=self.deposit_balance - previous_deposit_balance,
                amount_before_adjustment=previous_deposit_balance,
                amount_after_adjustment=self.deposit_balance,
                reason=deposit_balance_change_reason
                or "Customer Deposit Balance Update",
            )

    def __str__(self):
        return f"{self.customer_name} ({self.customer_type})"

    def get_gender_and_name(self):
        full_name = self.customer_name

        if self.customer_type == "business":
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
        from utilities.helpers import get_fiscal_year

        if self.are_initial_transactions_processed:
            return

        if self.opening_balance == 0:
            return

        institution = self.get_institution()
        opening_balance_date = (
            self.opening_balance_received_date.date()
            if self.opening_balance_received_date
            else (self.created_at.date() if self.created_at else timezone.localdate())
        )
        fiscal_year = get_fiscal_year(
            institution,
            opening_balance_date,
        )

        from utilities.helpers import format_2dp

        journal_owner = (
            self._create_opening_balance_payment(opening_balance_date)
            if self.opening_balance < 0
            else self._create_opening_balance_invoice()
        )

        opening_balance_account = (
            self.opening_balance_account
            or get_or_create_default_account(
                institution, "opening_balance_account", self.currency
            )
        )

        receivable_account = get_or_create_default_account(
            institution, "receivable_account", self.currency
        )

        document_currency, document_rate = journal_owner.determine_rate_currency_used()
        amount = abs(self.opening_balance)

        if self.opening_balance < 0:
            journal_lines = [
                JournalLine(
                    account=receivable_account,
                    entry_type="credit",
                    transaction_amount=amount,
                    transaction_currency=document_currency,
                    exchange_rate=document_rate,
                    description=(
                        f"Opening Balance: Company owes " f"{self.customer_name}"
                    ),
                ),
                JournalLine(
                    account=opening_balance_account,
                    entry_type="debit",
                    transaction_amount=amount,
                    transaction_currency=document_currency,
                    exchange_rate=document_rate,
                    description=f"Cash held for {self.customer_name}",
                ),
            ]
        else:
            journal_lines = [
                JournalLine(
                    account=receivable_account,
                    entry_type="debit",
                    transaction_amount=amount,
                    transaction_currency=document_currency,
                    exchange_rate=document_rate,
                    description=(f"Receivable: {self.customer_name} owes company"),
                ),
                JournalLine(
                    account=opening_balance_account,
                    entry_type="credit",
                    transaction_amount=amount,
                    transaction_currency=document_currency,
                    exchange_rate=document_rate,
                    description=(f"Expected payment from {self.customer_name}"),
                ),
            ]

        JournalPostingService.post(
            fiscal_year=fiscal_year,
            title=f"Opening Balance for {self.customer_name}",
            description=(
                f"Customer added with opening balance of "
                f"{self.currency.code} "
                f"{format_2dp(self.opening_balance)}"
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

        Customer.objects.filter(pk=self.pk).update(
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
            before = self.outstanding_receivables_balance

            Customer.objects.filter(pk=self.pk).update(
                outstanding_receivables_balance=F("outstanding_receivables_balance")
                + amount
            )

            self.refresh_from_db(fields=["outstanding_receivables_balance"])
            after = self.outstanding_receivables_balance
            balance_type = "OUTSTANDING_RECEIVABLE_BALANCE"

        else:
            before = self.deposit_balance

            Customer.objects.filter(pk=self.pk).update(
                deposit_balance=F("deposit_balance") + amount
            )

            self.refresh_from_db(fields=["deposit_balance"])
            after = self.deposit_balance
            balance_type = "DEPOSIT_BALANCE"

        CustomerBalanceAdjustment.objects.create(
            customer=self,
            balance_adjusted=balance_type,
            amount=amount,
            amount_before_adjustment=before,
            amount_after_adjustment=after,
            reason="Opening balance applied",
        )

    def _create_opening_balance_payment(self, payment_date):
        institution = self.get_institution()
        amount = abs(self.opening_balance)

        payment = CustomerPayment.objects.create(
            institution=institution,
            customer=self,
            invoice=None,
            currency=self.currency,
            settlement_currency=self.currency,
            amount=amount,
            settlement_amount=amount,
            amount_reconciled=Decimal("0"),
            remaining_balance=amount,
            payment_date=payment_date,
            coa_cash_account=None,
            payment_status="APPROVED",
            approval_status="active",
            is_active=True,
            are_initial_journal_entries_made=True,
            description=f"Opening customer credit for {self.customer_name}",
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

    def _create_opening_balance_invoice(self):

        institution = self.get_institution()

        branch = (
            institution.branches.filter(deleted_at__isnull=True)
            .order_by("created_at")
            .first()
        )
        if branch is None:
            return

        amount = abs(self.opening_balance)
        issue_date = (
            self.opening_balance_received_date.date()
            if self.opening_balance_received_date
            else (self.created_at.date() if self.created_at else date.today())
        )

        invoice = Invoice(
            customer=self,
            branch=branch,
            currency=self.currency,
            issue_date=issue_date,
            due_date=issue_date,
            invoice_status="sent",
            invoice_payment_status="unpaid",
            is_active=False,
            approval_status="under_creation",
            total_amount=amount,
            net_total=amount,
            gross_total=amount,
            amount_due=amount,
            adjusted_total=amount,
            tax_total=Decimal("0.00"),
            credit_note_total=Decimal("0.00"),
            debit_note_total=Decimal("0.00"),
            partial_amount_paid=Decimal("0.00"),
            are_initial_journal_entries_made=True,
            description=f"Balance forward as of {issue_date}. Initial opening balance recorded on customer creation.",
            goods_issued_note_status="full_issued",
        )
        invoice.save()

        if self.currency != institution.currency:
            from system.services import FxRateService

            _, opening_balance_rate = self.determine_rate_currency_used()
            FxRateService.create_document_snapshot(
                source=invoice,
                institution=institution,
                currency=self.currency,
                supplied_rate=opening_balance_rate,
            )

        invoice.confirm_create()
        return invoice

    def finish_workflow(self, approval: Approval):
        with transaction.atomic():
            if approval.status == "completed":
                if approval.action.name in ["create", "update"]:
                    self.approval_status = "active"
                    self.is_active = True
                    self.deleted_at = None
                    self.original_data = None

                    if not self.are_initial_transactions_processed:
                        self._process_financial_events()

                elif approval.action.name == "delete":
                    self.approval_status = "active"
                    # The no-workflow path may already have soft-deleted the customer.
                    if self.deleted_at is None:
                        self.delete(using_soft_delete=True)

            elif approval.status == "rejected":
                if approval.action.name == "create":
                    self.approval_status = "active"
                    self.is_active = False
                    self.deleted_at = timezone.now()

                elif approval.action.name in ["update", "delete"]:
                    self.approval_status = "active"
                    self.is_active = True
                    self.deleted_at = None
                    if approval.action.name == "update" and self.original_data:
                        self.restore_from_data(self.original_data)
                        self.original_data = None

            self.save()

    def get_currency(self):
        return self.currency, True

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


class Quotation(ReportableModelMixin, BaseApprovableModel):
    reference_prefix = "QN"

    QUOTATION_STATUS_CHOICES = [
        ("draft", "Draft"),
        ("approved", "Approved"),
        ("sent", "Sent"),
        ("accepted", "Accepted"),
        ("rejected", "Rejected"),
        ("expired", "Expired"),
    ]

    branch = models.ForeignKey(
        Branch,
        related_name="quotations",
        on_delete=models.CASCADE,
        null=True,
        blank=True,
    )

    customer = models.ForeignKey(
        Customer, on_delete=models.CASCADE, blank=True, null=True
    )

    currency = models.ForeignKey(
        "system.SystemCurrency",
        on_delete=models.PROTECT,
        related_name="customer_quotations",
        null=True,
        blank=True,
    )

    issue_date = models.DateField()

    expiry_date = models.DateField(
        null=True, blank=True, help_text="Date when quotation expires"
    )

    status = models.CharField(
        max_length=20, choices=QUOTATION_STATUS_CHOICES, default="draft"
    )

    sales_person = models.ForeignKey(
        "customers.SalesPerson", on_delete=models.CASCADE, null=True, blank=True
    )

    net_total = models.DecimalField(
        max_digits=50,
        decimal_places=20,
        default=Decimal("0.00"),
    )
    tax_total = models.DecimalField(
        max_digits=50,
        decimal_places=20,
        default=Decimal("0.00"),
    )
    gross_total = models.DecimalField(
        max_digits=50,
        decimal_places=20,
        default=Decimal("0.00"),
    )
    total_discount = models.DecimalField(
        max_digits=50,
        decimal_places=20,
        default=Decimal("0.00"),
    )

    search_fields = ["customer__customer_name"]

    ordering_fields = [
        "reference_code",
        "customer__customer_name",
        "issue_date",
        "expiry_date",
        "gross_total",
        "status",
    ]

    filterset_fields = [
        *BaseApprovableModel.filterset_fields,
        "customer__base_uuid",
        "status",
    ]

    @classmethod
    def get_additional_filters(cls):
        return [
            "status",
            "issue_date",
        ]

    @classmethod
    def get_foreign_key_display_fields(cls):
        return {
            "customer": "customer_name",
            "sales_person": "name",
            "branch": "branch_name",
        }

    @classmethod
    def get_filter_serializer_class(cls):
        from customers.filters import QuotationReportFilterSerializer

        return QuotationReportFilterSerializer

    class Meta:
        ordering = ["-created_at"]
        verbose_name = "Quotation"
        verbose_name_plural = "Quotations"

    def __str__(self):
        return f"Quotation {self.status} for {self.customer.customer_name if self.customer else 'No Customer Attached'}"

    def clean(self):
        if not self.branch:
            raise validation_error("Branch is required to create a quotation.")

        if self.issue_date > date.today():
            raise ValidationError("Issue date cannot be in the future.")

        if self.expiry_date and self.expiry_date < timezone.now().date():
            raise validation_error("Expiry date cannot be in the past.")

    @property
    def total_amount(self):
        if self.gross_total:
            return self.gross_total

        return sum(item.line_total for item in self.line_items.all())

    def save(self, *args, **kwargs):
        self.full_clean()
        is_new = self._state.adding

        if is_new and not self.expiry_date:
            self.expiry_date = self.get_due_date()

        super().save(*args, **kwargs)

        if not is_new and self.status == "sent" and self.customer:
            self.send_quotation_email()

    def get_due_date(self):
        return get_quotation_expiry_date(self.get_institution(), self.issue_date)

    def send_quotation_email(self):
        if not self.customer or not self.customer.email:
            return

        customer = self.customer

        if customer is None:
            return

        if customer.email is None:
            return

        subject = f"Quotation #{self.status}"

        quotation_url = f"{settings.FRONTEND_URL}/quotation-preview/{self.base_uuid}"
        document_currency, _ = self.determine_rate_currency_used()
        currency_label = document_currency.symbol or document_currency.code
        legacy_subtotal = sum(
            (item.line_total or Decimal("0.00") for item in self.line_items.all()),
            Decimal("0.00"),
        )

        context = {
            "customer_name": self.customer.customer_name,
            "quotation_number": self.reference_code,
            "quotation_url": quotation_url,
            "subtotal": self.net_total or legacy_subtotal,
            "tax_total": self.tax_total or Decimal("0.00"),
            "total_amount": self.gross_total or legacy_subtotal,
            "issue_date": self.issue_date,
            "institution_name": self.customer.institution.institution_name,
            "currency": currency_label,
        }

        reciepients_lists = [self.customer.email]

        institution_email = (
            (self.branch.branch_email or self.branch.institution.institution_email)
            if self.branch.institution.are_notifications_enabled
            else None
        )

        if institution_email:
            reciepients_lists.append(institution_email)

        EmailClient.send(
            subject=subject,
            recipients=reciepients_lists,
            template_html="emails/quotation_email.html",
            context=context,
        )

    def get_institution(self):
        if self.branch_id:
            return self.branch.institution
        if self.customer_id:
            return self.customer.institution
        return None

    @classmethod
    def get_institution_filter_field(cls):
        return "institution"

    def finish_workflow(self, approval: Approval):
        with transaction.atomic():
            if approval.status == "completed":
                if approval.action.name in ["create", "update"]:
                    self.is_active = True
                    self.status = "approved"
                    self.approval_status = "active"

                elif approval.action.name == "delete":
                    self.is_active = False
                    self.deleted_at = timezone.now()
                    self.status = "rejected"

            elif approval.status == "rejected":
                if approval.action.name == "create":
                    self.is_active = False
                    self.status = "rejected"

                elif approval.action.name in ["update", "delete"]:
                    self.is_active = False
                    self.deleted_at = None

        self.save()

    def accept_quotation(self):
        if self.status not in ["sent", "approved"]:
            raise ValidationError(
                "Can't update quotation status to accepted unless it is sent or approved"
            )
        self.status = "accepted"
        self.save()

    def update_status_from_purchase_order(self):
        if self.status == "sent" or self.status == "approved":
            self.accept_quotation()
        else:
            raise ValidationError("Quotation cannot be accepted unless sent.")

    def determine_rate_currency_used(self):
        from system.services import FxRateService

        institution_currency = self.get_institution().currency
        document_currency = self.currency or institution_currency

        rate = FxRateService.resolve_base_rate(
            institution=self.get_institution(),
            currency=document_currency,
            source=self,
        )

        return (
            document_currency,
            rate,
        )

    def get_currency(self):
        target_currency, _ = self.determine_rate_currency_used()
        return target_currency, False if target_currency else True


class QuotationLineItem(BaseTimeStamp):
    quotation = models.ForeignKey(
        Quotation,
        on_delete=models.CASCADE,
        related_name="line_items",
    )
    line_item = models.ForeignKey(
        "items.BranchInventoryItem",
        on_delete=models.CASCADE,
        null=True,
        blank=True,
    )
    unit_of_measure = models.ForeignKey(
        "items.BranchInventoryItemUnitOfMeasure",
        on_delete=models.CASCADE,
        null=True,
        blank=True,
    )
    quantity = models.PositiveIntegerField(default=1)
    unit_price = models.DecimalField(max_digits=50, decimal_places=20, default=0.00)
    line_total = models.DecimalField(max_digits=50, decimal_places=20, default=0.00)

    tax_breakdowns = GenericRelation(
        TaxApplicationBreakDown,
        content_type_field="content_type",
        object_id_field="object_id",
        related_query_name="quotation_line_items",
    )
    discounts = GenericRelation(
        "SalesLineDiscount",
        content_type_field="content_type",
        object_id_field="object_id",
        related_query_name="quotation_line_items",
    )

    def __str__(self):
        return f"Line item for {self.quotation.status}: {self.line_item.inventory_item.item_name} (x{self.quantity})"

    def get_tax_breakdowns(self):
        return self.tax_breakdowns.all()

    def get_discounts(self):
        return self.discounts.filter(deleted_at__isnull=True).order_by("position")


class SalesLineDiscount(SoftDeletableTimeStampedModel):
    reference_prefix = "SLD"

    DISCOUNT_TYPE_CHOICES = [
        ("percentage", "Percentage"),
        ("fixed", "Fixed"),
    ]

    SUPPORTED_LINE_MODELS = [
        "quotationlineitem",
        "customerpurchaseorderlineitem",
        "invoicelineitem",
    ]

    content_type = models.ForeignKey(
        ContentType,
        on_delete=models.CASCADE,
        limit_choices_to={
            "model__in": SUPPORTED_LINE_MODELS,
        },
    )
    object_id = models.PositiveBigIntegerField()
    content_object = GenericForeignKey("content_type", "object_id")

    discount_type = models.CharField(max_length=20, choices=DISCOUNT_TYPE_CHOICES)
    discount_value = models.DecimalField(
        max_digits=50,
        decimal_places=20,
        validators=[MinValueValidator(Decimal("0"))],
    )
    discount_amount = models.DecimalField(
        max_digits=50,
        decimal_places=20,
        default=Decimal("0.00"),
        editable=False,
    )
    allocated_amount = models.DecimalField(
        max_digits=50,
        decimal_places=20,
        default=Decimal("0.00"),
        editable=False,
        help_text="Amount of fixed discount already allocated to downstream documents.",
    )
    position = models.PositiveIntegerField(default=0)
    source_discount = models.ForeignKey(
        "self",
        on_delete=models.SET_NULL,
        related_name="inherited_discounts",
        null=True,
        blank=True,
    )

    class Meta:
        verbose_name = "Sales Line Discount"
        verbose_name_plural = "Sales Line Discounts"
        ordering = ["position", "created_at"]
        constraints = [
            models.UniqueConstraint(
                fields=["content_type", "object_id", "position"],
                condition=models.Q(deleted_at__isnull=True),
                name="unique_discount_position_per_line",
            )
        ]
        indexes = [
            models.Index(
                fields=["content_type", "object_id"], name="idx_sld_target_line"
            ),
        ]

    def get_target_document(self):
        line = self.content_object
        if line is None:
            return None

        for attribute in ("quotation", "purchase_order", "invoice"):
            document = getattr(line, attribute, None)
            if document is not None:
                return document

        return None

    def get_institution(self):
        document = self.get_target_document()
        if document is None:
            return None

        return document.get_institution()

    def clean(self):
        from django.core.exceptions import ValidationError

        if not self.content_type_id or not self.object_id:
            return

        if self.content_type.model not in self.SUPPORTED_LINE_MODELS:
            raise ValidationError(
                "Discounts can only be applied to sales document line items."
            )

        if self.content_object is None:
            raise ValidationError("The discounted line item no longer exists.")

        if self.discount_value < Decimal("0"):
            raise ValidationError("Discount value cannot be negative.")

        if self.discount_type == "percentage" and self.discount_value > Decimal("100"):
            raise ValidationError("Percentage discount cannot exceed 100%.")

    def __str__(self):
        return (
            f"{self.get_discount_type_display()} discount of {self.discount_value} "
            f"on line {self.object_id}"
        )


class CustomerPurchaseOrder(ReportableModelMixin, BaseApprovableModel):
    reference_prefix = "SO"

    PURCHASE_ORDER_STATUS_CHOICES = [
        ("draft", "Draft"),
        ("approved", "Approved"),
        ("completed", "Completed"),
        ("invoiced", "Invoiced"),
        ("canceled", "Canceled"),
    ]

    customer = models.ForeignKey(
        Customer,
        on_delete=models.CASCADE,
        blank=True,
        null=True,
        related_name="purchase_orders",
    )

    quotation = models.ForeignKey(
        "customers.Quotation", on_delete=models.CASCADE, null=True, blank=True
    )

    currency = models.ForeignKey(
        "system.SystemCurrency",
        on_delete=models.PROTECT,
        related_name="customer_sales_orders",
        null=True,
        blank=True,
    )

    issue_date = models.DateField(default=timezone.now)

    status = models.CharField(
        max_length=20, choices=PURCHASE_ORDER_STATUS_CHOICES, default="draft"
    )

    goods_issued_note_status = models.CharField(
        max_length=100,
        choices=[
            ("full_issued", "Full Issued"),
            ("not_issued", "Not Issued"),
            ("partially_issued", "Partially Issued"),
            ("not_required", "Not Required"),
        ],
        default="not_issued",
    )

    invoice_status = models.CharField(
        max_length=100,
        choices=[
            ("fully_invoiced", "Fully Invoiced"),
            ("not_invoiced", "Not Invoiced"),
            ("partially_invoiced", "Partially Invoiced"),
        ],
        default="not_invoiced",
    )

    branch = models.ForeignKey(
        Branch,
        related_name="customer_purchase_orders",
        on_delete=models.CASCADE,
        null=True,
        blank=True,
    )

    net_total = models.DecimalField(
        max_digits=50,
        decimal_places=20,
        default=Decimal("0.00"),
    )
    tax_total = models.DecimalField(
        max_digits=50,
        decimal_places=20,
        default=Decimal("0.00"),
    )
    gross_total = models.DecimalField(
        max_digits=50,
        decimal_places=20,
        default=Decimal("0.00"),
    )
    total_discount = models.DecimalField(
        max_digits=50,
        decimal_places=20,
        default=Decimal("0.00"),
    )

    search_fields = [
        "quotation__customer__customer_name",
        "quotation__customer__email",
        "quotation__customer__customer_type",
        "branch__branch_name",
    ]

    ordering_fields = [
        "reference_code",
        "issue_date",
        "status",
        "goods_issued_note_status",
        "invoice_status",
        "customer__customer_name",
        "gross_total",
    ]

    filterset_fields = [
        "customer__base_uuid",
        "quotation__base_uuid",
        "branch__base_uuid",
        "status",
        "goods_issued_note_status",
        "invoice_status",
    ]

    class Meta:
        ordering = ["-created_at"]
        verbose_name = "Customer Purchase Order"
        verbose_name_plural = "Customer Purchase Orders"

    def get_purchase_order_customer(self):
        customer = getattr(self, "customer", None)

        if customer is None:
            customer = getattr(self.quotation, "customer", None)

        return customer

    def complete_purchase_order(self):
        if self.status != "approved":
            raise ValidationError("Can't complete purchase order unless it is approved")
        self.status = "invoiced"
        self.save()

    def update_purchase_order_status_on_sent_invoice(self):
        if self.status == "approved":
            self.complete_purchase_order()
        else:
            raise ValidationError("Purchase order cannot be completed unless approved.")

    @classmethod
    def get_additional_filters(cls):
        return [
            "status",
            "is_active",
            "reference_code",
        ]

    @classmethod
    def get_filter_serializer_class(cls):
        from customers.filters import CustomerPurchaseOrderReportFilterSerializer

        return CustomerPurchaseOrderReportFilterSerializer

    def __str__(self):
        return f"Purchase Order {self.reference_code} for {self.quotation.customer.customer_name if self.quotation else None}"

    def clean(self):
        if self.issue_date > date.today():
            raise ValidationError("Issue date cannot be in the future.")

    def get_institution(self):
        return self.branch.institution

    @classmethod
    def get_institution_filter_field(cls):
        return "branch__institution"

    @property
    def total_price(self):
        if self.gross_total:
            return self.gross_total

        return sum(
            line_item.line_total
            for line_item in self.line_items.filter(deleted_at__isnull=True)
        )

    def finish_workflow(self, approval: Approval):
        with transaction.atomic():
            if approval.status == "completed":
                if approval.action.name == "create":
                    self.approval_status = "active"
                    self.is_active = True
                    self.status = "approved"

                    has_goods = (
                        self.line_items.active()
                        .filter(
                            line_item__inventory_item__item_type="GOODS",
                        )
                        .exists()
                    )

                    if not has_goods:
                        self.goods_issued_note_status = "not_required"

                    if has_goods and self.goods_issued_note_status == "not_issued":
                        from .services import AutoGINCreationService

                        AutoGINCreationService.start(
                            source=self,
                            inventory_reduction_timing=self.get_institution().inventory_reduction_timing,
                            source_approval=approval,
                        ),

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

        if self.quotation and self.quotation.status == "sent":
            self.quotation.update_status_from_purchase_order()

        super().save(*args, **kwargs)

    def determine_rate_currency_used(self):
        from system.services import FxRateService

        institution = self.get_institution()
        document_currency = (
            self.currency
            or (
                self.quotation.currency
                if self.quotation and self.quotation.currency_id
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
                else (
                    self.quotation
                    if self.quotation and self.quotation.currency_id
                    else self
                )
            ),
        )
        return document_currency, rate

    def get_currency(self):
        target_currency, _ = self.determine_rate_currency_used()
        return target_currency, False if target_currency else True

    def send_customer_purchase_order_email(self):
        if self.get_purchase_order_customer() is None:
            return

        customer = self.get_purchase_order_customer()

        if customer.email is None:
            return

        institution = self.get_institution()

        subject = (
            f"Customer PO #{self.reference_code} from {institution.institution_name}"
        )
        document_currency, _ = self.determine_rate_currency_used()
        currency_label = document_currency.symbol or document_currency.code
        legacy_subtotal = sum(
            (item.line_total or Decimal("0.00") for item in self.line_items.all()),
            Decimal("0.00"),
        )

        context = {
            "reference_code": self.reference_code,
            "institution_name": institution.institution_name,
            "institution_email": institution.institution_email,
            "issue_date": self.issue_date.strftime("%B %d, %Y"),
            "salutation_line": f"Dear {customer.get_gender_and_name()}",
            "customer_name": customer.customer_name,
            "customer_email": customer.email,
            "customer_address": customer.address,
            "line_items": [
                {
                    "name": item.line_item.inventory_item.item_name,
                    "quantity": item.quantity,
                    "unit_price": f"{item.unit_price:.2f}",
                    "line_total": f"{item.line_total:.2f}",
                }
                for item in self.line_items.all()
            ],
            "currency": currency_label,
            "subtotal": f"{(self.net_total or legacy_subtotal):.2f}",
            "tax_total": f"{(self.tax_total or Decimal('0.00')):.2f}",
            "total_amount": f"{(self.gross_total or legacy_subtotal):.2f}",
        }

        reciepients_lists = [customer.email]

        institution_email = (
            (self.branch.branch_email or self.branch.institution.institution_email)
            if self.branch.institution.are_notifications_enabled
            else None
        )

        if institution_email:
            reciepients_lists.append(institution_email)

        EmailClient.send(
            subject=subject,
            recipients=reciepients_lists,
            template_html="emails/customer_purchase_order_email.html",
            context=context,
        )


class CustomerPurchaseOrderLineItem(SoftDeletableTimeStampedModel):
    purchase_order = models.ForeignKey(
        CustomerPurchaseOrder, on_delete=models.CASCADE, related_name="line_items"
    )
    source_quotation_line = models.ForeignKey(
        QuotationLineItem,
        on_delete=models.SET_NULL,
        related_name="sales_order_lines",
        null=True,
        blank=True,
    )
    line_item = models.ForeignKey(
        "items.BranchInventoryItem",
        on_delete=models.CASCADE,
        related_name="customer_line_items",
        null=True,
        blank=True,
    )
    unit_of_measure = models.ForeignKey(
        "items.BranchInventoryItemUnitOfMeasure",
        on_delete=models.CASCADE,
        null=True,
        blank=True,
    )
    quantity = models.PositiveIntegerField(default=1)
    unit_price = models.DecimalField(max_digits=50, decimal_places=20, default=0.00)
    line_total = models.DecimalField(max_digits=50, decimal_places=20, default=0.00)

    tax_breakdowns = GenericRelation(
        TaxApplicationBreakDown,
        content_type_field="content_type",
        object_id_field="object_id",
        related_query_name="sales_order_line_items",
    )
    discounts = GenericRelation(
        "SalesLineDiscount",
        content_type_field="content_type",
        object_id_field="object_id",
        related_query_name="sales_order_line_items",
    )

    quantity_issued = models.PositiveIntegerField(
        default=0,
        help_text="Total quantity issued across all approved GINs for this CPO.",
    )
    quantity_pending = models.PositiveIntegerField(
        default=0,
        help_text="Remaining quantity yet to be issued (quantity - quantity_issued).",
    )

    def __str__(self):
        return f"Line item for {self.purchase_order.reference_code}: {self.line_item.inventory_item.item_name} (x{self.quantity})"

    def get_tax_breakdowns(self):
        return self.tax_breakdowns.all()

    def get_discounts(self):
        return self.discounts.filter(deleted_at__isnull=True).order_by("position")

    class Meta:
        verbose_name = "Customer Purchase Order Line Item"
        verbose_name_plural = "Customer Purchase Order Line Items"
        ordering = ["-created_at"]

        indexes = (
            models.Index(
                fields=["line_item", "purchase_order"], name="idx_cpolineitem_item"
            ),
        )


class CustomerPurchaseOrderPayment(
    ReportableModelMixin, BaseApprovableModel, ReversibleFinancialMixin
):
    reference_prefix = "SO-PAY"

    sales_order = models.ForeignKey(
        CustomerPurchaseOrder,
        on_delete=models.CASCADE,
        related_name="payments",
    )

    invoice = models.ForeignKey(
        "customers.Invoice",
        on_delete=models.CASCADE,
        related_name="sales_order_payments",
        null=True,
        blank=True,
    )

    amount_paid = models.DecimalField(
        max_digits=50,
        decimal_places=20,
    )

    amount_applied = models.DecimalField(
        max_digits=50,
        decimal_places=20,
        default=0,
    )

    payment_date = models.DateField(default=timezone.now)

    payment_status = models.CharField(
        max_length=255,
        choices=[
            ("pending", "Pending"),
            ("approved", "Approved"),
            ("transferred", "Transferred"),
            ("rejected", "Rejected"),
        ],
        default="pending",
    )

    is_transfer_processed = models.BooleanField(
        default=False,
    )
    account = models.ForeignKey(
        "accounts.Account",
        on_delete=models.CASCADE,
        related_name="customer_purchase_order_payments",
        help_text="Account from which the payment was made. This account will be debited when the payment is approved.",
    )

    are_initial_journal_entries_made = models.BooleanField(default=False)

    search_fields = [
        "sales_order__reference_code",
        "invoice__reference_code",
        "reference_code",
    ]

    class Meta:
        ordering = ["-created_at"]
        verbose_name = "Sales Order Payment"
        verbose_name_plural = "Sales Order Payments"

    def __str__(self):
        return f"{self.reference_code} - {self.amount_paid}"

    def get_institution(self):
        return self.sales_order.get_institution()

    def clean(self):
        super().clean()

        self.account.validate_account(
            expected_group_types={AccountGroupTypes.ASSET},
            expected_role_codes={"cash_account"},
        )

    def save(self, *args, **kwargs):
        self.full_clean()

        super().save(*args, **kwargs)

    def finish_workflow(self, approval: Approval):
        with transaction.atomic():
            if approval.status == "completed":
                if approval.action.name == "create":
                    self.is_active = True
                    self.payment_status = "approved"
                    self.save(
                        update_fields=[
                            "is_active",
                            "payment_status",
                        ]
                    )
                    self._process_initial_journal_entries()

                elif approval.action.name == "delete":
                    if self.invoice_id:
                        raise validation_error(
                            "A transferred Sales Order payment cannot be deleted."
                        )

                    self.payment_status = "cancelled"
                    self.save(
                        update_fields=[
                            "payment_status",
                        ]
                    )
                    self.delete()

            elif approval.status == "rejected":
                self.payment_status = "cancelled"
                self.is_active = False
                self.deleted_at = timezone.now()
                self.save(
                    update_fields=[
                        "payment_status",
                        "is_active",
                        "deleted_at",
                    ]
                )

    @transaction.atomic
    def _process_initial_journal_entries(self):
        from accounts.utils import get_or_create_default_account
        from transactions.services import JournalLine, JournalPostingService

        if self.are_initial_journal_entries_made:
            return

        payment = (
            CustomerPurchaseOrderPayment.objects.select_for_update()
            .select_related("sales_order", "account")
            .get(pk=self.pk)
        )

        institution = self.get_institution()
        amount = self.amount_paid

        payment.account._update_cash_account_balance(amount)

        document_currency, document_rate = (
            payment.sales_order.determine_rate_currency_used()
        )
        account_currency = (
            None if document_currency == institution.currency else document_currency
        )

        advance_liability = get_or_create_default_account(
            institution,
            "misc_liability_account",
            account_currency,
        )
        cash_account = self.account

        journal_lines = [
            JournalLine(
                account=cash_account,
                entry_type="debit",
                transaction_amount=amount,
                transaction_currency=document_currency,
                exchange_rate=document_rate,
                description=(
                    f"Cash received for Sales Order "
                    f"{payment.sales_order.reference_code}"
                ),
            ),
            JournalLine(
                account=advance_liability,
                entry_type="credit",
                transaction_amount=amount,
                transaction_currency=document_currency,
                exchange_rate=document_rate,
                description=(
                    f"Customer deposit received for Sales Order "
                    f"{payment.sales_order.reference_code}"
                ),
            ),
        ]

        transaction_record, _ = JournalPostingService.post(
            fiscal_year=get_fiscal_year(
                institution,
                payment.payment_date,
            ),
            title=f"Sales Order payment {payment.reference_code}",
            description=(
                f"Payment received for Sales Order "
                f"{payment.sales_order.reference_code}"
            ),
            transaction_date=payment.payment_date,
            lines=journal_lines,
            branch=payment.sales_order.branch,
            content_type=ContentType.objects.get_for_model(
                CustomerPurchaseOrderPayment,
                for_concrete_model=False,
            ),
            object_id=payment.pk,
            source=payment.sales_order,
        )

        payment.payment_status = "approved"
        payment.are_initial_journal_entries_made = True
        payment.save(
            update_fields=[
                "payment_status",
                "are_initial_journal_entries_made",
            ]
        )

        return transaction_record


class CustomerBalanceAdjustment(SoftDeletableTimeStampedModel):
    reference_prefix = "CBA"

    BALANCE_ADJUSTED_CHOICES = [
        ("OUTSTANDING_RECEIVABLE_BALANCE", "Outstanding Receivable Balance"),
        ("DEPOSIT_BALANCE", "Deposit Balance"),
    ]

    customer = models.ForeignKey(
        Customer, on_delete=models.CASCADE, related_name="balance_adjustments"
    )
    balance_adjusted = models.CharField(
        max_length=150,
        choices=BALANCE_ADJUSTED_CHOICES,
        default="OUTSTANDING_RECEIVABLE_BALANCE",
    )
    adjustment_date = models.DateField(default=timezone.now)
    amount = models.DecimalField(max_digits=50, decimal_places=20)
    amount_before_adjustment = models.DecimalField(max_digits=50, decimal_places=20)
    amount_after_adjustment = models.DecimalField(max_digits=50, decimal_places=20)
    reason = models.CharField(max_length=255, blank=True, null=True)

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
        return f"{self.customer.customer_name}: {self.amount}"

    class Meta:
        verbose_name = "Customer Balance Adjustment"
        verbose_name_plural = "Customer Balance Adjustments"
        ordering = ["created_at"]


class CustomerDepositAllocation(SoftDeletableTimeStampedModel):
    reference_prefix = "CDA"

    prepayment = models.ForeignKey(
        "customers.CustomerPayment",
        on_delete=models.CASCADE,
        related_name="allocations",
        blank=True,
        null=True,
    )

    invoice = models.ForeignKey(
        "customers.Invoice", on_delete=models.CASCADE, related_name="allocations"
    )
    amount_applied = models.DecimalField(max_digits=50, decimal_places=20)

    class Meta:
        verbose_name = "Deposit Allocation"
        verbose_name_plural = "Deposit Allocations"
        ordering = ["-created_at"]

        constraints = [
            models.UniqueConstraint(
                fields=["prepayment", "invoice"],
                name="unique_active_prepayment_per_invoice",
                condition=models.Q(
                    deleted_at__isnull=True,
                    prepayment__isnull=False,
                ),
            )
        ]

    def __str__(self):
        return self.reference_code

    def clean(self):
        if not self.prepayment:
            raise validation_error("Prepayment is required")

    def save(self, *args, **kwargs):
        self.full_clean()
        super().save(*args, **kwargs)


class Invoice(ReportableModelMixin, BaseApprovableModel):
    reference_prefix = "C-INV"

    customer = models.ForeignKey(
        Customer,
        on_delete=models.CASCADE,
        null=True,
        blank=True,
    )
    quotation = models.ForeignKey(
        "customers.Quotation", on_delete=models.CASCADE, null=True, blank=True
    )
    purchase_order = models.ForeignKey(
        CustomerPurchaseOrder, on_delete=models.CASCADE, null=True, blank=True
    )

    currency = models.ForeignKey(
        "system.SystemCurrency",
        on_delete=models.PROTECT,
        related_name="customer_invoices",
        null=True,
        blank=True,
    )

    issue_date = models.DateField(default=timezone.now)

    due_date = models.DateField(blank=True, null=True)

    sales_person = models.ForeignKey(
        "customers.SalesPerson", on_delete=models.CASCADE, null=True, blank=True
    )

    invoice_status = models.CharField(
        max_length=100,
        choices=[
            ("not_sent", "Not Sent"),
            ("sent", "Sent"),
            ("canceled", "Canceled"),
        ],
        default="not_sent",
    )

    invoice_payment_status = models.CharField(
        max_length=100,
        choices=[
            ("unpaid", "Unpaid"),
            ("partially_paid", "Partially Paid"),
            ("paid", "Paid"),
        ],
        default="unpaid",
    )

    goods_issued_note_status = models.CharField(
        max_length=100,
        choices=[
            ("full_issued", "Full Issued"),
            ("not_issued", "Not Issued"),
            ("partially_issued", "Partially Issued"),
            ("not_required", "Not Required"),
        ],
        default="not_issued",
    )

    are_initial_journal_entries_made = models.BooleanField(default=False)

    is_originating_from_pos = models.BooleanField(
        default=False,
        help_text="Indicates whether this invoice was generated from a POS transaction.",
    )

    accounts_receivable_account = models.ForeignKey(
        "accounts.Account",
        on_delete=models.CASCADE,
        related_name="receivable_invoices",
        null=True,
        blank=True,
    )

    branch = models.ForeignKey(
        Branch,
        related_name="invoices",
        on_delete=models.CASCADE,
        null=True,
        blank=True,
    )

    total_amount = models.DecimalField(
        max_digits=50,
        decimal_places=20,
        default=0,
    )

    amount_due = models.DecimalField(
        max_digits=50,
        decimal_places=20,
        default=0,
    )

    partial_amount_paid = models.DecimalField(
        max_digits=50,
        decimal_places=20,
        default=Decimal("0.00"),
    )

    net_total = models.DecimalField(
        max_digits=50,
        decimal_places=20,
        default=Decimal("0.00"),
    )
    tax_total = models.DecimalField(
        max_digits=50,
        decimal_places=20,
        default=Decimal("0.00"),
    )
    gross_total = models.DecimalField(
        max_digits=50,
        decimal_places=20,
        default=Decimal("0.00"),
    )
    total_discount = models.DecimalField(
        max_digits=50,
        decimal_places=20,
        default=Decimal("0.00"),
    )

    credit_note_total = models.DecimalField(
        max_digits=50,
        decimal_places=20,
        default=Decimal("0.00"),
        help_text="Sum of all approved CREDIT note amounts against this invoice.",
    )
    debit_note_total = models.DecimalField(
        max_digits=50,
        decimal_places=20,
        default=Decimal("0.00"),
        help_text="Sum of all approved DEBIT note amounts against this invoice.",
    )
    adjusted_total = models.DecimalField(
        max_digits=50,
        decimal_places=20,
        default=Decimal("0.00"),
        help_text="Effective invoice total after credit/debit note adjustments.",
    )

    recurring_invoice = models.ForeignKey(
        "customers.RecurringInvoice", on_delete=models.CASCADE, null=True, blank=True
    )
    billing_start_date = models.DateField(blank=True, null=True)
    billing_end_date = models.DateField(blank=True, null=True)

    search_fields = [
        "customer__customer_name",
    ]
    ordering_fields = [
        "reference_code",
        "customer__customer_name",
        "issue_date",
        "due_date",
        "amount_due",
        "invoice_payment_status",
    ]
    filterset_fields = [
        *BaseApprovableModel.filterset_fields,
        "invoice_payment_status",
        "goods_issued_note_status",
        "customer__base_uuid",
        "currency_id",
    ]

    def get_invoice_customer(self):
        if self.customer:
            return self.customer

        if self.purchase_order:
            return self.purchase_order.get_purchase_order_customer()

        if self.recurring_invoice:
            return self.recurring_invoice.customer

        if self.quotation:
            return self.quotation.customer

        return None

    @classmethod
    def get_additional_filters(cls):
        return [
            "invoice_status",
            "is_active",
            "invoice_payment_status",
        ]

    @classmethod
    def get_excluded_report_fields(cls):
        return super().get_excluded_report_fields() + [
            "sales_person",
            "is_originating_from_pos",
        ]

    @classmethod
    def get_foreign_key_display_fields(cls):
        return {
            "customer": "customer_name",
            "branch": "branch_name",
            "sales_person": "name",
            "quotation": "reference_code",
            "purchase_order": "reference_code",
            "recurring_invoice": "reference_code",
            "currency": "code",
            "accounts_receivable_account": "account_name",
        }

    @classmethod
    def get_filter_serializer_class(cls):
        from customers.filters import InvoiceReportFilterSerializer

        return InvoiceReportFilterSerializer

    def __str__(self):
        return f"Invoice {self.reference_code} for {self.customer.customer_name if self.customer else 'No Customer'}"

    def clean(self):
        if self.due_date and self.due_date < self.issue_date:
            raise ValidationError("Due date must be after issue date.")
        if self.issue_date > date.today():
            raise ValidationError("Issue date cannot be in the future.")

        if self.amount_due > self.total_amount:
            raise ValidationError("Amount due cannot exceed total amount.")

        if self.amount_due < 0:
            raise ValidationError("Amount due cannot be negative.")

        if (
            self.invoice_payment_status == "unpaid"
            and self.amount_due != self.total_amount
        ):
            raise ValidationError(
                "Amount due must equal total amount if invoice is marked as unpaid."
            )

    def get_institution(self):
        return self.branch.institution

    def recompute_note_totals(self):

        from django.db.models import Sum

        approved_notes = CreditDebitNote.objects.filter(
            invoice=self,
            falls_under="SALES",
            status__in=["APPROVED", "RESOLVED"],
            is_active=True,
            deleted_at__isnull=True,
        )

        credit_total = approved_notes.filter(type="CREDIT").aggregate(t=Sum("amount"))[
            "t"
        ] or Decimal("0.00")
        debit_total = approved_notes.filter(type="DEBIT").aggregate(t=Sum("amount"))[
            "t"
        ] or Decimal("0.00")

        adjusted = (self.total_amount - credit_total + debit_total).quantize(
            Decimal("0.01")
        )
        adjusted = max(adjusted, Decimal("0.00"))

        total_paid = self._total_confirmed_payments()

        new_amount_due = max(adjusted - total_paid, Decimal("0.00"))

        Invoice.objects.filter(pk=self.pk).update(
            credit_note_total=credit_total,
            debit_note_total=debit_total,
            adjusted_total=adjusted,
            amount_due=new_amount_due,
        )
        self.refresh_from_db(
            fields=[
                "credit_note_total",
                "debit_note_total",
                "adjusted_total",
                "amount_due",
            ]
        )

        self._sync_payment_status()

    def _total_confirmed_payments(self) -> Decimal:
        return CustomerPayment.objects.filter(
            invoice=self,
            payment_status="APPROVED",
            is_active=True,
            deleted_at__isnull=True,
        ).aggregate(t=Sum("amount"))["t"] or Decimal("0.00")

    def _sync_payment_status(self):
        self.refresh_from_db(fields=["amount_due", "adjusted_total"])
        if self.adjusted_total == Decimal("0.00") or self.amount_due == Decimal("0.00"):
            new_status = "paid"
        elif self.amount_due < self.adjusted_total:
            new_status = "partially_paid"
        else:
            new_status = "unpaid"
        Invoice.objects.filter(pk=self.pk).update(invoice_payment_status=new_status)
        self.invoice_payment_status = new_status

    def get_all_tax_breakdowns(self):

        from django.contrib.contenttypes.models import ContentType

        line_item_ct = ContentType.objects.get_for_model(InvoiceLineItem)
        line_item_ids = self.line_items.values_list("id", flat=True)

        return TaxApplicationBreakDown.objects.filter(
            content_type=line_item_ct, object_id__in=line_item_ids
        )

    @classmethod
    def get_institution_filter_field(cls):
        return "customer__institution"

    def compute_totals(self):
        if self.are_initial_journal_entries_made and not self.line_items.exists():
            return

        from taxation.service import SalesLineDiscountService

        SalesLineDiscountService.recompute_document_totals_with_discounts(self)

        self.total_amount = self.gross_total
        self.amount_due = self.gross_total

        self.adjusted_total = self.total_amount
        self.credit_note_total = Decimal("0.00")
        self.debit_note_total = Decimal("0.00")

        self.save(
            update_fields=[
                "net_total",
                "tax_total",
                "gross_total",
                "total_discount",
                "total_amount",
                "amount_due",
                "adjusted_total",
                "credit_note_total",
                "debit_note_total",
            ]
        )

    def _handle_commission(self):
        if self.sales_person:
            commission_exists = SalesPersonCommissionEntry.objects.filter(
                sales_person=self.sales_person,
                invoice=self,
            ).exists()

            if (
                self.invoice_payment_status != "paid"
                or not self.sales_person
                or commission_exists
            ):
                return

            institution = self.get_institution()

            is_commission_enabled = institution.is_sales_person_commission_enabled

            if is_commission_enabled is False:
                return

            commission_rate = institution.commission_percentage

            if commission_rate is not None and commission_rate > 0:

                commission_amount = self.total_amount * (commission_rate / Decimal(100))

                SalesPersonCommissionEntry.objects.create(
                    sales_person=self.sales_person,
                    amount=commission_amount,
                    commission="earnings",
                    invoice=self,
                )

    class Meta:
        verbose_name = "Invoice"
        verbose_name_plural = "Invoices"
        ordering = ["-created_at", "-issue_date"]

        constraints = [
            models.UniqueConstraint(
                fields=["recurring_invoice", "billing_start_date", "billing_end_date"],
                name="unique_billing_period_per_recurring_invoice",
                condition=Q(
                    recurring_invoice__isnull=False,
                    billing_start_date__isnull=False,
                    billing_end_date__isnull=False,
                ),
            )
        ]

        indexes = [
            models.Index(fields=["billing_start_date"]),
            models.Index(fields=["billing_end_date"]),
        ]

    def save(self, *args, **kwargs):

        self.full_clean()

        super().save(*args, **kwargs)

        if self.purchase_order and self.purchase_order.status == "approved":
            self.purchase_order.update_purchase_order_status_on_sent_invoice()

        # TODO Improve to only call commission only if theres a transisition from one payment to paid or saved as paid
        if self.invoice_payment_status == "paid":
            self._handle_commission()

    def finish_workflow(self, approval: Approval):
        from django.db import transaction
        from procurement.back_order_automation import (
            sync_invoice_fulfillment_status,
            sync_cpo_fulfillment_status,
        )

        with transaction.atomic():
            if approval.status == "completed":
                if approval.action.name in ["create", "update"]:
                    self.is_active = True
                    self.invoice_status = "sent"
                    self.approval_status = "active"
                    self.save(
                        update_fields=["approval_status", "is_active", "invoice_status"]
                    )

                    if self.purchase_order_id:
                        from customers.order_payments import (
                            transfer_sales_order_payments_to_invoice,
                        )

                        transfer_sales_order_payments_to_invoice(self)
                        self.refresh_from_db(
                            fields=[
                                "amount_due",
                                "invoice_payment_status",
                            ]
                        )

                    if not self.are_initial_journal_entries_made:
                        self._process_financial_events()

                        sync_invoice_fulfillment_status(self)
                        sync_cpo_fulfillment_status(self)

                        institution = self.get_institution()

                        from customers.services import (
                            AutoGINCreationService,
                            SalesInventoryAccountingService,
                        )

                        AutoGINCreationService.start(
                            source=self,
                            source_approval=approval,
                            inventory_reduction_timing=(
                                institution.inventory_reduction_timing
                            ),
                        )

                        SalesInventoryAccountingService.recognize_for_invoice(self)

                        # Automatic GIN approval synchronizes this value through
                        # a separate Invoice instance. Refresh it before the final
                        # save below so this stale instance cannot overwrite the
                        # synchronized status.
                        self.refresh_from_db(fields=["goods_issued_note_status"])

                elif approval.action.name == "delete":
                    self.is_active = False
                    self.deleted_at = timezone.now()
                    self.invoice_status = "canceled"

            elif approval.status == "rejected":
                if approval.action.name in ["create", "update"]:
                    self.is_active = False
                    self.deleted_at = timezone.now()
                    self.invoice_status = "not_sent"

                elif approval.action.name in ["update", "delete"]:
                    self.is_active = False
                    self.deleted_at = None
                    self.invoice_status = "not_sent"

        self.save()

    @transaction.atomic
    def _process_financial_events(self):
        from accounts.utils import get_or_create_default_account
        from transactions.services import JournalLine, JournalPostingService
        from taxation.service import SalesLineDiscountService

        if self.are_initial_journal_entries_made:
            return None

        institution = self.get_institution()
        fiscal_year = get_fiscal_year(institution, date=self.issue_date)
        invoice_customer = self.get_invoice_customer()
        document_currency, _ = self.determine_rate_currency_used()
        account_currency = (
            None if document_currency == institution.currency else document_currency
        )

        account_receivable = (
            self.accounts_receivable_account
            or get_or_create_default_account(
                institution,
                "receivable_account",
                account_currency,
            )
        )

        journal_lines = [
            JournalLine(
                account=account_receivable,
                entry_type="debit",
                transaction_amount=self.total_amount,
                transaction_currency=document_currency,
                description=f"Accounts receivable for invoice {self.reference_code}",
            )
        ]

        total_discount_expense = Decimal("0.00")

        for item in self.line_items.select_related("line_item__inventory_item").all():
            inventory_item = item.line_item.inventory_item

            revenue_account = (
                inventory_item.revenue_account
                or get_or_create_default_account(institution, "income_account", None)
            )

            accounting = SalesLineDiscountService.get_line_accounting(item)
            total_discount_expense += accounting["discount_expense"]

            if accounting["original_net"] > 0:
                journal_lines.append(
                    JournalLine(
                        account=revenue_account,
                        entry_type="credit",
                        transaction_amount=accounting["original_net"],
                        transaction_currency=document_currency,
                        description=f"Revenue for {inventory_item.item_name}",
                    )
                )

        if total_discount_expense > 0:
            discount_expense_account = get_or_create_default_account(
                institution, "sales_discount_expense_account", account_currency
            )
            journal_lines.append(
                JournalLine(
                    account=discount_expense_account,
                    entry_type="debit",
                    transaction_amount=total_discount_expense,
                    transaction_currency=document_currency,
                    description=f"Sales discounts for invoice {self.reference_code}",
                )
            )

        for tb in self.get_all_tax_breakdowns():
            tax_account = tb.tax.tax_account or get_or_create_default_account(
                institution, "vat_controlled_account", None
            )

            if tb.tax_amount > 0:
                journal_lines.append(
                    JournalLine(
                        account=tax_account,
                        entry_type="credit",
                        transaction_amount=tb.tax_amount,
                        transaction_currency=document_currency,
                        description=f"{tb.tax.tax_name} payable",
                    )
                )

        txn, _ = JournalPostingService.post(
            fiscal_year=fiscal_year,
            title=f"Invoice {self.reference_code}",
            description=(
                f"Invoice issued to "
                f"{invoice_customer.customer_name if invoice_customer else 'unknown customer'}"
            ),
            transaction_date=self.issue_date,
            lines=journal_lines,
            branch=self.branch,
            content_type=ContentType.objects.get_for_model(
                self.__class__,
                for_concrete_model=False,
            ),
            object_id=self.id,
            source=self,
        )

        Invoice.objects.filter(pk=self.pk).update(
            accounts_receivable_account=account_receivable,
            are_initial_journal_entries_made=True,
        )
        self.refresh_from_db(
            fields=["accounts_receivable_account", "are_initial_journal_entries_made"]
        )

        if invoice_customer is not None:
            invoice_customer.outstanding_receivables_balance += self.amount_due
            invoice_customer.save(
                update_fields=["outstanding_receivables_balance"],
                outstanding_receivables_balance_change_reason="Invoice created",
            )

        return txn

    @transaction.atomic()
    def apply_taxation(self):
        if self.are_initial_journal_entries_made and not self.line_items.exists():
            return []

        from taxation.service import SalesDocumentTaxService

        breakdowns = []

        for item in self.line_items.all():
            breakdowns.extend(
                SalesDocumentTaxService.apply_line_taxes(
                    line=item,
                )
            )

        return breakdowns

    def determine_rate_currency_used(self):
        from system.services import FxRateService

        institution = self.get_institution()

        if self.currency_id:
            document_currency = self.currency
            rate_source = self
        elif self.purchase_order_id:
            document_currency, _ = self.purchase_order.determine_rate_currency_used()
            rate_source = self.purchase_order
        elif self.quotation_id:
            document_currency, _ = self.quotation.determine_rate_currency_used()
            rate_source = self.quotation
        else:
            document_currency = institution.currency
            rate_source = self

        rate = FxRateService.resolve_base_rate(
            institution=institution,
            currency=document_currency,
            source=rate_source,
        )
        return document_currency, rate

    def send_invoice_email(self):
        if (
            self.get_invoice_customer() is None
            or self.get_institution().institution_email is None
        ):
            return

        customer = self.get_invoice_customer()

        if customer.email is None:
            return

        subject = f"Invoice #{self.reference_code} from {self.branch.institution.institution_name}"

        context = {
            "reference_code": self.reference_code,
            "institution_name": self.get_institution().institution_name,
            "institution_email": self.get_institution().institution_email,
            "date": self.issue_date.strftime("%B %d, %Y"),
            "salutation_line": f"Dear {customer.get_gender_and_name()}",
            "customer_name": customer.customer_name,
            "customer_email": customer.email,
            "customer_address": customer.address,
            "line_items": [
                {
                    "name": item.line_item.inventory_item.item_name,
                    "quantity": item.quantity,
                    "unit_price": f"{item.unit_price:.2f}",
                    "line_total": f"{item.line_total:.2f}",
                }
                for item in self.line_items.all()
            ],
            "net_total": f"{self.net_total:.2f}",
            "tax_total": f"{self.tax_total:.2f}",
            "gross_total": f"{self.gross_total:.2f}",
            "total_amount": f"{self.total_amount:.2f}",
            "due_date": self.due_date.strftime("%B %d, %Y"),
        }

        reciepients_lists = [customer.email]

        institution_email = (
            (self.branch.branch_email or self.branch.institution.institution_email)
            if self.branch.institution.are_notifications_enabled
            else None
        )

        if institution_email:
            reciepients_lists.append(institution_email)

        EmailClient.send(
            subject=subject,
            recipients=reciepients_lists,
            template_html="emails/invoice_email.html",
            context=context,
        )

    def intiate_payment(self, payment_account):
        from django.contrib.contenttypes.models import ContentType
        from .serializers import CustomerPaymentSerializer

        if self.invoice_payment_status not in ["paid", "partially_paid"]:
            return

        if (
            not payment_account
            or "content_type" not in payment_account
            or "content_object_uuid" not in payment_account
        ):
            raise ValidationError(
                "A cash account must be provided when an invoice is paid or partially paid."
            )

        if self.invoice_payment_status == "paid":
            paid_amount = self.total_amount
        else:
            paid_amount = self.partial_amount_paid

        if paid_amount <= 0:
            return

        content_type = ContentType.objects.get(pk=payment_account["content_type"])
        cash_object = content_type.get_object_for_this_type(
            base_uuid=payment_account["content_object_uuid"]
        )
        coa_account = cash_object.get_chart_of_account_reference()

        if not coa_account:
            raise ValidationError(
                "The selected cash account is not linked to a chart of account "
                "and cannot be used to record payment."
            )

        payload = {
            "invoice": str(self.base_uuid),
            "amount": str(paid_amount),
            "payment_date": self.issue_date,
            "coa_cash_account": str(coa_account.base_uuid),
            "description": "Auto-generated payment on invoice creation",
        }

        invoice_currency, invoice_rate = self.determine_rate_currency_used()
        institution_currency = self.get_institution().currency

        if invoice_currency != institution_currency:
            payload["payment_exchange_rate"] = {
                "one_side": {
                    "currency": invoice_currency.pk,
                    "value": "1",
                },
                "other_side": {
                    "currency": institution_currency.pk,
                    "value": str(invoice_rate),
                },
            }

        serializer = CustomerPaymentSerializer(data=payload)
        serializer.is_valid(raise_exception=True)
        customer_payment = serializer.save(
            created_by=self.created_by,
            updated_by=self.created_by,
        )
        customer_payment.confirm_create()

    @transaction.atomic
    def _auto_create_gin(self, inventory_reduction_timing):

        if not inventory_reduction_timing:
            raise validation_error(
                "Inventory Reduction Timing is not set for this institution and can't proceed."
            )

        if self.goods_issued_notes.filter(
            is_automated=True, is_active=True, deleted_at__isnull=True
        ).exists():
            return None

        goods_lines = self.line_items.filter(
            line_item__inventory_item__item_type="GOODS",
            deleted_at__isnull=True,
        ).select_related("line_item", "unit_of_measure")

        if not goods_lines.exists():
            self.goods_issued_note_status = "not_required"
            self.save(update_fields=["goods_issued_note_status"])
            return None

        line_items_payload = []

        from .serializers import GoodsIssuedNoteSerializer

        for item in goods_lines:
            line_items_payload.append(
                {
                    "line_item": item.line_item.base_uuid,
                    "unit_of_measure": item.unit_of_measure.base_uuid,
                    "quantity": item.quantity,
                }
            )

        payload = {
            "invoice": self.base_uuid,
            "branch": self.branch.id,
            "is_automated": True,
            "line_items": line_items_payload,
        }

        gin_serializer = GoodsIssuedNoteSerializer(
            data=payload,
            context={
                "institution": self.get_institution(),
            },
        )

        gin_serializer.is_valid(raise_exception=True)
        gin = gin_serializer.save()

        if inventory_reduction_timing == "ON_INVOICE":
            gin.status = "pending"
        else:
            gin.status = "draft"

        GoodsIssuedNote.objects.filter(pk=gin.pk).update(status=gin.status)

        gin.confirm_create()

        gin._sync_fulfilment_after_approval()

        return gin


class InvoiceLineItem(SoftDeletableTimeStampedModel):
    reference_prefix = "INV-L"

    invoice = models.ForeignKey(
        Invoice, on_delete=models.CASCADE, related_name="line_items"
    )
    source_purchase_order_line = models.ForeignKey(
        CustomerPurchaseOrderLineItem,
        on_delete=models.SET_NULL,
        related_name="invoice_lines",
        null=True,
        blank=True,
    )
    source_quotation_line = models.ForeignKey(
        QuotationLineItem,
        on_delete=models.SET_NULL,
        related_name="invoice_lines",
        null=True,
        blank=True,
    )
    line_item = models.ForeignKey(
        "items.BranchInventoryItem", on_delete=models.CASCADE, null=True, blank=True
    )
    unit_of_measure = models.ForeignKey(
        "items.BranchInventoryItemUnitOfMeasure",
        on_delete=models.CASCADE,
        null=True,
        blank=True,
    )
    quantity = models.PositiveIntegerField(default=1)
    unit_price = models.DecimalField(max_digits=50, decimal_places=20, default=0.00)
    line_total = models.DecimalField(max_digits=50, decimal_places=20, default=0.00)

    tax_breakdowns = GenericRelation(
        TaxApplicationBreakDown,
        content_type_field="content_type",
        object_id_field="object_id",
        related_query_name="invoice_line_items",
    )
    discounts = GenericRelation(
        "SalesLineDiscount",
        content_type_field="content_type",
        object_id_field="object_id",
        related_query_name="invoice_line_items",
    )

    quantity_ordered = models.PositiveIntegerField(
        default=0,
        help_text="Total quantity of GOODS line items on this invoice (ordered by customer).",
    )
    quantity_issued = models.PositiveIntegerField(
        default=0,
        help_text="Total quantity issued to the customer across all approved GINs.",
    )
    quantity_pending = models.PositiveIntegerField(
        default=0,
        help_text="Remaining quantity yet to be issued (quantity_ordered - quantity_issued).",
    )

    search_fields = [
        "line_item__inventory_item__item_name",
        "line_item__inventory_item__reference_code",
    ]

    ordering_fields = [
        "created_at",
        "updated_at",
        "reference_code",
        "quantity",
        "unit_price",
        "line_total",
        "line_item__inventory_item__item_name",
    ]

    def __str__(self):
        return f"Line item for {self.invoice.reference_code}"

    def get_tax_breakdowns(self):
        return self.tax_breakdowns.all()

    def get_discounts(self):
        return self.discounts.filter(deleted_at__isnull=True).order_by("position")

    class Meta:
        verbose_name = "Invoice Line Item"
        verbose_name_plural = "Invoice Line Items"
        ordering = ["created_at"]

        indexes = [
            models.Index(fields=["line_item", "invoice"], name="idx_invlineitem_item"),
        ]


class RecurringInvoice(ReportableModelMixin, BaseApprovableModel):

    class Frequency(models.TextChoices):
        DAILY = "daily", "Daily"
        WEEKLY = "weekly", "Weekly"
        MONTHLY = "monthly", "Monthly"
        BI_ANNUALLY = "bi-annually", "Bi-Annually"
        ANNUALLY = "annually", "Annually"

    reference_prefix = "R-INV"

    STATUS_CHOICES = [
        ("pending_approval", "Pending"),
        ("approved", "Approved"),
        ("cancelled", "Cancelled"),
    ]

    branch = models.ForeignKey(
        "institution.Branch",
        related_name="recurring_invoices",
        on_delete=models.CASCADE,
        null=True,
        blank=True,
    )

    customer = models.ForeignKey(
        Customer,
        on_delete=models.CASCADE,
        related_name="customers",
    )

    recurring_frequency = models.CharField(
        max_length=20,
        choices=Frequency.choices,
        default=Frequency.MONTHLY,
    )

    status = models.CharField(
        max_length=20,
        choices=STATUS_CHOICES,
        default="pending_approval",
    )

    start_date = models.DateField(default=timezone.now)

    end_date = models.DateField(null=True, blank=True)

    next_recurring_date = models.DateField(null=True, blank=True, db_index=True)

    should_always_use_template_price = models.BooleanField(
        default=False,
        help_text="If enabled, the recurring invoice will always use the template's unit cost for line items, regardless of any changes in the inventory item's price.",
    )

    def clean(self):
        super().clean()

        errors = {}

        if not self.branch_id:
            errors["branch"] = "Branch is required."

        if self.start_date and self.end_date and self.end_date < self.start_date:
            errors["end_date"] = "End date cannot be earlier than start date."

        if (
            self.branch_id
            and self.customer_id
            and self.branch.institution_id != self.customer.institution_id
        ):
            errors["branch"] = (
                "Branch and customer must belong to the same institution."
            )

        if self.pk:
            schedule = RecurringInvoiceSchedule.objects.filter(
                recurring_invoice_id=self.pk
            ).first()

            if schedule:
                schedule.recurring_invoice = self
                try:
                    schedule.clean()
                except ValidationError as exc:
                    errors["schedule"] = getattr(exc, "message_dict", exc.messages)

        if errors:
            raise ValidationError(errors)

    def advance_next_date(self):
        if not self.next_recurring_date:
            return

        schedule = getattr(self, "schedule", None)

        has_specific_config = schedule and (
            schedule.days_of_week
            or schedule.days_of_month
            or schedule.weeks_of_month
            or schedule.months_of_year
        )

        if not has_specific_config:
            if self.recurring_frequency == self.Frequency.DAILY:
                delta = relativedelta(days=1)
            elif self.recurring_frequency == self.Frequency.WEEKLY:
                delta = relativedelta(weeks=1)
            elif self.recurring_frequency == self.Frequency.MONTHLY:
                delta = relativedelta(months=1)
            elif self.recurring_frequency == self.Frequency.BI_ANNUALLY:
                delta = relativedelta(months=6)
            elif self.recurring_frequency == self.Frequency.ANNUALLY:
                delta = relativedelta(years=1)
            else:
                raise validation_error("Invalid Invoice Recurrence frequency")

            self.next_recurring_date += delta
            return

        current_date = self.next_recurring_date
        next_date = None

        if self.recurring_frequency == self.Frequency.DAILY and schedule.days_of_week:
            target_weekdays = sorted([int(d) for d in schedule.days_of_week])
            for i in range(1, 8):
                potential_date = current_date + timedelta(days=i)
                if potential_date.weekday() in target_weekdays:
                    next_date = potential_date
                    break

        elif (
            self.recurring_frequency == self.Frequency.MONTHLY
            and schedule.days_of_month
        ):
            target_days = sorted([int(d) for d in schedule.days_of_month])

            for d in target_days:
                if d > current_date.day:
                    try:
                        next_date = current_date.replace(day=d)
                        break
                    except ValueError:
                        continue

            if not next_date:
                search_date = current_date
                for _ in range(12):
                    search_date += relativedelta(months=1)
                    search_date = search_date.replace(day=1)
                    for d in target_days:
                        try:
                            next_date = search_date.replace(day=d)
                            break
                        except ValueError:
                            continue
                    if next_date:
                        break

        elif (
            self.recurring_frequency == self.Frequency.ANNUALLY
            and schedule.months_of_year
        ):
            target_months = sorted([int(m) for m in schedule.months_of_year])
            target_days = (
                sorted([int(d) for d in schedule.days_of_month])
                if schedule.days_of_month
                else [current_date.day]
            )

            search_date = current_date
            for _ in range(24):
                search_date += relativedelta(months=1)
                if search_date.month in target_months:
                    for d in target_days:
                        try:
                            temp_date = search_date.replace(day=d)
                            if temp_date > current_date:
                                next_date = temp_date
                                break
                        except ValueError:
                            continue
                if next_date:
                    break

        if next_date:
            self.next_recurring_date = next_date
        else:

            delta = relativedelta(months=1)
            self.next_recurring_date += delta

    def __str__(self):
        return (
            f"Recurring Invoice {self.reference_code} for {self.customer.customer_name}"
        )

    def save(self, *args, **kwargs):
        is_new = self._state.adding
        if not self.next_recurring_date and self.start_date:
            self.next_recurring_date = self.start_date

        self.full_clean()
        super().save(*args, **kwargs)

        if is_new:
            self._create_invoice_schedule()

    def _create_invoice_schedule(self):
        RecurringInvoiceSchedule.objects.get_or_create(recurring_invoice=self)

    def get_institution(self):
        return self.customer.get_institution()

    def finish_workflow(self, approval: Approval):
        with transaction.atomic():
            if approval.status == "completed":
                if approval.action.name in ["create", "update"]:
                    self.is_active = True
                    self.status = "approved"

                elif approval.action.name == "delete":
                    self.delete()
                    self.status = "cancelled"

            elif approval.status == "rejected":
                if approval.action.name == "create":
                    self.is_active = False
                    self.deleted_at = None

                elif approval.action.name in ["update", "delete"]:
                    self.is_active = False
                    self.deleted_at = None

        self.save()

    def has_reached_occurrence_limit(self):
        schedule = getattr(self, "schedule", None)

        if not schedule or not schedule.interval:
            return False

        generated_occurrences = Invoice.objects.filter(recurring_invoice=self).count()

        return generated_occurrences >= schedule.interval

    def create_invoice_for_recurring_invoice(self):
        from .serializers import InvoiceSerializer

        with transaction.atomic():

            recurring_invoice = (
                RecurringInvoice.objects.select_for_update()
                .select_related("customer")
                .prefetch_related("recurring_items")
                .get(pk=self.pk)
            )

            if recurring_invoice.has_reached_occurrence_limit():
                return None

            due_date_anchor = (
                recurring_invoice.next_recurring_date or recurring_invoice.start_date
            )

            if not due_date_anchor:
                raise validation_error(
                    "Cannot generate invoice: Recurring invoice must have a start date or next recurring date."
                )

            exists = Invoice.objects.filter(
                recurring_invoice=recurring_invoice,
                billing_start_date=due_date_anchor,
            ).exists()

            if exists:
                print(
                    "Invoice for this billing period already exists. Skipping generation."
                )
                return None

            line_items_data = []

            for item in recurring_invoice.recurring_items.all():

                data = {
                    "line_item": item.line_item_id,
                    "unit_of_measure": item.unit_of_measure.base_uuid,
                    "quantity": item.quantity,
                }

                if recurring_invoice.should_always_use_template_price:
                    data["unit_price"] = item.unit_cost

                if item.description:
                    data["description"] = item.description

                line_items_data.append(data)

            if not line_items_data:
                print("No line items found for recurring invoice. Skipping generation.")
                return None

            payload = {
                "recurring_invoice": recurring_invoice.id,
                "line_items": line_items_data,
                "description": f"Invoice automatically generated from recurring invoice template {recurring_invoice.reference_code}",
                "billing_start_date": due_date_anchor,
                "customer": recurring_invoice.customer_id,
                "branch": (
                    recurring_invoice.branch_id if recurring_invoice.branch else None
                ),
                "issue_date": due_date_anchor,
            }

            class MockRequest:
                def __init__(self, user):
                    self.user = user

            serializer = InvoiceSerializer(
                data=payload,
                context={
                    "request": MockRequest(recurring_invoice.created_by),
                    "institution": recurring_invoice.customer.institution,
                },
            )
            serializer.is_valid(raise_exception=True)

            invoice = serializer.save()

            invoice.confirm_create()

            return invoice


class RecurringInvoiceSchedule(ReportableModelMixin, BaseApprovableModel):
    recurring_invoice = models.OneToOneField(
        "RecurringInvoice",
        on_delete=models.CASCADE,
        related_name="schedule",
    )

    interval = models.PositiveIntegerField(
        default=1,
        help_text="Maximum number of invoices to generate for this recurring invoice.",
    )

    days_of_week = models.JSONField(
        null=True,
        blank=True,
        help_text="List of weekdays (0-6, where 0 is Monday).",
    )

    days_of_month = models.JSONField(
        null=True,
        blank=True,
        help_text="List of days of the month (1-31).",
    )

    weeks_of_month = models.JSONField(
        null=True,
        blank=True,
        help_text="List of weeks of the month (1-4, where 1 is the first week).",
    )

    months_of_year = models.JSONField(
        null=True,
        blank=True,
        help_text="List of months of the year (1-12).",
    )

    additional_notes = models.TextField(blank=True, null=True)

    def __str__(self):
        return f"Schedule for {self.recurring_invoice}"

    def get_institution(self):
        return self.recurring_invoice.get_institution()

    class Meta:
        verbose_name = "Recurring Invoice Schedule"
        verbose_name_plural = "Recurring Invoice Schedules"

    @staticmethod
    def _validate_integer_list(field_name, values, minimum, maximum, errors):
        if values is None:
            return

        if not isinstance(values, list):
            errors[field_name] = "Must be a list of integers."
            return

        if any(type(value) is not int for value in values):
            errors[field_name] = "Every value must be an integer."
            return

        if any(value < minimum or value > maximum for value in values):
            errors[field_name] = f"Values must be between {minimum} and {maximum}."
            return

        if len(values) != len(set(values)):
            errors[field_name] = "Duplicate values are not allowed."

    def clean(self):
        super().clean()

        errors = {}

        if self.interval is None or self.interval < 1:
            errors["interval"] = "Interval must be at least 1."

        self._validate_integer_list("days_of_week", self.days_of_week, 0, 6, errors)
        self._validate_integer_list("days_of_month", self.days_of_month, 1, 31, errors)
        self._validate_integer_list("weeks_of_month", self.weeks_of_month, 1, 4, errors)
        self._validate_integer_list(
            "months_of_year", self.months_of_year, 1, 12, errors
        )

        frequency = (
            self.recurring_invoice.recurring_frequency
            if self.recurring_invoice_id
            else None
        )

        if self.days_of_week and frequency != RecurringInvoice.Frequency.DAILY:
            errors["days_of_week"] = (
                "Days of the week can only be set for daily recurring invoices."
            )

        if self.days_of_month and frequency != RecurringInvoice.Frequency.MONTHLY:
            errors["days_of_month"] = (
                "Days of the month can only be set for monthly recurring invoices."
            )

        if self.weeks_of_month and frequency != RecurringInvoice.Frequency.WEEKLY:
            errors["weeks_of_month"] = (
                "Weeks of the month can only be set for weekly recurring invoices."
            )

        if self.months_of_year and frequency != RecurringInvoice.Frequency.MONTHLY:
            errors["months_of_year"] = (
                "Months of the year can only be set for monthly recurring invoices."
            )

        if errors:
            raise ValidationError(errors)

    def save(self, *args, **kwargs):
        self.full_clean()
        super().save(*args, **kwargs)


class RecurringInvoiceItem(BaseTimeStamp):
    recurring_invoice = models.ForeignKey(
        RecurringInvoice, on_delete=models.CASCADE, related_name="recurring_items"
    )

    line_item = models.ForeignKey(
        "items.InventoryItem",
        on_delete=models.CASCADE,
        null=True,
        blank=True,
        related_name="recurring_invoice_items",
    )

    unit_of_measure = models.ForeignKey(
        "items.InventoryItemUnitOfMeasure",
        on_delete=models.CASCADE,
        null=True,
        blank=True,
        related_name="recurring_invoice_items",
    )

    quantity = models.DecimalField(max_digits=50, decimal_places=20)
    unit_cost = models.DecimalField(max_digits=50, decimal_places=20)

    @property
    def line_total(self):
        return self.quantity * self.unit_cost

    def clean(self):
        super().clean()

        errors = {}

        if not self.line_item_id:
            errors["line_item"] = "Line item is required."

        if not self.unit_of_measure_id:
            errors["unit_of_measure"] = "Unit of measure is required."

        if self.quantity is None or self.quantity <= 0:
            errors["quantity"] = "Quantity must be greater than zero."

        if self.unit_cost is None or self.unit_cost < 0:
            errors["unit_cost"] = "Unit cost cannot be negative."

        if (
            self.line_item_id
            and self.unit_of_measure_id
            and self.unit_of_measure.inventory_item_id != self.line_item_id
        ):
            errors["unit_of_measure"] = (
                "Unit of measure must belong to the selected inventory item."
            )

        if (
            self.recurring_invoice_id
            and self.line_item_id
            and self.recurring_invoice.customer.institution_id
            != self.line_item.institution_id
        ):
            errors["line_item"] = (
                "Inventory item and recurring invoice must belong to the same institution."
            )

        if errors:
            raise ValidationError(errors)

    def save(self, *args, **kwargs):
        self.full_clean()
        super().save(*args, **kwargs)

    def get_institution(self):
        return self.recurring_invoice.get_institution()


class PaymentTerm(ReportableModelMixin, BaseApprovableModel):
    reference_prefix = "PAY-TERM"
    institution = models.ForeignKey(
        "institution.Institution",
        on_delete=models.CASCADE,
        related_name="terms",
    )
    term_name = models.CharField(max_length=100)
    days_until_due = models.PositiveIntegerField(default=30)

    is_default = models.BooleanField(default=False)

    search_fields = [
        "term_name",
        "days_until_due",
    ]

    ordering_fields = [
        "term_name",
        "days_until_due",
        "created_at",
    ]

    filterset_fields = [
        "created_by__base_uuid",
    ]

    def __str__(self):
        return self.term_name

    def get_institution(self):
        return self.institution

    def finish_workflow(self, approval: Approval):
        with transaction.atomic():
            if approval.status == "completed":
                if approval.action.name in ["create", "update"]:
                    self.is_active = True
                elif approval.action.name == "delete":
                    self.delete()
            elif approval.status == "rejected":
                if approval.action.name == "create":
                    self.is_active = False
                elif approval.action.name in ["update", "delete"]:
                    self.is_active = False
                    self.deleted_at = None

        self.save()

    class Meta:
        verbose_name = "Payment Term"
        verbose_name_plural = "Payment Terms"
        constraints = [
            models.UniqueConstraint(
                fields=["institution", "term_name", "days_until_due"],
                condition=models.Q(deleted_at__isnull=True),
                name="uniq_active_payment_term",
            ),
            models.UniqueConstraint(
                fields=["institution"],
                condition=models.Q(is_default=True, deleted_at__isnull=True),
                name="uniq_default_payment_term",
            ),
        ]


class CustomerPayment(ReportableModelMixin, BaseApprovableModel):
    reference_prefix = "C-PAY"

    PAYMENT_STATUS_CHOICES = [
        ("DRAFT", "Draft"),
        ("APPROVED", "Approved"),
        ("CANCELLED", "Cancelled"),
        ("FAILED", "Failed"),
        ("REVERSED", "Reversed"),
        ("PENDING", "Pending"),
    ]

    institution = models.ForeignKey(
        "institution.Institution",
        on_delete=models.CASCADE,
        related_name="customer_payments",
    )

    branch = models.ForeignKey(
        "institution.Branch",
        on_delete=models.CASCADE,
        related_name="payments",
        blank=True,
        null=True,
    )

    customer = models.ForeignKey(
        "customers.Customer",
        on_delete=models.SET_NULL,
        blank=True,
        null=True,
        related_name="payments",
    )

    currency = models.ForeignKey(
        "system.SystemCurrency",
        on_delete=models.PROTECT,
        related_name="customer_payment_documents",
        null=True,
        blank=True,
    )

    settlement_currency = models.ForeignKey(
        "system.SystemCurrency",
        on_delete=models.PROTECT,
        related_name="customer_payment_settlements",
        null=True,
        blank=True,
        help_text=("Customer or invoice currency in which balances are settled."),
    )

    invoice = models.ForeignKey(
        Invoice,
        on_delete=models.CASCADE,
        related_name="customer_payments",
        blank=True,
        null=True,
    )

    originating_payment = models.ForeignKey(
        "self",
        on_delete=models.CASCADE,
        null=True,
        blank=True,
        related_name="generated_prepayments",
    )

    amount = models.DecimalField(max_digits=50, decimal_places=20, default=0.00)

    settlement_amount = models.DecimalField(
        max_digits=50,
        decimal_places=20,
        default=Decimal("0.00"),
        help_text=(
            "Amount credited to the customer deposit or applied to the "
            "invoice, expressed in settlement_currency."
        ),
    )

    payment_status = models.CharField(
        max_length=30,
        choices=PAYMENT_STATUS_CHOICES,
        default="DRAFT",
    )
    payment_date = models.DateField(default=timezone.now)

    coa_cash_account = models.ForeignKey(
        "accounts.Account",
        on_delete=models.SET_NULL,
        related_name="customer_payments",
        blank=True,
        null=True,
    )

    amount_reconciled = models.DecimalField(
        max_digits=50, decimal_places=20, default=Decimal("0.00")
    )
    remaining_balance = models.DecimalField(
        max_digits=50,
        decimal_places=20,
        default=Decimal("0.00"),
        help_text="Unallocated balance remaining on this prepayment. Only meaningful when invoice=None.",
    )
    are_initial_journal_entries_made = models.BooleanField(default=False)

    distribution_strategy = models.CharField(
        max_length=50,
        choices=DepositDistributionStrategy.choices,
        blank=True,
        null=True,
        help_text="Override institution deposit distribution strategy",
    )

    is_externally_managed = models.BooleanField(
        default=False,
        help_text="Indicates if the payment is managed by an external system.",
    )

    search_fields = [
        "reference_code",
        "description",
        "payment_status",
        "customer__customer_name",
        "invoice__reference_code",
    ]
    ordering_fields = [
        "created_at",
        "payment_date",
        "amount",
        "payment_status",
        "reference_code",
    ]

    def clean(
        self,
    ):
        super().clean()

        if self.invoice and self.customer:
            raise validation_error(
                "A customer payment cannot have both an invoice and a customer."
            )

        if not self.invoice and not self.customer:
            raise validation_error(
                "A customer payment must have either an invoice or a customer."
            )

        if not self.originating_payment_id:
            return

        if self.invoice_id:
            raise validation_error(
                "A generated overpayment cannot be linked directly to an invoice."
            )

        if not self.customer_id:
            raise validation_error(
                "A generated overpayment must be linked to a customer."
            )

        if self.pk and self.originating_payment_id == self.pk:
            raise validation_error("A payment cannot be its own originating payment.")

        origin = self.originating_payment

        if not origin.invoice_id:
            raise validation_error(
                "The originating payment must be an invoice payment."
            )

        if origin.originating_payment_id:
            raise validation_error(
                "A generated overpayment cannot generate another overpayment."
            )

        origin_customer = origin.get_customer()
        if not origin_customer or origin_customer.pk != self.customer_id:
            raise validation_error(
                "The generated overpayment and originating payment must "
                "belong to the same customer."
            )

        if origin.institution_id != self.institution_id:
            raise validation_error(
                "The generated overpayment and originating payment must "
                "belong to the same institution."
            )

        duplicate = CustomerPayment.objects.filter(
            originating_payment_id=self.originating_payment_id,
            deleted_at__isnull=True,
        ).exclude(pk=self.pk)

        if duplicate.exists():
            raise validation_error(
                "An active generated prepayment already exists for this payment."
            )

    def save(self, *args, **kwargs):
        allow_external_update = kwargs.pop("allow_external_update", False)

        if self.pk and not allow_external_update:
            externally_managed = (
                type(self)
                .objects.filter(
                    pk=self.pk,
                    is_externally_managed=True,
                )
                .exists()
            )
            if externally_managed:
                raise validation_error(
                    "Externally managed customer payments cannot be changed manually."
                )

        self.full_clean()

        is_new = self._state.adding

        if is_new:
            if self.customer and self.invoice is None:
                self.remaining_balance = self.settlement_amount

        super().save(*args, **kwargs)

    def delete(self, *args, **kwargs):
        if self.is_externally_managed:
            raise validation_error(
                "Externally managed customer payments cannot be deleted manually."
            )
        return super().delete(*args, **kwargs)

    def _trigger_approval(
        self,
        action_name,
        profile_institution=None,
        external_identity=None,
    ):
        if self.is_externally_managed:
            raise validation_error(
                "Externally managed customer payments do not use approval workflows."
            )

        return super()._trigger_approval(
            action_name,
            profile_institution,
            external_identity,
        )

    @property
    def is_invoice_payment(self):
        return self.invoice_id is not None

    @property
    def is_standalone_prepayment(self):
        return (
            self.invoice_id is None
            and self.customer_id is not None
            and self.originating_payment_id is None
        )

    @property
    def is_generated_overpayment(self):
        return (
            self.invoice_id is None
            and self.customer_id is not None
            and self.originating_payment_id is not None
        )

    @property
    def is_deposit(self):
        return self.invoice_id is None

    def get_customer(
        self,
    ):
        return (
            self.customer
            if self.customer
            else self.invoice.get_invoice_customer() if self.invoice else None
        )

    @transaction.atomic
    def finish_workflow(self, approval: Approval):
        if approval.status == "completed":
            if approval.action.name in ["create", "update"]:
                self.is_active = True
                self.payment_status = "APPROVED"

                from customers.services import CustomerPaymentService

                CustomerPaymentService.process_financial_events(self)

            elif approval.action.name == "delete":
                self.delete()
        elif approval.status == "rejected":
            if approval.action.name == "create":
                self.is_active = False
                self.deleted_at = timezone.now()
            elif approval.action.name in ["update", "delete"]:
                self.is_active = False
                self.deleted_at = None

        self.save()

    class Meta:
        verbose_name = "Customer Payment"
        verbose_name_plural = "Customer Payments"
        constraints = [
            models.UniqueConstraint(
                fields=["originating_payment"],
                condition=models.Q(
                    originating_payment__isnull=False,
                    deleted_at__isnull=True,
                ),
                name="unique_active_generated_prepayment_per_payment",
            ),
        ]

    def get_institution(self):
        return self.institution

    def determine_rate_currency_used(self):
        from system.services import FxRateService

        payment_currency = self.currency or self.institution.currency
        rate = FxRateService.resolve_base_rate(
            institution=self.institution,
            currency=payment_currency,
            source=self,
        )
        return payment_currency, rate

    def determine_settlement_rate_currency_used(self):
        from system.services import FxRateService

        settlement_currency = self.settlement_currency

        if settlement_currency is None and self.invoice_id:
            settlement_currency = self.invoice.determine_rate_currency_used()[0]

        if settlement_currency is None:
            customer = self.get_customer()
            settlement_currency = (
                customer.currency
                if customer and customer.currency_id
                else self.institution.currency
            )

        rate = FxRateService.resolve_base_rate(
            institution=self.institution,
            currency=settlement_currency,
            source=self,
        )
        return settlement_currency, rate

    def resolve_distribution_strategy(self):
        return (
            self.distribution_strategy
            or self.customer.deposit_distribution_strategy
            or self.get_institution().deposit_distribution_strategy
        )


class CustomerPaymentMethod(SoftDeletableTimeStampedModel):
    reference_prefix = "C-PAY-METH"

    payment = models.OneToOneField(
        CustomerPayment,
        on_delete=models.CASCADE,
        related_name="payment_method",
    )

    method_type = models.CharField(
        max_length=50,
        choices=[
            ("bank", "Bank"),
            ("mobile_money", "Mobile Money"),
            ("digital_wallet", "Digital Wallet"),
        ],
    )

    identifier = models.CharField(
        max_length=100,
        help_text="The account number, mobile money number, or digital wallet identifier.",
        editable=False,
    )

    operator_country_code = models.CharField(
        max_length=10,
        blank=True,
        null=True,
        db_index=True,
        help_text="ISO 3166-1 alpha-2 country code, such as UG or KE.",
    )
    operator_code = models.CharField(
        max_length=100,
        blank=True,
        null=True,
        editable=False,
    )
    operator_name = models.CharField(
        max_length=100,
        blank=True,
        null=True,
        editable=False,
    )

    verified_account_name = models.CharField(
        max_length=255,
        blank=True,
        null=True,
        editable=False,
        help_text="Account-holder name returned by BaisoftPay verification.",
    )

    external_charge_merchant = models.BooleanField(
        blank=True,
        null=True,
        editable=False,
    )

    external_transaction_public_id = models.CharField(
        max_length=255, null=True, blank=True, editable=False, db_index=True
    )
    external_transaction_status = models.CharField(
        max_length=50, null=True, blank=True, editable=False
    )

    class Meta:
        verbose_name = "Customer Payment Method"
        verbose_name_plural = "Customer Payment Methods"

    def __str__(self):
        return f"{self.method_type.capitalize()} - {self.identifier}"

    def clean(self):
        super().clean()

        if not self.payment.is_externally_managed:
            raise validation_error(
                "Payment method can only be set for externally managed payments."
            )


class SalesPerson(ReportableModelMixin, BaseApprovableModel):
    name = models.CharField(max_length=100)
    email = models.EmailField(max_length=254, blank=True, null=True)
    institution = models.ForeignKey("institution.Institution", on_delete=models.CASCADE)
    balance = models.DecimalField(max_digits=50, decimal_places=20, default=0.00)
    profile_photo = models.ImageField(
        upload_to="salesperson_photos/",
        blank=True,
        null=True,
        help_text="Optional profile photo for the salesperson",
    )
    address = models.CharField(
        max_length=255,
        blank=True,
        null=True,
        help_text="Optional address of the salesperson",
    )
    contact = models.CharField(
        max_length=20,
        blank=True,
        null=True,
        help_text="Optional contact phone number",
    )

    search_fields = ["name"]

    def __str__(self):
        return self.name

    def get_institution(self):
        return self.institution

    def finish_workflow(self, approval: Approval):
        with transaction.atomic():
            if approval.status == "completed":
                if approval.action.name in ["create", "update"]:
                    self.is_active = True
                elif approval.action.name == "delete":
                    self.delete()
            elif approval.status == "rejected":
                if approval.action.name == "create":
                    self.is_active = False
                    self.deleted_at = timezone.now()

                elif approval.action.name in ["update", "delete"]:
                    self.is_active = False
                    self.deleted_at = None

        self.save()


class SalesPersonCommissionEntry(ReportableModelMixin, BaseApprovableModel):
    sales_person = models.ForeignKey(
        SalesPerson,
        on_delete=models.CASCADE,
        related_name="commission_history",
    )

    COMMISSION_CHOICES = [
        ("earnings", "earnings"),
        ("payments", "payments"),
    ]

    invoice = models.ForeignKey(
        Invoice,
        on_delete=models.CASCADE,
        related_name="commission_entries",
        null=True,
    )

    amount = models.DecimalField(
        max_digits=10,
        decimal_places=2,
        help_text="The amount of this specific commission transaction.",
    )

    new_commission = models.DecimalField(
        max_digits=10,
        decimal_places=2,
        help_text="The salesperson's balance after this transaction.",
    )
    old_commission = models.DecimalField(
        max_digits=10,
        decimal_places=2,
        help_text="The salesperson's balance before this transaction.",
    )

    commission_type = models.CharField(max_length=50, choices=COMMISSION_CHOICES)

    payment_account = models.ForeignKey(
        "accounts.Account",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
    )

    def clean(self):
        if self.amount <= 0:
            raise validation_error("Commission amount must be greater than zero.")

        if self.commission_type == "earnings" and self.payment_account:
            raise validation_error(
                "Payment account should not be set for earnings commission type."
            )

    def get_institution(self):
        return self.sales_person.get_institution()

    @classmethod
    def get_institution_filter_field(cls):
        return "sales_person__institution"

    def save(self, *args, **kwargs):
        self.old_commission = self.sales_person.balance

        self.new_commission = self.old_commission + self.amount

        self.sales_person.balance = self.new_commission
        self.sales_person.save()

        super().save(*args, **kwargs)

    def __str__(self):
        return f"{self.commission_type.capitalize()} of {self.amount} for {self.sales_person.name}"

    def finish_workflow(self, approval: Approval):
        with transaction.atomic():
            if approval.status == "completed":
                if approval.action.name in ["create", "update"]:
                    self.is_active = True
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


class CreditDebitNote(ReportableModelMixin, BaseApprovableModel):
    branch = models.ForeignKey(
        "institution.Branch",
        on_delete=models.CASCADE,
        related_name="credit_debit_notes",
        null=True,
        blank=True,
    )

    coa_cash_account = models.ForeignKey(
        "accounts.Account",
        on_delete=models.PROTECT,
        related_name="credit_debit_note_refunds",
        null=True,
        blank=True,
    )

    CREDIT_DEBIT_TYPE_CHOICES = [
        ("CREDIT", "Credit"),
        ("DEBIT", "Debit"),
    ]

    FALLS_UNDER_CHOICES = [
        ("SALES", "Sales"),
        ("PURCHASE", "Purchase"),
    ]

    STATUS_CHOICES = [
        ("PENDING", "Pending"),
        ("APPROVED", "Approved"),
        ("RESOLVED", "Resolved"),
        ("CANCELLED", "Cancelled"),
    ]

    type = models.CharField(max_length=50, choices=CREDIT_DEBIT_TYPE_CHOICES)
    falls_under = models.CharField(max_length=50, choices=FALLS_UNDER_CHOICES)

    bill = models.ForeignKey(
        "vendors.VendorBill",
        on_delete=models.CASCADE,
        related_name="credit_debit_notes",
        null=True,
        blank=True,
    )

    invoice = models.ForeignKey(
        "customers.Invoice",
        on_delete=models.CASCADE,
        related_name="credit_debit_notes",
        null=True,
        blank=True,
    )

    status = models.CharField(max_length=50, choices=STATUS_CHOICES, default="PENDING")

    amount = models.DecimalField(max_digits=50, decimal_places=20, editable=False)

    issue_date = models.DateField(blank=True, null=True)

    are_initial_journal_entries_made = models.BooleanField(default=False)

    search_fields = [
        "reference_code",
        "amount",
        "status",
        "invoice__customer__customer_name",
        "coa_cash_account__account_name",
        "branch__branch_name",
        "bill__reference_code",
        "invoice__reference_code",
        "coa_cash_account__reference_code",
    ]

    ordering_fields = [
        "reference_code",
        "invoice__customer__customer_name",
        "invoice__reference_code",
        "amount",
        "status",
        "issue_date",
    ]

    filterset_fields = [
        "status",
        "invoice__customer__base_uuid",
        "coa_cash_account__base_uuid",
        "branch__base_uuid",
        "bill__base_uuid",
        "invoice__base_uuid",
    ]

    @property
    def reference_prefix(self):
        if not self.falls_under or not self.type:
            return "CRED-DEB"

        if self.falls_under == "SALES" and self.type == "CREDIT":
            return "CRED"

        if self.falls_under == "PURCHASE" and self.type == "DEBIT":
            return "DEB"

    def clean(self):
        if self.falls_under == "SALES" and self.type == "DEBIT":
            raise validation_error("Debit notes cannot be linked to sales.")
        if self.falls_under == "PURCHASE" and self.type == "CREDIT":
            raise validation_error("Credit notes cannot be linked to purchases.")
        if self.falls_under == "SALES" and self.bill:
            raise validation_error("Bill can only be linked to purchases.")
        if self.falls_under == "PURCHASE" and self.invoice:
            raise validation_error("Invoice can only be linked to sales.")
        if not self.bill and not self.invoice:
            raise validation_error("Either bill or invoice must be provided.")
        if self.bill and self.invoice:
            raise validation_error("Cannot link both bill and invoice.")

        if self.invoice and self.type == "CREDIT" and self.falls_under == "SALES":
            invoice = self.invoice

            existing_credit = CreditDebitNote.objects.filter(
                invoice=invoice,
                type="CREDIT",
                falls_under="SALES",
                status__in=["APPROVED", "RESOLVED"],
                is_active=True,
                deleted_at__isnull=True,
            ).exclude(pk=self.pk).aggregate(t=Sum("amount"))["t"] or Decimal("0.00")

            max_credit = invoice.total_amount - existing_credit

            if self.amount > max_credit:
                raise validation_error(
                    f"Credit note amount ({self.amount}) exceeds the remaining adjustable balance ({max_credit})."
                )

            cash_refund = max(
                self.amount - invoice.amount_due,
                Decimal("0.00"),
            )

            if cash_refund > Decimal("0.00"):
                if not self.coa_cash_account:
                    raise validation_error(
                        {
                            "coa_cash_account": (
                                "A cash or bank account is required for the paid "
                                "portion of this Credit Note."
                            )
                        }
                    )

                institution = self.get_institution()

                if self.coa_cash_account.institution_id != institution.id:
                    raise validation_error(
                        {
                            "coa_cash_account": (
                                "The selected cash account must belong to the "
                                "Credit Note institution."
                            )
                        }
                    )

                self.coa_cash_account.validate_account(
                    expected_group_types={"asset"},
                    expected_role_codes={"cash_account"},
                )

                invoice_currency = invoice.determine_rate_currency_used()[0]
                cash_currency = self.coa_cash_account.get_account_currency()

                if cash_currency.pk != invoice_currency.pk:
                    raise validation_error(
                        {
                            "coa_cash_account": (
                                "The cash account currency must match the invoice "
                                "currency."
                            )
                        }
                    )
        if self.bill and self.type == "DEBIT" and self.falls_under == "PURCHASE":
            bill = self.bill
            existing_debit = CreditDebitNote.objects.filter(
                bill=bill,
                type="DEBIT",
                falls_under="PURCHASE",
                deleted_at__isnull=True,
            ).exclude(pk=self.pk).aggregate(t=Sum("amount"))["t"] or Decimal("0.00")
            max_debit = bill.total_amount - existing_debit
            if self.amount > max_debit:
                raise validation_error(
                    f"Debit note amount ({self.amount}) exceeds the remaining adjustable balance ({max_debit})."
                )

    def save(self, *args, **kwargs):
        self.full_clean()
        super().save(*args, **kwargs)

    def get_institution(self):
        if self.branch_id:
            return self.branch.institution
        if self.bill_id:
            return self.bill.get_institution()
        if self.invoice_id:
            return self.invoice.get_institution()
        return None

    @classmethod
    def get_institution_filter_field(cls):
        return "branch__institution"

    def finish_workflow(self, approval: Approval):
        with transaction.atomic():
            if approval.status == "completed":
                if approval.action.name in ["create", "update"]:
                    if self.are_initial_journal_entries_made:
                        raise validation_error(
                            "A posted Credit/Debit Note cannot be approved or updated again."
                        )

                    self.is_active = True
                    self.status = "APPROVED"

                    active_lines = list(self.line_items.filter(deleted_at__isnull=True))

                    for line in active_lines:
                        line.full_clean()
                        recalculated_amount = line.determine_amount_to_deduct()
                        CreditDebitNoteLineItem.objects.filter(pk=line.pk).update(
                            amount_to_deduct=recalculated_amount
                        )
                        line.amount_to_deduct = recalculated_amount

                    self._recompute_amount_from_line_items()

                    self.save(update_fields=["is_active", "status"])

                    self.create_price_effect()

                    if not self.are_initial_journal_entries_made:
                        self._process_financial_events()

                    if self.invoice and self.falls_under == "SALES":
                        self.invoice.recompute_note_totals()

                    if self.bill and self.falls_under == "PURCHASE":
                        self.bill.recompute_note_totals()

                    return

                elif approval.action.name == "delete":
                    if self.are_initial_journal_entries_made:
                        raise validation_error(
                            "A posted Credit/Debit Note cannot be deleted. "
                            "An explicit reversal document is required."
                        )

                    self.delete()

                    if self.invoice and self.falls_under == "SALES":
                        self.invoice.recompute_note_totals()

                    if self.bill and self.falls_under == "PURCHASE":
                        self.bill.recompute_note_totals()

            elif approval.status == "rejected":
                if self.are_initial_journal_entries_made:
                    raise validation_error(
                        "A posted Credit/Debit Note cannot be rejected."
                    )

                if approval.action.name == "create":
                    self.is_active = False
                    self.deleted_at = timezone.now()

                elif approval.action.name in ["update", "delete"]:
                    self.is_active = False
                    self.deleted_at = None

        self.save()

    def _has_item_line_items(self) -> bool:
        return self.line_items.filter(
            type="ITEM_RETURN",
            deleted_at__isnull=True,
        ).exists()

    def _recompute_amount_from_line_items(self):
        from django.db.models import Sum

        total = self.line_items.filter(deleted_at__isnull=True).aggregate(
            t=Sum("amount_to_deduct")
        )["t"] or Decimal("0.00")
        CreditDebitNote.objects.filter(pk=self.pk).update(amount=total)
        self.amount = total

    def create_price_effect(self):
        self.price_effects.all().delete()

        if self.falls_under == "PURCHASE" and self.bill:
            amount_before = self.bill.adjusted_total
        elif self.falls_under == "SALES" and self.invoice:
            amount_before = self.invoice.adjusted_total
        else:
            return

        if amount_before is None:
            return

        if self.falls_under == "SALES" and self.type == "CREDIT":
            amount_after = amount_before - self.amount
        elif self.falls_under == "PURCHASE" and self.type == "DEBIT":
            amount_after = amount_before - self.amount
        else:
            return

        CreditDebitNotePriceEffect.objects.create(
            credit_debit_note=self,
            amount_before=amount_before,
            amount_after=amount_after,
            description=f"{self.type} note applied: {self.amount}",
        )

    @transaction.atomic
    def _process_financial_events(self):

        from transactions.models import Transaction

        CreditDebitNote.objects.select_for_update().get(pk=self.pk)
        self.refresh_from_db(fields=["are_initial_journal_entries_made"])

        content_type = ContentType.objects.get_for_model(
            self.__class__,
            for_concrete_model=False,
        )
        existing_journal = Transaction.objects.filter(
            content_type=content_type,
            object_id=self.pk,
            deleted_at__isnull=True,
        ).first()

        if self.are_initial_journal_entries_made:
            if existing_journal is None:
                raise validation_error(
                    "The Credit/Debit Note is marked posted but its journal "
                    "cannot be found."
                )
            return existing_journal

        if existing_journal is not None:
            raise validation_error(
                "A journal already exists for this Credit/Debit Note while "
                "the note is not marked posted. Manual reconciliation is required."
            )

        institution = self.get_institution()

        if self.type == "CREDIT" and self.falls_under == "SALES":
            return self._post_sales_credit_journal(
                institution=institution,
            )

        if self.type == "DEBIT" and self.falls_under == "PURCHASE":
            return self._post_purchase_debit_journal(institution=institution)

        raise validation_error("Unsupported Credit/Debit Note type and category.")

    def _post_sales_credit_journal(
        self,
        *,
        institution,
    ):
        from accounts.utils import get_or_create_default_account
        from customers.services import CreditNoteLineAmountService
        from transactions.services import JournalLine, JournalPostingService

        if not self.invoice:
            raise validation_error("A sales Credit Note must reference an invoice.")

        invoice = Invoice.objects.select_for_update().get(pk=self.invoice_id)
        note_amount = self.amount
        receivable_reduction = min(note_amount, invoice.amount_due)
        cash_refund = note_amount - receivable_reduction
        document_currency, document_rate = invoice.determine_rate_currency_used()
        account_currency = (
            None if document_currency == institution.currency else document_currency
        )
        ar_account = (
            invoice.accounts_receivable_account
            or get_or_create_default_account(
                institution,
                "receivable_account",
                account_currency,
            )
        )
        sales_account = get_or_create_default_account(
            institution,
            "income_account",
            None,
        )
        journal_lines = []

        active_lines = list(
            self.line_items.filter(deleted_at__isnull=True).select_related(
                "account",
                "invoice_line_item",
                "invoice_line_item__line_item",
                "invoice_line_item__line_item__inventory_item",
            )
        )

        if active_lines:
            for line in active_lines:
                if line.invoice_line_item_id:
                    invoice_line = line.invoice_line_item
                    inventory_item = invoice_line.line_item.inventory_item
                    revenue_account = (
                        line.account or inventory_item.revenue_account or sales_account
                    )

                    if line.amount_on_general_adjustment:
                        journal_lines.append(
                            JournalLine(
                                account=revenue_account,
                                entry_type="debit",
                                transaction_amount=line.amount_on_general_adjustment,
                                transaction_currency=document_currency,
                                exchange_rate=document_rate,
                                description=(
                                    f"Credit adjustment for {inventory_item.item_name} "
                                    f"(credit note {self.reference_code})"
                                ),
                            )
                        )
                        continue

                    components = CreditNoteLineAmountService.components(
                        quantity=line.quantity,
                        invoice_line_item=invoice_line,
                    )

                    if components["revenue_amount"] > Decimal("0.00"):
                        journal_lines.append(
                            JournalLine(
                                account=revenue_account,
                                entry_type="debit",
                                transaction_amount=components["revenue_amount"],
                                transaction_currency=document_currency,
                                exchange_rate=document_rate,
                                description=(
                                    f"Revenue reversed for "
                                    f"{inventory_item.item_name} "
                                    f"(credit note {self.reference_code})"
                                ),
                            )
                        )

                    for tax_component in components["tax_components"]:
                        breakdown = tax_component["breakdown"]
                        tax_amount = tax_component["amount"]

                        if tax_amount <= Decimal("0.00"):
                            continue

                        tax_account = (
                            breakdown.tax.tax_account
                            or get_or_create_default_account(
                                institution,
                                "vat_controlled_account",
                                None,
                            )
                        )
                        journal_lines.append(
                            JournalLine(
                                account=tax_account,
                                entry_type="debit",
                                transaction_amount=tax_amount,
                                transaction_currency=document_currency,
                                exchange_rate=document_rate,
                                description=(
                                    f"{breakdown.tax.tax_name} reversed "
                                    f"(credit note {self.reference_code})"
                                ),
                            )
                        )
                else:
                    line_amount = line.amount_to_deduct or Decimal("0.00")
                    debit_account = line.account if line.account_id else sales_account
                    journal_lines.append(
                        JournalLine(
                            account=debit_account,
                            entry_type="debit",
                            transaction_amount=line_amount,
                            transaction_currency=document_currency,
                            exchange_rate=document_rate,
                            description=(
                                f"{debit_account.account_name} reduced"
                                + (f" – {line.label}" if line.label else "")
                                + f" (credit note {self.reference_code})"
                            ),
                        )
                    )
        else:
            journal_lines.append(
                JournalLine(
                    account=sales_account,
                    entry_type="debit",
                    transaction_amount=note_amount,
                    transaction_currency=document_currency,
                    exchange_rate=document_rate,
                    description=f"Sales revenue reduced (credit note {self.reference_code})",
                )
            )

        if receivable_reduction > Decimal("0.00"):
            journal_lines.append(
                JournalLine(
                    account=ar_account,
                    entry_type="credit",
                    transaction_amount=receivable_reduction,
                    transaction_currency=document_currency,
                    exchange_rate=document_rate,
                    description=(
                        f"Customer receivable reduced by credit note "
                        f"{self.reference_code}"
                    ),
                )
            )

        if cash_refund > Decimal("0.00"):
            if not self.coa_cash_account:
                raise validation_error(
                    "A cash or bank account is required for this refund."
                )

            journal_lines.append(
                JournalLine(
                    account=self.coa_cash_account,
                    entry_type="credit",
                    transaction_amount=cash_refund,
                    transaction_currency=document_currency,
                    exchange_rate=document_rate,
                    description=(
                        f"Cash refunded for credit note {self.reference_code}"
                    ),
                )
            )

        journal, _ = JournalPostingService.post(
            fiscal_year=get_fiscal_year(
                institution,
                self.issue_date or date.today(),
            ),
            title=f"Credit Note {self.reference_code}",
            description=self.description or "",
            transaction_date=self.issue_date,
            lines=journal_lines,
            branch=self.branch,
            content_type=ContentType.objects.get_for_model(
                self.__class__,
                for_concrete_model=False,
            ),
            object_id=self.pk,
            source=self,
        )

        customer = invoice.get_invoice_customer()
        if customer and receivable_reduction > Decimal("0.00"):
            customer = Customer.objects.select_for_update().get(pk=customer.pk)
            customer.outstanding_receivables_balance = max(
                customer.outstanding_receivables_balance - receivable_reduction,
                Decimal("0.00"),
            )
            customer.save(
                update_fields=["outstanding_receivables_balance"],
                outstanding_receivables_balance_change_reason=(
                    f"Credit note {self.reference_code} applied to invoice "
                    f"{invoice.reference_code}"
                ),
            )

        CreditDebitNote.objects.filter(pk=self.pk).update(
            are_initial_journal_entries_made=True
        )
        self.are_initial_journal_entries_made = True

        return journal

    def _post_purchase_debit_journal(self, *, institution):
        from accounts.utils import get_or_create_default_account
        from transactions.services import JournalLine, JournalPostingService
        from vendors.models import VendorBill

        if not self.bill_id:
            raise validation_error("A purchase Debit Note must reference a bill.")

        bill = VendorBill.objects.select_for_update().get(pk=self.bill_id)
        vendor = bill.get_bill_vendor()
        document_currency, document_rate = bill.determine_rate_currency_used()
        account_currency = (
            None if document_currency == institution.currency else document_currency
        )
        ap_account = (
            vendor.default_account_payable if vendor else None
        ) or get_or_create_default_account(
            institution, "payable_account", account_currency
        )
        purchase_account = get_or_create_default_account(institution, "sgna_account")

        payment_status = bill.payment_status
        note_amount = self.amount

        ap_portion = Decimal("0.00")
        cash_portion = Decimal("0.00")

        if payment_status == "unpaid":
            ap_portion = note_amount

        elif payment_status == "partially_paid":
            amount_due = bill.balance_due
            amount_paid = bill._total_confirmed_payments()

            if note_amount <= amount_due:
                ap_portion = note_amount
            else:
                ap_portion = amount_due
                cash_portion = min(note_amount - amount_due, amount_paid)

        elif payment_status == "paid":
            cash_portion = note_amount
        else:
            raise validation_error("Unsupported payment status for the linked bill.")

        entries = []

        entries.append(
            JournalLine(
                account=purchase_account,
                entry_type="credit",
                transaction_amount=note_amount,
                transaction_currency=document_currency,
                exchange_rate=document_rate,
                description=f"Purchase expense reduced (debit note {self.reference_code})",
            )
        )

        if ap_portion > 0:
            entries.append(
                JournalLine(
                    account=ap_account,
                    entry_type="debit",
                    transaction_amount=ap_portion,
                    transaction_currency=document_currency,
                    exchange_rate=document_rate,
                    description=f"Supplier payable reduced by debit note {self.reference_code}",
                )
            )

        if cash_portion > 0:
            cash_account = get_or_create_default_account(
                institution, "cash_account", account_currency
            )
            entries.append(
                JournalLine(
                    account=cash_account,
                    entry_type="debit",
                    transaction_amount=cash_portion,
                    transaction_currency=document_currency,
                    exchange_rate=document_rate,
                    description=f"Cash refund receivable for debit note {self.reference_code}",
                )
            )

        transaction_date = self.issue_date or timezone.localdate()
        journal, _ = JournalPostingService.post(
            fiscal_year=get_fiscal_year(institution, transaction_date),
            title=f"{self.type} Note {self.reference_code}",
            description=self.description or "",
            transaction_date=transaction_date,
            lines=entries,
            branch=self.branch,
            content_type=ContentType.objects.get_for_model(
                self.__class__,
                for_concrete_model=False,
            ),
            object_id=self.pk,
            source=self,
        )

        if vendor and ap_portion > 0:
            vendor = vendor.__class__.objects.select_for_update().get(pk=vendor.pk)
            vendor.outstanding_payables = max(
                vendor.outstanding_payables - ap_portion, Decimal("0.00")
            )
            vendor.save(
                update_fields=["outstanding_payables"],
                outstanding_payables_balance_change_reason=f"Debit note {self.reference_code} applied to bill {bill.reference_code}",
            )

        CreditDebitNote.objects.filter(pk=self.pk).update(
            are_initial_journal_entries_made=True
        )
        self.are_initial_journal_entries_made = True

        return journal


class CreditDebitNoteLineItem(SoftDeletableTimeStampedModel):
    LINE_TYPE_CHOICES = [
        ("ITEM_RETURN", "Item Return"),
        ("PRICE_ADJUSTMENT", "Price Adjustment"),
        ("GENERAL_ADJUSTMENT", "General Adjustment"),
    ]

    type = models.CharField(
        max_length=50,
        choices=LINE_TYPE_CHOICES,
        default="GENERAL_ADJUSTMENT",
        editable=False,
    )

    credit_debit_note = models.ForeignKey(
        "customers.CreditDebitNote",
        on_delete=models.CASCADE,
        related_name="line_items",
        blank=True,
        null=True,
    )

    label = models.CharField(
        max_length=100,
        blank=True,
        null=True,
    )

    invoice_line_item = models.ForeignKey(
        "customers.InvoiceLineItem",
        on_delete=models.CASCADE,
        related_name="credit_note_line_items",
        blank=True,
        null=True,
    )

    bill_line_item = models.ForeignKey(
        "vendors.VendorBillLineItem",
        on_delete=models.CASCADE,
        related_name="debit_note_line_items",
        blank=True,
        null=True,
    )

    account = models.ForeignKey(
        "accounts.Account",
        on_delete=models.SET_NULL,
        related_name="credit_debit_note_line_items",
        blank=True,
        null=True,
    )

    quantity = models.PositiveIntegerField(blank=True, null=True)

    amount_on_general_adjustment = models.DecimalField(
        max_digits=50,
        decimal_places=20,
        blank=True,
        null=True,
    )

    amount_to_deduct = models.DecimalField(
        max_digits=50,
        decimal_places=20,
        default=Decimal("0.00"),
        editable=False,
    )

    def __str__(self):
        return f"{self.type} for {self.credit_debit_note.reference_code}"

    class Meta:
        verbose_name = "Credit/Debit Note Line Item"
        verbose_name_plural = "Credit/Debit Note Line Items"
        ordering = ["-created_at"]

    def clean(self):
        if not self.credit_debit_note:
            raise validation_error("Credit/Debit Note is required.")

        if self.invoice_line_item and self.bill_line_item:
            raise validation_error(
                "Cannot link both invoice line item and bill line item to the same credit/debit note line."
            )

        if (self.invoice_line_item or self.bill_line_item) and not self.quantity:
            raise validation_error(
                "Quantity is required when linked to an invoice or bill line item."
            )

        if self.invoice_line_item:
            note = self.credit_debit_note

            if note.falls_under != "SALES" or note.type != "CREDIT":
                raise validation_error(
                    "Invoice lines can only be used on sales Credit Notes."
                )

            if note.invoice_id != self.invoice_line_item.invoice_id:
                raise validation_error(
                    "The invoice line must belong to the Credit Note invoice."
                )

            previously_credited = (
                CreditDebitNoteLineItem.objects.filter(
                    invoice_line_item=self.invoice_line_item,
                    credit_debit_note__falls_under="SALES",
                    credit_debit_note__type="CREDIT",
                    credit_debit_note__status__in=["APPROVED", "RESOLVED"],
                    credit_debit_note__is_active=True,
                    credit_debit_note__deleted_at__isnull=True,
                    deleted_at__isnull=True,
                )
                .exclude(pk=self.pk)
                .aggregate(total=Sum("quantity"))["total"]
                or 0
            )

            requested_quantity = self.quantity or 0
            remaining_quantity = max(
                self.invoice_line_item.quantity - previously_credited,
                0,
            )

            if requested_quantity > remaining_quantity:
                raise validation_error(
                    f"Credit quantity ({requested_quantity}) exceeds the "
                    f"remaining invoice-line quantity ({remaining_quantity})."
                )

        if self.bill_line_item:
            note = self.credit_debit_note

            if note.falls_under != "PURCHASE" or note.type != "DEBIT":
                raise validation_error(
                    "Bill lines can only be used on purchase Debit Notes."
                )

            if note.bill_id != self.bill_line_item.bill_id:
                raise validation_error(
                    "The bill line must belong to the selected Debit Note bill."
                )

            if self.quantity > self.bill_line_item.quantity:
                raise validation_error(
                    f"Debit quantity ({self.quantity}) exceeds the bill-line "
                    f"quantity ({self.bill_line_item.quantity})."
                )

            if self.amount_on_general_adjustment:
                maximum_adjustment = (
                    Decimal(str(self.quantity))
                    * Decimal(str(self.bill_line_item.unit_price))
                ).quantize(Decimal("0.01"))

                if self.amount_on_general_adjustment > maximum_adjustment:
                    raise validation_error(
                        f"Debit amount ({self.amount_on_general_adjustment}) exceeds "
                        f"the selected quantity value ({maximum_adjustment})."
                    )

        if not (self.invoice_line_item or self.bill_line_item) and self.quantity:
            raise validation_error(
                "Quantity should be empty when not linked to an invoice or bill line item."
            )

        if (
            not (self.invoice_line_item or self.bill_line_item)
            and not self.amount_on_general_adjustment
        ):
            raise validation_error("Amount is required for general adjustment lines.")

        if self.account:
            note = self.credit_debit_note

            if note.falls_under == "PURCHASE" and note.type == "DEBIT":
                self.account.validate_account(expected_group_types={"asset"})
            elif note.falls_under == "SALES" and note.type == "CREDIT":
                self.account.validate_account(expected_group_types={"expense"})
            else:
                self.account.validate_account(
                    expected_group_types={"expense", "revenue"},
                )

        if (
            self.amount_on_general_adjustment
            and self.amount_on_general_adjustment <= Decimal("0.00")
        ):
            raise validation_error(
                "Amount on general adjustment must be greater than zero."
            )

    def save(self, *args, **kwargs):
        self.full_clean()

        is_new = self._state.adding

        if is_new:
            self.type = self._infer_line_type()

            self.amount_to_deduct = self.determine_amount_to_deduct()

        super().save(*args, **kwargs)

    def _infer_line_type(self) -> str:
        if (
            self.credit_debit_note.falls_under == "SALES"
            and self.credit_debit_note.type == "CREDIT"
        ):
            line_item = self.invoice_line_item
        elif (
            self.credit_debit_note.falls_under == "PURCHASE"
            and self.credit_debit_note.type == "DEBIT"
        ):
            line_item = self.bill_line_item
        else:
            line_item = None

        if line_item is None:
            return "GENERAL_ADJUSTMENT"
        elif (
            self.credit_debit_note.falls_under == "PURCHASE"
            and self.credit_debit_note.type == "DEBIT"
        ):
            return "PRICE_ADJUSTMENT"
        else:
            return "ITEM_RETURN"

    def determine_amount_to_deduct(self):

        if self.amount_on_general_adjustment:
            return self.amount_on_general_adjustment

        if self.type == "GENERAL_ADJUSTMENT":
            return self.amount_on_general_adjustment

        from .services import CreditNoteLineAmountService, DebitNoteLineAmountService

        if self.credit_debit_note.type == "CREDIT":
            return CreditNoteLineAmountService.compute(
                quantity=self.quantity,
                invoice_line_item=self.invoice_line_item,
            )
        elif self.credit_debit_note.type == "DEBIT":
            return DebitNoteLineAmountService.compute(
                quantity=self.quantity,
                bill_line_item=self.bill_line_item,
            )


class CreditDebitNotePriceEffect(ReportableModelMixin, BaseApprovableModel):

    credit_debit_note = models.ForeignKey(
        CreditDebitNote,
        on_delete=models.CASCADE,
        related_name="price_effects",
    )

    amount_before = models.DecimalField(max_digits=50, decimal_places=20)
    amount_after = models.DecimalField(max_digits=50, decimal_places=20)

    def save(self, *args, **kwargs):
        super().save(*args, **kwargs)

    def get_institution(self):
        return self.credit_debit_note.get_institution()

    @classmethod
    def get_institution_filter_field(cls):
        return "credit_debit_note__branch__institution"

    def finish_workflow(self, approval: Approval):
        with transaction.atomic():
            if approval.status == "completed":
                if approval.action.name in ["create", "update"]:
                    self.is_active = True
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


class ItemReturn(ReportableModelMixin, BaseApprovableModel, ReversibleFinancialMixin):
    reference_prefix = "IR"

    RETURN_TYPE_CHOICES = [
        ("REPLACEMENT", "Replacement"),
        ("CASH_REFUND", "Cash Refund"),
    ]

    RETURN_STATUS_CHOICES = [
        ("PENDING", "Pending"),
        ("APPROVED", "Approved"),
        ("REJECTED", "Rejected"),
    ]

    institution = models.ForeignKey(
        "institution.Institution",
        on_delete=models.CASCADE,
        related_name="item_returns",
        blank=True,
        null=True,
    )

    goods_issued_note = models.ForeignKey(
        "customers.GoodsIssuedNote",
        on_delete=models.SET_NULL,
        related_name="item_returns",
        null=True,
        blank=True,
    )

    coa_cash_account = models.ForeignKey(
        "accounts.Account",
        on_delete=models.PROTECT,
        related_name="item_return_refund_requests",
        null=True,
        blank=True,
    )

    return_type = models.CharField(
        max_length=100,
        choices=RETURN_TYPE_CHOICES,
        default="REPLACEMENT",
    )

    return_status = models.CharField(
        max_length=100,
        choices=RETURN_STATUS_CHOICES,
        default="PENDING",
    )

    return_date = models.DateTimeField(
        blank=True,
        null=True,
        default=timezone.now,
    )

    are_initial_journal_entries_made = models.BooleanField(default=False)

    search_fields = [
        "return_type",
        "return_status",
        "goods_issued_note__reference_code",
        "goods_issued_note__invoice__reference_code",
        "goods_issued_note__purchase_order__reference_code",
        "goods_issued_note__branch__branch_name",
        "coa_cash_account__account_name",
    ]

    ordering_fields = [
        "return_type",
        "return_status",
        "return_date",
    ]

    filterset_fields = [
        "return_type",
        "return_status",
        "goods_issued_note__base_uuid",
        "goods_issued_note__invoice__base_uuid",
        "goods_issued_note__purchase_order__base_uuid",
        "goods_issued_note__branch__base_uuid",
        "coa_cash_account__base_uuid",
    ]

    class Meta:
        verbose_name = "Item Return"
        verbose_name_plural = "Item Returns"
        ordering = ["-created_at"]

    @classmethod
    def get_foreign_key_display_fields(cls):
        return {
            "goods_issued_note": "reference_code",
            "coa_cash_account": "account_name",
        }

    @classmethod
    def get_filter_serializer_class(cls):
        from customers.filters import ItemReturnFilterSerializer

        return ItemReturnFilterSerializer

    def get_institution(self):
        return self.institution

    def get_invoice(self):
        return getattr(self.goods_issued_note, "invoice", None)

    def get_purchase_order(self):
        gin = self.goods_issued_note

        if gin.purchase_order:
            return gin.purchase_order

        if gin.invoice and gin.invoice.purchase_order:
            return gin.invoice.purchase_order

        return None

    def get_branch(self):
        return self.goods_issued_note.branch if self.goods_issued_note else None

    def save(self, *args, **kwargs):
        self.full_clean()
        super().save(*args, **kwargs)

    def check_if_return_can_be_made(self):
        institution = self.get_institution()

        supports_sales_returns = institution.supports_sales_returns

        if not supports_sales_returns:
            raise validation_error(
                "This institution does not support returning products once sold."
            )

        minimal_days_for_sales_return = institution.minimal_days_for_sales_return

        if minimal_days_for_sales_return is not None:
            gin_date = self.goods_issued_note.date_issued

            if gin_date is None:
                raise validation_error(
                    "Cannot determine if return is within allowed period: goods issued note has no issue date."
                )

            days_since_issue = (self.return_date - gin_date).days

            if days_since_issue > minimal_days_for_sales_return:
                raise validation_error(
                    f"Return period has expired. Returns must be made within {minimal_days_for_sales_return} days of the goods issue date."
                )

        enable_cash_refund_for_item_return = (
            institution.enable_cash_refund_for_item_return
        )

        if self.return_type == "CASH_REFUND" and not enable_cash_refund_for_item_return:
            raise validation_error(
                "However much item returns are enabled, cash refunds in particular are not allowed."
            )

    def clean(self):
        if not self.goods_issued_note:
            raise validation_error(
                "GIN is required for an item return. Please provide a valid Goods Issued Note."
            )

        self.check_if_return_can_be_made()

        if self.return_type == "CASH_REFUND":
            if not self.coa_cash_account:
                raise validation_error(
                    {
                        "coa_cash_account": (
                            "A cash or bank account is required for a cash refund."
                        )
                    }
                )

            if self.coa_cash_account.institution_id != self.institution_id:
                raise validation_error(
                    {
                        "coa_cash_account": (
                            "The selected cash account must belong to the "
                            "Item Return institution."
                        )
                    }
                )

            self.coa_cash_account.validate_account(
                expected_group_types={"asset"},
                expected_role_codes={"cash_account"},
            )

        if self.pk and self.item_return_items.exists():
            if self.return_type == "CASH_REFUND":
                from customers.services import ItemReturnQuantityService

                for return_item in self.item_return_items.select_related(
                    "goods_issued_note_line"
                ):
                    ItemReturnQuantityService.validate_cash_refund_quantity(
                        goods_issued_note_line=return_item.goods_issued_note_line,
                        requested_quantity=return_item.quantity,
                        exclude_item_return=self,
                    )

            service_items = [
                str(ri.item.inventory_item.item_name)
                for ri in self.item_return_items.all()
                if ri.item.inventory_item.item_type == "SERVICES"
            ]

            if service_items:
                raise validation_error(
                    f"Cannot return service items: {', '.join(service_items)}"
                )

    def finish_workflow(self, approval: Approval):
        with transaction.atomic():
            if approval.status == "completed":
                if approval.action.name in ["create", "update"]:

                    if self.are_initial_journal_entries_made:
                        raise validation_error(
                            "A processed Item Return cannot be approved or updated again."
                        )

                    self.is_active = True
                    self.return_status = "APPROVED"
                    self.save(update_fields=["is_active", "return_status"])

                    from customers.services import ItemReturnProcessingService

                    ItemReturnProcessingService.process(item_return=self)

                    return

                elif approval.action.name == "delete":

                    if self.are_initial_journal_entries_made:
                        raise validation_error(
                            "A processed Item Return cannot be deleted. "
                            "An explicit reversal document is required."
                        )

                    self.is_active = False
                    self.deleted_at = timezone.now()

            elif approval.status == "rejected":

                if self.are_initial_journal_entries_made:
                    raise validation_error(
                        "A processed Item Return cannot be rejected."
                    )

                if approval.action.name == "create":
                    self.is_active = False
                    self.deleted_at = timezone.now()
                elif approval.action.name in ["update", "delete"]:
                    self.is_active = False
                    self.deleted_at = None

        self.save()


class ItemReturnItem(ReportableModelMixin, SoftDeletableTimeStampedModel):
    item_return = models.ForeignKey(
        ItemReturn,
        on_delete=models.CASCADE,
        related_name="item_return_items",
    )

    goods_issued_note_line = models.ForeignKey(
        "customers.GoodsIssuedNoteLineItem",
        on_delete=models.PROTECT,
        related_name="item_return_items",
        null=True,
        blank=True,
        help_text=(
            "Exact Goods Issued Note line whose physical issue is being returned. "
            "Temporarily nullable while legacy rows are reconciled."
        ),
    )

    unit_of_measure = models.ForeignKey(
        "items.BranchInventoryItemUnitOfMeasure",
        on_delete=models.CASCADE,
        null=True,
        blank=True,
    )

    quantity = models.PositiveIntegerField(default=0)

    return_reason = models.ForeignKey(
        "institution.InstitutionItemReturnReason",
        on_delete=models.CASCADE,
        related_name="items",
    )

    class Meta:
        verbose_name = "Item Return Item"
        verbose_name_plural = "Item Return Items"
        ordering = ["-created_at"]
        constraints = [
            models.UniqueConstraint(
                fields=["item_return", "goods_issued_note_line"],
                condition=models.Q(
                    deleted_at__isnull=True,
                    goods_issued_note_line__isnull=False,
                ),
                name="uniq_active_return_gin_line",
            ),
        ]

    def get_institution(self):
        return self.item_return.get_institution()

    def __str__(self):
        return f"{self.quantity} x {self.item.inventory_item.item_name} for return {self.item_return.reference_code}"

    @property
    def item(self):
        return (
            self.goods_issued_note_line.line_item
            if self.goods_issued_note_line_id
            else None
        )

    def clean(self):
        if self.goods_issued_note_line_id:
            source_line = self.goods_issued_note_line

            if (
                source_line.goods_issued_note_id
                != self.item_return.goods_issued_note_id
            ):
                raise validation_error(
                    "The selected GIN line does not belong to the Item Return's GIN."
                )

            if (
                self.unit_of_measure_id
                and self.unit_of_measure_id != source_line.unit_of_measure_id
            ):
                raise validation_error(
                    "The returned unit of measure must match the selected GIN line."
                )

        if self.quantity <= 0:
            raise validation_error("Quantity must be greater than zero.")

        if not self.goods_issued_note_line_id:
            raise validation_error("The exact originating GIN line is required.")

        if not self.item.can_be_returned:
            raise validation_error(
                f"Item '{self.item.inventory_item.item_name}' cannot be returned."
            )

        if self.item.inventory_item.item_type == "SERVICES":
            raise validation_error(
                f"Item '{self.item.inventory_item.item_name}' is a service and cannot be returned."
            )


class GoodsIssuedNote(ReportableModelMixin, BaseApprovableModel):
    reference_prefix = "GIN"

    STATUS_CHOICES = [
        ("draft", "Draft"),
        ("pending", "Pending"),
        ("approved", "Approved"),
        ("cancelled", "Cancelled"),
    ]

    purchase_order = models.ForeignKey(
        "customers.CustomerPurchaseOrder",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="goods_issued_notes",
        help_text="Sales Order this GIN fulfils. Optional for ad-hoc issuance.",
    )

    invoice = models.ForeignKey(
        Invoice,
        on_delete=models.CASCADE,
        related_name="goods_issued_notes",
        null=True,
        blank=True,
    )

    branch = models.ForeignKey(
        "institution.Branch",
        on_delete=models.CASCADE,
        related_name="goods_issued_notes",
    )

    is_inventory_removed = models.BooleanField(default=False)

    status = models.CharField(
        max_length=20,
        choices=STATUS_CHOICES,
        default="draft",
    )

    date_issued = models.DateTimeField(default=timezone.now)

    is_automated = models.BooleanField(
        default=False,
        help_text=(
            "True when this GIN was auto-created by the system on invoice approval "
            "(ON_INVOICE mode). False means it was created manually."
        ),
    )

    create_back_order = models.BooleanField(
        default=False,
        help_text=(
            "Whether to create a back order for any unfulfilled quantity on this GIN. "
            "Only applicable for GINs linked to a purchase order."
        ),
    )

    search_fields = [
        "purchase_order__reference_code",
        "invoice__reference_code",
        "branch__branch_name",
        "purchase_order__customer__customer_name",
        "invoice__customer__customer_name",
        "status",
    ]

    filterset_fields = [
        "purchase_order__base_uuid",
        "invoice__base_uuid",
        "branch__base_uuid",
    ]

    ordering_fields = [
        "status",
        "date_issued",
        "purchase_order__reference_code",
        "invoice__reference_code",
        "branch__branch_name",
    ]

    class Meta:
        ordering = ["-created_at"]
        verbose_name = "Goods Issued Note"
        verbose_name_plural = "Goods Issued Notes"

    def clean(self):
        institution = self.get_institution()

        if self.pk:
            original = GoodsIssuedNote.objects.get(pk=self.pk)
            if original.status == "approved":
                raise validation_error(
                    "Approved Goods Issued Notes cannot be modified."
                )

        if institution and institution.inventory_reduction_timing == "ON_INVOICE":
            if not self.is_automated:
                raise validation_error(
                    "Manual Goods Issued Notes are disabled when inventory reduction "
                    "timing is set to ON_INVOICE. GINs are created automatically "
                    "when an invoice is approved."
                )

        if self.invoice and self.purchase_order:
            raise validation_error(
                "A Goods Issued Note cannot be linked to both an invoice and a "
                "purchase order simultaneously. Link it to one or the other."
            )

        if not self.invoice and not self.purchase_order:
            raise validation_error(
                "A Goods Issued Note must be linked to either an invoice or a "
                "purchase order."
            )

    def save(self, *args, **kwargs):
        self.full_clean()

        is_new = self._state.adding
        super().save(*args, **kwargs)

        if is_new:
            self.send_goods_issued_note_email()

    def __str__(self):
        return self.reference_code

    def get_institution(self):
        return self.branch.institution

    def finish_workflow(self, approval: Approval):
        with transaction.atomic():

            if approval.status == "completed":

                self.is_active = True

                if approval.action.name in ["create", "update"] and self.status in [
                    "pending",
                    "draft",
                ]:
                    self.status = "approved"
                    should_process_inventory = not self.is_inventory_removed

                    self.save()

                    if should_process_inventory:
                        self._process_financial_events()

                        self._sync_fulfilment_after_approval()

                        from customers.services import (
                            SalesInventoryAccountingService,
                        )

                        SalesInventoryAccountingService.recognize_for_gin(self)

                    return

                elif approval.action.name == "delete":
                    self.status = "cancelled"
                    self.is_active = False
                    self.deleted_at = timezone.now()

            elif approval.status == "rejected":
                self.status = "cancelled"
                self.is_active = False

                if approval.action.name in ["update", "delete"]:
                    self.deleted_at = None

            self.save()

    def _sync_fulfilment_after_approval(self):
        from procurement.back_order_automation import (
            sync_gin_fulfillment_status,
            maybe_create_outgoing_back_order_for_gin,
            sync_invoice_gin_fulfillment_status,
        )

        if self.purchase_order:
            sync_gin_fulfillment_status(self)
            maybe_create_outgoing_back_order_for_gin(self)

        if self.invoice:

            if self.invoice.purchase_order:
                sync_gin_fulfillment_status(self)
                maybe_create_outgoing_back_order_for_gin(self)

            sync_invoice_gin_fulfillment_status(self)

    @transaction.atomic
    def _process_financial_events(self):
        if self.is_inventory_removed:
            return

        has_goods = self.line_items.filter(
            line_item__inventory_item__item_type="GOODS",
            deleted_at__isnull=True,
        ).exists()
        if not has_goods:
            return

        from accounts.utils import get_or_create_default_account
        from transactions.services import JournalLine, JournalPostingService

        institution = self.get_institution()
        transaction_date = self.date_issued.date() or timezone.now().date()
        total_cogs = self._record_inventory_reduction()

        if total_cogs > Decimal("0.00"):
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

            po_ref = (
                self.purchase_order.reference_code if self.purchase_order else "ad-hoc"
            )

            journal_lines = [
                JournalLine(
                    account=interim_inventory_account,
                    entry_type="debit",
                    transaction_amount=total_cogs,
                    transaction_currency=institution.currency,
                    exchange_rate=Decimal("1"),
                    description=(
                        f"Interim inventory reduction for GIN " f"{self.reference_code}"
                    ),
                ),
                JournalLine(
                    account=actual_inventory_account,
                    entry_type="credit",
                    transaction_amount=total_cogs,
                    transaction_currency=institution.currency,
                    exchange_rate=Decimal("1"),
                    description=(
                        f"Actual inventory reduction for GIN " f"{self.reference_code}"
                    ),
                ),
            ]

            JournalPostingService.post(
                fiscal_year=get_fiscal_year(
                    institution,
                    transaction_date,
                ),
                title=f"Inventory reduction for GIN {self.reference_code}",
                description=(
                    f"Inventory reduction for GIN {self.reference_code} "
                    f"linked to sales order {po_ref}"
                ),
                transaction_date=transaction_date,
                lines=journal_lines,
                branch=self.branch,
                content_type=ContentType.objects.get_for_model(
                    self.__class__,
                    for_concrete_model=False,
                ),
                object_id=self.id,
                source=self,
            )

        self.is_inventory_removed = True
        GoodsIssuedNote.objects.filter(pk=self.pk).update(is_inventory_removed=True)
        self.refresh_from_db(fields=["is_inventory_removed"])

    @transaction.atomic
    def _record_inventory_reduction(self):
        from procurement.back_order_automation import (
            sync_gin_fulfillment_status,
            maybe_create_outgoing_back_order_for_gin,
        )

        if self.is_inventory_removed:
            return Decimal("0.00")

        stock_lines = list(
            self.line_items.filter(
                line_item__inventory_item__item_type="GOODS",
                deleted_at__isnull=True,
            )
        )

        if not stock_lines:
            return Decimal("0.00")

        for item in stock_lines:
            branch_item = item.line_item
            quantity = item.quantity

            allow_oversell = getattr(
                branch_item.branch, "allow_sales_out_of_stock", False
            )

            StockValuationService.apply_stock_consumption(
                branch_item,
                quantity,
                movement_type="GIN_ISSUE",
                source_document=self,
                source_reference=self.reference_code,
                sold_unit=item.unit_of_measure.unit_of_measure,
                allow_oversell=allow_oversell,
                goods_issued_note_line=item,
            )

        if self.purchase_order:
            sync_gin_fulfillment_status(self)
            maybe_create_outgoing_back_order_for_gin(self)

        from customers.services import SalesInventoryAccountingService

        # This is intentionally derived after consumption. It is the exact total
        # of persisted GIN_ISSUE and applicable NEGATIVE_SALE movements that this
        # GIN generated and is also the source used by later COGS matching.
        total_cogs = SalesInventoryAccountingService.get_actual_issued_cost(self)

        return total_cogs

    def send_goods_issued_note_email(self):
        from utilities.email_client import EmailClient

        institution = self.get_institution()
        branch = self.branch

        recipients = []

        if institution and institution.institution_email:
            recipients.append(institution.institution_email)

        if branch and branch.branch_email:
            recipients.append(branch.branch_email)

        if not recipients:
            return

        line_items = self.line_items.filter(deleted_at__isnull=True)

        subject = f"Goods Issued Note {self.reference_code}"

        context = {
            "reference_code": self.reference_code,
            "status": self.status.replace("_", " ").title(),
            "date": (
                self.date_issued.date().strftime("%B %d, %Y")
                if self.date_issued
                else timezone.now().date().strftime("%B %d, %Y")
            ),
            "institution_name": institution.institution_name if institution else "",
            "branch_name": branch.branch_name if branch else "",
            "vendor_name": branch.branch_name if branch else "Vendor",
            "line_items": [
                {
                    "name": (
                        item.line_item.inventory_item.item_name
                        if hasattr(item.line_item, "inventory_item")
                        and item.line_item.inventory_item
                        else "N/A"
                    ),
                    "unit_of_measure": (
                        item.unit_of_measure.unit_name if item.unit_of_measure else ""
                    ),
                    "quantity": item.quantity,
                }
                for item in line_items
            ],
            "total_quantity": sum(item.quantity for item in line_items),
        }

        EmailClient.send(
            subject=subject,
            recipients=recipients,
            template_html="emails/goods_issued_note_email.html",
            context=context,
        )


class GoodsIssuedNoteLineItem(SoftDeletableTimeStampedModel):
    goods_issued_note = models.ForeignKey(
        "GoodsIssuedNote", on_delete=models.CASCADE, related_name="line_items"
    )
    source_invoice_line = models.ForeignKey(
        "customers.InvoiceLineItem",
        on_delete=models.PROTECT,
        related_name="goods_issue_lines",
        null=True,
        blank=True,
    )
    source_purchase_order_line = models.ForeignKey(
        "customers.CustomerPurchaseOrderLineItem",
        on_delete=models.PROTECT,
        related_name="goods_issue_lines",
        null=True,
        blank=True,
    )
    line_item = models.ForeignKey(
        "items.BranchInventoryItem",
        on_delete=models.CASCADE,
    )
    unit_of_measure = models.ForeignKey(
        "items.BranchInventoryItemUnitOfMeasure",
        on_delete=models.CASCADE,
        null=True,
        blank=True,
    )
    quantity = models.PositiveIntegerField(default=1)

    quantity_returned = models.PositiveIntegerField(default=0)

    def clean(self):
        super().clean()

        if self.source_invoice_line_id and self.source_purchase_order_line_id:
            raise validation_error(
                "A GIN line cannot reference both an invoice line and "
                "a sales-order line."
            )

        if self.goods_issued_note.invoice_id and not self.source_invoice_line_id:
            raise validation_error(
                "An invoice-based GIN line requires its exact source invoice line."
            )

        if (
            self.goods_issued_note.purchase_order_id
            and not self.source_purchase_order_line_id
        ):
            raise validation_error(
                "A sales-order-based GIN line requires its exact source "
                "sales-order line."
            )

        if (
            self.source_invoice_line_id
            and self.goods_issued_note.invoice_id
            and self.source_invoice_line.invoice_id != self.goods_issued_note.invoice_id
        ):
            raise validation_error(
                "The source invoice line does not belong to the GIN invoice."
            )

        if (
            self.source_purchase_order_line_id
            and self.goods_issued_note.purchase_order_id
            and self.source_purchase_order_line.purchase_order_id
            != self.goods_issued_note.purchase_order_id
        ):
            raise validation_error(
                "The source sales-order line does not belong to the GIN sales order."
            )

        source_line = self.source_invoice_line or self.source_purchase_order_line
        if source_line and source_line.line_item_id != self.line_item_id:
            raise validation_error(
                "The GIN item must match its commercial source line."
            )

        if self.line_item_id and self.line_item.inventory_item.item_type != "GOODS":
            raise validation_error(
                "Only GOODS items can be added to a Goods Issued Note."
            )

    def save(self, *args, **kwargs):
        self.full_clean()
        return super().save(*args, **kwargs)

    def __str__(self):
        return f"Line item for {self.goods_issued_note.reference_code}"

    class Meta:
        verbose_name = "Goods Issued Note Line Item"
        verbose_name_plural = "Goods Issued Note Line Items"

        indexes = [
            models.Index(
                fields=["line_item", "goods_issued_note"], name="idx_gin_lineitem_item"
            ),
        ]

    def __str__(self):
        return f"Line item for {self.goods_issued_note.reference_code}"

    class Meta:
        verbose_name = "Goods Issued Note Line Item"
        verbose_name_plural = "Goods Issued Note Line Items"

        indexes = [
            models.Index(
                fields=["line_item", "goods_issued_note"], name="idx_gin_lineitem_item"
            ),
        ]
