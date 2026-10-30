from django.db import models
from utilities.utility_base_model import SoftDeletableTimeStampedModel
from approval.models import Approval, BaseApprovableModel
from django.db import transaction
from django.utils import timezone
from django.core.exceptions import ValidationError
from reports.mixins import ReportableModelMixin
from utilities.helpers import validation_error
from decimal import Decimal
from django.utils import timezone
from utilities.email_client import EmailClient
from django.contrib.contenttypes.models import ContentType
from django.contrib.contenttypes.fields import GenericForeignKey
from .stock_logger import log_stock_movement
from items.unit_converter import get_conversion_factor


class ItemCategory(ReportableModelMixin, BaseApprovableModel):
    reference_prefix = "ITMCAT"

    institution = models.ForeignKey(
        "institution.Institution",
        on_delete=models.CASCADE,
        related_name="item_categories",
    )
    name = models.CharField(max_length=100)

    expense_account = models.ForeignKey(
        "accounts.Account",
        on_delete=models.CASCADE,
        related_name="item_category_expense_account",
        null=True,
        blank=True,
    )

    revenue_account = models.ForeignKey(
        "accounts.Account",
        on_delete=models.CASCADE,
        related_name="item_category_revenue_account",
        null=True,
        blank=True,
    )

    inventory_account = models.ForeignKey(
        "accounts.Account",
        on_delete=models.CASCADE,
        related_name="item_category_inventory_account",
        null=True,
        blank=True,
    )

    search_fields = [
        "name",
        "description",
        "expense_account__account_name",
        "revenue_account__account_name",
        "inventory_account__account_name",
    ]

    ordering_fields = ["name", "created_at"]

    filterset_fields = [
        "expense_account__base_uuid",
        "revenue_account__base_uuid",
        "inventory_account__base_uuid",
    ]

    class Meta:
        unique_together = (
            "institution",
            "name",
        )

        ordering = ["-created_at", "name"]

    def __str__(self):
        return self.name

    @classmethod
    def get_additional_filters(cls):
        return [
            "name",
        ]

    @classmethod
    def get_filter_serializer_class(cls):
        from items.filters import ItemCategoryFilterSerializer

        return ItemCategoryFilterSerializer

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


class ItemUnitOfMeasure(ReportableModelMixin, BaseApprovableModel):
    reference_prefix = "ITUOM"
    institution = models.ForeignKey(
        "institution.Institution",
        on_delete=models.CASCADE,
        related_name="item_units_of_measure",
    )
    unit_name = models.CharField(max_length=50)
    unit_abbreviation = models.CharField(max_length=50)

    search_fields = [
        "unit_name",
        "unit_abbreviation",
        "description",
        "created_by__fullname",
    ]

    filterset_fields = [
        "created_by__base_uuid",
    ]

    ordering_fields = [
        "unit_name",
        "unit_abbreviation",
        "created_by__fullname",
    ]

    def __str__(self):
        return self.unit_name

    class Meta:
        unique_together = ("institution", "unit_name")

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


class InventoryItem(ReportableModelMixin, BaseApprovableModel):
    reference_prefix = "ITM"

    institution = models.ForeignKey(
        "institution.Institution", on_delete=models.CASCADE, null=True, blank=True
    )

    ITEM_TYPE_CHOICES = [
        ("GOODS", "Goods"),
        ("SERVICES", "Services"),
    ]

    item_name = models.CharField(max_length=100)

    item_type = models.CharField(
        max_length=20, choices=ITEM_TYPE_CHOICES, default="GOODS"
    )
    item_category = models.ForeignKey(
        ItemCategory, on_delete=models.CASCADE, blank=False, null=False
    )

    reorder_point = models.IntegerField(default=0)

    inventory_account = models.ForeignKey(
        "accounts.Account",
        on_delete=models.CASCADE,
        related_name="inventory_account",
        null=True,
        blank=True,
    )
    revenue_account = models.ForeignKey(
        "accounts.Account",
        on_delete=models.CASCADE,
        related_name="revenue_account",
        null=True,
        blank=True,
    )

    expense_account = models.ForeignKey(
        "accounts.Account",
        on_delete=models.CASCADE,
        related_name="expense_account",
        null=True,
        blank=True,
    )

    preferred_vendors = models.ManyToManyField(
        "vendors.Vendor",
        through="ItemVendor",
        related_name="inventory_items",
        blank=True,
    )

    are_initial_journal_entries_made = models.BooleanField(default=False)

    product_stock_valuation_method = models.ForeignKey(
        "system.SystemStockValuationMethod",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
    )
    product_stock_movement_strategy = models.ForeignKey(
        "system.SystemStockMovementStrategy",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
    )

    inventory_item_units_of_measure = models.ManyToManyField(
        ItemUnitOfMeasure,
        through="InventoryItemUnitOfMeasure",
        related_name="inventory_items",
        blank=True,
        through_fields=("inventory_item", "unit_of_measure"),
    )

    sales_tax = models.ForeignKey(
        "taxation.Tax",
        on_delete=models.CASCADE,
        related_name="sold_items",
        blank=True,
        null=True,
    )
    purchase_tax = models.ForeignKey(
        "taxation.Tax",
        on_delete=models.CASCADE,
        related_name="purchased_items",
        blank=True,
        null=True,
    )

    can_be_sold = models.BooleanField(default=True)
    can_be_purchased = models.BooleanField(default=True)

    selling_branches = models.ManyToManyField(
        "institution.Branch",
        related_name="items_sold",
        blank=True,
        through="BranchInventoryItem",
    )

    search_fields = [
        "item_name",
        "reference_code",
        "item_category__name",
    ]
    ordering_fields = [
        "reference_code",
        "item_name",
    ]

    class Meta:
        unique_together = (
            "institution",
            "reference_code",
        )
        verbose_name = "Inventory Item"
        verbose_name_plural = "Inventory Items"
        ordering = ["-created_at", "item_name"]

    def _get_inventory_account(self):
        if self.inventory_account:
            return self.inventory_account

        if self.item_category and self.item_category.inventory_account:
            return self.item_category.inventory_account

        return None

    def clean(self):
        revenue_account = self.revenue_account or None
        inventory_account = self.inventory_account or None

        if (
            revenue_account
            and revenue_account.account_role is not None
            and revenue_account.account_role.role_group.group_type_name.lower()
            != "revenue"
        ):
            raise validation_error(
                {
                    "revenue_account": "Revenue account must belong to a Revenue account group."
                }
            )

        if (
            inventory_account
            and inventory_account.account_role is not None
            and inventory_account.account_role.role_group.group_type_name.lower()
            != "asset"
        ):
            raise validation_error(
                {
                    "inventory_account": "Inventory account must belong to an Asset account group."
                }
            )

    @classmethod
    def get_additional_filters(cls):
        return [
            "item_type",
        ]

    @classmethod
    def get_filter_serializer_class(cls):
        from items.filters import ItemFilterSerializer

        return ItemFilterSerializer

    def get_institution(self):
        return self.item_category.institution

    @classmethod
    def get_institution_filter_field(cls):
        return "item_category__institution"

    def __str__(self):
        return f"{self.item_name} ({self.item_category})"

    def _soft_delete_branch_inventory_items(self):
        branch_item_ids = list(
            BranchInventoryItem.objects.filter(
                inventory_item=self,
                deleted_at__isnull=True,
            ).values_list("id", flat=True)
        )

        if not branch_item_ids:
            return

        deleted_at = timezone.now()

        BranchInventoryItemUnitOfMeasure.objects.filter(
            branch_inventory_item_id__in=branch_item_ids,
            deleted_at__isnull=True,
        ).update(deleted_at=deleted_at, is_active=False)

        BranchInventoryItemStockLayer.objects.filter(
            branch_inventory_item_id__in=branch_item_ids,
            deleted_at__isnull=True,
        ).update(deleted_at=deleted_at, is_active=False)

        BranchInventoryItem.objects.filter(id__in=branch_item_ids).update(
            deleted_at=deleted_at,
            is_active=False,
        )

    def finish_workflow(self, approval: Approval):
        with transaction.atomic():
            if approval.status == "completed":
                if approval.action.name in ["create", "update"]:
                    self.is_active = True
                elif approval.action.name == "delete":
                    self._soft_delete_branch_inventory_items()
                    self.delete()
            elif approval.status == "rejected":
                if approval.action.name == "create":
                    self.is_active = False
                elif approval.action.name in ["update", "delete"]:
                    self.is_active = False
                    self.deleted_at = None

        self.save()

    def _create_branch_inventory_item_units(self, branch_inventory_items):
        item_units = InventoryItemUnitOfMeasure.objects.filter(
            inventory_item=self,
            deleted_at__isnull=True,
        )

        if not item_units.exists():
            return

        branch_inventory_item_units = []

        for branch_item in branch_inventory_items:
            for item_unit in item_units:
                branch_inventory_item_units.append(
                    BranchInventoryItemUnitOfMeasure(
                        branch_inventory_item=branch_item,
                        unit_of_measure=item_unit.unit_of_measure,
                        conversion_factor=item_unit.conversion_factor,
                        selling_price=item_unit.selling_price,
                        is_base_unit_of_measure=item_unit.is_base_unit_of_measure,
                    )
                )

        BranchInventoryItemUnitOfMeasure.objects.bulk_create(
            branch_inventory_item_units
        )

    def assign_inventory_items_to_all_branches(
        self, branches: list = None, skip_uom_sync=False
    ):
        if branches is None:
            branches = self.item_category.institution.branches.all()

        existing_branch_ids = BranchInventoryItem.objects.filter(
            inventory_item=self,
            branch__in=branches,
        ).values_list("branch_id", flat=True)

        new_branches = [
            branch for branch in branches if branch.id not in existing_branch_ids
        ]

        new_items = [
            BranchInventoryItem(
                inventory_item=self,
                branch=branch,
            )
            for branch in new_branches
        ]

        with transaction.atomic():
            created_items = BranchInventoryItem.objects.bulk_create(new_items)
            if not skip_uom_sync:
                self._create_branch_inventory_item_units(created_items)

    def save(self, *args, **kwargs):

        if self.item_type == "SERVICES":
            self.inventory_account = None
            self.product_stock_valuation_method = None
            self.product_stock_movement_strategy = None

        self.full_clean()

        super().save(*args, **kwargs)

    def bulk_assign_to_branches(new_inventory_items):
        if not new_inventory_items:
            return

        items_by_institution = {}
        for item in new_inventory_items:
            institution = item.item_category.institution

            if institution not in items_by_institution:
                items_by_institution[institution] = []
            items_by_institution[institution].append(item)

        new_branch_inventory_items = []

        for institution, items in items_by_institution.items():
            branches = institution.branches.all()

            for branch in branches:
                for item in items:
                    new_branch_inventory_items.append(
                        BranchInventoryItem(
                            inventory_item=item,
                            branch=branch,
                        )
                    )

        if new_branch_inventory_items:
            BranchInventoryItem.objects.bulk_create(new_branch_inventory_items)

    def get_default_stock_movement_strategy(self):
        if self.product_stock_movement_strategy:
            return self.product_stock_movement_strategy

        if self.branch and self.branch.default_stock_movement_strategy:
            return self.branch.default_stock_movement_strategy

        if self.institution and self.institution.default_stock_movement_strategy:
            return self.institution.default_stock_movement_strategy

        else:
            return None

    def get_default_stock_valuation_method(self):
        if self.product_stock_valuation_method:
            return self.product_stock_valuation_method

        if self.institution and self.institution.default_stock_valuation_method:
            return self.institution.default_stock_valuation_method

        else:
            return None

    def get_quantity_on_hand(self, unit_of_measure=None):

        item_stock_layers = InventoryItemStockLayer.objects.filter(
            inventory_item=self, deleted_at__isnull=True
        )

        if unit_of_measure is not None:
            item_stock_layers = item_stock_layers.filter(
                unit_of_measure=unit_of_measure
            )

        qty_in_layers = (
            item_stock_layers.aggregate(
                total_quantity=models.Sum("quantity_remaining")
            )["total_quantity"]
            or 0
        )

        return qty_in_layers


