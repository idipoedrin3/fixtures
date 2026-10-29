from accounts.models import Account
from accounts.serializers import AccountSerializer
from manufacturing.models import BillOfMaterial
from .services import DemandNoticeService, ItemReturnQuantityService
from bank_management.utils import (
    CashAccountInputSerializer,
)
from transactions.utils import get_general_journal_items_for_object
from vendors.models import VendorBill, VendorBillLineItem
from system.serializers import (
    ExchangeRateInputSerializer,
    SystemCurrencySerializer,
)
from system.services import FxRateService
from utilities.helpers import (
    get_due_date,
    get_institution,
    UUIDRelatedField,
    validation_error,
    _validate_payment_term_days,
    get_quotation_expiry_date,
)
from items.serializers import BranchInventoryItemSerializer
from rest_framework import serializers
from items.models import (
    BranchInventoryItem,
    BranchInventoryItemUnitOfMeasure,
    InventoryItem,
    InventoryItemUnitOfMeasure,
)
from customers.models import (
    CreditDebitNote,
    CreditDebitNoteLineItem,
    CreditDebitNotePriceEffect,
    Customer,
    CustomerBalanceAdjustment,
    CustomerDepositAllocation,
    CustomerPayment,
    ItemReturn,
    ItemReturnItem,
    Quotation,
    QuotationLineItem,
    CustomerPurchaseOrder,
    CustomerPurchaseOrderLineItem,
    Invoice,
    InvoiceLineItem,
    PaymentTerm,
    SalesPerson,
    SalesPersonCommissionEntry,
    RecurringInvoice,
    RecurringInvoiceItem,
    RecurringInvoiceSchedule,
    GoodsIssuedNoteLineItem,
    GoodsIssuedNote,
    CustomerPurchaseOrderPayment,
    SalesLineDiscount,
)
from django.db.models import Q, Sum, F, Value, CharField
from datetime import date
from django.db import transaction as db_transaction
import logging
from approval.serializers import ContentTypeIdSerializerMixin
from institution.serializers import SimpleBranchSerializer
from decimal import Decimal
from django.db import IntegrityError, transaction
from system.exceptions import SystemNotFoundError
from rest_framework import status
from system.models import SystemCurrency
from django.contrib.contenttypes.models import ContentType
from django.core.exceptions import ObjectDoesNotExist
from django.utils import timezone
from utilities.file_utils import Base64FileFieldMixin
from taxation.serializers import (
    GeneralTaxInputSerializer,
    TaxApplicationBreakDownSerializer,
)
from taxation.service import SalesLineDiscountService
from institution.models import Branch, InstitutionItemReturnReason
from bank_management.models import (
    BankAccount,
    MobileMoneyAccount,
    DigitalWalletAccount,
    CashAtHandAccount,
)

logger = logging.getLogger(__name__)


class SalesLineDiscountSerializer(serializers.ModelSerializer):

    id = serializers.IntegerField(required=False, allow_null=True)

    class Meta:
        model = SalesLineDiscount
        fields = [
            "id",
            "base_uuid",
            "discount_type",
            "discount_value",
            "discount_amount",
            "position",
            "description",
            "source_discount",
            "created_at",
            "updated_at",
        ]
        read_only_fields = [
            "base_uuid",
            "discount_amount",
            "source_discount",
            "created_at",
            "updated_at",
        ]

    def validate_discount_type(self, value):
        if value not in dict(SalesLineDiscount.DISCOUNT_TYPE_CHOICES):
            raise serializers.ValidationError("Unsupported discount type.")
        return value

    def validate_discount_value(self, value):
        if value is None:
            raise serializers.ValidationError("A discount value is required.")
        if value < Decimal("0"):
            raise serializers.ValidationError("Discount value cannot be negative.")
        return value

    def validate(self, data):
        discount_type = data.get(
            "discount_type", getattr(self.instance, "discount_type", None)
        )
        discount_value = data.get(
            "discount_value", getattr(self.instance, "discount_value", None)
        )

        if discount_type == "percentage" and discount_value is not None:
            if discount_value > Decimal("100"):
                raise serializers.ValidationError(
                    "Percentage discount cannot exceed 100%."
                )

        return data


class SalesLineDiscountSupportMixin:

    TEMPORARY_POSITION_OFFSET = 10000

    def _order_discounts(self, discounts):

        ordered = []

        for index, discount in enumerate(discounts):
            position = discount.get("position")
            if position is None:
                position = index
            ordered.append((int(position), index, discount))

        positions = [position for position, _, _ in ordered]
        if len(set(positions)) != len(positions):
            raise validation_error(
                {"discounts": ["Each discount must have a unique position."]}
            )

        ordered.sort(key=lambda entry: (entry[0], entry[1]))

        return [discount for _, _, discount in ordered]

    def _prepare_discounts(self, discounts, *, keep_ids=True):
        prepared = []

        for index, discount in enumerate(discounts or []):
            prepared.append(
                {
                    "id": discount.get("id") if keep_ids else None,
                    "discount_type": discount.get("discount_type"),
                    "discount_value": discount.get("discount_value"),
                    "description": discount.get("description") or None,
                    "position": (
                        discount["position"]
                        if discount.get("position") is not None
                        else index
                    ),
                }
            )

        return self._order_discounts(prepared)

    def _validate_discount_values(self, discounts, *, quantity, unit_price):

        original_amount = SalesLineDiscountService._money(
            Decimal(str(quantity or 0)) * Decimal(str(unit_price or 0))
        )
        remaining_amount = original_amount

        for index, discount in enumerate(discounts):
            discount_type = discount.get("discount_type")
            discount_value = discount.get("discount_value")

            if discount_type not in dict(SalesLineDiscount.DISCOUNT_TYPE_CHOICES):
                raise validation_error(
                    {"discounts": [f"Discount {index + 1} has an unsupported type."]}
                )

            if discount_value is None:
                raise validation_error(
                    {"discounts": [f"Discount {index + 1} requires a value."]}
                )

            discount_value = Decimal(str(discount_value))

            if discount_value < Decimal("0"):
                raise validation_error(
                    {"discounts": [f"Discount {index + 1} cannot be negative."]}
                )

            if discount_type == "percentage":
                if discount_value > Decimal("100"):
                    raise validation_error(
                        {
                            "discounts": [
                                f"Percentage discount {index + 1} cannot exceed 100%."
                            ]
                        }
                    )
                discount_amount = SalesLineDiscountService._money(
                    remaining_amount * discount_value / Decimal("100")
                )
            else:
                if discount_value > remaining_amount:
                    raise validation_error(
                        {
                            "discounts": [
                                f"Fixed discount {index + 1} cannot be greater than "
                                "the remaining line amount."
                            ]
                        }
                    )
                discount_amount = discount_value

            remaining_amount = SalesLineDiscountService._money(
                remaining_amount - discount_amount
            )

        return remaining_amount

    def _invoiced_quantity_for_source(self, source_line, exclude_invoice=None):

        from django.db.models import Sum

        queryset = InvoiceLineItem.objects.filter(
            deleted_at__isnull=True,
            invoice__deleted_at__isnull=True,
        ).exclude(invoice__invoice_status="canceled")

        if isinstance(source_line, CustomerPurchaseOrderLineItem):
            queryset = queryset.filter(source_purchase_order_line=source_line)
        else:
            queryset = queryset.filter(source_quotation_line=source_line)

        if exclude_invoice is not None:
            queryset = queryset.exclude(invoice=exclude_invoice)

        return queryset.aggregate(total=Sum("quantity"))["total"] or 0

    def _discounts_match_source(self, submitted, source_discounts):
        if len(submitted) != len(source_discounts):
            return False

        for sub, src in zip(submitted, source_discounts):
            if sub["discount_type"] != src.discount_type:
                return False
            if Decimal(str(sub["discount_value"])) != Decimal(str(src.discount_value)):
                return False
            if (sub.get("description") or None) != (src.description or None):
                return False

        return True

    def _discounts_match(self, line, discounts):
        existing = list(
            line.discounts.filter(deleted_at__isnull=True).order_by("position")
        )

        if len(existing) != len(discounts):
            return False

        for current, submitted in zip(existing, discounts):
            if submitted.get("id") is not None and current.id != submitted.get("id"):
                return False

            if current.position != submitted.get("position"):
                return False

            if current.discount_type != submitted.get("discount_type"):
                return False

            if Decimal(str(current.discount_value)) != Decimal(
                str(submitted.get("discount_value") or 0)
            ):
                return False

            if (current.description or None) != (submitted.get("description") or None):
                return False

        return True

    def _apply_discounts_to_line(
        self,
        line,
        discounts,
        *,
        source_discount=None,
    ):
        existing = {
            discount.id: discount
            for discount in line.discounts.filter(deleted_at__isnull=True)
        }
        submitted_ids = {
            discount["id"] for discount in discounts if discount.get("id") is not None
        }

        for discount_id in submitted_ids:
            if discount_id not in existing:
                raise validation_error(
                    {
                        "discounts": [
                            "A submitted discount no longer belongs to this line. "
                            "Reload and try again."
                        ]
                    }
                )

        for discount_id, discount in existing.items():
            if discount_id not in submitted_ids:
                self._release_discount_allocation(discount)
                discount.delete()

        temporary_position = (
            max(
                [discount.position for discount in existing.values()]
                + [discount["position"] for discount in discounts]
                + [0]
            )
            + 1
        )
        for offset, discount in enumerate(existing.values()):
            if discount.id not in submitted_ids:
                continue
            discount.position = temporary_position + offset
            discount.save(update_fields=["position", "updated_at"])

        for discount in discounts:
            discount_id = discount.get("id")
            values = {
                "discount_type": discount["discount_type"],
                "discount_value": discount["discount_value"],
                "description": discount.get("description") or None,
                "position": discount["position"],
            }

            if discount_id is not None:
                target = existing[discount_id]
                if target.source_discount_id:
                    source = SalesLineDiscount.objects.select_for_update().get(
                        pk=target.source_discount_id
                    )
                    if (
                        source.discount_type == SalesLineDiscountService.FIXED_TYPE
                        and values["discount_type"]
                        == SalesLineDiscountService.FIXED_TYPE
                    ):
                        allocated_elsewhere = (
                            SalesLineDiscountService.allocated_source_discount_amount(
                                source,
                                exclude_discount=target,
                            )
                        )
                        if (
                            Decimal(str(values["discount_value"])) + allocated_elsewhere
                            > source.discount_value
                        ):
                            raise validation_error(
                                {
                                    "discounts": [
                                        "This fixed discount exceeds the remaining "
                                        "discount available from its source."
                                    ]
                                }
                            )
                for field, value in values.items():
                    setattr(target, field, value)
                target.save(
                    update_fields=[
                        "discount_type",
                        "discount_value",
                        "description",
                        "position",
                        "updated_at",
                    ]
                )
            else:
                SalesLineDiscount.objects.create(
                    content_object=line,
                    source_discount=source_discount,
                    **values,
                )

        return list(line.discounts.filter(deleted_at__isnull=True).order_by("position"))

    def _release_discount_allocation(self, discount):
        """Give back the amount a fixed discount had allocated downstream."""
        if not discount.source_discount_id:
            return

        if discount.discount_type != SalesLineDiscountService.FIXED_TYPE:
            return

        released = SalesLineDiscountService._money(discount.discount_amount)

        if released <= 0:
            return

        SalesLineDiscount.objects.filter(pk=discount.source_discount_id).update(
            allocated_amount=F("allocated_amount") - released
        )

    def _copy_source_discounts(
        self,
        line,
        source_discounts,
        *,
        invoice_quantity=None,
        source_quantity=None,
        already_invoiced_quantity=0,
    ):
        created = []

        for source_discount in source_discounts:
            discount_value = source_discount.discount_value

            if source_discount.discount_type == SalesLineDiscountService.FIXED_TYPE:
                discount_value = SalesLineDiscountService.allocate_source_discount(
                    source_discount,
                    invoice_quantity=invoice_quantity,
                    source_quantity=source_quantity,
                    already_invoiced_quantity=already_invoiced_quantity,
                )

            new_discount = SalesLineDiscount.objects.create(
                content_object=line,
                discount_type=source_discount.discount_type,
                discount_value=discount_value,
                position=source_discount.position,
                description=source_discount.description,
                source_discount=source_discount,
            )

            if (
                source_discount.discount_type == SalesLineDiscountService.FIXED_TYPE
                and discount_value > 0
            ):
                SalesLineDiscount.objects.filter(pk=source_discount.pk).update(
                    allocated_amount=F("allocated_amount") + discount_value
                )

            created.append(new_discount)

        return created


PAYMENT_TERM_DUPLICATE_MESSAGE = (
    "A payment term with the same name and days until due already exists."
)


def resolve_manufacturing_output(line_item, branch_unit_of_measure):
    if not line_item or not branch_unit_of_measure:
        raise validation_error(
            "Inventory item and unit of measure are required when manufacturing is enabled."
        )

    if branch_unit_of_measure.branch_inventory_item_id != line_item.id:
        raise validation_error(
            {
                "unit_of_measure": (
                    "The selected unit of measure does not belong to the selected item."
                )
            }
        )

    inventory_unit_of_measure = (
        InventoryItemUnitOfMeasure.objects.undeleted()
        .filter(
            inventory_item=line_item.inventory_item,
            unit_of_measure=branch_unit_of_measure.unit_of_measure,
        )
        .first()
    )

    if not inventory_unit_of_measure:
        raise validation_error(
            {
                "unit_of_measure": (
                    "The selected branch unit of measure is not configured on the "
                    "institution inventory item."
                )
            }
        )

    return line_item.inventory_item, inventory_unit_of_measure


class PaymentTermListSerializer(serializers.ListSerializer):
    def validate(self, data):
        seen = set()

        for item in data:
            key = (
                item.get("term_name", "").strip().casefold(),
                item.get("days_until_due"),
            )

            if key in seen:
                raise validation_error(PAYMENT_TERM_DUPLICATE_MESSAGE)

            seen.add(key)

        return data


class PaymentTermSerializer(
    ContentTypeIdSerializerMixin,
):
    class Meta:
        model = PaymentTerm
        fields = "__all__"
        list_serializer_class = PaymentTermListSerializer
        read_only_fields = [
            "id",
            "base_uuid",
            "created_at",
            "updated_at",
            "updated_by",
            "institution",
        ]

    def validate_days_until_due(self, value):
        _validate_payment_term_days(value, "Payment term")
        return value

    def validate(self, data):
        institution = self.context.get("institution")
        if not institution:
            raise validation_error("Institution not found in serializer context.")

        term_name = data.get(
            "term_name",
            getattr(self.instance, "term_name", None),
        )
        days_until_due = data.get(
            "days_until_due",
            getattr(self.instance, "days_until_due", None),
        )

        existing_qs = (
            PaymentTerm.objects.undeleted()
            .filter(
                institution=institution,
                term_name__iexact=term_name.strip(),
                days_until_due=days_until_due,
            )
            .exclude(pk=getattr(self.instance, "pk", None))
        )

        if existing_qs.exists():
            raise validation_error(PAYMENT_TERM_DUPLICATE_MESSAGE)

        data["term_name"] = term_name.strip()
        return data

    def create(self, validated_data):
        institution = self.context.get("institution")
        if not institution:
            raise validation_error("Institution not found in serializer context.")

        validated_data["institution"] = institution
        try:
            with transaction.atomic():
                return super().create(validated_data)
        except IntegrityError:
            raise validation_error(PAYMENT_TERM_DUPLICATE_MESSAGE)

    def update(self, instance, validated_data):
        validated_data.pop("institution", None)
        try:
            with transaction.atomic():
                return super().update(instance, validated_data)
        except IntegrityError:
            raise validation_error(PAYMENT_TERM_DUPLICATE_MESSAGE)


class SimpleCustomerSerializer(serializers.ModelSerializer):
    currency = SystemCurrencySerializer(read_only=True)

    class Meta:
        model = Customer
        fields = [
            "id",
            "base_uuid",
            "customer_name",
            "customer_type",
            "currency",
            "email",
            "address",
            "phone_number",
            "profile_photo",
            "tin",
        ]


class QuotationLineItemSerializer(serializers.ModelSerializer):
    line_item = UUIDRelatedField(
        queryset=BranchInventoryItem.objects.all(),
        help_text="Base UUID of the branch inventory item.",
    )

    unit_of_measure = UUIDRelatedField(
        queryset=BranchInventoryItemUnitOfMeasure.objects.all(),
        required=True,
    )

    class Meta:
        model = QuotationLineItem
        fields = "__all__"
        read_only_fields = [
            "id",
            "base_uuid",
            "created_at",
            "updated_at",
            "quotation",
            "created_by",
            "updated_by",
            "is_deleted",
            "line_total",
        ]

    def validate(self, data):
        quantity = data.get("quantity")

        unit_price = data.get("unit_price")

        if not quantity:
            raise validation_error("Quantity is required.")

        if unit_price is None:
            data["unit_price"] = data["unit_of_measure"].selling_price

        data["line_total"] = data["unit_price"] * quantity

        return data

    def to_representation(self, instance):
        repr = super().to_representation(instance)
        repr["line_item"] = BranchInventoryItemSerializer(instance.line_item).data
        repr["line_item_tax_breakdowns"] = TaxApplicationBreakDownSerializer(
            instance.get_tax_breakdowns(),
            many=True,
        ).data
        repr["discounts"] = SalesLineDiscountSerializer(
            instance.get_discounts(),
            many=True,
        ).data

        if instance.unit_of_measure:
            repr["unit_of_measure"] = {
                "id": instance.unit_of_measure.id,
                "unit_name": instance.unit_of_measure.unit_of_measure.unit_name,
                "unit_abbreviation": instance.unit_of_measure.unit_of_measure.unit_abbreviation,
                "is_base_unit_of_measure": instance.unit_of_measure.is_base_unit_of_measure,
                "selling_price": instance.unit_of_measure.selling_price,
                "base_uuid": instance.unit_of_measure.base_uuid,
            }

        return repr


