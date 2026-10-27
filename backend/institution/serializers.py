from rest_framework import serializers
from django.utils import timezone
import json
from system.services import BaisoftPayService, BaisoftPayServiceError
from institution.services import InstitutionDataSyncService
from users.services import (
    RoleAssignmentService,
    grant_all_permissions_to_institution_owners,
)
from bank_management.models import BankAccount
from .utils import humanize_model_name
from utilities.helpers import (
    UUIDRelatedField,
    parse_json_or_dict,
    validation_error,
    _validate_payment_term_days,
)
from users.models import (
    CustomUser,
    ExternalIdentity,
    ProfileInstitution,
    Role,
)
from users.serializers import CustomUserSerializer
from .models import (
    BranchAdmin,
    InstitutionBaisoftPayConfiguration,
    InstitutionNotificationSetting,
    InstitutionOwnershipTransferHistory,
    Notes,
    Institution,
    Branch,
    InstitutionItemReturnReason,
    UserBranch,
    InstitutionDocument,
    BusinessFinancialDocuments,
    BusinessDocumentCategory,
    Announcement,
    AnnouncementTargetUser,
    AnnouncementTargetRole,
    UserAnnouncementAcknowledgment,
    InstitutionFeatureStatus,
    InstitutionSupportedCurrency,
    BranchSupportedCurrency,
    InstitutionKYCDocument,
    InstitutionSupportedPaymentOption,
    InstitutionSupportedBankingInstitution,
    InstitutionReferenceSequence,
    RecycleBin,
    RecycleBinItem,
)
from system.models import SystemNotification
from utilities.file_utils import Base64FileFieldMixin
from django.db import transaction as db_transaction
import os
from django.db import transaction
from system.serializers import (
    SystemCurrencySerializer,
    SystemFeatureSerializer,
    SystemNotificationSerializer,
    SystemSupportedFinancialDocumentsCategorySerializer,
    SystemIndustrySerializer,
    SystemStockValuationMethodSerializer,
    SystemStockMovementStrategySerializer,
)
from approval.serializers import BaseApprovableSerializer, BaseUnApprovableSerializer
from utilities.helpers import (
    get_institution,
    validation_error,
    _validate_payment_term_days,
)
from utilities.common_serializers import BaseModelSerializer
from system.models import (
    SystemCurrency,
    SystemKYCDocumentCategory,
    SystemSupportedFinancialDocumentsCategory,
)
from bank_management.models import (
    BankAccount,
    MobileMoneyAccount,
    DigitalWalletAccount,
    CashAtHandAccount,
)

allowed_models = [
    BankAccount,
    MobileMoneyAccount,
    DigitalWalletAccount,
    CashAtHandAccount,
]
from bank_management.utils import (
    CashAccountInputSerializer,
)
from decimal import Decimal
from django.contrib.contenttypes.models import ContentType


class InstitutionBaisoftPayConfigurationSerializer(serializers.ModelSerializer):
    @staticmethod
    def verify_credentials(api_key, signing_key):
        try:
            service = BaisoftPayService(
                api_key=api_key,
                signing_key=signing_key,
            )
            service.get_payment_methods(
                params={
                    "page": 1,
                    "page_size": 1,
                }
            )
        except BaisoftPayServiceError as exc:
            raise validation_error(
                {
                    "credentials": (
                        "The BaisoftPay API key or signing key is invalid. "
                        f"{str(exc).strip()}"
                    )
                }
            )

    branch = UUIDRelatedField(
        queryset=Branch.objects.undeleted(),
        required=False,
        allow_null=True,
        write_only=True,
    )
    api_key = serializers.CharField(
        write_only=True,
        required=False,
        allow_blank=False,
        trim_whitespace=True,
    )
    signing_key = serializers.CharField(
        write_only=True,
        required=False,
        allow_blank=False,
        trim_whitespace=True,
    )

    has_api_key = serializers.BooleanField(read_only=True)
    has_signing_key = serializers.BooleanField(read_only=True)

    class Meta:
        model = InstitutionBaisoftPayConfiguration
        fields = [
            "base_uuid",
            "branch",
            "api_key",
            "signing_key",
            "has_api_key",
            "has_signing_key",
            "last_verified_at",
            "is_active",
            "created_at",
            "updated_at",
        ]
        read_only_fields = [
            "base_uuid",
            "has_api_key",
            "has_signing_key",
            "last_verified_at",
            "created_at",
            "updated_at",
        ]

    def to_representation(self, instance):
        representation = super().to_representation(instance)
        representation["branch"] = (
            {
                "base_uuid": str(instance.branch.base_uuid),
                "branch_name": instance.branch.branch_name,
            }
            if instance.branch_id
            else None
        )
        return representation

    def validate(self, attrs):
        request = self.context["request"]
        institution = get_institution(request)

        branch = attrs.get(
            "branch",
            self.instance.branch if self.instance else None,
        )

        if branch and branch.institution_id != institution.id:
            raise validation_error(
                {
                    "branch": (
                        "The selected branch does not belong to the current "
                        "institution."
                    )
                }
            )

        if self.instance is None:
            if not attrs.get("api_key"):
                raise validation_error(
                    {"api_key": "The BaisoftPay API key is required."}
                )

            if not attrs.get("signing_key"):
                raise validation_error(
                    {"signing_key": ("The BaisoftPay signing key is required.")}
                )

        existing = InstitutionBaisoftPayConfiguration.objects.undeleted().filter(
            institution=institution,
            branch=branch,
        )

        if self.instance:
            existing = existing.exclude(pk=self.instance.pk)

        if existing.exists():
            scope = branch.branch_name if branch else "institution default"
            raise validation_error(
                {"branch": (f"A BaisoftPay configuration already exists for {scope}.")}
            )

        return attrs

    def create(self, validated_data):
        request = self.context["request"]
        institution = get_institution(request)
        api_key = validated_data.pop("api_key")
        signing_key = validated_data.pop("signing_key")

        self.verify_credentials(api_key, signing_key)

        configuration = InstitutionBaisoftPayConfiguration(
            institution=institution,
            created_by=request.user,
            updated_by=request.user,
            last_verified_at=timezone.now(),
            **validated_data,
        )
        configuration.set_credentials(
            api_key=api_key,
            signing_key=signing_key,
        )
        configuration.full_clean()
        configuration.save()
        return configuration

    def update(self, instance, validated_data):
        api_key = validated_data.pop("api_key", None)
        signing_key = validated_data.pop("signing_key", None)

        if api_key is not None or signing_key is not None:
            self.verify_credentials(
                api_key or instance.api_key,
                signing_key or instance.signing_key,
            )
            instance.last_verified_at = timezone.now()

        for field, value in validated_data.items():
            setattr(instance, field, value)

        instance.set_credentials(
            api_key=api_key,
            signing_key=signing_key,
        )
        instance.updated_by = self.context["request"].user
        instance.full_clean()
        instance.save()
        return instance


class InstitutionReferenceSequenceSerializer(serializers.ModelSerializer):
    content_type_label = serializers.CharField(
        source="content_type.app_labeled_name",
        read_only=True,
    )

    class Meta:
        model = InstitutionReferenceSequence
        fields = [
            "base_uuid",
            "institution",
            "content_type",
            "content_type_label",
            "prefix",
            "sequence_type",
            "starting_value",
            "padding_digits",
            "last_value",
            "is_active",
            "created_at",
            "updated_at",
        ]
        read_only_fields = [
            "base_uuid",
            "institution",
            "content_type_label",
            "last_value",
            "created_at",
            "updated_at",
        ]

    def validate(self, attrs):
        sequence_type = attrs.get(
            "sequence_type",
            getattr(self.instance, "sequence_type", None),
        )
        starting_value = attrs.get(
            "starting_value",
            getattr(self.instance, "starting_value", None),
        )
        padding_digits = attrs.get(
            "padding_digits",
            getattr(self.instance, "padding_digits", None),
        )

        if sequence_type == InstitutionReferenceSequence.SequenceType.ALPHA:
            attrs["starting_value"] = None
            attrs["padding_digits"] = None

        if (
            sequence_type == InstitutionReferenceSequence.SequenceType.NUMERIC
            and starting_value is not None
            and starting_value < 1
        ):
            raise validation_error(
                {"starting_value": "Starting value must be at least 1."}
            )

        if (
            sequence_type == InstitutionReferenceSequence.SequenceType.NUMERIC
            and padding_digits is not None
            and padding_digits < 1
        ):
            raise validation_error(
                {"padding_digits": "Number of digits must be at least 1."}
            )

        if self.instance and self.instance.last_value not in (None, ""):
            if "starting_value" in attrs:
                attrs.pop("starting_value")

        return attrs

    def create(self, validated_data):
        institution = validated_data["institution"]
        content_type = validated_data["content_type"]

        with transaction.atomic():
            existing_sequence = (
                InstitutionReferenceSequence.objects.select_for_update()
                .filter(
                    institution=institution,
                    content_type=content_type,
                )
                .first()
            )

            if existing_sequence and existing_sequence.deleted_at is None:
                raise validation_error(
                    {
                        "content_type": (
                            "A reference sequence already exists for this record type."
                        )
                    }
                )

            if existing_sequence:
                if existing_sequence.last_value not in (None, ""):
                    validated_data.pop("starting_value", None)

                for field, value in validated_data.items():
                    setattr(existing_sequence, field, value)

                existing_sequence.deleted_at = None
                existing_sequence.is_active = True
                existing_sequence.save()
                return existing_sequence

            return super().create(validated_data)


class InstitutionNotificationSettingSerializer(serializers.ModelSerializer):

    target_users = serializers.SerializerMethodField(
        read_only=True,
    )

    class Meta:
        model = InstitutionNotificationSetting
        fields = "__all__"

        read_only_fields = [
            "id",
            "institution",
            "created_at",
            "updated_at",
            "base_uuid",
            "deleted_at",
            "created_by",
            "updated_by",
        ]

    def get_target_users(self, obj):
        return [
            {
                "id": user.id,
                "fullname": user.fullname,
                "email": user.email,
                "base_uuid": user.base_uuid,
            }
            for user in obj.target_users.all()
        ]

    def to_representation(self, instance):
        repr = super().to_representation(instance)
        repr["system_notification"] = SystemNotificationSerializer(
            instance.system_notification
        ).data
        return repr


class InstitutionNotificationSettingInputSerializer(serializers.Serializer):
    notification = UUIDRelatedField(queryset=SystemNotification.objects.all())
    is_enabled = serializers.BooleanField(default=True)
    target_user_uuids = serializers.ListField(
        child=UUIDRelatedField(queryset=CustomUser.objects.all()),
        required=False,
        help_text="List of user UUIDs to receive this notification",
    )


class InstitutionSupportedPaymentOptionSerializer(serializers.ModelSerializer):

    class Meta:
        model = InstitutionSupportedPaymentOption
        fields = "__all__"

    def to_representation(self, instance):
        repr = super().to_representation(instance)

        from bank_management.serializers import CashAccountOutputSerializer

        repr["payment_option"] = CashAccountOutputSerializer(
            instance.payment_option
        ).data

        return repr


class InstitutionDocumentSerializer(serializers.ModelSerializer):

    class Meta:
        model = InstitutionDocument
        fields = "__all__"

    def validate_file(self, value):
        if value:
            if value.document_size > 10 * 1024 * 1024:
                raise validation_error("File size cannot exceed 10MB.")

            allowed_extensions = [".pdf", ".doc", ".docx", ".jpg", ".jpeg", ".png"]
            ext = os.path.splitext(value.document_title)[1].lower()
            if ext not in allowed_extensions:
                raise validation_error(
                    f"File type {ext} not allowed. Allowed types: {', '.join(allowed_extensions)}"
                )
        return value


