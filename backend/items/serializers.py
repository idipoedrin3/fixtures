from decimal import Decimal

import attrs
from django.core.exceptions import ValidationError as DjangoValidationError
from rest_framework import serializers
from utilities.file_utils import Base64FileFieldMixin
from vendors.models import Vendor
from utilities.helpers import UUIDRelatedField, get_institution, validation_error
from transactions.utils import get_general_journal_items_for_object
from institution.serializers import BranchSerializer
from users.serializers import CustomUserSerializer
from .models import (
    InventoryItemImage,
    ItemCategory,
    InventoryItem,
    FiscalYear,
    ItemUnitOfMeasure,
    StockMovementLog,
    StockToBranchAllocationProduct,
    StockToBranchAllocation,
    InventoryItemPriceChange,
    InventoryItemStockLayer,
    BranchInventoryItemStockLayer,
    BranchInventoryItemPriceChange,
    InventoryItemUnitOfMeasure,
    BranchInventoryItemUnitOfMeasure,
    BranchToBranchStockMovement,
    BranchToBranchStockMovementItem,
    ItemVendorUnitPrice,
    ItemVendor,
    WriteOff,
    InventoryItemWriteOffLineItem,
    BranchInventorytemWriteOffLineItem,
)
from approval.serializers import BaseApprovableSerializer, BaseUnApprovableSerializer
from institution.models import Branch
from items.models import BranchInventoryItem
from django.db import transaction
from system.serializers import (
    SystemStockValuationMethodSerializer,
    SystemStockMovementStrategySerializer,
)
from taxation.models import Tax
from approval.serializers import BaseApprovableSerializer
from items.models import (
    InventoryItem,
    InventoryItemUnitOfMeasure,
    BranchInventoryItem,
    BranchInventoryItemUnitOfMeasure,
)
from accounts.models import Account
from institution.models import Institution, Branch
from django.utils import timezone
from datetime import datetime, date
from django.db.models import Sum


class SimpleInventoryItemSerializer(serializers.ModelSerializer):
    class Meta:
        model = InventoryItem
        fields = [
            "base_uuid",
            "reference_code",
            "item_name",
            "item_type",
            "item_category",
            "reorder_point",
        ]
        read_only_fields = fields

    def to_representation(self, instance):
        repr = super().to_representation(instance)

        repr["item_category"] = {
            "id": instance.item_category.id,
            "base_uuid": instance.item_category.base_uuid,
            "name": instance.item_category.name,
            "description": instance.item_category.description,
        }

        return repr


class BranchInventoryItemSerializer(BaseApprovableSerializer):
    quantity = serializers.SerializerMethodField()

    class Meta:
        model = BranchInventoryItem
        fields = "__all__"

    def get_quantity(self, obj):
        return obj.get_quantity_at_hand()

    def to_representation(self, instance):
        repr = super().to_representation(instance)
        repr["branch"] = {
            "base_uuid": instance.branch.base_uuid,
            "branch_name": instance.branch.branch_name,
            "allow_sales_out_of_stock": instance.branch.allow_sales_out_of_stock,
        }
        repr["inventory_item"] = SimpleInventoryItemSerializer(
            instance.inventory_item
        ).data

        image = (
            instance.inventory_item.images.filter(deleted_at__isnull=True)
            .order_by("-is_default", "-created_at")
            .first()
        )

        repr["inventory_item"]["default_image"] = (
            InventoryItemImageSerializer(
                image,
                context=self.context,
            ).data
            if image
            else None
        )

        units_qs = instance.units.filter(deleted_at__isnull=True)
        repr["branch_inventory_item_units_of_measure"] = [
            {
                "selling_price": unit.selling_price,
                "is_base_unit_of_measure": unit.is_base_unit_of_measure,
                "unit_of_measure": {
                    "id": unit.unit_of_measure.id,
                    "unit_name": unit.unit_of_measure.unit_name,
                    "unit_abbreviation": unit.unit_of_measure.unit_abbreviation,
                    "is_base_unit_of_measure": unit.is_base_unit_of_measure,
                },
                "base_uuid": unit.base_uuid,
            }
            for unit in units_qs
        ]

        return repr


class SingleBranchSellingPriceUpdateSerializer(serializers.Serializer):
    unit_of_measure = UUIDRelatedField(
        queryset=BranchInventoryItemUnitOfMeasure.objects.all(),
        required=True,
    )
    selling_price = serializers.DecimalField(max_digits=50, decimal_places=20)

    def validate(self, attrs):
        unit = attrs["unit_of_measure"]
        new_price = attrs["selling_price"]

        request = self.context.get("request")
        branch_inventory_item = self.context.get("branch_inventory_item")

        if not branch_inventory_item:
            raise validation_error("Branch inventory item is missing in context.")

        if unit.branch_inventory_item_id != branch_inventory_item.id:
            raise validation_error(
                "The selected unit of measure does not belong to this branch inventory item."
            )

        stock_layers = BranchInventoryItemStockLayer.objects.filter(
            branch_inventory_item=branch_inventory_item,
            unit_of_measure=unit.unit_of_measure,
            deleted_at__isnull=True,
        )

        for layer in stock_layers:
            if new_price < layer.unit_cost:
                raise validation_error(
                    f"Selling price ({new_price}) cannot be less than stock cost ({layer.unit_cost})."
                )

        try:
            inventory_uom = InventoryItemUnitOfMeasure.objects.get(
                inventory_item=branch_inventory_item.inventory_item,
                unit_of_measure=unit.unit_of_measure,
                deleted_at__isnull=True,
            )
        except InventoryItemUnitOfMeasure.DoesNotExist:
            raise validation_error(
                "Base inventory unit of measure not found for comparison."
            )

        if new_price < inventory_uom.selling_price:
            raise validation_error(
                f"Selling price ({new_price}) cannot be less than institution selling price ({inventory_uom.selling_price})."
            )

        return attrs


class BranchSellingPriceUpdateSerializer(serializers.Serializer):
    price_changes = SingleBranchSellingPriceUpdateSerializer(
        many=True,
        required=False,
    )
    can_be_returned = serializers.BooleanField(required=False)

    def validate(self, attrs):
        price_changes = attrs.get("price_changes", [])

        if not price_changes and "can_be_returned" not in attrs:
            raise validation_error(
                "Provide at least one price change or the return setting."
            )

        if "can_be_returned" in attrs:
            branch_inventory_item = self.context.get("branch_inventory_item")

            if not branch_inventory_item:
                raise validation_error("Branch inventory item is missing in context.")

            original_value = branch_inventory_item.can_be_returned
            branch_inventory_item.can_be_returned = attrs["can_be_returned"]

            try:
                branch_inventory_item.clean()
            except DjangoValidationError as exc:
                raise validation_error(
                    getattr(exc, "message_dict", None) or exc.messages
                )
            finally:
                branch_inventory_item.can_be_returned = original_value

        return attrs

    def save(self, **kwargs):
        branch_inventory_item = self.context.get("branch_inventory_item")

        if not branch_inventory_item:
            raise validation_error("Branch inventory item context is required.")

        price_changes = self.validated_data.get("price_changes", [])

        results = []

        with transaction.atomic():
            if "can_be_returned" in self.validated_data:
                branch_inventory_item.can_be_returned = self.validated_data[
                    "can_be_returned"
                ]
                branch_inventory_item.save(
                    update_fields=[
                        "can_be_returned",
                        "updated_at",
                    ]
                )

            for change in price_changes:
                uom = change["unit_of_measure"]
                new_price = change["selling_price"]

                old_price = uom.selling_price

                uom.selling_price = new_price
                uom.save()

                results.append(
                    {
                        "unit_of_measure": uom.base_uuid,
                        "old_price": old_price,
                        "new_price": new_price,
                    }
                )

        return results


class SingleInventoryItemPriceUpdateSerializer(serializers.Serializer):
    unit_of_measure = UUIDRelatedField(
        queryset=InventoryItemUnitOfMeasure.objects.all(),
        required=True,
    )
    selling_price = serializers.DecimalField(max_digits=50, decimal_places=20)

    def validate(self, attrs):
        unit = attrs["unit_of_measure"]
        new_price = attrs["selling_price"]

        inventory_item = self.context.get("inventory_item")

        if inventory_item and unit.inventory_item_id != inventory_item.id:
            raise validation_error(
                "The selected unit of measure does not belong to this inventory item."
            )

        stock_layers = InventoryItemStockLayer.objects.filter(
            inventory_item=inventory_item,
            unit_of_measure=unit.unit_of_measure,
            deleted_at__isnull=True,
        )

        if stock_layers.exists():

            if new_price < stock_layers.unit_cost:
                raise validation_error(
                    f"Selling price ({new_price}) cannot be less than stock cost ({stock_layers.unit_cost})."
                )

        return attrs


