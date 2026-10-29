from dataclasses import dataclass
from typing import Any

from accounts.serializers import COABulkUploadSerializer
from customers.serializers import CustomerSerializer, SalesPersonBulkUploadSerializer
from fixed_assets.serializers import (
    BulkAssetCategoryUploadSerializer,
    BulkFixedAssetItemUploadSerializer,
)
from items.serializers import (
    BulkItemCategoryUploadSerializer,
    ItemUnitOfMeasureSerializer,
)
from requisitions.serializers import (
    BulkRequisitionItemUploadSerializer,
    BulkExpenseUploadSerializer,
)
from vendors.serializers import BulkVendorBillRowSerializer, VendorSerializer

from .bulk_upload_tasks import (
    bulk_create_charts_of_accounts,
    bulk_create_customers,
    bulk_create_fixed_asset_categories,
    bulk_create_fixed_asset_items,
    bulk_create_inventory_item_categories,
    bulk_create_inventory_units_of_measure,
    bulk_create_requisition_items,
    bulk_create_salespersons,
    bulk_create_vendors,
    bulk_create_expenses,
    bulk_create_vendor_bills,
)

CUSTOMER_COLUMN_DEFS = [
    {"name": "customer_name", "required": True, "dropdown": None},
    {"name": "customer_type", "required": True, "dropdown": ["individual", "business"]},
    {"name": "credit_limit", "required": True, "dropdown": None},
    {"name": "gender", "required": False, "dropdown": ["MALE", "FEMALE", "OTHER"]},
    {"name": "address", "required": False, "dropdown": None},
    {"name": "phone_number", "required": False, "dropdown": None},
    {"name": "email", "required": False, "dropdown": None},
    {"name": "currency_code", "required": False, "dropdown": None},
    {"name": "opening_balance", "required": False, "dropdown": None},
    {"name": "opening_balance_received_date", "required": False, "dropdown": None},
    {"name": "tin", "required": False, "dropdown": None},
]

INVENTORY_UNITS_OF_MEASURE_COLUMN_DEFS = [
    {"name": "unit_name", "required": True, "dropdown": None},
    {"name": "unit_abbreviation", "required": True, "dropdown": None},
]

INVENTORY_ITEM_CATEGORIES_COLUMN_DEFS = [
    {"name": "name", "required": True, "dropdown": None},
    {"name": "expense_account", "required": False, "dropdown": None},
    {"name": "inventory_account", "required": False, "dropdown": None},
    {"name": "revenue_account", "required": False, "dropdown": None},
]

COA_COLUMN_DEFS = [
    {"name": "account_name", "required": True, "dropdown": None},
    {"name": "account_role", "required": True, "dropdown": None},
    {"name": "parent_account", "required": False, "dropdown": None},
    {"name": "currency_code", "required": False, "dropdown": None},
    {"name": "opening_balance_debit", "required": False, "dropdown": None},
    {"name": "opening_balance_credit", "required": False, "dropdown": None},
    {"name": "description", "required": False, "dropdown": None},
]

VENDOR_COLUMN_DEFS = [
    {"name": "vendor_name", "required": True, "dropdown": None},
    {"name": "vendor_type", "required": True, "dropdown": ["individual", "business"]},
    {"name": "gender", "required": False, "dropdown": ["MALE", "FEMALE", "OTHER"]},
    {"name": "email", "required": False, "dropdown": None},
    {"name": "phone_number", "required": False, "dropdown": None},
    {"name": "address", "required": False, "dropdown": None},
    {"name": "website", "required": False, "dropdown": None},
    {"name": "opening_balance", "required": False, "dropdown": None},
    {"name": "opening_balance_received_date", "required": False, "dropdown": None},
    {"name": "currency_code", "required": False, "dropdown": None},
    {"name": "tax_identification_number", "required": False, "dropdown": None},
]

FIXED_ASSET_CATEGORY_COLUMN_DEFS = [
    {"name": "reference_code", "required": True, "dropdown": None},
    {"name": "category_name", "required": True, "dropdown": None},
    {"name": "asset_class", "required": True, "dropdown": None},
    {"name": "asset_type", "required": True, "dropdown": ["TANGIBLE", "INTANGIBLE"]},
    {"name": "is_capitalizable", "required": True, "dropdown": ["True", "False"]},
    {"name": "is_depreciable", "required": True, "dropdown": ["True", "False"]},
    {
        "name": "depreciation_frequency",
        "required": True,
        "dropdown": [
            "DAILY",
            "WEEKLY",
            "MONTHLY",
            "QUARTERLY",
            "SEMI_ANNUALLY",
            "ANNUALLY",
        ],
    },
    {"name": "fixed_asset_account", "required": True, "dropdown": None},
    {"name": "depreciation_expense_account", "required": True, "dropdown": None},
    {"name": "accumulated_depreciation_account", "required": True, "dropdown": None},
]

REQUISITION_ITEM_COLUMN_DEFS = [
    {"name": "reference_code", "required": False, "dropdown": None},
    {"name": "name", "required": True, "dropdown": None},
    {"name": "description", "required": False, "dropdown": None},
    {"name": "unit_of_measure", "required": False, "dropdown": None},
    {"name": "unit_price", "required": False, "dropdown": None},
]

SALESPERSON_COLUMN_DEFS = [
    {"name": "name", "required": True, "dropdown": None},
    {"name": "email", "required": False, "dropdown": None},
    {"name": "contact", "required": False, "dropdown": None},
    {"name": "address", "required": False, "dropdown": None},
    {"name": "balance", "required": False, "dropdown": None},
]