class SupportedCurrencyRateSerializer(serializers.Serializer):
    value = serializers.DecimalField(max_digits=50, decimal_places=20)
    currency_id = serializers.IntegerField()


class SupportedCurrenciesInputSerializer(serializers.Serializer):
    currency_id = serializers.IntegerField(
        help_text="ID of the currency", required=True
    )

    one_side = SupportedCurrencyRateSerializer(required=True)
    other_side = SupportedCurrencyRateSerializer(required=True)


class InstitutionSupportedBankingInstitutionSerializer(serializers.ModelSerializer):
    class Meta:
        model = InstitutionSupportedBankingInstitution
        fields = "__all__"
        read_only_fields = [
            "id",
            "base_uuid",
            "institution",
            "created_at",
            "updated_at",
            "is_active",
            "deleted_at",
        ]

    def validate_bank_name(self, value):
        bank_name = value.strip()
        if not bank_name:
            raise validation_error("Bank name is required.")

        request = self.context.get("request")
        institution = get_institution(request) if request else None

        if institution:
            existing = InstitutionSupportedBankingInstitution.objects.filter(
                institution=institution,
                bank_name__iexact=bank_name,
            )

            if self.instance:
                existing = existing.exclude(pk=self.instance.pk)

            if existing.exists():
                raise validation_error(
                    "This bank is already supported by the institution."
                )

        return bank_name

    def create(self, validated_data):
        request = self.context.get("request")
        validated_data["institution"] = get_institution(request)
        return super().create(validated_data)


class InstitutionSupportedCurrencySerial(serializers.ModelSerializer):

    one_side = serializers.SerializerMethodField()
    other_side = serializers.SerializerMethodField()

    class Meta:
        model = InstitutionSupportedCurrency
        fields = "__all__"

        read_only_fields = [
            "institution",
            "format",
            "rate",
            "currency",
            "one_side",
            "other_side",
        ]

    def get_one_side(self, obj):
        rep = obj.represent_rate()["x"]
        return {
            "value": rep["value"],
            "currency": SystemCurrencySerializer(rep["currency"]).data,
        }

    def get_other_side(self, obj):
        rep = obj.represent_rate()["y"]
        return {
            "value": rep["value"],
            "currency": SystemCurrencySerializer(rep["currency"]).data,
        }

    def to_representation(self, instance):
        repr = super().to_representation(instance)

        repr["currency"] = SystemCurrencySerializer(instance.currency).data

        return repr


class InstitutionKYCDocumentInputSerializer(serializers.Serializer):
    category = serializers.PrimaryKeyRelatedField(
        queryset=SystemKYCDocumentCategory.objects.all(),
        help_text="Select the KYC document category",
    )
    document_name = serializers.CharField(
        max_length=255,
        required=False,
        help_text="Optional custom name of the document; defaults to category name if not provided",
    )
    file = serializers.FileField(help_text="The actual document file")
    issue_date = serializers.DateField(required=False)
    expiry_date = serializers.DateField(required=False)


