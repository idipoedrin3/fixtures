from rest_framework import serializers
from django.db import transaction
from accounts.serializers import AccountSerializer
from accounts.models import Account
from customers.serializers import PaymentTermSerializer
from bank_management.utils import (
    CashAccountInputSerializer,
    CashAccountOutputSerializer,
)
from taxation.models import TaxApplicationBreakDown
from fixed_assets.models import AssetCategory
from taxation.serializers import (
    GeneralTaxInputSerializer,
    TaxApplicationBreakDownSerializer,
)
from taxation.service import SalesDocumentTaxService
from .models import (
    GoodsReceivedNoteLineItem,
    Vendor,
    VendorBill,
    VendorBillLineItem,
    VendorBillOtherExpenses,
    VendorPurchaseOrder,
    VendorPayment,
    VendorPaymentOption,
    GoodsReceivedNote,
    VendorPurchaseOrderLineItem,
    VendorOutstandingBalanceAdjustment,
    PrepaymentAllocation,
)
from django.db.models import Q, Sum
from datetime import date
from items.models import InventoryItem, InventoryItemUnitOfMeasure
from django.db import transaction as db_transaction
from decimal import Decimal
from approval.serializers import (
    ContentTypeIdSerializerMixin,
    BaseUnApprovableSerializer,
)
from utilities.helpers import (
    normalize_url,
    validation_error,
    UUIDRelatedField,
)
from system.serializers import (
    ExchangeRateInputSerializer,
    SystemCurrencySerializer,
)
from system.services import FxRateService
from utilities.helpers import get_institution
from system.models import SystemCurrency
from django.contrib.contenttypes.models import ContentType
from requisitions.models import Requisition
from requisitions.serializers import (
    BeneficiaryPaymentMethodSerializer,
    RequisitionBeneficiarySerializer,
)
from customers.models import PaymentTerm
from .utils import (
    create_other_expenses,
    recalculate_and_save_bill_totals,
    create_line_items,
)
from utilities.file_utils import Base64FileFieldMixin
from institution.models import Branch
from transactions.utils import get_general_journal_items_for_object


class VendorPaymentOptionSerializer(BaseUnApprovableSerializer):
    class Meta:
        model = VendorPaymentOption
        fields = "__all__"

        read_only_fields = [
            "id",
            "base_uuid",
            "vendor",
        ]


class VendorPaymentOptionInputSerializer(serializers.Serializer):
    title = serializers.CharField(max_length=255)
    description = serializers.CharField(
        max_length=255, required=False, allow_blank=True, allow_null=True
    )


class SimpleVendorSerializer(serializers.ModelSerializer):
    class Meta:
        model = Vendor
        fields = [
            "vendor_name",
            "gender",
            "tax_identification_number",
            "vendor_type",
            "base_uuid",
        ]


class VendorSerializer(ContentTypeIdSerializerMixin):

    IMMUTABLE_FIELDS_ON_UPDATE = [
        "currency",
        "opening_balance",
        "opening_balance_received_date",
        "opening_balance_account",
    ]

    payment_term = UUIDRelatedField(
        queryset=PaymentTerm.objects.all(),
        required=False,
        allow_null=True,
        write_only=True,
    )

    opening_balance_account = UUIDRelatedField(
        queryset=Account.objects.all(),
        required=False,
        allow_null=True,
    )

    default_account_payable = UUIDRelatedField(
        queryset=Account.objects.all(),
        required=False,
        allow_null=True,
    )

    foreign_exchange_rate = ExchangeRateInputSerializer(
        required=False,
        allow_null=True,
        write_only=True,
    )

    payment_options = BeneficiaryPaymentMethodSerializer(
        many=True,
        required=False,
        write_only=True,
    )

    class Meta:
        model = Vendor
        fields = "__all__"
        read_only_fields = [
            "id",
            "base_uuid",
            "created_at",
            "updated_at",
            "outstanding_payables",
            "deposit_balance",
            "are_initial_journal_entries_made",
            "institution",
        ]

    def _validate_vendor_account(
        self, *, account, field_name, institution, vendor_currency
    ):
        if account is None:
            return

        if account.institution_id != institution.id:
            raise validation_error(
                f"The selected {field_name.replace('_', ' ')} does not belong to the current institution."
            )

        account_currency = account.currency or institution.currency

        if account_currency != vendor_currency:
            raise validation_error(
                f"The selected {field_name.replace('_', ' ')} uses "
                f"{account_currency.code}, but the vendor's currency is {vendor_currency.code}. "
            )

    def validate(self, data):
        data = super().validate(data)

        if data.get("vendor_type") == "individual":
            vendor_name = data.get("vendor_name", "").strip()
            name_parts = vendor_name.split()
            if len(name_parts) < 2:
                raise validation_error(
                    "For individual vendors, please provide both first and last names."
                )

        if self.instance:
            for field in self.IMMUTABLE_FIELDS_ON_UPDATE:
                if field in data:
                    raise validation_error(
                        {
                            field: f"{field.replace('_', ' ').capitalize()} can only be set on creation and cannot be changed."
                        }
                    )

        request = self.context.get("request")
        institution = (
            self.instance.institution if self.instance else get_institution(request)
        )
        if not institution:
            raise validation_error("Institution not found in serializer context.")

        data["website"] = normalize_url(data.get("website"))

        institution_currency = institution.currency
        if not institution_currency:
            raise validation_error("Institution does not have a default currency set.")

        selected_currency = data.get(
            "currency",
            self.instance.currency if self.instance else None,
        )
        vendor_currency = selected_currency or institution_currency

        if not self.instance and selected_currency is None:
            data["currency"] = institution_currency

        default_account_payable = data.get(
            "default_account_payable",
            self.instance.default_account_payable if self.instance else None,
        )
        opening_balance_account = data.get(
            "opening_balance_account",
            self.instance.opening_balance_account if self.instance else None,
        )

        self._validate_vendor_account(
            account=default_account_payable,
            field_name="default_account_payable",
            institution=institution,
            vendor_currency=vendor_currency,
        )
        self._validate_vendor_account(
            account=opening_balance_account,
            field_name="opening_balance_account",
            institution=institution,
            vendor_currency=vendor_currency,
        )

        opening_balance = data.get(
            "opening_balance",
            self.instance.opening_balance if self.instance else Decimal("0"),
        )
        opening_balance = opening_balance or Decimal("0")

        opening_balance_received_date = data.get(
            "opening_balance_received_date",
            self.instance.opening_balance_received_date if self.instance else None,
        )

        if opening_balance != Decimal("0") and not opening_balance_received_date:
            raise validation_error(
                "You must specify the date for which this opening balance was created."
            )

        foreign_exchange_rate = data.get("foreign_exchange_rate")

        if vendor_currency != institution_currency and opening_balance != Decimal("0"):
            supported_currency = institution.institution_supported_currencies.filter(
                currency=vendor_currency,
                deleted_at__isnull=True,
            ).first()

            if not supported_currency:
                raise validation_error(
                    f"{vendor_currency.code} is not supported by this institution."
                )

            if foreign_exchange_rate is None and (
                supported_currency.rate is None
                or supported_currency.rate <= Decimal("0")
            ):
                raise validation_error(
                    f"A valid exchange rate is required for {vendor_currency.code}."
                )

        return data

    def to_representation(self, instance):
        repr = super().to_representation(instance)
        if instance.currency:
            repr["currency"] = SystemCurrencySerializer(instance.currency).data
        else:
            repr["currency"] = None

        if instance.payment_term is not None:
            repr["payment_term"] = PaymentTermSerializer(instance.payment_term).data
        else:
            repr["payment_term"] = None

        beneficiary = instance.requisition_beneficiary
        payment_methods = (
            beneficiary.payment_methods.undeleted() if beneficiary is not None else []
        )
        repr["payment_options"] = BeneficiaryPaymentMethodSerializer(
            payment_methods,
            many=True,
            context=self.context,
        ).data

        return repr

    @transaction.atomic
    def create(self, validated_data):
        payment_options_data = validated_data.pop("payment_options", [])

        foreign_exchange_rate = validated_data.pop("foreign_exchange_rate", None)

        request = self.context.get("request")
        institution = get_institution(request)

        if not institution:
            raise validation_error("Institution not found in serializer context.")

        validated_data["institution"] = institution

        vendor = Vendor.objects.create(**validated_data)

        beneficiary = vendor._ensure_requisition_beneficiary()

        # ********************************START OF FOREIGN EXCHANGE******************************
        target_currency = vendor.currency

        should_create_foreign_exchange_instance = (
            target_currency != institution.currency
            and vendor.opening_balance != Decimal("0")
        )

        if should_create_foreign_exchange_instance:

            institution_target_currency = (
                institution.institution_supported_currencies.filter(
                    currency=target_currency
                ).first()
            )

            if not institution_target_currency:
                raise validation_error("Currency is not supported by institution.")

            FxRateService.create_document_snapshot(
                source=vendor,
                institution=institution,
                currency=target_currency,
                rate_input=foreign_exchange_rate,
            )

        # *************************************************** END OF FOREIGN EXCHANGE *********************************

        RequisitionBeneficiarySerializer(
            context=self.context,
        ).save_payment_methods(
            beneficiary,
            payment_options_data,
        )

        return vendor

    @transaction.atomic
    def update(self, instance, validated_data):

        payment_options_data = validated_data.pop("payment_options", None)

        for attr, value in validated_data.items():
            setattr(instance, attr, value)
        instance.save()

        beneficiary = instance._ensure_requisition_beneficiary()
        beneficiary.name = instance.vendor_name
        beneficiary.contact_phone_number = instance.phone_number
        beneficiary.email = instance.email
        beneficiary.updated_by = instance.updated_by
        beneficiary.save(
            update_fields=[
                "name",
                "contact_phone_number",
                "email",
                "updated_by",
                "updated_at",
            ]
        )

        if payment_options_data is not None:
            RequisitionBeneficiarySerializer(
                context=self.context,
            ).save_payment_methods(
                beneficiary,
                payment_options_data,
                replace_existing=True,
            )

        return instance