class InventoryItemPriceUpdateSerializer(serializers.Serializer):
    price_changes = SingleInventoryItemPriceUpdateSerializer(many=True, required=True)

    def save(self, **kwargs):
        price_changes = self.validated_data.get("price_changes", [])
        results = []

        with transaction.atomic():
            for change in price_changes:
                uom = change["unit_of_measure"]
                new_price = change["selling_price"]
                old_price = uom.selling_price

                uom.selling_price = new_price
                uom.save()

                results.append(
                    {
                        "unit_of_measure": uom.base_uuid,
                        "old_price": old_price,
                        "new_price": new_price,
                        "unit_name": uom.unit_of_measure.unit_name,
                    }
                )
        return results


class NestedBranchInventoryItemSerializer(serializers.ModelSerializer):
    class Meta:
        model = BranchInventoryItem
        fields = [
            "id",
            "branch",
            "quantity",
            "selling_price",
            "inventory_item",
        ]
        read_only_fields = fields


class SimpleItemCategorySerializer(serializers.ModelSerializer):
    class Meta:
        model = ItemCategory
        fields = [
            "id",
            "base_uuid",
            "reference_code",
            "name",
        ]

    def to_representation(self, instance):
        from accounts.serializers import AccountMiniSerializer

        repr = super().to_representation(instance)

        repr["expense_account"] = (
            AccountMiniSerializer(instance.expense_account).data
            if instance.expense_account
            else None
        )
        repr["revenue_account"] = (
            AccountMiniSerializer(instance.revenue_account).data
            if instance.revenue_account
            else None
        )
        repr["inventory_account"] = (
            AccountMiniSerializer(instance.inventory_account).data
            if instance.inventory_account
            else None
        )
        return repr


class ItemCategorySerializer(BaseApprovableSerializer):
    expense_account = UUIDRelatedField(
        queryset=Account.objects.all(),
        required=False,
        allow_null=True,
    )
    revenue_account = UUIDRelatedField(
        queryset=Account.objects.all(),
        required=False,
        allow_null=True,
    )
    inventory_account = UUIDRelatedField(
        queryset=Account.objects.all(),
        required=False,
        allow_null=True,
    )

    class Meta:
        model = ItemCategory
        fields = "__all__"
        read_only_fields = [
            "institution",
        ]

    def validate(self, data):
        request = self.context.get("request")
        data["institution"] = get_institution(request)
        return data

    def to_representation(self, instance):
        from accounts.serializers import AccountMiniSerializer

        repr = super().to_representation(instance)

        repr["expense_account"] = (
            AccountMiniSerializer(instance.expense_account).data
            if instance.expense_account
            else None
        )
        repr["revenue_account"] = (
            AccountMiniSerializer(instance.revenue_account).data
            if instance.revenue_account
            else None
        )
        repr["inventory_account"] = (
            AccountMiniSerializer(instance.inventory_account).data
            if instance.inventory_account
            else None
        )
        return repr


class BulkItemCategoryUploadSerializer(ItemCategorySerializer):
    expense_account = serializers.CharField(
        required=False, allow_null=True, allow_blank=True
    )
    revenue_account = serializers.CharField(
        required=False, allow_null=True, allow_blank=True
    )
    inventory_account = serializers.CharField(
        required=False, allow_null=True, allow_blank=True
    )


class InventoryItemStockLayerInputSerializer(serializers.Serializer):
    unit_of_measure = UUIDRelatedField(
        queryset=ItemUnitOfMeasure.objects.all(),
        required=True,
    )
    quantity_remaining = serializers.IntegerField(required=True)
    unit_cost = serializers.DecimalField(
        max_digits=50, decimal_places=20, required=True
    )

    def validate_unit_cost(self, value):
        if value <= 0:
            raise serializers.ValidationError(
                "Enter a unit cost greater than zero. "
                "For gifted stock, enter its assessed unit value."
            )
        return value

    recieved_date = serializers.DateField(required=False, allow_null=True)

    opening_balance_account = UUIDRelatedField(
        queryset=Account.objects.all(),
        required=False,
        write_only=True,
        allow_null=True,
    )

    location = UUIDRelatedField(
        queryset=Branch.objects.all(),
        required=False,
        write_only=True,
        allow_null=True,
        help_text="Branch location where the stock is stored. Required if this stock is on a specific branch.",
    )


class InventoryItemUnitOfMeasureInputSerializer(serializers.Serializer):
    unit_of_measure = UUIDRelatedField(
        queryset=ItemUnitOfMeasure.objects.all(),
        required=True,
    )
    selling_price = serializers.DecimalField(
        max_digits=50,
        decimal_places=20,
        required=True,
    )
    is_base_unit_of_measure = serializers.BooleanField(default=False)

    other_quantity = serializers.DecimalField(
        max_digits=50,
        decimal_places=20,
        required=False,
    )

    other_uom = UUIDRelatedField(
        queryset=ItemUnitOfMeasure.objects.all(),
        required=False,
    )

    def validate(self, attrs):
        is_base = attrs.get("is_base_unit_of_measure", False)
        other_uom = attrs.get("other_uom")
        other_qty = attrs.get("other_quantity")

        if is_base:
            if other_uom or other_qty:
                raise validation_error(
                    "Base unit must not define other_uom or other_quantity."
                )

            attrs["conversion_factor"] = Decimal("1")

            return attrs

        else:
            if other_uom is None or other_qty is None:
                raise validation_error(
                    "Non-base unit must define both other_uom and other_quantity."
                )

            attrs["conversion_factor"] = Decimal("0")

        return attrs


class ItemVendorSerializer(serializers.ModelSerializer):

    unit_prices = serializers.SerializerMethodField(read_only=True)

    class Meta:
        model = ItemVendor
        fields = "__all__"

    def get_unit_prices(self, obj):
        unit_prices = getattr(obj, "_active_unit_prices", None)
        if unit_prices is None:
            unit_prices = obj.unit_prices.filter(deleted_at__isnull=True)
        return ItemVendorUnitPriceSerializer(unit_prices, many=True).data

    def to_representation(self, instance):
        repr = super().to_representation(instance)

        from vendors.serializers import SimpleVendorSerializer

        if instance.vendor is not None:
            repr["vendor"] = SimpleVendorSerializer(instance.vendor).data

        return repr


class ItemVendorUnitPriceSerializer(serializers.ModelSerializer):
    class Meta:
        model = ItemVendorUnitPrice
        fields = "__all__"

    def to_representation(self, instance):
        repr = super().to_representation(instance)

        repr["unit_of_measure"] = (
            {
                "reference_code": instance.unit_of_measure.reference_code,
                "base_uuid": instance.unit_of_measure.base_uuid,
                "id": instance.unit_of_measure.id,
                "unit_of_measure": {
                    "reference_code": instance.unit_of_measure.unit_of_measure.reference_code,
                    "base_uuid": instance.unit_of_measure.unit_of_measure.base_uuid,
                    "unit_name": instance.unit_of_measure.unit_of_measure.unit_name,
                },
            }
            if instance.unit_of_measure
            else None
        )

        return repr


class ItemVendorUnitPriceInputSerializer(serializers.Serializer):
    unit_of_measure = UUIDRelatedField(
        queryset=ItemUnitOfMeasure.objects.all(),
        required=True,
    )
    price = serializers.DecimalField(
        max_digits=15,
        decimal_places=2,
        min_value=Decimal("0.01"),
        required=True,
    )
    minimum_order_qty = serializers.IntegerField(
        min_value=0,
        default=0,
        required=False,
    )


class ItemVendorInputSerializer(serializers.Serializer):
    unit_prices = ItemVendorUnitPriceInputSerializer(many=True, required=True)
    vendor = UUIDRelatedField(queryset=Vendor.objects.all(), required=True)