class InventoryItemImage(SoftDeletableTimeStampedModel):
    reference_prefix = "ITMIMG"
    inventory_item = models.ForeignKey(
        InventoryItem, on_delete=models.CASCADE, related_name="images"
    )
    image_name = models.CharField(max_length=100, blank=True, null=True)
    image = models.ImageField(upload_to="inventory_item_images/")
    is_default = models.BooleanField(default=False)

    def __str__(self):
        return f"{self.inventory_item.item_name} - Image"

    class Meta:
        verbose_name = "Inventory Item Image"
        verbose_name_plural = "Inventory Item Images"
        ordering = ["-created_at"]

    def clean(self):
        if self.is_default:
            existing_default = (
                InventoryItemImage.objects.undeleted()
                .filter(
                    inventory_item=self.inventory_item,
                    is_default=True,
                )
                .exclude(id=self.id)
            )

            if existing_default.exists():
                raise ValidationError(
                    "There is already a default image for this inventory item."
                )

    def save(self, *args, **kwargs):
        self.full_clean()
        super().save(*args, **kwargs)


class ItemVendor(SoftDeletableTimeStampedModel):
    item = models.ForeignKey(
        InventoryItem, on_delete=models.CASCADE, related_name="item_vendors"
    )

    vendor = models.ForeignKey(
        "vendors.Vendor", on_delete=models.CASCADE, related_name="vendor_items"
    )

    class Meta:
        unique_together = ("item", "vendor")

    def __str__(self):
        return f"{self.item} - {self.vendor}"


class ItemVendorUnitPrice(SoftDeletableTimeStampedModel):
    item_vendor = models.ForeignKey(
        ItemVendor, on_delete=models.CASCADE, related_name="unit_prices"
    )

    unit_of_measure = models.ForeignKey(
        "items.InventoryItemUnitOfMeasure", on_delete=models.CASCADE
    )

    price = models.DecimalField(max_digits=15, decimal_places=2)

    minimum_order_qty = models.PositiveIntegerField(default=1)

    class Meta:
        unique_together = ("item_vendor", "unit_of_measure")
        verbose_name = "Item Vendor Unit Price"
        verbose_name_plural = "Item Vendor Unit Prices"

    def __str__(self):
        return f"{self.item_vendor} - {self.unit_of_measure}"


class InventoryItemUnitOfMeasure(SoftDeletableTimeStampedModel):
    reference_prefix = "ITUOM"
    inventory_item = models.ForeignKey(
        InventoryItem,
        on_delete=models.CASCADE,
        related_name="units",
    )
    unit_of_measure = models.ForeignKey(
        ItemUnitOfMeasure,
        on_delete=models.CASCADE,
        related_name="inventory_item_units",
    )

    conversion_factor = models.DecimalField(
        max_digits=50,
        decimal_places=20,
        help_text="This is the factor to base unit of measure. For example, if the unit of measure is 'box' and the base unit is 'piece', and there are 10 pieces in a box, then the conversion factor would be 10.",
    )

    selling_price = models.DecimalField(max_digits=50, decimal_places=20, default=0.00)

    is_base_unit_of_measure = models.BooleanField(default=False)

    other_quantity = models.DecimalField(
        max_digits=50,
        decimal_places=20,
        blank=True,
        null=True,
    )
    other_uom = models.ForeignKey(
        "items.ItemUnitOfMeasure",
        on_delete=models.CASCADE,
        blank=True,
        null=True,
        related_name="inventory_item_uoms",
    )

    def __str__(self):
        return f"{self.inventory_item.item_name} - {self.unit_of_measure.unit_name} (x{self.conversion_factor})"

    def clean(self):
        if self.is_base_unit_of_measure:
            existing_base_units = InventoryItemUnitOfMeasure.objects.filter(
                inventory_item=self.inventory_item,
                is_base_unit_of_measure=True,
                deleted_at__isnull=True,
            ).exclude(id=self.id)

            if existing_base_units.exists():
                raise ValidationError(
                    "There is already a base unit of measure assigned to this inventory item."
                )

            if self.other_quantity is not None:
                raise validation_error(
                    "Other QTY should be empty for base unit of measure."
                )

            if self.other_uom is not None:
                raise validation_error(
                    "Other UOM should be empty for base unit of measure."
                )

    class Meta:
        unique_together = (
            "inventory_item",
            "unit_of_measure",
        )
        verbose_name = "Inventory Item Unit of Measure"
        verbose_name_plural = "Inventory Item Units of Measure"
        ordering = ["-created_at"]

    def get_institution(self):
        return self.inventory_item.get_institution()

    def save(self, *args, **kwargs):
        self.full_clean()

        with transaction.atomic():
            super().save(*args, **kwargs)

            self.sync_to_branches()

    def sync_to_branches(self):
        branch_items = BranchInventoryItem.objects.active().filter(
            inventory_item=self.inventory_item,
        )

        existing_records = BranchInventoryItemUnitOfMeasure.objects.filter(
            branch_inventory_item__in=branch_items,
            unit_of_measure=self.unit_of_measure,
        )

        existing_map = {r.branch_inventory_item_id: r for r in existing_records}

        to_create = []
        to_update = []

        for branch_item in branch_items:
            existing = existing_map.get(branch_item.id)

            if existing:
                existing.conversion_factor = self.conversion_factor
                existing.selling_price = self.selling_price
                existing.is_base_unit_of_measure = self.is_base_unit_of_measure
                existing.other_quantity = self.other_quantity
                existing.other_uom = self.other_uom
                to_update.append(existing)
            else:
                to_create.append(
                    BranchInventoryItemUnitOfMeasure(
                        branch_inventory_item=branch_item,
                        unit_of_measure=self.unit_of_measure,
                        conversion_factor=self.conversion_factor,
                        selling_price=self.selling_price,
                        is_base_unit_of_measure=self.is_base_unit_of_measure,
                        other_quantity=self.other_quantity,
                        other_uom=self.other_uom,
                    )
                )

        if to_create:
            BranchInventoryItemUnitOfMeasure.objects.bulk_create(to_create)

        if to_update:
            BranchInventoryItemUnitOfMeasure.objects.bulk_update(
                to_update,
                [
                    "conversion_factor",
                    "selling_price",
                    "is_base_unit_of_measure",
                    "other_quantity",
                    "other_uom",
                ],
            )

    def get_cost_price(self):
        from manufacturing.services import ManufacturingUnitCostingService

        return ManufacturingUnitCostingService.estimate_inventory_item_unit_cost(
            self.inventory_item,
            self,
        )

    def get_markup(self):
        cost_price = Decimal(self.get_cost_price() or "0")
        selling_price = Decimal(self.selling_price or "0")

        if cost_price <= 0:
            return Decimal("0.0000")

        profit = selling_price - cost_price

        return ((profit / cost_price) * Decimal("100")).quantize(Decimal("0.0001"))

    def get_margin(self):
        cost_price = Decimal(self.get_cost_price() or "0")
        selling_price = Decimal(self.selling_price or "0")

        if selling_price <= 0:
            return Decimal("0.0000")

        profit = selling_price - cost_price

        return ((profit / selling_price) * Decimal("100")).quantize(Decimal("0.0001"))


class InventoryItemPriceChange(SoftDeletableTimeStampedModel):

    TYPE_OF_PRICE_CHANGE_CHOICES = [
        ("BUYING_PRICE", "Buying Price"),
        ("SELLING_PRICE", "Selling Price"),
    ]
    inventory_item = models.ForeignKey("InventoryItem", on_delete=models.CASCADE)
    type_of_price_change = models.CharField(
        max_length=20,
        choices=TYPE_OF_PRICE_CHANGE_CHOICES,
        default="BUYING_PRICE",
    )
    price_before = models.DecimalField(max_digits=50, decimal_places=20)
    price_after = models.DecimalField(max_digits=50, decimal_places=20)

    def __str__(self):
        return f"{self.inventory_item.item_name} - {self.type_of_price_change} - {self.price_before} to {self.price_after}"

    class Meta:
        verbose_name = "Inventory Item Price Change"
        verbose_name_plural = "Inventory Item Price Changes"
        ordering = ["-created_at"]


