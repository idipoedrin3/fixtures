from django.contrib import admin
from .models import (
    InventoryItemWriteOffLineItem,
    ItemCategory,
    ItemUnitOfMeasure,
    ItemVendor,
    ItemVendorUnitPrice,
    InventoryItem,
    FiscalYear,
    StockMovementLog,
    StockToBranchAllocationProduct,
    StockToBranchAllocation,
    BranchInventoryItem,
    BranchInventoryItemStockLayer,
    InventoryItemStockLayer,
    InventoryItemUnitOfMeasure,
    BranchInventoryItemUnitOfMeasure,
    BranchInventoryItemPriceChange,
    BranchToBranchStockMovement,
    BranchToBranchStockMovementItem,
    WriteOff,
    BranchInventorytemWriteOffLineItem,
    InventoryItemPriceChange,
)


@admin.register(ItemCategory)
class ItemCategoryAdmin(admin.ModelAdmin):
    list_display = ("name", "institution", "is_active", "created_at")
    list_filter = ("institution", "is_active")
    search_fields = ("name", "institution__institution_name")
    list_select_related = ("institution",)
    ordering = ("institution", "name")


@admin.register(ItemUnitOfMeasure)
class ItemUnitOfMeasureAdmin(admin.ModelAdmin):
    list_display = (
        "unit_name",
        "unit_abbreviation",
        "institution",
        "is_active",
        "created_at",
    )
    list_filter = ("institution", "is_active")
    search_fields = (
        "unit_name",
        "unit_abbreviation",
        "description",
        "institution__institution_name",
    )
    list_select_related = ("institution",)
    ordering = ("institution", "unit_name")


@admin.register(InventoryItem)
class InventoryItemAdmin(admin.ModelAdmin):
    list_display = (
        "reference_code",
        "item_name",
        "item_type",
        "item_category",
        "get_institution",
        "can_be_sold",
        "can_be_purchased",
        "reorder_point",
        "is_active",
        "created_at",
    )
    list_filter = (
        "item_type",
        "can_be_sold",
        "can_be_purchased",
        "is_active",
        "item_category__institution",
        "item_category",
    )
    search_fields = (
        "reference_code",
        "item_name",
        "item_category__name",
        "item_category__institution__institution_name",
    )
    raw_id_fields = (
        "item_category",
        "inventory_account",
        "revenue_account",
        "expense_account",
    )
    list_select_related = ("item_category", "item_category__institution")
    ordering = ("item_category__institution", "item_name")

    @admin.display(description="Institution")
    def get_institution(self, obj):
        return obj.item_category.institution


@admin.register(InventoryItemUnitOfMeasure)
class InventoryItemUnitOfMeasureAdmin(admin.ModelAdmin):
    list_display = (
        "inventory_item",
        "unit_of_measure",
        "conversion_factor",
        "selling_price",
        "is_base_unit_of_measure",
        "created_at",
    )
    list_filter = (
        "is_base_unit_of_measure",
        "inventory_item__item_category__institution",
        "unit_of_measure",
    )
    search_fields = (
        "inventory_item__item_name",
        "inventory_item__reference_code",
        "unit_of_measure__unit_name",
        "unit_of_measure__unit_abbreviation",
    )
    raw_id_fields = ("inventory_item", "unit_of_measure")
    list_select_related = ("inventory_item", "unit_of_measure")
    ordering = ("inventory_item__item_name", "unit_of_measure__unit_name")


@admin.register(InventoryItemPriceChange)
class InventoryItemPriceChangeAdmin(admin.ModelAdmin):
    list_display = (
        "inventory_item",
        "type_of_price_change",
        "price_before",
        "price_after",
        "created_at",
    )
    list_filter = ("type_of_price_change",)
    search_fields = ("inventory_item__item_name", "inventory_item__reference_code")
    raw_id_fields = ("inventory_item",)
    list_select_related = ("inventory_item",)
    ordering = ("-created_at",)


@admin.register(InventoryItemStockLayer)
class InventoryItemStockLayerAdmin(admin.ModelAdmin):
    list_display = (
        "inventory_item",
        "get_institution",
        "unit_of_measure",
        "quantity_remaining",
        "unit_cost",
        "recieved_date",
        "expiry_date",
        "created_at",
    )
    list_filter = (
        "inventory_item__item_category__institution",
        "unit_of_measure",
        "recieved_date",
        "expiry_date",
    )
    search_fields = (
        "inventory_item__item_name",
        "inventory_item__reference_code",
        "inventory_item__item_category__institution__institution_name",
        "reference_code",
    )
    raw_id_fields = ("inventory_item", "unit_of_measure")
    list_select_related = (
        "inventory_item",
        "unit_of_measure",
        "inventory_item__item_category__institution",
    )
    ordering = ("-recieved_date",)
    date_hierarchy = "recieved_date"

    @admin.display(description="Institution")
    def get_institution(self, obj):
        return obj.inventory_item.item_category.institution


