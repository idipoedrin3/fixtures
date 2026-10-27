from decimal import Decimal

from django.db import models
from approval.models import BaseApprovableModel, Approval
from django.db import transaction
from django.db.models import Q
from utilities.utility_base_model import SoftDeletableTimeStampedModel
from reports.mixins import ReportableModelMixin


class Lender(ReportableModelMixin, BaseApprovableModel):
    institution = models.ForeignKey(
        "institution.Institution",
        on_delete=models.CASCADE,
        related_name="lenders",
    )
    name = models.CharField(max_length=255)

    search_fields = ["name"]
    ordering_fields = ["name", "created_at"]

    class Meta:
        verbose_name = "Lender"
        verbose_name_plural = "Lenders"
        ordering = ["name"]
        constraints = [
            models.UniqueConstraint(
                fields=["institution", "name"],
                condition=Q(deleted_at__isnull=True),
                name="unique_undeleted_lender_name_per_institution",
            ),
        ]

    def __str__(self):
        return self.name

    def get_institution(self):
        return self.institution

    @transaction.atomic
    def finish_workflow(self, approval: Approval):
        super().finish_workflow(approval)
        if (
            approval.status == "completed"
            and approval.action.name in ["create", "update"]
        ) or (
            approval.status == "rejected"
            and approval.action.name in ["update", "delete"]
        ):
            self.save()

    @transaction.atomic
    def confirm_delete(self, **kwargs):
        from .services import LenderService

        LenderService.validate_delete(self)
        return super().confirm_delete(**kwargs)

    @transaction.atomic
    def delete(self, *args, **kwargs):
        from .services import LenderService

        if self.pk is not None:
            LenderService.validate_delete(self)
        return super().delete(*args, **kwargs)


