from rest_framework import serializers
from utilities.helpers import BaseReportFilterSerializer


class ItemCategoryFilterSerializer(BaseReportFilterSerializer):
    name = serializers.CharField(required=False)
    is_active = serializers.BooleanField(required=False)


class ItemFilterSerializer(BaseReportFilterSerializer):
    item_type = serializers.ChoiceField(choices=["GOODS", "SERVICES"], required=False)
    is_active = serializers.BooleanField(required=False)


class StockToBranchAllocationFilterSerializer(BaseReportFilterSerializer):
    alloc_status = serializers.ChoiceField(
        choices=["PENDING", "ALLOCATED", "CANCELLED"], required=False
    )
    is_stock_moved = serializers.BooleanField(required=False)