@admin.register(FiscalYear)
class FiscalYearAdmin(admin.ModelAdmin):
    list_display = (
        "name",
        "institution",
        "start_date",
        "end_date",
        "is_current",
        "is_closed",
        "is_active",
    )
    list_filter = ("institution", "is_current", "is_closed", "is_active")
    search_fields = ("name", "institution__institution_name")
    raw_id_fields = ("institution",)
    list_select_related = ("institution",)
    ordering = ("-start_date",)
    date_hierarchy = "start_date"


@admin.register(BranchInventoryItem)
class BranchInventoryItemAdmin(admin.ModelAdmin):
    list_display = (
        "inventory_item",
        "branch",
        "get_institution",
        "is_active",
        "created_at",
    )
    list_filter = ("branch__institution", "branch", "is_active")
    search_fields = (
        "inventory_item__item_name",
        "inventory_item__reference_code",
        "branch__branch_name",
        "branch__institution__institution_name",
    )
    raw_id_fields = ("inventory_item", "branch")
    list_select_related = ("inventory_item", "branch", "branch__institution")
    ordering = (
        "branch__institution",
        "branch__branch_name",
        "inventory_item__item_name",
    )

    @admin.display(description="Institution")
    def get_institution(self, obj):
        return obj.branch.institution


@admin.register(BranchInventoryItemStockLayer)
class BranchInventoryItemStockLayerAdmin(admin.ModelAdmin):
    list_display = (
        "get_item_name",
        "get_branch",
        "get_institution",
        "unit_of_measure",
        "quantity_remaining",
        "unit_cost",
        "received_date",
        "source_branch",
        "created_at",
    )
    list_filter = (
        "branch_inventory_item__branch__institution",
        "branch_inventory_item__branch",
        "unit_of_measure",
        "received_date",
        "source_branch",
    )
    search_fields = (
        "branch_inventory_item__inventory_item__item_name",
        "branch_inventory_item__inventory_item__reference_code",
        "branch_inventory_item__branch__branch_name",
        "branch_inventory_item__branch__institution__institution_name",
        "reference_code",
    )
    raw_id_fields = ("branch_inventory_item", "unit_of_measure", "source_branch")
    list_select_related = (
        "branch_inventory_item",
        "branch_inventory_item__inventory_item",
        "branch_inventory_item__branch",
        "branch_inventory_item__branch__institution",
        "unit_of_measure",
        "source_branch",
    )
    ordering = ("-received_date",)
    date_hierarchy = "received_date"

    @admin.display(description="Item")
    def get_item_name(self, obj):
        return obj.branch_inventory_item.inventory_item.item_name

    @admin.display(description="Branch")
    def get_branch(self, obj):
        return obj.branch_inventory_item.branch

    @admin.display(description="Institution")
    def get_institution(self, obj):
        return obj.branch_inventory_item.branch.institution


@admin.register(BranchInventoryItemUnitOfMeasure)
class BranchInventoryItemUnitOfMeasureAdmin(admin.ModelAdmin):
    list_display = (
        "get_item_name",
        "get_branch",
        "unit_of_measure",
        "conversion_factor",
        "selling_price",
        "is_base_unit_of_measure",
        "created_at",
    )
    list_filter = (
        "is_base_unit_of_measure",
        "branch_inventory_item__branch__institution",
        "branch_inventory_item__branch",
        "unit_of_measure",
    )
    search_fields = (
        "branch_inventory_item__inventory_item__item_name",
        "branch_inventory_item__inventory_item__reference_code",
        "branch_inventory_item__branch__branch_name",
        "unit_of_measure__unit_name",
    )
    raw_id_fields = ("branch_inventory_item", "unit_of_measure")
    list_select_related = (
        "branch_inventory_item",
        "branch_inventory_item__inventory_item",
        "branch_inventory_item__branch",
        "unit_of_measure",
    )
    ordering = (
        "branch_inventory_item__branch__branch_name",
        "unit_of_measure__unit_name",
    )

    @admin.display(description="Item")
    def get_item_name(self, obj):
        return obj.branch_inventory_item.inventory_item.item_name

    @admin.display(description="Branch")
    def get_branch(self, obj):
        return obj.branch_inventory_item.branch