class InventoryItemStockLayer(SoftDeletableTimeStampedModel):
    reference_prefix = "ITSL"
    inventory_item = models.ForeignKey(
        "items.InventoryItem", on_delete=models.CASCADE, related_name="stock_layers"
    )
    unit_of_measure = models.ForeignKey(
        ItemUnitOfMeasure, on_delete=models.CASCADE, blank=True, null=True
    )
    quantity_remaining = models.IntegerField(default=0)
    unit_cost = models.DecimalField(max_digits=50, decimal_places=20, default=0.00)
    recieved_date = models.DateTimeField(default=timezone.now)

    reorder_point = models.PositiveIntegerField(default=0)

    expiry_date = models.DateTimeField(
        null=True,
        blank=True,
        help_text="Optional expiry date of the inventory item",
    )

    opening_balance_account = models.ForeignKey(
        "accounts.Account",
        on_delete=models.CASCADE,
        related_name="opening_balance_account",
        null=True,
        blank=True,
    )

    seach_fields = [
        "inventory_item__item_name",
        "inventory_item__reference_code",
    ]

    def __str__(self):
        return f"{self.inventory_item.item_name} - Stock Layer ({self.quantity_remaining} units at {self.unit_cost})"

    def get_institution(self):
        return self.inventory_item.get_institution()

    def clean(self):
        if self.unit_cost is not None and self.unit_cost <= 0:
            raise ValidationError(
                {
                    "unit_cost": "Stock must have a unit cost greater than zero. "
                    "For gifted stock, enter its assessed unit value."
                }
            )

        if self.quantity_remaining < 0:
            raise ValidationError("Quantity remaining cannot be negative.")

        if self.recieved_date > timezone.now():
            raise ValidationError("Received date cannot be in the future.")

    class Meta:
        verbose_name = "Inventory Item Stock Layer"
        verbose_name_plural = "Inventory Item Stock Layers"
        db_table = "inventory_item_stock_layers"
        ordering = ["-recieved_date"]
        constraints = [
            models.UniqueConstraint(
                fields=["inventory_item", "unit_cost"],
                condition=models.Q(deleted_at__isnull=True),
                name="uniq_active_inventory_layer_per_cost",
            )
        ]

    def save(self, *args, **kwargs):
        self.full_clean()
        is_new = self._state.adding

        super().save(*args, **kwargs)

        if is_new:
            log_stock_movement(
                movement_type="OPENING_STOCK",
                inventory_item=self.inventory_item,
                quantity_change=self.quantity_remaining,
                quantity_before=0,
                unit_cost=self.unit_cost,
                unit_of_measure=self.unit_of_measure,
                institution=self.get_institution(),
                source_document=self,
                source_reference=self.reference_code,
                notes=f"Opening stock entry for '{self.inventory_item.item_name}'",
            )

            if (
                not self.inventory_item.are_initial_journal_entries_made
                and self.inventory_item.item_type == "GOODS"
            ):
                self._process_financial_events()

    @transaction.atomic
    def _process_financial_events(self):
        from utilities.helpers import format_2dp

        self = self.__class__.objects.select_for_update().get(pk=self.pk)

        if (
            self.inventory_item.are_initial_journal_entries_made
            or self.quantity_remaining <= 0
        ):
            return

        institution = self.get_institution()

        from transactions.models import Transaction
        from transactions.services import JournalLine, JournalPostingService
        from accounts.utils import get_or_create_default_account
        from django.contrib.contenttypes.models import ContentType
        from utilities.helpers import get_fiscal_year

        content_type = ContentType.objects.get_for_model(self.__class__)
        if Transaction.objects.filter(
            content_type=content_type,
            object_id=self.pk,
            deleted_at__isnull=True,
        ).exists():
            return

        total_value = self.quantity_remaining * self.unit_cost
        posting_date = (
            self.recieved_date
            or self.inventory_item.created_at
            or self.created_at
            or timezone.now()
        )

        inventory_account = (
            self.inventory_item.inventory_account
            or get_or_create_default_account(institution, "inventory_account")
        )
        opening_stock_account = (
            self.opening_balance_account
            or get_or_create_default_account(institution, "opening_balance_account")
        )

        JournalPostingService.post(
            fiscal_year=get_fiscal_year(institution, posting_date),
            title=f"Opening Stock Entry - {self.inventory_item.item_name}",
            description=(
                f"Opening stock entry of {self.quantity_remaining} "
                f"{self.unit_of_measure.unit_name if self.unit_of_measure else 'units'} of "
                f"'{self.inventory_item.item_name}' at unit cost {format_2dp(self.unit_cost)} each. "
                f"Total value: {format_2dp(total_value)}"
            ),
            lines=[
                JournalLine(
                    account=inventory_account,
                    entry_type="debit",
                    transaction_amount=total_value,
                    transaction_currency=institution.currency,
                    exchange_rate=Decimal("1"),
                    description=f"Inventory added for item '{self.inventory_item.item_name}'",
                ),
                JournalLine(
                    account=opening_stock_account,
                    entry_type="credit",
                    transaction_amount=total_value,
                    transaction_currency=institution.currency,
                    exchange_rate=Decimal("1"),
                    description=f"Opening stock for inventory item '{self.inventory_item.item_name}'",
                ),
            ],
            content_type=content_type,
            object_id=self.pk,
            transaction_date=posting_date,
        )


class FiscalYear(ReportableModelMixin, BaseApprovableModel):
    reference_prefix = "FY"

    institution = models.ForeignKey(
        "institution.Institution",
        on_delete=models.CASCADE,
        related_name="fiscal_years",
    )
    name = models.CharField(max_length=255, blank=True, null=True)
    start_date = models.DateField()
    end_date = models.DateField()
    is_current = models.BooleanField(default=False)
    is_closed = models.BooleanField(default=False)

    filterset_fields = ["is_closed", "is_current"]

    search_fields = [
        "name",
        "reference_code",
    ]
    ordering_fields = [
        "reference_code",
        "name",
        "start_date",
        "end_date",
        "is_current",
        "is_closed",
    ]

    def __str__(self):
        return f"Fiscal Year {self.name} ({self.start_date} - {self.end_date})"

    class Meta:
        unique_together = ("institution", "name")
        ordering = [
            "-start_date",
            "-end_date",
        ]
        verbose_name = "Fiscal Year"
        verbose_name_plural = "Fiscal Years"

    def clean(self):
        if self.start_date >= self.end_date:
            raise ValidationError("Start date must be before end date.")

        if self.is_current:
            current_fy = FiscalYear.objects.filter(
                institution=self.institution, is_current=True
            ).exclude(id=self.id)
            if current_fy.exists():
                raise ValidationError(
                    "Another fiscal year is already marked as current."
                )

    def save(self, *args, **kwargs):
        self.full_clean()
        super().save(*args, **kwargs)

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
                    self.deleted_at = timezone.now()

                elif approval.action.name in ["update", "delete"]:
                    self.is_active = False
                    self.deleted_at = None

        self.save()


class BranchInventoryItem(ReportableModelMixin, BaseApprovableModel):
    reference_prefix = "BITM"

    branch = models.ForeignKey(
        "institution.Branch",
        on_delete=models.CASCADE,
        related_name="branch_inventory",
        blank=False,
        null=False,
    )

    inventory_item = models.ForeignKey(
        InventoryItem,
        on_delete=models.CASCADE,
        related_name="branch_specific_inventory",
        blank=False,
        null=False,
    )

    can_be_returned = models.BooleanField(default=False)

    search_fields = [
        "inventory_item__item_name",
    ]

    class Meta:
        unique_together = ("branch", "inventory_item")
        verbose_name = "Branch Inventory Item"
        verbose_name_plural = "Branch Inventory Items"
        ordering = [
            "-created_at",
            "inventory_item__item_name",
        ]

    def clean(self):
        institution = self.branch.institution

        if self.can_be_returned:

            if self.inventory_item.item_type != "GOODS":
                raise ValidationError(
                    "Only items of type 'GOODS' can be marked as returnable."
                )

            if not institution.supports_sales_returns:
                raise validation_error(
                    {
                        "Return Policy": "This institution does not support sales returns, so this item cannot be marked as returnable by customers."
                    }
                )

    def __str__(self):
        return f"{self.inventory_item.item_name} @ {self.branch.branch_name}"

    def get_institution(self):
        return self.branch.institution

    @classmethod
    def get_institution_filter_field(cls):
        return "branch__institution"

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

    def get_quantity_at_hand(self, unit_of_measure=None):
        item_stock_layers = BranchInventoryItemStockLayer.objects.filter(
            branch_inventory_item=self, deleted_at__isnull=True
        )

        if unit_of_measure is not None:
            item_stock_layers = item_stock_layers.filter(
                unit_of_measure=unit_of_measure.unit_of_measure
            )

        qty_in_layers = (
            item_stock_layers.aggregate(
                total_quantity=models.Sum("quantity_remaining")
            )["total_quantity"]
            or 0
        )

        return qty_in_layers

    def get_effective_quantity_at_hand(self, unit_of_measure=None) -> Decimal:
        if unit_of_measure is None:
            return self.get_quantity_at_hand()

        institution = self.get_institution()

        allow_breakdown = getattr(institution, "allow_unit_breakdown", False)

        if not allow_breakdown:
            return self.get_quantity_at_hand(unit_of_measure=unit_of_measure)

        sold_item_uom = unit_of_measure.unit_of_measure

        try:
            sold_cf = get_conversion_factor(self, sold_item_uom)
        except ValueError:
            return self.get_quantity_at_hand(unit_of_measure=unit_of_measure)

        layers = BranchInventoryItemStockLayer.objects.active().filter(
            branch_inventory_item=self,
            quantity_remaining__gt=0,
        )

        total_base = Decimal("0")

        for layer in layers:

            layer_item_uom = layer.unit_of_measure

            if layer_item_uom is None:
                layer_cf = Decimal("1")
            else:
                try:
                    layer_cf = get_conversion_factor(self, layer_item_uom)

                except ValueError:
                    continue

            print("---- LAYER ----")
            print("UOM:", layer_item_uom.unit_name)
            print("QTY:", layer.quantity_remaining)
            print("CF:", layer_cf)

            total_base += Decimal(layer.quantity_remaining) * layer_cf

        return total_base / sold_cf

    def save(self, *args, **kwargs):
        self.full_clean()
        super().save(*args, **kwargs)


class BranchInventoryItemStockLayer(SoftDeletableTimeStampedModel):
    reference_prefix = "BITMSL"
    branch_inventory_item = models.ForeignKey(
        BranchInventoryItem, on_delete=models.CASCADE, related_name="stock_layers"
    )
    unit_of_measure = models.ForeignKey(
        ItemUnitOfMeasure, on_delete=models.CASCADE, blank=True, null=True
    )
    quantity_remaining = models.DecimalField(
        max_digits=50,
        decimal_places=20,
        default=Decimal("0"),
    )
    unit_cost = models.DecimalField(max_digits=50, decimal_places=20, default=0.0)
    received_date = models.DateTimeField(default=timezone.now)

    source_branch = models.ForeignKey(
        "institution.Branch", null=True, blank=True, on_delete=models.SET_NULL
    )

    restored_from_movement = models.ForeignKey(
        "items.StockMovementLog",
        on_delete=models.PROTECT,
        related_name="restored_stock_layers",
        null=True,
        blank=True,
    )
    restored_by_return_item = models.ForeignKey(
        "customers.ItemReturnItem",
        on_delete=models.PROTECT,
        related_name="restored_stock_layers",
        null=True,
        blank=True,
    )

    def __str__(self):
        return f"{self.branch_inventory_item.inventory_item.item_name} - Branch Stock Layer ({self.quantity_remaining} units at {self.unit_cost})"

    def get_institution(self):
        return self.branch_inventory_item.get_institution()

    class Meta:
        verbose_name = "Branch Inventory Item Stock Layer"
        verbose_name_plural = "Branch Inventory Item Stock Layers"
        db_table = "branch_inventory_item_stock_layers"
        ordering = ["-received_date"]

        constraints = [
            models.UniqueConstraint(
                fields=[
                    "branch_inventory_item",
                    "unit_of_measure",
                    "unit_cost",
                ],
                condition=models.Q(
                    deleted_at__isnull=True,
                    restored_from_movement__isnull=True,
                ),
                name="uniq_active_normal_branch_layer_cost",
            ),
            models.UniqueConstraint(
                fields=["restored_by_return_item", "restored_from_movement"],
                condition=models.Q(
                    deleted_at__isnull=True,
                    restored_by_return_item__isnull=False,
                    restored_from_movement__isnull=False,
                ),
                name="uniq_return_layer_issue_slice",
            ),
        ]

        indexes = [
            models.Index(
                fields=["branch_inventory_item", "deleted_at"],
                name="idx_layer_item_deleted",
            ),
        ]

    def clean(self):
        if self.unit_cost is not None and self.unit_cost <= 0:
            raise ValidationError(
                {
                    "unit_cost": "Stock must have a unit cost greater than zero. "
                    "For gifted stock, enter its assessed unit value."
                }
            )

        allows_oversell = getattr(
            self.branch_inventory_item.branch, "allow_sales_out_of_stock", False
        )
        if not allows_oversell and self.quantity_remaining < 0:
            raise ValidationError("Quantity remaining cannot be negative.")

        if self.received_date > timezone.now():
            raise ValidationError("Received date cannot be in the future.")

    def save(self, *args, **kwargs):
        self.full_clean()

        is_new = self._state.adding

        old_unit_cost = None

        if not is_new:
            old = BranchInventoryItemStockLayer.objects.filter(pk=self.pk).first()
            if old:
                old_unit_cost = old.unit_cost

        super().save(*args, **kwargs)

        if not is_new and old_unit_cost is not None and old_unit_cost != self.unit_cost:
            BranchInventoryItemPriceChange.objects.create(
                type_of_price_change="BUYING_PRICE",
                unit_of_measure=self,
                price_before=old_unit_cost,
                price_after=self.unit_cost,
            )