class ItemPreferredVendorWriteSerializer(serializers.Serializer):
    vendor = UUIDRelatedField(
        queryset=Vendor.objects.all(),
        required=False,
    )
    unit_prices = ItemVendorUnitPriceInputSerializer(
        many=True,
        allow_empty=False,
        required=True,
    )

    def validate(self, attrs):
        inventory_item = self.context["inventory_item"]
        vendor = attrs.get("vendor") or getattr(self.instance, "vendor", None)

        if vendor is None:
            raise validation_error({"vendor": "Vendor is required."})

        if vendor.institution_id != inventory_item.institution_id:
            raise validation_error(
                {"vendor": "Vendor does not belong to this institution."}
            )

        duplicate = ItemVendor.objects.active().filter(
            item=inventory_item,
            vendor=vendor,
        )
        if self.instance:
            duplicate = duplicate.exclude(pk=self.instance.pk)
        if duplicate.exists():
            raise validation_error(
                {"vendor": "Vendor is already preferred for this inventory item."}
            )

        inventory_units = {
            unit.unit_of_measure_id: unit
            for unit in InventoryItemUnitOfMeasure.objects.active().filter(
                inventory_item=inventory_item,
            )
        }

        submitted_units = set()
        for price_data in attrs["unit_prices"]:
            unit = price_data["unit_of_measure"]
            if unit.id not in inventory_units:
                raise validation_error(
                    {
                        "unit_prices": (
                            f"Unit '{unit.unit_name}' is not configured for this "
                            "inventory item."
                        )
                    }
                )
            if unit.id in submitted_units:
                raise validation_error(
                    {
                        "unit_prices": (
                            f"Unit '{unit.unit_name}' was submitted more than once."
                        )
                    }
                )
            submitted_units.add(unit.id)

        attrs["vendor"] = vendor
        return attrs

    def _sync_unit_prices(self, item_vendor, unit_prices):
        inventory_units = {
            unit.unit_of_measure_id: unit
            for unit in InventoryItemUnitOfMeasure.objects.filter(
                inventory_item=item_vendor.item,
                deleted_at__isnull=True,
            )
        }

        submitted_inventory_unit_ids = [
            inventory_units[price_data["unit_of_measure"].id].id
            for price_data in unit_prices
        ]

        ItemVendorUnitPrice.objects.filter(item_vendor=item_vendor).exclude(
            unit_of_measure_id__in=submitted_inventory_unit_ids
        ).delete()

        for price_data in unit_prices:
            inventory_unit = inventory_units[price_data["unit_of_measure"].id]
            ItemVendorUnitPrice.objects.update_or_create(
                item_vendor=item_vendor,
                unit_of_measure=inventory_unit,
                defaults={
                    "price": price_data["price"],
                    "minimum_order_qty": price_data.get("minimum_order_qty", 0),
                    "deleted_at": None,
                    "is_active": True,
                },
            )

    @transaction.atomic
    def create(self, validated_data):
        inventory_item = self.context["inventory_item"]
        vendor = validated_data["vendor"]
        unit_prices = validated_data["unit_prices"]

        item_vendor = ItemVendor.objects.filter(
            item=inventory_item,
            vendor=vendor,
        ).first()

        if item_vendor:
            item_vendor.deleted_at = None
            item_vendor.is_active = True
            item_vendor.save(update_fields=["deleted_at", "is_active"])
        else:
            item_vendor = ItemVendor.objects.create(
                item=inventory_item,
                vendor=vendor,
            )

        self._sync_unit_prices(item_vendor, unit_prices)
        return item_vendor

    @transaction.atomic
    def update(self, instance, validated_data):
        instance.vendor = validated_data["vendor"]
        instance.save(update_fields=["vendor", "updated_at"])
        self._sync_unit_prices(instance, validated_data["unit_prices"])
        return instance


class InventoryItemImageListSerializer(serializers.ListSerializer):
    def validate(self, data):
        default_images_by_item = {}
        context_inventory_item = self.context.get("inventory_item")

        for index, item in enumerate(data):
            if not item.get("is_default", False):
                continue

            inventory_item = item.get("inventory_item") or context_inventory_item
            if not inventory_item:
                continue

            item_id = inventory_item.id
            if item_id in default_images_by_item:
                raise validation_error(
                    "Only one default image can be created per inventory item."
                )

            default_images_by_item[item_id] = index

        return data


class InventoryItemImageSerializer(Base64FileFieldMixin, BaseUnApprovableSerializer):
    base64_file_fields = ["image"]

    class Meta:
        model = InventoryItemImage
        fields = [
            "id",
            "base_uuid",
            "image_name",
            "image",
            "inventory_item",
            "is_default",
            "created_at",
            "updated_at",
        ]

        read_only_fields = [
            "id",
            "base_uuid",
            "created_at",
            "updated_at",
            "inventory_item",
        ]

        list_serializer_class = InventoryItemImageListSerializer
        extra_kwargs = {
            "image": {"required": False},
        }

    def create(self, validated_data):
        return InventoryItemImage.objects.create(**validated_data)

    def validate(self, data):
        inventory_item = self.context.get("inventory_item") or data.get(
            "inventory_item"
        )
        is_default = data.get("is_default", False)

        if self.instance is None and not data.get("image"):
            raise validation_error("image is required.")

        if inventory_item and is_default:
            existing_default = (
                InventoryItemImage.objects.undeleted()
                .filter(
                    inventory_item=inventory_item,
                    is_default=True,
                )
                .exclude(id=getattr(self.instance, "id", None))
            )

            if existing_default.exists():
                raise validation_error(
                    "There is already a default image for this inventory item."
                )

        return data