class QuotationNestedLineItemSerializer(QuotationLineItemSerializer):
    quotation_line_item_uuid = UUIDRelatedField(
        required=False,
        write_only=True,
        queryset=QuotationLineItem.objects.filter(is_deleted=False),
    )
    discounts = SalesLineDiscountSerializer(many=True, required=False)

    def validate(self, data):
        quotation = self.root.instance
        quotation_line = data.get("quotation_line_item_uuid")

        if quotation_line is not None:
            if quotation is None:
                raise validation_error(
                    {
                        "quotation_line_item_uuid": [
                            "Do not supply an existing quotation line item when creating a new quotation."
                        ]
                    }
                )

            if quotation_line.quotation_id != quotation.id:
                raise validation_error(
                    {
                        "quotation_line_item_uuid": [
                            "The provided quotation line item does not belong to the current quotation."
                        ]
                    }
                )

        required_fields = ["line_item", "unit_of_measure", "quantity"]

        if quotation is not None:
            required_fields.append("unit_price")

        errors = {
            field: ["This field is required for each submitted line item."]
            for field in required_fields
            if data.get(field) is None
        }

        if errors:
            raise validation_error(errors)

        if data["unit_of_measure"].branch_inventory_item_id != data["line_item"].id:
            raise validation_error(
                {
                    "unit_of_measure": [
                        "The selected unit of measure does not belong to the selected inventory item."
                    ]
                }
            )

        return super().validate(data)


class QuotationSerializer(SalesLineDiscountSupportMixin, ContentTypeIdSerializerMixin):
    line_items = QuotationNestedLineItemSerializer(
        many=True,
        write_only=True,
    )

    line_items_count = serializers.SerializerMethodField(
        read_only=True,
    )

    total_amount = serializers.DecimalField(
        max_digits=50,
        decimal_places=20,
        read_only=True,
    )

    exchange_rate = ExchangeRateInputSerializer(
        required=False,
        allow_null=True,
        write_only=True,
    )

    customer = UUIDRelatedField(
        queryset=Customer.objects.active(),
        required=True,
        write_only=True,
    )

    def get_line_items_count(self, instance):
        return instance.line_items.count()

    class Meta:
        model = Quotation
        fields = "__all__"
        read_only_fields = [
            "approval_status",
            "original_data",
            "total_amount",
            "net_total",
            "tax_total",
            "gross_total",
            "status",
            "branch",
            "currency",
            "line_items_count",
        ]

    def to_representation(self, instance):
        representation = super().to_representation(instance)
        representation["customer"] = SimpleCustomerSerializer(instance.customer).data
        representation["branch"] = SimpleBranchSerializer(instance.branch).data
        representation["currency"] = (
            SystemCurrencySerializer(instance.currency).data
            if instance.currency
            else None
        )

        exchange_rate = (
            FxRateService.get_document_rate_representation(
                source=instance,
                institution=instance.get_institution(),
                currency=instance.currency,
            )
            if instance.currency
            else None
        )

        representation["exchange_rate"] = exchange_rate
        representation["exchange_rate_status"] = (
            exchange_rate["source"] if exchange_rate is not None else "missing"
        )

        return representation

    def validate(self, data):
        customer = data.get("customer", getattr(self.instance, "customer", None))

        if self.instance:
            if CustomerPurchaseOrder.objects.filter(quotation=self.instance).exists():
                raise validation_error(
                    "Cannot update a quotation that has associated purchase orders."
                )

            if Invoice.objects.filter(quotation=self.instance).exists():
                raise validation_error(
                    "Cannot update a quotation that has associated invoices."
                )

            institution = self.instance.get_institution()
            current_currency = self.instance.currency or institution.currency
            requested_currency = (
                customer.currency
                if customer and customer.currency_id
                else institution.currency
            )

            if requested_currency != current_currency:
                raise validation_error(
                    {
                        "customer": [
                            "The selected customer uses a different currency. "
                            "Create a new quotation instead."
                        ]
                    }
                )

        if not customer:
            raise validation_error("A quotation must have a customer.")

        if customer.approval_status != "active" or customer.has_ongoing_approval():
            raise validation_error(
                {
                    "customer": [
                        "The customer's approval process must be completed "
                        "before they can be used on a quotation."
                    ]
                }
            )

        expiry_date = data.get("expiry_date")
        if "issue_date" in data and data["issue_date"] > date.today():
            raise validation_error("Issue date cannot be in the future.")

        if expiry_date and expiry_date < timezone.now().date():
            raise validation_error({"Expiry date cannot be in the past."})

        if "line_items" in data:
            line_items = data["line_items"]
            if not isinstance(line_items, list) or len(line_items) == 0:
                raise validation_error(
                    {"line_items": ["At least one line item is required."]}
                )

            branches = {item["line_item"].branch_id for item in line_items}

            if len(branches) > 1:
                raise validation_error(
                    {"line_items": ["All line items must belong to the same branch."]}
                )

            submitted_ids = [
                item["quotation_line_item_uuid"].pk
                for item in line_items
                if item.get("quotation_line_item_uuid") is not None
            ]
            if len(submitted_ids) != len(set(submitted_ids)):
                raise validation_error(
                    {
                        "line_items": [
                            "The same quotation line cannot be submitted twice."
                        ]
                    }
                )

            if self.instance and branches != {self.instance.branch_id}:
                raise validation_error(
                    {
                        "line_items": [
                            "All line items must belong to the quotation's branch."
                        ]
                    }
                )

        if (
            customer
            and not customer.currency_id
            and not customer.institution.currency_id
        ):
            raise validation_error(
                "The customer and institution do not have a configured currency."
            )

        return data

    def create(self, validated_data):
        request = self.context.get("request")
        institution = get_institution(request)

        line_items_data = validated_data.pop("line_items")
        rate_input = validated_data.pop("exchange_rate", None)

        expiry_date = validated_data.get("expiry_date")
        issue_date = validated_data.get("issue_date")

        if not expiry_date:
            validated_data["expiry_date"] = get_quotation_expiry_date(
                institution, issue_date
            )

        validated_data["branch"] = line_items_data[0]["line_item"].branch

        customer = validated_data.get("customer")
        target_currency = (
            customer.currency
            if customer and customer.currency_id
            else institution.currency
        )
        validated_data["currency"] = target_currency

        with db_transaction.atomic():
            quotation = Quotation.objects.create(**validated_data)

            canonical_rate = FxRateService.create_document_snapshot(
                source=quotation,
                institution=institution,
                currency=target_currency,
                rate_input=rate_input,
            )

            for item_data in line_items_data:
                discounts_data = self._prepare_discounts(
                    item_data.pop("discounts", None)
                )
                quantity = item_data.get("quantity")
                unit_of_measure = item_data.get("unit_of_measure")
                unit_price = (
                    item_data.get("unit_price") or unit_of_measure.selling_price
                )

                if target_currency != quotation.get_institution().currency:
                    converted_unit_price = FxRateService.convert_from_base(
                        unit_price,
                        canonical_rate,
                    )

                else:
                    converted_unit_price = unit_price

                line_total = converted_unit_price * quantity

                self._validate_discount_values(
                    discounts_data,
                    quantity=quantity,
                    unit_price=converted_unit_price,
                )

                quotation_line = QuotationLineItem.objects.create(
                    quotation=quotation,
                    line_item=item_data["line_item"],
                    quantity=quantity,
                    unit_price=converted_unit_price,
                    line_total=line_total,
                    unit_of_measure=unit_of_measure,
                )

                self._apply_discounts_to_line(quotation_line, discounts_data)

                SalesLineDiscountService.apply_line_discounts_and_taxes(
                    line=quotation_line,
                )

            SalesLineDiscountService.recompute_document_totals_with_discounts(quotation)

        return quotation

    def update(self, instance, validated_data):
        line_items_data = validated_data.pop("line_items", None)
        rate_was_provided = "exchange_rate" in validated_data
        rate_input = validated_data.pop("exchange_rate", None)
        institution = instance.get_institution()

        with db_transaction.atomic():
            for attr, value in validated_data.items():
                setattr(instance, attr, value)
            instance.save()

            if rate_was_provided:
                FxRateService.replace_document_snapshot(
                    source=instance,
                    institution=institution,
                    currency=instance.currency or institution.currency,
                    rate_input=rate_input,
                )

            if line_items_data is not None:
                existing_items = {
                    item.pk: item for item in instance.line_items.select_for_update()
                }
                retained_ids = set()

                for item_data in line_items_data:
                    line_data = item_data.copy()
                    submitted_discounts = line_data.pop("discounts", None)
                    discounts_data = (
                        self._prepare_discounts(submitted_discounts)
                        if submitted_discounts is not None
                        else None
                    )
                    submitted_line = line_data.pop("quotation_line_item_uuid", None)

                    if submitted_line is None:
                        quotation_line = QuotationLineItem.objects.create(
                            quotation=instance,
                            **line_data,
                        )
                        changed = True
                    else:
                        quotation_line = existing_items.get(submitted_line.pk)
                        if quotation_line is None:
                            raise validation_error(
                                {
                                    "line_items": [
                                        "A submitted line no longer belongs "
                                        "to this quotation. Reload and try again."
                                    ]
                                }
                            )

                        changed = False
                        for attr, value in line_data.items():
                            if getattr(quotation_line, attr) != value:
                                setattr(quotation_line, attr, value)
                                changed = True

                        if changed:
                            quotation_line.save()

                    retained_ids.add(quotation_line.pk)

                    if discounts_data is not None:
                        self._validate_discount_values(
                            discounts_data,
                            quantity=quotation_line.quantity,
                            unit_price=quotation_line.unit_price,
                        )
                        self._apply_discounts_to_line(quotation_line, discounts_data)
                        changed = True

                    if changed:
                        SalesLineDiscountService.apply_line_discounts_and_taxes(
                            line=quotation_line,
                        )

                removed_ids = set(existing_items) - retained_ids

                if removed_ids:
                    for removed_line in existing_items.values():
                        if removed_line.pk in removed_ids:
                            for discount in removed_line.discounts.filter(
                                deleted_at__isnull=True
                            ):
                                self._release_discount_allocation(discount)
                    instance.line_items.filter(pk__in=removed_ids).delete()

                SalesLineDiscountService.recompute_document_totals_with_discounts(
                    instance
                )

        return instance


class CustomerPurchaseOrderLineItemSerializer(serializers.ModelSerializer):
    line_item = UUIDRelatedField(queryset=BranchInventoryItem.objects.all())

    unit_of_measure = UUIDRelatedField(
        queryset=BranchInventoryItemUnitOfMeasure.objects.all(),
        required=True,
    )

    should_auto_create_manufacturing_order = serializers.BooleanField(
        default=False,
        write_only=True,
    )
    bill_of_material_to_be_used = UUIDRelatedField(
        queryset=BillOfMaterial.objects.undeleted(),
        required=False,
        allow_null=True,
        write_only=True,
    )
    qty_to_be_manufactured = serializers.IntegerField(
        required=False,
        min_value=1,
        write_only=True,
    )
    manufacturing_order_description = serializers.CharField(
        required=False,
        allow_blank=True,
        allow_null=True,
        max_length=1000,
        write_only=True,
    )

    quantity_billed = serializers.SerializerMethodField()

    class Meta:
        model = CustomerPurchaseOrderLineItem
        fields = "__all__"
        read_only_fields = [
            "id",
            "base_uuid",
            "created_at",
            "updated_at",
            "purchase_order",
            "source_quotation_line",
            "quantity_pending",
            "quantity_issued",
            "quantity_billed",
        ]

    def get_quantity_billed(self, instance):
        annotated_quantity = getattr(instance, "annotated_quantity_billed", None)
        if annotated_quantity is not None:
            return annotated_quantity

        sales_order = instance.purchase_order

        if sales_order is None:
            return 0

        total = InvoiceLineItem.objects.filter(
            invoice__purchase_order=sales_order,
            line_item=instance.line_item,
            deleted_at__isnull=True,
        ).aggregate(total_quantity=Sum("quantity"))

        return total["total_quantity"] or 0

    def validate(self, data):
        quantity = data.get("quantity")
        unit_price = data.get("unit_price")

        if quantity is None or unit_price is None:
            raise validation_error("Quantity and unit price are required")

        line_total = quantity * unit_price

        data["line_total"] = line_total

        if data.get("should_auto_create_manufacturing_order", False):
            bill_of_material = data.get("bill_of_material_to_be_used")
            line_item = data.get("line_item")
            inventory_item, inventory_unit_of_measure = resolve_manufacturing_output(
                line_item,
                data.get("unit_of_measure"),
            )

            if bill_of_material and (
                bill_of_material.inventory_item_id != inventory_item.id
                or bill_of_material.unit_of_measure_id != inventory_unit_of_measure.id
            ):
                raise validation_error(
                    "The selected Bill of Material must match the sales order "
                    "item and unit of measure."
                )

            if not data.get("qty_to_be_manufactured"):
                data["qty_to_be_manufactured"] = quantity

        return data

    def to_representation(self, instance):
        repr = super().to_representation(instance)
        repr["line_item"] = BranchInventoryItemSerializer(instance.line_item).data
        repr["line_item_tax_breakdowns"] = TaxApplicationBreakDownSerializer(
            instance.get_tax_breakdowns(),
            many=True,
        ).data
        repr["discounts"] = SalesLineDiscountSerializer(
            instance.get_discounts(),
            many=True,
        ).data
        repr["source_quotation_line"] = (
            {
                "id": instance.source_quotation_line.id,
                "base_uuid": instance.source_quotation_line.base_uuid,
            }
            if instance.source_quotation_line
            else None
        )

        if instance.unit_of_measure:
            repr["unit_of_measure"] = {
                "id": instance.unit_of_measure.id,
                "unit_name": instance.unit_of_measure.unit_of_measure.unit_name,
                "unit_abbreviation": instance.unit_of_measure.unit_of_measure.unit_abbreviation,
                "is_base_unit_of_measure": instance.unit_of_measure.is_base_unit_of_measure,
                "selling_price": instance.unit_of_measure.selling_price,
                "base_uuid": instance.unit_of_measure.base_uuid,
            }

        return repr


class CustomerPurchaseOrderListSerializer(serializers.ModelSerializer):
    line_items_count = serializers.IntegerField(read_only=True)
    total_price = serializers.DecimalField(
        max_digits=50,
        decimal_places=20,
        read_only=True,
    )
    quotation = serializers.SerializerMethodField()
    customer = serializers.SerializerMethodField()
    branch = serializers.SerializerMethodField()
    currency = serializers.SerializerMethodField()
    rate = serializers.SerializerMethodField()

    class Meta:
        model = CustomerPurchaseOrder
        fields = [
            "id",
            "base_uuid",
            "reference_code",
            "issue_date",
            "status",
            "approval_status",
            "goods_issued_note_status",
            "invoice_status",
            "description",
            "is_active",
            "created_at",
            "updated_at",
            "line_items_count",
            "total_price",
            "net_total",
            "tax_total",
            "gross_total",
            "quotation",
            "customer",
            "branch",
            "currency",
            "rate",
        ]

    def get_quotation(self, instance):
        quotation = instance.quotation
        if quotation is None:
            return None

        customer = quotation.customer
        return {
            "id": quotation.id,
            "base_uuid": quotation.base_uuid,
            "reference_code": quotation.reference_code,
            "status": quotation.status,
            "customer": (
                {
                    "id": customer.id,
                    "base_uuid": customer.base_uuid,
                    "customer_name": customer.customer_name,
                }
                if customer
                else None
            ),
        }

    def get_customer(self, instance):
        customer = instance.get_purchase_order_customer()
        if customer is None:
            return None

        return {
            "id": customer.id,
            "base_uuid": customer.base_uuid,
            "customer_name": customer.customer_name,
        }

    def get_branch(self, instance):
        branch = instance.branch
        if branch is None:
            return None

        return {
            "id": branch.id,
            "base_uuid": branch.base_uuid,
            "reference_code": branch.reference_code,
            "branch_name": branch.branch_name,
        }

    def get_currency(self, instance):
        currency = instance.currency or instance.branch.institution.currency
        return SystemCurrencySerializer(currency).data

    def get_rate(self, instance):
        exchange_rate = self.context["exchange_rates"].get(instance.id)
        return exchange_rate.rate if exchange_rate else 1


class CustomerPurchaseOrderPaymentSerializer(ContentTypeIdSerializerMixin):
    cash_account = CashAccountInputSerializer(
        write_only=True,
        required=True,
    )

    class Meta:
        model = CustomerPurchaseOrderPayment
        fields = "__all__"

        read_only_fields = [
            "are_initial_journal_entries_made",
            "sales_order",
            "invoice",
            "account",
            "amount_applied",
            "payment_status",
            "is_transfer_processed",
        ]

    def validate(self, attrs):
        purchase_order = self.context.get("purchase_order")

        if not purchase_order:
            raise validation_error(
                {"purchase_order": "Customer purchase order is required."}
            )

        if (
            not purchase_order.is_active
            or purchase_order.deleted_at is not None
            or purchase_order.approval_status != "active"
            or purchase_order.has_ongoing_approval()
        ):
            raise validation_error(
                {
                    "purchase_order": [
                        "Payments can only be recorded against an active "
                        "sales order with no ongoing approvals."
                    ]
                }
            )

        amount = attrs.get(
            "amount_paid",
            getattr(self.instance, "amount_paid", None),
        )

        if amount is not None and amount <= 0:
            raise validation_error(
                {"amount_paid": "Payment amount must be greater than zero."}
            )

        institution = purchase_order.get_institution()
        cash_account_data = attrs.get("cash_account")

        if (
            cash_account_data
            and cash_account_data["cash_account_object"].get_institution()
            != institution
        ):
            raise validation_error(
                {
                    "cash_account": (
                        "The selected cash account must belong to the same institution."
                    )
                }
            )

        existing_payments = purchase_order.payments.undeleted().exclude(
            payment_status="rejected"
        ).aggregate(total=Sum("amount_paid"))["total"] or Decimal("0")
        remaining_amount = purchase_order.total_price - existing_payments

        if amount is not None and amount > remaining_amount:
            raise validation_error(
                {
                    "amount_paid": (
                        f"Payment cannot exceed the remaining order balance "
                        f"of {remaining_amount}."
                    )
                }
            )

        return attrs

    def create(self, validated_data):
        purchase_order = self.context.get("purchase_order")

        if not purchase_order:
            raise validation_error(
                {"purchase_order": "Customer purchase order is required."}
            )

        cash_account_data = validated_data.pop("cash_account")
        cash_account = cash_account_data["cash_account_object"]
        account = cash_account.get_chart_of_account_reference()

        if not account:
            raise validation_error(
                {
                    "cash_account": (
                        "The selected cash account is not linked to a chart of account."
                    )
                }
            )

        validated_data["sales_order"] = purchase_order
        validated_data["account"] = account
        validated_data["amount_applied"] = Decimal("0")
        validated_data["payment_status"] = "pending"

        return super().create(validated_data)

    def to_representation(self, instance):
        representation = super().to_representation(instance)

        representation["account"] = (
            AccountSerializer(instance.account).data if instance.account else None
        )

        representation["invoice"] = (
            {
                "id": instance.invoice.id,
                "reference_code": instance.invoice.reference_code,
                "base_uuid": instance.invoice.base_uuid,
            }
            if instance.invoice
            else None
        )

        representation["sales_order"] = {
            "id": instance.sales_order.id,
            "reference_code": instance.sales_order.reference_code,
            "base_uuid": instance.sales_order.base_uuid,
        }

        return representation