class BranchInventoryItemUnitOfMeasure(SoftDeletableTimeStampedModel):
    reference_prefix = "BIITMOUM"
    branch_inventory_item = models.ForeignKey(
        BranchInventoryItem, on_delete=models.CASCADE, related_name="units"
    )
    unit_of_measure = models.ForeignKey(ItemUnitOfMeasure, on_delete=models.CASCADE)
    conversion_factor = models.DecimalField(max_digits=50, decimal_places=20)
    selling_price = models.DecimalField(max_digits=50, decimal_places=20, default=0.00)

    is_base_unit_of_measure = models.BooleanField(default=False)

    other_quantity = models.DecimalField(
        max_digits=50,
        decimal_places=20,
        blank=True,
        null=True,
    )
    other_uom = models.ForeignKey(
        "items.ItemUnitOfMeasure",
        on_delete=models.CASCADE,
        blank=True,
        null=True,
        related_name="branch_inventory_item_uoms",
    )

    def __str__(self):
        return f"{self.branch_inventory_item.inventory_item.item_name} - {self.unit_of_measure.unit_name} (x{self.conversion_factor})"

    def clean(self):
        if self.is_base_unit_of_measure:
            existing_base_units = BranchInventoryItemUnitOfMeasure.objects.filter(
                branch_inventory_item=self.branch_inventory_item,
                is_base_unit_of_measure=True,
                deleted_at__isnull=True,
            ).exclude(id=self.id)

            if existing_base_units.exists():
                raise ValidationError(
                    "There is already a base unit of measure assigned to this inventory item."
                )

            if self.other_quantity is not None:
                raise validation_error(
                    "Other QTY should be empty for base unit of measure."
                )

            if self.other_uom is not None:
                raise validation_error(
                    "Other UOM should be empty for base unit of measure."
                )

    class Meta:
        unique_together = (
            "branch_inventory_item",
            "unit_of_measure",
        )
        verbose_name = "Branch Inventory Item Unit of Measure"
        verbose_name_plural = "Branch Inventory Item Units of Measure"

    def get_institution(self):
        return self.branch_inventory_item.get_institution()

    def save(self, *args, **kwargs):
        self.full_clean()

        is_new = self._state.adding

        old_price = None

        if not is_new:
            old = BranchInventoryItemUnitOfMeasure.objects.filter(pk=self.pk).first()
            if old:
                old_price = old.selling_price

        super().save(*args, **kwargs)

        if not is_new and old_price is not None and old_price != self.selling_price:
            BranchInventoryItemPriceChange.objects.create(
                type_of_price_change="SELLING_PRICE",
                unit_of_measure=self,
                price_before=old_price,
                price_after=self.selling_price,
            )


class StockToBranchAllocation(ReportableModelMixin, BaseApprovableModel):
    reference_prefix = "STBA"

    ALLOCATION_STATUS_CHOICES = [
        ("ALLOCATED", "Allocated"),
        ("PENDING", "Pending"),
        ("CANCELLED", "Cancelled"),
    ]

    alloc_status = models.CharField(
        max_length=10,
        choices=ALLOCATION_STATUS_CHOICES,
        default="PENDING",
    )

    allocation_date = models.DateTimeField(default=timezone.now)

    branch_to = models.ForeignKey(
        "institution.Branch",
        on_delete=models.CASCADE,
        related_name="allocations_from_main_stock_to_branch",
    )

    is_stock_moved = models.BooleanField(default=False)

    search_fields = [
        "branch_to__branch_name",
        "alloc_status",
    ]

    class Meta:
        verbose_name = "Stock to Branch Allocation"
        verbose_name_plural = "Stock to Branch Allocations"
        ordering = ["-created_at", "-allocation_date"]
        indexes = [
            models.Index(
                fields=[
                    "branch_to",
                    "alloc_status",
                    "allocation_date",
                    "created_at",
                ],
                name="stba_branch_status_date_idx",
            ),
        ]

    @classmethod
    def get_additional_filters(cls):
        return [
            "alloc_status",
            "is_stock_moved",
        ]

    @classmethod
    def get_filter_serializer_class(cls):
        from items.filters import StockToBranchAllocationFilterSerializer

        return StockToBranchAllocationFilterSerializer

    def get_institution(self):
        return self.branch_to.get_institution()

    @classmethod
    def get_institution_filter_field(cls):
        return "branch_to__institution"

    def finish_workflow(self, approval: Approval):
        with transaction.atomic():
            if approval.status == "completed":
                if approval.action.name in ["create", "update"]:
                    self.is_active = True

                    if not self.is_stock_moved:
                        self.move_stock_to_branch()

                    self.alloc_status = "ALLOCATED"

                elif approval.action.name == "delete":
                    self.is_active = False
                    self.deleted_at = timezone.now()
                    self.alloc_status = "CANCELLED"
            elif approval.status == "rejected":
                if approval.action.name == "create":
                    self.is_active = False
                    self.deleted_at = timezone.now()
                    self.alloc_status = "CANCELLED"

                elif approval.action.name in ["update", "delete"]:
                    self.is_active = False
                    self.deleted_at = None
                    self.alloc_status = "CANCELLED"

        self.save()

    @transaction.atomic
    def move_stock_to_branch(self):
        from items.unit_converter import (
            decompose_base_units,
            SMALLEST_ONLY,
        )
        from utilities.helpers import validation_error
        from decimal import Decimal

        institution = self.get_institution()
        allow_breakdown = getattr(institution, "allow_unit_breakdown", False)
        breakdown_strategy = getattr(
            institution, "unit_breakdown_strategy", SMALLEST_ONLY
        )

        for alloc_item in self.items.select_related("item", "unit_of_measure").all():
            inventory_item = alloc_item.item

            try:
                branch_inventory_item = BranchInventoryItem.objects.get(
                    inventory_item=inventory_item,
                    branch=self.branch_to,
                )
            except BranchInventoryItem.DoesNotExist:
                raise validation_error(
                    f"'{inventory_item.item_name}' is not assigned to branch '{self.branch_to.branch_name}'"
                )

            requested_uom = (
                alloc_item.unit_of_measure.unit_of_measure
                if alloc_item.unit_of_measure
                else None
            )
            requested_cf = self._get_layer_conversion_factor(
                inventory_item, requested_uom
            )

            order = "recieved_date"

            if allow_breakdown:
                requested_qty_in_base = Decimal(str(alloc_item.quantity)) * requested_cf

                stock_layers = (
                    InventoryItemStockLayer.objects.select_for_update()
                    .filter(
                        inventory_item=inventory_item,
                        deleted_at__isnull=True,
                        quantity_remaining__gt=0,
                    )
                    .order_by(order)
                )

                total_available_base = sum(
                    Decimal(str(l.quantity_remaining))
                    * self._get_layer_conversion_factor(
                        inventory_item, l.unit_of_measure
                    )
                    for l in stock_layers
                )
                if total_available_base < requested_qty_in_base:
                    raise validation_error(
                        f"Not enough stock for '{inventory_item.item_name}'. "
                        f"Requested: {alloc_item.quantity} {requested_uom.unit_name if requested_uom else 'units'} "
                        f"({requested_qty_in_base} base units), available: {total_available_base} base units."
                    )

                remaining_base = requested_qty_in_base

                for layer in stock_layers:
                    if remaining_base <= Decimal("0"):
                        break

                    layer_uom = layer.unit_of_measure
                    layer_cf = self._get_layer_conversion_factor(
                        inventory_item, layer_uom
                    )
                    layer_base_total = Decimal(str(layer.quantity_remaining)) * layer_cf

                    take_base = min(layer_base_total, remaining_base)
                    qty_before = Decimal(str(layer.quantity_remaining))

                    same_unit = (requested_uom is None) or (layer_uom == requested_uom)

                    if same_unit:
                        consume_qty = take_base / layer_cf
                        layer.quantity_remaining -= consume_qty
                        layer.save(update_fields=["quantity_remaining"])

                        if layer.quantity_remaining == 0:
                            layer.deleted_at = timezone.now()
                            layer.save(
                                update_fields=["deleted_at", "quantity_remaining"]
                            )

                        log_stock_movement(
                            movement_type="ALLOCATION_OUT",
                            inventory_item=inventory_item,
                            unit_of_measure=layer_uom,
                            quantity_change=-consume_qty,
                            quantity_before=qty_before,
                            unit_cost=layer.unit_cost,
                            institution=institution,
                            source_document=self,
                            source_reference=self.reference_code,
                        )

                        branch_units = consume_qty

                    else:
                        full_packs = take_base // layer_cf
                        leftover_base = take_base % layer_cf
                        partial_pack = leftover_base > Decimal("0")
                        packs_to_remove = full_packs + (
                            Decimal("1") if partial_pack else Decimal("0")
                        )

                        layer.quantity_remaining -= packs_to_remove
                        layer.save(update_fields=["quantity_remaining"])

                        if layer.quantity_remaining == 0:
                            layer.deleted_at = timezone.now()
                            layer.save(
                                update_fields=["deleted_at", "quantity_remaining"]
                            )

                        log_stock_movement(
                            movement_type="ALLOCATION_OUT",
                            inventory_item=inventory_item,
                            unit_of_measure=layer_uom,
                            quantity_change=-packs_to_remove,
                            quantity_before=qty_before,
                            unit_cost=layer.unit_cost,
                            institution=institution,
                            source_document=self,
                            source_reference=self.reference_code,
                        )

                        if partial_pack:
                            remainder_base = layer_cf - leftover_base
                            base_unit_cost = layer.unit_cost / layer_cf

                            decomposed = decompose_base_units(
                                remainder_base,
                                branch_inventory_item,
                                strategy=breakdown_strategy,
                            )

                            for remainder_uom, remainder_qty in decomposed:
                                remainder_cf = self._get_layer_conversion_factor(
                                    inventory_item, remainder_uom
                                )
                                prorated_cost = (
                                    base_unit_cost * remainder_cf
                                ).quantize(Decimal("0.0001"))

                                existing = InventoryItemStockLayer.objects.filter(
                                    inventory_item=inventory_item,
                                    unit_of_measure=remainder_uom,
                                    unit_cost=prorated_cost,
                                    deleted_at__isnull=True,
                                ).first()

                                if existing:
                                    log_remainder_before = Decimal(
                                        str(existing.quantity_remaining)
                                    )
                                    existing.quantity_remaining += remainder_qty
                                    existing.save(update_fields=["quantity_remaining"])
                                else:
                                    log_remainder_before = Decimal("0")
                                    InventoryItemStockLayer.objects.create(
                                        inventory_item=inventory_item,
                                        unit_of_measure=remainder_uom,
                                        unit_cost=prorated_cost,
                                        quantity_remaining=remainder_qty,
                                        recieved_date=layer.recieved_date,
                                    )

                                log_stock_movement(
                                    movement_type="UNIT_BREAKDOWN",
                                    inventory_item=inventory_item,
                                    unit_of_measure=remainder_uom,
                                    quantity_change=+remainder_qty,
                                    quantity_before=log_remainder_before,
                                    unit_cost=prorated_cost,
                                    institution=institution,
                                    source_document=self,
                                    source_reference=self.reference_code,
                                )

                        branch_units = take_base / requested_cf

                    branch_layer = BranchInventoryItemStockLayer.objects.filter(
                        branch_inventory_item=branch_inventory_item,
                        unit_cost=layer.unit_cost,
                        deleted_at__isnull=True,
                    ).first()

                    if branch_layer:
                        branch_qty_before = Decimal(
                            str(branch_layer.quantity_remaining)
                        )
                        branch_layer.quantity_remaining += branch_units
                        branch_layer.save(update_fields=["quantity_remaining"])
                    else:
                        branch_qty_before = Decimal("0")
                        BranchInventoryItemStockLayer.objects.create(
                            branch_inventory_item=branch_inventory_item,
                            unit_of_measure=requested_uom,
                            unit_cost=layer.unit_cost,
                            quantity_remaining=branch_units,
                            received_date=layer.recieved_date,
                        )

                    log_stock_movement(
                        movement_type="ALLOCATION_IN",
                        inventory_item=inventory_item,
                        unit_of_measure=requested_uom,
                        quantity_change=+branch_units,
                        quantity_before=branch_qty_before,
                        unit_cost=layer.unit_cost,
                        branch=self.branch_to,
                        source_document=self,
                        source_reference=self.reference_code,
                    )

                    remaining_base -= take_base

            else:
                layer_filter = dict(
                    inventory_item=inventory_item,
                    deleted_at__isnull=True,
                    quantity_remaining__gt=0,
                )
                if requested_uom is not None:
                    layer_filter["unit_of_measure"] = requested_uom

                stock_layers = (
                    InventoryItemStockLayer.objects.select_for_update()
                    .filter(**layer_filter)
                    .order_by(order)
                )

                total_available = sum(
                    Decimal(str(l.quantity_remaining)) for l in stock_layers
                )
                remaining = Decimal(str(alloc_item.quantity))

                if total_available < remaining:
                    all_layers = InventoryItemStockLayer.objects.filter(
                        inventory_item=inventory_item,
                        deleted_at__isnull=True,
                        quantity_remaining__gt=0,
                    )
                    layer_summary = ", ".join(
                        f"{l.quantity_remaining} @ UOM={l.unit_of_measure.unit_name if l.unit_of_measure else 'none'}"
                        for l in all_layers
                    )
                    raise validation_error(
                        f"Not enough stock for '{inventory_item.item_name}' in "
                        f"{requested_uom.unit_name if requested_uom else 'units'}. "
                        f"Available: {total_available}. All layers: [{layer_summary}]. "
                        f"Enable unit breakdown to allocate across UOMs."
                    )

                for layer in stock_layers:
                    if remaining <= Decimal("0"):
                        break

                    move_qty = min(Decimal(str(layer.quantity_remaining)), remaining)
                    qty_before = Decimal(str(layer.quantity_remaining))

                    layer.quantity_remaining -= move_qty
                    layer.save(update_fields=["quantity_remaining"])

                    if layer.quantity_remaining == 0:
                        layer.deleted_at = timezone.now()
                        layer.save(update_fields=["deleted_at", "quantity_remaining"])

                    log_stock_movement(
                        movement_type="ALLOCATION_OUT",
                        inventory_item=inventory_item,
                        unit_of_measure=layer.unit_of_measure,
                        quantity_change=-move_qty,
                        quantity_before=qty_before,
                        unit_cost=layer.unit_cost,
                        institution=institution,
                        source_document=self,
                        source_reference=self.reference_code,
                    )

                    branch_layer = BranchInventoryItemStockLayer.objects.filter(
                        branch_inventory_item=branch_inventory_item,
                        unit_cost=layer.unit_cost,
                        deleted_at__isnull=True,
                    ).first()

                    if branch_layer:
                        branch_qty_before = Decimal(
                            str(branch_layer.quantity_remaining)
                        )
                        branch_layer.quantity_remaining += move_qty
                        branch_layer.save(update_fields=["quantity_remaining"])
                    else:
                        branch_qty_before = Decimal("0")
                        BranchInventoryItemStockLayer.objects.create(
                            branch_inventory_item=branch_inventory_item,
                            unit_of_measure=layer.unit_of_measure,
                            unit_cost=layer.unit_cost,
                            quantity_remaining=move_qty,
                            received_date=layer.recieved_date,
                        )

                    log_stock_movement(
                        movement_type="ALLOCATION_IN",
                        inventory_item=inventory_item,
                        unit_of_measure=layer.unit_of_measure,
                        quantity_change=+move_qty,
                        quantity_before=branch_qty_before,
                        unit_cost=layer.unit_cost,
                        branch=self.branch_to,
                        source_document=self,
                        source_reference=self.reference_code,
                    )

                    remaining -= move_qty

        self.is_stock_moved = True
        self.save(update_fields=["is_stock_moved"])

    def _get_layer_conversion_factor(self, inventory_item, layer_uom) -> Decimal:
        if layer_uom is None:
            return Decimal("1")
        try:
            item_uom = InventoryItemUnitOfMeasure.objects.get(
                inventory_item=inventory_item,
                unit_of_measure=layer_uom,
                deleted_at__isnull=True,
            )
            return Decimal(str(item_uom.conversion_factor))
        except InventoryItemUnitOfMeasure.DoesNotExist:
            return Decimal("1")