class VendorPurchaseOrderLineItemInputSerializer(serializers.Serializer):
    purchase_order_line_item_uuid = serializers.UUIDField(required=False)

    def validate(self, data):
        required_fields = {
            name for name, field in self.fields.items() if field.required
        } | {"quantity", "unit_price"}
        errors = {
            field: ["This field is required for each submitted line item."]
            for field in required_fields
            if data.get(field) is None
        }
        if errors:
            raise validation_error(errors)
        if data["quantity"] <= 0:
            raise validation_error(
                {"quantity": ["Quantity must be greater than zero."]}
            )
        line_item = data.get("line_item")
        is_service = (
            isinstance(line_item, InventoryItem) and line_item.item_type == "SERVICES"
        )
        if data["unit_price"] < 0 and not is_service:
            raise validation_error({"unit_price": ["Unit price cannot be negative."]})
        return data


class InventoryVendorPurchaseOrderLineItemInputSerializer(
    VendorPurchaseOrderLineItemInputSerializer
):

    line_item = UUIDRelatedField(queryset=InventoryItem.objects.all(), required=True)

    unit_of_measure = UUIDRelatedField(
        queryset=InventoryItemUnitOfMeasure.objects.all(),
        required=True,
    )
    quantity = serializers.IntegerField(default=1)
    unit_price = serializers.DecimalField(
        max_digits=50, decimal_places=20, default=0.00
    )

    def validate(self, data):
        data = super().validate(data)
        if data["unit_of_measure"].inventory_item_id != data["line_item"].pk:
            raise validation_error(
                {"unit_of_measure": ["This unit does not belong to the selected item."]}
            )
        quantity = data.get("quantity")
        unit_price = data.get("unit_price")

        line_total = quantity * unit_price

        data["line_total"] = line_total

        return data


class FixedAssetVendorPurchaseOrderLineItemInputSerializer(
    VendorPurchaseOrderLineItemInputSerializer
):

    line_item = serializers.CharField(
        max_length=255,
        required=False,
        allow_blank=True,
    )

    asset_category = UUIDRelatedField(
        queryset=AssetCategory.objects.all(),
    )

    quantity = serializers.IntegerField(default=1)
    unit_price = serializers.DecimalField(
        max_digits=50, decimal_places=20, default=0.00
    )
    applicable_taxes = GeneralTaxInputSerializer(many=True, required=False)

    def validate(self, data):
        data = super().validate(data)
        quantity = data.get("quantity")
        unit_price = data.get("unit_price")
        line_item = data.get("line_item", "").strip()

        line_total = quantity * unit_price

        data["line_total"] = line_total

        if line_item == "":
            data["line_item"] = f"{data['asset_category'].category_name}"

        return data


class OtherVendorPurchaseOrderLineItemInputSerializer(
    VendorPurchaseOrderLineItemInputSerializer
):

    line_item = serializers.CharField(max_length=255, required=True)
    unit_of_measure = serializers.CharField(max_length=255, required=True)
    quantity = serializers.IntegerField(default=1)
    unit_price = serializers.DecimalField(
        max_digits=50, decimal_places=20, default=0.00
    )
    applicable_taxes = GeneralTaxInputSerializer(many=True, required=False)

    def validate(self, data):
        data = super().validate(data)
        quantity = data.get("quantity")
        unit_price = data.get("unit_price")

        line_total = quantity * unit_price

        data["line_total"] = line_total

        return data


class SimpleVendorPurchaseOrderSerializer(serializers.ModelSerializer):
    total_amount = serializers.SerializerMethodField()
    currency = serializers.SerializerMethodField()

    class Meta:
        model = VendorPurchaseOrder
        fields = [
            "id",
            "base_uuid",
            "reference_code",
            "status",
            "issue_date",
            "total_amount",
            "currency",
            "goods_received_note_status",
            "bill_status",
            "expected_delivery_date",
        ]

    def get_total_amount(self, obj):
        return obj.get_total_amount()

    def get_currency(self, obj):
        currency, _ = obj.determine_rate_currency_used()
        return SystemCurrencySerializer(currency).data if currency else None

    def to_representation(self, instance):
        repr = super().to_representation(instance)

        repr["vendor"] = {
            "id": instance.vendor.id,
            "base_uuid": str(instance.vendor.base_uuid),
            "vendor_name": instance.vendor.vendor_name,
        }

        if instance.branch:
            repr["branch"] = {
                "id": instance.branch.id,
                "base_uuid": str(instance.branch.base_uuid),
                "branch_name": instance.branch.branch_name,
                "reference_code": instance.branch.reference_code,
            }

        return repr


class VendorPurchaseOrderLineItemSerializer(serializers.ModelSerializer):
    qty_billed = serializers.SerializerMethodField()

    class Meta:
        model = VendorPurchaseOrderLineItem
        fields = "__all__"

        read_only_fields = [
            "qty_ordered",
            "qty_received",
            "qty_to_receive",
            "qty_billed",
        ]

    def get_qty_billed(self, instance):
        purchase_order = instance.purchase_order

        if purchase_order is None:
            return 0

        total = VendorBillLineItem.objects.filter(
            bill__purchase_order=purchase_order,
            inventory_item=instance.inventory_item,
            deleted_at__isnull=True,
        ).aggregate(total_quantity=Sum("quantity"))

        return total["total_quantity"] or 0

    def to_representation(self, instance):
        repr = super().to_representation(instance)

        repr["line_item_tax_breakdowns"] = TaxApplicationBreakDownSerializer(
            instance.get_tax_breakdowns(), many=True
        ).data

        if instance.item_type == "inventory":

            if instance.inventory_item:
                repr["inventory_item"] = {
                    "id": instance.inventory_item.id,
                    "base_uuid": str(instance.inventory_item.base_uuid),
                    "item_name": instance.inventory_item.item_name,
                    "item_type": instance.inventory_item.item_type,
                }

            else:
                repr["inventory_item"] = None

            if instance.unit_of_measure:
                repr["unit_of_measure"] = {
                    "id": instance.unit_of_measure.id,
                    "base_uuid": str(instance.unit_of_measure.base_uuid),
                    "unit_name": instance.unit_of_measure.unit_of_measure.unit_name,
                }

            else:
                repr["unit_of_measure"] = None

        if instance.item_type == "fixed_asset":

            if instance.asset_category:
                repr["asset_category"] = {
                    "id": instance.asset_category.id,
                    "base_uuid": str(instance.asset_category.base_uuid),
                    "category_name": instance.asset_category.category_name,
                }

            else:
                repr["asset_category"] = None

        return repr