FIXED_ASSET_ITEMS_COLUMN_DEFS = [
    {
        "name": "useful_life",
        "label": "Useful Life",
        "required": False,
        "dropdown": None,
    },
    {
        "name": "salvage_value",
        "label": "Salvage Value",
        "required": False,
        "dropdown": None,
    },
    {
        "name": "reference_code",
        "label": "Serial Number",
        "required": True,
        "dropdown": None,
    },
    {"name": "category", "label": "Asset Category", "required": True, "dropdown": None},
    {"name": "asset_name", "label": "Asset Name", "required": True, "dropdown": None},
    {
        "name": "purchase_date",
        "label": "Purchase Date",
        "required": True,
        "dropdown": None,
    },
    {
        "name": "purchase_price",
        "label": "Purchase Price",
        "required": True,
        "dropdown": None,
    },
]

EXPENSES_COLUMN_DEFS = [
    {"name": "reference_code", "required": False, "dropdown": None},
    {"name": "branch", "required": False, "dropdown": None},
    {"name": "date", "required": True, "dropdown": None},
    {"name": "currency_code", "required": True, "dropdown": None},
    {"name": "description", "required": False, "dropdown": None},
    {"name": "payee", "required": False, "dropdown": None},
    {"name": "amount", "required": True, "dropdown": None},
    {"name": "cash_account", "required": True, "dropdown": None},
    {"name": "expense_account", "required": False, "dropdown": None},
    {"name": "applicable_taxes", "required": False, "dropdown": None},
]

VENDOR_BILL_COLUMN_DEFS = [
    {"name": "reference_code", "label": "Reference Code", "required": True, "dropdown": None},
    {"name": "vendor", "label": "Vendor", "required": True, "dropdown": None},
    {"name": "branch", "label": "Branch", "required": False, "dropdown": None},
    {"name": "payment_terms", "label": "Payment Terms", "required": False, "dropdown": None},
    {
        "name": "type",
        "label": "Type",
        "required": True,
        "dropdown": ["Inventory", "Service", "Other", "Other Expense"],
    },
    {"name": "item", "label": "Item", "required": True, "dropdown": None, "strict": False},
    {"name": "uom", "label": "UOM", "required": False, "dropdown": None, "strict": False},
    {"name": "qty", "label": "Qty", "required": True, "dropdown": None},
    {"name": "unit_price", "label": "Unit Price (UGX)", "required": True, "dropdown": None},
    {"name": "expense_account", "label": "Expense Account", "required": False, "dropdown": None},
    {"name": "tax", "label": "Tax", "required": False, "dropdown": None},
    {
        "name": "payment_status",
        "label": "Payment Status",
        "required": True,
        "dropdown": ["Paid", "Unpaid", "Partially Paid"],
    },
    {"name": "amount_paid", "label": "Amount Paid (UGX)", "required": False, "dropdown": None},
    {"name": "cash_account", "label": "Cash Account", "required": False, "dropdown": None},
    {"name": "due_date", "label": "Due Date", "required": False, "dropdown": None},
]

@dataclass(frozen=True)
class BulkUploadDefinition:
    columns: list[dict]
    serializer: type
    task: Any

    @property
    def column_names(self):
        return [column["name"] for column in self.columns]


BULK_UPLOAD_REGISTRY = {
    "customer": BulkUploadDefinition(
        columns=CUSTOMER_COLUMN_DEFS,
        serializer=CustomerSerializer,
        task=bulk_create_customers,
    ),
    "vendor": BulkUploadDefinition(
        columns=VENDOR_COLUMN_DEFS,
        serializer=VendorSerializer,
        task=bulk_create_vendors,
    ),
    "fixed_asset_category": BulkUploadDefinition(
        columns=FIXED_ASSET_CATEGORY_COLUMN_DEFS,
        serializer=BulkAssetCategoryUploadSerializer,
        task=bulk_create_fixed_asset_categories,
    ),
    "fixed_asset_items": BulkUploadDefinition(
        columns=FIXED_ASSET_ITEMS_COLUMN_DEFS,
        serializer=BulkFixedAssetItemUploadSerializer,
        task=bulk_create_fixed_asset_items,
    ),
    "salesperson": BulkUploadDefinition(
        columns=SALESPERSON_COLUMN_DEFS,
        serializer=SalesPersonBulkUploadSerializer,
        task=bulk_create_salespersons,
    ),
    "charts_of_accounts": BulkUploadDefinition(
        columns=COA_COLUMN_DEFS,
        serializer=COABulkUploadSerializer,
        task=bulk_create_charts_of_accounts,
    ),
    "requisition_item": BulkUploadDefinition(
        columns=REQUISITION_ITEM_COLUMN_DEFS,
        serializer=BulkRequisitionItemUploadSerializer,
        task=bulk_create_requisition_items,
    ),
    "inventory_units_of_measure": BulkUploadDefinition(
        columns=INVENTORY_UNITS_OF_MEASURE_COLUMN_DEFS,
        serializer=ItemUnitOfMeasureSerializer,
        task=bulk_create_inventory_units_of_measure,
    ),
    "inventory_item_categories": BulkUploadDefinition(
        columns=INVENTORY_ITEM_CATEGORIES_COLUMN_DEFS,
        serializer=BulkItemCategoryUploadSerializer,
        task=bulk_create_inventory_item_categories,
    ),
    "expenses": BulkUploadDefinition(
        columns=EXPENSES_COLUMN_DEFS,
        serializer=BulkExpenseUploadSerializer,
        task=bulk_create_expenses,
    ),
    "vendor_bill": BulkUploadDefinition(
        columns=VENDOR_BILL_COLUMN_DEFS,
        serializer=BulkVendorBillRowSerializer,
        task=bulk_create_vendor_bills,
    ),
}