class InstitutionSerializer(serializers.ModelSerializer):
    IMMUTABLE_FIELDS_ON_UPDATE = [
        "industry",
        "institution_owner",
        "approval_status",
        "approval_date",
        "approved_by",
        "rejection_reason",
        "currency",
    ]

    institution_owner_id = serializers.PrimaryKeyRelatedField(
        queryset=CustomUser.objects.all()
    )
    institution_logo = serializers.ImageField(required=False, allow_null=True)
    documents = InstitutionDocumentSerializer(many=True, read_only=True)

    approval_status_display = serializers.CharField(
        source="get_approval_status_display", read_only=True
    )

    document_files = serializers.ListField(
        child=serializers.FileField(), write_only=True, required=False, allow_empty=True
    )
    document_titles = serializers.ListField(
        child=serializers.CharField(max_length=255),
        write_only=True,
        required=False,
        allow_empty=True,
    )

    selected_units = serializers.ListField(
        child=serializers.CharField(),
        write_only=True,
        required=False,
        allow_empty=True,
    )

    selected_business_document_categories = serializers.ListField(
        child=serializers.CharField(),
        write_only=True,
        required=False,
        allow_empty=True,
    )

    selected_other_income_categories = serializers.ListField(
        child=serializers.CharField(),
        write_only=True,
        required=False,
        allow_empty=True,
    )

    selected_requisition_types = serializers.ListField(
        child=serializers.CharField(),
        write_only=True,
        required=False,
        allow_empty=True,
    )
    selected_categories = serializers.ListField(
        child=serializers.CharField(),
        write_only=True,
        required=False,
        allow_empty=True,
    )

    selected_roles = serializers.ListField(
        child=serializers.CharField(),
        write_only=True,
        required=False,
        allow_empty=True,
    )

    selected_payment_terms = serializers.ListField(
        child=serializers.JSONField(),
        write_only=True,
        required=False,
        allow_empty=True,
    )

    supported_currencies = SupportedCurrenciesInputSerializer(
        many=True,
        write_only=True,
        required=False,
        help_text="List of supported currencies",
    )

    payment_options = CashAccountInputSerializer(
        many=True,
        write_only=True,
        required=False,
        help_text="List of supported payment options with content type and object UUID",
    )

    is_integrated_in_peracosoft = serializers.SerializerMethodField(read_only=True)

    owner_profile = serializers.SerializerMethodField(read_only=True)

    feature_statuses = serializers.SerializerMethodField(read_only=True)

    recycle_bin_item_count = serializers.SerializerMethodField()

    has_baisoftpay_configuration = serializers.SerializerMethodField(read_only=True)

    class Meta:
        model = Institution
        fields = [
            "id",
            "institution_owner_id",
            "approval_status_display",
            "approval_status",
            "rejection_reason",
            "suspension_reason",
            "institution_name",
            "institution_email",
            "approval_date",
            "documents",
            "document_files",
            "document_titles",
            "base_uuid",
            "is_sales_person_commission_enabled",
            "commission_percentage",
            "first_phone_number",
            "second_phone_number",
            "user_inactivity_time",
            "date_format",
            "default_pagination_page_size",
            "payment_options",
            "selected_units",
            "feature_statuses",
            "selected_business_document_categories",
            "selected_other_income_categories",
            "selected_requisition_types",
            "selected_categories",
            "selected_roles",
            "selected_payment_terms",
            "fiscal_year_start_month",
            "fiscal_period_type",
            "maximum_cashbook_topup_amount",
            "base_uuid",
            "currency",
            "created_at",
            "updated_at",
            "approval_date",
            "institution_logo",
            "default_invoice_due_days",
            "is_tax_filing_automated",
            "financial_document_expiry_notification_days",
            "location",
            "latitude",
            "longitude",
            "theme_color",
            "base_uuid",
            "external_base_uuid",
            "is_integrated_in_peracosoft",
            "industry",
            "accounting_method",
            "institution_owner_id",
            "owner_profile",
            "supported_currencies",
            "supports_multiple_currencies",
            "default_stock_valuation_method",
            "default_stock_movement_strategy",
            "supports_sales_returns",
            "minimal_days_for_sales_return",
            "deposit_distribution_strategy",
            "kyc_documents",
            "allow_sales_out_of_stock",
            "enable_cash_refund_for_item_return",
            "quotation_default_expiry_days",
            "inventory_reduction_timing",
            "inventory_increment_timing",
            "website",
            "unit_breakdown_strategy",
            "allow_unit_breakdown",
            "recycle_bin_item_count",
            "timezone",
            "are_notifications_enabled",
            "auto_depreciation_enabled",
            "allow_item_reuse_across_templates",
            "cash_account_reconciliation_automatch_threshold_percent",
            "should_vendor_payments_go_through_requisitions",
            "require_statement_for_cash_account_reconciliation",
            "has_baisoftpay_configuration",
        ]

        read_only_fields = [
            "base_uuid",
            "created_at",
            "updated_at",
            "approval_date",
            "created_by",
            "updated_by",
            "is_deleted",
            "base_uuid",
            "external_base_uuid",
            "approval_status",
            "rejection_reason",
            "suspension_reason",
            "recycle_bin_item_count",
            "has_baisoftpay_configuration",
        ]

    def get_recycle_bin_item_count(self, instance):
        try:
            bin_obj = instance.recycle_bin
            return bin_obj.items.count()
        except RecycleBin.DoesNotExist:
            return 0

    def get_has_baisoftpay_configuration(self, instance):
        return (
            InstitutionBaisoftPayConfiguration.objects.undeleted()
            .filter(institution=instance)
            .exists()
        )

    def get_is_integrated_in_peracosoft(self, instance):
        return (
            True
            if instance.external_identities.filter(is_active=True).exists()
            else False
        )

    def get_feature_statuses(self, instance):
        from .features import InstitutionFeatureService

        return list(InstitutionFeatureService.get_all_features(instance.id))

    def get_owner_profile(self, instance):
        from .services import IdentityService

        profile = IdentityService.ensure_profile(instance.institution_owner)
        owner_inst_profile = ProfileInstitution.objects.filter(
            profile=profile, institution=instance
        ).first()
        return {
            "id": owner_inst_profile.id if owner_inst_profile else None,
            "base_uuid": owner_inst_profile.base_uuid if owner_inst_profile else None,
        }

    def to_representation(self, instance):
        representation = super().to_representation(instance)

        if instance.currency:
            representation["currency"] = SystemCurrencySerializer(
                instance.currency
            ).data
        else:
            representation["currency"] = None

        if instance.industry:
            representation["industry"] = {
                "base_uuid": str(instance.industry.base_uuid),
                "industry_name": instance.industry.industry_name,
                "industry_description": instance.industry.industry_description,
            }
        else:
            representation["industry"] = None

        supported_currency_qs = (
            instance.institution_supported_currencies.select_related(
                "currency", "institution__currency"
            ).all()
        )

        representation["supported_currencies"] = InstitutionSupportedCurrencySerial(
            supported_currency_qs, many=True
        ).data

        if instance.default_stock_valuation_method:
            representation["default_stock_valuation_method"] = {
                "base_uuid": str(instance.default_stock_valuation_method.base_uuid),
                "name": instance.default_stock_valuation_method.name,
                "description": instance.default_stock_valuation_method.description,
            }
        else:
            representation["default_stock_valuation_method"] = None

        if instance.default_stock_movement_strategy:
            representation["default_stock_movement_strategy"] = {
                "base_uuid": str(instance.default_stock_movement_strategy.base_uuid),
                "name": instance.default_stock_movement_strategy.name,
                "description": instance.default_stock_movement_strategy.description,
            }
        else:
            representation["default_stock_movement_strategy"] = None

        kyc_docs_qs = instance.institution_kyc_files.select_related("category").all()
        representation["kyc_documents"] = [
            {
                "category": {
                    "id": doc.category.id,
                    "category_code": doc.category.category_code,
                    "category_name": doc.category.category_name,
                },
                "document_name": doc.document_name,
                "file": doc.file.url if doc.file else None,
                "issue_date": doc.issue_date.isoformat() if doc.issue_date else None,
                "expiry_date": doc.expiry_date.isoformat() if doc.expiry_date else None,
            }
            for doc in kyc_docs_qs
        ]

        representation["payment_options"] = InstitutionSupportedPaymentOptionSerializer(
            instance.supported_payment_options.undeleted(),
            many=True,
        ).data

        return representation

    def validate_default_invoice_due_days(self, value):
        _validate_payment_term_days(value, "Institution default invoice due days")
        return value

    def validate_quotation_default_expiry_days(self, value):
        _validate_payment_term_days(value, "Institution quotation default expiry days")
        return value

    def validate_selected_payment_terms(self, value):
        terms = []
        for item in value:
            try:
                term = parse_json_or_dict(item)
            except (json.JSONDecodeError, TypeError, ValueError):
                raise validation_error(
                    {
                        "selected_payment_terms": "Each payment term must be a JSON object."
                    }
                )
            if not isinstance(term, dict):
                raise validation_error(
                    {
                        "selected_payment_terms": "Each payment term must be a JSON object."
                    }
                )
            _validate_payment_term_days(term.get("days_until_due"), "Payment term")
            terms.append(term)
        return terms

    def validate(self, data):
        if self.instance is not None:
            submitted_owner_fields = {
                "institution_owner",
                "institution_owner_id",
            }.intersection(self.initial_data.keys())

            if submitted_owner_fields:
                raise validation_error(
                    {
                        field: (
                            "Institution ownership cannot be changed through "
                            "the institution update endpoint."
                        )
                        for field in sorted(submitted_owner_fields)
                    }
                )

        default_invoice_due_days = data.get("default_invoice_due_days")
        if default_invoice_due_days is not None:
            _validate_payment_term_days(
                default_invoice_due_days, "Institution default invoice due days"
            )

        quotation_default_expiry_days = data.get("quotation_default_expiry_days")
        if quotation_default_expiry_days is not None:
            _validate_payment_term_days(
                quotation_default_expiry_days,
                "Institution quotation default expiry days",
            )

        document_files = data.get("document_files", [])
        document_titles = data.get("document_titles", [])

        if len(document_files) != len(document_titles):
            raise validation_error(
                "The number of document files must match the number of document titles."
            )

        supports_sales_returns = data.get("supports_sales_returns", False)
        should_vendor_payments_go_through_requisitions = data.get(
            "should_vendor_payments_go_through_requisitions", False
        )
        minimal_days = data.get("minimal_days_for_sales_return")

        if not supports_sales_returns:
            enable_cash_refund = data.get("enable_cash_refund_for_item_return", False)

            if not supports_sales_returns and enable_cash_refund:
                raise validation_error(
                    "Cash refund cannot be enabled when sales returns are disabled."
                )

        if not supports_sales_returns:
            data["minimal_days_for_sales_return"] = 0

        else:
            if minimal_days is None or minimal_days <= 0:
                raise validation_error(
                    "Minimal days must be greater than 0 when sales returns are supported."
                )

        if self.instance:
            requisitions_feature = self.instance.feature_statuses.filter(
                system_feature__feature_code="requisitions_management",
                is_enabled=True,
            ).exists()

            if (
                should_vendor_payments_go_through_requisitions
                and not requisitions_feature
            ):
                raise validation_error(
                    "You cannot enable Vendor Payments to go through Requisitions when the Requisitions feature is disabled. Please enable the Requisitions feature first."
                )

        return data

    def update(self, instance, validated_data):
        validated_data.pop("institution_owner", None)
        validated_data.pop("institution_owner_id", None)
        return super().update(instance, validated_data)

    @transaction.atomic()
    def create(self, validated_data):
        request = self.context.get("request")
        if not request or not request.user.is_authenticated:
            raise validation_error(
                "User must be authenticated to create an Institution."
            )

        document_files = validated_data.pop("document_files", [])
        document_titles = validated_data.pop("document_titles", [])

        supports_multiple_currencies = validated_data.get(
            "supports_multiple_currencies"
        )
        supported_currencies_data = validated_data.pop(
            "supported_currencies", self.initial_data.get("supported_currencies", [])
        )

        institution_owner = validated_data.pop("institution_owner_id")

        selected_units = validated_data.pop("selected_units", [])
        selected_business_document_categories = validated_data.pop(
            "selected_business_document_categories", []
        )
        selected_other_income_categories = validated_data.pop(
            "selected_other_income_categories", []
        )
        selected_requisition_types = validated_data.pop(
            "selected_requisition_types", []
        )
        selected_categories = validated_data.pop("selected_categories", [])
        selected_roles = validated_data.pop("selected_roles", [])
        selected_payment_terms = validated_data.pop("selected_payment_terms", [])
        payment_options_data = validated_data.pop("payment_options", [])

        request = self.context.get("request")
        if isinstance(supported_currencies_data, str):
            supported_currencies_data = json.loads(supported_currencies_data)

        with db_transaction.atomic():
            institution = Institution(
                institution_owner=institution_owner,
                created_by=request.user,
                **validated_data,
            )
            institution.save(standalone_mode=True)

            from .services import IdentityService

            profile = IdentityService.ensure_profile(institution_owner)
            IdentityService.ensure_profile_institution(profile, institution)

        if supports_multiple_currencies and supported_currencies_data:
            currencies_to_create = []
            base_currency = institution.currency

            for item in supported_currencies_data:
                supported_currency_id = SystemCurrency.objects.get(
                    id=item["currency_id"]
                )
                one_currency = SystemCurrency.objects.get(
                    id=item["one_side"]["currency_id"]
                )
                other_currency = SystemCurrency.objects.get(
                    id=item["other_side"]["currency_id"]
                )

                x = {
                    "value": Decimal(item["one_side"]["value"]),
                    "currency": one_currency,
                }
                y = {
                    "value": Decimal(item["other_side"]["value"]),
                    "currency": other_currency,
                }

                rate, format_type = (
                    InstitutionSupportedCurrency.determine_format_and_rate(
                        x, y, base_currency
                    )
                )

                currencies_to_create.append(
                    InstitutionSupportedCurrency(
                        institution=institution,
                        currency=supported_currency_id,
                        rate=rate,
                        format=format_type,
                    )
                )

            InstitutionSupportedCurrency.objects.bulk_create(
                currencies_to_create,
                ignore_conflicts=True,
            )

        for file, title in zip(document_files, document_titles):
            InstitutionDocument.objects.create(
                institution=institution, document_title=title, document_file=file
            )

        if selected_units:
            self.create_selected_units(institution, selected_units, request.user)

        if selected_other_income_categories:
            self.create_selected_other_income_categories(
                institution, selected_other_income_categories, request.user
            )

        if selected_business_document_categories:
            self.create_selected_business_document_categories(
                institution, selected_business_document_categories, request.user
            )

        if selected_requisition_types:
            self.create_selected_requisition_types(
                institution, selected_requisition_types, request.user
            )
        if selected_categories:
            self.create_selected_categories(
                institution, selected_categories, request.user
            )

        if selected_roles:
            self.create_selected_roles(
                institution,
                selected_roles,
            )

        if selected_payment_terms:
            self.create_selected_payment_terms(
                institution, selected_payment_terms, request.user
            )

        grant_all_permissions_to_institution_owners()

        if payment_options_data:
            self.create_payment_options(institution, payment_options_data)

        return institution

    def create_selected_units(self, institution, selected_units, created_by):
        import json
        from items.models import ItemUnitOfMeasure

        units_to_create = []
        for unit_json in selected_units:
            try:
                unit_data = json.loads(unit_json)
                units_to_create.append(
                    ItemUnitOfMeasure(
                        institution=institution,
                        unit_name=unit_data.get("unit_name"),
                        unit_abbreviation=unit_data.get("unit_abbreviation"),
                        description=unit_data.get("description"),
                        created_by=created_by,
                    )
                )
            except (json.JSONDecodeError, KeyError) as e:
                print(f"Error parsing unit data: {e}")
                continue

        if units_to_create:
            ItemUnitOfMeasure.objects.bulk_create(
                units_to_create, ignore_conflicts=True
            )

    def create_selected_other_income_categories(
        self, institution, selected_other_income_categories, created_by
    ):
        from accounts.models import OtherIncomeCategories
        from taxation.models import Tax

        categories_to_create = []
        category_map = {}

        for item in selected_other_income_categories:
            try:
                data = parse_json_or_dict(item)

                name = data.get("category_name")
                if not name:
                    continue

                category = OtherIncomeCategories(
                    institution=institution,
                    category_name=name,
                    category_description=data.get("category_description", ""),
                    created_by=created_by,
                )
                categories_to_create.append(category)
                category_map[name] = data

            except Exception as e:
                print(f"Error parsing other income category data: {e}")

        if categories_to_create:
            OtherIncomeCategories.objects.bulk_create(
                categories_to_create, ignore_conflicts=True
            )

        for name, data in category_map.items():
            tax_ids = data.get("tax_ids", [])
            if not tax_ids:
                continue

            try:
                category = OtherIncomeCategories.objects.get(
                    institution=institution, category_name=name
                )
                category.taxes.add(*Tax.objects.filter(id__in=tax_ids))
            except Exception as e:
                print(f"Error attaching taxes to '{name}': {e}")

    def create_selected_business_document_categories(
        self, institution, selected_business_document_categories, created_by
    ):
        from institution.models import BusinessDocumentCategory
        from system.models import SystemSupportedFinancialDocumentsCategory

        documents_to_create = []

        for item in selected_business_document_categories:
            try:
                data = parse_json_or_dict(item)

                system_code = data.get("system_category_code")
                if not system_code:
                    continue

                try:
                    system_category = (
                        SystemSupportedFinancialDocumentsCategory.objects.get(
                            category_code=system_code
                        )
                    )
                except SystemSupportedFinancialDocumentsCategory.DoesNotExist:
                    continue

                documents_to_create.append(
                    BusinessDocumentCategory(
                        institution=institution,
                        name=data.get("name"),
                        description=data.get("description", ""),
                        system_category=system_category,
                        created_by=created_by,
                    )
                )

            except Exception as e:
                print(f"Error parsing business document category data: {e}")

        if documents_to_create:
            BusinessDocumentCategory.objects.bulk_create(
                documents_to_create, ignore_conflicts=True
            )

    def create_selected_requisition_types(
        self, institution, selected_requisition_types, created_by
    ):
        import json
        from requisitions.models import RequisitionType
        from accounts.utils import get_or_create_default_account

        requisition_types_to_create = []
        for req_type_json in selected_requisition_types:
            try:
                req_type_data = parse_json_or_dict(req_type_json)
                requisition_types_to_create.append(
                    RequisitionType(
                        institution=institution,
                        name=req_type_data.get("requisition_type_name"),
                        description=req_type_data.get("requisition_type_description"),
                        created_by=created_by,
                        default_expense_account=get_or_create_default_account(
                            institution, "sgna_account"
                        ),
                        default_spending_account=get_or_create_default_account(
                            institution, "cash_account"
                        ),
                    )
                )
            except (json.JSONDecodeError, KeyError) as e:
                print(f"Error parsing requisition type data: {e}")
                continue

        if requisition_types_to_create:
            RequisitionType.objects.bulk_create(
                requisition_types_to_create, ignore_conflicts=True
            )

    def create_selected_categories(self, institution, selected_categories, created_by):
        import json
        from items.models import ItemCategory

        categories_to_create = []
        for category_json in selected_categories:
            try:
                category_data = parse_json_or_dict(category_json)
                categories_to_create.append(
                    ItemCategory(
                        institution=institution,
                        name=category_data.get("category_name"),
                        description=category_data.get("category_description"),
                        created_by=created_by,
                    )
                )
            except (json.JSONDecodeError, KeyError) as e:
                print(f"Error parsing category data: {e}")
                continue

        if categories_to_create:
            ItemCategory.objects.bulk_create(
                categories_to_create, ignore_conflicts=True
            )

    def create_selected_roles(self, institution, selected_roles):
        import json
        from users.models import Role

        roles_to_create = []
        for role_json in selected_roles:
            try:
                role_data = parse_json_or_dict(role_json)
                roles_to_create.append(
                    Role(
                        institution=institution,
                        name=role_data.get("role_name"),
                        description=role_data.get("role_description"),
                    )
                )
            except (json.JSONDecodeError, KeyError) as e:
                print(f"Error parsing role data: {e}")
                continue

        if roles_to_create:
            Role.objects.bulk_create(roles_to_create, ignore_conflicts=True)

    def create_selected_payment_terms(
        self, institution, selected_payment_terms, created_by
    ):
        from customers.models import PaymentTerm

        terms = self.validate_selected_payment_terms(selected_payment_terms)
        payment_terms_to_create = [
            PaymentTerm(
                institution=institution,
                term_name=term.get("term_name"),
                days_until_due=term["days_until_due"],
                created_by=created_by,
            )
            for term in terms
        ]
        if payment_terms_to_create:
            PaymentTerm.objects.bulk_create(
                payment_terms_to_create,
                ignore_conflicts=True,
            )

    def update(self, instance, validated_data):

        payment_options_data = validated_data.pop("payment_options", None)

        currency = validated_data.pop("currency", None)

        if currency and currency != instance.currency:
            raise validation_error("Updating currency is not allowed.")

        supports_multiple_currencies = validated_data.get(
            "supports_multiple_currencies"
        )
        supported_currencies_data = validated_data.pop(
            "supported_currencies", self.initial_data.get("supported_currencies", [])
        )

        for attr, value in validated_data.items():
            setattr(instance, attr, value)

        instance.save(standalone_mode=True)

        base_currency = instance.currency

        if supports_multiple_currencies is not None:

            qs = InstitutionSupportedCurrency.objects.filter(institution=instance)

            if supports_multiple_currencies:
                sent_currency_ids = (
                    [
                        item["currency_id"]
                        for item in supported_currencies_data
                        if item["currency_id"] != base_currency.id
                    ]
                    if supported_currencies_data
                    else []
                )

                if sent_currency_ids:
                    qs.exclude(
                        currency_id__in=sent_currency_ids + [base_currency.id]
                    ).delete()
                else:
                    qs.exclude(currency_id=base_currency.id).delete()

                for item in supported_currencies_data:

                    supported_currency = SystemCurrency.objects.get(
                        id=item["currency_id"]
                    )
                    one_currency = SystemCurrency.objects.get(
                        id=item["one_side"]["currency_id"]
                    )
                    other_currency = SystemCurrency.objects.get(
                        id=item["other_side"]["currency_id"]
                    )

                    x = {
                        "value": Decimal(item["one_side"]["value"]),
                        "currency": one_currency,
                    }
                    y = {
                        "value": Decimal(item["other_side"]["value"]),
                        "currency": other_currency,
                    }

                    rate, format_type = (
                        InstitutionSupportedCurrency.determine_format_and_rate(
                            x, y, base_currency
                        )
                    )

                    InstitutionSupportedCurrency.objects.update_or_create(
                        institution=instance,
                        currency=supported_currency,
                        defaults={"rate": rate, "format": format_type},
                    )

            else:
                qs.exclude(currency=base_currency).delete()

        if payment_options_data is not None:
            self.update_payment_options(instance, payment_options_data)

        return instance

    def create_payment_options(self, institution, payment_options_data):
        serializer = CashAccountInputSerializer(data=payment_options_data, many=True)
        serializer.is_valid(raise_exception=True)

        options_to_create = []

        for item in serializer.validated_data:
            cash_account = item["cash_account_object"]

            content_type = ContentType.objects.get_for_model(cash_account)

            options_to_create.append(
                InstitutionSupportedPaymentOption(
                    institution=institution,
                    content_type=content_type,
                    object_id=cash_account.pk,
                )
            )

        InstitutionSupportedPaymentOption.objects.bulk_create(
            options_to_create,
            ignore_conflicts=True,
        )

    def update_payment_options(self, institution, payment_options_data):
        serializer = CashAccountInputSerializer(data=payment_options_data, many=True)
        serializer.is_valid(raise_exception=True)

        desired = set()
        for item in serializer.validated_data:
            cash_account = item["cash_account_object"]
            content_type = ContentType.objects.get_for_model(cash_account)
            desired.add((content_type.pk, cash_account.pk))

        existing_qs = InstitutionSupportedPaymentOption.objects.filter(
            institution=institution,
            deleted_at__isnull=True,
        )
        for option in existing_qs:
            if (option.content_type_id, option.object_id) not in desired:
                option.delete()

        for content_type_id, object_id in desired:
            InstitutionSupportedPaymentOption.objects.update_or_create(
                institution=institution,
                content_type_id=content_type_id,
                object_id=object_id,
                defaults={
                    "deleted_at": None,
                    "is_active": True,
                },
            )