class Loan(BaseApprovableModel):
    reference_prefix = "LN"

    class Direction(models.TextChoices):
        INFLOW = "inflow", "Inflow"
        OUTFLOW = "outflow", "Outflow"

    class InterestMethod(models.TextChoices):
        FLAT = "flat", "Flat Rate"
        REDUCING = "reducing", "Reducing Balance"

    class InterestType(models.TextChoices):
        SIMPLE = "simple", "Simple Interest"
        COMPOUND = "compound", "Compound Interest"

    class DayCountConvention(models.TextChoices):
        ACTUAL_365 = "actual_365", "Actual/365 Fixed"
        ACTUAL_360 = "actual_360", "Actual/360"
        ACTUAL_ACTUAL_ISDA = "actual_actual_isda", "Actual/Actual ISDA"

    class RepaymentStructure(models.TextChoices):
        PERIODIC = "periodic", "Periodic Repayment"
        SINGLE = "single", "Single Repayment"

    class RepaymentFrequency(models.TextChoices):
        DAILY = "daily", "Daily"
        WEEKLY = "weekly", "Weekly"
        BIWEEKLY = "biweekly", "Biweekly"
        MONTHLY = "monthly", "Monthly"
        QUARTERLY = "quarterly", "Quarterly"
        SEMIANNUALLY = "semiannually", "Semiannually"
        ANNUALLY = "annually", "Annually"

    class RepaymentTiming(models.TextChoices):
        BEGINNING = "beginning", "Beginning of Period"
        END = "end", "End of Period"

    class RepaymentMethod(models.TextChoices):
        EQUAL_INSTALLMENTS = "equal_installments", "Equal Instalments"
        EQUAL_PRINCIPAL = "equal_principal", "Equal Principal"

    class Status(models.TextChoices):
        PENDING = "pending", "Pending"
        APPROVED = "approved", "Approved"
        REJECTED = "rejected", "Rejected"

    class InitialAccountingTreatment(models.TextChoices):
        NEW_CASH = "new_cash", "New disbursement or receipt"
        HISTORICAL_CASH = "historical_cash", "Historical cash transaction to post"
        OPENING_BALANCE = "opening_balance", "Opening balance conversion"
        ALREADY_RECORDED = "already_recorded", "Already represented in the ledger"

    institution = models.ForeignKey(
        "institution.Institution",
        on_delete=models.CASCADE,
        related_name="loans",
    )

    branch = models.ForeignKey(
        "institution.Branch",
        on_delete=models.PROTECT,
        related_name="loans",
        blank=True,
        null=True,
    )

    direction = models.CharField(
        max_length=10,
        choices=Direction.choices,
        help_text="The direction of the loan.",
    )

    party_content_type = models.ForeignKey(
        "contenttypes.ContentType",
        on_delete=models.PROTECT,
        related_name="loan_party_content_type",
        help_text="The content type of the party associated with the loan.",
    )

    party_object_uuid = models.UUIDField(
        help_text="The UUID of the party associated with the loan.",
    )

    currency = models.ForeignKey(
        "institution.InstitutionSupportedCurrency",
        on_delete=models.PROTECT,
        related_name="loans",
        help_text="The currency of the loan.",
    )

    principal = models.DecimalField(
        max_digits=50,
        decimal_places=20,
        help_text="The principal amount of the loan.",
    )

    annual_interest_rate = models.DecimalField(
        max_digits=5,
        decimal_places=2,
        help_text="The annual interest rate of the loan.",
    )

    interest_method = models.CharField(
        max_length=20,
        choices=InterestMethod.choices,
        help_text="The method used to calculate interest on the loan.",
    )

    interest_type = models.CharField(
        max_length=20,
        choices=InterestType.choices,
        help_text="The type of interest used to calculate interest on the loan.",
    )

    day_count_convention = models.CharField(
        max_length=20,
        choices=DayCountConvention.choices,
        blank=True,
        null=True,
        help_text="Select the contractual day-count convention before generating schedules.",
    )

    repayment_structure = models.CharField(
        max_length=20,
        choices=RepaymentStructure.choices,
        help_text="The repayment structure of the loan.",
    )

    repayment_frequency = models.CharField(
        max_length=20,
        choices=RepaymentFrequency.choices,
        help_text="The frequency of repayments for the loan.",
        blank=True,
        null=True,
    )

    repayment_method = models.CharField(
        max_length=20,
        choices=RepaymentMethod.choices,
        blank=True,
        null=True,
        help_text="The method used to calculate periodic repayments.",
    )

    repayment_timing = models.CharField(
        max_length=20,
        choices=RepaymentTiming.choices,
        blank=True,
        null=True,
        help_text="The timing of repayments for the loan.",
    )

    disbursement_date = models.DateField(
        help_text="The disbursement date of the loan.",
    )

    first_repayment_date = models.DateField(
        help_text="The date of the first repayment of the loan.",
    )

    maturity_date = models.DateField(
        help_text="The maturity date of the loan.",
    )

    status = models.CharField(
        max_length=20,
        choices=Status.choices,
        default=Status.PENDING,
        help_text="The status of the loan.",
    )

    are_initial_journal_entries_processed = models.BooleanField(
        default=False,
        help_text="Indicates whether the initial journal entries for the loan have been processed.",
    )

    initial_accounting_treatment = models.CharField(
        max_length=20,
        choices=InitialAccountingTreatment.choices,
        blank=True,
        null=True,
        help_text="Explicit treatment required before initial accounting is confirmed.",
    )

    initial_accounting_date = models.DateField(
        blank=True,
        null=True,
        help_text="Actual transaction date or opening balance conversion date.",
    )

    opening_principal = models.DecimalField(
        max_digits=50,
        decimal_places=20,
        blank=True,
        null=True,
        help_text="Outstanding principal at the conversion date, not original principal.",
    )

    opening_balance_account = models.ForeignKey(
        "accounts.Account",
        on_delete=models.PROTECT,
        related_name="loans_as_opening_balance_account",
        blank=True,
        null=True,
        help_text="Validated offset account for a non-cash conversion entry.",
    )

    initial_journal = models.ForeignKey(
        "transactions.Transaction",
        on_delete=models.PROTECT,
        related_name="loans_as_initial_journal",
        blank=True,
        null=True,
        help_text="Journal posted or verified for the initial accounting event.",
    )

    initial_accounting_reference = models.TextField(
        blank=True,
        help_text="Supporting ledger or conversion reference for historical balances.",
    )

    cash_account = models.ForeignKey(
        "accounts.Account",
        on_delete=models.PROTECT,
        related_name="loans_as_cash_account",
        help_text="The cash account associated with the loan.",
    )

    liability_receivable_account = models.ForeignKey(
        "accounts.Account",
        on_delete=models.PROTECT,
        related_name="loans_as_liability_receivable_account",
        help_text="The liability or receivable account associated with the loan.",
    )

    search_fields = ["reference_code", "description"]
    ordering_fields = [
        "reference_code",
        "created_at",
        "disbursement_date",
        "maturity_date",
        "principal",
    ]

    class Meta:
        verbose_name = "Loan"
        verbose_name_plural = "Loans"
        ordering = ["-created_at"]

        constraints = [
            models.CheckConstraint(
                condition=Q(principal__gte=0),
                name="loan_principal_nonnegative",
            ),
            models.CheckConstraint(
                condition=Q(annual_interest_rate__gte=0),
                name="loan_annual_interest_rate_nonnegative",
            ),
        ]

    def __str__(self):
        return f"{self.reference_code}"

    def get_institution(self):
        return self.institution

    @transaction.atomic
    def save(self, *args, **kwargs):
        from .services import LoanService

        LoanService.validate_update(self)
        self.full_clean()

        return super().save(*args, **kwargs)

    @transaction.atomic
    def delete(self, *args, **kwargs):
        from .services import LoanService

        LoanService.validate_delete(self)
        return super().delete(*args, **kwargs)

    def finish_workflow(self, approval: Approval):
        from .services import LoanRepaymentScheduleService, LoanService

        with transaction.atomic():
            completed_create_or_update = (
                approval.status == "completed"
                and approval.action.name in {"create", "update"}
            )

            if completed_create_or_update:
                LoanService.validate_configuration(self)

            super().finish_workflow(approval)

            if completed_create_or_update:
                self.status = self.Status.APPROVED
                self.save(
                    update_fields=[
                        "status",
                        "approval_status",
                        "is_active",
                        "deleted_at",
                        "original_data",
                    ]
                )
                LoanRepaymentScheduleService.create_missing_installments(self)
                self._process_initial_journal_entries()

    @transaction.atomic
    def _process_initial_journal_entries(self):
        from utilities.helpers import validation_error
        from .services import LoanInitialAccountingService

        loan = (
            type(self)._base_manager.select_for_update(of=("self",))
            .select_related("institution", "currency__currency")
            .get(pk=self.pk)
        )

        treatment = loan.initial_accounting_treatment
        cash_treatments = {
            self.InitialAccountingTreatment.NEW_CASH,
            self.InitialAccountingTreatment.HISTORICAL_CASH,
        }

        if treatment in {
            self.InitialAccountingTreatment.OPENING_BALANCE,
            self.InitialAccountingTreatment.ALREADY_RECORDED,
        }:
            return loan.initial_journal

        if treatment not in cash_treatments:
            raise validation_error(
                "Choose an initial accounting treatment before approving the loan."
            )

        if loan.are_initial_journal_entries_processed and not loan.initial_journal_id:
            raise validation_error(
                "The loan is marked as processed but has no initial journal. "
                "Reconcile the accounting record before continuing."
            )

        if loan.currency.currency_id == loan.institution.currency_id:
            exchange_rate = Decimal("1")
        else:
            raise validation_error(
                "A foreign-currency exchange rate is required before the loan "
                "can be approved and its principal journal posted."
            )

        journal = LoanInitialAccountingService.post_cash_transaction(
            loan,
            funds_confirmed=True,
            exchange_rate=exchange_rate,
            created_by=None,
        )
        journal.refresh_from_db()
        processed = (
            journal.transaction_status == "posted"
            and journal.is_active
            and journal.deleted_at is None
        )
        type(self)._base_manager.filter(pk=loan.pk).update(
            initial_journal_id=journal.pk,
            are_initial_journal_entries_processed=processed,
        )
        self.initial_journal = journal
        self.are_initial_journal_entries_processed = processed
        return journal


