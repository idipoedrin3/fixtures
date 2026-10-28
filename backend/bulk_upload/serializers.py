from rest_framework import serializers
from utilities.helpers import validation_error

TEMPLATE_CHOICES = [
    "expenses",
    "customer",
    "vendor",
    "fixed_asset_category",
    "fixed_asset_items",
    "requisition_item",
    "salesperson",
    "charts_of_accounts",
    "inventory_units_of_measure",
    "inventory_item_categories",
]


class BulkUploadRequestSerializer(serializers.Serializer):
    template_type = serializers.ChoiceField(choices=TEMPLATE_CHOICES)
    file = serializers.FileField()

    def validate_file(self, value):
        name = value.name.lower()
        if not (name.endswith(".xlsx") or name.endswith(".csv")):
            raise validation_error(
                "File must be an Excel file (.xlsx) or a CSV file (.csv)."
            )
        return value

    def validate(self, data):
        return data