class BranchSupportedCurrencySerializer(serializers.ModelSerializer):
    class Meta:
        model = BranchSupportedCurrency
        fields = "__all__"


class BranchSupportedCurrencyInputSerializer(serializers.Serializer):
    branch = serializers.PrimaryKeyRelatedField(
        queryset=Branch.objects.filter(is_deleted=False)
    )
    currency = serializers.PrimaryKeyRelatedField(queryset=SystemCurrency.objects.all())
    rate = serializers.DecimalField(
        max_digits=50,
        decimal_places=20,
        required=False,
        allow_null=True,
    )

    def validate(self, attrs):
        request = self.context["request"]
        institution = get_institution(request)

        if not institution:
            raise validation_error("Institution not found.")

        branch = attrs["branch"]

        if branch.institution != institution:
            raise validation_error("Branch does not belong to this institution.")

        if BranchSupportedCurrency.objects.filter(
            branch=branch,
            currency=attrs["currency"],
            deleted_at__isnull=True,
        ).exists():
            raise validation_error("This currency is already supported by the branch.")

        return attrs

    def create(self, validated_data):
        request = self.context["request"]

        obj = BranchSupportedCurrency(
            branch=validated_data["branch"],
            currency=validated_data["currency"],
            rate=validated_data.get("rate"),
            created_by=request.user,
            updated_by=request.user,
        )
        obj.full_clean()
        obj.save()
        return obj


class BranchAdminInputSerializer(serializers.Serializer):
    admin = serializers.PrimaryKeyRelatedField(
        queryset=CustomUser.objects.all(),
        required=True,
    )
    is_super_admin = serializers.BooleanField(default=False)


class BranchAdminSerializer(BaseModelSerializer):
    admin = serializers.PrimaryKeyRelatedField(
        queryset=CustomUser.objects.select_related("profile").all(),
        required=True,
    )

    is_super_admin = serializers.BooleanField(default=False)

    class Meta:
        model = BranchAdmin
        fields = "__all__"
        read_only_fields = [
            "base_uuid",
            "created_at",
            "updated_at",
            "approval_date",
            "created_by",
            "updated_by",
            "is_deleted",
            "is_active",
            "external_base_uuid",
            "reference_code",
            "deleted_at",
        ]

    def validate(self, attrs):
        request = self.context["request"]
        institution = get_institution(request)

        if not institution:
            raise validation_error("Institution not found.")

        branch = attrs.get("branch") or getattr(self.instance, "branch", None)
        if not branch:
            raise validation_error("Branch must be provided.")

        if branch.institution != institution:
            raise validation_error("Branch does not belong to this institution.")

        admin = attrs.get("admin") or getattr(self.instance, "admin", None)
        if not admin:
            raise validation_error("Admin must be provided.")

        if not hasattr(admin, "profile"):
            raise validation_error("Admin profile is missing.")

        profile = getattr(admin, "profile", None)
        if not profile or profile.institution_id != institution.id:
            raise validation_error("Admin does not belong to this institution.")

        qs = BranchAdmin.objects.filter(
            branch=branch,
            admin=admin,
            deleted_at__isnull=True,
        )
        if self.instance:
            qs = qs.exclude(pk=self.instance.pk)

        if qs.exists():
            raise validation_error("This admin is already assigned to the branch.")

        return attrs

    def create(self, validated_data):
        request = self.context["request"]
        branch = validated_data.get("branch")
        admin = validated_data.get("admin")

        soft_deleted_admin = BranchAdmin.objects.filter(
            branch=branch,
            admin=admin,
            deleted_at__isnull=False,
        ).first()

        if soft_deleted_admin:
            soft_deleted_admin.deleted_at = None
            soft_deleted_admin.updated_by = request.user
            soft_deleted_admin.is_super_admin = validated_data.get(
                "is_super_admin", soft_deleted_admin.is_super_admin
            )
            soft_deleted_admin.save()
            return soft_deleted_admin

        validated_data["created_by"] = request.user
        validated_data["updated_by"] = request.user

        return super().create(validated_data)

    def update(self, instance, validated_data):
        request = self.context["request"]

        new_branch = validated_data.get("branch", instance.branch)
        new_admin = validated_data.get("admin", instance.admin)

        if new_branch != instance.branch or new_admin != instance.admin:

            qs = BranchAdmin.objects.filter(
                branch=new_branch,
                admin=new_admin,
                deleted_at__isnull=True,
            ).exclude(pk=instance.pk)

            if qs.exists():
                raise validation_error(
                    "This admin is already assigned to the selected branch."
                )

            instance.branch = new_branch
            instance.admin = new_admin

        if "is_super_admin" in validated_data:
            instance.is_super_admin = validated_data["is_super_admin"]

        instance.updated_by = request.user
        instance.save()

        return instance

    def to_representation(self, instance):
        data = super().to_representation(instance)

        if instance.branch:
            data["branch"] = {
                "id": instance.branch.id,
                "branch_name": instance.branch.branch_name,
                "base_uuid": instance.branch.base_uuid,
            }

        if instance.admin:
            data["admin"] = {
                "id": instance.admin.id,
                "fullname": instance.admin.fullname,
            }

        return data


class SimpleBranchSerializer(serializers.ModelSerializer):
    class Meta:
        model = Branch
        fields = [
            "id",
            "branch_name",
            "base_uuid",
            "reference_code",
            "branch_location",
        ]