class InventoryItemSerializer(Base64FileFieldMixin, BaseApprovableSerializer):
    IMMUTABLE_FIELDS_ON_UPDATE = [
        "stock_layers",
    ]

    preferred_vendors = ItemVendorInputSerializer(
        many=True, required=False, write_only=True
    )

    inventory_item_units_of_measure = InventoryItemUnitOfMeasureInputSerializer(
        many=True, write_only=True, required=False
    )

    stock_layers = InventoryItemStockLayerInputSerializer(
        many=True, write_only=True, required=False
    )

    quantity_on_hand = serializers.SerializerMethodField()

    sales_tax = UUIDRelatedField(
        queryset=Tax.objects.all(),
        required=False,
        allow_null=True,
    )
    purchase_tax = UUIDRelatedField(
        queryset=Tax.objects.all(),
        required=False,
        allow_null=True,
    )
    general_journal_items = serializers.SerializerMethodField()

    price_changes = SingleInventoryItemPriceUpdateSerializer(
        many=True, required=False, write_only=True
    )

    revenue_account = UUIDRelatedField(
        queryset=Account.objects.all(),
        required=False,
        allow_null=True,
        write_only=True,
    )

    expense_account = UUIDRelatedField(
        queryset=Account.objects.all(),
        required=False,
        allow_null=True,
        write_only=True,
    )

    inventory_account = UUIDRelatedField(
        queryset=Account.objects.all(),
        required=False,
        allow_null=True,
        write_only=True,
    )

    selling_branches = serializers.ListField(
        child=UUIDRelatedField(queryset=Branch.objects.all()),
        required=False,
        write_only=True,
    )

    base64_file_fields = []

    class Meta:
        model = InventoryItem
        fields = "__all__"
        read_only_fields = [
            "id",
            "base_uuid",
            "created_at",
            "updated_at",
            "are_initial_journal_entries_made",
            "institution",
            "quantity_on_hand",
            "buying_price",
            "selling_price",
            "general_journal_items",
        ]

    def get_general_journal_items(self, obj):
        return get_general_journal_items_for_object(obj)

    def get_quantity_on_hand(self, obj):
        stock_layers = getattr(obj, "_active_stock_layers", None)
        if stock_layers is not None:
            return sum(layer.quantity_remaining for layer in stock_layers)
        return obj.get_quantity_on_hand()

    def to_representation(self, instance):
        repr = super().to_representation(instance)

        item_vendors = getattr(instance, "_active_item_vendors", None)
        if item_vendors is None:
            item_vendors = instance.item_vendors.all()
        repr["preferred_vendors"] = ItemVendorSerializer(item_vendors, many=True).data

        repr["item_category"] = {
            "id": instance.item_category.id,
            "base_uuid": instance.item_category.base_uuid,
            "name": instance.item_category.name,
            "description": instance.item_category.description,
        }

        if instance.product_stock_valuation_method:
            repr["product_stock_valuation_method"] = (
                SystemStockValuationMethodSerializer(
                    instance.product_stock_valuation_method
                ).data
            )
        else:
            repr["product_stock_valuation_method"] = None

        if instance.product_stock_movement_strategy:
            repr["product_stock_movement_strategy"] = (
                SystemStockMovementStrategySerializer(
                    instance.product_stock_movement_strategy
                ).data
            )
        else:
            repr["product_stock_movement_strategy"] = None

        units_qs = getattr(instance, "_active_units", None)
        if units_qs is None:
            units_qs = instance.units.filter(deleted_at__isnull=True)

        repr["inventory_item_units_of_measure"] = [
            {
                "selling_price": unit.selling_price,
                "is_base_unit_of_measure": unit.is_base_unit_of_measure,
                "conversion_factor": unit.conversion_factor,
                "other_quantity": unit.other_quantity if unit.other_quantity else None,
                "other_uom": (
                    {
                        "id": unit.other_uom.id,
                        "unit_name": unit.other_uom.unit_name,
                        "unit_abbreviation": unit.other_uom.unit_abbreviation,
                        "base_uuid": unit.other_uom.base_uuid,
                    }
                    if unit.other_uom
                    else None
                ),
                "unit_of_measure": {
                    "id": unit.unit_of_measure.id,
                    "unit_name": unit.unit_of_measure.unit_name,
                    "unit_abbreviation": unit.unit_of_measure.unit_abbreviation,
                    "is_base_unit_of_measure": unit.is_base_unit_of_measure,
                    "base_uuid": unit.unit_of_measure.base_uuid,
                },
                "base_uuid": unit.base_uuid,
            }
            for unit in units_qs
        ]

        repr["inventory_account"] = (
            {
                "reference_code": instance.inventory_account.reference_code,
                "base_uuid": instance.inventory_account.base_uuid,
                "id": instance.inventory_account.id,
                "account_name": instance.inventory_account.account_name,
            }
            if instance.inventory_account
            else None
        )

        repr["revenue_account"] = (
            {
                "reference_code": instance.revenue_account.reference_code,
                "base_uuid": instance.revenue_account.base_uuid,
                "id": instance.revenue_account.id,
                "account_name": instance.revenue_account.account_name,
            }
            if instance.revenue_account
            else None
        )

        repr["sales_tax"] = (
            {
                "reference_code": instance.sales_tax.reference_code,
                "base_uuid": instance.sales_tax.base_uuid,
                "id": instance.sales_tax.id,
                "tax_name": instance.sales_tax.tax_name,
            }
            if instance.sales_tax
            else None
        )

        repr["purchase_tax"] = (
            {
                "reference_code": instance.purchase_tax.reference_code,
                "base_uuid": instance.purchase_tax.base_uuid,
                "id": instance.purchase_tax.id,
                "tax_name": instance.purchase_tax.tax_name,
            }
            if instance.purchase_tax
            else None
        )

        return repr

    def validate(self, data):
        if self.instance:
            for field in self.IMMUTABLE_FIELDS_ON_UPDATE:
                if field in data:
                    raise validation_error(
                        f"Inventory Item field '{field}' cannot be updated once set."
                    )

        preferred_vendors = data.get("preferred_vendors", [])
        inventory_units = data.get("inventory_item_units_of_measure", [])

        request = self.context.get("request")
        institution = get_institution(request)

        if not institution:
            raise validation_error("Institution in request context is missing.")

        reference_code = data.get("reference_code")
        item_name = data.get("item_name")

        if (
            InventoryItem.objects.filter(
                institution=institution, reference_code=reference_code
            )
            .exclude(id=self.instance.id if self.instance else None)
            .exists()
        ):
            raise validation_error("Item code already exists for this institution.")

        if (
            InventoryItem.objects.filter(institution=institution, item_name=item_name)
            .exclude(id=self.instance.id if self.instance else None)
            .exists()
        ):
            raise validation_error("Item name already exists for this institution.")

        inventory_units_of_measure_data = data.get(
            "inventory_item_units_of_measure", []
        )

        base_unit_count = sum(
            1
            for unit_data in inventory_units_of_measure_data
            if unit_data.get("is_base_unit_of_measure", False)
        )
        if base_unit_count > 1:
            raise validation_error(
                "Only one unit of measure can be set as the base unit."
            )

        submitted_uom_ids = {
            unit_data["unit_of_measure"].id
            for unit_data in inventory_units_of_measure_data
        }
        for unit_data in inventory_units_of_measure_data:
            other_uom = unit_data.get("other_uom")
            if other_uom and other_uom.id not in submitted_uom_ids:
                raise validation_error(
                    f"other_uom '{other_uom.unit_name}' must be one of the units "
                    f"defined for this inventory item."
                )
            if other_uom and other_uom.id == unit_data["unit_of_measure"].id:
                raise validation_error(
                    f"Unit '{unit_data['unit_of_measure'].unit_name}' cannot reference itself as other_uom."
                )

        inventory_uom_base_uuids = {
            unit_data["unit_of_measure"].base_uuid for unit_data in inventory_units
        }

        for vendor_data in preferred_vendors:
            for price_data in vendor_data.get("unit_prices", []):
                if (
                    price_data["unit_of_measure"].base_uuid
                    not in inventory_uom_base_uuids
                ):
                    raise validation_error(
                        "Vendor pricing unit must exist in inventory item units."
                    )

        return data

    @transaction.atomic
    def create(self, validated_data):
        from items.uom_sync import sync_inventory_item_uom_conversion_factors

        preferred_vendors_data = validated_data.pop("preferred_vendors", [])
        selling_branches_data = validated_data.pop("selling_branches", [])
        inventory_units_of_measure_data = validated_data.pop(
            "inventory_item_units_of_measure", []
        )
        stock_layers_data = validated_data.pop("stock_layers", [])

        request = self.context.get("request")
        institution = get_institution(request)
        if not institution:
            raise validation_error("Institution in request context is missing.")

        validated_data["institution"] = institution

        instance = InventoryItem.objects.create(**validated_data)

        if inventory_units_of_measure_data:
            units_to_create = [
                InventoryItemUnitOfMeasure(
                    inventory_item=instance,
                    unit_of_measure=unit_data["unit_of_measure"],
                    conversion_factor=unit_data["conversion_factor"],
                    selling_price=unit_data["selling_price"],
                    is_base_unit_of_measure=unit_data.get(
                        "is_base_unit_of_measure", False
                    ),
                    other_quantity=unit_data.get("other_quantity"),
                    other_uom=unit_data.get("other_uom"),
                )
                for unit_data in inventory_units_of_measure_data
            ]
            InventoryItemUnitOfMeasure.objects.bulk_create(units_to_create)

            item_id = instance.id

            def _sync_uoms_and_branches():
                sync_inventory_item_uom_conversion_factors(item_id)
                for unit in InventoryItemUnitOfMeasure.objects.filter(
                    inventory_item_id=item_id,
                    deleted_at__isnull=True,
                ):
                    unit.sync_to_branches()

            transaction.on_commit(_sync_uoms_and_branches)

        if selling_branches_data:
            branches = list(set(selling_branches_data))
        else:
            branches = Branch.objects.filter(institution=institution)

        instance.assign_inventory_items_to_all_branches(branches)

        if preferred_vendors_data:
            self._sync_preferred_vendors(instance, preferred_vendors_data)

        pending_allocations = []
        if stock_layers_data:
            for stock_layer_data in stock_layers_data:
                unit_of_measure = stock_layer_data["unit_of_measure"]
                quantity_remaining = int(stock_layer_data["quantity_remaining"])
                unit_cost = stock_layer_data["unit_cost"]
                received_date = stock_layer_data.get("recieved_date")
                opening_balance_account = stock_layer_data.get(
                    "opening_balance_account"
                )
                location = stock_layer_data.get("location")

                existing_layer = (
                    InventoryItemStockLayer.objects.select_for_update()
                    .filter(
                        inventory_item=instance,
                        unit_of_measure=unit_of_measure,
                        unit_cost=unit_cost,
                        deleted_at__isnull=True,
                    )
                    .first()
                )

                if existing_layer:
                    existing_layer.quantity_remaining += quantity_remaining
                    existing_layer.save(update_fields=["quantity_remaining"])
                else:
                    InventoryItemStockLayer.objects.create(
                        inventory_item=instance,
                        unit_of_measure=unit_of_measure,
                        quantity_remaining=quantity_remaining,
                        unit_cost=unit_cost,
                        recieved_date=received_date,
                        opening_balance_account=opening_balance_account,
                    )

                if location:
                    try:
                        inventory_uom = InventoryItemUnitOfMeasure.objects.get(
                            inventory_item=instance,
                            unit_of_measure=unit_of_measure,
                            deleted_at__isnull=True,
                        )
                    except InventoryItemUnitOfMeasure.DoesNotExist:
                        raise validation_error(
                            f"Unit of measure '{unit_of_measure.unit_name}' is not "
                            f"configured for item '{instance.item_name}'."
                        )

                    if received_date:
                        if isinstance(received_date, date) and not isinstance(
                            received_date, datetime
                        ):
                            allocation_date = timezone.make_aware(
                                datetime.combine(received_date, timezone.now().time())
                            )
                        else:
                            allocation_date = received_date
                    else:
                        allocation_date = timezone.now()

                    pending_allocations.append(
                        {
                            "branch_to": location.pk,
                            "allocation_date": allocation_date,
                            "items": [
                                {
                                    "item": instance.pk,
                                    "unit_of_measure": inventory_uom.base_uuid,
                                    "quantity": quantity_remaining,
                                }
                            ],
                        }
                    )

        if pending_allocations:

            def run_allocations():
                for allocation_data in pending_allocations:
                    serializer = StockToBranchAllocationSerializer(
                        data=allocation_data,
                        context=self.context,
                    )
                    serializer.is_valid(raise_exception=True)
                    allocation = serializer.save()
                    if hasattr(allocation, "confirm_create"):
                        allocation.confirm_create()

            transaction.on_commit(run_allocations)

        return instance

    @transaction.atomic
    def update(self, instance, validated_data):
        from items.uom_sync import sync_inventory_item_uom_conversion_factors

        inventory_units_of_measure_data = validated_data.pop(
            "inventory_item_units_of_measure", []
        )
        validated_data.pop("stock_layers", None)
        preferred_vendors_data = validated_data.pop("preferred_vendors", None)

        for attr, value in validated_data.items():
            setattr(instance, attr, value)
        instance.save()

        if inventory_units_of_measure_data:
            existing_units = InventoryItemUnitOfMeasure.objects.filter(
                inventory_item=instance
            )

            new_uuids = {
                u["unit_of_measure"].base_uuid for u in inventory_units_of_measure_data
            }

            existing_units.exclude(unit_of_measure__base_uuid__in=new_uuids).delete()

            to_create = []
            to_update = []

            existing_map = {u.unit_of_measure.base_uuid: u for u in existing_units}

            for unit_data in inventory_units_of_measure_data:
                uom_uuid = unit_data["unit_of_measure"].base_uuid

                defaults = {
                    "conversion_factor": unit_data["conversion_factor"],
                    "selling_price": unit_data["selling_price"],
                    "is_base_unit_of_measure": unit_data.get(
                        "is_base_unit_of_measure", False
                    ),
                }

                if uom_uuid in existing_map:
                    obj = existing_map[uom_uuid]
                    for key, val in defaults.items():
                        setattr(obj, key, val)
                    obj.other_quantity = unit_data.get("other_quantity")
                    obj.other_uom = unit_data.get("other_uom")
                    to_update.append(obj)
                else:
                    to_create.append(
                        InventoryItemUnitOfMeasure(
                            inventory_item=instance,
                            unit_of_measure=unit_data["unit_of_measure"],
                            other_quantity=unit_data.get("other_quantity"),
                            other_uom=unit_data.get("other_uom"),
                            **defaults,
                        )
                    )

            if to_update:
                InventoryItemUnitOfMeasure.objects.bulk_update(
                    to_update,
                    [
                        "conversion_factor",
                        "selling_price",
                        "is_base_unit_of_measure",
                        "other_quantity",
                        "other_uom",
                    ],
                )

            if to_create:
                InventoryItemUnitOfMeasure.objects.bulk_create(to_create)

            item_id = instance.id

            def _sync_uoms_and_branches():
                sync_inventory_item_uom_conversion_factors(item_id)
                for unit in InventoryItemUnitOfMeasure.objects.filter(
                    inventory_item_id=item_id,
                    deleted_at__isnull=True,
                ):
                    unit.sync_to_branches()

            transaction.on_commit(_sync_uoms_and_branches)

        if preferred_vendors_data is not None:
            self._sync_preferred_vendors(instance, preferred_vendors_data)

        return instance

    def _sync_preferred_vendors(self, instance, preferred_vendors_data):
        existing_item_vendors = ItemVendor.objects.filter(item=instance)

        incoming_vendor_ids = {
            vendor_data["vendor"].id for vendor_data in preferred_vendors_data
        }

        existing_item_vendors.exclude(vendor_id__in=incoming_vendor_ids).delete()

        inventory_units_map = {
            unit.unit_of_measure_id: unit
            for unit in InventoryItemUnitOfMeasure.objects.filter(
                inventory_item=instance,
                deleted_at__isnull=True,
            )
        }

        for vendor_data in preferred_vendors_data:
            unit_prices_data = vendor_data.get("unit_prices", [])

            item_vendor, _ = ItemVendor.objects.get_or_create(
                item=instance,
                vendor=vendor_data["vendor"],
            )

            existing_prices = ItemVendorUnitPrice.objects.filter(
                item_vendor=item_vendor
            )

            incoming_inventory_unit_ids = []

            for price_data in unit_prices_data:
                global_uom = price_data["unit_of_measure"]
                inventory_unit = inventory_units_map.get(global_uom.id)

                if not inventory_unit:
                    raise validation_error(
                        f"Unit {global_uom} is not configured for this inventory item."
                    )

                incoming_inventory_unit_ids.append(inventory_unit.id)

            existing_prices.exclude(
                unit_of_measure_id__in=incoming_inventory_unit_ids
            ).delete()

            for price_data in unit_prices_data:
                global_uom = price_data["unit_of_measure"]
                inventory_unit = inventory_units_map.get(global_uom.id)

                ItemVendorUnitPrice.objects.update_or_create(
                    item_vendor=item_vendor,
                    unit_of_measure=inventory_unit,
                    defaults={
                        "price": price_data["price"],
                        "minimum_order_qty": price_data.get("minimum_order_qty", 1),
                    },
                )