class LoanRepaymentSchedule(SoftDeletableTimeStampedModel):
    class Status(models.TextChoices):
        PENDING = "pending", "Pending"
        PARTIALLY_PAID = "partially_paid", "Partially Paid"
        PAID = "paid", "Paid"
        OVERDUE = "overdue", "Overdue"
        WAIVED = "waived", "Waived"

    loan = models.ForeignKey(
        Loan,
        on_delete=models.CASCADE,
        related_name="repayment_schedules",
        help_text="The loan associated with the repayment schedule.",
    )

    installation_number = models.PositiveIntegerField(
        help_text="The installment number of the repayment schedule.",
    )

    due_date = models.DateField(
        help_text="The due date of the repayment schedule.",
    )

    opening_principal = models.DecimalField(
        max_digits=50,
        decimal_places=20,
        help_text="Outstanding principal at the start of this period.",
    )

    principal_due = models.DecimalField(
        max_digits=50,
        decimal_places=20,
        help_text="The principal amount due for the repayment schedule.",
    )

    interest_due = models.DecimalField(
        max_digits=50,
        decimal_places=20,
        help_text="The interest amount due for the repayment schedule.",
    )

    fees_due = models.DecimalField(
        max_digits=50,
        decimal_places=20,
        help_text="The fees amount due for the repayment schedule.",
    )

    status = models.CharField(
        max_length=20,
        choices=Status.choices,
        default=Status.PENDING,
        help_text="The status of the repayment schedule.",
    )

    def __str__(self):
        return f"Loan Repayment Schedule {self.installation_number} for Loan {self.loan.reference_code}"

    class Meta:
        verbose_name = "Loan Repayment Schedule"
        verbose_name_plural = "Loan Repayment Schedules"
        ordering = ["due_date"]

        constraints = [
            models.UniqueConstraint(
                fields=["loan", "installation_number"],
                name="unique_installment_per_loan",
                condition=models.Q(deleted_at__isnull=True),
            ),
            models.CheckConstraint(
                condition=Q(principal_due__gte=0),
                name="loan_schedule_principal_nonnegative",
            ),
            models.CheckConstraint(
                condition=Q(interest_due__gte=0),
                name="loan_schedule_interest_nonnegative",
            ),
            models.CheckConstraint(
                condition=Q(fees_due__gte=0),
                name="loan_schedule_fees_nonnegative",
            ),
        ]

    def save(self, *args, **kwargs):
        self.full_clean()

        return super().save(*args, **kwargs)


