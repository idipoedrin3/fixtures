from copy import copy
from decimal import Decimal
from django.contrib.contenttypes.models import ContentType
from django.db import transaction
from rest_framework import serializers
from accounts.models import Account
from approval.serializers import ContentTypeIdSerializerMixin
from customers.models import Customer
from institution.models import Branch, InstitutionSupportedCurrency
from utilities.helpers import UUIDRelatedField, get_institution
from .models import Lender, Loan, LoanPaymentAllocation, LoanRepayment, LoanRepaymentSchedule
from .services import (
    LoanRepaymentScheduleService,
    LoanRepaymentService,
    LoanService,
)


class LenderSerializer(ContentTypeIdSerializerMixin):
    class Meta:
        model = Lender
        fields = "__all__"
        read_only_fields = ["institution"]

    def validate_name(self, value):
        institution = get_institution(self.context["request"])
        duplicates = Lender._base_manager.filter(
            institution=institution,
            name=value,
            deleted_at__isnull=True,
        )
        if self.instance is not None:
            duplicates = duplicates.exclude(pk=self.instance.pk)
        if duplicates.exists():
            raise serializers.ValidationError(
                "A lender with this name already exists in this institution."
            )
        return value

    def validate_reference_code(self, value):
        if not value:
            return value
        institution = get_institution(self.context["request"])
        duplicates = Lender._base_manager.filter(
            institution=institution,
            reference_code=value,
            deleted_at__isnull=True,
        )
        if self.instance is not None:
            duplicates = duplicates.exclude(pk=self.instance.pk)
        if duplicates.exists():
            raise serializers.ValidationError(
                "A lender with this reference code already exists in this institution."
            )
        return value

    def create(self, validated_data):
        institution = get_institution(self.context["request"])
        if institution is None:
            raise serializers.ValidationError("Institution context is required.")
        validated_data["institution"] = institution
        return super().create(validated_data)


class LoanSerializer(ContentTypeIdSerializerMixin):
    branch = UUIDRelatedField(
        queryset=Branch.objects.all(),
        required=False,
        allow_null=True,
    )
    currency = UUIDRelatedField(
        queryset=InstitutionSupportedCurrency.objects.all(),
    )
    cash_account = UUIDRelatedField(queryset=Account.objects.all())
    liability_receivable_account = UUIDRelatedField(
        queryset=Account.objects.all(),
    )
    opening_balance_account = UUIDRelatedField(
        queryset=Account.objects.all(),
        required=False,
        allow_null=True,
    )
    day_count_convention = serializers.ChoiceField(
        choices=Loan.DayCountConvention.choices,
    )
    initial_journal = serializers.SlugRelatedField(
        slug_field="base_uuid",
        read_only=True,
    )

    RELATED_FIELDS = (
        "branch",
        "currency",
        "cash_account",
        "liability_receivable_account",
        "opening_balance_account",
    )

    class Meta:
        model = Loan
        fields = "__all__"
        read_only_fields = [
            "institution",
            "status",
            "party_content_type",
            "initial_journal",
            "are_initial_journal_entries_processed",
        ]

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        if self.instance is not None:
            self.fields["reference_code"].read_only = True
        request = self.context.get("request")
        if request is not None:
            institution = get_institution(request)
            for name in self.RELATED_FIELDS:
                field = self.fields[name]
                field.queryset = field.queryset.filter(
                    institution=institution,
                    deleted_at__isnull=True,
                    is_active=True,
                )

    def validate_reference_code(self, value):
        if not value:
            return value
        institution = get_institution(self.context["request"])
        duplicates = Loan._base_manager.filter(
            institution=institution,
            reference_code=value,
            deleted_at__isnull=True,
        )
        if self.instance is not None:
            duplicates = duplicates.exclude(pk=self.instance.pk)
        if duplicates.exists():
            raise serializers.ValidationError(
                "A loan with this reference code already exists in this institution."
            )
        return value

    @transaction.atomic
    def validate(self, attrs):
        attrs = super().validate(attrs)
        institution = get_institution(self.context["request"])
        if institution is None:
            raise serializers.ValidationError("Institution context is required.")

        candidate = copy(self.instance) if self.instance is not None else Loan()
        candidate.institution = institution
        for name, value in attrs.items():
            setattr(candidate, name, value)

        if candidate.direction == Loan.Direction.OUTFLOW:
            party_model = Customer
        elif candidate.direction == Loan.Direction.INFLOW:
            party_model = Lender
        else:
            raise serializers.ValidationError(
                {"direction": "Select a valid direction."}
            )
        candidate.party_content_type = ContentType.objects.get_for_model(party_model)

        LoanService.validate_configuration(candidate)
        LoanService.validate_update(candidate)
        LoanRepaymentScheduleService._build_schedule(candidate)
        if candidate.opening_principal is not None and not (
            0 <= candidate.opening_principal <= candidate.principal
        ):
            raise serializers.ValidationError(
                {
                    "opening_principal": "Must be between zero and original principal.",
                }
            )

        attrs["institution"] = institution
        attrs["party_content_type"] = candidate.party_content_type
        return attrs

    def to_representation(self, instance):
        data = super().to_representation(instance)
        party_model = (
            Customer if instance.direction == Loan.Direction.OUTFLOW else Lender
        )
        party = party_model._base_manager.filter(
            institution_id=instance.institution_id,
            base_uuid=instance.party_object_uuid,
        ).first()
        data["party_name"] = (
            party.customer_name
            if isinstance(party, Customer)
            else party.name if party is not None else None
        )
        data["currency_code"] = instance.currency.currency.code
        data["branch_name"] = (
            instance.branch.branch_name if instance.branch_id else None
        )
        data["cash_account_name"] = instance.cash_account.account_name
        data["loan_account_name"] = instance.liability_receivable_account.account_name
        for name in self.RELATED_FIELDS:
            related = getattr(instance, name)
            data[name] = str(related.base_uuid) if related is not None else None
        return data


