from django.db import models
from datetime import time, datetime
from approval.models import BaseApprovableModel, Approval
from django.utils import timezone
from django.db import transaction
from utilities.common_models import BaseTimeStamp
from utilities.email_client import EmailClient
from reports.mixins import ReportableModelMixin
from utilities.helpers import validation_error
from utilities.utility_base_model import SoftDeletableTimeStampedModel
from django.contrib.contenttypes.models import ContentType
from django.contrib.contenttypes.fields import GenericForeignKey
from system.models import SystemFeature, SystemIndustry, SystemKYCDocumentCategory
from decimal import Decimal
from django.conf import settings
from users.models import ExternalIdentity, Role, RolePermission, Permission
from django.core import serializers
from django.core.validators import MaxValueValidator, MinValueValidator
from pytz import common_timezones


class DepositDistributionStrategy(models.TextChoices):
    PAY_OLDEST_INVOICE_FIRST = "PAY_OLDEST_INVOICE_FIRST", "Pay Oldest Invoice First"
    PAY_LAST_INVOICE_FIRST = "PAY_LAST_INVOICE_FIRST", "Pay Latest Invoice First"
    HOLD_AS_CREDIT = "HOLD_AS_CREDIT", "Hold as Customer Credit"


class InstitutionInventoryReductionTiming(models.TextChoices):
    ON_INVOICE = "ON_INVOICE", "Reduce stock on Invoice issuance"
    ON_GIN = "ON_GIN", "Reduce stock on Goods Issued Note creation (GIN)"


class InstitutionInventoryIncrementTiming(models.TextChoices):
    ON_BILL_RECEIPT = (
        "ON_BILL_RECEIPT",
        "Increase stock on Bill Receipt",
    )
    ON_GRN = "ON_GRN", "Increase stock on Goods Received Note creation (GRN)"


class UnitBreakdownStrategy(models.TextChoices):
    SMALLEST_ONLY = (
        "SMALLEST_ONLY",
        "Break to smallest unit directly (e.g. always Pieces)",
    )
    LARGEST_FIRST = (
        "LARGEST_FIRST",
        "Break to largest intermediaries first (e.g. Dozens, then Pieces)",
    )