class LoanRepayment(BaseApprovableModel):
    reference_prefix = "LRP"

    class Status(models.TextChoices):
        PENDING = "pending", "Pending"
        COMPLETED = "completed", "Completed"
        REJECTED = "rejected", "Rejected"

    class AccountingTreatment(models.TextChoices):
        CASH = "cash", "Current cash transaction to post"
        HISTORICAL_CASH = "historical_cash", "Historical cash transaction to post"
        ALREADY_RECORDED = "already_recorded", "Already represented in the ledger"

    status = models.CharField(
        max_length=20,
        choices=Status.choices,
        default=Status.PENDING,
    )

    accounting_treatment = models.CharField(
        max_length=20,
        choices=AccountingTreatment.choices,
        blank=True,
        null=True,
        help_text="Explicit treatment required before repayment processing.",
    )

    journal = models.ForeignKey(
        "transactions.Transaction",
        on_delete=models.PROTECT,
        related_name="loan_repayments",
        blank=True,
        null=True,
        help_text="Journal posted or verified for this actual repayment.",
    )

    accounting_reference = models.TextField(
        blank=True,
        help_text="Supporting reference for a repayment already recorded in the ledger.",
    )

    loan = models.ForeignKey(
        Loan,
        on_delete=models.CASCADE,
        related_name="repayments",
        help_text="The loan associated with the repayment.",
    )

    date = models.DateField(
        help_text="The date of the loan repayment.",
    )

    amount = models.DecimalField(
        max_digits=50,
        decimal_places=20,
        help_text="The amount of the loan repayment.",
    )

    allocations_snapshot = models.JSONField(
        blank=True,
        null=True,
        editable=False,
        help_text="Allocations held while an update awaits approval.",
    )

    search_fields = ["reference_code", "accounting_reference"]
    ordering_fields = ["date", "amount", "created_at", "reference_code"]

    def __str__(self):
        return f"Loan Repayment of {self.amount} for Loan {self.loan.reference_code} on {self.date}"

    class Meta:
        verbose_name = "Loan Repayment"
        verbose_name_plural = "Loan Repayments"
        ordering = ["-created_at"]

        constraints = [
            models.CheckConstraint(
                condition=Q(amount__gte=0),
                name="loan_repayment_amount_nonnegative",
            ),
        ]

    def get_institution(self):
        return self.loan.institution

    def save(self, *args, **kwargs):
        self.full_clean()

        return super().save(*args, **kwargs)

    def finish_workflow(self, approval: Approval):
        from .services import LoanRepaymentService

        action = approval.action.name
        with transaction.atomic():
            super().finish_workflow(approval)
            if approval.status == "completed" and action in ["create", "update"]:
                if action == "create":
                    self.status = self.Status.COMPLETED
                self.allocations_snapshot = None
                self.save(
                    update_fields=[
                        "status",
                        "approval_status",
                        "is_active",
                        "deleted_at",
                        "original_data",
                        "allocations_snapshot",
                    ]
                )
            elif approval.status == "rejected" and action == "create":
                LoanRepayment._base_manager.filter(pk=self.pk).update(
                    status=self.Status.REJECTED
                )
            elif approval.status == "rejected" and action == "update":
                self.save()
                LoanRepaymentService.restore_allocations(self)
            LoanRepaymentService.refresh_schedule_statuses(self.loan)

    @transaction.atomic
    def confirm_delete(self, **kwargs):
        from .services import LoanRepaymentService

        LoanRepaymentService.validate_delete(self)
        return super().confirm_delete(**kwargs)