class VendorPurchaseOrderSerializer(Base64FileFieldMixin, ContentTypeIdSerializerMixin):

    LINE_ITEM_FIELDS = {
        "inventory_line_items": "inventory",
        "other_line_items": "other",
        "fixed_asset_line_items": "fixed_asset",
    }

    inventory_line_items = InventoryVendorPurchaseOrderLineItemInputSerializer(
        many=True,
        required=False,
        write_only=True,
    )
    other_line_items = OtherVendorPurchaseOrderLineItemInputSerializer(
        many=True, required=False, write_only=True
    )
    fixed_asset_line_items = FixedAssetVendorPurchaseOrderLineItemInputSerializer(
        many=True, required=False, write_only=True
    )

    request_requisition = UUIDRelatedField(
        queryset=Requisition.objects.all(),
        required=False,
        allow_null=True,
    )

    exchange_rate = ExchangeRateInputSerializer(
        required=False,
        allow_null=True,
        write_only=True,
    )

    total_amount = serializers.SerializerMethodField()
    net_total = serializers.SerializerMethodField()
    tax_total = serializers.SerializerMethodField()
    gross_total = serializers.SerializerMethodField()

    base64_file_fields = ["supporting_document_file"]

    branch = UUIDRelatedField(
        queryset=Branch.objects.all(),
        required=False,
        allow_null=True,
    )

    class Meta:
        model = VendorPurchaseOrder

        fields = "__all__"

        read_only_fields = [
            "status",
            "institution",
            "is_active",
            "approval_status",
            "original_data",
            "total_amount",
            "fixed_asset_items",
            "inventory_items",
            "other_items",
            "goods_received_note_status",
            "bill_status",
        ]

    def get_total_amount(self, obj):
        return obj.get_total_amount()

    def get_net_total(self, obj):
        return obj.get_net_total()

    def get_tax_total(self, obj):
        return obj.get_tax_total()

    def get_gross_total(self, obj):
        return obj.get_total_amount()

    def to_representation(self, instance):
        repr = super().to_representation(instance)

        for field, item_type in self.LINE_ITEM_FIELDS.items():
            repr[field.replace("_line_items", "_items")] = (
                VendorPurchaseOrderLineItemSerializer(
                    instance.line_items.undeleted().filter(item_type=item_type),
                    many=True,
                    context=self.context,
                ).data
            )

        repr["vendor"] = VendorSerializer(instance.vendor).data

        document_currency, _ = instance.determine_rate_currency_used()

        repr["currency"] = SystemCurrencySerializer(document_currency).data

        exchange_rate = (
            FxRateService.get_document_rate_representation(
                source=(
                    instance
                    if instance.currency_id
                    else instance.vendor if instance.vendor.currency_id else None
                ),
                institution=instance.get_institution(),
                currency=document_currency,
            )
            if document_currency
            else None
        )
        repr["exchange_rate"] = exchange_rate
        repr["exchange_rate_status"] = (
            exchange_rate["source"] if exchange_rate else "missing"
        )

        if instance.request_requisition:
            repr["request_requisition"] = {
                "id": instance.request_requisition.id,
                "base_uuid": str(instance.request_requisition.base_uuid),
                "requisition_code": instance.request_requisition.reference_code,
            }
        else:
            repr["request_requisition"] = None

        if instance.branch:
            repr["branch"] = {
                "id": instance.branch.id,
                "base_uuid": str(instance.branch.base_uuid),
                "branch_name": instance.branch.branch_name,
                "reference_code": instance.branch.reference_code,
            }
        else:
            repr["branch"] = None

        return repr

    def validate(self, data):
        vendor = data.get("vendor", getattr(self.instance, "vendor", None))
        currency = data.get("currency", None)
        institution = (
            self.instance.get_institution()
            if self.instance
            else get_institution(self.context.get("request"))
        )

        if vendor and (
            vendor.institution_id != institution.pk or vendor.deleted_at is not None
        ):
            raise validation_error(
                {"vendor": ["Select an undeleted vendor from the current institution."]}
            )

        for field in ("branch", "request_requisition"):
            record = data.get(field)
            if record is not None and (
                record.institution_id != institution.pk or record.deleted_at is not None
            ):
                raise validation_error(
                    {
                        field: [
                            "Select an undeleted record from the current institution."
                        ]
                    }
                )

        for item in data.get("inventory_line_items", []):
            inventory_item = item["line_item"]
            unit = item["unit_of_measure"]
            if (
                inventory_item.get_institution().pk != institution.pk
                or inventory_item.deleted_at is not None
                or unit.deleted_at is not None
            ):
                raise validation_error(
                    {
                        "inventory_line_items": [
                            "Select valid inventory from the current institution."
                        ]
                    }
                )

        for item in data.get("fixed_asset_line_items", []):
            category = item["asset_category"]
            if (
                category.institution_id != institution.pk
                or category.deleted_at is not None
            ):
                raise validation_error(
                    {
                        "fixed_asset_line_items": [
                            "Select a valid asset category from the current institution."
                        ]
                    }
                )

        if self.instance:
            if (
                VendorBill.objects.undeleted()
                .filter(purchase_order=self.instance)
                .exists()
            ):
                raise validation_error(
                    "Cannot edit a purchase order that already has a vendor bill attachment"
                )

            if (
                GoodsReceivedNote.objects.undeleted()
                .filter(purchase_order=self.instance)
                .exists()
            ):
                raise validation_error(
                    "Cannot edit a purchase order that already has a goods received note attachment"
                )

        if "issue_date" in data and data["issue_date"] > date.today():
            raise validation_error("Issue date cannot be in the future.")

        existing_items = (
            {item.base_uuid: item for item in self.instance.line_items.undeleted()}
            if self.instance
            else {}
        )
        submitted_uuids = set()
        resulting_count = 0
        for field, item_type in self.LINE_ITEM_FIELDS.items():
            if field not in data:
                resulting_count += sum(
                    item.item_type == item_type for item in existing_items.values()
                )
                continue
            resulting_count += len(data[field])
            for item in data[field]:
                line_uuid = item.get("purchase_order_line_item_uuid")
                if line_uuid is None:
                    continue
                existing = existing_items.get(line_uuid)
                if existing is None or existing.item_type != item_type:
                    raise validation_error(
                        {
                            field: [
                                "The supplied line must belong to this purchase "
                                "order and match the submitted item type."
                            ]
                        }
                    )
                if line_uuid in submitted_uuids:
                    raise validation_error(
                        {
                            field: [
                                "The same purchase order line cannot be submitted twice."
                            ]
                        }
                    )
                submitted_uuids.add(line_uuid)

        if resulting_count == 0:
            raise validation_error("At least one line item is required.")

        if self.instance and "currency" in data:
            current_currency, _ = self.instance.determine_rate_currency_used()
            if currency != current_currency:
                raise validation_error(
                    {
                        "currency": [
                            "Create a new purchase order to change its currency."
                        ]
                    }
                )
        elif vendor and currency:
            raise validation_error(
                "Currency and vendor cannot be sent at the same time."
            )

        if self.instance and vendor and vendor.pk != self.instance.vendor_id:
            institution_currency = self.instance.get_institution().currency
            requested_currency = (
                vendor.currency if vendor.currency_id else institution_currency
            )
            current_currency, _ = self.instance.determine_rate_currency_used()

            if requested_currency != current_currency:
                raise validation_error(
                    {
                        "vendor": [
                            "The selected vendor uses a different currency. "
                            "Create a new purchase order instead."
                        ]
                    }
                )

        return data

    def create(self, validated_data):
        inventory_line_items_data = validated_data.pop("inventory_line_items", [])
        other_line_items_data = validated_data.pop("other_line_items", [])
        fixed_asset_line_items_data = validated_data.pop("fixed_asset_line_items", [])

        requested_currency = validated_data.pop("currency", None)
        rate_input = validated_data.pop("exchange_rate", None)

        institution = get_institution(self.context.get("request"))
        validated_data["institution"] = institution

        vendor = validated_data["vendor"]
        target_currency = (
            vendor.currency
            if vendor.currency_id
            else requested_currency or institution.currency
        )
        validated_data["currency"] = target_currency

        with db_transaction.atomic():

            purchase_order = VendorPurchaseOrder.objects.create(**validated_data)

            institution = purchase_order.get_institution()

            FxRateService.create_document_snapshot(
                source=purchase_order,
                institution=institution,
                currency=target_currency,
                rate_input=rate_input,
            )

            all_items = (
                [{"item_type": "inventory", **i} for i in inventory_line_items_data]
                + [{"item_type": "other", **i} for i in other_line_items_data]
                + [
                    {"item_type": "fixed_asset", **i}
                    for i in fixed_asset_line_items_data
                ]
            )

            for item_data in all_items:

                applicable_taxes = item_data.pop("applicable_taxes", None)

                unit_price = item_data["unit_price"]
                quantity = item_data["quantity"]

                line_total = unit_price * quantity

                data = {
                    "purchase_order": purchase_order,
                    "item_type": item_data["item_type"],
                    "quantity": quantity,
                    "unit_price": unit_price,
                    "line_total": line_total,
                    "qty_ordered": quantity,
                    "qty_to_receive": quantity,
                    "qty_received": 0,
                }

                if item_data["item_type"] == "inventory":
                    data["inventory_item"] = item_data["line_item"]
                    data["unit_of_measure"] = item_data["unit_of_measure"]

                elif item_data["item_type"] == "other":
                    data["line_item_name"] = item_data["line_item"]
                    data["other_unit_of_measure"] = item_data["unit_of_measure"]

                elif item_data["item_type"] == "fixed_asset":
                    data["line_item_name"] = item_data["line_item"]
                    data["asset_category"] = item_data["asset_category"]

                purchase_order_line = VendorPurchaseOrderLineItem.objects.create(**data)
                SalesDocumentTaxService.apply_line_taxes(
                    line=purchase_order_line,
                    applicable_taxes=applicable_taxes or None,
                    default_tax_field="purchase_tax",
                )

            purchase_order.send_vendor_purchase_order_email()

        return purchase_order

    def update(self, instance, validated_data):

        rate_was_provided = "exchange_rate" in validated_data
        rate_input = validated_data.pop("exchange_rate", None)

        submitted_groups = {
            item_type: validated_data.pop(field)
            for field, item_type in self.LINE_ITEM_FIELDS.items()
            if field in validated_data
        }

        with db_transaction.atomic():

            for attr, value in validated_data.items():
                setattr(instance, attr, value)

            instance.save()

            if rate_was_provided:
                document_currency, _ = instance.determine_rate_currency_used()
                FxRateService.replace_document_snapshot(
                    source=instance,
                    institution=instance.get_institution(),
                    currency=document_currency,
                    rate_input=rate_input,
                )

            for item_type, items in submitted_groups.items():
                existing_items = {
                    line.base_uuid: line
                    for line in instance.line_items.undeleted()
                    .select_for_update()
                    .filter(item_type=item_type)
                }
                retained_ids = set()

                for item_data in items:
                    line_uuid = item_data.get("purchase_order_line_item_uuid")
                    line = existing_items.get(line_uuid)
                    if line_uuid is not None and line is None:
                        raise validation_error(
                            "A submitted line is no longer available. Reload and try again."
                        )

                    quantity = item_data["quantity"]
                    if line is not None and quantity < line.qty_received:
                        raise validation_error(
                            "Ordered quantity cannot be less than the quantity received."
                        )

                    line_data = {
                        "quantity": quantity,
                        "unit_price": item_data["unit_price"],
                        "line_total": quantity * item_data["unit_price"],
                        "qty_ordered": quantity,
                        "qty_to_receive": quantity - (line.qty_received if line else 0),
                    }
                    if item_type == "inventory":
                        line_data.update(
                            inventory_item=item_data["line_item"],
                            unit_of_measure=item_data["unit_of_measure"],
                        )
                    elif item_type == "other":
                        line_data.update(
                            line_item_name=item_data["line_item"],
                            other_unit_of_measure=item_data["unit_of_measure"],
                        )
                    else:
                        line_data.update(
                            line_item_name=item_data["line_item"],
                            asset_category=item_data["asset_category"],
                        )

                    applicable_taxes = item_data.get("applicable_taxes")
                    if (
                        line is not None
                        and item_type != "inventory"
                        and "applicable_taxes" not in item_data
                    ):
                        applicable_taxes = [
                            {
                                "tax": breakdown.tax,
                                "is_inclusive": breakdown.is_inclusive,
                            }
                            for breakdown in line.get_tax_breakdowns()
                        ]

                    changed = line is None
                    if line is None:
                        line = VendorPurchaseOrderLineItem.objects.create(
                            purchase_order=instance,
                            item_type=item_type,
                            **line_data,
                        )
                    else:
                        for attr, value in line_data.items():
                            if getattr(line, attr) != value:
                                setattr(line, attr, value)
                                changed = True
                        if changed:
                            line.save()

                    retained_ids.add(line.pk)
                    if changed or "applicable_taxes" in item_data:
                        SalesDocumentTaxService.apply_line_taxes(
                            line=line,
                            applicable_taxes=applicable_taxes,
                            default_tax_field="purchase_tax",
                        )

                removed_ids = {
                    line.pk for line in existing_items.values()
                } - retained_ids
                if removed_ids:
                    instance.line_items.filter(pk__in=removed_ids).delete()

        return instance