class Institution(SoftDeletableTimeStampedModel):
    APPROVAL_STATUS_CHOICES = [
        ("pending", "Pending Approval"),
        ("approved", "Approved"),
        ("rejected", "Rejected"),
        ("under_review", "Under Review"),
        ("suspended", "Suspended"),
    ]

    DATE_FORMAT_CHOICES = [
        ("dd/mm/yy", "DD/MM/YY (e.g., 27/10/25)"),
        ("mm/dd/yy", "MM/DD/YY (e.g., 10/27/25)"),
        ("yy/mm/dd", "YY/MM/DD (e.g., 25/10/27)"),
    ]

    ACCOUNTING_METHOD_CHOICES = [
        ("Accrual", "Accrual-Based"),
        ("Cash", "Cash-Based"),
    ]

    industry = models.ForeignKey(
        SystemIndustry,
        on_delete=models.SET_NULL,
        related_name="institutions",
        null=True,
        blank=True,
    )

    accounting_method = models.CharField(
        max_length=20,
        choices=ACCOUNTING_METHOD_CHOICES,
        default="Accrual",
        null=True,
        blank=True,
    )

    timezone = models.CharField(
        max_length=120,
        default="UTC",
        choices=[(tz, tz) for tz in common_timezones],
    )

    institution_owner = models.ForeignKey(
        "users.CustomUser", related_name="institutions_owned", on_delete=models.CASCADE
    )
    institution_email = models.EmailField(max_length=255, blank=True, null=True)
    institution_name = models.CharField(max_length=255)
    # new
    institution_legal_name = models.CharField(max_length=255, blank=True, null=True)
    first_phone_number = models.CharField(max_length=20, blank=True, null=True)
    second_phone_number = models.CharField(max_length=20, blank=True, null=True)
    institution_logo = models.ImageField(
        upload_to="institutions/images/", blank=True, null=True
    )

    theme_color = models.CharField(max_length=400, blank=True, null=True)
    # new
    website = models.URLField(blank=True, null=True)

    # Location fields
    location = models.CharField(max_length=500, blank=True, null=True)
    latitude = models.FloatField(blank=True, null=True)
    longitude = models.FloatField(blank=True, null=True)
    # location_geodjango = gis_models.PointField(geography=True, null=True, blank=True)
    user_inactivity_time = models.PositiveIntegerField(
        default=15, help_text="User inactivity time in minutes before automatic logout"
    )

    # new
    support_auto_settlement_of_invoices = models.BooleanField(
        default=False,
        help_text="Automatically settle customer balances when deposits are made.",
    )
    deposit_distribution_strategy = models.CharField(
        max_length=50,
        choices=DepositDistributionStrategy.choices,
        default=DepositDistributionStrategy.PAY_OLDEST_INVOICE_FIRST,
    )

    inventory_reduction_timing = models.CharField(
        max_length=20,
        choices=InstitutionInventoryReductionTiming.choices,
        default=InstitutionInventoryReductionTiming.ON_GIN,
    )
    inventory_increment_timing = models.CharField(
        max_length=20,
        choices=InstitutionInventoryIncrementTiming.choices,
        default=InstitutionInventoryIncrementTiming.ON_GRN,
    )

    approval_status = models.CharField(
        max_length=20,
        choices=APPROVAL_STATUS_CHOICES,
        default="pending",
    )
    date_format = models.CharField(
        max_length=20,
        choices=DATE_FORMAT_CHOICES,
        default="dd/mm/yy",
        help_text="Preferred date format for the institution",
    )
    approval_date = models.DateTimeField(blank=True, null=True)
    approved_by = models.ForeignKey(
        "users.CustomUser",
        related_name="approved_institutions",
        on_delete=models.CASCADE,
        blank=True,
        null=True,
    )
    rejection_reason = models.TextField(blank=True, null=True)
    suspension_reason = models.TextField(blank=True, null=True)

    currency = models.ForeignKey(
        "system.SystemCurrency", on_delete=models.CASCADE, null=True, blank=True
    )
    is_sales_person_commission_enabled = models.BooleanField(default=False)
    commission_percentage = models.DecimalField(
        max_digits=5, decimal_places=2, blank=True, null=True, default=0.00
    )

    fiscal_year_start_month = models.IntegerField(default=1)
    fiscal_period_type = models.CharField(
        max_length=20,
        choices=[
            ("monthly", "Monthly"),
            ("quarterly", "Quarterly"),
            ("half_year", "Half Yearly"),
            ("annual", "Annual"),
        ],
        default="monthly",
    )

    maximum_cashbook_topup_amount = models.DecimalField(
        max_digits=50, decimal_places=20, default=0
    )

    default_invoice_due_days = models.PositiveIntegerField(default=30)

    is_tax_filing_automated = models.BooleanField(default=False)

    default_pagination_page_size = models.IntegerField(
        blank=True, null=True, default=20
    )
    financial_document_expiry_notification_days = models.PositiveIntegerField(
        blank=True,
        null=True,
        default=30,
        help_text="Number of days before expiry to send a document notification.",
    )
    supports_multiple_currencies = models.BooleanField(default=False)
    supported_currencies = models.ManyToManyField(
        "system.SystemCurrency",
        through="InstitutionSupportedCurrency",
        through_fields=("institution", "currency"),
        related_name="institutions_with_currency",
        blank=True,
    )

    default_stock_valuation_method = models.ForeignKey(
        "system.SystemStockValuationMethod",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
    )

    default_stock_movement_strategy = models.ForeignKey(
        "system.SystemStockMovementStrategy",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
    )

    supports_sales_returns = models.BooleanField(default=False)
    minimal_days_for_sales_return = models.IntegerField(
        blank=True,
        null=True,
    )
    enable_cash_refund_for_item_return = models.BooleanField(default=False)

    deposit_distribution_strategy = models.CharField(
        max_length=50,
        choices=DepositDistributionStrategy.choices,
        default=DepositDistributionStrategy.PAY_OLDEST_INVOICE_FIRST,
    )

    kyc_documents = models.ManyToManyField(
        SystemKYCDocumentCategory,
        through="InstitutionKYCDocument",
        related_name="institutions",
        blank=True,
    )

    # new
    business_registration_number = models.CharField(
        max_length=100,
        blank=True,
        null=True,
        help_text="Official business registration number of the institution.",
    )
    # new
    tax_identification_number = models.CharField(
        max_length=100,
        blank=True,
        null=True,
        help_text="Tax identification number for tax reporting purposes. e.g., TIN, PAN, SSN, TFN.",
    )

    # new
    offering_type = models.CharField(
        max_length=100,
        default="PRODUCT_AND_SERVICE",
        choices=[
            ("PRODUCTS_ONLY", "Products Only"),
            ("SERVICES_ONLY", "Services Only"),
            ("PRODUCTS_AND_SERVICES", "Both Product and Service"),
        ],
    )

    description = models.TextField(blank=True, null=True)

    # new
    business_start_date = models.DateField(
        blank=True,
        null=True,
        help_text="The date when the business was officially started or registered.",
    )

    allow_sales_out_of_stock = models.BooleanField(
        default=False,
        help_text=(
            "If True, this institution allows selling inventory items "
            "even when they are out of stock."
        ),
    )

    business_organisation = models.ForeignKey(
        "system.SystemSupportedBusinessOrganisation",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        help_text="The legal structure of the business organization.",
    )

    quotation_default_expiry_days = models.PositiveIntegerField(default=30)

    unit_breakdown_strategy = models.CharField(
        max_length=20,
        choices=UnitBreakdownStrategy.choices,
        default=UnitBreakdownStrategy.SMALLEST_ONLY,
        help_text=(
            "When a larger stock unit (e.g. Carton) is broken open to fulfil a "
            "sale of smaller units (e.g. Pieces), this controls what units the "
            "leftover quantity is stored as.\n\n"
            "SMALLEST_ONLY: all remainder → Pieces (simple, maximally granular).\n"
            "LARGEST_FIRST: remainder → Dozens first, then Pieces (fewer fragments, "
            "but subsequent sales of Pieces may trigger further breakdowns)."
        ),
    )

    allow_unit_breakdown = models.BooleanField(default=False)

    are_notifications_enabled = models.BooleanField(
        default=False,
        help_text="Master toggle to enable or disable all notifications for this institution.",
    )

    notification_settings = models.ManyToManyField(
        "system.SystemNotification",
        blank=True,
        related_name="notifications",
        through="InstitutionNotificationSetting",
    )

    auto_depreciation_enabled = models.BooleanField(
        default=False,
    )

    allow_item_reuse_across_templates = models.BooleanField(
        default=False,
        help_text="Permits reuse or attachment of a single requisition item across multiple requisition templates.",
    )

    cash_account_reconciliation_automatch_threshold_percent = models.DecimalField(
        max_digits=5,
        decimal_places=2,
        blank=True,
        null=True,
        validators=[
            MinValueValidator(Decimal("0")),
            MaxValueValidator(Decimal("100")),
        ],
        help_text=(
            "Optional reconciliation auto-match threshold percentage. "
            "Uses the system setting when left blank."
        ),
    )

    require_statement_for_cash_account_reconciliation = models.BooleanField(
        default=True,
        help_text="Require a statement to be uploaded when reconciling a cash account.",
    )

    should_vendor_payments_go_through_requisitions = models.BooleanField(
        default=False,
        help_text="If True, all vendor payments will auto create a requisition that needs approval and its after the approval and the payment  that the vendor payment will be marked as payment. If False, vendor payments will be independent of requisitions and will go through the normal approval process.",
    )

    class Meta:
        unique_together = ("institution_owner", "institution_name")

    class Meta:
        unique_together = ("institution_owner", "institution_name")

    def __str__(self):
        return self.institution_name

    @property
    def is_approved(self):
        return self.approval_status == "approved"

    def get_institution_bin(self):
        bin_obj, _ = RecycleBin.objects.get_or_create(institution=self)
        return bin_obj

    def create_default_role(self):
        if not self.is_approved:
            return None

        default_role = Role.objects.filter(
            institution=self, name="Default Role"
        ).first()
        if default_role:
            return default_role

        import json
        from django.db import transaction
        from django.conf import settings

        DEFAULT_PERMISSIONS_PATH = (
            settings.BASE_DIR / "users" / "fixtures" / "default_role_permissions.json"
        )

        with open(DEFAULT_PERMISSIONS_PATH, "r") as file:
            data = json.load(file)

        permission_codes = []
        for perms in data.values():
            permission_codes.extend([perm["code"] for perm in perms])

        permissions = Permission.objects.filter(permission_code__in=permission_codes)

        with transaction.atomic():
            default_role = Role.objects.create(
                name="Default Role",
                description="Automatically created default role with default permissions",
                institution=self,
            )

            RolePermission.objects.bulk_create(
                [RolePermission(role=default_role, permission=p) for p in permissions]
            )

        return default_role

    def save(self, *args, **kwargs):
        standalone_mode = kwargs.pop("standalone_mode", None)
        skip_main_branch_creation = kwargs.pop("skip_main_branch_creation", False)

        is_new = self._state.adding
        previous_status = None

        if not is_new and self.pk:
            previous_status = (
                Institution.objects.filter(pk=self.pk)
                .values_list("approval_status", flat=True)
                .first()
            )

        super().save(*args, **kwargs)

        if is_new:
            try:
                from taxation.utils import (
                    create_default_taxes_for_institution_based_on_location,
                )

                create_default_taxes_for_institution_based_on_location(self)
            except ImportError as e:
                import logging

                logger = logging.getLogger(__name__)
                logger.warning(f"Could not import tax helper: {e}")

            if not self.currency_id:
                try:
                    from utilities.currency_mapping import (
                        assign_default_currency_to_institution,
                    )

                    assign_default_currency_to_institution(self)
                except ImportError as e:
                    import logging

                    logger = logging.getLogger(__name__)
                    logger.error(f"Could not import currency helper: {e}")

            if self.currency_id:
                InstitutionSupportedCurrency.objects.get_or_create(
                    institution=self,
                    currency=self.currency,
                    defaults={"rate": Decimal("1.0")},
                )

            try:
                from requisitions.utils import get_or_create_payroll_requisition_type

                get_or_create_payroll_requisition_type(self)
            except ImportError:
                pass

            self.create_default_role()
            self.create_institution_feature_statuses()
            self.set_owner_user_work_place()

            if not skip_main_branch_creation:
                self.create_main_branch()

            # self._create_institution_industry_coa()

            self.auto_approve_if_external_identity()

            if standalone_mode:
                self._inform_mgt_on_institution_creation()
                self._inform_owner_on_institution_creation()

            self._create_default_approval_categories()

        else:
            if (
                not self.owner_has_external_identity()
                and previous_status != self.approval_status
            ):
                self._inform_owner_on_status_change(previous_status)

    def _create_default_approval_categories(self):
        from approval.models import ApprovalDocumentCategory

        DEFAULT_CATEGORIES = [
            {
                "name": "Approve",
                "description": "The classification where initial approval takes place after submission.",
                "code": "review",
                "level": 1,
            },
            {
                "name": "Authorise",
                "description": "The classification responsible for final authorisation after approval.",
                "code": "approve",
                "level": 2,
            },
        ]

        existing = set(
            ApprovalDocumentCategory.objects.filter(
                institution=self,
                deleted_at__isnull=True,
            ).values_list("reference_code", flat=True)
        )

        to_create = [
            ApprovalDocumentCategory(
                institution=self,
                name=cat["name"],
                description=cat["description"],
                reference_code=cat["code"],
                level=cat["level"],
            )
            for cat in DEFAULT_CATEGORIES
            if cat["code"] not in existing
        ]

        if to_create:
            ApprovalDocumentCategory.objects.bulk_create(to_create)

    def auto_approve_if_external_identity(self):
        if self.owner_has_external_identity():
            old_status = self.approval_status
            self.approval_status = "approved"
            super().save(update_fields=["approval_status"])
            self._inform_owner_on_status_change(old_status)

    def owner_has_external_identity(self) -> bool:
        return ExternalIdentity.objects.filter(
            user=self.institution_owner, institution=self
        ).exists()

    def can_apply_invoice_taxes(self):
        return self.invoice_taxes.filter(
            is_active=True,
            institution=self,
        ).exists()

    def create_institution_feature_statuses(self):
        system_features = SystemFeature.objects.filter(is_active=True)
        statuses = [
            InstitutionFeatureStatus(
                institution=self,
                system_feature=sf,
                is_enabled=True,
            )
            for sf in system_features
        ]

        if statuses:
            InstitutionFeatureStatus.objects.bulk_create(
                statuses, ignore_conflicts=True
            )

    def create_main_branch(self):
        Branch.objects.create(
            institution=self,
            branch_name=f"{self.institution_name} Main Branch",
            branch_phone_number=self.first_phone_number,
            branch_location=self.location,
            branch_email=self.institution_email,
            created_by=self.created_by,
        )

    def set_owner_user_work_place(self):
        from users.models import Profile

        user = self.institution_owner
        profile, created = Profile.objects.get_or_create(user=user)
        profile.institution = self
        profile.save()

    def _create_institution_industry_coa(self):
        from accounts.utils import create_industry_specific_coa_for_institution

        create_industry_specific_coa_for_institution(self)

    def _inform_mgt_on_institution_creation(self):
        # TODO It will have attachments, those are the KYC Docs
        EmailClient.send(
            subject="New Institution Created",
            recipients=[settings.DEFAULT_MGT_EMAIL],
            template_html="emails/institution_creation_email.html",
            context={
                "institution_reference_code": self.reference_code,
                "institution_name": self.institution_name,
                "institution_email": self.institution_email,
                "institution_owner_fullname": self.institution_owner.fullname,
                "institution_owner_email": (
                    self.institution_owner.email if self.institution_owner else None
                ),
                "institution_owner_phone_number": (
                    self.institution_owner.phone_number
                    if self.institution_owner
                    else None
                ),
                "institution_industry_name": (
                    self.industry.industry_name if self.industry else None
                ),
                "institution_industry_code": (
                    self.industry.industry_code if self.industry else None
                ),
                "institution_location": self.location if self.location else None,
                "institution_currency": self.currency.code if self.currency else None,
                "institution_fiscal_year_start_month": self.fiscal_year_start_month,
                "current_year": datetime.now().year,
            },
        )

    def _inform_owner_on_institution_creation(self):
        EmailClient.send(
            subject="Your Institution Has Been Created",
            recipients=[self.institution_owner.email],
            template_html="emails/institution_owner_creation_email.html",
            context={
                "institution_name": self.institution_name,
                "approval_status": self.approval_status,
                "owner_fullname": self.institution_owner.fullname,
                "current_year": datetime.now().year,
            },
        )

    def _inform_owner_on_status_change(self, old_status):
        EmailClient.send(
            subject=f"Institution Status Update: {self.approval_status.title()}",
            recipients=[self.institution_owner.email],
            template_html="emails/institution_status_update_email.html",
            context={
                "institution_name": self.institution_name,
                "owner_fullname": self.institution_owner.fullname,
                "old_status": old_status,
                "new_status": self.approval_status,
                "rejection_reason": self.rejection_reason,
                "suspension_reason": self.suspension_reason,
                "current_year": datetime.now().year,
            },
        )

    def get_current_fiscal_year(self):
        return self.fiscal_years.filter(
            deleted_at__isnull=True,
            is_current=True,
            is_closed=False,
        ).first()

    def is_ugandan_situated(self):
        if self.currency and self.currency.code.upper() == "UGX":
            return True

        if self.location and "uganda" in self.location.lower():
            return True

        return False