@admin.register(BranchInventoryItemPriceChange)
class BranchInventoryItemPriceChangeAdmin(admin.ModelAdmin):
    list_display = (
        "get_item_name",
        "get_branch",
        "type_of_price_change",
        "price_before",
        "price_after",
        "created_at",
    )
    list_filter = (
        "type_of_price_change",
        "unit_of_measure__branch_inventory_item__branch__institution",
        "unit_of_measure__branch_inventory_item__branch",
    )
    search_fields = (
        "unit_of_measure__branch_inventory_item__inventory_item__item_name",
        "unit_of_measure__branch_inventory_item__branch__branch_name",
    )
    raw_id_fields = ("unit_of_measure",)
    list_select_related = (
        "unit_of_measure",
        "unit_of_measure__branch_inventory_item",
        "unit_of_measure__branch_inventory_item__inventory_item",
        "unit_of_measure__branch_inventory_item__branch",
    )
    ordering = ("-created_at",)

    @admin.display(description="Item")
    def get_item_name(self, obj):
        return obj.unit_of_measure.branch_inventory_item.inventory_item.item_name

    @admin.display(description="Branch")
    def get_branch(self, obj):
        return obj.unit_of_measure.branch_inventory_item.branch


@admin.register(StockToBranchAllocation)
class StockToBranchAllocationAdmin(admin.ModelAdmin):
    list_display = (
        "reference_code",
        "branch_to",
        "get_institution",
        "alloc_status",
        "is_stock_moved",
        "allocation_date",
        "is_active",
        "created_at",
    )
    list_filter = (
        "alloc_status",
        "is_stock_moved",
        "is_active",
        "branch_to__institution",
        "branch_to",
        "allocation_date",
    )
    search_fields = (
        "reference_code",
        "branch_to__branch_name",
        "branch_to__institution__institution_name",
    )
    raw_id_fields = ("branch_to",)
    list_select_related = ("branch_to", "branch_to__institution")
    ordering = ("-allocation_date",)
    date_hierarchy = "allocation_date"

    @admin.display(description="Institution")
    def get_institution(self, obj):
        return obj.branch_to.institution


@admin.register(StockToBranchAllocationProduct)
class StockToBranchAllocationProductAdmin(admin.ModelAdmin):
    list_display = ("allocation", "item", "unit_of_measure", "quantity", "created_at")
    list_filter = (
        "allocation__alloc_status",
        "allocation__branch_to__institution",
        "allocation__branch_to",
        "item__item_category",
    )
    search_fields = (
        "allocation__reference_code",
        "item__item_name",
        "item__reference_code",
        "allocation__branch_to__branch_name",
    )
    raw_id_fields = ("allocation", "item", "unit_of_measure")
    list_select_related = ("allocation", "item", "unit_of_measure")
    ordering = ("-created_at",)


@admin.register(BranchToBranchStockMovement)
class BranchToBranchStockMovementAdmin(admin.ModelAdmin):
    list_display = (
        "reference_code",
        "branch_from",
        "branch_to",
        "get_institution",
        "stock_movement_status",
        "is_stock_moved",
        "stock_movement_date",
        "is_active",
        "created_at",
    )
    list_filter = (
        "stock_movement_status",
        "is_stock_moved",
        "is_active",
        "branch_from__institution",
        "branch_from",
        "branch_to",
        "stock_movement_date",
    )
    search_fields = (
        "reference_code",
        "branch_from__branch_name",
        "branch_to__branch_name",
        "branch_from__institution__institution_name",
    )
    raw_id_fields = ("branch_from", "branch_to")
    list_select_related = ("branch_from", "branch_to", "branch_from__institution")
    ordering = ("-stock_movement_date",)
    date_hierarchy = "stock_movement_date"

    @admin.display(description="Institution")
    def get_institution(self, obj):
        return obj.branch_from.institution


@admin.register(BranchToBranchStockMovementItem)
class BranchToBranchStockMovementItemAdmin(admin.ModelAdmin):
    list_display = (
        "stock_movement",
        "get_item_name",
        "get_branch_from",
        "unit_of_measure",
        "quantity",
        "created_at",
    )
    list_filter = (
        "stock_movement__stock_movement_status",
        "stock_movement__branch_from__institution",
        "stock_movement__branch_from",
        "stock_movement__branch_to",
    )
    search_fields = (
        "stock_movement__reference_code",
        "inventory_item__inventory_item__item_name",
        "inventory_item__inventory_item__reference_code",
        "stock_movement__branch_from__branch_name",
        "stock_movement__branch_to__branch_name",
    )
    raw_id_fields = ("stock_movement", "inventory_item", "unit_of_measure")
    list_select_related = (
        "stock_movement",
        "stock_movement__branch_from",
        "inventory_item",
        "inventory_item__inventory_item",
        "unit_of_measure",
    )
    ordering = ("-created_at",)

    @admin.display(description="Item")
    def get_item_name(self, obj):
        return obj.inventory_item.inventory_item.item_name

    @admin.display(description="Branch From")
    def get_branch_from(self, obj):
        return obj.stock_movement.branch_from