class NestedSalesOrderPaymentSerializer(serializers.Serializer):
    amount_paid = serializers.DecimalField(
        write_only=True,
        max_digits=50,
        decimal_places=20,
    )

    cash_account = CashAccountInputSerializer(
        write_only=True,
        required=True,
    )

    def validate_amount_paid(self, value):
        if value <= 0:
            raise validation_error("Payment amount must be greater than zero.")

        return value


class CustomerPurchaseOrderNestedLineItemSerializer(
    CustomerPurchaseOrderLineItemSerializer
):
    sales_order_line_item_uuid = UUIDRelatedField(
        queryset=CustomerPurchaseOrderLineItem.objects.undeleted(),
        required=False,
        write_only=True,
    )
    discounts = SalesLineDiscountSerializer(many=True, required=False)

    def validate(self, data):
        sales_order = self.root.instance
        existing_line = data.get("sales_order_line_item_uuid")

        if existing_line is not None:
            if sales_order is None or existing_line.purchase_order_id != sales_order.pk:
                raise validation_error(
                    {
                        "sales_order_line_item_uuid": [
                            "The selected line must belong to the sales order "
                            "being updated."
                        ]
                    }
                )

        errors = {
            field: ["This field is required for each submitted line item."]
            for field in ("line_item", "unit_of_measure", "quantity", "unit_price")
            if data.get(field) is None
        }
        if errors:
            raise validation_error(errors)

        if data["unit_of_measure"].branch_inventory_item_id != data["line_item"].pk:
            raise validation_error(
                {
                    "unit_of_measure": [
                        "The selected unit of measure does not belong to "
                        "the selected inventory item."
                    ]
                }
            )

        if sales_order is not None and data.get(
            "should_auto_create_manufacturing_order", False
        ):
            raise validation_error(
                "Create manufacturing orders separately when editing a sales order."
            )

        return super().validate(data)