class StockToBranchAllocationProduct(SoftDeletableTimeStampedModel):
    allocation = models.ForeignKey(
        StockToBranchAllocation, on_delete=models.CASCADE, related_name="items"
    )
    item = models.ForeignKey(
        "items.InventoryItem",
        on_delete=models.CASCADE,
        related_name="main_stock_to_branch_allocations",
    )

    unit_of_measure = models.ForeignKey(
        InventoryItemUnitOfMeasure,
        on_delete=models.CASCADE,
        blank=True,
        null=True,
    )

    quantity = models.DecimalField(max_digits=50, decimal_places=20)

    def __str__(self):
        return f"{self.allocation} - {self.item.item_name} - {self.quantity}"

    class Meta:
        unique_together = ("allocation", "item")
        verbose_name = "Stock to Branch Allocation Product"
        verbose_name_plural = "Stock to Branch Allocation Products"

    def save(self, *args, **kwargs):
        self.full_clean()
        super().save(*args, **kwargs)

    def clean(self):
        from utilities.helpers import validation_error

        if self.unit_of_measure:
            if self.unit_of_measure.inventory_item != self.item:
                raise validation_error(
                    "Unit of measure does not belong to the specified inventory item."
                )

        if self.unit_of_measure and self.allocation_id:
            branch = self.allocation.branch_to

            try:
                branch_inventory_item = BranchInventoryItem.objects.get(
                    inventory_item=self.item,
                    branch=branch,
                    deleted_at__isnull=True,
                )
            except BranchInventoryItem.DoesNotExist:
                if self._state.adding or not self.allocation_id:
                    return
                raise validation_error("Item is not configured on the target branch.")

            exists = BranchInventoryItemUnitOfMeasure.objects.filter(
                branch_inventory_item=branch_inventory_item,
                unit_of_measure=self.unit_of_measure.unit_of_measure,
                deleted_at__isnull=True,
            ).exists()

            if not exists:
                raise validation_error(
                    "This unit of measure is not enabled on the target branch."
                )


class BranchInventoryItemPriceChange(SoftDeletableTimeStampedModel):
    type_of_price_change = models.CharField(
        max_length=50,
        choices=[
            ("BUYING_PRICE", "Buying Price"),
            ("SELLING_PRICE", "Selling Price"),
        ],
        default="BUYING_PRICE",
    )

    unit_of_measure = models.ForeignKey(
        BranchInventoryItemUnitOfMeasure,
        on_delete=models.CASCADE,
        related_name="price_changes",
        blank=True,
        null=True,
    )

    price_before = models.DecimalField(max_digits=50, decimal_places=20)
    price_after = models.DecimalField(max_digits=50, decimal_places=20)

    class Meta:
        verbose_name = "Branch Inventory Item Price Change"
        verbose_name_plural = "Branch Inventory Item Price Changes"
        ordering = ["-created_at"]

    def __str__(self):
        return f"{self.unit_of_measure.branch_inventory_item.inventory_item.item_name} @ {self.unit_of_measure.branch_inventory_item.branch.branch_name} - {self.price_before} → {self.price_after}"