@admin.register(WriteOff)
class WriteOffAdmin(admin.ModelAdmin):
    list_display = (
        "reference_code",
        "institution",
        "branch",
        "reason",
        "status",
        "are_journal_entries_made",
        "write_off_date",
        "is_active",
        "created_at",
    )
    list_filter = (
        "status",
        "reason",
        "are_journal_entries_made",
        "is_active",
        "institution",
        "branch__institution",
        "branch",
        "write_off_date",
    )
    search_fields = (
        "reference_code",
        "institution__institution_name",
        "branch__branch_name",
    )
    raw_id_fields = ("institution", "branch", "expense_account")
    list_select_related = ("institution", "branch", "branch__institution")
    ordering = ("-write_off_date",)
    date_hierarchy = "write_off_date"


@admin.register(InventoryItemWriteOffLineItem)
class InventoryItemWriteOffLineItemAdmin(admin.ModelAdmin):
    list_display = (
        "write_off",
        "inventory_item",
        "inventory_item_unit_of_measure",
        "quantity",
        "created_at",
    )
    list_filter = (
        "write_off__status",
        "write_off__reason",
        "write_off__institution",
        "inventory_item__item_category",
    )
    search_fields = (
        "write_off__reference_code",
        "inventory_item__item_name",
        "inventory_item__reference_code",
    )
    raw_id_fields = ("write_off", "inventory_item", "inventory_item_unit_of_measure")
    list_select_related = (
        "write_off",
        "inventory_item",
        "inventory_item_unit_of_measure",
    )
    ordering = ("-created_at",)


@admin.register(BranchInventorytemWriteOffLineItem)
class BranchInventoryItemWriteOffLineItemAdmin(admin.ModelAdmin):
    list_display = (
        "write_off",
        "get_item_name",
        "get_branch",
        "branch_item_unit_of_measure",
        "quantity",
        "created_at",
    )
    list_filter = (
        "write_off__status",
        "write_off__reason",
        "write_off__branch__institution",
        "write_off__branch",
        "branch_inventory_item__inventory_item__item_category",
    )
    search_fields = (
        "write_off__reference_code",
        "branch_inventory_item__inventory_item__item_name",
        "branch_inventory_item__inventory_item__reference_code",
        "branch_inventory_item__branch__branch_name",
    )
    raw_id_fields = (
        "write_off",
        "branch_inventory_item",
        "branch_item_unit_of_measure",
    )
    list_select_related = (
        "write_off",
        "branch_inventory_item",
        "branch_inventory_item__inventory_item",
        "branch_inventory_item__branch",
        "branch_item_unit_of_measure",
    )
    ordering = ("-created_at",)

    @admin.display(description="Item")
    def get_item_name(self, obj):
        return obj.branch_inventory_item.inventory_item.item_name

    @admin.display(description="Branch")
    def get_branch(self, obj):
        return obj.branch_inventory_item.branch


@admin.register(StockMovementLog)
class StockMovementLogAdmin(admin.ModelAdmin):
    list_display = (
        "movement_type",
        "stock_level",
        "inventory_item",
        "unit_of_measure",
        "quantity_before",
        "quantity_change",
        "quantity_after",
        "unit_cost",
        "institution",
        "branch",
        "source_reference",
        "movement_date",
    )
    list_filter = (
        "movement_type",
        "stock_level",
        "institution",
        "branch__institution",
        "branch",
        "unit_of_measure",
        "movement_date",
    )
    search_fields = (
        "inventory_item__item_name",
        "inventory_item__reference_code",
        "source_reference",
        "institution__institution_name",
        "branch__branch_name",
    )
    list_select_related = (
        "inventory_item",
        "unit_of_measure",
        "institution",
        "branch",
        "branch__institution",
    )
    ordering = ("-movement_date",)
    date_hierarchy = "movement_date"

    def has_add_permission(self, request):
        return False

    def has_change_permission(self, request, obj=None):
        return False