class CustomerPurchaseOrderSerializer(
    SalesLineDiscountSupportMixin, ContentTypeIdSerializerMixin
):
    can_record_payment_or_invoice = serializers.SerializerMethodField()

    def get_can_record_payment_or_invoice(self, instance):
        return (
            instance.is_active
            and instance.deleted_at is None
            and instance.approval_status == "active"
            and not instance.has_ongoing_approval()
        )

    currency = serializers.PrimaryKeyRelatedField(
        queryset=SystemCurrency.objects.all(),
        required=False,
        allow_null=True,
    )
    line_items = CustomerPurchaseOrderNestedLineItemSerializer(
        many=True,
        write_only=True,
    )

    line_items_count = serializers.SerializerMethodField()

    payments = CustomerPurchaseOrderPaymentSerializer(
        many=True,
        read_only=True,
    )

    quotation = serializers.PrimaryKeyRelatedField(
        queryset=Quotation.objects.all(), required=False, allow_null=True
    )

    total_price = serializers.DecimalField(
        max_digits=50, decimal_places=20, read_only=True
    )

    customer = UUIDRelatedField(
        queryset=Customer.objects.all(),
        required=False,
        allow_null=True,
    )

    exchange_rate = ExchangeRateInputSerializer(
        required=False,
        allow_null=True,
        write_only=True,
    )

    payment = NestedSalesOrderPaymentSerializer(
        write_only=True,
        required=False,
    )

    def get_line_items_count(self, instance):
        return instance.line_items.filter(deleted_at__isnull=True).count()

    class Meta:
        model = CustomerPurchaseOrder
        fields = "__all__"
        read_only_fields = [
            "approval_status",
            "original_data",
            "goods_issued_note_status",
            "invoice_status",
            "branch",
            "status",
            "net_total",
            "tax_total",
            "gross_total",
        ]

    def to_representation(self, instance):
        repr = super().to_representation(instance)
        if instance.quotation:
            repr["quotation"] = QuotationSerializer(instance.quotation).data
        else:
            repr["quotation"] = None

        repr["branch"] = SimpleBranchSerializer(instance.branch).data

        document_currency, _ = instance.determine_rate_currency_used()
        repr["currency"] = SystemCurrencySerializer(document_currency).data
        exchange_rate = (
            FxRateService.get_document_rate_representation(
                source=(
                    instance
                    if instance.currency_id
                    else (
                        instance.quotation
                        if instance.quotation and instance.quotation.currency_id
                        else instance
                    )
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

        customer = instance.get_purchase_order_customer()

        if customer is not None:
            repr["customer"] = SimpleCustomerSerializer(customer).data
        else:
            repr["customer"] = None

        return repr

    def validate(self, data):

        quotation = data.get("quotation", getattr(self.instance, "quotation", None))
        payment = data.get("payment")
        customer = data.get(
            "customer",
            getattr(self.instance, "customer", None),
        )
        effective_customer = customer or (quotation.customer if quotation else None)

        if effective_customer:
            if (
                not effective_customer.is_active
                or effective_customer.deleted_at is not None
                or effective_customer.approval_status != "active"
                or effective_customer.has_ongoing_approval()
            ):
                raise validation_error(
                    {
                        "customer": [
                            "Select an active customer with no ongoing approvals."
                        ]
                    }
                )

        if quotation and (
            not quotation.is_active
            or quotation.deleted_at is not None
            or quotation.approval_status != "active"
            or quotation.has_ongoing_approval()
        ):
            raise validation_error(
                {"quotation": ["Select an active quotation with no ongoing approvals."]}
            )

        if "issue_date" in data and data["issue_date"] > date.today():
            raise validation_error("Issue date cannot be in the future.")
        if self.instance is None and not data.get("line_items"):
            raise validation_error("At least one line item is required.")

        if self.instance is not None and payment:
            raise validation_error(
                {"payment": ["Use the sales-order payment endpoint to add a payment."]}
            )

        if payment and not effective_customer:
            raise validation_error(
                {
                    "customer": [
                        "A customer must be selected when a payment is attached "
                        "to the sales order."
                    ]
                }
            )

        if quotation and customer and customer != quotation.customer:
            raise validation_error(
                {
                    "customer": [
                        "The selected customer must match the quotation customer."
                    ]
                }
            )

        if self.instance:
            institution = self.instance.get_institution()
            current_currency = self.instance.currency or institution.currency
            requested_currency = (
                quotation.currency
                if quotation
                else (
                    customer.currency
                    if customer and customer.currency_id
                    else institution.currency
                )
            )
            if requested_currency != current_currency:
                raise validation_error(
                    {
                        "customer": [
                            "The selected source uses a different currency. "
                            "Create a new sales order instead."
                        ]
                    }
                )

        if quotation:
            qs = CustomerPurchaseOrder.objects.undeleted().filter(quotation=quotation)

        if quotation and self.instance:
            qs = qs.exclude(pk=self.instance.pk)

        existing_purchase_order = (
            qs.only("reference_code").first() if quotation else None
        )
        if existing_purchase_order:
            raise validation_error(
                "This quotation is already attached to Sales Order "
                f"{existing_purchase_order.reference_code}."
            )

        if self.instance:
            if Invoice.objects.filter(purchase_order=self.instance).exists():
                raise validation_error(
                    "Cannot update a sales order that has associated invoices."
                )

            if "quotation" in data and quotation != self.instance.quotation:
                raise validation_error(
                    "The source quotation cannot be changed after the sales order "
                    "has been created."
                )

        if "line_items" in data:
            line_items = data["line_items"]
            if not isinstance(line_items, list) or len(line_items) == 0:
                raise validation_error(
                    {"line_items": ["At least one line item is required."]}
                )

            branches = {item["line_item"].branch_id for item in line_items}

            if len(branches) > 1:
                raise validation_error(
                    {"line_items": ["All line items must belong to the same branch."]}
                )

            expected_branch_id = (
                self.instance.branch_id
                if self.instance
                else quotation.branch_id if quotation else None
            )
            if expected_branch_id is not None and branches != {expected_branch_id}:
                raise validation_error(
                    {"line_items": ["All lines must belong to the document's branch."]}
                )

            submitted_ids = [
                item["sales_order_line_item_uuid"].pk
                for item in line_items
                if item.get("sales_order_line_item_uuid") is not None
            ]
            if len(submitted_ids) != len(set(submitted_ids)):
                raise validation_error(
                    {"line_items": ["The same sales-order line cannot appear twice."]}
                )

        return data

    def _resolve_source_quotation_line(
        self,
        quotation,
        item_data,
        used_source_line_ids,
    ):
        if quotation is None:
            return None

        source_line = (
            quotation.line_items.filter(
                line_item=item_data["line_item"],
                unit_of_measure=item_data["unit_of_measure"],
            )
            .exclude(id__in=used_source_line_ids)
            .order_by("id")
            .first()
        )

        if source_line is not None:
            used_source_line_ids.add(source_line.id)

        return source_line

    def create(self, validated_data):
        line_items_data = validated_data.pop("line_items")
        quotation = validated_data.get("quotation")
        rate_input = validated_data.pop("exchange_rate", None)
        payment_data = validated_data.pop("payment", None)
        requested_currency = validated_data.pop("currency", None)

        if quotation is not None:
            validated_data["branch"] = quotation.branch
            validated_data["customer"] = quotation.customer
            target_currency = quotation.currency or quotation.get_institution().currency
        else:
            validated_data["branch"] = line_items_data[0]["line_item"].branch
            institution = validated_data["branch"].institution
            customer = validated_data.get("customer")
            target_currency = (
                customer.currency
                if customer and customer.currency_id
                else requested_currency or institution.currency
            )

        validated_data["currency"] = target_currency

        request = self.context.get("request")

        with db_transaction.atomic():
            purchase_order = CustomerPurchaseOrder.objects.create(**validated_data)

            if quotation is not None:
                canonical_rate = FxRateService.resolve_base_rate(
                    institution=purchase_order.get_institution(),
                    currency=target_currency,
                    source=quotation,
                )
                canonical_rate = FxRateService.create_document_snapshot(
                    source=purchase_order,
                    institution=purchase_order.get_institution(),
                    currency=target_currency,
                    supplied_rate=canonical_rate,
                )
            else:
                canonical_rate = FxRateService.create_document_snapshot(
                    source=purchase_order,
                    institution=purchase_order.get_institution(),
                    currency=target_currency,
                    rate_input=rate_input,
                )

            if payment_data:
                cash_account_data = payment_data["cash_account"]
                cash_account = cash_account_data["cash_account_object"]

                if cash_account.institution_id != purchase_order.get_institution().id:
                    raise validation_error(
                        {
                            "payment": {
                                "cash_account": (
                                    "The selected cash account must belong "
                                    "to the same institution as the Sales Order."
                                )
                            }
                        }
                    )

                account = cash_account.get_chart_of_account_reference()

                if account is None:
                    raise validation_error(
                        {
                            "payment": {
                                "cash_account": (
                                    "The selected cash account does not have "
                                    "a chart-of-account reference."
                                )
                            }
                        }
                    )

                payment = CustomerPurchaseOrderPayment.objects.create(
                    sales_order=purchase_order,
                    amount_paid=payment_data["amount_paid"],
                    account=account,
                )

                payment.confirm_create(
                    profile_institution=request.profile_institution,
                    external_identity=request.external_identity,
                )

            manufacturing_order_requests = []

            institution_currency = purchase_order.get_institution().currency
            used_source_line_ids = set()

            for item_data in line_items_data:
                submitted_discounts = item_data.pop("discounts", None)
                discounts_data = (
                    self._prepare_discounts(submitted_discounts, keep_ids=False)
                    if submitted_discounts is not None
                    else None
                )
                source_quotation_line = self._resolve_source_quotation_line(
                    quotation=purchase_order.quotation,
                    item_data=item_data,
                    used_source_line_ids=used_source_line_ids,
                )
                unit_price = item_data.get("unit_price")
                quantity = item_data.get("quantity")
                unit_of_measure = item_data.get("unit_of_measure")

                if purchase_order.quotation:
                    converted_unit_price = unit_price
                elif target_currency != institution_currency:
                    converted_unit_price = FxRateService.convert_from_base(
                        unit_price,
                        canonical_rate,
                    )
                else:
                    converted_unit_price = unit_price

                line_total = converted_unit_price * quantity

                purchase_order_line = CustomerPurchaseOrderLineItem.objects.create(
                    purchase_order=purchase_order,
                    source_quotation_line=source_quotation_line,
                    line_item=item_data["line_item"],
                    unit_price=converted_unit_price,
                    quantity=quantity,
                    line_total=line_total,
                    unit_of_measure=unit_of_measure,
                    quantity_pending=(
                        quantity
                        if item_data["line_item"].inventory_item.item_type == "GOODS"
                        else 0
                    ),
                )
                source_discounts = []
                if source_quotation_line:
                    source_discounts = list(
                        source_quotation_line.discounts.select_for_update()
                        .filter(deleted_at__isnull=True)
                        .order_by("position")
                    )

                if (
                    discounts_data is not None
                    and source_discounts
                    and self._discounts_match_source(discounts_data, source_discounts)
                ):
                    discounts_data = None

                if discounts_data is None:
                    if source_discounts:
                        self._copy_source_discounts(
                            purchase_order_line,
                            source_discounts,
                            invoice_quantity=quantity,
                            source_quantity=source_quotation_line.quantity,
                        )
                else:
                    self._validate_discount_values(
                        discounts_data,
                        quantity=quantity,
                        unit_price=converted_unit_price,
                    )
                    self._apply_discounts_to_line(purchase_order_line, discounts_data)

                SalesLineDiscountService.apply_line_discounts_and_taxes(
                    line=purchase_order_line,
                    source_line=source_quotation_line,
                )

                if item_data.get("should_auto_create_manufacturing_order", False):
                    inventory_item, inventory_unit_of_measure = (
                        resolve_manufacturing_output(
                            item_data["line_item"],
                            item_data["unit_of_measure"],
                        )
                    )
                    manufacturing_order_requests.append(
                        {
                            "bill_of_material": item_data.get(
                                "bill_of_material_to_be_used"
                            ),
                            "inventory_item": inventory_item,
                            "unit_of_measure": inventory_unit_of_measure,
                            "quantity_to_produce": item_data["qty_to_be_manufactured"],
                            "description": item_data.get(
                                "manufacturing_order_description"
                            )
                            or "",
                        }
                    )

            if manufacturing_order_requests:
                self._bulk_create_manufacturing_orders(
                    purchase_order,
                    manufacturing_order_requests,
                )

            has_goods = any(
                item_data["line_item"].inventory_item.item_type == "GOODS"
                for item_data in line_items_data
            )
            purchase_order.goods_issued_note_status = (
                "not_issued" if has_goods else "not_required"
            )
            purchase_order.save(update_fields=["goods_issued_note_status"])
            SalesLineDiscountService.recompute_document_totals_with_discounts(
                purchase_order
            )

        purchase_order.send_customer_purchase_order_email()

        return purchase_order

    def _bulk_create_manufacturing_orders(
        self,
        purchase_order: CustomerPurchaseOrder,
        order_requests: list[dict],
    ):
        from manufacturing.serializers import ManufacturingOrderSerializer

        customer = purchase_order.get_purchase_order_customer()
        payload = [
            {
                **(
                    {
                        "bill_of_material": str(
                            order_request["bill_of_material"].base_uuid
                        )
                    }
                    if order_request["bill_of_material"]
                    else {}
                ),
                "inventory_item": str(order_request["inventory_item"].base_uuid),
                "unit_of_measure": str(order_request["unit_of_measure"].base_uuid),
                "quantity_to_produce": order_request["quantity_to_produce"],
                "description": order_request.get("description") or "",
                "branch": str(purchase_order.branch.base_uuid),
                "content_type": ContentType.objects.get_for_model(
                    CustomerPurchaseOrder
                ).id,
                "content_object_uuid": str(purchase_order.base_uuid),
                **({"client": str(customer.base_uuid)} if customer else {}),
            }
            for order_request in order_requests
        ]

        serializer = ManufacturingOrderSerializer(
            data=payload,
            many=True,
            allow_empty=False,
            context=self.context,
        )
        serializer.is_valid(raise_exception=True)
        orders = serializer.save()

        request = self.context["request"]
        for order in orders:
            order.confirm_create(
                profile_institution=request.profile_institution,
                external_identity=request.external_identity,
            )

    def update(self, instance, validated_data):
        line_items_data = validated_data.pop("line_items", None)
        rate_was_provided = "exchange_rate" in validated_data
        rate_input = validated_data.pop("exchange_rate", None)

        with db_transaction.atomic():
            for attr, value in validated_data.items():
                setattr(instance, attr, value)
            instance.save()

            if rate_was_provided:
                FxRateService.replace_document_snapshot(
                    source=instance,
                    institution=instance.get_institution(),
                    currency=instance.currency or instance.get_institution().currency,
                    rate_input=rate_input,
                )

            if line_items_data is None:
                return instance

            existing_items = {
                line.pk: line
                for line in instance.line_items.filter(
                    deleted_at__isnull=True
                ).select_for_update()
            }
            retained_ids = set()
            used_source_line_ids = {
                line.source_quotation_line_id
                for line in existing_items.values()
                if line.source_quotation_line_id
            }

            for item_data in line_items_data:
                line_data = item_data.copy()
                submitted_discounts = line_data.pop("discounts", None)
                discounts_data = (
                    self._prepare_discounts(submitted_discounts)
                    if submitted_discounts is not None
                    else None
                )
                submitted_line = line_data.pop("sales_order_line_item_uuid", None)
                for field in (
                    "should_auto_create_manufacturing_order",
                    "bill_of_material_to_be_used",
                    "qty_to_be_manufactured",
                    "manufacturing_order_description",
                ):
                    line_data.pop(field, None)

                purchase_order_line = None
                if submitted_line is not None:
                    purchase_order_line = existing_items.get(submitted_line.pk)
                    if purchase_order_line is None:
                        raise validation_error(
                            "A submitted line no longer belongs to this sales order. "
                            "Reload and try again."
                        )

                changed = purchase_order_line is None or any(
                    getattr(purchase_order_line, field) != value
                    for field, value in line_data.items()
                )

                if purchase_order_line is not None and changed:
                    if (
                        purchase_order_line.quantity_issued
                        or purchase_order_line.goods_issue_lines.exists()
                    ):
                        raise validation_error(
                            "A line linked to a goods-issued note cannot be changed."
                        )

                if purchase_order_line is not None and discounts_data is not None:
                    if not self._discounts_match(purchase_order_line, discounts_data):
                        changed = True

                if purchase_order_line is not None and not changed:
                    retained_ids.add(purchase_order_line.pk)
                    continue

                same_source_item = (
                    purchase_order_line is not None
                    and purchase_order_line.line_item_id == line_data["line_item"].pk
                    and purchase_order_line.unit_of_measure_id
                    == line_data["unit_of_measure"].pk
                )
                source_quotation_line = (
                    purchase_order_line.source_quotation_line
                    if same_source_item
                    else self._resolve_source_quotation_line(
                        quotation=instance.quotation,
                        item_data=line_data,
                        used_source_line_ids=used_source_line_ids,
                    )
                )
                line_data["source_quotation_line"] = source_quotation_line
                line_data["quantity_pending"] = (
                    line_data["quantity"]
                    if line_data["line_item"].inventory_item.item_type == "GOODS"
                    else 0
                )

                if purchase_order_line is None:
                    purchase_order_line = CustomerPurchaseOrderLineItem.objects.create(
                        purchase_order=instance,
                        **line_data,
                    )
                else:
                    for field, value in line_data.items():
                        setattr(purchase_order_line, field, value)
                    purchase_order_line.save()

                retained_ids.add(purchase_order_line.pk)

                if discounts_data is not None:
                    self._validate_discount_values(
                        discounts_data,
                        quantity=purchase_order_line.quantity,
                        unit_price=purchase_order_line.unit_price,
                    )
                    self._apply_discounts_to_line(purchase_order_line, discounts_data)
                    changed = True

                if changed:
                    SalesLineDiscountService.apply_line_discounts_and_taxes(
                        line=purchase_order_line,
                        source_line=source_quotation_line,
                    )

            for removed_id in set(existing_items) - retained_ids:
                removed_line = existing_items[removed_id]
                if (
                    removed_line.quantity_issued
                    or removed_line.goods_issue_lines.exists()
                ):
                    raise validation_error(
                        "A line linked to a goods-issued note cannot be removed."
                    )
                for discount in removed_line.discounts.filter(deleted_at__isnull=True):
                    self._release_discount_allocation(discount)
                removed_line.delete()

            has_goods = instance.line_items.filter(
                deleted_at__isnull=True,
                line_item__inventory_item__item_type="GOODS",
            ).exists()
            if not has_goods:
                instance.goods_issued_note_status = "not_required"
            elif instance.goods_issued_note_status == "not_required":
                instance.goods_issued_note_status = "not_issued"

            instance.save(update_fields=["goods_issued_note_status"])
            SalesLineDiscountService.recompute_document_totals_with_discounts(
                instance,
                lines=instance.line_items.filter(deleted_at__isnull=True),
            )

        return instance


class InvoiceLineItemSerializer(serializers.ModelSerializer):
    line_item = UUIDRelatedField(
        queryset=BranchInventoryItem.objects.all(), write_only=True
    )

    unit_of_measure = UUIDRelatedField(
        queryset=BranchInventoryItemUnitOfMeasure.objects.all(),
        required=True,
    )

    should_auto_create_manufacturing_order = serializers.BooleanField(
        default=False,
        write_only=True,
        help_text="Indicates whether a manufacturing order should be automatically created for this line item if it is a manufactured item.",
    )
    bill_of_material_to_be_used = UUIDRelatedField(
        queryset=BillOfMaterial.objects.undeleted(),
        required=False,
        allow_null=True,
        write_only=True,
    )
    qty_to_be_manufactured = serializers.IntegerField(
        required=False,
        min_value=1,
        write_only=True,
        help_text="The quantity to be manufactured for this line item if it is a manufactured item.",
    )
    manufacturing_order_description = serializers.CharField(
        required=False,
        allow_blank=True,
        allow_null=True,
        max_length=1000,
        write_only=True,
    )

    class Meta:
        model = InvoiceLineItem
        fields = "__all__"
        read_only_fields = [
            "id",
            "base_uuid",
            "created_at",
            "updated_at",
            "invoice",
            "source_purchase_order_line",
            "source_quotation_line",
            "created_by",
            "updated_by",
            "is_deleted",
        ]

    def validate(self, data):

        line_item = data.get("line_item")

        if (
            line_item
            and line_item.inventory_item
            and line_item.inventory_item.can_be_sold is False
        ):
            raise validation_error(
                f"The item '{line_item.inventory_item.item_name}' cannot be sold."
            )

        quantity = data.get("quantity")
        unit_price = data.get("unit_price") or data["unit_of_measure"].selling_price
        data["unit_price"] = unit_price
        line_total = quantity * unit_price
        data["line_total"] = line_total

        should_auto_create_manufacturing_order = data.get(
            "should_auto_create_manufacturing_order", False
        )

        if should_auto_create_manufacturing_order:
            bill_of_material = data.get("bill_of_material_to_be_used")
            inventory_item, inventory_unit_of_measure = resolve_manufacturing_output(
                line_item,
                data.get("unit_of_measure"),
            )

            if bill_of_material and (
                bill_of_material.inventory_item_id != inventory_item.id
                or bill_of_material.unit_of_measure_id != inventory_unit_of_measure.id
            ):
                raise validation_error(
                    "The selected Bill of Material must match the invoice item "
                    "and unit of measure."
                )

            if not data.get("qty_to_be_manufactured"):
                data["qty_to_be_manufactured"] = quantity

        return data

    def to_representation(self, instance):
        repr = super().to_representation(instance)

        inventory_item = (
            instance.line_item.inventory_item if instance.line_item else None
        )
        inventory_item_unit_of_measure = None

        if inventory_item and instance.unit_of_measure:
            inventory_item_unit_of_measure = next(
                (
                    unit
                    for unit in inventory_item.units.all()
                    if unit.deleted_at is None
                    and unit.unit_of_measure_id
                    == instance.unit_of_measure.unit_of_measure_id
                ),
                None,
            )

        if instance.line_item and instance.line_item.inventory_item:
            repr["branch_item"] = {
                "item_name": instance.line_item.inventory_item.item_name,
                "id": instance.line_item.id,
                "reference_code": instance.line_item.inventory_item.reference_code,
                "base_uuid": instance.line_item.base_uuid,
                "inventory_item": {
                    "id": inventory_item.id,
                    "item_name": inventory_item.item_name,
                    "reference_code": inventory_item.reference_code,
                    "base_uuid": inventory_item.base_uuid,
                },
            }

        tax_breakdowns_by_line_id = self.context.get("tax_breakdowns_by_line_id")
        tax_breakdowns = (
            tax_breakdowns_by_line_id.get(instance.id, [])
            if tax_breakdowns_by_line_id is not None
            else instance.get_tax_breakdowns()
        )

        repr["line_item_tax_breakdowns"] = TaxApplicationBreakDownSerializer(
            tax_breakdowns,
            many=True,
        ).data
        repr["source_purchase_order_line"] = (
            {
                "id": instance.source_purchase_order_line.id,
                "base_uuid": instance.source_purchase_order_line.base_uuid,
            }
            if instance.source_purchase_order_line
            else None
        )
        repr["source_quotation_line"] = (
            {
                "id": instance.source_quotation_line.id,
                "base_uuid": instance.source_quotation_line.base_uuid,
            }
            if instance.source_quotation_line
            else None
        )

        if instance.unit_of_measure:
            repr["unit_of_measure"] = {
                "id": instance.unit_of_measure.id,
                "unit_name": instance.unit_of_measure.unit_of_measure.unit_name,
                "unit_abbreviation": instance.unit_of_measure.unit_of_measure.unit_abbreviation,
                "is_base_unit_of_measure": instance.unit_of_measure.is_base_unit_of_measure,
                "selling_price": instance.unit_of_measure.selling_price,
                "base_uuid": instance.unit_of_measure.base_uuid,
                "inventory_item_unit_of_measure": (
                    {
                        "id": inventory_item_unit_of_measure.id,
                        "base_uuid": inventory_item_unit_of_measure.base_uuid,
                    }
                    if inventory_item_unit_of_measure
                    else None
                ),
            }

        repr["discounts"] = SalesLineDiscountSerializer(
            instance.get_discounts(),
            many=True,
        ).data

        return repr


class InvoiceLineItemListResponseSerializer(serializers.Serializer):
    count = serializers.IntegerField()
    next = serializers.URLField(allow_null=True)
    previous = serializers.URLField(allow_null=True)
    results = InvoiceLineItemSerializer(many=True)
    meta = serializers.DictField()


class InvoicePaymentCashAccount(serializers.Serializer):
    content_type = serializers.IntegerField()
    content_object_uuid = serializers.UUIDField()

    def validate(self, attrs):
        content_type = attrs.get("content_type")
        content_object_uuid = attrs.get("content_object_uuid", None)

        if content_type and content_object_uuid:
            try:
                content_type = ContentType.objects.get(pk=content_type)
            except ContentType.DoesNotExist:
                raise validation_error("Invalid content type.")

            model_class = content_type.model_class()

            if not model_class:
                raise validation_error("Invalid content type.")

            allowed_models = (
                BankAccount,
                MobileMoneyAccount,
                DigitalWalletAccount,
                CashAtHandAccount,
            )

            if model_class not in allowed_models:
                raise validation_error(
                    "Invoice payments can only be linked to a cash account model."
                )

            try:
                obj = model_class.objects.get(base_uuid=content_object_uuid)
            except ObjectDoesNotExist:
                raise validation_error(
                    "No object found with this UUID for the given content type."
                )

        return attrs


class InvoiceNestedLineItemSerializer(InvoiceLineItemSerializer):
    invoice_line_item_uuid = UUIDRelatedField(
        queryset=InvoiceLineItem.objects.undeleted(),
        required=False,
        write_only=True,
    )
    discounts = SalesLineDiscountSerializer(many=True, required=False)

    def validate(self, data):
        invoice = self.root.instance
        existing_line = data.get("invoice_line_item_uuid")
        if existing_line is not None and (
            invoice is None or existing_line.invoice_id != invoice.pk
        ):
            raise validation_error(
                {
                    "invoice_line_item_uuid": [
                        "The selected line must belong to the invoice being updated."
                    ]
                }
            )
        errors = {
            field: ["This field is required for each submitted line item."]
            for field in ("line_item", "unit_of_measure", "quantity", "unit_price")
            if data.get(field) is None
        }
        if errors:
            raise validation_error(errors)
        if data["quantity"] <= 0:
            raise validation_error(
                {"quantity": ["Quantity must be greater than zero."]}
            )
        if data["unit_of_measure"].branch_inventory_item_id != data["line_item"].pk:
            raise validation_error(
                {
                    "unit_of_measure": [
                        "The selected unit of measure does not belong to this item."
                    ]
                }
            )
        if invoice is not None and data.get(
            "should_auto_create_manufacturing_order", False
        ):
            raise validation_error(
                "Create manufacturing orders separately when editing an invoice."
            )
        supplied_unit_price = data["unit_price"]
        validated = super().validate(data)
        validated["unit_price"] = supplied_unit_price
        validated["line_total"] = data["quantity"] * supplied_unit_price
        return validated


class InvoiceSerializer(SalesLineDiscountSupportMixin, ContentTypeIdSerializerMixin):
    IMMUTABLE_FIELDS_ON_UPDATE = ["amount_due"]

    customer = UUIDRelatedField(
        queryset=Customer.objects.undeleted(),
        required=False,
        allow_null=True,
        write_only=True,
    )
    purchase_order = UUIDRelatedField(
        queryset=CustomerPurchaseOrder.objects.undeleted(),
        required=False,
        allow_null=True,
        write_only=True,
    )
    quotation = UUIDRelatedField(
        queryset=Quotation.objects.undeleted(),
        required=False,
        allow_null=True,
        write_only=True,
    )
    recurring_invoice = UUIDRelatedField(
        queryset=RecurringInvoice.objects.undeleted(),
        required=False,
        allow_null=True,
        default=None,
        write_only=True,
    )

    line_items = InvoiceNestedLineItemSerializer(many=True, write_only=True)

    currency = serializers.PrimaryKeyRelatedField(
        queryset=SystemCurrency.objects.all(),
        required=False,
        allow_null=True,
    )

    amount_paid = serializers.SerializerMethodField()

    cash_account = InvoicePaymentCashAccount(
        write_only=True, required=False, allow_null=True
    )

    related_goods_issued_notes = serializers.SerializerMethodField()
    related_invoice_payments = serializers.SerializerMethodField()

    payment_term = UUIDRelatedField(
        queryset=PaymentTerm.objects.undeleted(),
        required=False,
        write_only=True,
    )

    exchange_rate = ExchangeRateInputSerializer(
        required=False,
        allow_null=True,
        write_only=True,
    )

    class Meta:
        model = Invoice
        fields = "__all__"
        read_only_fields = [
            "approval_status",
            "original_data",
            "invoice_status",
            "branch",
            "total_amount",
            "net_total",
            "tax_total",
            "gross_total",
            "are_initial_journal_entries_made",
            "due_date",
            "amount_due",
            "amount_paid",
            "goods_issued_note_status",
            "related_goods_issued_notes",
            "adjusted_total",
            "related_invoice_payments",
        ]

    def get_related_goods_issued_notes(self, instance):
        relationship = Q(invoice=instance)

        if instance.purchase_order_id:
            relationship |= Q(purchase_order_id=instance.purchase_order_id)

        return list(
            GoodsIssuedNote.objects.filter(
                relationship,
                deleted_at__isnull=True,
            )
            .exclude(status="cancelled")
            .order_by("date_issued", "id")
            .values(
                "base_uuid",
                "reference_code",
                "status",
            )
        )

    def get_related_invoice_payments(self, obj):

        if not obj:
            return []

        if obj.invoice_payment_status not in ["paid", "partially_paid"]:
            return []

        payments = (
            CustomerPayment.objects.undeleted()
            .filter(
                invoice=obj,
                payment_status="APPROVED",
            )
            .annotate(
                type=Value("payment", output_field=CharField()),
                uuid_value=F("base_uuid"),
                ref_code=F("reference_code"),
            )
            .values(
                "uuid_value",
                "ref_code",
                "type",
                "payment_date",
            )
        )

        prepayments = (
            CustomerDepositAllocation.objects.undeleted()
            .filter(
                invoice=obj,
                prepayment__deleted_at__isnull=True,
                prepayment__is_active=True,
                prepayment__payment_status="APPROVED",
            )
            .annotate(
                uuid_value=F("prepayment__base_uuid"),
                ref_code=F("prepayment__reference_code"),
                type=Value("prepayment", output_field=CharField()),
                payment_date=F("prepayment__payment_date"),
            )
            .values(
                "uuid_value",
                "ref_code",
                "type",
                "payment_date",
            )
        )

        return list(payments.union(prepayments, all=True).order_by("-payment_date"))

    def get_amount_paid(self, instance):
        total_amount = Decimal(str(instance.total_amount or 0))
        amount_due = Decimal(str(instance.amount_due or 0))
        return total_amount - amount_due

    def to_representation(self, instance):
        repr = super().to_representation(instance)

        repr["customer"] = (
            SimpleCustomerSerializer(instance.get_invoice_customer()).data
            if instance.get_invoice_customer()
            else None
        )

        repr["purchase_order"] = (
            {
                "id": instance.purchase_order.id,
                "base_uuid": instance.purchase_order.base_uuid,
                "reference_code": instance.purchase_order.reference_code,
            }
            if instance.purchase_order
            else None
        )
        repr["quotation"] = (
            {
                "id": instance.quotation.id,
                "base_uuid": instance.quotation.base_uuid,
                "reference_code": instance.quotation.reference_code,
            }
            if instance.quotation
            else None
        )

        repr["branch"] = {
            "id": instance.branch.id if instance.branch else None,
            "base_uuid": instance.branch.base_uuid if instance.branch else None,
            "branch_name": instance.branch.branch_name if instance.branch else None,
        }

        currency, _ = instance.determine_rate_currency_used()
        repr["currency"] = SystemCurrencySerializer(currency).data
        exchange_rate = FxRateService.get_document_rate_representation(
            source=(
                instance
                if instance.currency_id
                else (
                    instance.purchase_order
                    if instance.purchase_order_id
                    else instance.quotation if instance.quotation_id else instance
                )
            ),
            institution=instance.get_institution(),
            currency=currency,
        )
        repr["exchange_rate"] = exchange_rate
        repr["exchange_rate_status"] = (
            exchange_rate["source"] if exchange_rate else "missing"
        )

        return repr

    def validate(self, data):
        from utilities.helpers import format_currency

        request = self.context.get("request")
        if not request:
            raise validation_error("Request Not found in the Context")

        institution = get_institution(request)

        instance = self.instance
        issue_date = data.get("issue_date", getattr(instance, "issue_date", None))
        line_items_data = data.get("line_items")
        cash_account = data.get("cash_account", None)
        invoice_payment_status = data.get(
            "invoice_payment_status",
            getattr(instance, "invoice_payment_status", None),
        )
        payment_term = data.pop(
            "payment_term",
            getattr(instance, "payment_term", None),
        )

        purchase_order = data.get(
            "purchase_order",
            getattr(instance, "purchase_order", None),
        )

        if purchase_order and (
            not purchase_order.is_active
            or purchase_order.deleted_at is not None
            or purchase_order.approval_status != "active"
            or purchase_order.has_ongoing_approval()
        ):
            raise validation_error(
                {
                    "purchase_order": [
                        "An invoice can only use an active sales order "
                        "with no ongoing approvals."
                    ]
                }
            )

        quotation = data.get(
            "quotation",
            getattr(instance, "quotation", None),
        )
        requested_currency = data.get(
            "currency",
            getattr(instance, "currency", None),
        )

        source_document = purchase_order or quotation
        if source_document is not None and requested_currency is not None:
            source_currency, _ = source_document.determine_rate_currency_used()
            if requested_currency != source_currency:
                raise validation_error(
                    {
                        "currency": [
                            "The invoice currency must match the selected "
                            "sales order or quotation currency."
                        ]
                    }
                )

        recurring_invoice = data.get(
            "recurring_invoice",
            getattr(instance, "recurring_invoice", None),
        )

        supplied_sources = [
            source
            for source in (purchase_order, quotation, recurring_invoice)
            if source is not None
        ]
        if len(supplied_sources) > 1:
            raise validation_error(
                "An invoice can use only one source: sales order, quotation, "
                "or recurring invoice."
            )

        customer = (
            data.get("customer")
            or getattr(instance, "customer", None)
            or (
                purchase_order.get_purchase_order_customer() if purchase_order else None
            )
            or getattr(quotation, "customer", None)
            or getattr(recurring_invoice, "customer", None)
        )

        if not customer and invoice_payment_status != "paid":
            raise validation_error(
                "An unpaid or partially paid invoice must have a customer."
            )

        attached_records = {
            "customer": customer,
            "purchase_order": purchase_order,
            "quotation": quotation,
            "recurring_invoice": recurring_invoice,
            "payment_term": payment_term or getattr(customer, "payment_term", None),
        }
        for field, record in attached_records.items():
            if record is None:
                continue
            if record.get_institution() != institution:
                raise validation_error(
                    {field: ["The selected record must belong to this institution."]}
                )
            if (
                not record.is_active
                or record.deleted_at is not None
                or record.approval_status != "active"
                or record.has_ongoing_approval()
            ):
                raise validation_error(
                    {field: ["Select an active record with no ongoing approvals."]}
                )

        if recurring_invoice and customer != recurring_invoice.customer:
            raise validation_error(
                {
                    "customer": [
                        "The selected customer must match the recurring invoice customer."
                    ]
                }
            )
        if instance:
            for field in ("purchase_order", "quotation", "recurring_invoice"):
                if field in data and data[field] != getattr(instance, field):
                    raise validation_error(
                        {
                            field: [
                                "The invoice source cannot be changed after creation."
                            ]
                        }
                    )

        if purchase_order and customer != purchase_order.get_purchase_order_customer():
            raise validation_error(
                {
                    "customer": [
                        "The selected customer must match the sales-order customer."
                    ]
                }
            )

        if quotation and customer != quotation.customer:
            raise validation_error(
                {
                    "customer": [
                        "The selected customer must match the quotation customer."
                    ]
                }
            )

        if self.instance and self.instance.are_initial_journal_entries_made:
            raise validation_error(
                "A posted invoice cannot be edited. Issue an adjustment or "
                "credit/debit note instead."
            )

        data["customer"] = customer
        data["due_date"] = get_due_date(
            institution=institution,
            payment_term=(payment_term or getattr(customer, "payment_term", None)),
            issue_date=issue_date,
        )

        if invoice_payment_status in ["paid", "partially_paid"] and not cash_account:
            raise validation_error(
                "Cash account must be given when an invoice is paid or partially paid."
            )

        if issue_date and issue_date > date.today():
            raise validation_error(
                {"issue_date": "Issue date cannot be in the future."}
            )

        if instance is not None and "line_items" not in data:
            return data

        if not line_items_data:
            raise validation_error(
                {"line_items": "At least one line item is required."}
            )

        submitted_ids = [
            item["invoice_line_item_uuid"].pk
            for item in line_items_data
            if item.get("invoice_line_item_uuid") is not None
        ]
        if len(submitted_ids) != len(set(submitted_ids)):
            raise validation_error(
                {"line_items": ["The same invoice line cannot appear twice."]}
            )

        branches = {item["line_item"].branch_id for item in line_items_data}

        if len(branches) > 1:
            raise validation_error(
                {"line_items": "All line items must belong to the same branch."}
            )

        branch = line_items_data[0]["line_item"].branch

        if instance and branch.pk != instance.branch_id:
            raise validation_error(
                {"line_items": ["All lines must belong to the invoice's branch."]}
            )

        data["branch"] = branch

        allow_oversell = getattr(branch, "allow_sales_out_of_stock", False)

        for item_data in line_items_data:
            branch_inventory_item = item_data.get("line_item")
            quantity = item_data.get("quantity")
            unit_of_measure = item_data.get("unit_of_measure")

            if not (
                branch_inventory_item
                and hasattr(branch_inventory_item, "inventory_item")
                and branch_inventory_item.inventory_item.item_type == "GOODS"
                and quantity
                and quantity > Decimal("0.00")
            ):
                continue

            try:
                branch_item = BranchInventoryItem.objects.get(
                    id=branch_inventory_item.id, branch=branch
                )

            except BranchInventoryItem.DoesNotExist:
                raise SystemNotFoundError(
                    detail="Branch inventory item does not exist",
                    status_code=status.HTTP_404_NOT_FOUND,
                )

            qty_available = branch_item.get_effective_quantity_at_hand(
                unit_of_measure=unit_of_measure
            )

            if (
                qty_available is not None
                and qty_available < quantity
                and not allow_oversell
            ):
                item_name = branch_inventory_item.inventory_item.item_name
                unit_name = (
                    unit_of_measure.unit_of_measure.unit_name
                    if unit_of_measure
                    else "units"
                )

                institution = get_institution(request)

                allow_breakdown = getattr(institution, "allow_unit_breakdown", False)

                if allow_breakdown:
                    raise validation_error(
                        f"Insufficient stock for '{item_name}'. "
                        f"You need {format_currency(quantity)} {unit_name} but only "
                        f"{format_currency(qty_available)} {unit_name} equivalent is available "
                        f"across all stock layers."
                    )
                else:
                    raise validation_error(
                        f"Insufficient stock for '{item_name}' in {unit_name}. "
                        f"Available: {format_currency(qty_available)} {unit_name}. "
                        f"Stock may exist in a different unit "
                        f"(e.g. Cartons) but unit breakdown is not enabled "
                        f"for this institution."
                    )

        return data

    def _resolve_source_line(
        self,
        purchase_order,
        quotation,
        item_data,
        used_order_line_ids,
        used_quotation_line_ids,
    ):
        if purchase_order is not None:
            source_order_line = (
                purchase_order.line_items.filter(
                    line_item=item_data["line_item"],
                    unit_of_measure=item_data["unit_of_measure"],
                )
                .exclude(id__in=used_order_line_ids)
                .order_by("id")
                .first()
            )

            if source_order_line is not None:
                used_order_line_ids.add(source_order_line.id)
                return (
                    source_order_line,
                    source_order_line.source_quotation_line,
                    source_order_line,
                )

        if purchase_order is None and quotation is not None:
            source_quotation_line = (
                quotation.line_items.filter(
                    line_item=item_data["line_item"],
                    unit_of_measure=item_data["unit_of_measure"],
                )
                .exclude(id__in=used_quotation_line_ids)
                .order_by("id")
                .first()
            )

            if source_quotation_line is not None:
                used_quotation_line_ids.add(source_quotation_line.id)
                return None, source_quotation_line, source_quotation_line

        return None, None, None

    @transaction.atomic
    def create(self, validated_data):
        line_items_data = validated_data.pop("line_items", [])
        invoice_payment_cash_account = validated_data.pop("cash_account", None)
        rate_input = validated_data.pop("exchange_rate", None)
        requested_currency = validated_data.pop("currency", None)

        purchase_order = validated_data.get("purchase_order")
        quotation = validated_data.get("quotation")
        customer = validated_data.get("customer")
        institution = validated_data["branch"].institution
        source_document = purchase_order or quotation

        if source_document is not None:
            target_currency, _ = source_document.determine_rate_currency_used()
        else:
            target_currency = (
                requested_currency
                or (customer.currency if customer and customer.currency_id else None)
                or institution.currency
            )

        validated_data["currency"] = target_currency

        with db_transaction.atomic():
            invoice = Invoice.objects.create(**validated_data)

            canonical_rate = FxRateService.create_document_snapshot(
                source=invoice,
                institution=institution,
                currency=target_currency,
                rate_input=rate_input,
            )

            manufacturing_order_requests = []
            used_order_line_ids = set()
            used_quotation_line_ids = set()

            for item_data in line_items_data:
                line_item_data = item_data.copy()
                submitted_discounts = line_item_data.pop("discounts", None)
                discounts_data = (
                    self._prepare_discounts(submitted_discounts, keep_ids=False)
                    if submitted_discounts is not None
                    else None
                )
                (
                    source_order_line,
                    source_quotation_line,
                    source_line,
                ) = self._resolve_source_line(
                    purchase_order=invoice.purchase_order,
                    quotation=invoice.quotation,
                    item_data=line_item_data,
                    used_order_line_ids=used_order_line_ids,
                    used_quotation_line_ids=used_quotation_line_ids,
                )
                line_item_data["source_purchase_order_line"] = source_order_line
                line_item_data["source_quotation_line"] = source_quotation_line
                should_create_order = line_item_data.pop(
                    "should_auto_create_manufacturing_order", False
                )
                bill_of_material = line_item_data.pop(
                    "bill_of_material_to_be_used", None
                )
                quantity_to_produce = line_item_data.pop("qty_to_be_manufactured", None)
                manufacturing_order_description = line_item_data.pop(
                    "manufacturing_order_description",
                    "",
                )

                if target_currency != institution.currency and source_line is None:
                    line_item_data["unit_price"] = FxRateService.convert_from_base(
                        line_item_data["unit_price"],
                        canonical_rate,
                    )
                    line_item_data["line_total"] = (
                        line_item_data["unit_price"] * line_item_data["quantity"]
                    )

                if source_line is not None:
                    source_line = source_line.__class__.objects.select_for_update().get(
                        pk=source_line.pk
                    )

                invoice_line = InvoiceLineItem.objects.create(
                    invoice=invoice,
                    **line_item_data,
                )

                source_discounts = []
                if source_order_line:
                    source_discounts = list(
                        source_order_line.discounts.select_for_update()
                        .filter(deleted_at__isnull=True)
                        .order_by("position")
                    )
                elif source_quotation_line:
                    source_discounts = list(
                        source_quotation_line.discounts.select_for_update()
                        .filter(deleted_at__isnull=True)
                        .order_by("position")
                    )

                if (
                    discounts_data is not None
                    and source_discounts
                    and self._discounts_match_source(discounts_data, source_discounts)
                ):
                    discounts_data = None

                if discounts_data is None:
                    if source_discounts:
                        source_line_qty = source_line.quantity if source_line else 0
                        already_invoiced_qty = self._invoiced_quantity_for_source(
                            source_line,
                            exclude_invoice=invoice,
                        )
                        self._copy_source_discounts(
                            invoice_line,
                            source_discounts,
                            invoice_quantity=invoice_line.quantity,
                            source_quantity=source_line_qty,
                            already_invoiced_quantity=already_invoiced_qty,
                        )
                else:
                    self._validate_discount_values(
                        discounts_data,
                        quantity=invoice_line.quantity,
                        unit_price=invoice_line.unit_price,
                    )
                    self._apply_discounts_to_line(invoice_line, discounts_data)

                SalesLineDiscountService.apply_line_discounts_and_taxes(
                    line=invoice_line,
                    source_line=source_line,
                )

                if should_create_order:
                    inventory_item, inventory_unit_of_measure = (
                        resolve_manufacturing_output(
                            line_item_data["line_item"],
                            line_item_data["unit_of_measure"],
                        )
                    )
                    manufacturing_order_requests.append(
                        {
                            "bill_of_material": bill_of_material,
                            "inventory_item": inventory_item,
                            "unit_of_measure": inventory_unit_of_measure,
                            "quantity_to_produce": quantity_to_produce,
                            "description": manufacturing_order_description or "",
                        }
                    )

            invoice.compute_totals()

            invoice_customer = invoice.get_invoice_customer()
            if (
                invoice.invoice_payment_status in ["unpaid", "partially_paid"]
                and invoice_customer is not None
            ):
                invoice_customer.check_credit_limit(invoice.gross_total)

            if manufacturing_order_requests:
                self._bulk_create_manufacturing_orders(
                    invoice,
                    manufacturing_order_requests,
                )

            has_goods = any(
                item_data["line_item"].inventory_item.item_type == "GOODS"
                for item_data in line_items_data
            )
            invoice.goods_issued_note_status = (
                "not_issued" if has_goods else "not_required"
            )
            invoice.save(update_fields=["goods_issued_note_status"])

            if invoice.invoice_payment_status in ["paid", "partially_paid"]:
                invoice.intiate_payment(invoice_payment_cash_account)

                invoice.refresh_from_db()

            invoice.send_invoice_email()

        return invoice

    def _prepare_quantity_change_discounts(self, line, source_line, discounts):
        existing = {discount.pk: discount for discount in line.get_discounts()}
        if discounts is None:
            discounts = [
                {
                    "id": discount.pk,
                    "discount_type": discount.discount_type,
                    "discount_value": discount.discount_value,
                    "position": discount.position,
                    "description": discount.description,
                }
                for discount in existing.values()
            ]
        else:
            discounts = [dict(discount) for discount in discounts]

        source_ids = {
            discount.source_discount_id
            for discount in existing.values()
            if discount.source_discount_id
        }
        sources = {
            source.pk: source
            for source in SalesLineDiscount.objects.select_for_update()
            .filter(pk__in=source_ids)
            .order_by("pk")
        }
        already_invoiced_quantity = self._invoiced_quantity_for_source(
            source_line,
            exclude_invoice=line.invoice,
        )

        for submitted in discounts:
            current = existing.get(submitted.get("id"))
            if current is None or not current.source_discount_id:
                continue
            if (
                current.discount_type != SalesLineDiscountService.FIXED_TYPE
                or submitted["discount_type"] != current.discount_type
                or Decimal(str(submitted["discount_value"])) != current.discount_value
            ):
                continue

            source = sources[current.source_discount_id]
            if source.discount_type != SalesLineDiscountService.FIXED_TYPE:
                raise validation_error(
                    {
                        "discounts": [
                            "The source discount type has changed. Remove and reapply "
                            "this discount before changing the invoiced quantity."
                        ]
                    }
                )

            submitted["discount_value"] = (
                SalesLineDiscountService.allocate_source_discount(
                    source,
                    invoice_quantity=line.quantity,
                    source_quantity=source_line.quantity,
                    already_invoiced_quantity=already_invoiced_quantity,
                    exclude_discount=current,
                )
            )

        return discounts

    def _sync_line_items(self, instance, line_items_data):
        existing = {
            line.pk: line
            for line in instance.line_items.filter(
                deleted_at__isnull=True
            ).select_for_update()
        }
        retained_ids = set()
        used_order_line_ids = {
            line.source_purchase_order_line_id
            for line in existing.values()
            if line.source_purchase_order_line_id
        }
        used_quotation_line_ids = {
            line.source_quotation_line_id
            for line in existing.values()
            if line.source_quotation_line_id
        }
        for item_data in line_items_data:
            line_data = item_data.copy()
            submitted_discounts = line_data.pop("discounts", None)
            discounts_data = (
                self._prepare_discounts(submitted_discounts)
                if submitted_discounts is not None
                else None
            )
            submitted_line = line_data.pop("invoice_line_item_uuid", None)
            for field in (
                "should_auto_create_manufacturing_order",
                "bill_of_material_to_be_used",
                "qty_to_be_manufactured",
                "manufacturing_order_description",
            ):
                line_data.pop(field, None)
            invoice_line = None
            if submitted_line is not None:
                invoice_line = existing.get(submitted_line.pk)
                if invoice_line is None:
                    raise validation_error(
                        "A submitted line no longer belongs to this invoice. "
                        "Reload and try again."
                    )
            changed = invoice_line is None or any(
                getattr(invoice_line, field) != value
                for field, value in line_data.items()
            )
            if invoice_line is not None and discounts_data is not None:
                if not self._discounts_match(invoice_line, discounts_data):
                    changed = True
            if invoice_line is not None and not changed:
                retained_ids.add(invoice_line.pk)
                continue
            if invoice_line is not None and (
                invoice_line.quantity_issued or invoice_line.goods_issue_lines.exists()
            ):
                raise validation_error(
                    "A line linked to goods issuance cannot be changed."
                )
            previous_quantity = (
                invoice_line.quantity if invoice_line is not None else None
            )
            same_source_item = (
                invoice_line is not None
                and invoice_line.line_item_id == line_data["line_item"].pk
                and invoice_line.unit_of_measure_id == line_data["unit_of_measure"].pk
            )
            if same_source_item:
                source_order_line = invoice_line.source_purchase_order_line
                source_quotation_line = invoice_line.source_quotation_line
                source_line = source_order_line or source_quotation_line
            else:
                source_order_line, source_quotation_line, source_line = (
                    self._resolve_source_line(
                        purchase_order=instance.purchase_order,
                        quotation=instance.quotation,
                        item_data=line_data,
                        used_order_line_ids=used_order_line_ids,
                        used_quotation_line_ids=used_quotation_line_ids,
                    )
                )
            if source_line is not None:
                source_line = source_line.__class__.objects.select_for_update().get(
                    pk=source_line.pk
                )

            line_data["source_purchase_order_line"] = source_order_line
            line_data["source_quotation_line"] = source_quotation_line
            if invoice_line is None:
                invoice_line = InvoiceLineItem.objects.create(
                    invoice=instance, **line_data
                )
            else:
                for field, value in line_data.items():
                    setattr(invoice_line, field, value)
                invoice_line.save()
            retained_ids.add(invoice_line.pk)

            if source_line is not None:
                if previous_quantity is None:
                    source_discounts = list(
                        source_line.get_discounts().select_for_update()
                    )
                    if discounts_data is None or self._discounts_match_source(
                        discounts_data, source_discounts
                    ):
                        self._copy_source_discounts(
                            invoice_line,
                            source_discounts,
                            invoice_quantity=invoice_line.quantity,
                            source_quantity=source_line.quantity,
                            already_invoiced_quantity=self._invoiced_quantity_for_source(
                                source_line,
                                exclude_invoice=instance,
                            ),
                        )
                        discounts_data = None
                elif same_source_item and previous_quantity != invoice_line.quantity:
                    discounts_data = self._prepare_quantity_change_discounts(
                        invoice_line,
                        source_line,
                        discounts_data,
                    )

            if discounts_data is not None:
                self._validate_discount_values(
                    discounts_data,
                    quantity=invoice_line.quantity,
                    unit_price=invoice_line.unit_price,
                )
                self._apply_discounts_to_line(invoice_line, discounts_data)

            SalesLineDiscountService.apply_line_discounts_and_taxes(
                line=invoice_line, source_line=source_line
            )

        removed_ids = set(existing) - retained_ids
        for removed_id in removed_ids:
            removed_line = existing[removed_id]
            if removed_line.quantity_issued or removed_line.goods_issue_lines.exists():
                raise validation_error(
                    "A line linked to goods issuance cannot be removed."
                )
            for removed_discount in removed_line.discounts.filter(
                deleted_at__isnull=True
            ):
                self._release_discount_allocation(removed_discount)
        if removed_ids:
            instance.line_items.filter(pk__in=removed_ids).delete()

    @transaction.atomic
    def update(self, instance, validated_data):
        line_items_data = validated_data.pop("line_items", None)
        rate_was_provided = "exchange_rate" in validated_data
        rate_input = validated_data.pop("exchange_rate", None)
        previous_amount_due = instance.amount_due or Decimal("0.00")
        was_posted = instance.are_initial_journal_entries_made

        with db_transaction.atomic():
            for attr, value in validated_data.items():
                setattr(instance, attr, value)
            instance.save()

            if rate_was_provided:
                FxRateService.replace_document_snapshot(
                    source=instance,
                    institution=instance.get_institution(),
                    currency=instance.currency or instance.get_institution().currency,
                    rate_input=rate_input,
                )

            if line_items_data is not None:
                self._sync_line_items(instance, line_items_data)

            instance.compute_totals()

            invoice_customer = instance.get_invoice_customer()
            if (
                instance.invoice_payment_status in ["unpaid", "partially_paid"]
                and invoice_customer is not None
            ):
                net_new_exposure = instance.gross_total

                if was_posted:
                    net_new_exposure -= previous_amount_due

                if net_new_exposure > Decimal("0.00"):
                    invoice_customer.check_credit_limit(net_new_exposure)

            has_goods = instance.line_items.filter(
                deleted_at__isnull=True,
                line_item__inventory_item__item_type="GOODS",
            ).exists()
            if not has_goods:
                instance.goods_issued_note_status = "not_required"
            elif instance.goods_issued_note_status == "not_required":
                instance.goods_issued_note_status = "not_issued"
            instance.save(update_fields=["goods_issued_note_status"])

            instance.send_invoice_email()

        return instance

    def _bulk_create_manufacturing_orders(
        self,
        invoice: Invoice,
        order_requests: list[dict],
    ):
        from manufacturing.serializers import ManufacturingOrderSerializer

        customer = invoice.get_invoice_customer()

        payload = [
            {
                **(
                    {
                        "bill_of_material": str(
                            order_request["bill_of_material"].base_uuid
                        )
                    }
                    if order_request["bill_of_material"]
                    else {}
                ),
                "inventory_item": str(order_request["inventory_item"].base_uuid),
                "unit_of_measure": str(order_request["unit_of_measure"].base_uuid),
                "quantity_to_produce": order_request["quantity_to_produce"],
                "description": order_request.get("description") or "",
                "branch": str(invoice.branch.base_uuid),
                "content_type": ContentType.objects.get_for_model(Invoice).id,
                "content_object_uuid": str(invoice.base_uuid),
                **({"client": str(customer.base_uuid)} if customer else {}),
            }
            for order_request in order_requests
        ]

        serializer = ManufacturingOrderSerializer(
            data=payload,
            many=True,
            allow_empty=False,
            context=self.context,
        )
        serializer.is_valid(raise_exception=True)
        orders = serializer.save()

        request = self.context["request"]
        for order in orders:
            order.confirm_create(
                profile_institution=request.profile_institution,
                external_identity=request.external_identity,
            )


class CustomerSerializer(Base64FileFieldMixin, ContentTypeIdSerializerMixin):

    IMMUTABLE_FIELDS_ON_UPDATE = [
        "currency",
        "opening_balance",
        "opening_balance_received_date",
        "deposit_balance",
        "outstanding_recievables_balance",
        "opening_balance_account",
        "approval_status",
        "original_data",
    ]

    opening_balance_account = UUIDRelatedField(
        queryset=Account.objects.all(),
        required=False,
        allow_null=True,
    )

    default_account = UUIDRelatedField(
        queryset=Account.objects.all(),
        required=False,
        allow_null=True,
    )

    foreign_exchange_rate = ExchangeRateInputSerializer(
        required=False,
        allow_null=True,
        write_only=True,
    )

    approval_status = serializers.CharField(read_only=True)
    original_data = serializers.JSONField(read_only=True)

    base64_file_fields = ["profile_photo"]

    class Meta:
        model = Customer
        fields = "__all__"

        read_only_fields = [
            "institution",
            "deposit_balance",
            "outstanding_recievables_balance",
            "approval_status",
            "original_data",
        ]

    def _validate_customer_account(
        self,
        *,
        account,
        field_name,
        institution,
        customer_currency,
    ):
        if account is None:
            return

        if account.institution_id != institution.id:
            raise validation_error(
                f"The selected {field_name.replace('_', ' ')} does not belong "
                "to the current institution."
            )

        account_currency = account.currency or institution.currency

        if account_currency != customer_currency:
            raise validation_error(
                f"The selected {field_name.replace('_', ' ')} uses "
                f"{account_currency.code}, but the customer uses "
                f"{customer_currency.code}."
            )

    def validate(self, attrs):
        attrs = super().validate(attrs)

        if self.instance:
            for field in self.IMMUTABLE_FIELDS_ON_UPDATE:
                if field in attrs:
                    raise validation_error(
                        f"Customer {field.replace('_', ' ')} cannot be changed once set."
                    )

        request = self.context.get("request")
        institution = (
            self.instance.institution if self.instance else get_institution(request)
        )

        if not institution:
            raise validation_error("Institution not found in serializer context.")

        institution_currency = institution.currency
        if not institution_currency:
            raise validation_error(
                "The institution must have a base currency before customers can be created."
            )

        selected_currency = attrs.get(
            "currency",
            self.instance.currency if self.instance else None,
        )
        customer_currency = selected_currency or institution_currency

        if not self.instance and selected_currency is None:
            attrs["currency"] = institution_currency

        default_account = attrs.get(
            "default_account",
            self.instance.default_account if self.instance else None,
        )
        opening_balance_account = attrs.get(
            "opening_balance_account",
            self.instance.opening_balance_account if self.instance else None,
        )

        self._validate_customer_account(
            account=default_account,
            field_name="default_account",
            institution=institution,
            customer_currency=customer_currency,
        )
        self._validate_customer_account(
            account=opening_balance_account,
            field_name="opening_balance_account",
            institution=institution,
            customer_currency=customer_currency,
        )

        opening_balance = attrs.get(
            "opening_balance",
            self.instance.opening_balance if self.instance else Decimal("0"),
        )
        opening_balance = opening_balance or Decimal("0")

        opening_balance_received_date = attrs.get(
            "opening_balance_received_date",
            self.instance.opening_balance_received_date if self.instance else None,
        )

        if opening_balance != Decimal("0") and not opening_balance_received_date:
            raise validation_error(
                "You must specify the date for which this opening balance was created."
            )

        if self.instance is None:
            credit_limit = attrs.get("credit_limit")

            if (
                opening_balance > Decimal("0")
                and credit_limit is not None
                and opening_balance > credit_limit
            ):
                raise validation_error(
                    "Opening balance exceeds the specified credit limit. "
                    "The customer would immediately breach their credit limit."
                )

        foreign_exchange_rate = attrs.get("foreign_exchange_rate")

        uses_foreign_currency = customer_currency != institution_currency

        if uses_foreign_currency and opening_balance != Decimal("0"):
            supported_currency = institution.institution_supported_currencies.filter(
                currency=customer_currency,
                deleted_at__isnull=True,
            ).first()

            if not supported_currency:
                raise validation_error(
                    f"{customer_currency.code} is not supported by this institution."
                )

            if foreign_exchange_rate is None and (
                supported_currency.rate is None
                or supported_currency.rate <= Decimal("0")
            ):
                raise validation_error(
                    f"A valid exchange rate is required for {customer_currency.code}."
                )

        return attrs

    @transaction.atomic
    def create(self, validated_data):
        foreign_exchange_rate = validated_data.pop("foreign_exchange_rate", None)

        request = self.context.get("request")

        institution = get_institution(request)
        validated_data["institution"] = institution

        customer = Customer.objects.create(**validated_data)

        # ********************************START OF FOREIGN EXCHANGE******************************
        target_currency = customer.currency
        institution_base_currency = institution.currency

        should_create_foreign_exchange_instance = (
            True
            if (target_currency != institution_base_currency)
            and customer.opening_balance != 0
            else False
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
                source=customer,
                institution=institution,
                currency=target_currency,
                rate_input=foreign_exchange_rate,
            )

        # *************************************************** END OF FOREIGN EXCHANGE *********************************

        return customer

    def to_representation(self, instance):
        repr = super().to_representation(instance)

        repr["payment_term"] = (
            PaymentTermSerializer(instance.payment_term).data
            if instance.payment_term
            else None
        )

        if instance.currency:
            repr["currency"] = SystemCurrencySerializer(instance.currency).data
        else:
            repr["currency"] = None

        if instance.salesperson:
            repr["salesperson"] = {
                "id": instance.salesperson.id,
                "name": instance.salesperson.name,
                "base_uuid": instance.salesperson.base_uuid,
            }
        else:
            repr["salesperson"] = None

        return repr


class SalesPersonSerializer(ContentTypeIdSerializerMixin):
    class Meta:
        model = SalesPerson
        fields = "__all__"
        read_only_fields = [
            "id",
            "base_uuid",
            "created_at",
            "updated_at",
            "institution",
        ]

    def validate(self, data):
        if not self.context.get("institution"):
            raise validation_error("Institution not found in serializer context.")
        return data

    def create(self, validated_data):
        institution = self.context.get("institution")
        if not institution:
            raise validation_error("Institution not found in serializer context.")

        validated_data["institution"] = institution
        return super().create(validated_data)

    def update(self, instance, validated_data):
        validated_data.pop("institution", None)
        return super().update(instance, validated_data)


class SalesPersonBulkUploadSerializer(serializers.Serializer):
    name = serializers.CharField(required=True)
    email = serializers.EmailField(required=False, allow_blank=True, allow_null=True)
    contact = serializers.CharField(required=False, allow_blank=True, allow_null=True)
    address = serializers.CharField(required=False, allow_blank=True, allow_null=True)
    balance = serializers.DecimalField(
        max_digits=50,
        decimal_places=20,
        required=False,
        default=Decimal("0.00"),
    )

    def validate_name(self, value):
        if not value or not value.strip():
            raise validation_error("Name is required.")
        return value.strip()

    def validate_balance(self, value):
        if value is None:
            return Decimal("0.00")
        return value


class SalesPersonCommissionEntrySerializer(ContentTypeIdSerializerMixin):
    payment_account = UUIDRelatedField(
        queryset=Account.objects.all(),
        required=False,
        allow_null=True,
        write_only=True,
    )

    class Meta:
        model = SalesPersonCommissionEntry
        fields = "__all__"
        read_only_fields = ["invoice", "new_commission", "old_commission"]

    def to_representation(self, instance):
        repr = super().to_representation(instance)

        if instance.payment_account:
            repr["payment_account"] = {
                "id": instance.payment_account.id,
                "account_name": instance.payment_account.account_name,
                "base_uuid": instance.payment_account.base_uuid,
                "reference_code": (
                    instance.payment_account.reference_code
                    if hasattr(instance.payment_account, "reference_code")
                    else None
                ),
            }

        repr["invoice"] = {
            "id": instance.invoice.id,
            "base_uuid": instance.invoice.base_uuid,
            "reference_code": instance.invoice.reference_code,
        }
        return repr


class CustomerPaymentSerializer(ContentTypeIdSerializerMixin):
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
    customer = UUIDRelatedField(
        queryset=Customer.objects.all(),
        required=False,
        allow_null=True,
    )
    invoice = UUIDRelatedField(
        queryset=Invoice.objects.all(),
        required=False,
        allow_null=True,
    )
    branch = UUIDRelatedField(
        queryset=Branch.objects.all(),
        required=False,
        allow_null=True,
    )
    coa_cash_account = UUIDRelatedField(
        queryset=Account.objects.all(),
        required=False,
        allow_null=True,
    )
    general_journal_items = serializers.SerializerMethodField()

    class Meta:
        model = CustomerPayment
        fields = "__all__"
        read_only_fields = [
            "institution",
            "currency",
            "settlement_currency",
            "settlement_amount",
            "payment_status",
            "amount_reconciled",
            "remaining_balance",
            "originating_payment",
            "are_initial_journal_entries_made",
            "general_journal_items",
        ]

    def get_general_journal_items(self, obj):
        return get_general_journal_items_for_object(obj)

    def validate(self, attrs):
        customer = attrs.get(
            "customer",
            getattr(self.instance, "customer", None),
        )
        invoice = attrs.get(
            "invoice",
            getattr(self.instance, "invoice", None),
        )
        branch = attrs.get(
            "branch",
            getattr(self.instance, "branch", None),
        )
        coa_cash_account = attrs.get(
            "coa_cash_account",
            getattr(self.instance, "coa_cash_account", None),
        )
        amount = attrs.get(
            "amount",
            getattr(self.instance, "amount", None),
        )
        payment_exchange_rate = attrs.get("payment_exchange_rate")
        settlement_exchange_rate = attrs.get("settlement_exchange_rate")

        if bool(customer) == bool(invoice):
            raise validation_error(
                {
                    "payment_target": (
                        "Provide either a customer for a prepayment or an "
                        "invoice for an invoice payment, but not both."
                    )
                }
            )

        if amount is not None and amount <= Decimal("0"):
            raise validation_error(
                {"amount": "Payment amount must be greater than zero."}
            )

        if not coa_cash_account:
            raise validation_error(
                {"coa_cash_account": "A receiving cash or bank account is required."}
            )

        if customer:
            institution = customer.institution
        else:
            invoice_customer = invoice.get_invoice_customer()
            institution = (
                invoice_customer.institution
                if invoice_customer is not None
                else invoice.get_institution()
            )

        if branch and branch.institution_id != institution.id:
            raise validation_error(
                {
                    "branch": (
                        "The selected branch must belong to the payment institution."
                    )
                }
            )

        if coa_cash_account and coa_cash_account.institution_id != institution.id:
            raise validation_error(
                {
                    "coa_cash_account": (
                        "The selected cash account must belong to the "
                        "payment institution."
                    )
                }
            )

        if coa_cash_account:
            coa_cash_account.validate_account(
                expected_group_types={"asset"},
                expected_role_codes={"cash_account"},
            )

        payment_currency = coa_cash_account.get_account_currency()
        settlement_currency = (
            invoice.determine_rate_currency_used()[0]
            if invoice
            else customer.currency or institution.currency
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
                            "the customer balance uses the institution base currency."
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

        if settlement_amount <= Decimal("0"):
            raise validation_error(
                {"amount": "The converted settlement amount must be positive."}
            )

        if (
            invoice
            and invoice.get_invoice_customer() is None
            and settlement_amount > Decimal(str(invoice.amount_due))
        ):
            raise validation_error(
                {
                    "amount": (
                        "Overpayment is not allowed for an invoice "
                        "without a customer."
                    )
                }
            )

        attrs["institution"] = institution
        attrs["currency"] = payment_currency
        attrs["settlement_currency"] = settlement_currency
        attrs["settlement_amount"] = settlement_amount
        attrs["_payment_base_rate"] = payment_base_rate
        attrs["_settlement_to_payment_rate"] = settlement_to_payment_rate
        return attrs

    @transaction.atomic
    def create(self, validated_data):
        payment_exchange_rate = validated_data.pop(
            "payment_exchange_rate",
            None,
        )
        settlement_exchange_rate = validated_data.pop(
            "settlement_exchange_rate",
            None,
        )
        payment_base_rate = validated_data.pop("_payment_base_rate")
        settlement_to_payment_rate = validated_data.pop("_settlement_to_payment_rate")

        payment = CustomerPayment.objects.create(**validated_data)

        FxRateService.create_document_snapshot(
            source=payment,
            institution=payment.institution,
            currency=payment.currency,
            rate_input=payment_exchange_rate,
            supplied_rate=payment_base_rate,
        )
        FxRateService.create_pair_snapshot(
            source=payment,
            institution=payment.institution,
            from_currency=payment.settlement_currency,
            to_currency=payment.currency,
            rate_input=settlement_exchange_rate,
            supplied_rate=settlement_to_payment_rate,
        )

        settlement_base_rate = settlement_to_payment_rate * payment_base_rate
        if (
            payment.settlement_currency != payment.currency
            and payment.currency != payment.institution.currency
        ):
            FxRateService.create_pair_snapshot(
                source=payment,
                institution=payment.institution,
                from_currency=payment.settlement_currency,
                to_currency=payment.institution.currency,
                supplied_rate=settlement_base_rate,
            )

        return payment

    def to_representation(self, instance):
        representation = super().to_representation(instance)

        payment_currency, _ = instance.determine_rate_currency_used()
        settlement_currency, _ = instance.determine_settlement_rate_currency_used()

        representation["currency"] = SystemCurrencySerializer(payment_currency).data
        representation["settlement_currency"] = SystemCurrencySerializer(
            settlement_currency
        ).data
        representation["payment_exchange_rate"] = (
            FxRateService.get_document_rate_representation(
                source=instance,
                institution=instance.institution,
                currency=payment_currency,
            )
        )
        representation["settlement_exchange_rate"] = (
            FxRateService.get_pair_rate_representation(
                source=instance,
                from_currency=settlement_currency,
                to_currency=payment_currency,
            )
        )

        representation["customer"] = (
            {
                "id": instance.customer.id,
                "base_uuid": str(instance.customer.base_uuid),
                "reference_code": instance.customer.reference_code,
                "customer_name": instance.customer.customer_name,
            }
            if instance.customer
            else None
        )
        representation["invoice"] = (
            {
                "id": instance.invoice.id,
                "base_uuid": str(instance.invoice.base_uuid),
                "reference_code": instance.invoice.reference_code,
            }
            if instance.invoice
            else None
        )
        representation["branch"] = (
            {
                "id": instance.branch.id,
                "base_uuid": str(instance.branch.base_uuid),
                "reference_code": instance.branch.reference_code,
                "branch_name": instance.branch.branch_name,
            }
            if instance.branch
            else None
        )
        representation["coa_cash_account"] = (
            AccountSerializer(instance.coa_cash_account).data
            if instance.coa_cash_account
            else None
        )

        return representation


class RecurringInvoiceItemSerializer(serializers.ModelSerializer):
    line_item = UUIDRelatedField(
        queryset=InventoryItem.objects.all(),
        required=True,
        allow_null=False,
    )
    unit_of_measure = UUIDRelatedField(
        queryset=InventoryItemUnitOfMeasure.objects.all(),
        required=True,
        allow_null=False,
    )
    quantity = serializers.DecimalField(
        max_digits=50,
        decimal_places=20,
        min_value=Decimal("0.00000000000000000001"),
    )
    unit_cost = serializers.DecimalField(
        max_digits=50,
        decimal_places=20,
        min_value=Decimal("0"),
    )

    class Meta:
        model = RecurringInvoiceItem
        fields = [
            "base_uuid",
            "recurring_invoice",
            "line_item",
            "quantity",
            "unit_cost",
            "unit_of_measure",
        ]
        read_only_fields = ["base_uuid", "recurring_invoice"]

    def to_representation(self, instance):
        representation = super().to_representation(instance)
        representation["line_item"] = {
            "id": instance.line_item.id,
            "base_uuid": instance.line_item.base_uuid,
            "item_name": instance.line_item.item_name,
            "item_code": instance.line_item.reference_code,
        }
        representation["unit_of_measure"] = {
            "id": instance.unit_of_measure.id,
            "base_uuid": instance.unit_of_measure.base_uuid,
            "unit_name": instance.unit_of_measure.unit_of_measure.unit_name,
            "unit_abbreviation": (
                instance.unit_of_measure.unit_of_measure.unit_abbreviation
            ),
        }
        return representation

    def validate(self, attrs):
        attrs = super().validate(attrs)

        line_item = attrs.get(
            "line_item",
            getattr(self.instance, "line_item", None),
        )
        unit_of_measure = attrs.get(
            "unit_of_measure",
            getattr(self.instance, "unit_of_measure", None),
        )

        if (
            line_item
            and unit_of_measure
            and unit_of_measure.inventory_item_id != line_item.id
        ):
            raise validation_error(
                {
                    "unit_of_measure": (
                        "Unit of measure must belong to the selected inventory item."
                    )
                }
            )

        if self.instance and line_item:
            invoice_institution_id = (
                self.instance.recurring_invoice.customer.institution_id
            )

            if line_item.institution_id != invoice_institution_id:
                raise validation_error(
                    {
                        "line_item": (
                            "Inventory item and recurring invoice must belong "
                            "to the same institution."
                        )
                    }
                )

        return attrs

    def to_representation(self, instance):
        repr = super().to_representation(instance)

        if instance.line_item and instance.line_item:
            repr["line_item"] = {
                "id": instance.line_item.id,
                "item_name": instance.line_item.item_name,
                "reference_code": instance.line_item.reference_code,
                "base_uuid": instance.line_item.base_uuid,
            }
        else:
            repr["line_item"] = None

        uom = getattr(instance.unit_of_measure, "unit_of_measure", None)
        if uom:
            repr["unit_of_measure"] = {
                "id": instance.unit_of_measure.id,
                "base_uuid": str(instance.unit_of_measure.base_uuid),
                "unit_name": uom.unit_name,
            }
        else:
            repr["unit_of_measure"] = None

        return repr


class RecurringInvoiceScheduleSerializer(ContentTypeIdSerializerMixin):
    interval = serializers.IntegerField(min_value=1, required=False)
    days_of_week = serializers.ListField(
        child=serializers.IntegerField(min_value=0, max_value=6),
        required=False,
        allow_null=True,
    )
    days_of_month = serializers.ListField(
        child=serializers.IntegerField(min_value=1, max_value=31),
        required=False,
        allow_null=True,
    )
    weeks_of_month = serializers.ListField(
        child=serializers.IntegerField(min_value=1, max_value=4),
        required=False,
        allow_null=True,
    )
    months_of_year = serializers.ListField(
        child=serializers.IntegerField(min_value=1, max_value=12),
        required=False,
        allow_null=True,
    )

    class Meta:
        model = RecurringInvoiceSchedule
        fields = "__all__"
        read_only_fields = [
            "id",
            "base_uuid",
            "recurring_invoice",
            "created_at",
            "updated_at",
            "institution",
        ]

    def validate(self, attrs):
        attrs = super().validate(attrs)
        errors = {}

        for field_name in (
            "days_of_week",
            "days_of_month",
            "weeks_of_month",
            "months_of_year",
        ):
            values = attrs.get(
                field_name,
                getattr(self.instance, field_name, None),
            )

            if values and len(values) != len(set(values)):
                errors[field_name] = "Duplicate values are not allowed."

        if errors:
            raise validation_error(errors)

        return attrs


class RecurringInvoiceSerializer(ContentTypeIdSerializerMixin):
    branch = UUIDRelatedField(
        queryset=Branch.objects.all(),
        required=True,
        allow_null=False,
    )
    recurring_items = RecurringInvoiceItemSerializer(
        many=True,
        write_only=True,
        allow_empty=False,
    )
    schedule = RecurringInvoiceScheduleSerializer(required=False)

    customer = UUIDRelatedField(
        queryset=Customer.objects.all(),
        required=True,
        allow_null=False,
    )

    class Meta:
        model = RecurringInvoice
        fields = "__all__"
        read_only_fields = [
            "next_recurring_date",
        ]

    def validate(self, attrs):
        attrs = super().validate(attrs)

        instance = self.instance
        customer = attrs.get(
            "customer",
            getattr(instance, "customer", None),
        )
        branch = attrs.get(
            "branch",
            getattr(instance, "branch", None),
        )
        start_date = attrs.get(
            "start_date",
            getattr(instance, "start_date", None),
        )
        end_date = attrs.get(
            "end_date",
            getattr(instance, "end_date", None),
        )
        frequency = attrs.get(
            "recurring_frequency",
            getattr(instance, "recurring_frequency", None),
        )

        errors = {}

        if start_date and end_date and end_date < start_date:
            errors["end_date"] = "End date cannot be earlier than start date."

        if customer and branch and customer.institution_id != branch.institution_id:
            errors["branch"] = (
                "Branch and customer must belong to the same institution."
            )

        recurring_items = attrs.get("recurring_items")
        if recurring_items is None:
            recurring_items = list(instance.recurring_items.all()) if instance else []

        if not recurring_items:
            errors["recurring_items"] = (
                "At least one recurring invoice item is required."
            )
        elif customer:
            for index, item in enumerate(recurring_items):
                line_item = (
                    item.get("line_item") if isinstance(item, dict) else item.line_item
                )

                if line_item and line_item.institution_id != customer.institution_id:
                    errors["recurring_items"] = (
                        f"Item at position {index + 1} does not belong to "
                        "the customer's institution."
                    )
                    break

        schedule_data = attrs.get("schedule")
        existing_schedule = getattr(instance, "schedule", None) if instance else None

        def schedule_value(field_name):
            if schedule_data is not None and field_name in schedule_data:
                return schedule_data[field_name]
            return getattr(existing_schedule, field_name, None)

        schedule_rules = {
            "days_of_week": (
                RecurringInvoice.Frequency.DAILY,
                "Days of the week can only be set for daily recurring invoices.",
            ),
            "days_of_month": (
                RecurringInvoice.Frequency.MONTHLY,
                "Days of the month can only be set for monthly recurring invoices.",
            ),
            "weeks_of_month": (
                RecurringInvoice.Frequency.WEEKLY,
                "Weeks of the month can only be set for weekly recurring invoices.",
            ),
            "months_of_year": (
                RecurringInvoice.Frequency.MONTHLY,
                "Months of the year can only be set for monthly recurring invoices.",
            ),
        }

        schedule_errors = {}
        for field_name, (allowed_frequency, message) in schedule_rules.items():
            if schedule_value(field_name) and frequency != allowed_frequency:
                schedule_errors[field_name] = message

        if schedule_errors:
            errors["schedule"] = schedule_errors

        if errors:
            raise validation_error(errors)

        return attrs

    def to_representation(self, instance):
        repr = super().to_representation(instance)
        repr["customer"] = {
            "customer_name": instance.customer.customer_name,
            "id": instance.customer.id,
        }
        repr["recurring_items"] = RecurringInvoiceItemSerializer(
            instance.recurring_items.all(), many=True
        ).data
        if hasattr(instance, "schedule"):
            repr["schedule"] = RecurringInvoiceScheduleSerializer(
                instance.schedule
            ).data
        return repr

    @transaction.atomic
    def create(self, validated_data):
        recurring_items_data = validated_data.pop("recurring_items")
        schedule_data = validated_data.pop("schedule", None)

        recurring_invoice = super().create(validated_data)

        for item_data in recurring_items_data:
            RecurringInvoiceItem.objects.create(
                recurring_invoice=recurring_invoice, **item_data
            )

        if schedule_data:
            schedule = getattr(recurring_invoice, "schedule", None)
            if schedule:
                for attr, value in schedule_data.items():
                    setattr(schedule, attr, value)
                schedule.save()

        return recurring_invoice

    @transaction.atomic
    def update(self, instance, validated_data):
        recurring_items_data = validated_data.pop("recurring_items", None)
        schedule_data = validated_data.pop("schedule", None)

        instance = super().update(instance, validated_data)

        if recurring_items_data is not None:
            instance.recurring_items.all().delete()
            for item_data in recurring_items_data:
                RecurringInvoiceItem.objects.create(
                    recurring_invoice=instance, **item_data
                )

        if schedule_data:
            schedule = getattr(instance, "schedule", None)
            if not schedule:
                schedule = RecurringInvoiceSchedule.objects.create(
                    recurring_invoice=instance
                )

            for attr, value in schedule_data.items():
                setattr(schedule, attr, value)
            schedule.save()

        return instance


class CustomerBalanceAdjustmentSerializer(serializers.ModelSerializer):
    class Meta:
        model = CustomerBalanceAdjustment
        fields = "__all__"


class CreditDebitNotePriceEffectSerializer(serializers.ModelSerializer):
    class Meta:
        model = CreditDebitNotePriceEffect
        fields = ["amount_after", "amount_before", "credit_debit_note"]


class CreditDebitNoteLineItemSerializer(serializers.ModelSerializer):
    label = serializers.CharField(
        write_only=True,
        required=False,
        allow_blank=True,
        allow_null=True,
    )
    description = serializers.CharField(
        source="label",
        required=False,
        allow_blank=True,
        allow_null=True,
    )
    invoice_line_item = UUIDRelatedField(
        queryset=InvoiceLineItem.objects.all(),
        required=False,
    )
    bill_line_item = UUIDRelatedField(
        queryset=VendorBillLineItem.objects.all(),
        required=False,
    )

    account = UUIDRelatedField(
        queryset=Account.objects.all(),
        required=False,
    )

    class Meta:
        model = CreditDebitNoteLineItem
        fields = "__all__"
        read_only_fields = [
            "credit_debit_note",
            "amount_to_deduct",
        ]

    def to_representation(self, instance):
        repr = super().to_representation(instance)

        if instance.invoice_line_item and instance.invoice_line_item.line_item:
            repr["line_item"] = {
                "id": instance.invoice_line_item.line_item.id,
                "item_name": instance.invoice_line_item.line_item.inventory_item.item_name,
                "reference_code": instance.invoice_line_item.line_item.inventory_item.reference_code,
                "base_uuid": instance.invoice_line_item.line_item.base_uuid,
            }
        else:
            repr["line_item"] = None

        if instance.account:
            repr["account"] = {
                "id": instance.account.id,
                "account_name": instance.account.account_name,
                "reference_code": instance.account.reference_code,
                "base_uuid": instance.account.base_uuid,
            }
        else:
            repr["account"] = None

        return repr


class CreditDebitNoteSerializer(ContentTypeIdSerializerMixin):
    line_items = CreditDebitNoteLineItemSerializer(many=True, write_only=True)

    price_effects = CreditDebitNotePriceEffectSerializer(many=True, read_only=True)

    branch = serializers.PrimaryKeyRelatedField(read_only=True)

    coa_cash_account = UUIDRelatedField(
        queryset=Account.objects.all(),
        required=False,
        allow_null=True,
    )

    bill = UUIDRelatedField(
        queryset=VendorBill.objects.all(),
        required=False,
    )

    invoice = UUIDRelatedField(
        queryset=Invoice.objects.all(),
        required=False,
    )

    class Meta:
        model = CreditDebitNote
        fields = "__all__"
        read_only_fields = [
            "id",
            "base_uuid",
            "created_at",
            "updated_at",
            "is_deleted",
            "approvals",
            "approval_status",
            "created_by",
            "updated_by",
            "is_active",
            "deleted_at",
            "status",
            "reference_code",
            "general_journal_items",
            "amount",
        ]

    def validate(self, attrs):
        line_items_data = attrs.get("line_items") or []

        if not line_items_data:
            raise validation_error(
                {"line_items": "At least one line item is required."}
            )

        invoice = attrs.get(
            "invoice",
            getattr(self.instance, "invoice", None),
        )
        bill = attrs.get(
            "bill",
            getattr(self.instance, "bill", None),
        )
        note_type = attrs.get(
            "type",
            getattr(self.instance, "type", None),
        )
        falls_under = attrs.get(
            "falls_under",
            getattr(self.instance, "falls_under", None),
        )

        if note_type == "CREDIT" and falls_under == "SALES":
            if not invoice:
                raise validation_error(
                    {"invoice": "An invoice is required for a customer Credit Note."}
                )

            if not invoice.branch_id:
                raise validation_error(
                    {"invoice": "The selected invoice does not have a branch."}
                )

            attrs["branch"] = invoice.branch

        if note_type == "DEBIT" and falls_under == "PURCHASE":
            if not bill:
                raise validation_error(
                    {"bill": "A bill is required for a purchase Debit Note."}
                )

            if bill.branch_id:
                attrs["branch"] = bill.branch
        coa_cash_account = attrs.get(
            "coa_cash_account",
            getattr(self.instance, "coa_cash_account", None),
        )

        if invoice and note_type == "CREDIT" and falls_under == "SALES":
            from customers.services import CreditNoteLineAmountService

            note_amount = Decimal("0.00")

            for index, line in enumerate(line_items_data):
                invoice_line = line.get("invoice_line_item")

                if invoice_line:
                    returned_source = Q(
                        goods_issued_note_line__source_invoice_line=invoice_line,
                    )

                    if invoice_line.source_purchase_order_line_id:
                        returned_source |= Q(
                            goods_issued_note_line__source_purchase_order_line_id=(
                                invoice_line.source_purchase_order_line_id
                            ),
                        )

                    was_returned = ItemReturnItem.objects.filter(
                        returned_source,
                        item_return__return_status="APPROVED",
                        item_return__are_initial_journal_entries_made=True,
                        item_return__deleted_at__isnull=True,
                        deleted_at__isnull=True,
                    ).exists()

                    if was_returned:
                        raise validation_error(
                            {
                                "line_items": {
                                    index: {
                                        "invoice_line_item": (
                                            "This invoice item has already been returned "
                                            "and cannot be included in a new Credit Note."
                                        )
                                    }
                                }
                            }
                        )

                    quantity = line.get("quantity")
                    if not quantity:
                        raise validation_error(
                            {
                                "line_items": {
                                    index: {
                                        "quantity": (
                                            "Quantity is required for an invoice "
                                            "product line."
                                        )
                                    }
                                }
                            }
                        )

                    note_amount += (
                        Decimal(str(line.get("amount_on_general_adjustment")))
                        if line.get("amount_on_general_adjustment")
                        else (
                            CreditNoteLineAmountService.compute(
                                quantity=quantity,
                                invoice_line_item=invoice_line,
                            )
                        )
                    )
                else:
                    note_amount += Decimal(
                        str(line.get("amount_on_general_adjustment") or 0)
                    )

            cash_refund = max(
                note_amount - invoice.amount_due,
                Decimal("0.00"),
            )

            if cash_refund > Decimal("0.00") and not coa_cash_account:
                raise validation_error(
                    {
                        "coa_cash_account": (
                            "A cash or bank account is required for the paid "
                            "portion of this Credit Note."
                        )
                    }
                )

        return attrs

    def to_representation(self, instance):
        repr = super().to_representation(instance)

        repr["invoice"] = (
            InvoiceSerializer(instance.invoice).data if instance.invoice else None
        )

        from vendors.serializers import VendorBillSerializer

        repr["bill"] = (
            VendorBillSerializer(instance.bill).data if instance.bill else None
        )

        repr["coa_cash_account"] = (
            AccountSerializer(instance.coa_cash_account).data
            if instance.coa_cash_account
            else None
        )

        return repr

    def create(self, validated_data):
        line_items_data = validated_data.pop("line_items", [])

        with transaction.atomic():

            if line_items_data:
                validated_data["amount"] = Decimal("0.00")

                credit_debit_note = CreditDebitNote.objects.create(**validated_data)

                total_amount = Decimal("0.00")

                for item_data in line_items_data:
                    line = CreditDebitNoteLineItem.objects.create(
                        credit_debit_note=credit_debit_note, **item_data
                    )
                    total_amount += line.amount_to_deduct

                CreditDebitNote.objects.filter(pk=credit_debit_note.pk).update(
                    amount=total_amount
                )
                credit_debit_note.amount = total_amount

        return credit_debit_note


class ItemReturnItemSerializer(serializers.ModelSerializer):
    goods_issued_note_line = UUIDRelatedField(
        queryset=GoodsIssuedNoteLineItem.objects.undeleted(),
        required=True,
    )
    unit_of_measure = UUIDRelatedField(
        queryset=BranchInventoryItemUnitOfMeasure.objects.all(),
        required=False,
    )
    return_reason = UUIDRelatedField(
        queryset=InstitutionItemReturnReason.objects.all(),
        required=True,
    )

    class Meta:
        model = ItemReturnItem
        fields = "__all__"

        read_only_fields = [
            "item_return",
            "reference_code",
        ]

    def validate(self, attrs):
        source_line = attrs.get("goods_issued_note_line")
        if not source_line:
            raise validation_error(
                {
                    "goods_issued_note_line": (
                        "The exact originating GIN line is required."
                    )
                }
            )

        item = source_line.line_item
        unit_of_measure = source_line.unit_of_measure

        supplied_uom = attrs.get("unit_of_measure")
        if supplied_uom and supplied_uom.pk != unit_of_measure.pk:
            raise validation_error(
                {
                    "unit_of_measure": (
                        "The unit of measure must match the selected GIN line."
                    )
                }
            )

        attrs["unit_of_measure"] = unit_of_measure

        if not item.can_be_returned:
            raise validation_error({"item": "This item cannot be returned."})

        if item.inventory_item.item_type == "SERVICES":
            raise validation_error({"item": "Service items cannot be returned."})

        ItemReturnQuantityService.validate_requested_quantity(
            goods_issued_note_line=source_line,
            requested_quantity=attrs.get("quantity"),
            exclude_item_return=(
                self.instance.item_return if self.instance is not None else None
            ),
        )

        return attrs

    def to_representation(self, instance):
        repr = super().to_representation(instance)

        repr["return_reason"] = {
            "id": instance.return_reason.id,
            "base_uuid": str(instance.return_reason.base_uuid),
            "return_reason_name": instance.return_reason.return_reason_name,
        }

        repr["item"] = {
            "id": instance.item.id,
            "base_uuid": str(instance.item.base_uuid),
            "inventory_item": {
                "item_name": instance.item.inventory_item.item_name,
                "reference_code": instance.item.inventory_item.reference_code,
                "item_category": instance.item.inventory_item.item_category.name,
            },
        }

        repr["unit_of_measure"] = {
            "id": instance.unit_of_measure.id,
            "base_uuid": str(instance.unit_of_measure.base_uuid),
            "unit_name": instance.unit_of_measure.unit_of_measure.unit_name,
        }

        return repr


class ItemReturnSerializer(ContentTypeIdSerializerMixin):
    item_return_items = ItemReturnItemSerializer(
        many=True,
        write_only=True,
    )

    goods_issued_note = UUIDRelatedField(
        queryset=GoodsIssuedNote.objects.all(),
        required=True,
    )

    coa_cash_account = UUIDRelatedField(
        queryset=Account.objects.all(),
        required=False,
        allow_null=True,
    )

    class Meta:
        model = ItemReturn
        fields = "__all__"
        read_only_fields = [
            "return_status",
            "are_initial_journal_entries_made",
            "institution",
        ]

    def to_representation(self, instance):
        repr = super().to_representation(instance)

        repr["goods_issued_note"] = {
            "reference_code": instance.goods_issued_note.reference_code,
            "base_uuid": str(instance.goods_issued_note.base_uuid),
        }

        repr["coa_cash_account"] = (
            {
                "base_uuid": str(instance.coa_cash_account.base_uuid),
                "account_name": instance.coa_cash_account.account_name,
            }
            if instance.coa_cash_account
            else None
        )

        return repr

    def validate(self, attrs):
        request = self.context.get("request")
        if not request:
            raise validation_error("Request context is required for validation.")

        institution = get_institution(request)

        if not institution:
            raise validation_error("Institution not found.")

        item_return_items_data = attrs.get("item_return_items", [])

        gin = attrs.get("goods_issued_note") or getattr(
            self.instance, "goods_issued_note", None
        )

        if not gin:
            raise validation_error(
                {"goods_issued_note": "Goods issued note is required for item returns."}
            )

        if gin.status != "approved":
            raise validation_error(
                {
                    "goods_issued_note": "Item returns can only be created for approved goods issued notes."
                }
            )

        seen_gin_line_ids = set()

        return_type = attrs.get(
            "return_type", getattr(self.instance, "return_type", None)
        )
        coa_cash_account = attrs.get(
            "coa_cash_account",
            getattr(self.instance, "coa_cash_account", None),
        )

        if return_type != "CASH_REFUND" and coa_cash_account:
            raise validation_error(
                {
                    "coa_cash_account": (
                        "A cash or bank account can only be specified for cash refunds."
                    )
                }
            )

        if return_type == "CASH_REFUND" and not coa_cash_account:
            raise validation_error(
                {
                    "coa_cash_account": (
                        "A cash or bank account is required for a cash refund."
                    )
                }
            )

        if coa_cash_account:
            if coa_cash_account.institution_id != institution.id:
                raise validation_error(
                    {
                        "coa_cash_account": (
                            "The selected cash account must belong to the "
                            "Item Return institution."
                        )
                    }
                )

            coa_cash_account.validate_account(
                expected_group_types={"asset"},
                expected_role_codes={"cash_account"},
            )

        for item_data in item_return_items_data:
            source_line = item_data.get("goods_issued_note_line")

            if source_line.goods_issued_note_id != gin.pk:
                raise validation_error(
                    {
                        "item_return_items": (
                            f"GIN line {source_line.pk} does not belong to "
                            f"GIN {gin.reference_code}."
                        )
                    }
                )

            if source_line.pk in seen_gin_line_ids:
                raise validation_error(
                    {
                        "item_return_items": (
                            "A GIN line may appear only once in an Item Return."
                        )
                    }
                )

            seen_gin_line_ids.add(source_line.pk)

            ItemReturnQuantityService.validate_requested_quantity(
                goods_issued_note_line=source_line,
                requested_quantity=item_data.get("quantity"),
                exclude_item_return=self.instance,
            )

            if return_type == "CASH_REFUND":
                ItemReturnQuantityService.validate_cash_refund_quantity(
                    goods_issued_note_line=source_line,
                    requested_quantity=item_data.get("quantity"),
                    exclude_item_return=self.instance,
                )

        attrs["institution"] = institution

        return attrs

    def create(self, validated_data):

        with transaction.atomic():

            item_return_items_data = validated_data.pop("item_return_items", [])

            item_return = super().create(validated_data)

            for item_return_item in item_return_items_data:
                ItemReturnItem.objects.create(
                    item_return=item_return, **item_return_item
                )

            return item_return

    @transaction.atomic
    def update(self, instance, validated_data):
        item_return_items_data = validated_data.pop("item_return_items", [])

        instance.item_return_items.all().delete()

        instance = super().update(instance, validated_data)

        for item_return_item in item_return_items_data:
            ItemReturnItem.objects.create(item_return=instance, **item_return_item)

        return instance


class TaxCalculationPreviewSerializer(serializers.Serializer):
    base_uuid = serializers.UUIDField(required=False)
    amount = serializers.DecimalField(
        max_digits=50,
        decimal_places=20,
    )
    type = serializers.ChoiceField(
        choices=[("sales", "Sales"), ("purchase", "Purchase")],
        required=False,
    )
    applicable_taxes = GeneralTaxInputSerializer(many=True, required=False)

    def validate(self, data):
        base_uuid = data.get("base_uuid")
        tax_type = data.get("type")

        if bool(base_uuid) != bool(tax_type):
            raise validation_error("base_uuid and type must be provided together.")

        return data


class GoodsIssuedNoteLineItemSerializer(serializers.ModelSerializer):
    line_item = UUIDRelatedField(
        queryset=BranchInventoryItem.objects.filter(inventory_item__item_type="GOODS"),
        help_text="UUID of the inventory item.",
    )

    unit_of_measure = UUIDRelatedField(
        queryset=BranchInventoryItemUnitOfMeasure.objects.all(),
        required=True,
    )

    quantity_that_can_be_returned = serializers.SerializerMethodField()
    quantity_that_can_be_refunded = serializers.SerializerMethodField()

    class Meta:
        model = GoodsIssuedNoteLineItem
        fields = "__all__"
        read_only_fields = [
            "id",
            "base_uuid",
            "created_at",
            "updated_at",
            "goods_issued_note",
            "created_by",
            "updated_by",
            "is_deleted",
            "quantity_returned",
        ]

    def get_quantity_that_can_be_returned(self, obj):
        return ItemReturnQuantityService.returnable_quantity(
            goods_issued_note_line=obj,
        )

    def get_quantity_that_can_be_refunded(self, obj):
        return ItemReturnQuantityService.invoiced_returnable_quantity(
            goods_issued_note_line=obj,
        )

    def to_representation(self, instance):
        repr = super().to_representation(instance)

        repr["line_item"] = BranchInventoryItemSerializer(instance.line_item).data

        if instance.unit_of_measure:
            repr["unit_of_measure"] = {
                "id": instance.unit_of_measure.id,
                "unit_name": instance.unit_of_measure.unit_of_measure.unit_name,
                "unit_abbreviation": instance.unit_of_measure.unit_of_measure.unit_abbreviation,
                "is_base_unit_of_measure": instance.unit_of_measure.is_base_unit_of_measure,
                "base_uuid": instance.unit_of_measure.base_uuid,
            }

        return repr


class GoodsIssuedNoteSerializer(ContentTypeIdSerializerMixin):

    purchase_order = UUIDRelatedField(
        queryset=CustomerPurchaseOrder.objects.all(),
        required=False,
        allow_null=True,
    )

    invoice = UUIDRelatedField(
        queryset=Invoice.objects.all(),
        required=False,
        allow_null=True,
    )

    line_items = GoodsIssuedNoteLineItemSerializer(many=True, write_only=True)

    line_items_count = serializers.SerializerMethodField()

    class Meta:
        model = GoodsIssuedNote
        fields = "__all__"
        read_only_fields = [
            "status",
            "is_inventory_removed",
            "branch",
            "line_items_count",
        ]

    @staticmethod
    def _resolve_commercial_source_line(goods_issued_note, item_data):
        branch_item = item_data["line_item"]
        unit_of_measure = item_data["unit_of_measure"]

        if goods_issued_note.invoice_id:
            candidates = goods_issued_note.invoice.line_items.undeleted().filter(
                line_item=branch_item,
                unit_of_measure=unit_of_measure,
            )
            source_field = "source_invoice_line"
        else:
            candidates = goods_issued_note.purchase_order.line_items.undeleted().filter(
                line_item=branch_item,
                unit_of_measure=unit_of_measure,
            )
            source_field = "source_purchase_order_line"

        candidate_ids = list(candidates.values_list("pk", flat=True)[:2])

        if not candidate_ids:
            raise validation_error(
                "No matching commercial source line exists for the GIN item."
            )

        if len(candidate_ids) > 1:
            raise validation_error(
                "The GIN item maps to multiple commercial source lines. "
                "Exact source-line selection is required."
            )

        return source_field, candidates.get(pk=candidate_ids[0])

    def get_line_items_count(self, obj):
        return obj.line_items.count()

    def to_representation(self, instance):
        repr = super().to_representation(instance)
        repr["branch"] = SimpleBranchSerializer(instance.branch).data

        repr["purchase_order"] = (
            {
                "id": instance.purchase_order.id,
                "base_uuid": str(instance.purchase_order.base_uuid),
                "reference_code": instance.purchase_order.reference_code,
                "customer_name": (
                    instance.purchase_order.customer.customer_name
                    if instance.purchase_order.customer
                    else None
                ),
            }
            if instance.purchase_order
            else None
        )

        repr["invoice"] = (
            {
                "id": instance.invoice.id,
                "base_uuid": str(instance.invoice.base_uuid),
                "reference_code": instance.invoice.reference_code,
                "customer_name": (
                    instance.invoice.customer.customer_name
                    if instance.invoice.customer
                    else None
                ),
            }
            if instance.invoice
            else None
        )

        return repr

    def validate(self, data):
        institution = self.context.get("institution")
        line_items = data.get("line_items", [])
        is_automated = data.get("is_automated", False)

        if not line_items or not isinstance(line_items, list):
            raise validation_error(
                {"line_items": ["At least one line item is required."]}
            )

        branch_ids = {
            item["line_item"].branch_id for item in line_items if "line_item" in item
        }
        if not branch_ids:
            raise validation_error(
                {"line_items": ["Selected line items must have a valid branch."]}
            )
        if len(branch_ids) > 1:
            raise validation_error(
                {"line_items": ["All line items must belong to the same branch."]}
            )

        branch = line_items[0]["line_item"].branch
        data["branch"] = branch

        allow_oversell = getattr(branch, "allow_sales_out_of_stock", False)

        for item_data in line_items:
            branch_inventory_item = item_data.get("line_item")
            quantity_to_issue = item_data.get("quantity")
            unit_of_measure = item_data.get("unit_of_measure")

            if (
                branch_inventory_item
                and branch_inventory_item.inventory_item.item_type != "GOODS"
            ):
                raise validation_error(
                    {"line_items": ["Only GOODS items can be issued on a GIN."]}
                )

            if not branch_inventory_item or quantity_to_issue <= 0:
                continue

            qty_available = branch_inventory_item.get_effective_quantity_at_hand(
                unit_of_measure=unit_of_measure
            )

            if (
                qty_available is not None
                and qty_available < quantity_to_issue
                and not allow_oversell
            ):
                item_name = branch_inventory_item.inventory_item.item_name
                unit_name = (
                    unit_of_measure.unit_of_measure.unit_name
                    if unit_of_measure
                    else "units"
                )

                allow_breakdown = getattr(institution, "allow_unit_breakdown", False)

                if allow_breakdown:
                    raise validation_error(
                        f"Insufficient stock for '{item_name}'. "
                        f"Requested: {quantity_to_issue} {unit_name}, "
                        f"available: {qty_available} {unit_name} equivalent across all layers."
                    )
                else:
                    raise validation_error(
                        f"Insufficient stock for '{item_name}' in {unit_name}. "
                        f"Available: {qty_available} {unit_name}. "
                        "Unit breakdown not enabled for this institution."
                    )

        if (
            not is_automated
            and institution
            and institution.inventory_reduction_timing == "ON_INVOICE"
        ):
            raise validation_error(
                "Manual GIN creation is disabled when inventory reduction timing is "
                "ON_INVOICE. GINs are created automatically upon invoice approval."
            )

        return data

    def create(self, validated_data):
        line_items_data = validated_data.pop("line_items")

        with db_transaction.atomic():
            goods_issued_note = GoodsIssuedNote.objects.create(**validated_data)

            for item_data in line_items_data:
                source_field, source_line = self._resolve_commercial_source_line(
                    goods_issued_note,
                    item_data,
                )
                GoodsIssuedNoteLineItem.objects.create(
                    goods_issued_note=goods_issued_note,
                    **item_data,
                    **{source_field: source_line},
                )

        return goods_issued_note

    def update(self, instance, validated_data):
        line_items_data = validated_data.pop("line_items", None)

        if instance.status != "draft":
            raise validation_error("Only GINs in draft status can be modified.")

        with db_transaction.atomic():
            for attr, value in validated_data.items():
                setattr(instance, attr, value)
            instance.save()

            if line_items_data is not None:
                existing_items = {
                    str(item.line_item.base_uuid): item
                    for item in instance.line_items.filter(deleted_at__isnull=True)
                }

                incoming_uuids = set()

                for item_data in line_items_data:
                    branch_item = item_data.get("line_item")

                    if not branch_item:
                        raise validation_error("Line item is required.")

                    item_uuid = str(branch_item.base_uuid)

                    if item_uuid not in existing_items:
                        raise validation_error(
                            f"Line item with UUID {item_uuid} does not exist on this GIN."
                        )

                    incoming_uuids.add(item_uuid)

                    existing_item = existing_items[item_uuid]

                    existing_item.unit_of_measure = item_data.get("unit_of_measure")
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


class ReconcileCustomerPrepaymentsSerializer(serializers.Serializer):
    prepayment_uuids = serializers.ListField(
        child=serializers.UUIDField(),
        min_length=1,
        help_text="List of customer prepayment base UUIDs to apply.",
    )
    invoice_uuids = serializers.ListField(
        child=serializers.UUIDField(),
        min_length=1,
        help_text="List of invoice base UUIDs to allocate prepayments against.",
    )


class DepositAllocationSerializer(serializers.ModelSerializer):
    class Meta:
        model = CustomerDepositAllocation
        fields = "__all__"

    def to_representation(self, instance):
        repr = super().to_representation(instance)

        if instance.prepayment:
            repr["prepayment"] = {
                "id": instance.prepayment.id,
                "base_uuid": str(instance.prepayment.base_uuid),
                "reference_code": instance.prepayment.reference_code,
            }
        else:
            repr["prepayment"] = None

        repr["invoice"] = {
            "id": instance.invoice.id,
            "base_uuid": str(instance.invoice.base_uuid),
            "reference_code": instance.invoice.reference_code,
        }

        return repr


class DemandNoticeSerializer(serializers.Serializer):
    invoice_uuids = serializers.ListField(
        child=serializers.UUIDField(),
        required=True,
    )

    def validate(self, attrs):
        request = self.context["request"]
        institution = get_institution(request)

        invoice_uuids = attrs.get("invoice_uuids")

        service = DemandNoticeService(institution)

        try:
            customer, invoices = service.get_validated_customer_and_invoices(
                invoice_uuids
            )

        except ValueError as e:
            raise validation_error(str(e))

        attrs["customer"] = customer
        attrs["invoices"] = invoices

        return attrs