class FiscalYearSerializer(BaseApprovableSerializer):
    class Meta:
        model = FiscalYear
        fields = "__all__"
        read_only_fields = [
            "id",
            "base_uuid",
            "created_at",
            "updated_at",
            "institution",
        ]


class ItemUnitOfMeasureSerializer(BaseApprovableSerializer):
    class Meta:
        model = ItemUnitOfMeasure
        fields = "__all__"
        read_only_fields = [
            "id",
            "base_uuid",
            "created_at",
            "updated_at",
            "institution",
        ]

    def create(self, validated_data):
        request = self.context.get("request")

        validated_data["institution"] = get_institution(request)

        return super().create(validated_data)

    def update(self, instance, validated_data):
        instance = super().update(instance, validated_data)
        return instance


class CombinedStockMovementSerializer(serializers.Serializer):
    id = serializers.IntegerField()
    base_uuid = serializers.UUIDField()
    reference_code = serializers.CharField(allow_null=True)
    movement_type = serializers.ChoiceField(
        choices=["MAIN_TO_BRANCH", "BRANCH_TO_BRANCH"]
    )
    movement_date = serializers.DateTimeField()
    status = serializers.ChoiceField(choices=["PENDING", "ALLOCATED", "CANCELLED"])
    branch_from_name = serializers.CharField(allow_null=True)
    branch_to_name = serializers.CharField(allow_null=True)
    item_count = serializers.IntegerField()
    created_at = serializers.DateTimeField()


class StockToBranchAllocationProductSerializer(serializers.ModelSerializer):
    item = serializers.PrimaryKeyRelatedField(queryset=InventoryItem.objects.all())
    unit_of_measure = UUIDRelatedField(
        queryset=InventoryItemUnitOfMeasure.objects.all(),
        required=True,
    )

    class Meta:
        model = StockToBranchAllocationProduct
        fields = ["item", "quantity", "unit_of_measure"]

    def to_representation(self, instance):
        representation = super().to_representation(instance)
        representation["item"] = InventoryItemSerializer(instance.item).data

        if instance.unit_of_measure:
            representation["unit_of_measure"] = InventoryItemUnitOfMeasureSerializer(
                instance.unit_of_measure
            ).data
        else:
            representation["unit_of_measure"] = None
        return representation


class StockToBranchAllocationSerializer(BaseApprovableSerializer):
    items = StockToBranchAllocationProductSerializer(many=True, required=True)
    branch_to = serializers.PrimaryKeyRelatedField(queryset=Branch.objects.all())

    class Meta:
        model = StockToBranchAllocation
        fields = "__all__"
        read_only_fields = [
            "base_uuid",
            "alloc_status",
            "is_stock_moved",
        ]

    @transaction.atomic
    def create(self, validated_data):
        items_data = validated_data.pop("items", [])

        allocation = StockToBranchAllocation.objects.create(**validated_data)

        for item_data in items_data:
            StockToBranchAllocationProduct.objects.create(
                allocation=allocation,
                **item_data,
            )

        return allocation

    def to_representation(self, instance):
        representation = super().to_representation(instance)
        representation["branch_to"] = BranchSerializer(instance.branch_to).data
        representation["items"] = StockToBranchAllocationProductSerializer(
            instance.items.all(), many=True
        ).data
        representation["created_by"] = CustomUserSerializer(instance.created_by).data
        return representation


class ItemDistributionSerializer(serializers.Serializer):
    id = serializers.IntegerField()
    branch_name = serializers.CharField()
    branch_location = serializers.CharField(allow_null=True)
    quantity = serializers.DecimalField(max_digits=50, decimal_places=2)
    selling_price = serializers.DecimalField(
        max_digits=50, decimal_places=2, required=False, allow_null=True
    )
    base_uuid = serializers.UUIDField()