class BranchSerializer(serializers.ModelSerializer):
    supported_currencies = BranchSupportedCurrencyInputSerializer(
        many=True, required=False, write_only=True
    )
    branch_admins = BranchAdminInputSerializer(
        many=True, required=False, write_only=True
    )
    children = serializers.SerializerMethodField()

    class Meta:
        model = Branch
        fields = "__all__"
        read_only_fields = [
            "base_uuid",
            "created_at",
            "updated_at",
            "approval_date",
            "created_by",
            "updated_by",
            "is_deleted",
            "institution",
            "children",
        ]

    def get_children(self, obj):
        children_qs = getattr(obj, "children", None)
        if children_qs is not None and children_qs.exists():
            return BranchSerializer(
                children_qs.filter(institution=obj.institution),
                many=True,
                context=self.context,
            ).data
        return []

    def validate_branch_admins(self, value):
        """Validate the branch_admins list."""
        if not isinstance(value, list):
            raise validation_error("branch_admins must be a list.")

        seen_admin_ids = set()
        super_admin_count = 0

        for item in value:
            admin = item.get("admin")

            if not admin:
                raise validation_error("Each branch admin entry must include an admin.")

            if admin.id in seen_admin_ids:
                raise validation_error("Duplicate admins are not allowed.")
            seen_admin_ids.add(admin.id)

            if item.get("is_super_admin"):
                super_admin_count += 1

        if super_admin_count > 1:
            raise validation_error("Only one super admin is allowed per branch.")

        return value

    @transaction.atomic
    def create(self, validated_data):
        supported_currencies = validated_data.pop("supported_currencies", None)
        branch_admins_data = validated_data.pop("branch_admins", None)
        request = self.context.get("request")

        validated_data["created_by"] = request.user
        validated_data["institution"] = get_institution(request)

        branch = Branch.objects.create(**validated_data)

        if supported_currencies:
            for currency_data in supported_currencies:
                BranchSupportedCurrency.objects.create(branch=branch, **currency_data)

        if branch_admins_data:
            for admin_data in branch_admins_data:

                admin_serializer_data = {
                    "admin": admin_data["admin"].id,
                    "branch": branch.id,
                    "is_super_admin": admin_data["is_super_admin"],
                }

                admin_serializer = BranchAdminSerializer(
                    data=admin_serializer_data, context=self.context
                )
                admin_serializer.is_valid(raise_exception=True)
                admin_serializer.save()

        return branch

    @transaction.atomic
    def update(self, instance, validated_data):
        supported_currencies = validated_data.pop("supported_currencies", None)
        branch_admins_data = validated_data.pop("branch_admins", None)
        request = self.context.get("request")

        validated_data["updated_by"] = request.user

        if supported_currencies is not None:
            existing_qs = BranchSupportedCurrency.objects.filter(branch=instance)
            existing_map = {sc.currency_id: sc for sc in existing_qs}
            incoming_currency_ids = set()

            for currency_data in supported_currencies:
                currency = currency_data["currency"]
                incoming_currency_ids.add(currency.id)

                if currency.id in existing_map:
                    obj = existing_map[currency.id]
                    obj.rate = currency_data.get("rate", obj.rate)
                    obj.save()
                else:
                    BranchSupportedCurrency.objects.create(
                        branch=instance, **currency_data
                    )

            existing_qs.exclude(currency_id__in=incoming_currency_ids).delete()

        if branch_admins_data is not None:
            existing_qs = instance.branch_admin_links.filter(deleted_at__isnull=True)
            existing_map = {ba.admin_id: ba for ba in existing_qs}
            incoming_admin_ids = set()

            for admin_data in branch_admins_data:
                admin = admin_data["admin"]
                incoming_admin_ids.add(admin.id)

                admin_serializer_data = {
                    "admin": admin.id,
                    "branch": instance.id,
                    "is_super_admin": admin_data["is_super_admin"],
                }

                if admin.id in existing_map:
                    instance_admin = existing_map[admin.id]
                    admin_serializer = BranchAdminSerializer(
                        instance=instance_admin,
                        data=admin_serializer_data,
                        context=self.context,
                    )
                else:
                    admin_serializer = BranchAdminSerializer(
                        data=admin_serializer_data, context=self.context
                    )

                admin_serializer.is_valid(raise_exception=True)
                admin_serializer.save()

            removed_admins = existing_qs.exclude(admin_id__in=incoming_admin_ids)
            for admin in removed_admins:
                admin.deleted_at = timezone.now()
                admin.updated_by = request.user
                admin.save()

        return super().update(instance, validated_data)

    def to_representation(self, instance):
        repr = super().to_representation(instance)

        repr["currency"] = (
            SystemCurrencySerializer(instance.currency).data
            if instance.currency
            else None
        )

        repr["supported_currencies"] = (
            BranchSupportedCurrencySerializer(
                instance.supported_currencies_links.all(), many=True
            ).data
            if instance.supported_currencies_links.exists()
            else []
        )

        repr["admins"] = (
            BranchAdminSerializer(
                instance.branch_admin_links.filter(deleted_at__isnull=True),
                many=True,
                context=self.context,
            ).data
            if instance.branch_admin_links.filter(deleted_at__isnull=True).exists()
            else []
        )

        if instance.inventory_cost_variance_account:
            repr["inventory_cost_variance_account"] = {
                "id": instance.inventory_cost_variance_account.id,
                "base_uuid": instance.inventory_cost_variance_account.base_uuid,
                "account_name": instance.inventory_cost_variance_account.account_name,
                "reference_code": instance.inventory_cost_variance_account.reference_code,
            }

        else:
            repr["inventory_cost_variance_account"] = None

        return repr


class InstitutionWithBranchesSerializer(InstitutionSerializer):
    branches = serializers.SerializerMethodField()

    class Meta(InstitutionSerializer.Meta):
        model = Institution
        fields = InstitutionSerializer.Meta.fields + ["branches"]

    def get_branches(self, institution):
        user = self.context.get("user")
        institution_branches = institution.branches.undeleted()

        if user and institution.institution_owner == user:
            branches = institution_branches.active()
        else:
            user_branches = (
                UserBranch.objects.active()
                .filter(user=user)
                .values_list(
                    "branch_id",
                    flat=True,
                )
            )
            branches = institution_branches.active().filter(id__in=user_branches)

        return SimpleBranchSerializer(branches, many=True).data


class UserBranchSerializer(serializers.ModelSerializer):
    user_details = CustomUserSerializer(source="user", read_only=True)
    branch_details = BranchSerializer(source="branch", read_only=True)

    class Meta:
        model = UserBranch
        fields = [
            "id",
            "user",
            "branch",
            "is_default",
            "user_details",
            "branch_details",
        ]

    def create(self, validated_data):
        request = self.context.get("request")
        if not request or not request.user.is_authenticated:
            raise validation_error(
                "User must be authenticated to create a user branch."
            )
        return UserBranch.objects.create(created_by=request.user, **validated_data)


class BusinessFinancialDocumentsSerializer(
    Base64FileFieldMixin,
    BaseApprovableSerializer,
):

    base64_file_fields = ["attachment"]

    class Meta:
        model = BusinessFinancialDocuments
        fields = "__all__"

    def validate(self, data):
        issue_date = data.get("issue_date")
        expiry_date = data.get("expiry_date")

        if issue_date and expiry_date and issue_date > expiry_date:
            raise validation_error(
                {"issue_date": "Issue date cannot be after the expiry date."}
            )

        return data

    def to_representation(self, instance):
        repr = super().to_representation(instance)

        if instance.branch:
            repr["branch"] = {
                "id": instance.branch.id,
                "branch_name": instance.branch.branch_name,
                "base_uuid": instance.branch.base_uuid,
                "reference_code": instance.branch.reference_code,
            }

        repr["category"] = {
            "id": instance.category.id,
            "name": instance.category.name,
            "description": instance.category.description,
            "base_uuid": instance.category.base_uuid,
            "reference_code": instance.category.reference_code,
        }
        return repr


class BusinessDocumentCategorySerializer(
    BaseApprovableSerializer,
):
    system_category_code = serializers.CharField(
        required=False,
        write_only=True,
    )

    class Meta:
        model = BusinessDocumentCategory
        fields = "__all__"
        read_only_fields = ["base_uuid", "created_at", "updated_at", "institution"]

    def validate(self, attrs):
        system_category_code = attrs.pop("system_category_code", None)

        if system_category_code:
            try:
                system_category_exists = (
                    SystemSupportedFinancialDocumentsCategory.objects.get(
                        category_code=system_category_code
                    )
                )
            except SystemSupportedFinancialDocumentsCategory.DoesNotExist:
                raise validation_error(
                    f"Category with code {system_category_code} does not exist."
                )

            attrs["system_category"] = system_category_exists

        return super().validate(attrs)

    def to_representation(self, instance):
        repr = super().to_representation(instance)
        repr["institution"] = InstitutionSerializer(instance.institution).data
        repr["system_category"] = SystemSupportedFinancialDocumentsCategorySerializer(
            instance.system_category
        ).data
        return repr

    def create(self, validated_data):
        request = self.context.get("request")
        if not request or not request.user.is_authenticated:
            raise validation_error(
                "User must be authenticated to create a business document category."
            )
        validated_data["institution"] = get_institution(request)
        return super().create(validated_data)


class InstitutionItemReturnReasonSerializer(BaseApprovableSerializer):

    class Meta:
        model = InstitutionItemReturnReason
        fields = "__all__"
        read_only_fields = [
            "base_uuid",
            "created_at",
            "updated_at",
            "institution",
        ]

    def create(self, validated_data):
        request = self.context.get("request")
        validated_data["institution"] = get_institution(request)
        return super().create(validated_data)


class ActInstitutionOwnerSerializer(serializers.Serializer):
    fullname = serializers.CharField(max_length=255)
    email = serializers.EmailField(required=False, allow_null=True, allow_blank=True)
    username = serializers.CharField(required=False, allow_null=True, allow_blank=True)
    phone_number = serializers.CharField(
        max_length=20, required=False, allow_blank=True, allow_null=True
    )
    gender = serializers.ChoiceField(
        choices=[("MALE", "Male"), ("FEMALE", "Female"), ("OTHER", "Other")],
        required=False,
        default="OTHER",
    )
    internal_base_uuid = serializers.CharField(allow_blank=False, required=True)

    external_base_uuid = serializers.UUIDField(
        required=False,
        allow_null=True,
    )
    profile_photo_base64 = serializers.CharField(
        required=False,
        allow_blank=True,
        allow_null=True,
    )
    signature_base64 = serializers.CharField(
        required=False,
        allow_blank=True,
        allow_null=True,
    )

    def validate(self, attrs):
        identifiers = [
            (attrs.get("email") or "").strip(),
            (attrs.get("username") or "").strip(),
            (attrs.get("phone_number") or "").strip(),
        ]

        if not any(identifiers):
            raise validation_error(
                "At least one of email, username, or phone_number is required."
            )

        return attrs


class ActInstitutionGeneralInfoSerializer(serializers.Serializer):
    institution_name = serializers.CharField(max_length=255)
    institution_email = serializers.EmailField()
    first_phone_number = serializers.CharField(max_length=20)
    second_phone_number = serializers.CharField(
        max_length=20,
        required=False,
        allow_blank=True,
        allow_null=True,
    )
    location = serializers.CharField(max_length=500)
    description = serializers.CharField(
        max_length=1000,
        required=False,
        allow_blank=True,
        allow_null=True,
    )
    institution_owner = ActInstitutionOwnerSerializer()
    internal_base_uuid = serializers.CharField(allow_blank=False, required=True)
    theme_color = serializers.CharField(
        max_length=20, allow_blank=True, required=False, allow_null=True
    )
    user_inactivity_time = serializers.IntegerField(
        required=False,
        allow_null=True,
    )
    date_format = serializers.CharField(
        max_length=20,
        allow_blank=True,
        required=False,
    )
    default_pagination_page_size = serializers.IntegerField(required=False)
    external_base_uuid = serializers.UUIDField(
        required=False,
        allow_null=True,
    )


class ActInstitutionBranchSerializer(serializers.Serializer):
    branch_name = serializers.CharField(max_length=255)
    branch_email = serializers.EmailField(allow_blank=True, required=False)
    branch_phone_number = serializers.CharField(
        max_length=20, allow_blank=True, required=False, allow_null=True
    )
    branch_location = serializers.CharField(
        max_length=500,
        allow_blank=True,
        required=False,
        allow_null=True,
    )
    branch_opening_time = serializers.TimeField()
    branch_closing_time = serializers.TimeField()
    internal_base_uuid = serializers.CharField(allow_blank=False, required=True)
    external_base_uuid = serializers.UUIDField(
        required=False,
        allow_null=True,
    )