class InstitutionBaisoftPayConfiguration(SoftDeletableTimeStampedModel):
    institution = models.ForeignKey(
        Institution,
        on_delete=models.CASCADE,
        related_name="baisoftpay_configurations",
    )

    branch = models.ForeignKey(
        "institution.Branch",
        on_delete=models.CASCADE,
        related_name="baisoftpay_configurations",
        null=True,
        blank=True,
        help_text=(
            "Leave blank to use these credentials as the institution-wide "
            "BaisoftPay configuration."
        ),
    )

    encrypted_api_key = models.TextField()
    encrypted_signing_key = models.TextField()

    last_verified_at = models.DateTimeField(
        null=True,
        blank=True,
    )

    class Meta:
        verbose_name = "Institution BaisoftPay Configuration"
        verbose_name_plural = "Institution BaisoftPay Configurations"
        ordering = ["branch__branch_name"]
        constraints = [
            models.UniqueConstraint(
                fields=["institution"],
                condition=models.Q(
                    branch__isnull=True,
                    deleted_at__isnull=True,
                ),
                name="unique_institution_baisoftpay_configuration",
            ),
            models.UniqueConstraint(
                fields=["institution", "branch"],
                condition=models.Q(
                    branch__isnull=False,
                    deleted_at__isnull=True,
                ),
                name="unique_branch_baisoftpay_configuration",
            ),
        ]

    def __str__(self):
        scope = self.branch.branch_name if self.branch_id else "Institution default"
        return f"{self.institution.institution_name} - BaisoftPay - {scope}"

    def get_institution(self):
        return self.institution

    @property
    def api_key(self):
        from institution.services import (
            InstitutionCredentialEncryptionService,
        )

        return InstitutionCredentialEncryptionService.decrypt(self.encrypted_api_key)

    @property
    def signing_key(self):
        from institution.services import (
            InstitutionCredentialEncryptionService,
        )

        return InstitutionCredentialEncryptionService.decrypt(
            self.encrypted_signing_key
        )

    @property
    def has_api_key(self):
        return bool(self.encrypted_api_key)

    @property
    def has_signing_key(self):
        return bool(self.encrypted_signing_key)

    def set_api_key(self, value):
        from institution.services import (
            InstitutionCredentialEncryptionService,
        )

        self.encrypted_api_key = InstitutionCredentialEncryptionService.encrypt(value)

    def set_signing_key(self, value):
        from institution.services import (
            InstitutionCredentialEncryptionService,
        )

        self.encrypted_signing_key = InstitutionCredentialEncryptionService.encrypt(
            value
        )

    def set_credentials(self, *, api_key=None, signing_key=None):
        if api_key is not None:
            self.set_api_key(api_key)

        if signing_key is not None:
            self.set_signing_key(signing_key)

    def clean(self):
        super().clean()

        if self.branch_id and self.branch.institution_id != self.institution_id:
            raise validation_error(
                {
                    "branch": (
                        "The selected branch must belong to the same " "institution."
                    )
                }
            )

    @classmethod
    def resolve_for_wallet(cls, digital_wallet):
        configurations = (
            cls.objects.undeleted()
            .filter(
                institution=digital_wallet.institution,
                is_active=True,
            )
            .select_related("institution", "branch")
        )

        if digital_wallet.branch_id:
            branch_configuration = configurations.filter(
                branch_id=digital_wallet.branch_id,
            ).first()

            if branch_configuration:
                return branch_configuration

        return configurations.filter(branch__isnull=True).first()