class VendorBillOtherExpensesSerializer(serializers.ModelSerializer):

    class Meta:
        model = VendorBillOtherExpenses
        fields = "__all__"

    def to_representation(self, instance):
        repr = super().to_representation(instance)

        repr["tax_breakdowns"] = TaxApplicationBreakDownSerializer(
            instance.get_tax_breakdowns(), many=True
        ).data

        repr["account_to_record_expense"] = AccountSerializer(
            instance.account_to_record_expense
        ).data

        return repr


class VendorBillOtherExpensesInputSerializer(serializers.Serializer):
    expense_name = serializers.CharField(max_length=255)
    amount = serializers.DecimalField(max_digits=50, decimal_places=20, default=0.00)
    account_to_record_expense = UUIDRelatedField(
        queryset=Account.objects.all(), required=False, allow_null=True
    )
    applicable_taxes = GeneralTaxInputSerializer(many=True, required=False)


class VendorBillLineItemSerializer(serializers.ModelSerializer):
    asset_category = UUIDRelatedField(
        queryset=AssetCategory.objects.all(),
        required=False,
        allow_null=True,
    )

    inventory_item = UUIDRelatedField(
        queryset=InventoryItem.objects.all(),
        required=False,
        allow_null=True,
    )

    unit_of_measure = UUIDRelatedField(
        queryset=InventoryItemUnitOfMeasure.objects.all(),
        required=False,
        allow_null=True,
    )

    class Meta:
        model = VendorBillLineItem
        fields = "__all__"

    def to_representation(self, instance):
        repr = super().to_representation(instance)

        repr["line_item_tax_breakdowns"] = TaxApplicationBreakDownSerializer(
            instance.get_tax_breakdowns(), many=True
        ).data

        if instance.item_type == "inventory":

            if instance.inventory_item:
                repr["inventory_item"] = {
                    "id": instance.inventory_item.id,
                    "base_uuid": str(instance.inventory_item.base_uuid),
                    "item_name": instance.inventory_item.item_name,
                    "item_type": instance.inventory_item.item_type,
                }

            else:
                repr["inventory_item"] = None

            if instance.unit_of_measure:
                repr["unit_of_measure"] = {
                    "id": instance.unit_of_measure.id,
                    "base_uuid": str(instance.unit_of_measure.base_uuid),
                    "unit_name": instance.unit_of_measure.unit_of_measure.unit_name,
                }

            else:
                repr["unit_of_measure"] = None

        if instance.item_type == "fixed_asset":

            if instance.asset_category:
                repr["asset_category"] = {
                    "id": instance.asset_category.id,
                    "base_uuid": str(instance.asset_category.base_uuid),
                    "category_name": instance.asset_category.category_name,
                }

            else:
                repr["asset_category"] = None

        return repr