class ActAccountingUserSerializer(serializers.Serializer):
    email = serializers.EmailField(
        required=False,
        allow_null=True,
        allow_blank=True,
    )
    phone_number = serializers.CharField(
        required=False,
        allow_null=True,
        allow_blank=True,
    )
    username = serializers.CharField(
        required=False,
        allow_null=True,
        allow_blank=True,
    )
    gender = serializers.ChoiceField(
        choices=[("MALE", "Male"), ("FEMALE", "Female"), ("OTHER", "Other")],
        required=False,
        default="OTHER",
    )
    fullname = serializers.CharField(
        required=False,
        allow_null=True,
        allow_blank=True,
    )
    branches = serializers.ListField(
        child=serializers.CharField(max_length=255),
        required=False,
        default=[],
    )
    role_internal_base_uuid = serializers.CharField(
        allow_blank=False,
        required=True,
    )
    internal_base_uuid = serializers.CharField(allow_blank=False, required=True)
    external_base_uuid = serializers.UUIDField(
        required=False,
        allow_null=True,
    )
    profile_photo_base64 = serializers.CharField(
        required=False,
        allow_blank=True,
        allow_null=True,
    )
    signature_base64 = serializers.CharField(
        required=False,
        allow_blank=True,
        allow_null=True,
    )

    def _get_identifier_values(self, data):
        return {
            "email": (data.get("email") or "").strip(),
            "username": (data.get("username") or "").strip(),
            "phone_number": (data.get("phone_number") or "").strip(),
        }

    def _sync_user_roles(self, user, role_internal_base_uuid, institution):
        role = (
            Role.objects.undeleted()
            .filter(
                institution=institution,
                external_base_uuid=role_internal_base_uuid,
            )
            .first()
        )

        if not role:
            raise validation_error(
                {
                    "role_internal_base_uuid": (
                        "Invalid role internal_base_uuid. The role must belong "
                        "to the institution being synchronized."
                    )
                }
            )

        return RoleAssignmentService.assign_institution_role(
            user=user,
            role=role,
        )

    def _sync_user_branches(self, user, branch_external_base_uuids, institution):
        if not branch_external_base_uuids:
            return

        branch_external_base_uuids = list(dict.fromkeys(branch_external_base_uuids))

        branches = list(
            Branch.objects.filter(
                institution=institution,
                external_base_uuid__in=branch_external_base_uuids,
            )
        )
        found_branch_uuids = {str(branch.external_base_uuid) for branch in branches}

        missing_branch_uuids = [
            branch_uuid
            for branch_uuid in branch_external_base_uuids
            if str(branch_uuid) not in found_branch_uuids
        ]

        if missing_branch_uuids:
            raise validation_error(
                {
                    "branches": (
                        "Invalid branch internal_base_uuid(s): "
                        f"{', '.join(map(str, missing_branch_uuids))}. "
                        "Each accounting user branch must match an institution_branches "
                        "internal_base_uuid for this institution."
                    )
                }
            )

        branch_ids = {branch.id for branch in branches}
        UserBranch.objects.filter(
            user=user,
            branch__institution=institution,
        ).exclude(branch_id__in=branch_ids).delete()

        existing_branch_ids = set(
            UserBranch.objects.filter(user=user, branch__in=branches).values_list(
                "branch_id", flat=True
            )
        )
        UserBranch.objects.bulk_create(
            [
                UserBranch(user=user, branch=branch)
                for branch in branches
                if branch.id not in existing_branch_ids
            ]
        )

    def validate(self, attrs):
        if not attrs.get("branches"):
            attrs["branches"] = []

        identifiers = self._get_identifier_values(attrs)

        if not any(identifiers.values()):
            raise validation_error(
                "At least one of email, username, or phone_number is required."
            )

        return attrs


class ActFixedAssetsSerializer(serializers.Serializer):

    asset_code = serializers.CharField(max_length=255)
    asset_name = serializers.CharField(max_length=255)
    asset_description = serializers.CharField(required=False, allow_blank=True)
    internal_base_uuid = serializers.CharField(allow_blank=False, required=True)
    external_base_uuid = serializers.UUIDField(
        required=False,
        allow_null=True,
    )


class ActInstitutionBankSerializer(serializers.Serializer):
    account_name = serializers.CharField(max_length=255)
    account_number = serializers.CharField(max_length=255)
    bank_name = serializers.CharField(max_length=255)
    description = serializers.CharField(required=False, allow_blank=True)
    account_balance = serializers.DecimalField(
        max_digits=20,
        decimal_places=4,
        required=False,
    )
    internal_base_uuid = serializers.CharField(allow_blank=False, required=True)
    external_base_uuid = serializers.UUIDField(
        required=False,
        allow_null=True,
    )


class ActInstitutionRoleSerializer(serializers.Serializer):
    role_name = serializers.CharField(
        max_length=255,
        required=True,
    )
    role_description = serializers.CharField(
        max_length=500,
        required=False,
        allow_blank=True,
    )
    internal_base_uuid = serializers.CharField(
        allow_blank=False,
        required=True,
    )
    external_base_uuid = serializers.UUIDField(
        required=False,
        allow_null=True,
    )


class InstitutionBaisoftPayDigitalWalletSerializer(serializers.Serializer):

    account_name = serializers.CharField(max_length=255, required=True)

    account_balance = serializers.DecimalField(
        max_digits=50,
        decimal_places=20,
        default=Decimal("0.0"),
    )

    wallet_email = serializers.EmailField(required=False)

    wallet_id = serializers.CharField(max_length=255, required=True)

    custodian_external_identifier = serializers.CharField(
        max_length=255,
        required=False,
        allow_blank=True,
        allow_null=True,
    )

    branch_external_base_uuid = serializers.CharField(
        max_length=255,
        required=False,
        allow_null=True,
        allow_blank=True,
    )

    currency_code = serializers.CharField(
        max_length=10,
        required=False,
    )

    internal_base_uuid = serializers.CharField(allow_blank=False, required=True)
    external_base_uuid = serializers.UUIDField(
        required=False,
        allow_null=True,
    )


class ActSupraledgerActivationSerializer(serializers.Serializer):

    institution_info = ActInstitutionGeneralInfoSerializer(required=True)

    institution_branches = ActInstitutionBranchSerializer(many=True, required=False)

    accounting_users = ActAccountingUserSerializer(many=True, required=False)

    fixed_assets = ActFixedAssetsSerializer(many=True, required=False)

    banks = ActInstitutionBankSerializer(many=True, required=False)

    baisoft_pay_digital_wallets = InstitutionBaisoftPayDigitalWalletSerializer(
        many=True,
        required=False,
    )

    institution_roles = ActInstitutionRoleSerializer(
        many=True,
        required=False,
    )

    callback_url = serializers.URLField(required=False, allow_blank=True)

    def to_representation(self, instance):
        institution_info = instance["institution"]
        institution_owner = instance["institution_owner"]
        owner_external_identity = instance["owner_external_identity"]
        institution_branches = instance.get("institution_branches", [])
        accounting_users = instance.get("accounting_users", [])
        external_identities = instance.get("external_identities", [])
        fixed_assets = instance.get("fixed_assets", [])
        bank_accounts = instance.get("bank_accounts", [])
        baisoft_pay_digital_wallets = instance.get("baisoft_pay_digital_wallets", [])
        institution_roles = instance.get("institution_roles", [])

        accounting_users_with_identity = []

        for idx, user in enumerate(accounting_users):
            external_identity = None
            if idx < len(external_identities):
                identity = external_identities[idx]
                external_identity = {
                    "base_uuid": identity.external_base_uuid,
                    "external_base_uuid": identity.base_uuid,
                }

            accounting_users_with_identity.append(
                {
                    "fullname": user.fullname,
                    "email": user.email,
                    "external_identity": external_identity,
                }
            )

        return {
            "status": "success",
            "institution_info": {
                "external_base_uuid": institution_info.base_uuid,
                "name": institution_info.institution_name,
                "email": institution_info.institution_email,
                "institution_owner": {
                    "fullname": institution_owner.fullname,
                    "email": institution_owner.email,
                    "external_identity": {
                        "base_uuid": owner_external_identity.external_base_uuid,
                        "external_base_uuid": owner_external_identity.base_uuid,
                    },
                },
            },
            "institution_branches": [
                {
                    "base_uuid": b.base_uuid,
                    "branch_name": b.branch_name,
                    "branch_location": b.branch_location,
                    "external_base_uuid": b.base_uuid,
                    "internal_base_uuid": b.external_base_uuid,
                }
                for b in institution_branches
            ],
            "accounting_users": accounting_users_with_identity,
            "fixed_assets": [
                {
                    "base_uuid": a.external_base_uuid,
                    "asset_code": a.reference_code,
                    "asset_name": a.asset_name,
                    "description": a.description,
                    "external_base_uuid": a.base_uuid,
                    "internal_base_uuid": a.external_base_uuid,
                }
                for a in fixed_assets
            ],
            "bank_accounts": [
                {
                    "account_name": b.account_name,
                    "account_number": b.account_number,
                    "bank_name": b.bank_name,
                    "external_base_uuid": b.base_uuid,
                    "internal_base_uuid": b.external_base_uuid,
                }
                for b in bank_accounts
            ],
            "baisoft_pay_digital_wallets": [
                {
                    "external_base_uuid": wallet.base_uuid,
                    "internal_base_uuid": wallet.external_base_uuid,
                }
                for wallet in baisoft_pay_digital_wallets
            ],
            "institution_roles": [
                {
                    "role_name": r.name,
                    "role_description": r.description,
                    "external_base_uuid": r.base_uuid,
                    "internal_base_uuid": r.external_base_uuid,
                }
                for r in institution_roles
            ],
        }

    def create(self, validated_data):

        from .services import IdentityService

        partner_system = self.context.get("partner_system")

        branches_data = validated_data.pop("institution_branches", [])
        institution_roles_data = validated_data.pop("institution_roles", [])
        accounting_users_data = validated_data.pop("accounting_users", [])
        fixed_assets_data = validated_data.pop("fixed_assets", [])
        banks_data = validated_data.pop("banks", [])
        institution_baisoft_pay_digital_wallets_data = validated_data.pop(
            "baisoft_pay_digital_wallets", []
        )

        institution_info = validated_data.pop("institution_info")

        institution_owner_data = institution_info.get("institution_owner")

        their_institution_id = institution_info["internal_base_uuid"]
        our_institution_id = institution_info.get("external_base_uuid")

        with db_transaction.atomic():

            institution = (
                Institution.objects.filter(
                    base_uuid=our_institution_id,
                ).first()
                if our_institution_id
                else None
            )

            institution_created = institution is None
            owner_user = None
            owner_external_identity = None

            local_owner_identity_uuid = institution_owner_data.get("external_base_uuid")

            if not institution_created and local_owner_identity_uuid:
                owner_external_identity = (
                    ExternalIdentity.objects.select_related("user")
                    .filter(
                        base_uuid=local_owner_identity_uuid,
                        partner_system=partner_system,
                        institution=institution,
                    )
                    .first()
                )

                if owner_external_identity:
                    owner_user = owner_external_identity.user
                    owner_user.is_active = True
                    owner_user.save(update_fields=["is_active"])

            if institution_created:

                if owner_user is None:
                    owner_user = IdentityService.get_or_create_user(
                        email=institution_owner_data.get("email"),
                        username=institution_owner_data.get("username"),
                        phone_number=institution_owner_data.get("phone_number"),
                        defaults={
                            "fullname": institution_owner_data["fullname"],
                            "gender": institution_owner_data.get("gender", "OTHER"),
                        },
                    )

                profile = IdentityService.ensure_profile(owner_user)

                institution = Institution(
                    institution_owner=owner_user,
                    institution_name=institution_info["institution_name"],
                    institution_email=institution_info["institution_email"],
                    first_phone_number=institution_info["first_phone_number"],
                    second_phone_number=institution_info.get("second_phone_number"),
                    location=institution_info["location"],
                    description=institution_info.get("description"),
                    external_base_uuid=their_institution_id,
                    theme_color=institution_info.get("theme_color"),
                    user_inactivity_time=institution_info.get("user_inactivity_time"),
                    date_format=institution_info.get("date_format"),
                    default_pagination_page_size=institution_info.get(
                        "default_pagination_page_size"
                    ),
                    approval_status="approved",
                )

                institution.save(skip_main_branch_creation=True)

                IdentityService.ensure_profile_institution(
                    profile,
                    institution,
                    signature_base64=institution_owner_data.get(
                        "signature_base64", None
                    ),
                    profile_photo_base64=institution_owner_data.get(
                        "profile_photo_base64", None
                    ),
                )

            else:

                if owner_user is None:
                    owner_user = IdentityService.get_or_create_user(
                        email=institution_owner_data.get("email"),
                        username=institution_owner_data.get("username"),
                        phone_number=institution_owner_data.get("phone_number"),
                        defaults={
                            "fullname": institution_owner_data["fullname"],
                            "gender": institution_owner_data.get("gender", "OTHER"),
                        },
                    )

                profile = IdentityService.ensure_profile(owner_user)

                institution.institution_name = institution_info["institution_name"]
                institution.institution_email = institution_info["institution_email"]
                institution.first_phone_number = institution_info["first_phone_number"]
                institution.second_phone_number = institution_info.get(
                    "second_phone_number"
                )
                institution.location = institution_info["location"]
                institution.description = institution_info.get("description")
                institution.theme_color = institution_info.get("theme_color")
                institution.user_inactivity_time = institution_info.get(
                    "user_inactivity_time"
                )
                institution.date_format = institution_info.get("date_format")
                institution.default_pagination_page_size = institution_info.get(
                    "default_pagination_page_size"
                )
                institution.external_base_uuid = their_institution_id
                institution.approval_status = "approved"

                IdentityService.ensure_profile_institution(
                    profile,
                    institution,
                    signature_base64=institution_owner_data.get(
                        "signature_base64", None
                    ),
                    profile_photo_base64=institution_owner_data.get(
                        "profile_photo_base64", None
                    ),
                )

            owner_ext_uuid = institution_owner_data["internal_base_uuid"]

            owner_external_identity = IdentityService.ensure_external_identity(
                user=owner_user,
                partner_system=partner_system,
                institution=institution,
                external_base_uuid=owner_ext_uuid,
                identity=owner_external_identity,
            )

            institution.institution_owner = owner_user
            institution.save()

            branches = InstitutionDataSyncService.sync_branches(
                institution=institution,
                branches_data=branches_data,
            )

            institution_roles = InstitutionDataSyncService.sync_roles(
                institution=institution,
                institution_roles_data=institution_roles_data,
            )

            accounting_users = []
            external_identities = []
            accounting_user_serializer = self.fields["accounting_users"].child

            for user_data in accounting_users_data:
                ext_uuid = user_data["internal_base_uuid"]
                local_external_identity_uuid = user_data.get("external_base_uuid")

                ext_identity = (
                    ExternalIdentity.objects.select_related("user")
                    .filter(
                        base_uuid=local_external_identity_uuid,
                        partner_system=partner_system,
                        institution=institution,
                    )
                    .first()
                    if local_external_identity_uuid
                    else None
                )

                branch_ext_uuids = user_data.get("branches", [])
                role_ext_uuid = user_data["role_internal_base_uuid"]

                if ext_identity:
                    user = ext_identity.user
                    user.is_active = True
                    user.save(update_fields=["is_active"])

                    ext_identity = IdentityService.ensure_external_identity(
                        user=user,
                        partner_system=partner_system,
                        institution=institution,
                        external_base_uuid=ext_uuid,
                        identity=ext_identity,
                    )

                else:
                    identifiers = accounting_user_serializer._get_identifier_values(
                        user_data
                    )
                    user = None

                    if identifiers["email"]:
                        user = CustomUser.objects.filter(
                            email__iexact=identifiers["email"]
                        ).first()
                    elif identifiers["username"]:
                        user = CustomUser.objects.filter(
                            username__iexact=identifiers["username"]
                        ).first()
                    elif identifiers["phone_number"]:
                        user = CustomUser.objects.filter(
                            phone_number__iexact=identifiers["phone_number"]
                        ).first()

                    if not user:
                        new_user_data = {
                            "email": identifiers["email"] or None,
                            "fullname": user_data.get("fullname", ""),
                            "phone_number": identifiers["phone_number"],
                            "is_email_verified": True,
                            "gender": user_data.get("gender", "OTHER"),
                            "is_active": True,
                        }

                        if identifiers["username"]:
                            new_user_data["username"] = identifiers["username"]

                        user = CustomUser.objects.create(**new_user_data)

                    ext_identity = IdentityService.ensure_external_identity(
                        user=user,
                        partner_system=partner_system,
                        institution=institution,
                        external_base_uuid=ext_uuid,
                    )

                profile = IdentityService.ensure_profile(user)
                IdentityService.ensure_profile_institution(
                    profile,
                    institution,
                    signature_base64=user_data.get("signature_base64", None),
                    profile_photo_base64=user_data.get("profile_photo_base64", None),
                )

                accounting_user_serializer._sync_user_branches(
                    user,
                    branch_ext_uuids,
                    institution,
                )
                accounting_user_serializer._sync_user_roles(
                    user,
                    role_ext_uuid,
                    institution,
                )

                accounting_users.append(user)
                external_identities.append(ext_identity)

            fixed_assets = InstitutionDataSyncService.sync_fixed_assets(
                institution=institution,
                fixed_assets_data=fixed_assets_data,
            )

            bank_accounts = InstitutionDataSyncService.sync_bank_accounts(
                institution=institution,
                banks_data=banks_data,
            )

            institution_baisoft_pay_digital_wallets_data = InstitutionDataSyncService.sync_baisoft_pay_digital_wallets(
                institution=institution,
                baisoft_pay_digital_wallets_data=institution_baisoft_pay_digital_wallets_data,
            )

            return {
                "institution": institution,
                "institution_owner": owner_user,
                "owner_external_identity": owner_external_identity,
                "institution_branches": branches,
                "institution_roles": institution_roles,
                "accounting_users": accounting_users,
                "external_identities": external_identities,
                "fixed_assets": fixed_assets,
                "bank_accounts": bank_accounts,
                "baisoft_pay_digital_wallets": institution_baisoft_pay_digital_wallets_data,
            }


