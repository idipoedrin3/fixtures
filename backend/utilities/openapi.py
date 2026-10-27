from drf_spectacular.utils import OpenApiParameter
from drf_spectacular.types import OpenApiTypes

SEARCH_PARAM = OpenApiParameter(
    name="search",
    type=OpenApiTypes.STR,
    location=OpenApiParameter.QUERY,
    description="Search across all searchable fields (including base fields like reference_code).",
    required=False,
)

ORDERING_PARAM = OpenApiParameter(
    name="ordering",
    type=OpenApiTypes.STR,
    location=OpenApiParameter.QUERY,
    description="Order results by field name, prefix with '-' for descending. "
    "Example: ?ordering=-created_at",
    required=False,
)


def uuid_param(name: str, description: str, required=True):
    return OpenApiParameter(
        name=name,
        type=OpenApiTypes.UUID,
        location=OpenApiParameter.QUERY,
        description=description,
        required=required,
    )


def content_type_id_param(required=True):
    return OpenApiParameter(
        name="content_type_id",
        type=OpenApiTypes.INT,
        location=OpenApiParameter.QUERY,
        description="ID of the content type",
        required=required,
    )


def institution_role_uuid_param(required=True):
    return uuid_param("institution_role_uuid", "UUID of the institution role", required)


def object_base_uuid_param(required=True):
    return uuid_param("object_base_uuid", "Base UUID of the object", required)


def role_base_uuid_param(required=False):
    return uuid_param(
        "role_base_uuid",
        "Return only records assigned to the specified institution role",
        required,
    )


def return_reason_uuid_param(required=False):
    return uuid_param(
        "return_reason_uuid",
        "Filter item returns by the base UUID of their return reason",
        required,
    )


def permission_category_base_uuid_param(required=False):
    return uuid_param(
        "permission_category_base_uuid",
        "Filter permissions by the base UUID of their permission category",
        required,
    )


def corporate_unit_uuid_param(required=True):
    return uuid_param("corporate_unit_uuid", "UUID of the corporate unit", required)


def branch_base_uuid_param(required=True):
    return uuid_param(
        "branch_uuid", "Filter by a specific branch's unique identifier", required
    )


def branch_uuids_param(required=True):
    return uuid_param(
        "branch_uuids", "Filter by multiple branch UUIDs (comma-separated)", required
    )


def vendor_base_uuid_param(required=True):
    return uuid_param("vendor_base_uuid", "Filter by vendor base UUID", required)


def purchase_order_uuid_param(required=True):
    return uuid_param(
        "purchase_order_uuid", "Filter by a specific purchase order UUID.", required
    )


def vendor_payment_base_uuid_param(required=True):
    return uuid_param(
        "vendor_payment_base_uuid", "Filter by vendor payment base UUID", required
    )


def customer_purchase_order_base_uuid_param(required=False):
    return uuid_param(
        "customer_purchase_order_base_uuid",
        "Filter by customer sales order UUID",
        required,
    )


def bill_base_uuid_param(required=True):
    return uuid_param("bill_base_uuid", "Filter by  bill base UUID", required)


def asset_base_uuid_param(required=True):
    return uuid_param(
        "asset_base_uuid", "Filter by the base_uuid of the FixedAsset", required
    )


def asset_class_base_uuid_param(required=True):
    return uuid_param(
        "asset_class_base_uuid",
        "Filter by the base_uuid of the FixedAsset Class",
        required,
    )


def asset_category_base_uuid_param(required=True):
    return uuid_param(
        "asset_category_base_uuid",
        "Filter by the base_uuid of the FixedAsset Category",
        required,
    )


def transaction_uuid_param(required=True):
    return uuid_param(
        "transaction_uuid", "Filter by a specific transaction UUID.", required
    )


def account_uuid_param(required=True):
    return uuid_param("account_uuid", "Filter by a specific account UUID.", required)