class VendorBillLineItemsAndExpensesSerializer(serializers.Serializer):
    line_items = VendorBillLineItemSerializer(many=True, read_only=True)
    expenses = VendorBillOtherExpensesSerializer(many=True, read_only=True)


class SimpleVendorBillSerializer(serializers.ModelSerializer):
    class Meta:
        model = VendorBill
        fields = [
            "id",
            "base_uuid",
        ]


class InventoryVendorBillLineItemInputSerializer(serializers.Serializer):

    line_item = UUIDRelatedField(queryset=InventoryItem.objects.all(), required=True)

    unit_of_measure = UUIDRelatedField(
        queryset=InventoryItemUnitOfMeasure.objects.all(),
        required=True,
    )
    quantity = serializers.IntegerField(default=1)
    unit_price = serializers.DecimalField(
        max_digits=50, decimal_places=20, default=0.00
    )

    def validate(self, data):
        quantity = data.get("quantity")
        unit_price = data.get("unit_price")

        line_total = quantity * unit_price

        data["line_total"] = line_total

        return data


class FixedAssetVendorBillLineItemInputSerializer(serializers.Serializer):

    line_item = serializers.CharField(max_length=255, required=False, allow_blank=True)

    asset_category = UUIDRelatedField(
        queryset=AssetCategory.objects.all(), required=True
    )

    quantity = serializers.IntegerField(default=1)
    unit_price = serializers.DecimalField(
        max_digits=50, decimal_places=20, default=0.00
    )
    applicable_taxes = GeneralTaxInputSerializer(many=True, required=False)

    def validate(self, data):
        quantity = data.get("quantity")
        unit_price = data.get("unit_price")

        line_total = quantity * unit_price

        data["line_total"] = line_total

        return data


class OtherVendorBillLineItemInputSerializer(serializers.Serializer):

    line_item = serializers.CharField(
        max_length=255,
        required=True,
    )
    unit_of_measure = serializers.CharField(
        max_length=255,
        required=False,
        allow_blank=True,
    )
    quantity = serializers.IntegerField(default=1)
    unit_price = serializers.DecimalField(
        max_digits=50, decimal_places=20, default=0.00
    )
    applicable_taxes = GeneralTaxInputSerializer(many=True, required=False)

    def validate(self, data):
        quantity = data.get("quantity")
        unit_price = data.get("unit_price")

        line_total = quantity * unit_price

        data["line_total"] = line_total

        return data


class BulkVendorBillRowSerializer(serializers.Serializer):
    reference_code = serializers.CharField(max_length=100)
    vendor = serializers.CharField(max_length=255)
    branch = serializers.CharField(
        max_length=255,
        required=False,
        allow_blank=True,
        allow_null=True,
    )
    payment_terms = serializers.CharField(
        max_length=255,
        required=False,
        allow_blank=True,
        allow_null=True,
    )
    type = serializers.CharField(max_length=50)
    item = serializers.CharField(max_length=255)
    uom = serializers.CharField(
        max_length=255,
        required=False,
        allow_blank=True,
        allow_null=True,
    )
    qty = serializers.IntegerField(min_value=1)
    unit_price = serializers.DecimalField(
        max_digits=50,
        decimal_places=20,
        min_value=Decimal("0.00"),
    )
    net_amount = serializers.DecimalField(
        max_digits=50,
        decimal_places=20,
        required=False,
        allow_null=True,
    )
    tax_amount = serializers.DecimalField(
        max_digits=50,
        decimal_places=20,
        required=False,
        allow_null=True,
    )
    gross_amount = serializers.DecimalField(
        max_digits=50,
        decimal_places=20,
        required=False,
        allow_null=True,
    )
    payment_status = serializers.CharField(max_length=50)
    received_date = serializers.DateField(required=False, allow_null=True)
    due_date = serializers.DateField(required=False, allow_null=True)