class InstitutionNotificationSetting(SoftDeletableTimeStampedModel):
    institution = models.ForeignKey(
        Institution,
        on_delete=models.CASCADE,
        related_name="inst_notification_settings",
    )
    system_notification = models.ForeignKey(
        "system.SystemNotification",
        on_delete=models.CASCADE,
        related_name="inst_notification_settings",
    )

    target_users = models.ManyToManyField(
        "users.CustomUser",
        blank=True,
        related_name="notification_settings",
        help_text="Users to receive this notification when enabled",
        through="InstitutionNotificationSettingTargetUser",
        through_fields=("notification_setting", "target_user"),
    )

    is_enabled = models.BooleanField(default=True)

    class Meta:
        unique_together = ("institution", "system_notification")
        verbose_name = "Institution Notification Setting"
        verbose_name_plural = "Institution Notification Settings"
        ordering = ["-created_at"]

    def __str__(self):
        status = "Enabled" if self.is_enabled else "Disabled"
        return f"{self.institution.institution_name} - {self.system_notification.title}: {status}"

    def clean(self):
        if not self.institution.are_notifications_enabled:
            raise validation_error(
                "Cannot make changes to notification settings when notifications are disabled for the institution."
            )

    def save(self, *args, **kwargs):
        self.full_clean()
        super().save(*args, **kwargs)


class InstitutionNotificationSettingTargetUser(SoftDeletableTimeStampedModel):
    notification_setting = models.ForeignKey(
        InstitutionNotificationSetting,
        on_delete=models.CASCADE,
        related_name="target_user_links",
    )
    target_user = models.ForeignKey(
        "users.CustomUser",
        on_delete=models.CASCADE,
        related_name="notification_setting_links",
    )

    class Meta:
        unique_together = ("notification_setting", "target_user")
        verbose_name = "Institution Notification Setting Target User"
        verbose_name_plural = "Institution Notification Setting Target Users"
        ordering = ["-created_at"]

    def __str__(self):
        return f"{self.notification_setting} -> {self.target_user.fullname}"


class InstitutionSupportedPaymentOption(SoftDeletableTimeStampedModel):
    institution = models.ForeignKey(
        "institution.Institution",
        on_delete=models.CASCADE,
        related_name="supported_payment_options",
    )

    content_type = models.ForeignKey(ContentType, on_delete=models.CASCADE)
    object_id = models.PositiveIntegerField()
    payment_option = GenericForeignKey("content_type", "object_id")

    class Meta:
        unique_together = ("institution", "content_type", "object_id")

    def __str__(self):
        return f"{self.institution_id} -> {self.content_type.model} ({self.object_id})"

    def get_institution(self):
        return self.institution

    def clean(self):
        from bank_management.models import (
            BankAccount,
            MobileMoneyAccount,
            DigitalWalletAccount,
            CashAtHandAccount,
        )

        if self.content_type:
            allowed_models = [
                BankAccount,
                MobileMoneyAccount,
                DigitalWalletAccount,
                CashAtHandAccount,
            ]

            allowed_content_types = ContentType.objects.get_for_models(
                *allowed_models
            ).values()

            if self.content_type not in allowed_content_types:
                raise validation_error(
                    "Institution Supported Payment Options must be a Bank Account, Mobile Money Account, Digital Wallet Account, or Cash at Hand Account."
                )

    def save(self, *args, **kwargs):
        self.full_clean()
        super().save(*args, **kwargs)