class ItemDistributionRequestSerializer(serializers.Serializer):
    inventory_item_id = serializers.UUIDField()
    branch_base_uuids = serializers.ListField(
        child=serializers.UUIDField(), required=True, allow_empty=False
    )


class InventoryItemPriceChangeSerializer(serializers.ModelSerializer):
    class Meta:
        model = InventoryItemPriceChange
        fields = [
            "id",
            "inventory_item",
            "type_of_price_change",
            "price_before",
            "price_after",
            "created_at",
        ]
        read_only_fields = ["id", "created_at"]


class InventoryItemStockLayerSerializer(serializers.ModelSerializer):

    general_journal_items = serializers.SerializerMethodField()

    class Meta:
        model = InventoryItemStockLayer
        fields = "__all__"

    def get_general_journal_items(self, obj):
        return get_general_journal_items_for_object(obj)

    def to_representation(self, instance):
        rep = super().to_representation(instance)

        if instance.unit_of_measure:
            rep["unit_of_measure"] = {
                "id": instance.unit_of_measure.id,
                "base_uuid": instance.unit_of_measure.base_uuid,
                "unit_name": instance.unit_of_measure.unit_name,
                "unit_abbreviation": instance.unit_of_measure.unit_abbreviation,
                "description": instance.unit_of_measure.description,
            }
        else:
            rep["unit_of_measure"] = None

        if instance.opening_balance_account:
            rep["opening_balance_account"] = {
                "id": instance.opening_balance_account.id,
                "base_uuid": instance.opening_balance_account.base_uuid,
                "account_name": instance.opening_balance_account.account_name,
                "reference_code": instance.opening_balance_account.reference_code,
            }
        else:
            rep["opening_balance_account"] = None

        return rep


class BranchInventoryItemStockLayerSerializer(serializers.ModelSerializer):
    class Meta:
        model = BranchInventoryItemStockLayer
        fields = "__all__"

    def to_representation(self, instance):
        rep = super().to_representation(instance)

        if instance.unit_of_measure:
            rep["unit_of_measure"] = {
                "id": instance.unit_of_measure.id,
                "base_uuid": instance.unit_of_measure.base_uuid,
                "unit_name": instance.unit_of_measure.unit_name,
                "unit_abbreviation": instance.unit_of_measure.unit_abbreviation,
                "description": instance.unit_of_measure.description,
            }
        else:
            rep["unit_of_measure"] = None

        return rep


class BranchStockLayerGroupSerializer(serializers.Serializer):
    branch = serializers.DictField()
    stock_layers = BranchInventoryItemStockLayerSerializer(many=True)


class InventoryItemAllStockLayersSerializer(serializers.Serializer):
    inventory_item = SimpleInventoryItemSerializer()
    warehouse = InventoryItemStockLayerSerializer(many=True)
    branches = BranchStockLayerGroupSerializer(many=True)


class BranchInventoryItemPriceChangeSerializer(serializers.ModelSerializer):
    branch_inventory_item = serializers.PrimaryKeyRelatedField(read_only=True)

    class Meta:
        model = BranchInventoryItemPriceChange
        fields = [
            "id",
            "branch_inventory_item",
            "price_before",
            "base_uuid",
            "price_after",
            "created_at",
            "updated_at",
        ]
        read_only_fields = ["id", "created_at", "updated_at", "base_uuid"]

    def to_representation(self, instance):
        rep = super().to_representation(instance)

        branch_inventory_item = instance.branch_inventory_item
        if branch_inventory_item:
            rep["branch_inventory_item"] = {
                "id": branch_inventory_item.id,
                "branch": (
                    {
                        "id": branch_inventory_item.branch.id,
                        "branch_name": branch_inventory_item.branch.branch_name,
                        "base_uuid": branch_inventory_item.branch.base_uuid,
                    }
                    if branch_inventory_item.branch
                    else None
                ),
                "inventory_item": (
                    {
                        "id": branch_inventory_item.inventory_item.id,
                        "item_name": branch_inventory_item.inventory_item.item_name,
                        "base_uuid": branch_inventory_item.inventory_item.base_uuid,
                    }
                    if branch_inventory_item.inventory_item
                    else None
                ),
            }

        return rep


class BranchInventoryItemUnitOfMeasureSerializer(serializers.ModelSerializer):
    branch_inventory_item = UUIDRelatedField(
        queryset=BranchInventoryItem.objects.all(),
        required=True,
    )

    unit_of_measure = UUIDRelatedField(
        queryset=ItemUnitOfMeasure.objects.all(),
        required=True,
    )

    class Meta:
        model = BranchInventoryItemUnitOfMeasure
        fields = "__all__"
        read_only_fields = [
            "created_by",
            "updated_by",
            "is_deleted",
            "is_active",
            "base_uuid",
            "external_base_uuid",
            "reference_code",
            "deleted_at",
        ]

    def validate(self, attrs):
        branch_inventory_item = attrs.get(
            "branch_inventory_item",
            getattr(self.instance, "branch_inventory_item", None),
        )
        unit_of_measure = attrs.get(
            "unit_of_measure",
            getattr(self.instance, "unit_of_measure", None),
        )
        is_base = attrs.get(
            "is_base_unit_of_measure",
            getattr(self.instance, "is_base_unit_of_measure", False),
        )

        if is_base:
            qs_base = BranchInventoryItemUnitOfMeasure.objects.filter(
                branch_inventory_item=branch_inventory_item,
                is_base_unit_of_measure=True,
                deleted_at__isnull=True,
            )
            if self.instance:
                qs_base = qs_base.exclude(id=self.instance.id)
            if qs_base.exists():
                raise validation_error(
                    "There is already a base unit of measure for this inventory item."
                )

        return attrs

    def create(self, validated_data):
        request = self.context.get("request")
        user = getattr(request, "user", None)

        if user and user.is_authenticated:
            validated_data["created_by"] = user
            validated_data["updated_by"] = user

        branch_inventory_item = validated_data["branch_inventory_item"]
        unit_of_measure = validated_data["unit_of_measure"]

        if BranchInventoryItemUnitOfMeasure.objects.filter(
            branch_inventory_item=branch_inventory_item,
            unit_of_measure=unit_of_measure,
            deleted_at__isnull=True,
        ).exists():
            raise validation_error(
                "This unit of measure already exists for the branch inventory item."
            )

        existing_soft_deleted = (
            BranchInventoryItemUnitOfMeasure.objects.filter(
                branch_inventory_item=branch_inventory_item,
                unit_of_measure=unit_of_measure,
                deleted_at__isnull=False,
            )
            .order_by("-deleted_at")
            .first()
        )

        if existing_soft_deleted:
            for key, value in validated_data.items():
                setattr(existing_soft_deleted, key, value)
            existing_soft_deleted.deleted_at = None
            if user and user.is_authenticated:
                existing_soft_deleted.updated_by = user
            existing_soft_deleted.save()
            return existing_soft_deleted

        return super().create(validated_data)

    def update(self, instance, validated_data):
        request = self.context.get("request")
        user = getattr(request, "user", None)

        if user and user.is_authenticated:
            validated_data["updated_by"] = user

        return super().update(instance, validated_data)

    def to_representation(self, instance):
        data = super().to_representation(instance)

        data["unit_of_measure"] = (
            ItemUnitOfMeasureSerializer(
                instance.unit_of_measure, context=self.context
            ).data
            if instance.unit_of_measure
            else None
        )

        return data