class LoanPaymentAllocationSerializer(serializers.ModelSerializer):
    repayment_schedule = UUIDRelatedField(queryset=LoanRepaymentSchedule.objects.all())
    principal_amount = serializers.DecimalField(
        max_digits=50, decimal_places=20, min_value=Decimal("0"), required=False
    )
    interest_amount = serializers.DecimalField(
        max_digits=50, decimal_places=20, min_value=Decimal("0"), required=False
    )
    fee_amount = serializers.DecimalField(
        max_digits=50, decimal_places=20, min_value=Decimal("0"), required=False
    )

    class Meta:
        model = LoanPaymentAllocation
        fields = [
            "repayment_schedule",
            "principal_amount",
            "interest_amount",
            "fee_amount",
        ]

    def to_representation(self, instance):
        data = super().to_representation(instance)
        schedule = instance.repayment_schedule
        data["repayment_schedule"] = str(schedule.base_uuid) if schedule else None
        data["installation_number"] = schedule.installation_number if schedule else None
        data["due_date"] = schedule.due_date.isoformat() if schedule else None
        data["amount"] = str(instance.amount)
        return data


class LoanRepaymentSerializer(ContentTypeIdSerializerMixin):
    loan = serializers.SlugRelatedField(slug_field="base_uuid", read_only=True)
    journal = serializers.SlugRelatedField(slug_field="base_uuid", read_only=True)
    allocations = LoanPaymentAllocationSerializer(many=True, required=False)

    class Meta:
        model = LoanRepayment
        fields = "__all__"
        read_only_fields = ["status", "loan", "journal"]

    @transaction.atomic
    def validate(self, attrs):
        attrs = super().validate(attrs)
        loan = self.context["loan"]
        instance = self.instance
        if instance is not None:
            LoanRepaymentService.validate_edit(instance)
        LoanRepaymentService.validate_header(
            loan,
            date=attrs.get("date", getattr(instance, "date", None)),
            treatment=attrs.get(
                "accounting_treatment", getattr(instance, "accounting_treatment", None)
            ),
            reference=attrs.get(
                "accounting_reference", getattr(instance, "accounting_reference", "")
            ),
        )
        if instance is None or "allocations" in attrs:
            total = LoanRepaymentService.validate_allocations(
                loan,
                attrs.get("allocations") or [],
                exclude_payment_id=getattr(instance, "pk", None),
            )
            if "amount" in attrs and abs(attrs["amount"] - total) > (
                LoanRepaymentService.TOLERANCE
            ):
                raise serializers.ValidationError(
                    {"amount": "Amount must equal the sum of the allocations."}
                )
            attrs["amount"] = total
        else:
            attrs.pop("amount", None)
        return attrs

    @transaction.atomic
    def create(self, validated_data):
        allocations = validated_data.pop("allocations")
        validated_data["loan"] = self.context["loan"]
        payment = super().create(validated_data)
        LoanRepaymentService.create_allocations(payment, allocations)
        return payment

    @transaction.atomic
    def update(self, instance, validated_data):
        allocations = validated_data.pop("allocations", None)
        if allocations is not None:
            validated_data["allocations_snapshot"] = (
                LoanRepaymentService.snapshot_allocations(instance)
            )
        instance = super().update(instance, validated_data)
        if allocations is not None:
            LoanRepaymentService.replace_allocations(instance, allocations)
        return instance

    def to_representation(self, instance):
        data = super().to_representation(instance)
        data.pop("allocations_snapshot", None)
        return data