class CustomUserLiteSerializer(serializers.ModelSerializer):
    class Meta:
        model = CustomUser
        fields = ["id", "fullname", "email"]
        read_only_fields = fields


class RoleLiteSerializer(serializers.ModelSerializer):
    """Minimal serializer for Role details (read-only payload)."""

    class Meta:
        model = Role
        fields = ["id", "name"]
        read_only_fields = fields


class AnnouncementSerializer(serializers.ModelSerializer):

    target_users_ids = serializers.ListField(
        child=serializers.PrimaryKeyRelatedField(queryset=CustomUser.objects.all()),
        write_only=True,
        required=False,
        allow_empty=True,
        help_text="List of CustomUser IDs to target.",
    )
    target_roles_ids = serializers.ListField(
        child=serializers.PrimaryKeyRelatedField(queryset=Role.objects.all()),
        write_only=True,
        required=False,
        allow_empty=True,
        help_text="List of Role IDs to target.",
    )

    # Read-only fields for output (full details of targeted users/roles)
    # target_users = CustomUserLiteSerializer(many=True, read_only=True)
    # target_roles = RoleLiteSerializer(many=True, read_only=True)

    class Meta:
        model = Announcement
        fields = [
            "id",
            "base_uuid",
            "title",
            "content",
            "requires_acknowledgment",
            "is_targetted_to_all_users",
            "is_role_targetted",
            # M2M Fields (Read-only for output)
            # "target_users",
            # "target_roles",
            # Write-Only IDs for input
            "target_users_ids",
            "target_roles_ids",
            # Inherited/System fields
            "approval_status",
            "created_at",
        ]
        read_only_fields = [
            "id",
            "base_uuid",
            "institution_name",
            "target_users",
            "target_roles",
            "approval_status",
            "created_at",
        ]
        extra_kwargs = {
            # institution is read_only on the model, but we need it for write
            "institution": {"write_only": True, "required": True},
        }

    def validate(self, data):
        """
        Performs conditional validation based on targeting flags.
        """
        is_all = data.get(
            "is_targetted_to_all_users",
            getattr(self.instance, "is_targetted_to_all_users", True),
        )
        is_role = data.get(
            "is_role_targetted", getattr(self.instance, "is_role_targetted", False)
        )

        # Get target IDs from the write_only fields
        target_users_ids = data.get("target_users_ids", [])
        target_roles_ids = data.get("target_roles_ids", [])

        # Target All Users: No specific users/roles should be provided.
        if is_all:
            if target_users_ids or target_roles_ids:
                raise validation_error(
                    {
                        "target_users_ids": "Target users/roles cannot be provided when targeting all users."
                    }
                )

        # Targeted to Specific Users (no role targeting)
        elif not is_role:
            if not target_users_ids:
                raise validation_error(
                    {
                        "target_users_ids": "When not targeting all users and not targeting roles, specific users must be provided."
                    }
                )

        # Role Targeting (roles required, users optional)
        elif is_role:
            if not target_roles_ids:
                raise validation_error(
                    {
                        "target_roles_ids": "Target roles must be provided when role targeting is active."
                    }
                )

        # Remove the temporary ID lists from validated data
        data.pop("target_users_ids", None)
        data.pop("target_roles_ids", None)

        return data

    def _update_m2m(self, instance, target_users_ids, target_roles_ids):
        """Helper to clear and set M2M relationships."""
        if target_users_ids is not None:
            instance.target_users.set(target_users_ids)

        if target_roles_ids is not None:
            instance.target_roles.set(target_roles_ids)

    @transaction.atomic
    def create(self, validated_data):
        # We temporarily store the IDs before popping them in validate
        target_users_ids = self.initial_data.get("target_users_ids")
        target_roles_ids = self.initial_data.get("target_roles_ids")

        # Create the Announcement instance
        announcement = super().create(validated_data)

        # Handle M2M relationships
        self._update_m2m(announcement, target_users_ids, target_roles_ids)

        return announcement

    @transaction.atomic
    def update(self, instance, validated_data):
        # We retrieve M2M IDs from the serializer's initial data if present
        target_users_ids = self.initial_data.get("target_users_ids")
        target_roles_ids = self.initial_data.get("target_roles_ids")

        # Update the Announcement instance
        announcement = super().update(instance, validated_data)

        # Only update M2M fields if the corresponding ID list was provided in the request
        if "target_users_ids" in self.initial_data:
            self._update_m2m(announcement, target_users_ids, None)

        if "target_roles_ids" in self.initial_data:
            self._update_m2m(announcement, None, target_roles_ids)

        return announcement


class CustomUserLiteSerializer(serializers.ModelSerializer):
    """Minimal serializer for CustomUser details (read-only payload)."""

    class Meta:
        model = CustomUser
        fields = ["id", "fullname", "email"]
        read_only_fields = fields


class AnnouncementTargetUserSerializer(serializers.ModelSerializer):
    """
    Serializer for the intermediary model, linking an Announcement to a CustomUser.

    It outputs the user's details but expects the user ID for write operations.
    """

    user_details = CustomUserLiteSerializer(source="user", read_only=True)

    class Meta:
        model = AnnouncementTargetUser
        fields = [
            "id",
            "announcement",
            "user",  # Used for input (ID) and object relationship
            "user_details",  # Used for output (User name/email)
        ]

        extra_kwargs = {
            "announcement": {"write_only": True, "required": True},
            "user": {"write_only": True},
        }