class InventoryItemUnitOfMeasureSerializer(serializers.ModelSerializer):

    inventory_item = UUIDRelatedField(
        queryset=InventoryItem.objects.all(),
        required=True,
    )

    unit_of_measure = UUIDRelatedField(
        queryset=ItemUnitOfMeasure.objects.all(),
        required=True,
    )

    cost_price = serializers.SerializerMethodField(read_only=True)
    margin = serializers.SerializerMethodField(read_only=True)
    markup = serializers.SerializerMethodField(read_only=True)

    class Meta:
        model = InventoryItemUnitOfMeasure
        fields = "__all__"
        read_only_fields = [
            "created_by",
            "updated_by",
            "is_deleted",
            "is_active",
            "base_uuid",
            "external_base_uuid",
            "reference_code",
            "deleted_at",
        ]

    def get_cost_price(self, obj):
        return obj.get_cost_price()

    def get_markup(self, obj):
        return obj.get_markup()

    def get_margin(self, obj):
        return obj.get_margin()

    def validate(self, attrs):
        inventory_item = attrs.get(
            "inventory_item",
            getattr(self.instance, "inventory_item", None),
        )
        is_base = attrs.get(
            "is_base_unit_of_measure",
            getattr(self.instance, "is_base_unit_of_measure", False),
        )

        if is_base:
            qs_base = InventoryItemUnitOfMeasure.objects.filter(
                inventory_item=inventory_item,
                is_base_unit_of_measure=True,
                deleted_at__isnull=True,
            )
            if self.instance:
                qs_base = qs_base.exclude(id=self.instance.id)
            if qs_base.exists():
                raise validation_error(
                    "There is already a base unit of measure for this inventory item."
                )

        return attrs

    def create(self, validated_data):
        request = self.context.get("request")
        user = getattr(request, "user", None)

        if user and user.is_authenticated:
            validated_data["created_by"] = user
            validated_data["updated_by"] = user

        inventory_item = validated_data["inventory_item"]
        unit_of_measure = validated_data["unit_of_measure"]

        if InventoryItemUnitOfMeasure.objects.filter(
            inventory_item=inventory_item,
            unit_of_measure=unit_of_measure,
            deleted_at__isnull=True,
        ).exists():
            raise validation_error(
                "This unit of measure already exists for the inventory item."
            )

        existing_soft_deleted = (
            InventoryItemUnitOfMeasure.objects.filter(
                inventory_item=inventory_item,
                unit_of_measure=unit_of_measure,
                deleted_at__isnull=False,
            )
            .order_by("-deleted_at")
            .first()
        )

        if existing_soft_deleted:
            for key, value in validated_data.items():
                setattr(existing_soft_deleted, key, value)
            existing_soft_deleted.deleted_at = None
            if user and user.is_authenticated:
                existing_soft_deleted.updated_by = user
            existing_soft_deleted.save()
            return existing_soft_deleted

        return super().create(validated_data)

    def update(self, instance, validated_data):
        request = self.context.get("request")
        user = getattr(request, "user", None)

        if user and user.is_authenticated:
            validated_data["updated_by"] = user

        return super().update(instance, validated_data)

    def to_representation(self, instance):
        data = super().to_representation(instance)

        data["unit_of_measure"] = (
            ItemUnitOfMeasureSerializer(
                instance.unit_of_measure, context=self.context
            ).data
            if instance.unit_of_measure
            else None
        )

        return data


class BranchToBranchStockMovementItemSerializer(serializers.ModelSerializer):
    unit_of_measure = UUIDRelatedField(
        queryset=BranchInventoryItemUnitOfMeasure.objects.all(),
        required=True,
    )
    inventory_item = UUIDRelatedField(
        queryset=BranchInventoryItem.objects.all(),
        required=True,
    )

    class Meta:
        model = BranchToBranchStockMovementItem
        fields = [
            "id",
            "inventory_item",
            "unit_of_measure",
            "quantity",
        ]

    def to_representation(self, instance):
        representation = super().to_representation(instance)
        representation["inventory_item"] = BranchInventoryItemSerializer(
            instance.inventory_item
        ).data

        if instance.unit_of_measure:
            representation["unit_of_measure"] = (
                BranchInventoryItemUnitOfMeasureSerializer(
                    instance.unit_of_measure
                ).data
            )
        else:
            representation["unit_of_measure"] = None
        return representation


class BranchToBranchStockMovementSerializer(BaseApprovableSerializer):
    items = BranchToBranchStockMovementItemSerializer(many=True)
    branch_from = UUIDRelatedField(
        queryset=Branch.objects.all(),
        required=True,
        write_only=True,
    )
    branch_to = UUIDRelatedField(
        queryset=Branch.objects.all(),
        required=True,
        write_only=True,
    )

    class Meta:
        model = BranchToBranchStockMovement
        fields = "__all__"
        read_only_fields = [
            "stock_movement_status",
            "is_stock_moved",
            "deleted_at",
            "approval_status",
            "base_uuid",
            "external_base_uuid",
            "is_active",
            "is_deleted",
            "original_data",
            "created_at",
        ]

    def create(self, validated_data):
        items_data = validated_data.pop("items", [])
        request = self.context.get("request")

        validated_data["created_by"] = request.user
        validated_data["updated_by"] = request.user

        movement = BranchToBranchStockMovement.objects.create(**validated_data)

        for item in items_data:
            BranchToBranchStockMovementItem.objects.create(
                stock_movement=movement, **item
            )

        return movement

    def update(self, instance, validated_data):
        items_data = validated_data.pop("items", None)
        request = self.context.get("request")
        validated_data["updated_by"] = request.user

        for attr, value in validated_data.items():
            setattr(instance, attr, value)

        instance.save()

        if items_data is not None:
            instance.items.all().delete()
            for item in items_data:
                BranchToBranchStockMovementItem.objects.create(
                    stock_movement=instance, **item
                )

        return instance

    def to_representation(self, instance):
        representation = super().to_representation(instance)
        representation["branch_to"] = BranchSerializer(instance.branch_to).data
        representation["branch_from"] = BranchSerializer(instance.branch_from).data

        return representation


class InstitutionWriteOffLineItemInputSerializer(serializers.Serializer):
    inventory_item = UUIDRelatedField(
        queryset=InventoryItem.objects.all(),
    )
    inventory_item_unit_of_measure = UUIDRelatedField(
        queryset=InventoryItemUnitOfMeasure.objects.all(),
    )
    quantity = serializers.IntegerField(min_value=1, default=1)


class InstitutionWriteOffLineItemSerializer(serializers.ModelSerializer):
    class Meta:
        model = InventoryItemWriteOffLineItem
        fields = [
            "id",
            "base_uuid",
            "inventory_item",
            "inventory_item_unit_of_measure",
            "quantity",
        ]

    def to_representation(self, instance):
        repr = super().to_representation(instance)

        if instance.inventory_item:
            repr["inventory_item"] = {
                "id": instance.inventory_item.id,
                "base_uuid": str(instance.inventory_item.base_uuid),
                "item_name": instance.inventory_item.item_name,
            }

        if instance.inventory_item_unit_of_measure:
            repr["inventory_item_unit_of_measure"] = {
                "id": instance.inventory_item_unit_of_measure.id,
                "base_uuid": str(instance.inventory_item_unit_of_measure.base_uuid),
                "unit_name": instance.inventory_item_unit_of_measure.unit_of_measure.unit_name,
            }

        return repr


class BranchWriteOffLineItemInputSerializer(serializers.Serializer):
    branch_inventory_item = UUIDRelatedField(
        queryset=BranchInventoryItem.objects.all(),
    )
    branch_item_unit_of_measure = UUIDRelatedField(
        queryset=BranchInventoryItemUnitOfMeasure.objects.all(),
    )
    quantity = serializers.IntegerField(min_value=1, default=1)


class BranchWriteOffLineItemSerializer(serializers.ModelSerializer):
    class Meta:
        model = BranchInventorytemWriteOffLineItem
        fields = [
            "id",
            "base_uuid",
            "branch_inventory_item",
            "branch_item_unit_of_measure",
            "quantity",
        ]

    def to_representation(self, instance):
        repr = super().to_representation(instance)

        if instance.branch_inventory_item:
            repr["branch_inventory_item"] = {
                "id": instance.branch_inventory_item.id,
                "base_uuid": str(instance.branch_inventory_item.base_uuid),
                "inventory_item": {
                    "id": instance.branch_inventory_item.inventory_item.id,
                    "base_uuid": str(
                        instance.branch_inventory_item.inventory_item.base_uuid
                    ),
                    "item_name": instance.branch_inventory_item.inventory_item.item_name,
                },
                "item_name": (
                    instance.branch_inventory_item.inventory_item.item_name
                    if instance.branch_inventory_item.inventory_item
                    else None
                ),
            }

        if instance.branch_item_unit_of_measure:
            repr["branch_item_unit_of_measure"] = {
                "id": instance.branch_item_unit_of_measure.id,
                "base_uuid": str(instance.branch_item_unit_of_measure.base_uuid),
                "unit_name": instance.branch_item_unit_of_measure.unit_of_measure.unit_name,
            }

        return repr