class LoanPaymentAllocation(SoftDeletableTimeStampedModel):
    payment = models.ForeignKey(
        "loan_mgt.LoanRepayment",
        on_delete=models.PROTECT,
        related_name="allocations",
    )

    repayment_schedule = models.ForeignKey(
        "loan_mgt.LoanRepaymentSchedule",
        on_delete=models.PROTECT,
        related_name="payment_allocations",
        blank=True,
        null=True,
        help_text=(
            "The scheduled instalment this allocation settles, " "if applicable."
        ),
    )

    principal_amount = models.DecimalField(
        max_digits=50,
        decimal_places=20,
        default=0,
        help_text="The portion applied to principal.",
    )

    interest_amount = models.DecimalField(
        max_digits=50,
        decimal_places=20,
        default=0,
        help_text="The portion applied to interest.",
    )

    fee_amount = models.DecimalField(
        max_digits=50,
        decimal_places=20,
        default=0,
        help_text="The portion applied to fees.",
    )

    class Meta:
        verbose_name = "Loan Payment Allocation"
        verbose_name_plural = "Loan Payment Allocations"
        constraints = [
            models.CheckConstraint(
                condition=(
                    Q(principal_amount__gte=0)
                    & Q(interest_amount__gte=0)
                    & Q(fee_amount__gte=0)
                ),
                name="loan_payment_allocation_nonnegative",
            ),
            models.CheckConstraint(
                condition=(
                    Q(principal_amount__gt=0)
                    | Q(interest_amount__gt=0)
                    | Q(fee_amount__gt=0)
                ),
                name="loan_payment_allocation_positive",
            ),
        ]

    @property
    def amount(self):
        return self.principal_amount + self.interest_amount + self.fee_amount

    def __str__(self):
        return f"Allocation for {self.payment} - " f"{self.amount}"