class VendorBillSerializer(ContentTypeIdSerializerMixin):
    inventory_line_items = InventoryVendorBillLineItemInputSerializer(
        many=True, write_only=True, required=False
    )

    other_line_items = OtherVendorBillLineItemInputSerializer(
        many=True, write_only=True, required=False
    )

    fixed_asset_line_items = FixedAssetVendorBillLineItemInputSerializer(
        many=True, write_only=True, required=False
    )

    other_expenses = VendorBillOtherExpensesInputSerializer(
        many=True, write_only=True, required=False
    )

    payment_terms = UUIDRelatedField(
        queryset=PaymentTerm.objects.all(),
        required=False,
    )

    purchase_order = UUIDRelatedField(
        queryset=VendorPurchaseOrder.objects.all(), required=False
    )

    vendor = UUIDRelatedField(queryset=Vendor.objects.all(), required=False)

    branch = UUIDRelatedField(queryset=Branch.objects.all(), required=False)

    exchange_rate = ExchangeRateInputSerializer(
        required=False,
        write_only=True,
        allow_null=True,
    )

    class Meta:
        model = VendorBill
        fields = "__all__"
        read_only_fields = [
            "total_amount",
            "total_net_amount",
            "total_tax_amount",
            "status",
            "balance_due",
            "are_initial_journal_entries_made",
            "due_date",
            "payment_status",
            "institution",
            "general_journal_items",
        ]

    def validate(self, attrs):
        purchase_order = attrs.get("purchase_order")
        vendor = attrs.get("vendor")
        branch = attrs.get("branch")

        requested_currency = attrs.get("currency")

        if purchase_order and vendor:
            raise validation_error(
                "You cannot provide both a purchase order and a vendor. Choose only one."
            )

        if not purchase_order and not vendor:
            raise validation_error(
                "You must provide either a purchase order or a vendor."
            )

        if branch:
            attrs["branch"] = branch

        if not branch and purchase_order and purchase_order.branch:
            attrs["branch"] = purchase_order.branch

        source_document = purchase_order or vendor
        if source_document is not None and requested_currency is not None:
            source_currency, _ = source_document.determine_rate_currency_used()
            if requested_currency != source_currency:
                raise validation_error(
                    {
                        "currency": [
                            "The bill currency must match the selected  "
                            "purchase order or vendor currency. Please select a different currency."
                        ]
                    }
                )

        attrs["institution"] = get_institution(self.context.get("request"))

        return attrs

    def validate_reference_code(self, value):
        value = str(value or "").strip()
        if not value:
            return None

        institution = get_institution(self.context.get("request"))
        if institution is None:
            return value

        queryset = VendorBill.objects.filter(
            reference_code__iexact=value,
        ).filter(
            Q(vendor__institution=institution)
            | Q(purchase_order__vendor__institution=institution)
        )
        if self.instance is not None:
            queryset = queryset.exclude(pk=self.instance.pk)

        if queryset.exists():
            raise validation_error(
                {
                    "reference_code": (
                        "A vendor bill with this reference code already exists."
                    )
                }
            )

        return value

    def to_representation(self, instance):
        repr = super().to_representation(instance)

        repr["inventory_line_items"] = VendorBillLineItemSerializer(
            instance.line_items.filter(item_type="inventory"), many=True
        ).data
        repr["fixed_asset_line_items"] = VendorBillLineItemSerializer(
            instance.line_items.filter(item_type="fixed_asset"), many=True
        ).data
        repr["other_line_items"] = VendorBillLineItemSerializer(
            instance.line_items.filter(item_type="other"), many=True
        ).data

        repr["order_expenses"] = VendorBillOtherExpensesSerializer(
            instance.order_expenses, many=True
        ).data

        if instance.purchase_order:
            repr["purchase_order"] = VendorPurchaseOrderSerializer(
                instance.purchase_order
            ).data

        repr["payment_term_name"] = (
            instance.payment_terms.term_name if instance.payment_terms else None
        )

        repr["line_item_tax_breakdowns"] = TaxApplicationBreakDownSerializer(
            instance.get_all_tax_breakdowns(), many=True
        ).data

        currency, _ = instance.determine_rate_currency_used()
        repr["currency"] = SystemCurrencySerializer(currency).data if currency else None
        exchange_rate = FxRateService.get_document_rate_representation(
            source=(
                instance
                if instance.currency_id
                else (
                    instance.purchase_order
                    if instance.purchase_order and instance.purchase_order.currency_id
                    else (
                        instance.vendor
                        if instance.vendor and instance.vendor.currency_id
                        else None
                    )
                )
            ),
            institution=instance.get_institution(),
            currency=currency,
        )
        repr["exchange_rate"] = exchange_rate
        repr["exchange_rate_status"] = (
            exchange_rate["source"] if exchange_rate else "missing"
        )

        bill_vendor = instance.get_bill_vendor()
        if bill_vendor:
            repr["vendor"] = {
                "id": bill_vendor.id,
                "base_uuid": bill_vendor.base_uuid,
                "vendor_name": bill_vendor.vendor_name,
                "email": bill_vendor.email,
                "phone_number": bill_vendor.phone_number,
            }
        else:
            repr["vendor"] = None

        if instance.branch:
            repr["branch"] = {
                "id": instance.branch.id,
                "base_uuid": instance.branch.base_uuid,
                "branch_name": instance.branch.branch_name,
                "reference_code": instance.branch.reference_code,
            }

        return repr

    @transaction.atomic()
    def create(self, validated_data):

        inventory_line_items_data = validated_data.pop("inventory_line_items", [])
        other_line_items_data = validated_data.pop("other_line_items", [])
        fixed_asset_line_items_data = validated_data.pop("fixed_asset_line_items", [])
        other_expenses_data = validated_data.pop("other_expenses", [])
        requested_currency = validated_data.pop("currency", None)
        rate_input = validated_data.pop("exchange_rate", None)

        source_document = validated_data.get("purchase_order") or validated_data.get(
            "vendor"
        )

        if source_document is not None:
            target_currency, _ = source_document.determine_rate_currency_used()

        else:
            target_currency = (
                requested_currency
                or get_institution(self.context.get("request")).currency
            )

        validated_data["currency"] = target_currency

        vendor_bill = VendorBill.objects.create(**validated_data)

        canonical_rate = FxRateService.create_document_snapshot(
            source=vendor_bill,
            institution=vendor_bill.get_institution(),
            currency=target_currency,
            rate_input=rate_input,
        )

        line_net, line_tax, line_gross = create_line_items(
            vendor_bill=vendor_bill,
            inventory_items=inventory_line_items_data,
            other_items=other_line_items_data,
            fixed_asset_items=fixed_asset_line_items_data,
            canonical_rate=canonical_rate,
        )

        expense_net, expense_tax, expense_gross = create_other_expenses(
            vendor_bill=vendor_bill,
            expenses_data=other_expenses_data,
            canonical_rate=canonical_rate,
        )

        recalculate_and_save_bill_totals(
            vendor_bill=vendor_bill,
            line_net=line_net,
            line_tax=line_tax,
            line_gross=line_gross,
            exp_net=expense_net,
            exp_tax=expense_tax,
            exp_gross=expense_gross,
        )

        return vendor_bill

    @transaction.atomic()
    def update(self, instance, validated_data):
        inventory_line_items_data = validated_data.pop("inventory_line_items", [])
        other_line_items_data = validated_data.pop("other_line_items", [])
        fixed_asset_line_items_data = validated_data.pop("fixed_asset_line_items", [])
        other_expenses_data = validated_data.pop("other_expenses", [])
        rate_input = validated_data.pop("exchange_rate", None)
        target_currency, _ = instance.determine_rate_currency_used()
        validated_data["currency"] = target_currency

        for attr, value in validated_data.items():
            setattr(instance, attr, value)
        instance.save()

        canonical_rate = FxRateService.create_document_snapshot(
            source=instance,
            institution=instance.get_institution(),
            currency=target_currency,
            rate_input=rate_input,
        )

        content_type_line = ContentType.objects.get_for_model(VendorBillLineItem)
        content_type_exp = ContentType.objects.get_for_model(VendorBillOtherExpenses)

        line_item_ids = instance.line_items.values_list("id", flat=True)
        expense_ids = instance.order_expenses.values_list("id", flat=True)

        TaxApplicationBreakDown.objects.filter(
            content_type=content_type_line, object_id__in=line_item_ids
        ).delete()
        TaxApplicationBreakDown.objects.filter(
            content_type=content_type_exp, object_id__in=expense_ids
        ).delete()

        instance.line_items.all().delete()
        instance.order_expenses.all().delete()

        line_net, line_tax, line_gross = create_line_items(
            vendor_bill=instance,
            inventory_items=inventory_line_items_data,
            fixed_asset_items=fixed_asset_line_items_data,
            other_items=other_line_items_data,
            canonical_rate=canonical_rate,
        )
        exp_net, exp_tax, exp_gross = create_other_expenses(
            vendor_bill=instance,
            expenses_data=other_expenses_data,
            canonical_rate=canonical_rate,
        )

        recalculate_and_save_bill_totals(
            instance, line_net, line_tax, line_gross, exp_net, exp_tax, exp_gross
        )

        return instance