def manufacturing_execution_consumption_group_uuid_param(required=False):
    return uuid_param(
        "manufacturing_execution_consumption_group_uuid",
        "Filter by a specific MEC Group UUID.",
        required,
    )


def fiscal_year_uuid_param(required=True):
    return uuid_param(
        "fiscal_year_uuid", "Filter by a specific fiscal year UUID.", required
    )


def tax_base_uuid_param(required=True):
    return uuid_param("tax_base_uuid", "Base UUID of the tax to filter by", required)


def inventory_item_uuid_param(required=True):
    return uuid_param(
        "inventory_item_uuid", "Filter by a specific inventory item UUID.", required
    )


def invoice_base_uuid_param(required=True):
    return uuid_param(
        "invoice_base_uuid", "Filter by a specific invoice base UUID.", required
    )


def inventory_item_unit_of_measure_uuid_param(required=True):
    return uuid_param(
        "inventory_item_unit_of_measure_uuid",
        "Filter by a specific inventory item unit of measure UUID.",
        required,
    )


def branch_inventory_item_uuid_param(required=True):
    return uuid_param(
        "branch_inventory_item_uuid",
        "Filter by a specific branch inventory item UUID.",
        required,
    )


def parent_branch_base_uuid_param(required=False):
    return uuid_param(
        "parent_branch_uuid",
        "Filter branches by the base UUID of their parent branch, If not provided, top-level branches are returned.",
        required,
    )


def branch_base_uuid_param_base(required=True):
    return uuid_param(
        "branch_base_uuid", "Filter by a specific branch's unique identifier", required
    )


def other_income_base_uuid_param_base(required=True):
    return uuid_param(
        "other_income_base_uuid",
        "Filter by a specific other income's unique identifier",
        required,
    )


def other_income_category_base_uuid_param(required=True):
    return uuid_param(
        "other_income_category_base_uuid",
        "Filter by a specific other income category's unique identifier",
        required,
    )


def business_document_category_uuid_param(required=True):
    return uuid_param(
        "business_document_category_base_uuid",
        "Filter by a specific business document category's unique identifier",
        required,
    )


def customer_base_uuid_param(required=True):
    return uuid_param(
        "customer_base_uuid",
        "Filter by a specific customer's unique identifier",
        required,
    )


def sales_person_base_uuid_param(required=True):
    return uuid_param(
        "sales_person_base_uuid",
        "Filter by a specific sales person's unique identifier",
        required,
    )


def custom_user_base_uuid_param(required=True):
    return uuid_param(
        "custom_user_base_uuid",
        "Filter by a specific custom user's unique identifier",
        required,
    )


def bank_base_uuid_param(required=True):
    return uuid_param(
        "bank_base_uuid",
        "Filter by a specific bank account's unique identifier",
        required,
    )


def requisition_type_base_uuid_param(required=True):
    return uuid_param(
        "requisition_type_base_uuid",
        "Filter by a specific requisition type's unique identifier",
        required,
    )


def requisition_base_uuid_param(required=True):
    return uuid_param(
        "requisition_base_uuid",
        "Filter by a specific requisition's unique identifier",
        required,
    )


def cashbook_base_uuid_param(required=True):
    return uuid_param(
        "cashbook_base_uuid",
        "Filter by a specific bank account's unique identifier",
        required,
    )


def customer_deposit_base_uuid_param(required=True):
    return uuid_param(
        "customer_deposit_base_uuid",
        "Filter by a specific customer deposit's unique identifier",
        required,
    )


def customer_payment_base_uuid_param(required=True):
    return uuid_param(
        "customer_payment_base_uuid",
        "Filter by a specific customer payment's unique identifier",
        required,
    )


def bill_of_material_base_uuid_param(required=True):
    return uuid_param(
        "bill_of_material_base_uuid",
        "Filter by a specific bill of material's unique identifier",
        required,
    )


def budget_adjustment_base_uuid_param(required=True):
    return uuid_param(
        "budget_adjustment_base_uuid",
        "Filter by a specific budget adjustment's unique identifier",
        required,
    )