class WriteOffSerializer(BaseApprovableSerializer):
    institution = UUIDRelatedField(
        queryset=Institution.objects.all(),
        required=False,
        allow_null=True,
    )
    expense_account = UUIDRelatedField(
        queryset=Account.objects.all(),
        required=False,
        allow_null=True,
    )
    institution_line_items = InstitutionWriteOffLineItemInputSerializer(
        many=True, write_only=True, required=False
    )
    branch_line_items = BranchWriteOffLineItemInputSerializer(
        many=True, write_only=True, required=False
    )

    general_journal_items = serializers.SerializerMethodField()

    write_off_type = serializers.SerializerMethodField()

    class Meta:
        model = WriteOff
        fields = "__all__"
        read_only_fields = ["general_journal_items"]

    def get_general_journal_items(self, obj):
        return get_general_journal_items_for_object(obj)

    def get_write_off_type(self, obj):
        if obj.branch_id:
            return "Branch Based"
        if obj.institution_id:
            return "Institution Based"
        return "Unknown"

    def _get_available_stock(
        self, stock_object, unit_of_measure, is_branch_based: bool
    ) -> Decimal:
        if is_branch_based:
            layers = BranchInventoryItemStockLayer.objects.filter(
                branch_inventory_item=stock_object,
                unit_of_measure=unit_of_measure,
                deleted_at__isnull=True,
                quantity_remaining__gt=0,
            )
        else:
            layers = InventoryItemStockLayer.objects.filter(
                inventory_item=stock_object,
                unit_of_measure=unit_of_measure,
                deleted_at__isnull=True,
                quantity_remaining__gt=0,
            )
        return layers.aggregate(total=Sum("quantity_remaining"))["total"] or Decimal(
            "0.00"
        )

    def validate(self, data):
        institution_items = data.get("institution_line_items", None)
        branch_items = data.get("branch_line_items", None)

        if institution_items and branch_items:
            raise validation_error(
                "Write-off cannot contain both institution and branch line items at the same time."
            )

        if not institution_items and not branch_items:
            raise validation_error(
                "Write-off must contain either institution or branch line items."
            )

        if branch_items:
            branch_item_branches = set()

            for item in branch_items:
                branch_inventory_item = item.get("branch_inventory_item")
                unit_of_measure = item.get(
                    "branch_item_unit_of_measure"
                ).unit_of_measure
                quantity = item.get("quantity")

                if branch_inventory_item and branch_inventory_item.branch_id:
                    branch_item_branches.add(branch_inventory_item.branch_id)

                available = self._get_available_stock(
                    stock_object=branch_inventory_item,
                    unit_of_measure=unit_of_measure,
                    is_branch_based=True,
                )

                if available < quantity:
                    raise validation_error(
                        {
                            "branch_line_items": f"Not enough stock for {branch_inventory_item}. "
                            f"Available: {available} {unit_of_measure.unit_name}, "
                            f"Requested: {quantity}"
                        }
                    )

            if len(branch_item_branches) > 1:
                raise validation_error(
                    "Branch line items must belong to the same branch."
                )

            data["branch"] = (
                branch_items[0].get("branch_inventory_item").branch
                if branch_items
                else None
            )

        if institution_items:
            for item in institution_items:
                inventory_item = item.get("inventory_item")
                unit_of_measure = item.get(
                    "inventory_item_unit_of_measure"
                ).unit_of_measure
                quantity = item.get("quantity")

                available = self._get_available_stock(
                    stock_object=inventory_item,
                    unit_of_measure=unit_of_measure,
                    is_branch_based=False,
                )

                if available < quantity:
                    raise validation_error(
                        {
                            "institution_line_items": f"Not enough stock for {inventory_item}. "
                            f"Available: {available} {unit_of_measure.unit_name}, "
                            f"Requested: {quantity}"
                        }
                    )

        return data

    @transaction.atomic
    def _create_institution_line_items(self, write_off, items_data):
        for item in items_data:
            line_data = {
                "write_off": write_off,
                "inventory_item": item.get("inventory_item"),
                "inventory_item_unit_of_measure": item.get(
                    "inventory_item_unit_of_measure"
                ),
                "quantity": item["quantity"],
            }
            InventoryItemWriteOffLineItem.objects.create(**line_data)

    @transaction.atomic
    def _create_branch_line_items(self, write_off, items_data):
        for item in items_data:
            line_data = {
                "write_off": write_off,
                "branch_inventory_item": item.get("branch_inventory_item"),
                "branch_item_unit_of_measure": item.get("branch_item_unit_of_measure"),
                "quantity": item["quantity"],
            }
            BranchInventorytemWriteOffLineItem.objects.create(**line_data)

    @transaction.atomic
    def create(self, validated_data):
        request = self.context.get("request")
        institution = get_institution(request)
        institution_items = validated_data.pop("institution_line_items", [])
        branch_items = validated_data.pop("branch_line_items", [])

        if institution_items:
            validated_data["institution"] = institution if institution else None
        else:
            validated_data["institution"] = None

        validated_data["branch"] = (
            branch_items[0].get("branch_inventory_item").branch
            if branch_items
            else None
        )

        write_off = WriteOff.objects.create(**validated_data)

        self._create_institution_line_items(write_off, institution_items)
        self._create_branch_line_items(write_off, branch_items)

        return write_off

    @transaction.atomic
    def update(self, instance, validated_data):
        institution_items = validated_data.pop("institution_line_items", None)
        branch_items = validated_data.pop("branch_line_items", None)

        for attr, value in validated_data.items():
            setattr(instance, attr, value)
        instance.save()

        if institution_items is not None or branch_items is not None:
            instance.institution_wo_line_items.all().delete()
            instance.branch_wo_line_items.all().delete()

            if institution_items:
                self._create_institution_line_items(instance, institution_items)
            if branch_items:
                self._create_branch_line_items(instance, branch_items)

        return instance

    def to_representation(self, instance):
        repr = super().to_representation(instance)

        if instance.institution:
            repr["institution"] = {
                "id": instance.institution.id,
                "base_uuid": str(instance.institution.base_uuid),
                "institution_name": instance.institution.institution_name,
            }

        if instance.branch:
            repr["branch"] = {
                "id": instance.branch.id,
                "base_uuid": str(instance.branch.base_uuid),
                "branch_name": instance.branch.branch_name,
            }

        if instance.expense_account:
            repr["expense_account"] = {
                "id": instance.expense_account.id,
                "base_uuid": str(instance.expense_account.base_uuid),
                "account_name": instance.expense_account.account_name,
                "account_code": instance.expense_account.reference_code,
            }

        return repr


class StockMovementLogSerializer(serializers.ModelSerializer):
    item_name = serializers.CharField(source="inventory_item.item_name", read_only=True)
    reference_code = serializers.CharField(
        source="inventory_item.reference_code", read_only=True
    )
    location_name = serializers.SerializerMethodField()
    unit_of_measure_name = serializers.CharField(
        source="unit_of_measure.unit_name", read_only=True, allow_null=True
    )

    class Meta:
        model = StockMovementLog
        fields = "__all__"

    def get_location_name(self, obj):
        if obj.branch:
            return obj.branch.branch_name

        if obj.institution:
            return obj.institution.institution_name

        return None


class StockLocationSerializer(serializers.Serializer):
    location_type = serializers.CharField()
    location_name = serializers.CharField()
    quantity_remaining = serializers.IntegerField()


class InventorySummarySerializer(serializers.Serializer):
    products = serializers.ListField(child=serializers.DictField())

    def to_representation(self, instance):
        products = instance

        for product in products:
            for unit in product.get("units_of_measure", []):
                unit["stock_locations"] = StockLocationSerializer(
                    unit.get("stock_locations", []), many=True
                ).data

        return {"products": products}


class StockMovementDownloadSerializer(serializers.Serializer):
    product_id = serializers.UUIDField(
        required=False, help_text="Optional download logs for a specific product"
    )
    branch_id = serializers.UUIDField(
        required=False, help_text="Optional: filter logs for a specific branch"
    )
    file_type = serializers.ChoiceField(
        choices=[("excel", "Excel"), ("pdf", "PDF")],
        default="pdf",
        required=False,
    )
    delivery_method = serializers.ChoiceField(
        choices=[("download", "Download"), ("email", "Email")],
        default="download",
        required=False,
    )
    recipient_email = serializers.EmailField(
        required=False,
        allow_blank=True,
        default="",
    )
    movement_type = serializers.ChoiceField(
        choices=StockMovementLog.MOVEMENT_TYPE_CHOICES,
        required=False,
    )
    stock_level = serializers.ChoiceField(
        choices=StockMovementLog.LEVEL_CHOICES,
        required=False,
    )
    start_date = serializers.DateField(required=False)
    end_date = serializers.DateField(required=False)
    date_filter = serializers.CharField(required=False, default="all")

    def validate_date_filter(self, value):
        allowed_keys = {
            "all",
            "today",
            "yesterday",
            "this_week",
            "this_week_to_date",
            "last_week",
            "last_week_to_date",
            "this_month",
            "this_month_to_date",
            "last_month",
            "last_month_to_date",
            "this_year",
            "this_year_to_date",
            "last_year",
            "last_year_to_date",
            "this_fiscal_year",
            "this_fiscal_year_to_date",
            "this_fiscal_year_to_last_month",
            "last_fiscal_year",
            "last_fiscal_year_to_date",
            "current_fiscal_year",
        }
        value = value.lower()
        if value not in allowed_keys:
            raise validation_error("Invalid date_filter")

        return value