class VendorPaymentSerializer(ContentTypeIdSerializerMixin):
    cash_account_used = CashAccountInputSerializer(required=False, write_only=True)

    bill = UUIDRelatedField(queryset=VendorBill.objects.all(), required=False)

    general_journal_items = serializers.SerializerMethodField()

    cash_account = serializers.SerializerMethodField(read_only=True)

    cash_requisition = UUIDRelatedField(
        queryset=Requisition.objects.all(),
        required=False,
        allow_null=True,
    )

    payment_exchange_rate = ExchangeRateInputSerializer(
        required=False,
        allow_null=True,
        write_only=True,
    )

    settlement_exchange_rate = ExchangeRateInputSerializer(
        required=False,
        allow_null=True,
        write_only=True,
    )

    vendor = UUIDRelatedField(
        queryset=Vendor.objects.undeleted(),
        required=False,
        allow_null=True,
        write_only=True,
    )

    payment_type = serializers.SerializerMethodField(
        read_only=True,
    )

    class Meta:
        model = VendorPayment
        fields = "__all__"

        read_only_fields = [
            "id",
            "institution",
            "currency",
            "settlement_currency",
            "settlement_amount",
            "payment_status",
            "are_initial_journal_entries_made",
            "created_at",
            "updated_at",
            "created_by",
            "updated_by",
            "object_id",
            "general_journal_items",
            "content_type",
            "remaining_balance",
            "amount_reconciled",
        ]

    def get_payment_type(self, obj):
        if obj.is_bill_payment:
            return "bill_payment"
        else:
            return "prepayment"

    def get_cash_account(self, obj):
        if not obj.cash_account:
            return None
        return CashAccountOutputSerializer(obj.cash_account).data

    def get_general_journal_items(self, obj):
        if obj.cash_requisition:
            requisition_payment = getattr(obj.cash_requisition, "payment", None)
            return get_general_journal_items_for_object(requisition_payment)

        return get_general_journal_items_for_object(obj)

    def validate(self, data):
        bill = data.get("bill", getattr(self.instance, "bill", None))
        vendor = data.get("vendor", getattr(self.instance, "vendor", None))
        branch = data.get("branch", getattr(self.instance, "branch", None))
        cash_account_data = data.get("cash_account_used")
        cash_account = (
            cash_account_data["cash_account_object"]
            if cash_account_data
            else getattr(self.instance, "cash_account", None)
        )
        amount = data.get("amount", getattr(self.instance, "amount", None))
        payment_exchange_rate = data.get("payment_exchange_rate")
        settlement_exchange_rate = data.get("settlement_exchange_rate")

        if bool(bill) == bool(vendor):
            raise validation_error(
                {
                    "payment_target": (
                        "Provide either a vendor for a prepayment or a bill "
                        "for a bill payment, but not both."
                    )
                }
            )

        if amount is None:
            raise validation_error({"amount": "The payment amount is required."})

        if amount <= Decimal("0.00"):
            raise validation_error({"amount": "The amount must be greater than zero."})

        institution = bill.get_institution() if bill else vendor.get_institution()

        if institution is None:
            raise validation_error(
                {"institution": "Could not determine the payment institution."}
            )

        if branch and branch.institution_id != institution.id:
            raise validation_error(
                {
                    "branch": (
                        "The selected branch must belong to the payment institution."
                    )
                }
            )

        if cash_account is None:
            raise validation_error(
                {"cash_account_used": "A cash or bank account is required."}
            )

        if cash_account.institution_id != institution.id:
            raise validation_error(
                {
                    "cash_account_used": (
                        "The selected cash account must belong to the "
                        "payment institution."
                    )
                }
            )

        payment_currency = (
            cash_account.currency.currency
            if cash_account.currency_id
            else institution.currency
        )
        settlement_currency = (
            bill.determine_rate_currency_used()[0]
            if bill
            else (vendor.currency if vendor.currency_id else institution.currency)
        )

        payment_base_rate = FxRateService.resolve_base_rate(
            institution=institution,
            currency=payment_currency,
            rate_input=payment_exchange_rate,
        )

        if (
            settlement_currency == institution.currency
            and payment_currency != institution.currency
        ):
            if settlement_exchange_rate is not None:
                raise validation_error(
                    {
                        "settlement_exchange_rate": (
                            "Do not provide a separate settlement rate when "
                            "the vendor balance uses the institution base currency."
                        )
                    }
                )
            settlement_to_payment_rate = Decimal("1") / payment_base_rate
        else:
            settlement_to_payment_rate = FxRateService.resolve_pair_rate(
                institution=institution,
                from_currency=settlement_currency,
                to_currency=payment_currency,
                rate_input=settlement_exchange_rate,
            )

        settlement_amount = Decimal(str(amount)) / settlement_to_payment_rate

        if settlement_amount <= Decimal("0.00"):
            raise validation_error(
                {"amount": "The converted settlement amount must be positive."}
            )

        if bill and settlement_amount > Decimal(str(bill.balance_due)):
            raise validation_error(
                {"amount": ("The payment amount cannot exceed the bill balance due.")}
            )

        requisition = data.get(
            "cash_requisition",
            getattr(self.instance, "cash_requisition", None),
        )

        if (
            self.instance is None
            and requisition
            and requisition.content_type
            and requisition.object_id
        ):
            raise validation_error(
                {
                    "cash_requisition": (
                        "The selected requisition is already linked to a payment."
                    )
                }
            )

        if requisition and self.instance:
            vendor_payment_content_type = ContentType.objects.get_for_model(
                VendorPayment,
                for_concrete_model=False,
            )

            if (
                requisition.content_type_id != vendor_payment_content_type.id
                or requisition.object_id != self.instance.pk
            ):
                raise validation_error(
                    {
                        "cash_requisition": (
                            "The selected requisition does not belong to this "
                            "vendor payment."
                        )
                    }
                )

        data["institution"] = institution
        data["currency"] = payment_currency
        data["settlement_currency"] = settlement_currency
        data["settlement_amount"] = settlement_amount
        data["_payment_base_rate"] = payment_base_rate
        data["_settlement_to_payment_rate"] = settlement_to_payment_rate

        return data

    @transaction.atomic
    def create(self, validated_data):
        cash_account_data = validated_data.pop("cash_account_used", None)
        payment_exchange_rate = validated_data.pop("payment_exchange_rate", None)
        settlement_exchange_rate = validated_data.pop("settlement_exchange_rate", None)
        payment_base_rate = validated_data.pop("_payment_base_rate")
        settlement_to_payment_rate = validated_data.pop("_settlement_to_payment_rate")

        instance = super().create(validated_data)

        if cash_account_data:
            cash_account = cash_account_data["cash_account_object"]

            instance.content_type = ContentType.objects.get_for_model(
                cash_account, for_concrete_model=False
            )
            instance.object_id = cash_account.id
            instance.save(update_fields=["content_type", "object_id"])

        FxRateService.create_document_snapshot(
            source=instance,
            institution=instance.institution,
            currency=instance.currency,
            rate_input=payment_exchange_rate,
            supplied_rate=payment_base_rate,
        )
        FxRateService.create_pair_snapshot(
            source=instance,
            institution=instance.institution,
            from_currency=instance.settlement_currency,
            to_currency=instance.currency,
            rate_input=settlement_exchange_rate,
            supplied_rate=settlement_to_payment_rate,
        )

        return instance

    @transaction.atomic
    def update(self, instance, validated_data):
        cash_account_data = validated_data.pop("cash_account_used", None)
        payment_exchange_rate = validated_data.pop("payment_exchange_rate", None)
        settlement_exchange_rate = validated_data.pop("settlement_exchange_rate", None)
        payment_base_rate = validated_data.pop("_payment_base_rate")
        settlement_to_payment_rate = validated_data.pop("_settlement_to_payment_rate")

        instance = super().update(instance, validated_data)

        if cash_account_data:
            cash_account = cash_account_data["cash_account_object"]

            instance.content_type = ContentType.objects.get_for_model(
                cash_account, for_concrete_model=False
            )
            instance.object_id = cash_account.id
            instance.save(update_fields=["content_type", "object_id"])

        FxRateService.create_document_snapshot(
            source=instance,
            institution=instance.institution,
            currency=instance.currency,
            rate_input=payment_exchange_rate,
            supplied_rate=payment_base_rate,
        )
        FxRateService.create_pair_snapshot(
            source=instance,
            institution=instance.institution,
            from_currency=instance.settlement_currency,
            to_currency=instance.currency,
            rate_input=settlement_exchange_rate,
            supplied_rate=settlement_to_payment_rate,
        )

        return instance

    def to_representation(self, instance):
        rep = super().to_representation(instance)

        payment_currency, _ = instance.determine_rate_currency_used()
        settlement_currency, _ = instance.determine_settlement_rate_currency_used()

        rep["currency"] = SystemCurrencySerializer(payment_currency).data
        rep["settlement_currency"] = SystemCurrencySerializer(settlement_currency).data
        rep["payment_exchange_rate"] = FxRateService.get_document_rate_representation(
            source=instance,
            institution=instance.get_institution(),
            currency=payment_currency,
        )
        rep["settlement_exchange_rate"] = FxRateService.get_pair_rate_representation(
            source=instance,
            from_currency=settlement_currency,
            to_currency=payment_currency,
        )

        rep["vendor"] = (
            VendorSerializer(instance.get_payment_vendor()).data
            if instance.get_payment_vendor()
            else None
        )
        rep["bill"] = (
            VendorBillSerializer(instance.bill).data if instance.bill else None
        )

        if instance.cash_requisition:
            requisition_instance = instance.cash_requisition

            rep["cash_requisition"] = {
                "id": requisition_instance.id,
                "base_uuid": str(requisition_instance.base_uuid),
                "requisition_code": requisition_instance.reference_code,
            }

        else:
            rep["cash_requisition"] = None

        return rep