class InstitutionSupportedCurrency(SoftDeletableTimeStampedModel):
    institution = models.ForeignKey(
        "institution.Institution",
        on_delete=models.CASCADE,
        related_name="institution_supported_currencies",
    )
    currency = models.ForeignKey(
        "system.SystemCurrency",
        on_delete=models.CASCADE,
        related_name="institution_currencies",
    )
    rate = models.DecimalField(max_digits=50, decimal_places=20, null=True, blank=True)

    format = models.CharField(
        max_length=30,
        choices=[
            ("base_to_other", "Base to Other"),
            ("other_to_base", "Other to Base"),
        ],
        default="base_to_other",
        help_text="Format indicating how rate should be interpreted",
    )

    search_fields = [
        "currency__name",
    ]

    class Meta:
        unique_together = ("institution", "currency")
        verbose_name = "Institution Supported Currency"
        verbose_name_plural = "Institution Supported Currencies"

    def __str__(self):
        rate = f"{self.rate:.6f}" if self.rate is not None else "N/A"

        if self.format == "base_to_other":
            return f" 1 {self.institution.currency.code} → {rate} {self.currency.code} by {self.institution.institution_name} using '{self.format}' format"
        else:
            return f"1 {self.currency.code} → {rate} {self.institution.currency.code} by {self.institution.institution_name} using '{self.format}' format"

    def get_institution(self):
        return self.institution

    def determine_operation(self, direction: str = None):
        if direction is None:
            direction = "from_base"

        if direction not in ("from_base", "to_base"):
            raise validation_error("Direction must be 'from_base' or 'to_base'")

        if self.format == "base_to_other":
            return "multiply" if direction == "from_base" else "divide"
        elif self.format == "other_to_base":
            return "divide" if direction == "from_base" else "multiply"
        else:
            raise validation_error("Invalid format type")

    @staticmethod
    def determine_format_and_rate(x, y, base_currency):
        # if x["value"] != 1 and y["value"] != 1:
        #     raise validation_error("One value must be 1")

        # if x["value"] == 1 and y["value"] == 1:
        #     raise validation_error("Only one value should be 1")

        if x["value"] == 1 and x["currency"] == base_currency:
            rate = Decimal(str(y["value"]))
            format_type = "base_to_other"

        elif y["value"] == 1 and y["currency"] == base_currency:
            rate = Decimal(str(x["value"]))
            format_type = "base_to_other"

        elif x["value"] == 1 and x["currency"] != base_currency:
            rate = Decimal(str(y["value"]))
            format_type = "other_to_base"

        elif y["value"] == 1 and y["currency"] != base_currency:
            rate = Decimal(str(x["value"]))
            format_type = "other_to_base"

        elif y["value"] == 1 and y["currency"] == base_currency:
            rate = Decimal(str(x["value"]))
            format_type = "base_to_other"

        elif x["value"] == 1 and x["currency"] == base_currency:
            rate = Decimal(str(y["value"]))
            format_type = "base_to_other"

        else:
            raise validation_error("Invalid configuration")

        return rate, format_type

    def represent_rate(self):
        if self.format == "base_to_other":
            return {
                "x": {"value": 1, "currency": self.institution.currency},
                "y": {"value": float(self.rate), "currency": self.currency},
            }

        else:
            return {
                "x": {"value": 1, "currency": self.currency},
                "y": {"value": float(self.rate), "currency": self.institution.currency},
            }

    def clean(self):
        super().clean()

        if self.rate is None:
            raise validation_error("Rate is required.")

        if self.rate <= 0:
            raise validation_error("Rate must be greater than zero.")

        if not self.institution:
            raise validation_error("Institution is required.")

        if not self.currency:
            raise validation_error("Currency is required.")


class InstitutionDocument(SoftDeletableTimeStampedModel):
    institution = models.ForeignKey(
        Institution, related_name="documents", on_delete=models.CASCADE
    )
    document_title = models.CharField(max_length=255)
    document_file = models.FileField(upload_to="institutions/documents/")
    document_type = models.CharField(max_length=10, blank=True, null=True)
    document_size = models.PositiveIntegerField(blank=True, null=True)

    def __str__(self):
        return f"{self.document_title} - {self.institution.institution_name}"

    class Meta:
        verbose_name = "Institution Document"
        verbose_name_plural = "Institution Documents"

    def save(self, *args, **kwargs):
        if self.document_file and not self.pk:
            self.document_size = self.document_file.size
            self.document_type = self.document_file.name.split(".")[-1].lower()
        super().save(*args, **kwargs)

    @property
    def document_size_mb(self):
        if self.document_size:
            return round(self.document_size / (1024 * 1024), 2)
        return 0


class Branch(ReportableModelMixin, SoftDeletableTimeStampedModel):
    reference_prefix = "IB"

    search_fields = [
        "branch_name",
        "branch_legal_name",
        "branch_location",
        "city",
    ]

    BRANCH_TYPE_CHOICES = [
        ("BRANCH", "Branch"),
        ("SUBSIDIARY", "Subsidiary Company"),
        ("AFFILIATE", "Affiliated Company"),
        ("DIVISION", "Internal Division"),
    ]

    STATUS_CHOICES = (
        ("operational", "Operational"),
        ("suspended", "Suspended"),
        ("closed", "Closed"),
    )
    institution = models.ForeignKey(
        Institution, related_name="branches", on_delete=models.CASCADE
    )
    parent = models.ForeignKey(
        "self",
        null=True,
        blank=True,
        on_delete=models.CASCADE,
        related_name="children",
    )
    admins = models.ManyToManyField(
        "users.CustomUser",
        blank=True,
        related_name="administered_branches",
        through="institution.BranchAdmin",
        through_fields=("branch", "admin"),
    )
    currency = models.ForeignKey(
        "system.SystemCurrency",
        related_name="branches",
        on_delete=models.CASCADE,
        blank=True,
        null=True,
    )
    supported_currencies = models.ManyToManyField(
        "system.SystemCurrency",
        through="BranchSupportedCurrency",
        through_fields=("branch", "currency"),
        related_name="branches_with_currency",
        blank=True,
    )
    branch_name = models.CharField(max_length=255, blank=True, null=True)
    branch_legal_name = models.CharField(max_length=255, blank=True, null=True)
    branch_email = models.EmailField(max_length=255, blank=True, null=True)
    branch_phone_number = models.CharField(max_length=20, blank=True, null=True)
    website = models.URLField(blank=True)

    branch_type = models.CharField(
        max_length=10, choices=BRANCH_TYPE_CHOICES, default="BRANCH"
    )
    status = models.CharField(
        max_length=20, choices=STATUS_CHOICES, default="operational"
    )

    ownership_percentage = models.DecimalField(
        max_digits=5,
        decimal_places=2,
        null=True,
        blank=True,
        help_text="Ownership percentage held by parent company",
    )

    supports_multiple_currencies = models.BooleanField(default=False)
    branch_location = models.CharField(max_length=255, blank=True, null=True)
    branch_latitude = models.FloatField(blank=True, null=True)
    branch_longitude = models.FloatField(blank=True, null=True)
    state_or_region = models.CharField(max_length=100, blank=True)
    city = models.CharField(max_length=100, blank=True)
    address = models.TextField(blank=True)
    branch_opening_time = models.TimeField(default=time(8, 0, 0))
    branch_closing_time = models.TimeField(default=time(23, 0, 0))
    registration_number = models.CharField(max_length=100, blank=True)
    tax_identification_number = models.CharField(max_length=100, blank=True)
    date_incorporated = models.DateField(null=True, blank=True)

    default_stock_valuation_method = models.ForeignKey(
        "system.SystemStockValuationMethod",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
    )

    default_stock_movement_strategy = models.ForeignKey(
        "system.SystemStockMovementStrategy",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
    )

    deposit_distribution_strategy = models.CharField(
        max_length=50,
        choices=DepositDistributionStrategy.choices,
        blank=True,
        null=True,
    )

    allow_sales_out_of_stock = models.BooleanField(
        default=False,
        help_text=(
            "If True, this branch allows selling items or services "
            "even when they are out of stock."
        ),
    )

    inventory_cost_variance_account = models.ForeignKey(
        "accounts.Account",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        help_text="Account used for inventory cost variances when negative stock is "
        "settled at a different actual cost. Falls back to item/category COGS.",
    )

    def clean(self):
        if self.parent and self.parent.branch_type == "BRANCH":
            raise validation_error("A branch cannot have child units.")

        if (
            self.branch_type in ["SUBSIDIARY", "AFFILIATE"]
            and self.ownership_percentage is None
        ):
            raise validation_error(
                "Subsidiaries and affiliates must have ownership percentage."
            )
        if self.parent_id and self.parent_id == self.id:
            raise validation_error("A branch cannot be its own parent.")

        if self.institution:
            allow_sales_out_of_stock_at_institution = (
                self.institution.allow_sales_out_of_stock
            )

            if (
                not allow_sales_out_of_stock_at_institution
                and self.allow_sales_out_of_stock is True
            ):
                raise validation_error(
                    "Cannot allow sales out of stock at branch level when it is not allowed at institution level."
                )

    def __str__(self):
        return f"{self.branch_name} - {self.institution.institution_name}"

    def save(self, *args, **kwargs):
        self.full_clean()
        is_new = self._state.adding

        super().save(*args, **kwargs)

        if is_new:
            from .utils import (
                give_branch_all_inventory_from_institution,
                create_branch_currency_as_branch_supported_currency,
            )

            give_branch_all_inventory_from_institution(self)
            create_branch_currency_as_branch_supported_currency(self)

    def get_institution(self):
        return self.institution

    class Meta:
        verbose_name = "Branch"
        verbose_name_plural = "Branches"
        db_table = "branches"

    def _get_inventory_cost_variance_account(self):
        if self.inventory_cost_variance_account:
            return self.inventory_cost_variance_account

        from accounts.utils import get_or_create_default_account

        institution = self.get_institution()

        return get_or_create_default_account(institution, "cogs_account")