class BranchToBranchStockMovement(ReportableModelMixin, BaseApprovableModel):
    reference_prefix = "B2BSM"

    STOCK_MOVEMENT_STATUS_CHOICES = [
        ("ALLOCATED", "Allocated"),
        ("PENDING", "Pending"),
        ("CANCELLED", "Cancelled"),
    ]

    stock_movement_status = models.CharField(
        max_length=10,
        choices=STOCK_MOVEMENT_STATUS_CHOICES,
        default="PENDING",
    )

    stock_movement_date = models.DateTimeField(default=timezone.now)

    branch_from = models.ForeignKey(
        "institution.Branch",
        on_delete=models.CASCADE,
        related_name="outgoing_branch_stock_movements",
    )

    branch_to = models.ForeignKey(
        "institution.Branch",
        on_delete=models.CASCADE,
        related_name="incoming_branch_stock_movements",
    )

    is_stock_moved = models.BooleanField(default=False)

    search_fields = [
        "branch_from__branch_name",
        "branch_to__branch_name",
        "stock_movement_status",
    ]

    class Meta:
        verbose_name = "Branch to Branch Stock Movement"
        verbose_name_plural = "Branch to Branch Stock Movements"
        ordering = ["-created_at", "-stock_movement_date"]
        indexes = [
            models.Index(
                fields=[
                    "branch_from",
                    "stock_movement_status",
                    "stock_movement_date",
                    "created_at",
                ],
                name="b2b_from_status_date_idx",
            ),
            models.Index(
                fields=[
                    "branch_to",
                    "stock_movement_status",
                    "stock_movement_date",
                    "created_at",
                ],
                name="b2b_to_status_date_idx",
            ),
        ]

    def get_institution(self):
        return self.branch_from.institution

    def clean(self):
        from utilities.helpers import validation_error

        if self.branch_from_id and self.branch_to_id:
            if self.branch_from_id == self.branch_to_id:
                raise validation_error("Cannot move stock to the same branch.")

            if self.branch_from.institution_id != self.branch_to.institution_id:
                raise validation_error("Branches must belong to the same institution.")

    def save(self, *args, **kwargs):
        self.full_clean()
        super().save(*args, **kwargs)

    def finish_workflow(self, approval: Approval):
        with transaction.atomic():
            if approval.status == "completed":
                if approval.action.name in ["create", "update"]:
                    self.is_active = True

                    if not self.is_stock_moved:
                        self.move_stock_between_branches()

                    self.stock_movement_status = "ALLOCATED"

                elif approval.action.name == "delete":
                    self.is_active = False
                    self.deleted_at = timezone.now()
                    self.stock_movement_status = "CANCELLED"
            elif approval.status == "rejected":
                if approval.action.name == "create":
                    self.is_active = False
                    self.deleted_at = timezone.now()
                    self.stock_movement_status = "CANCELLED"

                elif approval.action.name in ["update", "delete"]:
                    self.is_active = False
                    self.deleted_at = None
                    self.stock_movement_status = "CANCELLED"

        self.save()

    @transaction.atomic
    def move_stock_between_branches(self):
        from utilities.helpers import validation_error
        from items.unit_converter import decompose_base_units, SMALLEST_ONLY
        from items.stock_logger import log_stock_movement

        if self.is_stock_moved:
            return

        institution = self.get_institution()
        allow_breakdown = getattr(institution, "allow_unit_breakdown", False)
        breakdown_strategy = getattr(
            institution, "unit_breakdown_strategy", SMALLEST_ONLY
        )

        for movement_item in self.items.select_related(
            "inventory_item", "unit_of_measure"
        ).all():
            source_branch_item = movement_item.inventory_item
            inventory_item = source_branch_item.inventory_item

            try:
                target_branch_item = BranchInventoryItem.objects.get(
                    inventory_item=inventory_item,
                    branch=self.branch_to,
                    deleted_at__isnull=True,
                )
            except BranchInventoryItem.DoesNotExist:
                raise validation_error(
                    f"Item '{inventory_item.item_name}' is not configured on branch '{self.branch_to.branch_name}'."
                )

            requested_uom = (
                movement_item.unit_of_measure.unit_of_measure
                if movement_item.unit_of_measure
                else None
            )

            def get_cf(branch_item, uom):
                """Helper: get conversion factor from BranchInventoryItemUnitOfMeasure."""
                if uom is None:
                    return Decimal("1")
                record = BranchInventoryItemUnitOfMeasure.objects.filter(
                    branch_inventory_item=branch_item,
                    unit_of_measure=uom,
                    deleted_at__isnull=True,
                ).first()
                if record:
                    return Decimal(str(record.conversion_factor))
                return Decimal("1")

            requested_cf = get_cf(source_branch_item, requested_uom)
            remaining_qty = Decimal(str(movement_item.quantity))

            if allow_breakdown:
                requested_qty_in_base = remaining_qty * requested_cf

                stock_layers = (
                    BranchInventoryItemStockLayer.objects.select_for_update()
                    .filter(
                        branch_inventory_item=source_branch_item,
                        deleted_at__isnull=True,
                        quantity_remaining__gt=0,
                    )
                    .order_by("received_date")
                )

                total_available_base = sum(
                    Decimal(str(l.quantity_remaining))
                    * get_cf(source_branch_item, l.unit_of_measure)
                    for l in stock_layers
                )

                if total_available_base < requested_qty_in_base:
                    raise validation_error(
                        f"Not enough stock for '{inventory_item.item_name}' in branch '{self.branch_from.branch_name}'. "
                        f"Requested: {movement_item.quantity} {requested_uom.unit_name if requested_uom else 'units'} "
                        f"({requested_qty_in_base} base units), available: {total_available_base} base units."
                    )

                remaining_base = requested_qty_in_base

                for layer in stock_layers:
                    if remaining_base <= Decimal("0"):
                        break

                    layer_uom = layer.unit_of_measure
                    layer_cf = get_cf(source_branch_item, layer_uom)
                    layer_base_total = Decimal(str(layer.quantity_remaining)) * layer_cf

                    take_base = min(layer_base_total, remaining_base)
                    qty_before = Decimal(str(layer.quantity_remaining))

                    same_unit = (requested_uom is None) or (layer_uom == requested_uom)

                    if same_unit:
                        consume_qty = take_base / layer_cf
                        layer.quantity_remaining -= consume_qty
                        layer.save(update_fields=["quantity_remaining"])

                        if layer.quantity_remaining == 0:
                            layer.deleted_at = timezone.now()
                            layer.save(
                                update_fields=["deleted_at", "quantity_remaining"]
                            )

                        log_stock_movement(
                            movement_type="BRANCH_TRANSFER_OUT",
                            inventory_item=inventory_item,
                            unit_of_measure=layer_uom,
                            quantity_change=-consume_qty,
                            quantity_before=qty_before,
                            unit_cost=layer.unit_cost,
                            branch=self.branch_from,
                            source_document=self,
                            source_reference=self.reference_code,
                            notes=f"Stock transferred to branch '{self.branch_to.branch_name}'",
                        )

                        branch_units = consume_qty

                    else:
                        full_packs = take_base // layer_cf
                        leftover_base = take_base % layer_cf
                        partial_pack = leftover_base > Decimal("0")
                        packs_to_remove = full_packs + (
                            Decimal("1") if partial_pack else Decimal("0")
                        )

                        layer.quantity_remaining -= packs_to_remove
                        layer.save(update_fields=["quantity_remaining"])

                        if layer.quantity_remaining == 0:
                            layer.deleted_at = timezone.now()
                            layer.save(
                                update_fields=["deleted_at", "quantity_remaining"]
                            )

                        log_stock_movement(
                            movement_type="BRANCH_TRANSFER_OUT",
                            inventory_item=inventory_item,
                            unit_of_measure=layer_uom,
                            quantity_change=-packs_to_remove,
                            quantity_before=qty_before,
                            unit_cost=layer.unit_cost,
                            branch=self.branch_from,
                            source_document=self,
                            source_reference=self.reference_code,
                            notes=f"Stock transferred to branch '{self.branch_to.branch_name}'",
                        )

                        if partial_pack:
                            remainder_base = layer_cf - leftover_base
                            base_unit_cost = layer.unit_cost / layer_cf

                            decomposed = decompose_base_units(
                                remainder_base,
                                source_branch_item,
                                strategy=breakdown_strategy,
                            )

                            for remainder_uom, remainder_qty in decomposed:
                                remainder_cf = get_cf(source_branch_item, remainder_uom)
                                prorated_cost = (
                                    base_unit_cost * remainder_cf
                                ).quantize(Decimal("0.0001"))

                                remainder_layer = (
                                    BranchInventoryItemStockLayer.objects.filter(
                                        branch_inventory_item=source_branch_item,
                                        unit_cost=prorated_cost,
                                        deleted_at__isnull=True,
                                    ).first()
                                )

                                if remainder_layer:
                                    log_rem_before = Decimal(
                                        str(remainder_layer.quantity_remaining)
                                    )
                                    remainder_layer.quantity_remaining += remainder_qty
                                    remainder_layer.save(
                                        update_fields=["quantity_remaining"]
                                    )
                                else:
                                    log_rem_before = Decimal("0")
                                    BranchInventoryItemStockLayer.objects.create(
                                        branch_inventory_item=source_branch_item,
                                        unit_of_measure=remainder_uom,
                                        unit_cost=prorated_cost,
                                        quantity_remaining=remainder_qty,
                                        received_date=layer.received_date,
                                    )

                                log_stock_movement(
                                    movement_type="UNIT_BREAKDOWN",
                                    inventory_item=inventory_item,
                                    unit_of_measure=remainder_uom,
                                    quantity_change=+remainder_qty,
                                    quantity_before=log_rem_before,
                                    unit_cost=prorated_cost,
                                    branch=self.branch_from,
                                    source_document=self,
                                    source_reference=self.reference_code,
                                )

                        branch_units = take_base / requested_cf

                    target_layer = BranchInventoryItemStockLayer.objects.filter(
                        branch_inventory_item=target_branch_item,
                        unit_cost=layer.unit_cost,
                        deleted_at__isnull=True,
                    ).first()

                    if target_layer:
                        target_qty_before = Decimal(
                            str(target_layer.quantity_remaining)
                        )
                        target_layer.quantity_remaining += branch_units
                        target_layer.save(update_fields=["quantity_remaining"])
                    else:
                        target_qty_before = Decimal("0")
                        BranchInventoryItemStockLayer.objects.create(
                            branch_inventory_item=target_branch_item,
                            unit_of_measure=requested_uom,
                            unit_cost=layer.unit_cost,
                            quantity_remaining=branch_units,
                            received_date=layer.received_date,
                            source_branch=self.branch_from,
                        )

                    log_stock_movement(
                        movement_type="BRANCH_TRANSFER_IN",
                        inventory_item=inventory_item,
                        unit_of_measure=requested_uom,
                        quantity_change=+branch_units,
                        quantity_before=target_qty_before,
                        unit_cost=layer.unit_cost,
                        branch=self.branch_to,
                        source_document=self,
                        source_reference=self.reference_code,
                        notes=f"Stock received from branch '{self.branch_from.branch_name}'",
                    )

                    remaining_base -= take_base

            else:
                stock_layers = (
                    BranchInventoryItemStockLayer.objects.select_for_update()
                    .filter(
                        branch_inventory_item=source_branch_item,
                        unit_of_measure=requested_uom,
                        quantity_remaining__gt=0,
                        deleted_at__isnull=True,
                    )
                    .order_by("received_date")
                )

                total_available = stock_layers.aggregate(
                    total=models.Sum("quantity_remaining")
                )["total"] or Decimal("0")

                if total_available < remaining_qty:
                    raise validation_error(
                        f"Not enough stock for '{inventory_item.item_name}' in "
                        f"{requested_uom.unit_name if requested_uom else 'units'} "
                        f"at branch '{self.branch_from.branch_name}'. "
                        f"Available: {total_available}. "
                        f"Enable unit breakdown to allocate across UOMs."
                    )

                for layer in stock_layers:
                    if remaining_qty <= Decimal("0"):
                        break

                    move_qty = min(
                        Decimal(str(layer.quantity_remaining)), remaining_qty
                    )
                    qty_before = Decimal(str(layer.quantity_remaining))

                    layer.quantity_remaining -= move_qty
                    layer.save(update_fields=["quantity_remaining"])

                    if layer.quantity_remaining == 0:
                        layer.deleted_at = timezone.now()
                        layer.save(update_fields=["deleted_at", "quantity_remaining"])

                    log_stock_movement(
                        movement_type="BRANCH_TRANSFER_OUT",
                        inventory_item=inventory_item,
                        unit_of_measure=layer.unit_of_measure,
                        quantity_change=-move_qty,
                        quantity_before=qty_before,
                        unit_cost=layer.unit_cost,
                        branch=self.branch_from,
                        source_document=self,
                        source_reference=self.reference_code,
                        notes=f"Stock transferred to branch '{self.branch_to.branch_name}'",
                    )

                    target_layer = BranchInventoryItemStockLayer.objects.filter(
                        branch_inventory_item=target_branch_item,
                        unit_cost=layer.unit_cost,
                        deleted_at__isnull=True,
                    ).first()

                    if target_layer:
                        target_qty_before = Decimal(
                            str(target_layer.quantity_remaining)
                        )
                        target_layer.quantity_remaining += move_qty
                        target_layer.save(update_fields=["quantity_remaining"])
                    else:
                        target_qty_before = Decimal("0")
                        BranchInventoryItemStockLayer.objects.create(
                            branch_inventory_item=target_branch_item,
                            unit_of_measure=layer.unit_of_measure,
                            unit_cost=layer.unit_cost,
                            quantity_remaining=move_qty,
                            received_date=layer.received_date,
                            source_branch=self.branch_from,
                        )

                    log_stock_movement(
                        movement_type="BRANCH_TRANSFER_IN",
                        inventory_item=inventory_item,
                        unit_of_measure=layer.unit_of_measure,
                        quantity_change=+move_qty,
                        quantity_before=target_qty_before,
                        unit_cost=layer.unit_cost,
                        branch=self.branch_to,
                        source_document=self,
                        source_reference=self.reference_code,
                        notes=f"Stock received from branch '{self.branch_from.branch_name}'",
                    )

                    remaining_qty -= move_qty

        self.is_stock_moved = True
        self.stock_movement_status = "ALLOCATED"
        self.save(update_fields=["is_stock_moved", "stock_movement_status"])