class AnnouncementLiteSerializer(serializers.Serializer):
    """Minimal serializer for Announcement details (read-only payload)."""

    id = serializers.IntegerField(read_only=True)
    title = serializers.CharField(read_only=True)


class UserAnnouncementAcknowledgmentSerializer(serializers.ModelSerializer):
    """
    Serializer for the UserAnnouncementAcknowledgment model.
    Handles creation (acknowledgment) and retrieval.
    """

    user_details = CustomUserLiteSerializer(read_only=True)
    announcement_details = AnnouncementLiteSerializer(
        source="announcement", read_only=True
    )

    is_created = False

    class Meta:
        model = UserAnnouncementAcknowledgment
        fields = [
            "id",
            "user",
            "user_details",
            "announcement",
            "announcement_details",
            "acknowledged",
            "acknowledged_at",
        ]
        read_only_fields = [
            "id",
            "user_details",
            "announcement_details",
            "acknowledged_at",
        ]

        extra_kwargs = {
            "user": {"write_only": True, "required": False},
            "announcement": {"required": True},
        }

    def create(self, validated_data):
        """
        Custom create method to handle idempotency based on unique_together constraint.
        If the link already exists, we return the existing instance and set is_created=False.

        It also automatically sets 'acknowledged=True' and 'acknowledged_at' on creation.
        """
        user = validated_data.get("user")
        announcement = validated_data.get("announcement")

        try:
            instance = UserAnnouncementAcknowledgment.objects.get(
                user=user, announcement=announcement
            )
            self.is_created = False
            return instance
        except UserAnnouncementAcknowledgment.DoesNotExist:
            validated_data["acknowledged"] = True
            validated_data["acknowledged_at"] = timezone.now()

            instance = super().create(validated_data)
            self.is_created = True
            return instance

    def update(self, instance, validated_data):
        """
        Prevent changing user/announcement fields on update.
        Only allows updating 'acknowledged' status and 'acknowledged_at' (if logic permits).
        """

        # If 'acknowledged' is set to False (revoking acknowledgment), update acknowledged_at to None
        if validated_data.get("acknowledged") is False:
            validated_data["acknowledged_at"] = None

        # If 'acknowledged' is being set to True, update acknowledged_at to now
        elif (
            validated_data.get("acknowledged") is True
            and instance.acknowledged is False
        ):
            validated_data["acknowledged_at"] = timezone.now()

        return super().update(instance, validated_data)


class RoleLiteSerializer(serializers.ModelSerializer):
    """Minimal serializer for the Role model (read-only payload)."""

    class Meta:
        model = Role
        fields = ["id", "name", "description"]
        read_only_fields = ["id", "name", "description"]


class AnnouncementTargetRoleSerializer(serializers.ModelSerializer):
    """
    Serializer for the intermediary model, linking an Announcement to a Role.

    It outputs the role's details but expects the role ID for write operations.
    """

    # Nested serializer for read operations to show role name/description
    role_details = RoleLiteSerializer(source="role", read_only=True)

    class Meta:
        model = AnnouncementTargetRole
        fields = [
            "id",
            "announcement",
            "role",  # Used for input (ID) and object relationship
            "role_details",  # Used for output (Role details)
        ]

        extra_kwargs = {
            # Both IDs are required for creation
            "announcement": {"required": True},
            "role": {"required": True},
        }

        # The core fields are read-only for output, but kept in fields to allow input
        read_only_fields = ["id", "role_details"]


class NoteSerializer(serializers.ModelSerializer):
    user_details = CustomUserLiteSerializer(source="user", read_only=True)

    class Meta:
        model = Notes
        fields = [
            "id",
            "user",
            "user_details",
            "title",
            "content",
            "is_pinned",
            "created_at",
            "updated_at",
            "base_uuid",
        ]

        read_only_fields = [
            "id",
            "base_uuid",
            "user_details",
            "created_at",
            "updated_at",
        ]

        extra_kwargs = {"user": {"required": False}, "is_pinned": {"required": False}}

    def validate(self, attrs):
        request = self.context.get("request")

        if request and hasattr(request, "user"):
            attrs["user"] = request.user
        else:
            raise validation_error("Authenticated user is required.")

        return attrs


class InstitutionFeatureStatusSerializer(serializers.ModelSerializer):

    class Meta:
        model = InstitutionFeatureStatus
        fields = "__all__"
        read_only_fields = [
            "base_uuid",
            "created_at",
            "updated_at",
            "institution",
            "reference_code",
        ]

    def to_representation(self, instance):
        repr = super().to_representation(instance)
        repr["system_feature"] = SystemFeatureSerializer(instance.system_feature).data
        return repr


class InstitutionKYCDocumentSerializer(BaseApprovableSerializer):
    category = serializers.PrimaryKeyRelatedField(
        queryset=SystemKYCDocumentCategory.objects.all()
    )

    class Meta:
        model = InstitutionKYCDocument
        fields = "__all__"

    def validate(self, data):
        """
        Ensure issue_date is not after expiry_date.
        """
        issue_date = data.get("issue_date")
        expiry_date = data.get("expiry_date")

        if issue_date and expiry_date and issue_date > expiry_date:
            raise validation_error(
                {"issue_date": "Issue date cannot be after the expiry date."}
            )
        return data

    def create(self, validated_data):
        institution = self.context.get("institution")
        if not institution:
            raise validation_error("Institution context is required.")

        if not validated_data.get("document_name"):
            validated_data["document_name"] = validated_data["category"].category_name

        return InstitutionKYCDocument.objects.create(
            institution=institution, **validated_data
        )

    def update(self, instance, validated_data):
        instance.category = validated_data.get("category", instance.category)
        instance.document_name = validated_data.get(
            "document_name", instance.document_name
        )
        instance.file = validated_data.get("file", instance.file)
        instance.issue_date = validated_data.get("issue_date", instance.issue_date)
        instance.expiry_date = validated_data.get("expiry_date", instance.expiry_date)
        instance.save()
        return instance


class RecycleBinItemSerializer(serializers.ModelSerializer):
    model_name = serializers.SerializerMethodField()
    deleted_by_name = serializers.SerializerMethodField()

    class Meta:
        model = RecycleBinItem
        fields = [
            "id",
            "reference_code",
            "base_uuid",
            "model_name",
            "object_uuid",
            "deleted_at",
            "deleted_by",
            "deleted_by_name",
            "data",
        ]
        read_only_fields = fields

    def get_model_name(self, obj) -> str:
        content_type = obj.content_type

        if not isinstance(content_type, ContentType):
            try:
                content_type = ContentType.objects.get(pk=int(content_type))
            except (ContentType.DoesNotExist, ValueError):
                return str(content_type)

        return humanize_model_name(content_type)

    def get_deleted_by_name(self, obj) -> str:
        if obj.deleted_by:
            return str(obj.deleted_by)
        return "Unknown"


class RecycleBinSerializer(serializers.ModelSerializer):
    items = RecycleBinItemSerializer(many=True, read_only=True)
    item_count = serializers.SerializerMethodField()

    class Meta:
        model = RecycleBin
        fields = ["id", "institution", "created_at", "item_count", "items"]
        read_only_fields = fields

    def get_item_count(self, obj) -> int:
        return obj.items.count()


class InstitutionOwnershipTransferHistorySerializer(BaseUnApprovableSerializer):
    class Meta:
        model = InstitutionOwnershipTransferHistory
        fields = "__all__"


class InstitutionOwnerShipTransferSerializer(serializers.Serializer):
    new_owner = ActInstitutionOwnerSerializer(
        required=True,
        write_only=True,
    )
    transfer_date = serializers.DateField(
        required=False,
        default=timezone.now,
        write_only=True,
    )

    partner_record_internal_base_uuid = serializers.CharField(
        required=False,
        write_only=True,
    )

    def validate(self, attrs):
        request = self.context.get("request")

        institution = get_institution(request)
        partner_system = request.authenticated_system

        if not institution:
            raise validation_error({"institution": "Institution is required."})

        if not partner_system:
            raise validation_error({"partner_system": "Partner system is required."})

        existing_owner = self._resolve_existing_owner(
            attrs["new_owner"],
            institution,
            partner_system,
        )

        if (
            existing_owner
            and institution.institution_owner_id
            and existing_owner.id == institution.institution_owner_id
        ):
            raise validation_error(
                {"new_owner": "New owner cannot be the current institution owner."}
            )

        attrs["institution"] = institution
        attrs["partner_system"] = partner_system
        return attrs

    def create(self, validated_data):
        from .services import IdentityService
        from users.services import PermissionSyncService

        institution = validated_data["institution"]
        partner_system = validated_data["partner_system"]
        owner_data = validated_data["new_owner"]

        with db_transaction.atomic():
            previous_owner = institution.institution_owner

            new_owner = self._resolve_existing_owner(
                owner_data,
                institution,
                partner_system,
            )

            if not new_owner:
                new_owner = IdentityService.get_or_create_user(
                    email=owner_data.get("email"),
                    username=owner_data.get("username"),
                    phone_number=owner_data.get("phone_number"),
                    defaults={
                        "fullname": owner_data.get("fullname", ""),
                        "gender": owner_data.get("gender", "OTHER"),
                        "is_email_verified": True,
                        "is_active": True,
                    },
                )

            if previous_owner and previous_owner.id == new_owner.id:
                raise validation_error(
                    {"new_owner": "New owner cannot be the current institution owner."}
                )

            profile = IdentityService.ensure_profile(new_owner)
            profile_institution, _ = IdentityService.ensure_profile_institution(
                profile,
                institution,
                profile_photo_base64=owner_data.get("profile_photo_base64", None),
            )
            external_identity = IdentityService.ensure_external_identity(
                user=new_owner,
                partner_system=partner_system,
                institution=institution,
                external_base_uuid=owner_data["internal_base_uuid"],
            )

            institution.institution_owner = new_owner
            institution.save(update_fields=["institution_owner", "updated_at"])

            PermissionSyncService.grant_all_permissions_to_user(
                user=new_owner, profile_institution=profile_institution
            )

            return (
                InstitutionOwnershipTransferHistory.objects.create(
                    institution=institution,
                    previous_owner=previous_owner,
                    new_owner=new_owner,
                    transfer_date=validated_data["transfer_date"],
                    external_base_uuid=validated_data[
                        "partner_record_internal_base_uuid"
                    ],
                ),
                external_identity,
            )

    def to_representation(self, instance):
        repr = super().to_representation(instance)

        transfer_record, external_identity = instance

        repr["transfer_record"] = InstitutionOwnershipTransferHistorySerializer(
            transfer_record
        ).data

        repr["external_identity"] = {
            "internal_base_uuid": external_identity.external_base_uuid,
            "external_base_uuid": external_identity.base_uuid,
        }

        return repr

    def _get_identifier_values(self, data):
        return {
            "email": (data.get("email") or "").strip(),
            "username": (data.get("username") or "").strip(),
            "phone_number": (data.get("phone_number") or "").strip(),
        }

    def _resolve_existing_owner(self, owner_data, institution, partner_system):
        external_identity = (
            ExternalIdentity.objects.select_related("user")
            .filter(
                partner_system=partner_system,
                institution=institution,
                external_base_uuid=owner_data["internal_base_uuid"],
            )
            .first()
        )

        if external_identity:
            return external_identity.user

        identifiers = self._get_identifier_values(owner_data)

        if identifiers["email"]:
            return CustomUser.objects.filter(email__iexact=identifiers["email"]).first()

        if identifiers["username"]:
            return CustomUser.objects.filter(
                username__iexact=identifiers["username"]
            ).first()

        if identifiers["phone_number"]:
            return CustomUser.objects.filter(
                phone_number__iexact=identifiers["phone_number"]
            ).first()

        return None