class BranchSupportedCurrency(SoftDeletableTimeStampedModel):
    reference_prefix = "BC"

    branch = models.ForeignKey(
        Branch, on_delete=models.CASCADE, related_name="supported_currencies_links"
    )
    currency = models.ForeignKey(
        "system.SystemCurrency",
        on_delete=models.CASCADE,
        related_name="supported_branches",
    )
    rate = models.DecimalField(max_digits=50, decimal_places=20, null=True, blank=True)
    is_default = models.BooleanField(default=False)

    format = models.CharField(
        max_length=30,
        choices=[
            ("base_to_other", "Base to Other"),
            ("other_to_base", "Other to Base"),
        ],
        default="base_to_other",
        help_text="Format indicating how rate should be interpreted",
    )

    search_fields = [
        "currency__name",
        "currency__code",
    ]

    class Meta:
        verbose_name = "Branch Supported Currency"
        verbose_name_plural = "Branch Supported Currencies"
        unique_together = ("branch", "currency")
        db_table = "institution_branch_supported_currency"

    def __str__(self):
        return self.branch.branch_name + " - " + self.currency.name


class BranchAdmin(SoftDeletableTimeStampedModel):
    reference_prefix = "BA"
    branch = models.ForeignKey(
        Branch, on_delete=models.CASCADE, related_name="branch_admin_links"
    )
    admin = models.ForeignKey("users.CustomUser", on_delete=models.CASCADE)
    is_super_admin = models.BooleanField(default=False)

    search_fields = [
        "admin__fullname",
        "admin__email",
        "branch__branch_name",
        "branch__branch_email",
    ]

    class Meta:
        db_table = "institution_branch_admins"
        unique_together = ("branch", "admin")
        verbose_name = "Branch Admin"
        verbose_name_plural = "Branch Admins"

    def __str__(self):
        return f"{self.branch.branch_name} - {self.admin.email}"

    def clean(self):
        if self.branch.branch_type in ["BRANCH", "DIVISION"]:
            raise validation_error("Admin cannot be assigned to branch-based units.")

        admin = self.admin

        if not hasattr(admin, "profile"):
            raise validation_error("Selected admin user does not have a profile.")

        profile = admin.profile

        if not profile.institution:
            raise validation_error("Admin user is not linked to any institution.")

        is_institution_owner = admin == profile.institution.created_by

        is_branch_member = UserBranch.objects.filter(
            branch=self.branch,
            user=admin,
            deleted_at__isnull=True,
        ).exists()

        if not (is_institution_owner or is_branch_member):
            raise validation_error(
                "Admin must belong to the branch or be the institution owner."
            )


class UserBranch(ReportableModelMixin, SoftDeletableTimeStampedModel):
    user = models.ForeignKey(
        "users.CustomUser", related_name="attached_branches", on_delete=models.CASCADE
    )
    branch = models.ForeignKey(
        Branch, related_name="attached_users", on_delete=models.CASCADE
    )
    is_default = models.BooleanField(default=False)

    class Meta:
        unique_together = ["user", "branch"]
        verbose_name = "User Branch"
        verbose_name_plural = "User Branches"

    def save(self, *args, **kwargs):
        if self.is_default:
            UserBranch.objects.filter(user=self.user, is_default=True).update(
                is_default=False
            )

        super().save(*args, **kwargs)

    def __str__(self):
        return self.user.email + " - " + self.branch.branch_location

    @classmethod
    def get_institution_filter_field(cls):
        return "branch__institution"


class BusinessDocumentCategory(ReportableModelMixin, BaseApprovableModel):
    reference_prefix = "BDC"

    institution = models.ForeignKey(
        Institution,
        related_name="document_categories",
        on_delete=models.CASCADE,
        blank=True,
        null=True,
    )

    name = models.CharField(max_length=100)
    system_category = models.ForeignKey(
        "system.SystemSupportedFinancialDocumentsCategory",
        on_delete=models.CASCADE,
        related_name="business_document_categories",
        help_text="Link to a system-supported category.",
        blank=True,
        null=True,
    )
    description = models.TextField(blank=True, null=True)

    search_fields = [
        "name",
        "description",
    ]

    ordering_fields = [
        "name",
        "description",
    ]

    def __str__(self):
        return f"{self.name} - {self.institution.institution_name}"

    class Meta:
        verbose_name = "Business Document Category"
        verbose_name_plural = "Business Document Categories"

    def get_institution(self):
        return self.institution

    def finish_workflow(self, approval: Approval):
        with transaction.atomic():
            if approval.status == "completed":
                if approval.action.name in ["create", "update"]:
                    self.is_active = True
                    self.status = "draft"

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