class BranchToBranchStockMovementItem(SoftDeletableTimeStampedModel):
    stock_movement = models.ForeignKey(
        BranchToBranchStockMovement,
        on_delete=models.CASCADE,
        related_name="items",
    )

    inventory_item = models.ForeignKey(
        BranchInventoryItem,
        on_delete=models.CASCADE,
        related_name="branch_to_branch_stock_movement_items",
    )

    unit_of_measure = models.ForeignKey(
        BranchInventoryItemUnitOfMeasure,
        on_delete=models.CASCADE,
        blank=True,
        null=True,
    )

    quantity = models.DecimalField(max_digits=50, decimal_places=20)

    class Meta:
        unique_together = ("stock_movement", "inventory_item")
        verbose_name = "Branch to Branch Stock Movement Item"
        verbose_name_plural = "Branch to Branch Stock Movement Items"

    def __str__(self):
        return (
            f"{self.stock_movement.reference_code} - "
            f"{self.inventory_item.item_name} - "
            f"{self.quantity}"
        )

    def clean(self):
        from utilities.helpers import validation_error

        if self.unit_of_measure:
            if self.unit_of_measure.branch_inventory_item.id != self.inventory_item.id:
                raise validation_error(
                    "Unit of measure does not belong to the specified inventory item."
                )

    def save(self, *args, **kwargs):
        self.full_clean()
        super().save(*args, **kwargs)


class WriteOff(BaseApprovableModel, ReportableModelMixin):
    reference_prefix = "V-WO"

    REASON_CHOICES = [
        ("damaged", "Damaged"),
        ("expired", "Expired"),
        ("lost", "Lost"),
        ("obsolete", "Obsolete"),
        ("stolen", "Stolen"),
        ("other", "Other"),
    ]

    institution = models.ForeignKey(
        "institution.Institution",
        on_delete=models.CASCADE,
        related_name="write_offs",
        null=True,
        blank=True,
    )

    branch = models.ForeignKey(
        "institution.Branch",
        on_delete=models.CASCADE,
        related_name="write_offs",
        null=True,
        blank=True,
    )

    reason = models.CharField(
        max_length=50,
        choices=REASON_CHOICES,
        default="other",
    )

    write_off_date = models.DateField(
        default=timezone.now,
    )

    status = models.CharField(
        max_length=20,
        default="draft",
        choices=[
            ("draft", "Draft"),
            ("approved", "Approved"),
            ("completed", "Completed"),
            ("cancelled", "Cancelled"),
        ],
    )

    are_journal_entries_made = models.BooleanField(default=False)

    expense_account = models.ForeignKey(
        "accounts.Account",
        on_delete=models.CASCADE,
        help_text="The expense/loss account to debit for this write-off.",
        null=True,
        blank=True,
    )

    class Meta:
        ordering = ["-created_at"]
        verbose_name = "Write Off"
        verbose_name_plural = "Write Offs"

    def __str__(self):
        return f"Write Off {self.reference_code}"

    def get_institution(self):
        return self.institution or (self.branch.institution if self.branch else None)

    def finish_workflow(self, approval: Approval):
        with transaction.atomic():
            if approval.status == "completed":
                if approval.action.name in ["create", "update"]:
                    self.is_active = True
                    self.status = "approved"
                    if not self.are_journal_entries_made:
                        self._process_financial_events()

                    self.send_write_off_email()

                elif approval.action.name == "delete":
                    self.is_active = False
                    self.deleted_at = timezone.now()
            elif approval.status == "rejected":
                if approval.action.name == "create":
                    self.is_active = False
                else:
                    self.deleted_at = None

            self.save()

    def clean(self):

        if not self.institution and not self.branch:
            raise validation_error(
                "Write-off must belong to either an institution or a branch."
            )

        if self.institution and self.branch:
            raise validation_error(
                "Write-off cannot belong to both institution and branch."
            )

    def save(self, *args, **kwargs):
        self.full_clean()
        super().save(*args, **kwargs)

    @transaction.atomic
    def _process_financial_events(self):
        from accounts.utils import get_or_create_default_account
        from utilities.helpers import get_fiscal_year
        from transactions.services import (
            JournalPostingService,
            JournalLine,
            LEDGER_PRECISION,
        )
        from decimal import ROUND_HALF_UP

        if self.are_journal_entries_made:
            return

        institution_line_items = []
        branch_line_items = []

        if self.institution:
            institution_line_items = self.institution_wo_line_items.all()
        elif self.branch:
            branch_line_items = self.branch_wo_line_items.all()

        if (
            self.institution
            and institution_line_items.count() == 0
            or self.branch
            and branch_line_items.count() == 0
        ):
            return

        total_amount = Decimal("0.00")

        institution = self.get_institution()

        fiscal_year = get_fiscal_year(
            institution, self.write_off_date or timezone.now() or None
        )

        expense_account = self.expense_account or get_or_create_default_account(
            institution, "sgna_account"
        )

        journal_lines = []

        if institution_line_items:
            for item in institution_line_items:
                line_cost = self.consume_stock_layers(
                    is_branch_based=False,
                    stock_object=item.inventory_item,
                    unit_of_measure=item.inventory_item_unit_of_measure.unit_of_measure,
                    quantity=item.quantity,
                )

                line_cost = line_cost.quantize(LEDGER_PRECISION, rounding=ROUND_HALF_UP)
                if line_cost == 0:
                    continue

                total_amount += line_cost

                inventory_account = (
                    item.inventory_item.inventory_account
                    or get_or_create_default_account(
                        institution,
                        "inventory_account",
                    )
                )

                journal_lines.append(
                    JournalLine(
                        account=inventory_account,
                        entry_type="credit",
                        transaction_amount=line_cost,
                        description=f"Inventory write-off - {self.reason}",
                        transaction_currency=institution.currency,
                    )
                )

        if branch_line_items:
            for item in branch_line_items:
                line_cost = self.consume_stock_layers(
                    is_branch_based=True,
                    stock_object=item.branch_inventory_item,
                    unit_of_measure=item.branch_item_unit_of_measure.unit_of_measure,
                    quantity=item.quantity,
                )

                line_cost = line_cost.quantize(LEDGER_PRECISION, rounding=ROUND_HALF_UP)
                if line_cost == 0:
                    continue

                total_amount += line_cost

                inventory_account = (
                    item.branch_inventory_item.inventory_item.inventory_account
                    or get_or_create_default_account(
                        institution,
                        "inventory_account",
                    )
                )

                journal_lines.append(
                    JournalLine(
                        account=inventory_account,
                        entry_type="credit",
                        transaction_amount=line_cost,
                        description=f"Inventory write-off - {self.reason}",
                        transaction_currency=institution.currency,
                    )
                )

        if not journal_lines:
            WriteOff.objects.filter(id=self.id).update(are_journal_entries_made=True)
            self.refresh_from_db(fields=["are_journal_entries_made"])
            return

        journal_lines.append(
            JournalLine(
                account=expense_account,
                entry_type="debit",
                transaction_amount=total_amount,
                transaction_currency=institution.currency,
                description=f"Write-off {self.reference_code} - {self.reason}",
            )
        )

        JournalPostingService.post(
            fiscal_year=fiscal_year,
            title=f"Write-off {self.reference_code}",
            description=f"Write-off {self.reference_code} - {self.reason}",
            lines=journal_lines,
            transaction_date=self.write_off_date or timezone.now() or None,
            branch=self.branch or None,
            content_type=ContentType.objects.get_for_model(self.__class__),
            object_id=self.id,
        )

        WriteOff.objects.filter(id=self.id).update(are_journal_entries_made=True)
        self.refresh_from_db(fields=["are_journal_entries_made"])

    def send_write_off_email(self):
        institution = self.get_institution()
        branch = self.branch

        recipients = []

        if institution and institution.institution_email:
            recipients.append(institution.institution_email)

        if branch and branch.branch_email:
            recipients.append(branch.branch_email)

        if not recipients:
            return

        if institution:
            line_items = self.institution_wo_line_items.filter(deleted_at__isnull=True)
        elif branch:
            line_items = self.branch_wo_line_items.filter(deleted_at__isnull=True)
        else:
            line_items = []

        subject = f"Write-Off {self.reference_code} - {self.get_reason_display()}"

        context = {
            "reference_code": self.reference_code,
            "reason": self.get_reason_display(),
            "status": self.status.replace("_", " ").title(),
            "write_off_date": self.write_off_date.strftime("%B %d, %Y"),
            "institution_name": institution.institution_name if institution else "",
            "branch_name": branch.branch_name if branch else "",
            "line_items": [
                {
                    "name": (
                        item.inventory_item.item_name
                        if hasattr(item, "inventory_item") and item.inventory_item
                        else (
                            item.branch_inventory_item.inventory_item.item_name
                            if hasattr(item, "branch_inventory_item")
                            and item.branch_inventory_item
                            else "N/A"
                        )
                    ),
                    "quantity": item.quantity,
                }
                for item in line_items
            ],
        }

        EmailClient.send(
            subject=subject,
            recipients=recipients,
            template_html="emails/write_off_email.html",
            context=context,
        )

    @transaction.atomic
    def consume_stock_layers(
        self,
        is_branch_based: bool,
        stock_object,
        unit_of_measure,
        quantity: Decimal,
    ):
        institution = self.get_institution()

        strategy = (
            institution.default_stock_movement_strategy.code
            if institution.default_stock_movement_strategy
            else "FIFO"
        )

        remaining_quantity = quantity
        total_cost = Decimal("0.00")

        if is_branch_based:
            layer_model = BranchInventoryItemStockLayer
            filter_kwargs = {
                "branch_inventory_item": stock_object,
                "unit_of_measure": unit_of_measure,
                "deleted_at__isnull": True,
                "quantity_remaining__gt": 0,
            }
            date_field = "received_date"
            inventory_item = stock_object.inventory_item
            branch = stock_object.branch
            log_institution = None

        else:
            layer_model = InventoryItemStockLayer
            filter_kwargs = {
                "inventory_item": stock_object,
                "unit_of_measure": unit_of_measure,
                "deleted_at__isnull": True,
                "quantity_remaining__gt": 0,
            }
            date_field = "recieved_date"
            inventory_item = stock_object
            branch = None
            log_institution = institution

        layers = layer_model.objects.select_for_update().filter(**filter_kwargs)

        if strategy == "FIFO":
            layers = layers.order_by(date_field)
        else:
            layers = layers.order_by(f"-{date_field}")

        for layer in layers:
            if remaining_quantity <= 0:
                break

            available_qty = layer.quantity_remaining
            consume_qty = min(available_qty, remaining_quantity)

            qty_before = Decimal(layer.quantity_remaining)
            layer_cost = consume_qty * layer.unit_cost
            total_cost += layer_cost

            layer.quantity_remaining -= consume_qty
            layer.save(update_fields=["quantity_remaining"])
            remaining_quantity -= consume_qty

            log_stock_movement(
                movement_type="WRITE_OFF",
                inventory_item=inventory_item,
                unit_of_measure=unit_of_measure,
                quantity_change=-consume_qty,
                quantity_before=qty_before,
                unit_cost=layer.unit_cost,
                branch=branch,
                institution=log_institution,
                source_document=self,
                source_reference=self.reference_code,
            )

        if remaining_quantity > 0:
            raise validation_error(
                "Not enough stock available to consume for this write-off."
            )

        return total_cost