class ReconcilePrepaymentSerializer(serializers.Serializer):
    prepayment_uuids = serializers.ListField(
        child=serializers.UUIDField(),
        min_length=1,
        help_text="List of prepayment base UUIDs to apply.",
    )
    bill_uuids = serializers.ListField(
        child=serializers.UUIDField(),
        min_length=1,
        help_text="List of bill base UUIDs to allocate prepayments against.",
    )


class VendorInsightsSerializer(serializers.Serializer):
    vendor_id = serializers.IntegerField()
    vendor_name = serializers.CharField()
    lead_time_days = serializers.IntegerField()

    outstanding_payables = serializers.DecimalField(max_digits=50, decimal_places=20)
    total_purchases = serializers.DecimalField(max_digits=50, decimal_places=20)
    total_paid = serializers.DecimalField(max_digits=50, decimal_places=20)

    monthly_purchases = serializers.DecimalField(max_digits=50, decimal_places=20)
    monthly_payments = serializers.DecimalField(max_digits=50, decimal_places=20)
    monthly_net_profit = serializers.DecimalField(max_digits=50, decimal_places=20)


class InventoryGoodsReceivedNoteLineItemInputSerializer(serializers.Serializer):
    line_item = UUIDRelatedField(
        queryset=InventoryItem.objects.all(),
        required=True,
    )
    unit_of_measure = UUIDRelatedField(
        queryset=InventoryItemUnitOfMeasure.objects.all(),
        required=True,
    )
    quantity = serializers.IntegerField(min_value=1, default=1)

    def validate(self, data):
        if not data.get("line_item"):
            raise validation_error("Inventory item is required.")
        return data


class GoodsReceivedNoteLineItemSerializer(serializers.ModelSerializer):
    class Meta:
        model = GoodsReceivedNoteLineItem
        fields = "__all__"

    def to_representation(self, instance):
        repr = super().to_representation(instance)

        if instance.inventory_item:
            repr["inventory_item"] = {
                "id": instance.inventory_item.id,
                "base_uuid": str(instance.inventory_item.base_uuid),
                "item_name": instance.inventory_item.item_name,
            }
        else:
            repr["inventory_item"] = None

        if instance.unit_of_measure:
            repr["unit_of_measure"] = {
                "id": instance.unit_of_measure.id,
                "base_uuid": str(instance.unit_of_measure.base_uuid),
                "unit_name": instance.unit_of_measure.unit_of_measure.unit_name,
            }
        else:
            repr["unit_of_measure"] = None

        return repr


class GoodsReceivedNoteSerializer(ContentTypeIdSerializerMixin):
    purchase_order = UUIDRelatedField(
        queryset=VendorPurchaseOrder.objects.all(),
        required=False,
        allow_null=True,
    )

    bill = UUIDRelatedField(
        queryset=VendorBill.objects.all(),
        required=False,
        allow_null=True,
    )

    branch = UUIDRelatedField(
        queryset=Branch.objects.all(),
        required=False,
        allow_null=True,
    )

    inventory_line_items = InventoryGoodsReceivedNoteLineItemInputSerializer(
        many=True,
        write_only=True,
        required=True,
    )

    inventory_items = serializers.SerializerMethodField()

    class Meta:
        model = GoodsReceivedNote
        fields = "__all__"

        read_only_fields = [
            "inventory_items",
        ]

    def get_inventory_items(self, obj):
        items = obj.line_items.all()

        if items.exists():
            return GoodsReceivedNoteLineItemSerializer(items, many=True).data
        return []

    def _create_line_items(self, grn, items_data):
        for item in items_data:
            GoodsReceivedNoteLineItem.objects.create(
                goods_received_note=grn,
                inventory_item=item["line_item"],
                unit_of_measure=item.get("unit_of_measure"),
                quantity=item["quantity"],
            )

    def validate(self, data):
        request = self.context.get("request")
        is_automated = data.get("is_automated", False)
        institution = self.context.get("institution") or get_institution(request)

        if (
            not is_automated
            and institution
            and institution.inventory_increment_timing == "ON_BILL_RECEIPT"
        ):
            raise validation_error(
                "Manual GRN creation is disabled when inventory increment timing is "
                "ON_BILL_RECEIPT. GRNs are created automatically upon bill approval."
            )

        return data

    @transaction.atomic
    def create(self, validated_data):

        inventory_items = validated_data.pop("inventory_line_items", [])

        request = self.context.get("request")
        if request:
            validated_data["institution"] = get_institution(request)

        grn = GoodsReceivedNote.objects.create(**validated_data)

        self._create_line_items(grn, inventory_items)

        return grn

    @transaction.atomic
    def update(self, instance, validated_data):
        if instance.status != "DRAFT":
            raise validation_error("Only GRNs in DRAFT can be updated.")

        inventory_items = validated_data.pop("inventory_line_items", None)

        for attr, value in validated_data.items():
            setattr(instance, attr, value)
        instance.save()

        if inventory_items is not None:
            existing_items = {
                str(item.inventory_item.base_uuid): item
                for item in instance.line_items.filter(deleted_at__isnull=True)
            }

            incoming_uuids = set()

            for item_data in inventory_items:
                inventory_item = item_data.get("line_item")

                if not inventory_item:
                    raise validation_error("Inventory item is required.")

                item_uuid = str(inventory_item.base_uuid)
                incoming_uuids.add(item_uuid)

                if item_uuid in existing_items:
                    existing_item = existing_items[item_uuid]
                    existing_item.quantity = item_data.get(
                        "quantity", existing_item.quantity
                    )
                    existing_item.save()

            missing_uuids = set(existing_items.keys()) - incoming_uuids
            if missing_uuids:
                raise validation_error(
                    f"Cannot remove existing line items: {', '.join(missing_uuids)}"
                )

        return instance

    def to_representation(self, instance):
        repr = super().to_representation(instance)

        if instance.bill:
            repr["bill"] = {
                "id": instance.bill.id,
                "base_uuid": str(instance.bill.base_uuid),
                "reference_code": instance.bill.reference_code,
                "vendor_name": (
                    instance.bill.vendor.vendor_name if instance.bill.vendor else None
                ),
            }
        else:
            repr["bill"] = None

        if instance.branch:
            repr["branch"] = {
                "id": instance.branch.id,
                "base_uuid": str(instance.branch.base_uuid),
                "branch_name": instance.branch.branch_name,
                "reference_code": instance.branch.reference_code,
            }
        else:
            repr["branch"] = None

        if instance.purchase_order:
            repr["purchase_order"] = {
                "id": instance.purchase_order.id,
                "base_uuid": str(instance.purchase_order.base_uuid),
                "reference_code": instance.purchase_order.reference_code,
                "vendor_name": (
                    instance.purchase_order.vendor.vendor_name
                    if instance.purchase_order.vendor
                    else None
                ),
            }
        else:
            repr["purchase_order"] = None

        return repr


class VendorOutstandingBalanceAdjustmentSerializer(serializers.ModelSerializer):
    class Meta:
        model = VendorOutstandingBalanceAdjustment
        fields = "__all__"


class PrepaymentAllocationSerializer(serializers.ModelSerializer):
    class Meta:
        model = PrepaymentAllocation
        fields = "__all__"

    def to_representation(self, instance):
        repr = super().to_representation(instance)

        repr["prepayment"] = {
            "id": instance.prepayment.id,
            "base_uuid": str(instance.prepayment.base_uuid),
            "reference_code": instance.prepayment.reference_code,
        }

        repr["bill"] = {
            "id": instance.bill.id,
            "base_uuid": str(instance.bill.base_uuid),
            "reference_code": instance.bill.reference_code,
        }

        return repr