class BusinessFinancialDocuments(ReportableModelMixin, BaseApprovableModel):
    reference_prefix = "BFD"

    attachment = models.FileField(
        upload_to="institutions/documents", blank=True, null=True
    )

    name = models.CharField(max_length=255)

    branch = models.ForeignKey(Branch, null=True, blank=True, on_delete=models.CASCADE)

    expiry_date = models.DateField(null=True, blank=True)
    issue_date = models.DateField(null=True, blank=True)

    category = models.ForeignKey(
        BusinessDocumentCategory,
        null=True,
        blank=True,
        on_delete=models.CASCADE,
    )

    search_fields = [
        "name",
    ]

    ordering_fields = [
        "name",
        "issue_date",
        "expiry_date",
    ]

    def get_institution(self):
        return self.category.get_institution()

    def __str__(self):
        return f"{self.name} - {self.category.get_institution().institution_name}"

    def clean(self):
        """Custom validation for business rules."""
        if self.issue_date and self.expiry_date and self.issue_date > self.expiry_date:
            validation_error("Issue date cannot be after the expiry date.")

    def save(self, *args, **kwargs):
        self.full_clean()
        super().save(*args, **kwargs)

    class Meta:
        verbose_name = "Business Financial Document"
        verbose_name_plural = "Business Financial Documents"
        ordering = ["-issue_date", "name"]

    @classmethod
    def get_excluded_report_fields(cls):
        """
        Overrides the mixin method to include 'attachment' in the excluded fields list.
        """
        # Get the default excluded fields from the mixin
        excluded_fields = ReportableModelMixin.get_excluded_report_fields().copy()

        # Add 'attachment' as a field to exclude from reports for this specific model
        excluded_fields.append("attachment")
        return excluded_fields

    def finish_workflow(self, approval: Approval):
        with transaction.atomic():
            if approval.status == "completed":
                if approval.action.name in ["create", "update"]:
                    self.is_active = True
                    self.status = "draft"

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


class InstitutionItemReturnReason(ReportableModelMixin, BaseApprovableModel):
    reference_prefix = "IRR"

    institution = models.ForeignKey(
        Institution,
        on_delete=models.CASCADE,
        related_name="item_return_reasons",
    )
    return_reason_name = models.CharField(max_length=100)

    search_fields = [
        "return_reason_name",
        "description",
    ]

    ordering_fields = ["return_reason_name"]

    class Meta:
        verbose_name = "Institution Item Return Reason"
        verbose_name_plural = "Institution Item Return Reasons"
        ordering = ["institution", "return_reason_name"]

        constraints = [
            models.UniqueConstraint(
                fields=["institution", "return_reason_name"],
                name="unique_institution_return_reason",
                condition=models.Q(deleted_at__isnull=True),
            )
        ]

    def get_institution(self):
        return self.institution

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

                elif approval.action.name in ["update", "delete"]:
                    self.is_active = False
                    self.deleted_at = None

        self.save()


class Announcement(BaseApprovableModel):
    institution = models.ForeignKey("institution.Institution", on_delete=models.CASCADE)
    title = models.CharField(max_length=255)
    content = models.TextField()

    requires_acknowledgment = models.BooleanField(default=False)

    is_targetted_to_all_users = models.BooleanField(default=True)
    is_role_targetted = models.BooleanField(default=False)

    target_users = models.ManyToManyField(
        "users.CustomUser",
        related_name="targeted_announcements",
        blank=True,
        through="AnnouncementTargetUser",
    )
    target_roles = models.ManyToManyField(
        "users.Role",
        related_name="targeted_announcements",
        blank=True,
        through="AnnouncementTargetRole",
    )

    search_fields = [
        "title",
        "content",
    ]

    class Meta:
        verbose_name = "Announcement"
        verbose_name_plural = "Announcements"
        ordering = ["-created_at"]

    def __str__(self):
        return self.title

    def get_institution(self):
        return self.institution


class AnnouncementTargetUser(models.Model):
    announcement = models.ForeignKey(
        Announcement, on_delete=models.CASCADE, related_name="target_user_links"
    )
    user = models.ForeignKey(
        "users.CustomUser", on_delete=models.CASCADE, related_name="announcement_links"
    )

    class Meta:
        verbose_name = "Announcement Target User"
        verbose_name_plural = "Announcement Target Users"
        # unique_together = ("announcement", "user")
        indexes = [
            models.Index(fields=["user"]),
            models.Index(fields=["announcement"]),
        ]


class AnnouncementTargetRole(models.Model):
    announcement = models.ForeignKey(
        Announcement, on_delete=models.CASCADE, related_name="target_role_links"
    )
    role = models.ForeignKey(
        "users.Role", on_delete=models.CASCADE, related_name="announcement_links"
    )

    class Meta:
        verbose_name = "Announcement Target Role"
        verbose_name_plural = "Announcement Target Roles"
        # unique_together = ("announcement", "role")
        indexes = [
            models.Index(fields=["role"]),
            models.Index(fields=["announcement"]),
        ]


class UserAnnouncementAcknowledgment(models.Model):
    user = models.ForeignKey(
        "users.CustomUser",
        on_delete=models.CASCADE,
        related_name="announcement_acknowledgments",
    )
    announcement = models.ForeignKey(
        Announcement, on_delete=models.CASCADE, related_name="user_acknowledgments"
    )
    acknowledged = models.BooleanField(default=False)
    acknowledged_at = models.DateTimeField(blank=True, null=True)

    class Meta:
        verbose_name = "User Announcement Acknowledgment"
        verbose_name_plural = "User Announcement Acknowledgments"
        unique_together = ("user", "announcement")
        indexes = [
            models.Index(fields=["user"]),
            models.Index(fields=["announcement"]),
        ]

    def __str__(self):
        return f"{self.user.fullname} acknowledgment instance for {self.announcement.title}"


class Notes(SoftDeletableTimeStampedModel):
    user = models.ForeignKey(
        "users.CustomUser", on_delete=models.CASCADE, related_name="notes"
    )
    title = models.CharField(max_length=225)
    content = models.TextField()
    is_pinned = models.BooleanField(default=False)

    search_fields = [
        "title",
        "content",
    ]

    def __str__(self):
        return f"Note for User {self.user.fullname}: {self.title}"

    class Meta:
        verbose_name = "Note"
        verbose_name_plural = "Notes"
        ordering = ["-is_pinned", "-created_at"]

    def __str__(self):
        return self.title


class RecycleBin(BaseTimeStamp):
    reference_prefix = "RB"

    institution = models.OneToOneField(
        "institution.Institution",
        on_delete=models.CASCADE,
        related_name="recycle_bin",
    )

    def __str__(self):
        return f"Recycle Bin — {self.institution}"

    def items_for_model(self, model_class):
        ct = ContentType.objects.get_for_model(model_class)
        return self.items.filter(content_type=ct)

    def empty(self, user=None):
        for item in self.items.all():
            item.hard_delete(user=user)

    class Meta:
        ordering = ["-created_at"]
        verbose_name = "Recycle Bin"
        verbose_name_plural = "Recycle Bins"