class InventoryItemWriteOffLineItem(SoftDeletableTimeStampedModel):
    write_off = models.ForeignKey(
        WriteOff,
        on_delete=models.CASCADE,
        related_name="institution_wo_line_items",
    )

    inventory_item = models.ForeignKey(
        "items.InventoryItem",
        on_delete=models.CASCADE,
        related_name="institution_write_off_line_items",
        null=True,
        blank=True,
    )

    inventory_item_unit_of_measure = models.ForeignKey(
        "items.InventoryItemUnitOfMeasure",
        on_delete=models.CASCADE,
        related_name="institution_write_off_line_items",
        null=True,
        blank=True,
    )

    quantity = models.PositiveIntegerField(default=1)

    class Meta:
        ordering = ["-created_at"]
        verbose_name = "Institution Inventory Item Write Off Line Item"
        verbose_name_plural = "Institution Inventory Item Write Off Line Items"

    def __str__(self):
        return f"{self.get_item_type_display()} x{self.quantity}"

    def clean(self):
        if self.inventory_item.item_type == "SERVICES":
            raise validation_error("Cannot write off service items.")

        if not self.inventory_item:
            raise validation_error("Inventory item must be specified.")

        if self.inventory_item and self.inventory_item_unit_of_measure:
            uom = self.inventory_item_unit_of_measure.unit_of_measure
            quantity = Decimal(str(self.quantity or 1))

            available = InventoryItemStockLayer.objects.active().filter(
                inventory_item=self.inventory_item,
                unit_of_measure=uom,
                quantity_remaining__gt=0,
            ).aggregate(total=models.Sum("quantity_remaining"))["total"] or Decimal("0")

            if available < quantity:
                raise ValidationError(
                    f"Insufficient stock for '{self.inventory_item.item_name}' "
                    f"({uom.unit_name}): requested {quantity}, available {available}."
                )

    def save(self, *args, **kwargs):
        self.full_clean()
        super().save(*args, **kwargs)

    def get_item_type_display(self):
        return self.inventory_item.item_name if self.inventory_item else "N/A"


class BranchInventorytemWriteOffLineItem(SoftDeletableTimeStampedModel):
    write_off = models.ForeignKey(
        WriteOff,
        on_delete=models.CASCADE,
        related_name="branch_wo_line_items",
    )

    branch_inventory_item = models.ForeignKey(
        "items.BranchInventoryItem",
        on_delete=models.CASCADE,
        related_name="branch_write_off_line_items",
        null=True,
        blank=True,
    )
    branch_item_unit_of_measure = models.ForeignKey(
        "items.BranchInventoryItemUnitOfMeasure",
        on_delete=models.CASCADE,
        related_name="branch_write_off_line_items",
        null=True,
        blank=True,
    )

    quantity = models.PositiveIntegerField(default=1)

    class Meta:
        ordering = ["-created_at"]
        verbose_name = "Branch Inventory Item Write Off Line Item"
        verbose_name_plural = "Branch Inventory Item Write Off Line Items"

    def __str__(self):
        return f"{self.get_item_type_display()} x{self.quantity}"

    def clean(self):
        if self.branch_inventory_item.inventory_item.item_type == "SERVICES":
            raise validation_error("Cannot write off service items.")

        if not self.branch_inventory_item:
            raise validation_error("Branch inventory item must be specified.")

        if self.branch_inventory_item and self.branch_item_unit_of_measure:
            uom = self.branch_item_unit_of_measure.unit_of_measure
            quantity = Decimal(str(self.quantity or 1))

            available = BranchInventoryItemStockLayer.objects.active().filter(
                branch_inventory_item=self.branch_inventory_item,
                unit_of_measure=uom,
                quantity_remaining__gt=0,
            ).aggregate(total=models.Sum("quantity_remaining"))["total"] or Decimal("0")

            if available < quantity:
                raise ValidationError(
                    f"Insufficient stock for "
                    f"'{self.branch_inventory_item.inventory_item.item_name}' "
                    f"({uom.unit_name}) at '{self.branch_inventory_item.branch.branch_name}': "
                    f"requested {quantity}, available {available}."
                )

    def save(self, *args, **kwargs):
        self.full_clean()
        super().save(*args, **kwargs)

    def get_item_type_display(self):
        return (
            self.branch_inventory_item.inventory_item.item_name
            if self.branch_inventory_item
            else "N/A"
        )


class StockMovementLog(SoftDeletableTimeStampedModel):
    MOVEMENT_TYPE_CHOICES = [
        ("BILL_RECEIPT", "Bill Receipt"),
        ("GRN_RECEIPT", "GRN Receipt"),
        ("ALLOCATION_IN", "Allocation In"),
        ("BRANCH_TRANSFER_IN", "Branch Transfer In"),
        ("RETURN_RESTOCK", "Return Restock"),
        ("OPENING_STOCK", "Opening Stock"),
        ("INVOICE_SALE", "Invoice Sale"),
        ("GIN_ISSUE", "GIN Issue"),
        ("ALLOCATION_OUT", "Allocation Out"),
        ("BRANCH_TRANSFER_OUT", "Branch Transfer Out"),
        ("WRITE_OFF", "Write Off"),
        ("RETURN_CONSUMED", "Return Consumed"),
        ("UNIT_BREAKDOWN", "Unit Breakdown"),
        ("MANUFACTURING_CONSUMPTION", "Manufacturing Consumption"),
        ("NEGATIVE_SALE", "Negative Sale"),
        ("NEGATIVE_SETTLEMENT", "Negative Settlement"),
        ("COST_VARIANCE", "Cost Variance"),
    ]

    LEVEL_CHOICES = [
        ("institution", "Institution / Warehouse"),
        ("branch", "Branch"),
    ]

    movement_type = models.CharField(max_length=30, choices=MOVEMENT_TYPE_CHOICES)
    stock_level = models.CharField(max_length=15, choices=LEVEL_CHOICES)
    quantity_change = models.DecimalField(
        max_digits=50,
        decimal_places=20,
        help_text="Positive = stock added, Negative = stock removed",
    )
    quantity_before = models.DecimalField(max_digits=50, decimal_places=20)
    quantity_after = models.DecimalField(max_digits=50, decimal_places=20)
    unit_cost = models.DecimalField(max_digits=50, decimal_places=20, default=0)
    movement_date = models.DateTimeField(default=timezone.now)

    inventory_item = models.ForeignKey(
        InventoryItem,
        on_delete=models.CASCADE,
        related_name="stock_movement_logs",
    )
    unit_of_measure = models.ForeignKey(
        ItemUnitOfMeasure,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
    )

    institution = models.ForeignKey(
        "institution.Institution",
        on_delete=models.CASCADE,
        related_name="stock_movement_logs",
    )
    branch = models.ForeignKey(
        "institution.Branch",
        on_delete=models.CASCADE,
        null=True,
        blank=True,
        related_name="stock_movement_logs",
    )

    content_type = models.ForeignKey(
        ContentType, on_delete=models.SET_NULL, null=True, blank=True
    )
    object_id = models.PositiveIntegerField(null=True, blank=True)
    source_document = GenericForeignKey("content_type", "object_id")
    source_reference = models.CharField(
        max_length=100,
        blank=True,
        null=True,
        help_text="Human-readable reference code of the source document",
    )

    goods_issued_note_line = models.ForeignKey(
        "customers.GoodsIssuedNoteLineItem",
        on_delete=models.PROTECT,
        related_name="stock_movements",
        null=True,
        blank=True,
    )
    item_return_item = models.ForeignKey(
        "customers.ItemReturnItem",
        on_delete=models.PROTECT,
        related_name="stock_movements",
        null=True,
        blank=True,
    )
    reverses_movement = models.ForeignKey(
        "self",
        on_delete=models.PROTECT,
        related_name="return_movements",
        null=True,
        blank=True,
    )

    class Meta:
        ordering = ["-movement_date"]
        indexes = [
            models.Index(fields=["inventory_item", "movement_date"]),
            models.Index(
                fields=["institution", "-movement_date", "-id"],
                condition=models.Q(deleted_at__isnull=True),
                name="stocklog_inst_date_id_idx",
            ),
            models.Index(
                fields=["branch", "-movement_date", "-id"],
                condition=models.Q(deleted_at__isnull=True),
                name="stocklog_branch_date_id_idx",
            ),
            models.Index(fields=["movement_type"]),
        ]
        constraints = [
            models.UniqueConstraint(
                fields=["item_return_item", "reverses_movement"],
                condition=models.Q(
                    movement_type="RETURN_RESTOCK",
                    deleted_at__isnull=True,
                    item_return_item__isnull=False,
                    reverses_movement__isnull=False,
                ),
                name="uniq_return_movement_issue_slice",
            ),
        ]
        verbose_name = "Stock Movement Log"
        verbose_name_plural = "Stock Movement Logs"

    def __str__(self):
        location = (
            self.branch.branch_name
            if self.branch
            else (self.institution.institution_name if self.institution else "?")
        )
        return (
            f"{self.movement_type} | {self.inventory_item.item_name} | "
            f"{'+' if self.quantity_change >= 0 else ''}{self.quantity_change} @ {location}"
        )

    @property
    def location(self):
        if self.branch:
            return self.branch.branch_name
        if self.institution:
            return self.institution.institution_name
        return "-"