class RecycleBinItem(BaseTimeStamp):
    reference_prefix = "RBI"

    recycle_bin = models.ForeignKey(
        RecycleBin,
        on_delete=models.CASCADE,
        related_name="items",
    )
    content_type = models.ForeignKey(
        ContentType,
        on_delete=models.CASCADE,
    )
    object_uuid = models.UUIDField(db_index=True)
    content_object = GenericForeignKey("content_type", "object_uuid")

    deleted_at = models.DateTimeField(auto_now_add=True, db_index=True)
    deleted_by = models.ForeignKey(
        "users.CustomUser",
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="recycle_bin_items",
    )
    data = models.JSONField(help_text="Full serialized snapshot of the deleted object.")

    class Meta:
        ordering = ["-deleted_at"]
        indexes = [
            models.Index(fields=["content_type", "object_uuid"]),
        ]
        verbose_name = "Recycle Bin Item"
        verbose_name_plural = "Recycle Bin Items"

    def __str__(self):
        return (
            f"{self.content_type.app_labeled_name} (pk={self.object_uuid}) "
            f"deleted by {self.deleted_by} at {self.deleted_at:%Y-%m-%d %H:%M}"
        )

    @transaction.atomic
    def restore(self, user=None):
        if not self.data:
            raise ValueError("Cannot restore — no snapshot stored in this item.")

        json_str = f"[{self.data}]"
        deserialized = list(serializers.deserialize("json", json_str))

        if not deserialized:
            raise ValueError("Snapshot is corrupted or empty; cannot restore.")

        revived = deserialized[0].object
        revived._state.adding = False
        revived.base_uuid = self.object_uuid
        revived.deleted_at = None
        revived.is_active = True

        if user and hasattr(user, "is_authenticated") and user.is_authenticated:
            if hasattr(revived, "updated_by_id"):
                revived.updated_by = user

        revived.save()

        self.delete()

        return revived

    def hard_delete(self, user=None):
        try:
            original = self.content_type.get_object_for_this_type(
                base_uuid=self.object_uuid
            )
            original.delete(using_soft_delete=False)
        except self.content_type.model_class().DoesNotExist:
            pass

        self.delete()


class InstitutionFeatureStatus(SoftDeletableTimeStampedModel):
    institution = models.ForeignKey(
        Institution, related_name="feature_statuses", on_delete=models.CASCADE
    )
    system_feature = models.ForeignKey(
        "system.SystemFeature",
        related_name="institution_statuses",
        on_delete=models.CASCADE,
    )
    is_enabled = models.BooleanField(default=True)

    search_fields = [
        "system_feature__feature_name",
        "system_feature__description",
    ]

    class Meta:
        unique_together = ("institution", "system_feature")
        indexes = [
            models.Index(fields=["institution", "system_feature"]),
        ]
        ordering = ["system_feature__feature_name"]

    def __str__(self):
        return f"{self.institution} - {self.system_feature.feature_name} : {'ON' if self.is_enabled else 'OFF'}"

    def get_institution(self):
        return self.institution

    def get_all_features(self, institution_id):
        statuses = InstitutionFeatureStatus.objects.select_related(
            "system_feature"
        ).filter(
            institution_id=institution_id,
            system_feature__is_active=True,
        )

        feature_codes = []

        for status in statuses:
            sf = status.system_feature

            if sf.is_mandatory:
                feature_codes.append(sf.feature_code)

            else:
                if status.is_enabled:
                    feature_codes.append(sf.feature_code)

        return set(feature_codes)

    def has_feature(self, institution_id, feature_code):
        """check if feature is enabled and active."""
        if self.is_active and self.is_superuser:
            return True

        return feature_code in self.get_all_features(institution_id)


class InstitutionKYCDocument(ReportableModelMixin, BaseApprovableModel):
    institution = models.ForeignKey(
        "institution.Institution",
        on_delete=models.CASCADE,
        related_name="institution_kyc_files",
    )
    category = models.ForeignKey(
        SystemKYCDocumentCategory,
        on_delete=models.CASCADE,
        related_name="institution_documents",
    )
    document_name = models.CharField(max_length=255)
    file = models.FileField(upload_to="kyc/institutions/")
    issue_date = models.DateField(blank=True, null=True)
    expiry_date = models.DateField(blank=True, null=True)

    class Meta:
        unique_together = ("institution", "document_name")
        verbose_name = "Institution KYC Document"
        verbose_name_plural = "Institution KYC Documents"

    def __str__(self):
        return f"{self.institution} - {self.document_name}"

    def get_institution(self):
        return self.institution


class InstitutionReferenceSequence(SoftDeletableTimeStampedModel):
    class SequenceType(models.TextChoices):
        NUMERIC = "numeric", "Numeric"
        ALPHA = "alpha", "Alpha"

    institution = models.ForeignKey(
        Institution,
        on_delete=models.CASCADE,
        related_name="reference_sequences",
    )
    content_type = models.ForeignKey(
        "contenttypes.ContentType",
        on_delete=models.CASCADE,
        related_name="institution_reference_sequences",
    )

    prefix = models.CharField(max_length=30)

    starting_value = models.PositiveIntegerField(
        null=True,
        blank=True,
        help_text=(
            "Initial numeric value to start from. Used only before the first "
            "reference is generated for numeric sequences."
        ),
    )

    padding_digits = models.PositiveIntegerField(
        null=True,
        blank=True,
        help_text=(
            "Minimum number of digits for numeric references. For example, "
            "4 generates 0001, 0002; 2 generates 01, 02, 10."
        ),
    )

    last_value = models.CharField(max_length=100, null=True, blank=True)

    sequence_type = models.CharField(
        max_length=20,
        choices=SequenceType.choices,
        default=SequenceType.ALPHA,
    )

    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=["institution", "content_type"],
                name="unique_institution_content_type_sequence",
            )
        ]

    def __str__(self):
        return (
            f"{self.institution} - "
            f"{self.content_type.app_label}.{self.content_type.model} "
            f"({self.prefix})"
        )

    def get_institution(self):
        return self.institution


class InstitutionOwnershipTransferHistory(SoftDeletableTimeStampedModel):
    institution = models.ForeignKey(
        Institution,
        on_delete=models.CASCADE,
        related_name="ownership_transfer_history",
    )

    new_owner = models.ForeignKey(
        "users.CustomUser",
        on_delete=models.CASCADE,
        related_name="institution_ownership_transfers_received",
    )

    previous_owner = models.ForeignKey(
        "users.CustomUser",
        on_delete=models.CASCADE,
        related_name="institution_ownership_transfers_made",
    )

    transfer_date = models.DateField(default=timezone.now, db_index=True)

    class Meta:
        verbose_name = "Institution Ownership Transfer History"
        verbose_name_plural = "Institution Ownership Transfer Histories"
        ordering = ["-transfer_date"]
        indexes = [
            models.Index(fields=["institution", "-transfer_date"]),
            models.Index(fields=["previous_owner", "new_owner"]),
        ]

    def __str__(self):
        return (
            f"{self.institution} ownership transferred from "
            f"{self.previous_owner} to {self.new_owner}"
        )

    def get_institution(self):
        return self.institution


class InstitutionSupportedBankingInstitution(SoftDeletableTimeStampedModel):
    reference_prefix = "BNK"

    institution = models.ForeignKey(
        Institution,
        on_delete=models.CASCADE,
        related_name="supported_banking_institutions",
    )

    bank_name = models.CharField(max_length=100)

    search_fields = ["bank_name"]

    class Meta:
        unique_together = ("institution", "bank_name")
        verbose_name = "Institution Supported Banking Institution"
        verbose_name_plural = "Institution Supported Banking Institutions"
        ordering = ["bank_name"]

    def __str__(self):
        return f"{self.bank_name} — {self.institution}"

    def get_institution(self):
        return self.institution
