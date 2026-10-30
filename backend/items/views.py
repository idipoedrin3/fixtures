from datetime import datetime, time, timedelta
from uuid import UUID

from django.shortcuts import get_object_or_404
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework import status
from rest_framework.exceptions import ValidationError
from institution.utils import filter_queryset_by_branches
from system.utils import load_and_group_defaults
from utilities.helpers import (
    get_institution,
    get_or_raise,
    validation_error,
)
from django.utils import timezone
from django.utils.dateparse import parse_date
from .serializers import (
    BranchInventoryItemStockLayerSerializer,
    InventoryItemAllStockLayersSerializer,
    BranchSellingPriceUpdateSerializer,
    ItemCategorySerializer,
    InventoryItemSerializer,
    InventoryItemImageSerializer,
    FiscalYearSerializer,
    ItemDistributionRequestSerializer,
    ItemDistributionSerializer,
    ItemUnitOfMeasureSerializer,
    BranchInventoryItemSerializer,
    InventoryItemSerializer,
    SimpleItemCategorySerializer,
    StockMovementDownloadSerializer,
    StockMovementLogSerializer,
    StockToBranchAllocationSerializer,
    CombinedStockMovementSerializer,
    InventoryItemPriceChangeSerializer,
    InventoryItemStockLayerSerializer,
    BranchInventoryItemPriceChangeSerializer,
    BranchInventoryItemUnitOfMeasureSerializer,
    InventoryItemUnitOfMeasureSerializer,
    BranchToBranchStockMovementSerializer,
    WriteOffSerializer,
    InstitutionWriteOffLineItemSerializer,
    BranchWriteOffLineItemSerializer,
    StockMovementLog,
    InventorySummarySerializer,
    InventoryItemPriceUpdateSerializer,
    ItemPreferredVendorWriteSerializer,
    ItemVendorSerializer,
)
from .models import (
    BranchInventoryItemStockLayer,
    InventoryItemStockLayer,
    InventoryItemImage,
    ItemCategory,
    InventoryItem,
    FiscalYear,
    ItemUnitOfMeasure,
    BranchInventoryItem,
    StockToBranchAllocation,
    InventoryItemPriceChange,
    BranchInventoryItemPriceChange,
    BranchInventoryItemUnitOfMeasure,
    InventoryItemUnitOfMeasure,
    BranchToBranchStockMovement,
    WriteOff,
    StockMovementLog,
    ItemVendor,
    ItemVendorUnitPrice,
)
from django.db.models import (
    Q,
    Case,
    Prefetch,
    When,
    IntegerField,
    Count,
    F,
    Value,
    CharField,
)
from drf_spectacular.utils import extend_schema, OpenApiParameter
from drf_spectacular.types import OpenApiTypes
from audit.models import AuditLog
from django.contrib.contenttypes.models import ContentType
from utilities.pagination import CustomPageNumberPagination
from utilities.helpers import serialize_value
from django.db.models import Q
from django.db import transaction
from django.http import HttpResponse
import pandas as pd
import io
from institution.models import Branch
from system.exceptions import SystemNotFoundError
from users.permissions import HasInstitutionPermission
from utilities.openapi import (
    SEARCH_PARAM,
    ORDERING_PARAM,
    branch_base_uuid_param_base,
    branch_inventory_item_uuid_param,
    branch_uuids_param,
    inventory_item_uuid_param,
)
from utilities.mixin import SearchOrderMixin
from audit.utils import log_action

from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework import status
from django.db import transaction
from django.db.models import Q
from django.contrib.contenttypes.models import ContentType
from drf_spectacular.utils import extend_schema
from audit.models import AuditLog
from utilities.helpers import serialize_value
from utilities.pagination import CustomPageNumberPagination
from .services import get_inventory_summary
from utilities.helpers import get_institution
from .helpers.inventory_item_bulk_creation import (
    generate_bulk_inventory_template,
    process_bulk_inventory_upload,
)
from .tasks import bulk_inventory_upload_task, stock_movement_report_email_task
from bulk_upload.bulk_upload_tasks import (
    bulk_create_inventory_item_categories,
    bulk_create_inventory_units_of_measure,
)
from decimal import Decimal


class BaseItemView(APIView):
    def get_institution(self, request):
        return get_institution(request)

    def get_object_by_uuid(self, model, base_uuid, institution):
        try:
            return model.objects.get(base_uuid=base_uuid, institution=institution)
        except model.DoesNotExist:
            return None


class ItemCategoryListView(APIView, SearchOrderMixin):
    permission_classes = [HasInstitutionPermission]
    required_permissions = {
        "get": "can_view_item_categories",
        "post": "can_create_item_categories",
    }

    queryset = ItemCategory.objects.undeleted()

    @extend_schema(
        request=ItemCategorySerializer,
        responses={200: SimpleItemCategorySerializer(many=True)},
        description="Retrieve a list of all item categories. Supports searching by name or description.",
        summary="List all item categories",
        tags=["Item Management"],
        parameters=[
            SEARCH_PARAM,
            ORDERING_PARAM,
        ],
    )
    def get(self, request):
        institution = get_institution(request)

        item_categories = self.queryset.filter(institution=institution)

        item_categories = self.apply_search(item_categories)
        item_categories = self.apply_ordering(item_categories)
        item_categories = self.apply_filters(item_categories)

        paginator = CustomPageNumberPagination()
        paginator_qs = paginator.paginate_queryset(item_categories, request)
        serializer = SimpleItemCategorySerializer(paginator_qs, many=True)
        return paginator.get_paginated_response(serializer.data)

    @extend_schema(
        request=ItemCategorySerializer(many=True),
        responses={202: OpenApiTypes.OBJECT},
        description="Queue one or more item categories for creation.",
        summary="Queue bulk creation of item categories",
        tags=["Item Management"],
    )
    def post(self, request):
        is_many = isinstance(request.data, list)

        serializer = ItemCategorySerializer(
            data=request.data,
            many=is_many,
            context={"request": request},
        )
        serializer.is_valid(raise_exception=True)

        validated_rows = (
            serializer.validated_data if is_many else [serializer.validated_data]
        )
        rows = [
            {
                key: serialize_value(value)
                for key, value in row.items()
                if key != "institution"
            }
            for row in validated_rows
        ]

        institution = get_institution(request)
        result = bulk_create_inventory_item_categories.delay(
            institution_id=institution.pk,
            rows=rows,
            requested_by_id=request.user.pk,
        )

        return Response(
            {
                "detail": f"{len(rows)} item category(s) queued for creation.",
                "task_id": result.id,
                "total_rows": len(rows),
            },
            status=status.HTTP_202_ACCEPTED,
        )


class ItemCategoryDetailView(APIView):
    permission_classes = [HasInstitutionPermission]
    required_permissions = {
        "get": "can_view_item_categories",
        "patch": "can_edit_item_categories",
        "delete": "can_delete_item_categories",
    }

    def _get_category_object(self, request, base_uuid):
        institution = get_institution(request)

        return get_or_raise(
            queryset=ItemCategory.objects.undeleted(),
            message=f"Item category with UUID {base_uuid} not found",
            base_uuid=base_uuid,
            institution=institution,
        )

    @extend_schema(
        responses={200: ItemCategorySerializer},
        description="Retrieve details of a specific item category.",
        summary="Get item category details",
        tags=["Item Management"],
    )
    def get(self, request, base_uuid):
        return Response(
            ItemCategorySerializer(self._get_category_object(request, base_uuid)).data
        )

    @extend_schema(
        request=ItemCategorySerializer,
        responses={200: ItemCategorySerializer},
        description="Partially update details of a specific item category.",
        summary="Partially update item category details",
        tags=["Item Management"],
    )
    def patch(self, request, base_uuid):
        item_category = self._get_category_object(request, base_uuid)
        item_category.approval_status = "under_update"
        old_data = ItemCategorySerializer(item_category).data
        serializer = ItemCategorySerializer(
            item_category,
            data=request.data,
            partial=True,
            context={"request": request},
        )
        if serializer.is_valid():
            updated_item_category = serializer.save()
            new_data = ItemCategorySerializer(updated_item_category).data
            changes = {
                key: {"old": old_data.get(key), "new": new_data.get(key)}
                for key in request.data.keys()
                if old_data.get(key) != new_data.get(key)
            }
            AuditLog.objects.create(
                content_type=ContentType.objects.get_for_model(ItemCategory),
                object_id=updated_item_category.id,
                action="UPDATE",
                user=request.user if request.user.is_authenticated else None,
                changes=changes,
                description=f"Updated item category {updated_item_category.name} ({updated_item_category.base_uuid})",
            )
            updated_item_category.confirm_update(
                profile_institution=request.profile_institution,
                external_identity=request.external_identity,
            )
            return Response(serializer.data)
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

    @extend_schema(
        responses={204: None},
        description="Delete a specific item category.",
        summary="Delete an item category",
        tags=["Item Management"],
    )
    def delete(self, request, base_uuid):
        item_category = self._get_category_object(request, base_uuid)
        item_category_data = ItemCategorySerializer(item_category).data
        item_category_id = item_category.id
        item_category.confirm_delete(
            profile_institution=request.profile_institution,
            external_identity=request.external_identity,
        )
        AuditLog.objects.create(
            content_type=ContentType.objects.get_for_model(ItemCategory),
            object_id=item_category_id,
            action="DELETE",
            user=request.user if request.user.is_authenticated else None,
            changes=item_category_data,
            description=f"Deleted item category {item_category_data['name']} ({base_uuid})",
        )
        return Response(status=status.HTTP_204_NO_CONTENT)


class InventoryItemListView(SearchOrderMixin, APIView):
    permission_classes = [HasInstitutionPermission]
    required_permissions = {
        "get": "can_view_inventory_items",
        "post": "can_create_inventory_items",
    }

    @extend_schema(
        request=InventoryItemSerializer,
        responses={200: InventoryItemSerializer(many=True)},
        description="Retrieve a list of all inventory items. Supports"
        " searching by item name, code, category, item type, and sell/purchase flags.",
        summary="List all inventory items",
        tags=["Item Management"],
        parameters=[
            SEARCH_PARAM,
            ORDERING_PARAM,
            OpenApiParameter(
                name="item_type",
                type=str,
                location=OpenApiParameter.QUERY,
                description="Filter by item type. Use 'GOODS' or 'SERVICES'. Case-insensitive.",
                required=False,
                enum=["GOODS", "SERVICES"],
            ),
            OpenApiParameter(
                name="can_be_sold",
                type=bool,
                location=OpenApiParameter.QUERY,
                description="Filter items that can be sold (true/false).",
                required=False,
            ),
            OpenApiParameter(
                name="can_be_purchased",
                type=bool,
                location=OpenApiParameter.QUERY,
                description="Filter items that can be purchased (true/false).",
                required=False,
            ),
        ],
    )
    def get(self, request):

        institution = get_institution(request)

        item_type_query = request.query_params.get("item_type")
        can_be_sold_query = request.query_params.get("can_be_sold")
        can_be_purchased_query = request.query_params.get("can_be_purchased")

        inventory_items = (
            InventoryItem.objects.filter(
                institution=institution,
                deleted_at__isnull=True,
            )
            .select_related(
                "item_category",
                "product_stock_valuation_method",
                "product_stock_movement_strategy",
                "inventory_account",
                "revenue_account",
                "expense_account",
                "sales_tax",
                "purchase_tax",
                "created_by",
                "updated_by",
            )
            .prefetch_related(
                Prefetch(
                    "units",
                    queryset=InventoryItemUnitOfMeasure.objects.filter(
                        deleted_at__isnull=True,
                    ).select_related("unit_of_measure", "other_uom"),
                    to_attr="_active_units",
                ),
                Prefetch(
                    "stock_layers",
                    queryset=InventoryItemStockLayer.objects.filter(
                        deleted_at__isnull=True,
                    ).only("inventory_item_id", "quantity_remaining"),
                    to_attr="_active_stock_layers",
                ),
                Prefetch(
                    "item_vendors",
                    queryset=ItemVendor.objects.filter(
                        deleted_at__isnull=True,
                    )
                    .select_related("vendor")
                    .prefetch_related(
                        Prefetch(
                            "unit_prices",
                            queryset=ItemVendorUnitPrice.objects.filter(
                                deleted_at__isnull=True,
                            ).select_related(
                                "unit_of_measure",
                                "unit_of_measure__unit_of_measure",
                            ),
                            to_attr="_active_unit_prices",
                        )
                    ),
                    to_attr="_active_item_vendors",
                ),
            )
        )

        branch_uuids = [
            value.strip()
            for value in request.query_params.get("branch_uuids", "").split(",")
            if value.strip()
        ]
        if branch_uuids:
            inventory_items = inventory_items.filter(
                branch_specific_inventory__branch__base_uuid__in=branch_uuids,
                branch_specific_inventory__deleted_at__isnull=True,
            ).distinct()

        if item_type_query:
            item_type_query = item_type_query.upper()

            valid_types = [choice[0] for choice in InventoryItem.ITEM_TYPE_CHOICES]

            if item_type_query in valid_types:
                inventory_items = inventory_items.filter(item_type=item_type_query)

        if can_be_sold_query is not None:
            if can_be_sold_query.lower() in ["true", "false"]:
                inventory_items = inventory_items.filter(
                    can_be_sold=can_be_sold_query.lower() == "true"
                )

        if can_be_purchased_query is not None:
            if can_be_purchased_query.lower() in ["true", "false"]:
                inventory_items = inventory_items.filter(
                    can_be_purchased=can_be_purchased_query.lower() == "true"
                )

        inventory_items = self.apply_search(inventory_items)
        inventory_items = self.apply_ordering(inventory_items)

        paginator = CustomPageNumberPagination()
        paginator_qs = paginator.paginate_queryset(inventory_items, request)
        serializer = InventoryItemSerializer(
            paginator_qs,
            many=True,
            context={"request": request},
        )

        return paginator.get_paginated_response(serializer.data)

    @extend_schema(
        request=InventoryItemSerializer,
        responses={201: InventoryItemSerializer},
        description="Create a new inventory item.",
        summary="Create a new inventory item",
        tags=["Item Management"],
    )
    def post(self, request):
        serializer = InventoryItemSerializer(
            data=request.data, context={"request": request}
        )
        if serializer.is_valid():
            inventory_item = serializer.save()
            AuditLog.objects.create(
                content_type=ContentType.objects.get_for_model(InventoryItem),
                object_id=inventory_item.pk,
                action="CREATE",
                user=request.user,
                description=f"Created Inventory Item: {inventory_item.item_name}",
            )
            inventory_item.confirm_create(
                profile_institution=request.profile_institution,
                external_identity=request.external_identity,
            )
            return Response(serializer.data, status=status.HTTP_201_CREATED)
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)


class InventoryItemDetailView(APIView):
    permission_classes = [HasInstitutionPermission]
    required_permissions = {
        "get": "can_view_inventory_items",
        "patch": "can_edit_inventory_items",
        "delete": "can_delete_inventory_items",
    }

    @extend_schema(
        responses={200: InventoryItemSerializer},
        description="Retrieve details of a specific inventory item.",
        summary="Get inventory item details",
        tags=["Item Management"],
    )
    def get(self, request, base_uuid):
        try:
            inventory_item = InventoryItem.objects.undeleted().get(base_uuid=base_uuid)
        except InventoryItem.DoesNotExist:
            return SystemNotFoundError(
                detail=f"Inventory Item with UUID {base_uuid} not found",
                status_code=status.HTTP_404_NOT_FOUND,
            )
        serializer = InventoryItemSerializer(inventory_item)
        return Response(serializer.data)

    @extend_schema(
        request=InventoryItemSerializer,
        responses={200: InventoryItemSerializer},
        description="Partially update details of a specific inventory item.",
        summary="Partially update inventory item details",
        tags=["Item Management"],
    )
    def patch(self, request, base_uuid):
        try:
            inventory_item = InventoryItem.objects.undeleted().get(base_uuid=base_uuid)
        except InventoryItem.DoesNotExist:
            return SystemNotFoundError(
                detail=f"Inventory item with UUID {base_uuid} not found",
                status_code=status.HTTP_404_NOT_FOUND,
            )
        inventory_item.approval_status = "under_update"
        old_data = InventoryItemSerializer(inventory_item).data
        serializer = InventoryItemSerializer(
            inventory_item,
            data=request.data,
            partial=True,
            context={"request": request},
        )
        if serializer.is_valid():
            price_changes_data = serializer.validated_data.pop("price_changes", None)
            updated_inventory_item = serializer.save()
            new_data = InventoryItemSerializer(updated_inventory_item).data
            changes = {
                key: {"old": old_data.get(key), "new": new_data.get(key)}
                for key in request.data.keys()
                if old_data.get(key) != new_data.get(key)
            }

            if price_changes_data:
                price_serializer = InventoryItemPriceUpdateSerializer(
                    data={"price_changes": request.data.get("price_changes")},
                    context={"request": request, "inventory_item": inventory_item},
                )
                if price_serializer.is_valid():
                    price_results = price_serializer.save()
                    changes["price_changes"] = price_results

            AuditLog.objects.create(
                content_type=ContentType.objects.get_for_model(InventoryItem),
                object_id=updated_inventory_item.id,
                action="UPDATE",
                user=request.user if request.user.is_authenticated else None,
                changes=serialize_value(changes),
                description=f"Updated inventory item {updated_inventory_item.item_name} ({updated_inventory_item.base_uuid})",
            )
            updated_inventory_item.confirm_update(
                profile_institution=request.profile_institution,
                external_identity=request.external_identity,
            )
            return Response(serializer.data)
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

    @extend_schema(
        responses={204: None},
        description="Delete a specific inventory item.",
        summary="Delete an inventory item",
        tags=["Item Management"],
    )
    def delete(self, request, base_uuid):
        try:
            inventory_item = InventoryItem.objects.undeleted().get(base_uuid=base_uuid)
        except InventoryItem.DoesNotExist:
            raise SystemNotFoundError(
                detail=f"Inventory item with UUID {base_uuid} not found",
                status_code=status.HTTP_404_NOT_FOUND,
            )

        if inventory_item.get_quantity_on_hand() > 0:
            validation_error("Product cannot be deleted while inventory exists.")

        if (
            BranchInventoryItemStockLayer.objects.undeleted()
            .filter(
                branch_inventory_item__inventory_item=inventory_item,
                deleted_at__isnull=True,
                quantity_remaining__gt=0,
            )
            .exists()
        ):
            validation_error(
                "Product cannot be deleted while inventory exists in other branches."
            )

        with transaction.atomic():
            inventory_item_data = InventoryItemSerializer(inventory_item).data
            inventory_item_id = inventory_item.id
            inventory_item.confirm_delete(
                profile_institution=request.profile_institution,
                external_identity=request.external_identity,
            )
            AuditLog.objects.create(
                content_type=ContentType.objects.get_for_model(InventoryItem),
                object_id=inventory_item_id,
                action="DELETE",
                user=request.user if request.user.is_authenticated else None,
                changes=serialize_value(inventory_item_data),
                description=f"Deleted inventory item {inventory_item_data['item_name']} ({base_uuid})",
            )

        return Response(status=status.HTTP_204_NO_CONTENT)


class InventoryItemImageListCreateView(BaseItemView):

    permission_classes = [HasInstitutionPermission]
    required_permissions = {
        "get": "can_view_inventory_items",
        "post": "can_create_inventory_items",
    }

    @extend_schema(
        responses={200: InventoryItemImageSerializer(many=True)},
        description="Retrieve inventory item images. Optionally filter by inventory item UUID.",
        summary="List inventory item images",
        tags=["Item Management"],
        parameters=[
            inventory_item_uuid_param(required=True),
        ],
    )
    def get(self, request):
        institution = self.get_institution(request)
        inventory_item_uuid = request.query_params.get("inventory_item_uuid")

        if not inventory_item_uuid:
            validation_error("inventory_item_uuid is required.")

        inventory_item = self.get_object_by_uuid(
            InventoryItem, inventory_item_uuid, institution
        )

        if not inventory_item:
            raise SystemNotFoundError(
                detail=f"Inventory item with UUID {inventory_item_uuid} not found",
                status_code=status.HTTP_404_NOT_FOUND,
            )

        queryset = (
            InventoryItemImage.objects.undeleted()
            .filter(
                inventory_item=inventory_item,
            )
            .select_related("inventory_item")
        )

        paginator = CustomPageNumberPagination()
        page = paginator.paginate_queryset(queryset, request)
        serializer = InventoryItemImageSerializer(
            page,
            many=True,
            context={"request": request},
        )
        return paginator.get_paginated_response(serializer.data)

    @extend_schema(
        request=InventoryItemImageSerializer(many=True),
        responses={201: InventoryItemImageSerializer(many=True)},
        description="Create one or more inventory item images.",
        summary="Create inventory item images",
        tags=["Item Management"],
        parameters=[
            inventory_item_uuid_param(required=True),
        ],
    )
    def post(self, request):
        institution = self.get_institution(request)
        inventory_item_uuid = request.query_params.get("inventory_item_uuid")

        if not inventory_item_uuid:
            validation_error("inventory_item_uuid is required.")

        inventory_item = self.get_object_by_uuid(
            InventoryItem, inventory_item_uuid, institution
        )

        if not inventory_item:
            raise SystemNotFoundError(
                detail=f"Inventory item with UUID {inventory_item_uuid} not found",
                status_code=status.HTTP_404_NOT_FOUND,
            )

        is_many = isinstance(request.data, list)

        serializer = InventoryItemImageSerializer(
            data=request.data,
            many=is_many,
            context={"request": request, "inventory_item": inventory_item},
        )

        serializer.is_valid(raise_exception=True)

        with transaction.atomic():
            inventory_item_images = serializer.save(inventory_item=inventory_item)

            if not is_many:
                inventory_item_images = [inventory_item_images]

            for image in inventory_item_images:
                log_action(
                    model_class=InventoryItemImage,
                    object_id=image.id,
                    action="CREATE",
                    user=request.user if request.user.is_authenticated else None,
                    description=(
                        f"Created image {image.base_uuid} for inventory item "
                        f"{image.inventory_item.item_name}"
                    ),
                )

        output_serializer = InventoryItemImageSerializer(
            inventory_item_images,
            many=True,
            context={"request": request},
        )
        return Response(output_serializer.data, status=status.HTTP_201_CREATED)


class InventoryItemImageDetailView(APIView):
    permission_classes = [HasInstitutionPermission]
    required_permissions = {
        "get": "can_view_inventory_items",
        "patch": "can_edit_inventory_items",
        "delete": "can_delete_inventory_items",
    }

    def get_object(self, request, base_uuid):
        try:
            return (
                InventoryItemImage.objects.undeleted()
                .select_related("inventory_item")
                .get(
                    base_uuid=base_uuid,
                    inventory_item__institution=get_institution(request),
                )
            )
        except InventoryItemImage.DoesNotExist:
            raise SystemNotFoundError(
                detail=f"Inventory item image with UUID {base_uuid} not found",
                status_code=status.HTTP_404_NOT_FOUND,
            )

    @extend_schema(
        responses={200: InventoryItemImageSerializer},
        description="Retrieve details of a specific inventory item image.",
        summary="Get inventory item image details",
        tags=["Item Management"],
    )
    def get(self, request, base_uuid):
        image = self.get_object(request, base_uuid)
        serializer = InventoryItemImageSerializer(
            image,
            context={"request": request},
        )
        return Response(serializer.data)

    @extend_schema(
        request=InventoryItemImageSerializer,
        responses={200: InventoryItemImageSerializer},
        description="Partially update a specific inventory item image.",
        summary="Partially update inventory item image",
        tags=["Item Management"],
    )
    def patch(self, request, base_uuid):
        image = self.get_object(request, base_uuid)
        old_data = InventoryItemImageSerializer(
            image,
            context={"request": request},
        ).data
        serializer = InventoryItemImageSerializer(
            image,
            data=request.data,
            partial=True,
            context={"request": request},
        )
        serializer.is_valid(raise_exception=True)
        updated_image = serializer.save()
        new_data = InventoryItemImageSerializer(
            updated_image,
            context={"request": request},
        ).data

        changes = {
            key: {"old": old_data.get(key), "new": new_data.get(key)}
            for key in request.data.keys()
            if old_data.get(key) != new_data.get(key)
        }

        log_action(
            model_class=InventoryItemImage,
            object_id=updated_image.id,
            action="UPDATE",
            user=request.user if request.user.is_authenticated else None,
            changes=serialize_value(changes),
            description=f"Updated inventory item image ({updated_image.base_uuid})",
        )

        return Response(serializer.data)

    @extend_schema(
        responses={204: None},
        description="Delete a specific inventory item image.",
        summary="Delete inventory item image",
        tags=["Item Management"],
    )
    def delete(self, request, base_uuid):
        image = self.get_object(request, base_uuid)
        image_data = InventoryItemImageSerializer(
            image,
            context={"request": request},
        ).data
        image_id = image.id
        image.delete()

        log_action(
            model_class=InventoryItemImage,
            object_id=image_id,
            action="DELETE",
            user=request.user if request.user.is_authenticated else None,
            changes=serialize_value(image_data),
            description=f"Deleted inventory item image ({base_uuid})",
        )

        return Response(status=status.HTTP_204_NO_CONTENT)


class InventoryItemPreferredVendorListCreateView(APIView):
    permission_classes = [HasInstitutionPermission]
    required_permissions = {
        "get": "can_view_inventory_items",
        "post": "can_edit_inventory_items",
    }

    def get_inventory_item(self, request, base_uuid):
        return get_object_or_404(
            InventoryItem,
            base_uuid=base_uuid,
            institution=get_institution(request),
            deleted_at__isnull=True,
        )

    def get_queryset(self, inventory_item):
        return (
            ItemVendor.objects.filter(
                item=inventory_item,
                deleted_at__isnull=True,
                vendor__deleted_at__isnull=True,
            )
            .select_related("vendor")
            .prefetch_related(
                Prefetch(
                    "unit_prices",
                    queryset=ItemVendorUnitPrice.objects.filter(
                        deleted_at__isnull=True,
                    ).select_related(
                        "unit_of_measure",
                        "unit_of_measure__unit_of_measure",
                    ),
                    to_attr="_active_unit_prices",
                )
            )
        )

    @extend_schema(
        responses={200: ItemVendorSerializer(many=True)},
        summary="List inventory item preferred vendors",
        tags=["Item Management"],
    )
    def get(self, request, base_uuid):
        inventory_item = self.get_inventory_item(request, base_uuid)
        serializer = ItemVendorSerializer(
            self.get_queryset(inventory_item),
            many=True,
        )
        return Response(serializer.data)

    @extend_schema(
        request=ItemPreferredVendorWriteSerializer,
        responses={201: ItemVendorSerializer},
        summary="Add an inventory item preferred vendor",
        tags=["Item Management"],
    )
    def post(self, request, base_uuid):
        inventory_item = self.get_inventory_item(request, base_uuid)
        serializer = ItemPreferredVendorWriteSerializer(
            data=request.data,
            context={"request": request, "inventory_item": inventory_item},
        )
        serializer.is_valid(raise_exception=True)
        item_vendor = serializer.save()
        return Response(
            ItemVendorSerializer(item_vendor).data,
            status=status.HTTP_201_CREATED,
        )


class InventoryItemPreferredVendorDetailView(APIView):
    permission_classes = [HasInstitutionPermission]
    required_permissions = {
        "patch": "can_edit_inventory_items",
        "delete": "can_edit_inventory_items",
    }

    def get_objects(self, request, item_base_uuid, preferred_vendor_base_uuid):
        inventory_item = get_object_or_404(
            InventoryItem,
            base_uuid=item_base_uuid,
            institution=get_institution(request),
            deleted_at__isnull=True,
        )
        item_vendor = get_object_or_404(
            ItemVendor,
            base_uuid=preferred_vendor_base_uuid,
            item=inventory_item,
            deleted_at__isnull=True,
        )
        return inventory_item, item_vendor

    @extend_schema(
        request=ItemPreferredVendorWriteSerializer,
        responses={200: ItemVendorSerializer},
        summary="Update an inventory item preferred vendor",
        tags=["Item Management"],
    )
    def patch(self, request, item_base_uuid, preferred_vendor_base_uuid):
        inventory_item, item_vendor = self.get_objects(
            request,
            item_base_uuid,
            preferred_vendor_base_uuid,
        )
        serializer = ItemPreferredVendorWriteSerializer(
            item_vendor,
            data=request.data,
            context={"request": request, "inventory_item": inventory_item},
        )
        serializer.is_valid(raise_exception=True)
        item_vendor = serializer.save()
        return Response(ItemVendorSerializer(item_vendor).data)

    @extend_schema(
        responses={204: None},
        summary="Delete an inventory item preferred vendor",
        tags=["Item Management"],
    )
    def delete(self, request, item_base_uuid, preferred_vendor_base_uuid):
        _, item_vendor = self.get_objects(
            request,
            item_base_uuid,
            preferred_vendor_base_uuid,
        )
        item_vendor.delete(using_soft_delete=False)
        return Response(status=status.HTTP_204_NO_CONTENT)


class InventoryItemAllStockLayersView(APIView):
    permission_classes = [HasInstitutionPermission]
    required_permissions = {
        "get": [
            "can_view_inventory_item_stock_layer",
            "can_view_branch_inventory_item_stock_layer",
        ],
    }

    @extend_schema(
        responses={200: InventoryItemAllStockLayersSerializer},
        summary="List an inventory item's stock layers across all locations",
        description=(
            "Retrieve active warehouse and branch stock layers for a specific "
            "inventory item, grouped by location."
        ),
        tags=["Stock Mgt"],
    )
    def get(self, request, base_uuid):
        institution = get_institution(request)

        inventory_item = get_object_or_404(
            InventoryItem,
            base_uuid=base_uuid,
            institution=institution,
            deleted_at__isnull=True,
        )

        warehouse_layers = (
            InventoryItemStockLayer.objects.filter(
                inventory_item=inventory_item,
                deleted_at__isnull=True,
            )
            .select_related("unit_of_measure", "opening_balance_account")
            .order_by("-recieved_date")
        )

        branch_layer_queryset = (
            BranchInventoryItemStockLayer.objects.filter(
                deleted_at__isnull=True,
            )
            .select_related("unit_of_measure", "source_branch")
            .order_by("-received_date")
        )

        branch_items = (
            BranchInventoryItem.objects.filter(
                inventory_item=inventory_item,
                branch__institution=institution,
                deleted_at__isnull=True,
            )
            .select_related("branch")
            .prefetch_related(
                Prefetch(
                    "stock_layers",
                    queryset=branch_layer_queryset,
                    to_attr="active_stock_layers",
                )
            )
            .order_by("branch__branch_name")
        )

        branches = [
            {
                "branch": {
                    "base_uuid": branch_item.branch.base_uuid,
                    "reference_code": branch_item.branch.reference_code,
                    "branch_name": branch_item.branch.branch_name,
                    "branch_location": branch_item.branch.branch_location,
                },
                "stock_layers": branch_item.active_stock_layers,
            }
            for branch_item in branch_items
            if branch_item.active_stock_layers
        ]

        serializer = InventoryItemAllStockLayersSerializer(
            {
                "inventory_item": inventory_item,
                "warehouse": warehouse_layers,
                "branches": branches,
            }
        )
        return Response(serializer.data)


class FiscalYearListView(APIView, SearchOrderMixin):
    permission_classes = [HasInstitutionPermission]
    required_permissions = {
        "get": "can_view_fiscal_years",
        "post": "can_create_fiscal_years",
    }

    queryset = FiscalYear.objects.undeleted()

    @extend_schema(
        request=FiscalYearSerializer,
        responses={200: FiscalYearSerializer(many=True)},
        description="Retrieve a list of all fiscal years. Supports searching by year.",
        summary="List all fiscal years",
        tags=["Fiscal Management"],
        parameters=[
            SEARCH_PARAM,
            ORDERING_PARAM,
        ],
    )
    def get(self, request):
        fiscal_years = self.queryset.filter(
            institution=get_institution(request),
        )

        fiscal_years = self.apply_filters(fiscal_years)
        fiscal_years = self.apply_search(fiscal_years)
        fiscal_years = self.apply_ordering(fiscal_years)

        paginator = CustomPageNumberPagination()
        paginator_qs = paginator.paginate_queryset(fiscal_years, request)
        serializer = FiscalYearSerializer(paginator_qs, many=True)
        return paginator.get_paginated_response(serializer.data)

    @extend_schema(
        request=FiscalYearSerializer,
        responses={201: FiscalYearSerializer},
        description="Create a new fiscal year.",
        summary="Create a new fiscal year",
        tags=["Fiscal Management"],
    )
    def post(self, request):
        serializer = FiscalYearSerializer(
            data=request.data,
            context={"request": request},
        )
        if serializer.is_valid():
            fiscal_year = serializer.save(institution=get_institution(request))
            AuditLog.objects.create(
                content_type=ContentType.objects.get_for_model(FiscalYear),
                object_id=fiscal_year.pk,
                action="CREATE",
                user=request.user,
                description=f"Created Fiscal Year: {fiscal_year.name}",
            )
            fiscal_year.confirm_create(
                profile_institution=request.profile_institution,
                external_identity=request.external_identity,
            )
            return Response(serializer.data, status=status.HTTP_201_CREATED)
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)


class FiscalYearDetailView(APIView):
    permission_classes = [HasInstitutionPermission]
    required_permissions = {
        "get": "can_view_fiscal_years",
        "patch": "can_edit_fiscal_years",
        "delete": "can_delete_fiscal_years",
    }

    def _get_fiscal_year_object(self, request, base_uuid):
        return get_or_raise(
            FiscalYear.objects.undeleted(),
            message=f"Fiscal year with UUID {base_uuid} not found",
            base_uuid=base_uuid,
            institution=get_institution(request),
        )

    @extend_schema(
        responses={200: FiscalYearSerializer},
        description="Retrieve details of a specific fiscal year.",
        summary="Get fiscal year details",
        tags=["Fiscal Management"],
    )
    def get(self, request, base_uuid):
        fiscal_year = self._get_fiscal_year_object(request, base_uuid)
        serializer = FiscalYearSerializer(fiscal_year)
        return Response(serializer.data)

    @extend_schema(
        request=FiscalYearSerializer,
        responses={200: FiscalYearSerializer},
        description="Partially update details of a specific fiscal year.",
        summary="Partially update fiscal year details",
        tags=["Fiscal Management"],
    )
    def patch(self, request, base_uuid):
        fiscal_year = self._get_fiscal_year_object(request, base_uuid)
        fiscal_year.approval_status = "under_update"
        old_data = FiscalYearSerializer(fiscal_year).data
        serializer = FiscalYearSerializer(
            fiscal_year,
            data=request.data,
            partial=True,
            context={"request": request},
        )
        if serializer.is_valid():
            updated_fiscal_year = serializer.save()
            new_data = FiscalYearSerializer(updated_fiscal_year).data
            changes = {
                key: {"old": old_data.get(key), "new": new_data.get(key)}
                for key in request.data.keys()
                if old_data.get(key) != new_data.get(key)
            }
            AuditLog.objects.create(
                content_type=ContentType.objects.get_for_model(FiscalYear),
                object_id=updated_fiscal_year.id,
                action="UPDATE",
                user=request.user if request.user.is_authenticated else None,
                changes=changes,
                description=f"Updated fiscal year {updated_fiscal_year.name} ({updated_fiscal_year.base_uuid})",
            )
            updated_fiscal_year.confirm_update(
                profile_institution=request.profile_institution,
                external_identity=request.external_identity,
            )
            return Response(serializer.data)
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

    @extend_schema(
        responses={204: None},
        description="Delete a specific fiscal year.",
        summary="Delete a fiscal year",
        tags=["Fiscal Management"],
    )
    @transaction.atomic
    def delete(self, request, base_uuid):
        fiscal_year = self._get_fiscal_year_object(request, base_uuid)

        fiscal_year_data = FiscalYearSerializer(fiscal_year).data
        fiscal_year_id = fiscal_year.id
        fiscal_year.confirm_delete(
            profile_institution=request.profile_institution,
            external_identity=request.external_identity,
        )
        AuditLog.objects.create(
            content_type=ContentType.objects.get_for_model(FiscalYear),
            object_id=fiscal_year_id,
            action="DELETE",
            user=request.user if request.user.is_authenticated else None,
            changes=fiscal_year_data,
            description=f"Deleted fiscal year {fiscal_year_data['name']} ({base_uuid})",
        )
        return Response(status=status.HTTP_204_NO_CONTENT)


class ItemUnitOfMeasureListView(BaseItemView, SearchOrderMixin):
    permission_classes = [HasInstitutionPermission]
    required_permissions = {
        "get": "can_view_item_unit_of_measures",
        "post": "can_create_item_unit_of_measures",
    }

    queryset = ItemUnitOfMeasure.objects.undeleted()

    @extend_schema(
        request=ItemUnitOfMeasureSerializer,
        responses={200: ItemUnitOfMeasureSerializer(many=True)},
        description="Retrieve a list of all item unit of measures.",
        summary="List all item unit of measures",
        tags=["Item Management"],
        parameters=[
            SEARCH_PARAM,
            ORDERING_PARAM,
        ],
    )
    def get(self, request):
        institution = self.get_institution(request)
        if not institution:
            raise SystemNotFoundError(
                detail=f"User does not belong to an institution.",
                status_code=status.HTTP_403_FORBIDDEN,
            )

        item_unit_of_measures = self.queryset.filter(
            institution=institution,
        )

        item_unit_of_measures = self.apply_search(item_unit_of_measures)
        item_unit_of_measures = self.apply_ordering(item_unit_of_measures)
        item_unit_of_measures = self.apply_filters(item_unit_of_measures)

        paginator = CustomPageNumberPagination()
        paginator_qs = paginator.paginate_queryset(item_unit_of_measures, request)
        serializer = ItemUnitOfMeasureSerializer(paginator_qs, many=True)
        return paginator.get_paginated_response(serializer.data)

    @extend_schema(
        request=ItemUnitOfMeasureSerializer(many=True),
        responses={202: OpenApiTypes.OBJECT},
        description="Queue item units of measure for bulk creation.",
        summary="Queue bulk creation of item units of measure",
        tags=["Item Management"],
    )
    def post(self, request):
        institution = self.get_institution(request)
        if not institution:
            raise SystemNotFoundError(
                detail="User does not belong to an institution.",
                status_code=status.HTTP_403_FORBIDDEN,
            )

        serializer = ItemUnitOfMeasureSerializer(
            data=request.data,
            many=True,
            context={"request": request},
        )
        serializer.is_valid(raise_exception=True)

        rows = [
            {key: serialize_value(value) for key, value in row.items()}
            for row in serializer.validated_data
        ]

        result = bulk_create_inventory_units_of_measure.delay(
            institution_id=institution.pk,
            rows=rows,
            requested_by_id=request.user.pk,
        )

        return Response(
            {
                "detail": f"{len(rows)} unit(s) queued for creation.",
                "task_id": result.id,
                "total_rows": len(rows),
            },
            status=status.HTTP_202_ACCEPTED,
        )


class ItemUnitOfMeasureDetailView(BaseItemView):
    permission_classes = [HasInstitutionPermission]
    required_permissions = {
        "get": "can_view_item_unit_of_measures",
        "patch": "can_edit_item_unit_of_measures",
        "delete": "can_delete_item_unit_of_measures",
    }

    @extend_schema(
        responses={200: ItemUnitOfMeasureSerializer},
        description="Retrieve details of a specific item unit of measure.",
        summary="Get item unit of measure details",
        tags=["Item Management"],
    )
    def get(self, request, base_uuid):
        institution = self.get_institution(request)
        if not institution:
            return Response(
                {"error": "User does not belong to an institution."},
                status=status.HTTP_403_FORBIDDEN,
            )

        item_unit_of_measure = self.get_object_by_uuid(
            ItemUnitOfMeasure, base_uuid, institution
        )
        if not item_unit_of_measure:
            return SystemNotFoundError(status_code=status.HTTP_404_NOT_FOUND)

        serializer = ItemUnitOfMeasureSerializer(item_unit_of_measure)
        return Response(serializer.data)

    @extend_schema(
        request=ItemUnitOfMeasureSerializer,
        responses={200: ItemUnitOfMeasureSerializer},
        description="Partially update details of a specific item unit of measure.",
        summary="Partially update item unit of measure details",
        tags=["Item Management"],
    )
    def patch(self, request, base_uuid):
        institution = self.get_institution(request)
        if not institution:
            raise SystemNotFoundError(
                detail=f"User does not belong to an institution.",
                status_code=status.HTTP_403_FORBIDDEN,
            )

        item_unit_of_measure = self.get_object_by_uuid(
            ItemUnitOfMeasure, base_uuid, institution
        )
        item_unit_of_measure.approval_status = "under_update"
        if not item_unit_of_measure:
            return SystemNotFoundError(status_code=status.HTTP_404_NOT_FOUND)

        old_data = ItemUnitOfMeasureSerializer(item_unit_of_measure).data

        serializer = ItemUnitOfMeasureSerializer(
            item_unit_of_measure, data=request.data, partial=True
        )
        if serializer.is_valid():
            updated_item_unit_of_measure = serializer.save()

            new_data = ItemUnitOfMeasureSerializer(updated_item_unit_of_measure).data
            changes = {
                key: {"old": old_data.get(key), "new": new_data.get(key)}
                for key in request.data.keys()
                if old_data.get(key) != new_data.get(key)
            }

            AuditLog.objects.create(
                content_type=ContentType.objects.get_for_model(ItemUnitOfMeasure),
                object_id=updated_item_unit_of_measure.id,
                action="UPDATE",
                user=request.user,
                changes=changes,
                description=f"Updated item unit of measure {updated_item_unit_of_measure.unit_name} ({updated_item_unit_of_measure.base_uuid})",
            )
            updated_item_unit_of_measure.confirm_update(
                profile_institution=request.profile_institution,
                external_identity=request.external_identity,
            )
            return Response(serializer.data)
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

    @extend_schema(
        responses={204: None},
        description="Delete a specific item unit of measure.",
        summary="Delete an item unit of measure",
        tags=["Item Management"],
    )
    def delete(self, request, base_uuid):
        institution = self.get_institution(request)
        if not institution:
            return SystemNotFoundError(
                detail=f"User does not belong to an institution.",
                status_code=status.HTTP_403_FORBIDDEN,
            )

        item_unit_of_measure = self.get_object_by_uuid(
            ItemUnitOfMeasure, base_uuid, institution
        )
        if not item_unit_of_measure:
            return SystemNotFoundError(status_code=status.HTTP_404_NOT_FOUND)

        item_unit_of_measure_data = ItemUnitOfMeasureSerializer(
            item_unit_of_measure
        ).data
        item_unit_of_measure_id = item_unit_of_measure.id

        AuditLog.objects.create(
            content_type=ContentType.objects.get_for_model(ItemUnitOfMeasure),
            object_id=item_unit_of_measure_id,
            action="DELETE",
            user=request.user,
            changes=item_unit_of_measure_data,
            description=f"Deleted item unit of measure {item_unit_of_measure_data['unit_name']} ({base_uuid})",
        )
        item_unit_of_measure.confirm_delete(
            profile_institution=request.profile_institution,
            external_identity=request.external_identity,
        )
        return Response(status=status.HTTP_204_NO_CONTENT)


class BulkInventoryItemUploadView(APIView):
    permission_classes = [HasInstitutionPermission]
    required_permissions = {
        "get": "can_download_bulk_inventory_template",
        "post": "can_create_inventory_items",
    }

    @extend_schema(
        responses={200: None},
        summary="Download Inventory Excel Template",
        description="Download an Excel or CSV template for bulk Inventory creation.",
        tags=["Item Management"],
    )
    def get(self, request):
        format_type = request.query_params.get("format_type", "excel")
        institution = get_institution(request)
        template_bytes, content_type, extension = generate_bulk_inventory_template(
            format_type,
            institution=institution,
        )

        return HttpResponse(
            template_bytes,
            content_type=content_type,
            headers={
                "Content-Disposition": f'attachment; filename="inventory_items_template.{extension}"'
            },
        )

    @extend_schema(
        request={
            "multipart/form-data": {
                "type": "object",
                "properties": {
                    "file": {
                        "type": "string",
                        "format": "binary",
                        "description": (
                            "Excel (.xlsx/.xls) with up to four sheets: Items (required), "
                            "Units of Measure (optional), Opening Stock (optional), "
                            "Selling Branches (optional). "
                            "CSV supported for items-only uploads."
                        ),
                    }
                },
                "required": ["file"],
            }
        },
        responses={
            200: {
                "description": "File accepted, processing in background.",
                "content": {
                    "application/json": {
                        "schema": {
                            "type": "object",
                            "properties": {
                                "message": {"type": "string"},
                            },
                        }
                    }
                },
            },
            400: {
                "description": "Validation failed — row-level errors returned.",
                "content": {
                    "application/json": {
                        "schema": {
                            "type": "object",
                            "properties": {
                                "status": {"type": "string"},
                                "message": {"type": "string"},
                                "errors": {"type": "array"},
                            },
                        }
                    }
                },
            },
        },
        summary="Bulk upload inventory items from Excel/CSV",
        description=(
            "Upload a multi-sheet Excel file to bulk-create inventory items, units of measure, "
            "and opening stock. The file is fully validated synchronously — if any errors exist "
            "they are returned immediately. If validation passes, the creation is processed in "
            "the background via Celery."
        ),
        tags=["Item Management"],
    )
    def post(self, request):
        uploaded_file = request.FILES.get("file")

        if not uploaded_file:
            raise validation_error("File is required, No file uploaded.")

        institution = get_institution(request)
        file_bytes = uploaded_file.read()
        filename = uploaded_file.name

        validation_result = process_bulk_inventory_upload(
            file_bytes=file_bytes,
            filename=filename,
            request=request,
            dry_run=True,
        )

        if validation_result["status"] != "success":
            errors = validation_result.get("errors")
            message = validation_result.get("message", "Validation failed.")

            if errors:
                formatted = []
                for e in errors:
                    if "row" in e:
                        row_errors = e.get("errors", [])
                        ref = e.get("reference_code") or f"row {e['row']}"
                        for row_err in row_errors:
                            formatted.append(f"[{ref}] {row_err}")
                    elif "sheet" in e:
                        formatted.append(
                            f"[{e['sheet']} row {e.get('row', '?')}] {e.get('error', '')}"
                        )
                    elif "reference_code" in e:
                        formatted.append(
                            f"[{e['reference_code']}] {e.get('error', '')}"
                        )
                    else:
                        formatted.append(str(e))

                raise validation_error({"file": message, "errors": formatted})
            else:
                raise validation_error(message)

        bulk_inventory_upload_task.delay(
            file_bytes=file_bytes,
            filename=filename,
            user_id=request.user.id,
            institution_id=institution.id,
        )

        return Response(
            {
                "message": "File accepted. Your inventory items are being created in the background."
            },
            status=status.HTTP_200_OK,
        )


class BranchInventoryItemManagementView(SearchOrderMixin, APIView):
    permission_classes = [HasInstitutionPermission]
    required_permissions = {
        "get": "can_view_branch_inventory_items",
    }

    @extend_schema(
        responses={200: BranchInventoryItemSerializer(many=True)},
        description="Retrieve all inventory items and their specific quantities/prices "
        "for a given branch.Supports filtering by item type and sell/purchase flags.",
        summary="List inventory items by Branch",
        tags=["Branch Inventory"],
        parameters=[
            branch_uuids_param(required=False),
            OpenApiParameter(
                name="item_type",
                type=str,
                location=OpenApiParameter.QUERY,
                description="Filter by item type. Use 'GOODS' or 'SERVICES'. Case-insensitive.",
                required=False,
                enum=["GOODS", "SERVICES"],
            ),
            OpenApiParameter(
                name="can_be_sold",
                type=bool,
                location=OpenApiParameter.QUERY,
                description="Filter items that can be sold (true/false).",
                required=False,
            ),
            OpenApiParameter(
                name="can_be_purchased",
                type=bool,
                location=OpenApiParameter.QUERY,
                description="Filter items that can be purchased (true/false).",
                required=False,
            ),
            SEARCH_PARAM,
            ORDERING_PARAM,
        ],
    )
    def get(self, request):

        item_type_query = request.query_params.get("item_type")
        can_be_sold_query = request.query_params.get("can_be_sold")
        can_be_purchased_query = request.query_params.get("can_be_purchased")

        queryset = BranchInventoryItem.objects.filter(
            deleted_at__isnull=True,
            inventory_item__deleted_at__isnull=True,
        )

        queryset = filter_queryset_by_branches(queryset, request)

        if item_type_query:
            item_type_query = item_type_query.upper()

            valid_types = [choice[0] for choice in InventoryItem.ITEM_TYPE_CHOICES]

            if item_type_query in valid_types:
                queryset = queryset.filter(inventory_item__item_type=item_type_query)

        if can_be_sold_query is not None:
            if can_be_sold_query.lower() in ["true", "false"]:
                queryset = queryset.filter(
                    inventory_item__can_be_sold=can_be_sold_query.lower() == "true"
                )

        if can_be_purchased_query is not None:
            if can_be_purchased_query.lower() in ["true", "false"]:
                queryset = queryset.filter(
                    inventory_item__can_be_purchased=can_be_purchased_query.lower()
                    == "true"
                )

        queryset = self.apply_search(queryset)
        queryset = self.apply_ordering(queryset)

        paginator = CustomPageNumberPagination()
        paginator_qs = paginator.paginate_queryset(queryset, request)
        serializer = BranchInventoryItemSerializer(
            paginator_qs,
            many=True,
            context={"request": request},
        )

        return paginator.get_paginated_response(serializer.data)


class BranchInventoryItemDetailView(APIView):
    permission_classes = [HasInstitutionPermission]
    required_permissions = {
        "get": "can_view_branch_inventory_items",
        "patch": "can_edit_branch_inventory_items",
    }

    @extend_schema(
        responses={200: BranchInventoryItemSerializer},
        description="Retrieve the specific quantity/price details for one inventory item at a given branch.",
        summary="Get single inventory item details by Branch",
        tags=["Branch Inventory"],
    )
    def get(self, request, item_uuid):
        branch_inventory_item = get_object_or_404(
            BranchInventoryItem,
            base_uuid=item_uuid,
            deleted_at__isnull=True,
            inventory_item__deleted_at__isnull=True,
        )
        serializer = BranchInventoryItemSerializer(
            branch_inventory_item,
            context={"request": request},
        )
        return Response(serializer.data, status=status.HTTP_200_OK)

    @extend_schema(
        request=BranchSellingPriceUpdateSerializer,
        responses={200: BranchInventoryItemSerializer},
        summary="Update the selling price of a branch inventory item.",
        tags=["Branch Inventory"],
    )
    def patch(self, request, item_uuid):

        branch_inventory_item = get_object_or_404(
            BranchInventoryItem,
            base_uuid=item_uuid,
            deleted_at__isnull=True,
            inventory_item__deleted_at__isnull=True,
        )

        serializer = BranchSellingPriceUpdateSerializer(
            data=request.data,
            context={
                "request": request,
                "branch_inventory_item": branch_inventory_item,
            },
        )

        serializer.is_valid(raise_exception=True)
        serializer.save()

        response_serializer = BranchInventoryItemSerializer(
            branch_inventory_item,
            context={"request": request},
        )

        return Response(response_serializer.data, status=status.HTTP_200_OK)


class CombinedStockMovementListView(APIView):
    permission_classes = [HasInstitutionPermission]
    required_permissions = {
        "get": [
            "can_view_stock_allocations",
            "can_view_branch_stock_movements",
        ],
    }

    fields = (
        "id",
        "base_uuid",
        "reference_code",
        "movement_type",
        "movement_date",
        "status",
        "branch_from_name",
        "branch_to_name",
        "item_count",
        "created_at",
    )

    @extend_schema(
        responses={200: CombinedStockMovementSerializer(many=True)},
        summary="List allocations and branch stock transfers",
        description=(
            "Returns a database-paginated feed of main-to-branch allocations "
            "and branch-to-branch stock movements."
        ),
        tags=["Stock Movements"],
        parameters=[
            OpenApiParameter(
                name="institution_base_uuid",
                type=OpenApiTypes.UUID,
                required=False,
            ),
            OpenApiParameter(
                name="branch_base_uuid",
                type=OpenApiTypes.UUID,
                required=False,
            ),
            OpenApiParameter(
                name="status",
                type=OpenApiTypes.STR,
                required=False,
                enum=["PENDING", "ALLOCATED", "CANCELLED"],
            ),
            OpenApiParameter(
                name="movement_type",
                type=OpenApiTypes.STR,
                required=False,
                enum=["MAIN_TO_BRANCH", "BRANCH_TO_BRANCH"],
            ),
            OpenApiParameter(
                name="date_from",
                type=OpenApiTypes.DATE,
                required=False,
            ),
            OpenApiParameter(
                name="date_to",
                type=OpenApiTypes.DATE,
                required=False,
            ),
        ],
    )
    def get(self, request):
        institution = get_institution(request)
        params = request.query_params

        institution_uuid = self._parse_uuid(
            params.get("institution_base_uuid"),
            "institution_base_uuid",
        )
        branch_uuid = self._parse_uuid(
            params.get("branch_base_uuid"),
            "branch_base_uuid",
        )
        movement_status = params.get("status")
        movement_type = params.get("movement_type")
        date_from = self._parse_date(params.get("date_from"), "date_from")
        date_to = self._parse_date(params.get("date_to"), "date_to")

        if movement_status and movement_status not in {
            "PENDING",
            "ALLOCATED",
            "CANCELLED",
        }:
            raise ValidationError({"status": "Invalid movement status."})

        if movement_type and movement_type not in {
            "MAIN_TO_BRANCH",
            "BRANCH_TO_BRANCH",
        }:
            raise ValidationError({"movement_type": "Invalid movement type."})

        if date_from and date_to and date_from > date_to:
            raise ValidationError({"date_to": "Date to must be on or after date from."})

        allocations = StockToBranchAllocation.objects.filter(
            deleted_at__isnull=True,
            branch_to__institution=institution,
        )
        transfers = BranchToBranchStockMovement.objects.filter(
            deleted_at__isnull=True,
            branch_from__institution=institution,
        )

        if institution_uuid:
            allocations = allocations.filter(
                branch_to__institution__base_uuid=institution_uuid
            )
            transfers = transfers.filter(
                branch_from__institution__base_uuid=institution_uuid
            )

        if branch_uuid:
            allocations = allocations.filter(branch_to__base_uuid=branch_uuid)
            transfers = transfers.filter(
                Q(branch_from__base_uuid=branch_uuid)
                | Q(branch_to__base_uuid=branch_uuid)
            )

        if movement_status:
            allocations = allocations.filter(alloc_status=movement_status)
            transfers = transfers.filter(stock_movement_status=movement_status)

        if date_from:
            date_from_value = timezone.make_aware(datetime.combine(date_from, time.min))
            allocations = allocations.filter(allocation_date__gte=date_from_value)
            transfers = transfers.filter(stock_movement_date__gte=date_from_value)

        if date_to:
            date_to_value = timezone.make_aware(
                datetime.combine(date_to + timedelta(days=1), time.min)
            )
            allocations = allocations.filter(allocation_date__lt=date_to_value)
            transfers = transfers.filter(stock_movement_date__lt=date_to_value)

        allocation_rows = (
            allocations.order_by()
            .annotate(
                movement_type=Value(
                    "MAIN_TO_BRANCH",
                    output_field=CharField(),
                ),
                movement_date=F("allocation_date"),
                status=F("alloc_status"),
                branch_from_name=Value(None, output_field=CharField()),
                branch_to_name=F("branch_to__branch_name"),
                item_count=Count(
                    "items",
                    filter=Q(items__deleted_at__isnull=True),
                ),
            )
            .values(*self.fields)
        )

        transfer_rows = (
            transfers.order_by()
            .annotate(
                movement_type=Value(
                    "BRANCH_TO_BRANCH",
                    output_field=CharField(),
                ),
                movement_date=F("stock_movement_date"),
                status=F("stock_movement_status"),
                branch_from_name=F("branch_from__branch_name"),
                branch_to_name=F("branch_to__branch_name"),
                item_count=Count(
                    "items",
                    filter=Q(items__deleted_at__isnull=True),
                ),
            )
            .values(*self.fields)
        )

        if movement_type == "MAIN_TO_BRANCH":
            feed = allocation_rows
        elif movement_type == "BRANCH_TO_BRANCH":
            feed = transfer_rows
        else:
            feed = allocation_rows.union(transfer_rows, all=True)

        feed = feed.order_by("-created_at", "-movement_type", "-id")

        paginator = CustomPageNumberPagination()
        page = paginator.paginate_queryset(feed, request)
        serializer = CombinedStockMovementSerializer(page, many=True)

        return paginator.get_paginated_response(serializer.data)

    @staticmethod
    def _parse_uuid(value, field):
        if not value:
            return None
        try:
            return UUID(value)
        except (TypeError, ValueError):
            raise ValidationError({field: "Enter a valid UUID."})

    @staticmethod
    def _parse_date(value, field):
        if not value:
            return None

        parsed = parse_date(value)
        if parsed is None:
            raise ValidationError({field: "Use a valid date in YYYY-MM-DD format."})
        return parsed


class StockToBranchAllocationListCreateView(APIView, SearchOrderMixin):
    permission_classes = [HasInstitutionPermission]
    required_permissions = {
        "get": "can_view_stock_allocations",
        "post": "can_create_stock_allocations",
    }

    @extend_schema(
        request=StockToBranchAllocationSerializer,
        responses={200: StockToBranchAllocationSerializer(many=True)},
        summary="List all main stock to branch allocations",
        tags=["Stock Allocation to Branch"],
        parameters=[
            SEARCH_PARAM,
            ORDERING_PARAM,
            branch_uuids_param(required=True),
        ],
    )
    def get(self, request):

        allocations = StockToBranchAllocation.objects.filter(deleted_at__isnull=True)

        allocations = filter_queryset_by_branches(
            allocations, request, branch_lookup_field="branch_to__base_uuid"
        )

        allocations = allocations.annotate(
            pending_priority=Case(
                When(alloc_status="PENDING", then=0),
                default=1,
                output_field=IntegerField(),
            )
        ).order_by("pending_priority", "created_at")

        allocations = self.apply_search(allocations)
        allocations = self.apply_ordering(allocations)

        paginator = CustomPageNumberPagination()
        paginator_qs = paginator.paginate_queryset(allocations, request)
        serializer = StockToBranchAllocationSerializer(
            paginator_qs, many=True, context={"request": request}
        )
        return paginator.get_paginated_response(serializer.data)

    @extend_schema(
        request=StockToBranchAllocationSerializer,
        responses={201: StockToBranchAllocationSerializer},
        summary="Create a new main stock to branch allocation",
        tags=["Stock Allocation to Branch"],
    )
    def post(self, request):
        serializer = StockToBranchAllocationSerializer(
            data=request.data, context={"request": request}
        )
        if serializer.is_valid():
            allocation = serializer.save()
            AuditLog.objects.create(
                content_type=ContentType.objects.get_for_model(StockToBranchAllocation),
                object_id=allocation.pk,
                action="CREATE",
                user=request.user,
                description=f"Created Stock to Branch Allocation: {allocation.reference_code}",
            )
            allocation.confirm_create(
                profile_institution=request.profile_institution,
                external_identity=request.external_identity,
            )
            return Response(serializer.data, status=status.HTTP_201_CREATED)
        return Response(
            {"detail": serializer.errors}, status=status.HTTP_400_BAD_REQUEST
        )


class StockToBranchAllocationDetailView(APIView):
    """
    View to retrieve, update, or delete a main stock to branch allocation.
    """

    permission_classes = [HasInstitutionPermission]
    required_permissions = {
        "get": "can_view_stock_allocations",
        "patch": "can_edit_stock_allocations",
        "delete": "can_delete_stock_allocations",
    }

    @extend_schema(
        responses={200: StockToBranchAllocation},
        summary="Retrieve a main stock to branch allocation",
        tags=["Stock Allocation to Branch"],
    )
    def get(self, request, base_uuid):
        allocation = get_object_or_404(StockToBranchAllocation, base_uuid=base_uuid)
        serializer = StockToBranchAllocationSerializer(allocation)
        return Response(serializer.data)

    @extend_schema(
        request=StockToBranchAllocationSerializer,
        responses={200: StockToBranchAllocationSerializer},
        summary="Update a stock to branch allocation",
        tags=["Stock Allocation to Branch"],
    )
    def patch(self, request, base_uuid):
        try:
            allocation = StockToBranchAllocation.objects.get(base_uuid=base_uuid)
        except StockToBranchAllocation.DoesNotExist:
            raise SystemNotFoundError(
                detail=f"Stock at allocated branch with UUID {base_uuid} not found",
                status_code=status.HTTP_404_NOT_FOUND,
            )

        old_data = StockToBranchAllocationSerializer(allocation).data

        serializer = StockToBranchAllocationSerializer(
            allocation, data=request.data, partial=True
        )

        if serializer.is_valid():

            updated_allocation = serializer.save()
            new_data = StockToBranchAllocationSerializer(updated_allocation).data

            changes = {
                key: {"old": old_data.get(key), "new": new_data.get(key)}
                for key in request.data.keys()
                if old_data.get(key) != new_data.get(key)
            }

            AuditLog.objects.create(
                content_type=ContentType.objects.get_for_model(StockToBranchAllocation),
                object_id=updated_allocation.id,
                action="UPDATE",
                user=request.user if request.user.is_authenticated else None,
                changes=changes,
                description=f"Updated stock to branch allocation {updated_allocation.reference_code} ({updated_allocation.base_uuid})",
            )
            updated_allocation.confirm_update(
                profile_institution=request.profile_institution,
                external_identity=request.external_identity,
            )
            return Response(serializer.data)
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

    @extend_schema(
        responses={204: None},
        description="Delete a specific stock to branch allocation.",
        summary="Delete a stock to branch allocation",
        tags=["Stock Allocation to Branch"],
    )
    def delete(self, request, base_uuid):
        try:
            allocation = StockToBranchAllocation.objects.get(base_uuid=base_uuid)
        except StockToBranchAllocation.DoesNotExist:
            return SystemNotFoundError(
                detail=f"Stock at allocated branch with {base_uuid} not found",
                status_code=status.HTTP_404_NOT_FOUND,
            )

        allocation_data = StockToBranchAllocationSerializer(allocation).data
        allocation_id = allocation.id

        AuditLog.objects.create(
            content_type=ContentType.objects.get_for_model(StockToBranchAllocation),
            object_id=allocation_id,
            action="DELETE",
            user=request.user if request.user.is_authenticated else None,
            changes=allocation_data,
            description=f"Deleted stock to branch allocation {allocation_data['reference_code']} ({base_uuid})",
        )

        allocation.confirm_delete(
            profile_institution=request.profile_institution,
            external_identity=request.external_identity,
        )

        return Response(status=status.HTTP_204_NO_CONTENT)


class ItemBranchesView(APIView):
    permission_classes = [HasInstitutionPermission]
    required_permissions = {
        "get": "can_view_item_distribution",
        "post": "can_create_item_distribution",
        "patch": "can_edit_item_distribution",
    }

    @extend_schema(
        responses=ItemDistributionSerializer(many=True),
        description="Retrieve all branches that carry a specific product, including live quantity from stock layers and base-unit selling price.",
        summary="Get branches with specific product and quantities",
        tags=["Item Distribution Management"],
        parameters=[
            OpenApiParameter(
                name="item_base_uuid",
                type=str,
                required=True,
                description="UUID of the inventory item",
            ),
        ],
    )
    def get(self, request):
        item_base_uuid = request.query_params.get("item_base_uuid")
        if not item_base_uuid:
            raise validation_error("item_base_uuid query parameter is required.")

        institution = get_institution(request)

        branches_with_item = (
            Branch.objects.filter(
                branch_inventory__inventory_item__base_uuid=item_base_uuid,
                institution__base_uuid=institution.base_uuid,
                branch_inventory__is_active=True,
                branch_inventory__deleted_at__isnull=True,
            )
            .prefetch_related(
                Prefetch(
                    "branch_inventory",
                    queryset=BranchInventoryItem.objects.filter(
                        inventory_item__base_uuid=item_base_uuid,
                        is_active=True,
                        deleted_at__isnull=True,
                    ).prefetch_related(
                        Prefetch(
                            "stock_layers",
                            queryset=BranchInventoryItemStockLayer.objects.filter(
                                quantity_remaining__gt=0,
                                deleted_at__isnull=True,
                            ),
                        ),
                        Prefetch(
                            "units",
                            queryset=BranchInventoryItemUnitOfMeasure.objects.filter(
                                is_base_unit_of_measure=True,
                                deleted_at__isnull=True,
                            ),
                        ),
                    ),
                    to_attr="filtered_inventory",
                )
            )
            .distinct()
        )

        branch_data = []

        for branch in branches_with_item:
            branch_item = next(iter(branch.filtered_inventory), None)
            if not branch_item:
                continue

            total_quantity = sum(
                layer.quantity_remaining for layer in branch_item.stock_layers.all()
            )

            base_unit = next(iter(branch_item.units.all()), None)
            selling_price = base_unit.selling_price if base_unit else None

            branch_data.append(
                {
                    "id": branch.id,
                    "branch_name": branch.branch_name,
                    "branch_location": branch.branch_location,
                    "quantity": total_quantity,
                    "selling_price": selling_price,
                    "base_uuid": branch.base_uuid,
                }
            )

        serializer = ItemDistributionSerializer(branch_data, many=True)
        return Response(serializer.data, status=status.HTTP_200_OK)

    @extend_schema(
        request=ItemDistributionRequestSerializer,
        responses={
            200: {"description": "Inventory item successfully added to branches"}
        },
        description=(
            "Add an inventory item to one or more branches. "
            "Handles three cases: (1) fresh creation, (2) restoring a previously removed entry, "
            "(3) reporting already-active entries. UOMs are synced automatically."
        ),
        summary="Add inventory item to branches",
        tags=["Item Distribution Management"],
    )
    def post(self, request):
        serializer = ItemDistributionRequestSerializer(data=request.data)
        if not serializer.is_valid():
            return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

        inventory_item_uuid = serializer.validated_data["inventory_item_id"]
        branch_base_uuids = serializer.validated_data["branch_base_uuids"]

        try:
            with transaction.atomic():
                inventory_item = get_object_or_404(
                    InventoryItem, base_uuid=inventory_item_uuid
                )

                existing_branches = Branch.objects.filter(
                    base_uuid__in=branch_base_uuids,
                    institution=inventory_item.get_institution(),
                )
                if existing_branches.count() != len(branch_base_uuids):
                    raise validation_error(
                        "One or more branch UUIDs are invalid or do not belong to the institution."
                    )

                created_entries = []
                restored_entries = []
                existing_entries = []
                branch_map = {str(b.base_uuid): b for b in existing_branches}

                institution_uoms = InventoryItemUnitOfMeasure.objects.filter(
                    inventory_item=inventory_item,
                    deleted_at__isnull=True,
                )

                for branch_uuid_str, branch in branch_map.items():
                    branch_item = BranchInventoryItem.objects.filter(
                        inventory_item=inventory_item,
                        branch=branch,
                    ).first()

                    if branch_item:
                        if branch_item.deleted_at is not None:
                            branch_item.deleted_at = None
                            branch_item.is_active = True
                            branch_item.save(update_fields=["deleted_at", "is_active"])

                            sync_uoms_to_branch_item(branch_item, institution_uoms)

                            restored_entries.append(
                                {
                                    "branch_base_uuid": branch_uuid_str,
                                    "branch_name": branch.branch_name,
                                }
                            )
                        else:
                            existing_entries.append(
                                {
                                    "branch_base_uuid": branch_uuid_str,
                                    "branch_name": branch.branch_name,
                                }
                            )
                    else:
                        branch_item = BranchInventoryItem.objects.create(
                            inventory_item=inventory_item,
                            branch=branch,
                            is_active=True,
                        )
                        sync_uoms_to_branch_item(branch_item, institution_uoms)

                        created_entries.append(
                            {
                                "branch_base_uuid": branch_uuid_str,
                                "branch_name": branch.branch_name,
                            }
                        )

                return Response(
                    {
                        "detail": (
                            f"Processed inventory item {inventory_item_uuid} for "
                            f"{len(branch_base_uuids)} branch{'es' if len(branch_base_uuids) > 1 else ''}."
                        ),
                        "created_entries": created_entries,
                        "restored_entries": restored_entries,
                        "existing_entries": existing_entries,
                        "summary": {
                            "new_branches": len(created_entries),
                            "restored_branches": len(restored_entries),
                            "existing_branches": len(existing_entries),
                        },
                    },
                    status=status.HTTP_201_CREATED,
                )

        except Exception as e:
            raise e

    @extend_schema(
        request=ItemDistributionRequestSerializer,
        responses={
            200: {"description": "Inventory item successfully removed from branches"}
        },
        description=(
            "Remove a product from one or more branches. "
            "Soft-deletes the BranchInventoryItem entries and transfers all remaining "
            "stock-layer quantities back to the institution-level InventoryItemStockLayer."
        ),
        summary="Remove product from branches with quantity transfer",
        tags=["Item Distribution Management"],
    )
    def patch(self, request):
        serializer = ItemDistributionRequestSerializer(data=request.data)
        if not serializer.is_valid():
            return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

        inventory_item_uuid = serializer.validated_data["inventory_item_id"]
        branch_base_uuids = serializer.validated_data["branch_base_uuids"]

        try:
            with transaction.atomic():
                try:
                    inventory_item = InventoryItem.objects.select_for_update().get(
                        base_uuid=inventory_item_uuid
                    )
                except InventoryItem.DoesNotExist:
                    return SystemNotFoundError(
                        detail=f"Inventory item with UUID {inventory_item_uuid} not found",
                        status_code=status.HTTP_404_NOT_FOUND,
                    )

                valid_branches = Branch.objects.filter(
                    base_uuid__in=branch_base_uuids,
                    institution=inventory_item.get_institution(),
                )
                if valid_branches.count() != len(branch_base_uuids):
                    raise validation_error(
                        "One or more branch UUIDs are invalid or do not belong to the institution."
                    )

                branch_ids = list(valid_branches.values_list("id", flat=True))

                branch_items = BranchInventoryItem.objects.filter(
                    inventory_item=inventory_item,
                    branch_id__in=branch_ids,
                    deleted_at__isnull=True,
                ).prefetch_related(
                    Prefetch(
                        "stock_layers",
                        queryset=BranchInventoryItemStockLayer.objects.filter(
                            quantity_remaining__gt=0,
                            deleted_at__isnull=True,
                        ).select_for_update(),
                    )
                )

                if not branch_items.exists():
                    return Response(
                        {
                            "detail": "No active inventory entries found for the specified branches."
                        },
                        status=status.HTTP_404_NOT_FOUND,
                    )

                total_qty_transferred = Decimal("0")
                transfer_detail = []

                for branch_item in branch_items:
                    branch_qty = Decimal("0")

                    for layer in branch_item.stock_layers.all():
                        if layer.quantity_remaining <= 0:
                            continue

                        qty = Decimal(str(layer.quantity_remaining))
                        branch_qty += qty

                        institution_layer = (
                            InventoryItemStockLayer.objects.select_for_update()
                            .filter(
                                inventory_item=inventory_item,
                                unit_of_measure=layer.unit_of_measure,
                                unit_cost=layer.unit_cost,
                                deleted_at__isnull=True,
                            )
                            .first()
                        )

                        if institution_layer:
                            institution_layer.quantity_remaining += int(qty)
                            institution_layer.save(update_fields=["quantity_remaining"])
                        else:
                            InventoryItemStockLayer.objects.create(
                                inventory_item=inventory_item,
                                unit_of_measure=layer.unit_of_measure,
                                unit_cost=layer.unit_cost,
                                quantity_remaining=int(qty),
                                recieved_date=timezone.now(),
                            )

                        layer.quantity_remaining = 0
                        layer.deleted_at = timezone.now()
                        layer.save(update_fields=["quantity_remaining", "deleted_at"])

                    total_qty_transferred += branch_qty
                    transfer_detail.append(
                        {
                            "branch_name": branch_item.branch.branch_name,
                            "qty_returned": str(branch_qty),
                        }
                    )

                deleted_count = branch_items.update(
                    is_active=False,
                    deleted_at=timezone.now(),
                )

                return Response(
                    {
                        "detail": (
                            f"Removed inventory item {inventory_item_uuid} from "
                            f"{len(branch_base_uuids)} branch{'es' if len(branch_base_uuids) > 1 else ''}."
                        ),
                        "branches_affected": transfer_detail,
                        "quantities_transferred": {
                            "total_qty": str(total_qty_transferred),
                        },
                        "entries_deleted": deleted_count,
                    },
                    status=status.HTTP_200_OK,
                )

        except Exception as e:
            raise e


class InventoryItemPriceChangeListView(APIView):
    permission_classes = [HasInstitutionPermission]
    required_permissions = {
        "get": "can_view_inventory_items",
    }

    @extend_schema(
        responses={200: InventoryItemPriceChangeSerializer(many=True)},
        summary="List inventory item price change history",
        description="Retrieve price change history (buying or selling price) for a specific inventory item.",
        tags=["Item Management"],
        parameters=[
            OpenApiParameter(
                name="type",
                type=str,
                location=OpenApiParameter.QUERY,
                description="Filter by price change type (BUYING_PRICE or SELLING_PRICE)",
                required=False,
                enum=["BUYING_PRICE", "SELLING_PRICE"],
            ),
        ],
    )
    def get(self, request, inventory_item_id):
        institution = get_institution(request)

        price_type = request.query_params.get("type")

        inventory_item = get_object_or_404(
            InventoryItem,
            id=inventory_item_id,
            item_category__institution=institution,
            deleted_at__isnull=True,
        )

        price_changes = InventoryItemPriceChange.objects.filter(
            inventory_item=inventory_item,
            deleted_at__isnull=True,
        ).order_by("-created_at")

        if price_type:
            price_type = price_type.upper()
            valid_types = [
                choice[0]
                for choice in InventoryItemPriceChange.TYPE_OF_PRICE_CHANGE_CHOICES
            ]

            if price_type in valid_types:
                price_changes = price_changes.filter(type_of_price_change=price_type)

        paginator = CustomPageNumberPagination()
        paginated_qs = paginator.paginate_queryset(price_changes, request)

        serializer = InventoryItemPriceChangeSerializer(paginated_qs, many=True)

        return paginator.get_paginated_response(serializer.data)


class InventoryItemStockLayerListView(SearchOrderMixin, APIView):

    permission_classes = [HasInstitutionPermission]
    required_permissions = {
        "get": "can_view_inventory_item_stock_layer",
    }

    @extend_schema(
        responses={200: InventoryItemStockLayerSerializer(many=True)},
        summary="List inventory item stock layers",
        description="Retrieve stock layer details for a specific inventory item.",
        tags=["Stock Mgt"],
        parameters=[
            SEARCH_PARAM,
            ORDERING_PARAM,
            inventory_item_uuid_param(),
        ],
    )
    def get(self, request):

        inventory_item_uuid = request.query_params.get("inventory_item_uuid", None)

        institution = get_institution(request)

        if not inventory_item_uuid:
            raise validation_error("inventory_item_uuid query parameter is required.")

        inventory_item = get_object_or_404(
            InventoryItem,
            institution=institution,
            base_uuid=inventory_item_uuid,
            deleted_at__isnull=True,
        )

        stock_layers = InventoryItemStockLayer.objects.filter(
            inventory_item=inventory_item,
            deleted_at__isnull=True,
        )

        stock_layers = self.apply_search(stock_layers)
        stock_layers = self.apply_ordering(stock_layers)

        paginator = CustomPageNumberPagination()
        paginated_qs = paginator.paginate_queryset(stock_layers, request)

        serializer = InventoryItemStockLayerSerializer(paginated_qs, many=True)

        return paginator.get_paginated_response(serializer.data)

    # Never Implement a POST method for stock layers as they are created via other processes


class InventoryItemStockLayerDetailView(APIView):

    permission_classes = [HasInstitutionPermission]
    required_permissions = {
        "get": "can_view_inventory_item_stock_layer",
    }

    @extend_schema(
        responses={200: InventoryItemStockLayerSerializer},
        summary="Get inventory item stock layer details",
        description="Retrieve details of a specific stock layer by its UUID.",
        tags=["Stock Mgt"],
    )
    def get(self, request, base_uuid):

        stock_layer = get_object_or_404(
            InventoryItemStockLayer,
            base_uuid=base_uuid,
            deleted_at__isnull=True,
        )

        serializer = InventoryItemStockLayerSerializer(stock_layer)

        return Response(serializer.data, status=status.HTTP_200_OK)


class BranchInventoryItemStockLayerListView(SearchOrderMixin, APIView):

    permission_classes = [HasInstitutionPermission]
    required_permissions = {
        "get": "can_view_branch_inventory_item_stock_layer",
    }

    @extend_schema(
        responses={200: BranchInventoryItemStockLayerSerializer(many=True)},
        summary="List branch inventory item stock layers",
        description="Retrieve stock layer details for a specific branch inventory item.",
        tags=["Stock Mgt"],
        parameters=[
            SEARCH_PARAM,
            ORDERING_PARAM,
            branch_inventory_item_uuid_param(),
        ],
    )
    def get(self, request):

        branch_inventory_item_uuid = request.query_params.get(
            "branch_inventory_item_uuid", None
        )

        institution = get_institution(request)

        if not branch_inventory_item_uuid:
            raise validation_error(
                "branch_inventory_item_uuid query parameter is required."
            )

        branch_inventory_item = get_object_or_404(
            BranchInventoryItem,
            branch__institution=institution,
            base_uuid=branch_inventory_item_uuid,
            deleted_at__isnull=True,
        )

        branch_stock_layers = BranchInventoryItemStockLayer.objects.filter(
            branch_inventory_item=branch_inventory_item,
            deleted_at__isnull=True,
        )

        branch_stock_layers = self.apply_search(branch_stock_layers)
        branch_stock_layers = self.apply_ordering(branch_stock_layers)

        paginator = CustomPageNumberPagination()
        paginated_qs = paginator.paginate_queryset(branch_stock_layers, request)

        serializer = BranchInventoryItemStockLayerSerializer(paginated_qs, many=True)

        return paginator.get_paginated_response(serializer.data)

    # Never Implement a POST method for stock layers as they are created via other processes


class BranchInventoryItemStockLayerDetailView(APIView):

    permission_classes = [HasInstitutionPermission]
    required_permissions = {
        "get": "can_view_branch_inventory_item_stock_layer",
    }

    @extend_schema(
        responses={200: BranchInventoryItemStockLayerSerializer},
        summary="Get inventory item stock layer details",
        description="Retrieve details of a specific stock layer by its UUID.",
        tags=["Stock Mgt"],
    )
    def get(self, request, base_uuid):

        branch_stock_layer = get_object_or_404(
            BranchInventoryItemStockLayer,
            base_uuid=base_uuid,
            deleted_at__isnull=True,
        )

        serializer = BranchInventoryItemStockLayerSerializer(branch_stock_layer)

        return Response(serializer.data, status=status.HTTP_200_OK)


class BranchInventoryItemPriceChangeListView(SearchOrderMixin, APIView):
    """
    List price changes for a specific branch inventory item.
    """

    permission_classes = [HasInstitutionPermission]
    required_permissions = {
        "get": "can_view_branch_inventory_item_price_change",
    }

    @extend_schema(
        responses={200: BranchInventoryItemPriceChangeSerializer(many=True)},
        summary="List branch inventory item price changes",
        description="Retrieve price change history for a specific branch inventory item.",
        tags=["Stock Price Change Mgt"],
        parameters=[
            SEARCH_PARAM,
            ORDERING_PARAM,
            branch_inventory_item_uuid_param(),
        ],
    )
    def get(self, request):
        branch_inventory_item_uuid = request.query_params.get(
            "branch_inventory_item_uuid", None
        )
        institution = get_institution(request)

        if not branch_inventory_item_uuid:
            raise validation_error(
                "branch_inventory_item_uuid query parameter is required."
            )

        try:
            branch_inventory_item = BranchInventoryItem.objects.get(
                branch__institution=institution,
                base_uuid=branch_inventory_item_uuid,
                deleted_at__isnull=True,
            )
        except BranchInventoryItem.DoesNotExist:
            raise SystemNotFoundError(
                detail=f"No BranchInventoryItem matches UUID '{branch_inventory_item_uuid}' for your institution."
            )

        price_changes = BranchInventoryItemPriceChange.objects.filter(
            branch_inventory_item=branch_inventory_item,
            deleted_at__isnull=True,
        )

        price_changes = self.apply_search(price_changes)
        price_changes = self.apply_ordering(price_changes)

        paginator = CustomPageNumberPagination()
        paginated_qs = paginator.paginate_queryset(price_changes, request)

        serializer = BranchInventoryItemPriceChangeSerializer(paginated_qs, many=True)
        return paginator.get_paginated_response(serializer.data)


class BranchInventoryItemPriceChangeDetailView(APIView):
    """
    Retrieve a single branch inventory item price change by UUID.
    """

    permission_classes = [HasInstitutionPermission]
    required_permissions = {
        "get": "can_view_branch_inventory_item_price_change",
    }

    @extend_schema(
        responses={200: BranchInventoryItemPriceChangeSerializer},
        summary="Get branch inventory item price change details",
        description="Retrieve details of a specific price change by its UUID.",
        tags=["Stock Price Change Mgt"],
    )
    def get(self, request, base_uuid):
        try:
            price_change = BranchInventoryItemPriceChange.objects.get(
                base_uuid=base_uuid,
                deleted_at__isnull=True,
            )
        except BranchInventoryItemPriceChange.DoesNotExist:
            raise SystemNotFoundError(
                detail=f"No BranchInventoryItemPriceChange matches UUID '{base_uuid}'."
            )

        serializer = BranchInventoryItemPriceChangeSerializer(price_change)
        return Response(serializer.data, status=status.HTTP_200_OK)


class ItemUnitOfMeasureDefaultDataAPIView(APIView):

    @extend_schema(
        responses={200: dict},
        description="Retrieve default units of measurement not yet saved for the institution.",
        summary="Get unsaved unit defaults",
        tags=["Item Management"],
    )
    def get(self, request):
        institution = get_institution(request)

        existing_unit_names = {
            name.lower().strip()
            for name in ItemUnitOfMeasure.objects.filter(
                institution=institution, is_active=True
            ).values_list("unit_name", flat=True)
        }

        grouped_defaults = load_and_group_defaults()
        default_units = grouped_defaults.get("units", [])

        unsaved_units = [
            unit
            for unit in default_units
            if unit["unit_name"].lower().strip() not in existing_unit_names
        ]

        return Response({"units": unsaved_units}, status=status.HTTP_200_OK)


class BranchInventoryItemUnitOfMeasureListCreateView(BaseItemView, SearchOrderMixin):
    permission_classes = [HasInstitutionPermission]
    required_permissions = {
        "get": "can_view_branch_inventory_item_unit_of_measures",
        "post": "can_create_branch_inventory_item_unit_of_measures",
    }

    @extend_schema(
        responses={200: BranchInventoryItemUnitOfMeasureSerializer(many=True)},
        description="Retrieve a list of branch inventory item units of measure.",
        summary="List branch inventory item units of measure",
        tags=["BranchInventoryItemUnitOfMeasure Management"],
        parameters=[
            SEARCH_PARAM,
            ORDERING_PARAM,
            branch_inventory_item_uuid_param(required=False),
        ],
    )
    def get(self, request):
        institution = self.get_institution(request)
        branch_inventory_item_uuid = request.query_params.get(
            "branch_inventory_item_uuid", None
        )

        if not institution:
            raise SystemNotFoundError(
                detail="User does not belong to an institution.",
                status_code=status.HTTP_403_FORBIDDEN,
            )

        queryset = BranchInventoryItemUnitOfMeasure.objects.filter(
            branch_inventory_item__branch__institution=institution,
            deleted_at__isnull=True,
        )

        if branch_inventory_item_uuid:
            queryset = queryset.filter(
                branch_inventory_item__base_uuid=branch_inventory_item_uuid
            )

        queryset = self.apply_search(queryset)
        queryset = self.apply_ordering(queryset)

        paginator = CustomPageNumberPagination()
        page = paginator.paginate_queryset(queryset, request)

        serializer = BranchInventoryItemUnitOfMeasureSerializer(page, many=True)
        return paginator.get_paginated_response(serializer.data)

    @extend_schema(
        request=BranchInventoryItemUnitOfMeasureSerializer,
        responses={201: BranchInventoryItemUnitOfMeasureSerializer},
        description="Create a branch inventory item unit of measure.",
        summary="Create branch inventory item unit of measure",
        tags=["BranchInventoryItemUnitOfMeasure Management"],
    )
    def post(self, request):
        institution = self.get_institution(request)
        if not institution:
            raise SystemNotFoundError(
                detail="User does not belong to an institution.",
                status_code=status.HTTP_403_FORBIDDEN,
            )

        serializer = BranchInventoryItemUnitOfMeasureSerializer(
            data=request.data,
            context={"request": request},
        )
        serializer.is_valid(raise_exception=True)

        instance = serializer.save()

        output_serializer = BranchInventoryItemUnitOfMeasureSerializer(instance)
        return Response(output_serializer.data, status=status.HTTP_201_CREATED)


class BranchInventoryItemUnitOfMeasureDetailView(APIView):
    permission_classes = [HasInstitutionPermission]
    required_permissions = {
        "get": "can_view_branch_inventory_item_unit_of_measures",
        "patch": "can_edit_branch_inventory_item_unit_of_measures",
        "delete": "can_delete_branch_inventory_item_unit_of_measures",
    }

    def get_object(self, base_uuid, request):
        institution = get_institution(request)
        try:
            return BranchInventoryItemUnitOfMeasure.objects.select_related(
                "branch_inventory_item", "unit_of_measure"
            ).get(
                base_uuid=base_uuid,
                branch_inventory_item__branch__institution=institution,
                deleted_at__isnull=True,
            )
        except BranchInventoryItemUnitOfMeasure.DoesNotExist:
            raise SystemNotFoundError(
                detail=f"Unit of measure with UUID {base_uuid} not found",
                status_code=status.HTTP_404_NOT_FOUND,
            )

    @extend_schema(
        responses={200: BranchInventoryItemUnitOfMeasureSerializer},
        description="Retrieve details of a specific branch inventory item unit of measure.",
        summary="Get branch inventory item unit of measure details",
        tags=["BranchInventoryItemUnitOfMeasure Management"],
    )
    def get(self, request, base_uuid):
        unit = self.get_object(base_uuid, request)
        serializer = BranchInventoryItemUnitOfMeasureSerializer(
            unit, context={"request": request}
        )
        return Response(serializer.data)

    @extend_schema(
        request=BranchInventoryItemUnitOfMeasureSerializer,
        responses={200: BranchInventoryItemUnitOfMeasureSerializer},
        description="Partially update a branch inventory item unit of measure.",
        summary="Partially update branch inventory item unit of measure",
        tags=["BranchInventoryItemUnitOfMeasure Management"],
    )
    def patch(self, request, base_uuid):
        unit = self.get_object(base_uuid, request)
        old_data = BranchInventoryItemUnitOfMeasureSerializer(
            unit, context={"request": request}
        ).data

        serializer = BranchInventoryItemUnitOfMeasureSerializer(
            unit,
            data=request.data,
            partial=True,
            context={"request": request},
        )
        if serializer.is_valid():
            updated_unit = serializer.save()
            new_data = BranchInventoryItemUnitOfMeasureSerializer(
                updated_unit, context={"request": request}
            ).data

            changes = {
                key: {"old": old_data.get(key), "new": new_data.get(key)}
                for key in request.data.keys()
                if old_data.get(key) != new_data.get(key)
            }

            AuditLog.objects.create(
                content_type=ContentType.objects.get_for_model(
                    BranchInventoryItemUnitOfMeasure
                ),
                object_id=updated_unit.id,
                action="UPDATE",
                user=request.user if request.user.is_authenticated else None,
                changes=serialize_value(changes),
                description=(
                    f"Updated unit of measure ({updated_unit.base_uuid}) "
                    "for branch inventory item"
                ),
            )

            return Response(serializer.data)

        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

    @extend_schema(
        responses={204: None},
        description="Delete a branch inventory item unit of measure.",
        summary="Delete branch inventory item unit of measure",
        tags=["BranchInventoryItemUnitOfMeasure Management"],
    )
    def delete(self, request, base_uuid):
        unit = self.get_object(base_uuid, request)

        if unit.is_base_unit_of_measure:
            validation_error("Base unit of measure cannot be deleted.")

        with transaction.atomic():
            unit_data = BranchInventoryItemUnitOfMeasureSerializer(
                unit, context={"request": request}
            ).data
            unit_id = unit.id
            unit.delete()

            AuditLog.objects.create(
                content_type=ContentType.objects.get_for_model(
                    BranchInventoryItemUnitOfMeasure
                ),
                object_id=unit_id,
                action="DELETE",
                user=request.user if request.user.is_authenticated else None,
                changes=serialize_value(unit_data),
                description=(
                    f"Deleted branch inventory item unit of measure ({base_uuid})"
                ),
            )

        return Response(status=status.HTTP_204_NO_CONTENT)


class InventoryItemUnitOfMeasureListCreateView(BaseItemView, SearchOrderMixin):
    permission_classes = [HasInstitutionPermission]
    required_permissions = {
        "get": "can_view_inventory_item_unit_of_measures",
        "post": "can_create_inventory_item_unit_of_measures",
    }

    @extend_schema(
        responses={200: InventoryItemUnitOfMeasureSerializer(many=True)},
        description="Retrieve a list of inventory item units of measure.",
        summary="List inventory item units of measure",
        tags=["InventoryItemUnitOfMeasure Management"],
        parameters=[
            SEARCH_PARAM,
            ORDERING_PARAM,
            inventory_item_uuid_param(required=False),
        ],
    )
    def get(self, request):
        institution = self.get_institution(request)
        inventory_item_uuid = request.query_params.get("inventory_item_uuid", None)

        if not institution:
            raise SystemNotFoundError(
                detail="User does not belong to an institution.",
                status_code=status.HTTP_403_FORBIDDEN,
            )

        queryset = InventoryItemUnitOfMeasure.objects.undeleted().filter(
            inventory_item__institution=institution,
        )

        if inventory_item_uuid:
            queryset = queryset.filter(inventory_item__base_uuid=inventory_item_uuid)

        queryset = self.apply_search(queryset)
        queryset = self.apply_ordering(queryset)

        paginator = CustomPageNumberPagination()
        page = paginator.paginate_queryset(queryset, request)

        serializer = InventoryItemUnitOfMeasureSerializer(
            page, many=True, context={"request": request}
        )
        return paginator.get_paginated_response(serializer.data)

    @extend_schema(
        request=InventoryItemUnitOfMeasureSerializer,
        responses={201: InventoryItemUnitOfMeasureSerializer},
        description="Create an inventory item unit of measure.",
        summary="Create inventory item unit of measure",
        tags=["InventoryItemUnitOfMeasure Management"],
    )
    def post(self, request):
        institution = self.get_institution(request)
        if not institution:
            raise SystemNotFoundError(
                detail="User does not belong to an institution.",
                status_code=status.HTTP_403_FORBIDDEN,
            )

        serializer = InventoryItemUnitOfMeasureSerializer(
            data=request.data,
            context={"request": request},
        )
        serializer.is_valid(raise_exception=True)

        instance = serializer.save()

        output_serializer = InventoryItemUnitOfMeasureSerializer(
            instance, context={"request": request}
        )
        return Response(output_serializer.data, status=status.HTTP_201_CREATED)


class InventoryItemUnitOfMeasureDetailView(APIView):
    permission_classes = [HasInstitutionPermission]
    required_permissions = {
        "get": "can_view_inventory_item_unit_of_measures",
        "patch": "can_edit_inventory_item_unit_of_measures",
        "delete": "can_delete_inventory_item_unit_of_measures",
    }

    def _get_object(self, base_uuid, request):
        institution = get_institution(request)
        try:
            return (
                InventoryItemUnitOfMeasure.objects.select_related(
                    "inventory_item", "unit_of_measure"
                )
                .undeleted()
                .get(
                    base_uuid=base_uuid,
                    inventory_item__institution=institution,
                )
            )
        except InventoryItemUnitOfMeasure.DoesNotExist:
            raise SystemNotFoundError(
                detail=f"Unit of measure with UUID {base_uuid} not found",
                status_code=status.HTTP_404_NOT_FOUND,
            )

    @extend_schema(
        responses={200: InventoryItemUnitOfMeasureSerializer},
        description="Retrieve details of a specific inventory item unit of measure.",
        summary="Get inventory item unit of measure details",
        tags=["InventoryItemUnitOfMeasure Management"],
    )
    def get(self, request, base_uuid):
        unit = self._get_object(base_uuid, request)
        serializer = InventoryItemUnitOfMeasureSerializer(
            unit, context={"request": request}
        )
        return Response(serializer.data)

    @extend_schema(
        request=InventoryItemUnitOfMeasureSerializer,
        responses={200: InventoryItemUnitOfMeasureSerializer},
        description="Partially update an inventory item unit of measure.",
        summary="Partially update inventory item unit of measure",
        tags=["InventoryItemUnitOfMeasure Management"],
    )
    def patch(self, request, base_uuid):
        unit = self._get_object(base_uuid, request)
        old_data = InventoryItemUnitOfMeasureSerializer(
            unit, context={"request": request}
        ).data

        serializer = InventoryItemUnitOfMeasureSerializer(
            unit, data=request.data, partial=True, context={"request": request}
        )
        if serializer.is_valid():
            updated_unit = serializer.save()
            new_data = InventoryItemUnitOfMeasureSerializer(
                updated_unit, context={"request": request}
            ).data

            changes = {
                key: {"old": old_data.get(key), "new": new_data.get(key)}
                for key in request.data.keys()
                if old_data.get(key) != new_data.get(key)
            }

            AuditLog.objects.create(
                content_type=ContentType.objects.get_for_model(
                    InventoryItemUnitOfMeasure
                ),
                object_id=updated_unit.id,
                action="UPDATE",
                user=request.user if request.user.is_authenticated else None,
                changes=serialize_value(changes),
                description=(
                    f"Updated unit of measure ({updated_unit.base_uuid}) "
                    "for inventory item"
                ),
            )

            return Response(serializer.data)

        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

    @extend_schema(
        responses={204: None},
        description="Delete an inventory item unit of measure.",
        summary="Delete inventory item unit of measure",
        tags=["InventoryItemUnitOfMeasure Management"],
    )
    def delete(self, request, base_uuid):
        unit = self._get_object(base_uuid, request)

        if unit.is_base_unit_of_measure:
            validation_error("Base unit of measure cannot be deleted.")

        with transaction.atomic():
            unit_data = InventoryItemUnitOfMeasureSerializer(
                unit, context={"request": request}
            ).data
            unit_id = unit.id
            unit.delete()

            AuditLog.objects.create(
                content_type=ContentType.objects.get_for_model(
                    InventoryItemUnitOfMeasure
                ),
                object_id=unit_id,
                action="DELETE",
                user=request.user if request.user.is_authenticated else None,
                changes=serialize_value(unit_data),
                description=(f"Deleted inventory item unit of measure ({base_uuid})"),
            )

        return Response(status=status.HTTP_204_NO_CONTENT)


class BranchToBranchStockMovementListView(BaseItemView, SearchOrderMixin):
    permission_classes = [HasInstitutionPermission]
    required_permissions = {
        "get": "can_view_branch_stock_movements",
        "post": "can_create_branch_stock_movements",
    }

    @extend_schema(
        responses={200: BranchToBranchStockMovementSerializer(many=True)},
        description="Retrieve a list of branch to branch stock movements.",
        summary="List branch to branch stock movements",
        tags=["Stock Movements"],
        parameters=[SEARCH_PARAM, ORDERING_PARAM],
    )
    def get(self, request):
        institution = self.get_institution(request)
        if not institution:
            raise SystemNotFoundError(
                detail="User does not belong to an institution.",
                status_code=status.HTTP_403_FORBIDDEN,
            )

        movements = BranchToBranchStockMovement.objects.filter(
            branch_from__institution=institution,
            deleted_at__isnull=True,
        )

        movements = self.apply_search(movements)
        movements = self.apply_ordering(movements)

        paginator = CustomPageNumberPagination()
        paginator_qs = paginator.paginate_queryset(movements, request)
        serializer = BranchToBranchStockMovementSerializer(paginator_qs, many=True)
        return paginator.get_paginated_response(serializer.data)

    @extend_schema(
        request=BranchToBranchStockMovementSerializer,
        responses={201: BranchToBranchStockMovementSerializer},
        description="Create a branch to branch stock movement.",
        summary="Create branch to branch stock movement",
        tags=["Stock Movements"],
    )
    def post(self, request):
        institution = self.get_institution(request)
        if not institution:
            raise SystemNotFoundError(
                detail="User does not belong to an institution.",
                status_code=status.HTTP_403_FORBIDDEN,
            )

        serializer = BranchToBranchStockMovementSerializer(
            data=request.data, context={"request": request}
        )
        serializer.is_valid(raise_exception=True)
        movement = serializer.save()
        movement.confirm_create(
            profile_institution=request.profile_institution,
            external_identity=request.external_identity,
        )

        return Response(
            BranchToBranchStockMovementSerializer(movement).data,
            status=status.HTTP_201_CREATED,
        )


class BranchToBranchStockMovementDetailView(APIView):
    permission_classes = [HasInstitutionPermission]
    required_permissions = {
        "get": "can_view_branch_stock_movements",
        "patch": "can_edit_branch_stock_movements",
        "delete": "can_delete_branch_stock_movements",
    }

    def get_object(self, base_uuid, request):
        institution = get_institution(request)
        try:
            return BranchToBranchStockMovement.objects.get(
                base_uuid=base_uuid,
                branch_to__institution=institution,
                deleted_at__isnull=True,
            )
        except BranchToBranchStockMovement.DoesNotExist:
            raise SystemNotFoundError(
                detail=f"Branch to Branch Stock Movement with UUID {base_uuid} not found",
                status_code=status.HTTP_404_NOT_FOUND,
            )

    @extend_schema(
        responses={200: BranchToBranchStockMovementSerializer},
        description="Retrieve a specific branch to branch stock movement.",
        summary="Get branch to branch stock movement",
        tags=["Stock Movements"],
    )
    def get(self, request, base_uuid):

        movement = self.get_object(base_uuid, request)
        if not movement:
            return SystemNotFoundError(status_code=status.HTTP_404_NOT_FOUND)

        serializer = BranchToBranchStockMovementSerializer(movement)
        return Response(serializer.data)

    @extend_schema(
        request=BranchToBranchStockMovementSerializer,
        responses={200: BranchToBranchStockMovementSerializer},
        description="Update a branch to branch stock movement.",
        summary="Update branch to branch stock movement",
        tags=["Stock Movements"],
    )
    def patch(self, request, base_uuid):
        movement = self.get_object(base_uuid, request)
        if not movement:
            return SystemNotFoundError(status_code=status.HTTP_404_NOT_FOUND)

        old_data = BranchToBranchStockMovementSerializer(movement).data
        movement.approval_status = "under_update"
        movement.save(update_fields=["approval_status"])

        serializer = BranchToBranchStockMovementSerializer(
            movement, data=request.data, partial=True, context={"request": request}
        )
        serializer.is_valid(raise_exception=True)
        updated = serializer.save()

        new_data = BranchToBranchStockMovementSerializer(updated).data
        changes = {
            key: {"old": old_data.get(key), "new": new_data.get(key)}
            for key in request.data.keys()
            if old_data.get(key) != new_data.get(key)
        }

        AuditLog.objects.create(
            content_type=ContentType.objects.get_for_model(BranchToBranchStockMovement),
            object_id=updated.id,
            action="UPDATE",
            user=request.user,
            changes=serialize_value(changes),
            description=f"Updated branch stock movement {updated.stock_movement_code}",
        )

        updated.confirm_update(
            profile_institution=request.profile_institution,
            external_identity=request.external_identity,
        )
        return Response(serializer.data)

    @extend_schema(
        responses={204: None},
        description="Delete a branch to branch stock movement.",
        summary="Delete branch to branch stock movement",
        tags=["Stock Movements"],
    )
    def delete(self, request, base_uuid):
        movement = self.get_object(base_uuid, request)
        if not movement:
            return SystemNotFoundError(status_code=status.HTTP_404_NOT_FOUND)

        movement_data = BranchToBranchStockMovementSerializer(
            movement, context={"request": request}
        ).data
        movement_id = movement.id

        AuditLog.objects.create(
            content_type=ContentType.objects.get_for_model(BranchToBranchStockMovement),
            object_id=movement_id,
            action="DELETE",
            user=request.user if request.user.is_authenticated else None,
            changes=serialize_value(movement_data),
            description=f"Deleted branch stock movement {movement.stock_movement_code}",
        )

        movement.confirm_delete(
            profile_institution=request.profile_institution,
            external_identity=request.external_identity,
        )
        return Response(status=status.HTTP_204_NO_CONTENT)


class WriteOffListCreateView(APIView, SearchOrderMixin):
    permission_classes = [HasInstitutionPermission]
    required_permissions = {
        "get": "can_view_write_offs",
        "post": "can_create_write_offs",
    }

    @extend_schema(
        responses={200: WriteOffSerializer(many=True)},
        description="Retrieve a list of all write-offs.",
        summary="List all write-offs",
        tags=["Write Offs Management"],
        parameters=[SEARCH_PARAM, ORDERING_PARAM],
    )
    def get(self, request):
        institution = get_institution(request)

        write_offs = WriteOff.objects.filter(
            Q(institution=institution) | Q(branch__institution=institution),
            deleted_at__isnull=True,
        ).select_related(
            "institution",
            "branch",
            "expense_account",
            "created_by",
            "updated_by",
        )

        write_offs = self.apply_search(write_offs)
        write_offs = self.apply_ordering(write_offs)

        paginator = CustomPageNumberPagination()
        paginator_qs = paginator.paginate_queryset(write_offs, request)
        serializer = WriteOffSerializer(paginator_qs, many=True)
        return paginator.get_paginated_response(serializer.data)

    @extend_schema(
        request=WriteOffSerializer,
        responses={201: WriteOffSerializer},
        description="Create a new write-off.",
        summary="Create a new write-off",
        tags=["Write Offs Management"],
    )
    def post(self, request):
        user_institution = getattr(request.user, "institution", None)
        user_branch = (
            getattr(user_institution, "branch", None) if user_institution else None
        )

        serializer = WriteOffSerializer(
            data=request.data,
            context={"request": request},
        )

        if serializer.is_valid():

            write_off = serializer.save(
                institution=user_institution, branch=user_branch
            )

            AuditLog.objects.create(
                content_type=ContentType.objects.get_for_model(WriteOff),
                object_id=write_off.pk,
                action="CREATE",
                user=request.user if request.user.is_authenticated else None,
                description=f"Created write-off {write_off.reference_code}",
            )

            write_off.confirm_create(
                profile_institution=request.profile_institution,
                external_identity=request.external_identity,
            )

            return Response(serializer.data, status=status.HTTP_201_CREATED)

        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)


class WriteOffDetailView(APIView):
    permission_classes = [HasInstitutionPermission]
    required_permissions = {
        "get": "can_view_write_offs",
        "patch": "can_create_write_offs",
        "delete": "can_delete_write_offs",
    }

    def get_object(self, base_uuid):
        try:
            return WriteOff.objects.select_related(
                "institution",
                "branch",
                "expense_account",
                "created_by",
                "updated_by",
            ).get(base_uuid=base_uuid, deleted_at__isnull=True)
        except WriteOff.DoesNotExist:
            raise SystemNotFoundError(
                detail=f"Write Off with UUID '{base_uuid}' not found."
            )

    @extend_schema(
        responses={200: WriteOffSerializer},
        description="Retrieve details of a specific Write Off.",
        summary="Get Write Off details",
        tags=["Write Offs Management"],
    )
    def get(self, request, base_uuid):
        write_off = self.get_object(base_uuid)
        serializer = WriteOffSerializer(write_off)
        return Response(serializer.data)

    @extend_schema(
        request=WriteOffSerializer,
        responses={200: WriteOffSerializer},
        description="Partially update a specific Write Off.",
        summary="Partially update Write Off details",
        tags=["Write Offs Management"],
    )
    @transaction.atomic
    def patch(self, request, base_uuid):
        write_off = self.get_object(base_uuid)

        write_off.approval_status = "under_update"
        old_data = WriteOffSerializer(write_off).data

        serializer = WriteOffSerializer(
            write_off, data=request.data, partial=True, context={"request": request}
        )

        if serializer.is_valid():
            updated_write_off = serializer.save()
            new_data = WriteOffSerializer(updated_write_off).data

            changes = {
                key: {"old": old_data.get(key), "new": new_data.get(key)}
                for key in request.data.keys()
                if old_data.get(key) != new_data.get(key)
            }
            cleaned_changes = serialize_value(changes)

            AuditLog.objects.create(
                content_type=ContentType.objects.get_for_model(WriteOff),
                object_id=updated_write_off.id,
                action="UPDATE",
                user=request.user if request.user.is_authenticated else None,
                changes=cleaned_changes,
                description=f"Updated Write Off {updated_write_off.reference_code} ({updated_write_off.base_uuid})",
            )

            updated_write_off.confirm_update(
                profile_institution=request.profile_institution,
                external_identity=request.external_identity,
            )
            return Response(serializer.data)

        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

    @extend_schema(
        responses={204: None},
        description="Delete a specific Write Off.",
        summary="Delete a Write Off",
        tags=["Write Offs Management"],
    )
    @transaction.atomic
    def delete(self, request, base_uuid):
        write_off = self.get_object(base_uuid)

        write_off_data = WriteOffSerializer(write_off).data
        write_off.confirm_delete(
            profile_institution=request.profile_institution,
            external_identity=request.external_identity,
        )

        AuditLog.objects.create(
            content_type=ContentType.objects.get_for_model(WriteOff),
            object_id=write_off.id,
            action="DELETE",
            user=request.user if request.user.is_authenticated else None,
            changes=write_off_data,
            description=f"Deleted Write Off {write_off.reference_code} ({write_off.base_uuid})",
        )

        return Response(status=status.HTTP_204_NO_CONTENT)


class WriteOffLineItemsView(APIView):
    permission_classes = [HasInstitutionPermission]
    required_permissions = {"get": "can_view_write_offs"}

    @extend_schema(
        description=(
            "Retrieve paginated write-off line items. item_type identifies "
            "institution or branch items and their corresponding serializer."
        ),
        summary="Get Write Off line items",
        tags=["Write Offs Management"],
    )
    def get(self, request, base_uuid):
        institution = get_institution(request)
        write_off = get_or_raise(
            queryset=WriteOff.objects.undeleted().filter(
                Q(institution=institution) | Q(branch__institution=institution)
            ),
            message=f"Write Off with UUID '{base_uuid}' not found.",
            base_uuid=base_uuid,
        )
        if write_off.branch_id:
            item_type = "branch"
            line_items = write_off.branch_wo_line_items.filter(
                deleted_at__isnull=True
            ).select_related(
                "branch_inventory_item__inventory_item",
                "branch_item_unit_of_measure__unit_of_measure",
            )
            serializer_class = BranchWriteOffLineItemSerializer
        else:
            item_type = "institution"
            line_items = write_off.institution_wo_line_items.filter(
                deleted_at__isnull=True
            ).select_related(
                "inventory_item",
                "inventory_item_unit_of_measure__unit_of_measure",
            )
            serializer_class = InstitutionWriteOffLineItemSerializer

        paginator = CustomPageNumberPagination()
        page = paginator.paginate_queryset(line_items.order_by("pk"), request)
        serializer = serializer_class(page, many=True, context={"request": request})
        response = paginator.get_paginated_response(serializer.data)
        response.data["item_type"] = item_type
        return response


class StockMovementLogView(APIView):

    @extend_schema(
        tags=["Institution Stock Log (INs and OUTs)"],
        summary="List institution stock movements",
        description=(
            "Retrieve paginated stock movement logs for the current institution. "
            "Results include institution-level and branch-level stock movements, "
            "ordered by the most recent movement date first."
        ),
        responses={200: StockMovementLogSerializer(many=True)},
        parameters=[
            inventory_item_uuid_param(required=False),
            branch_base_uuid_param_base(required=False),
            OpenApiParameter(
                name="stock_level",
                type=OpenApiTypes.STR,
                location=OpenApiParameter.QUERY,
                required=False,
                description="Filter by the level at which the stock movement occurred.",
                enum=["institution", "branch"],
            ),
            OpenApiParameter(
                name="movement_type",
                type=OpenApiTypes.STR,
                location=OpenApiParameter.QUERY,
                required=False,
                description="Filter by stock movement type.",
                enum=[
                    "BILL_RECEIPT",
                    "GRN_RECEIPT",
                    "ALLOCATION_IN",
                    "BRANCH_TRANSFER_IN",
                    "RETURN_RESTOCK",
                    "OPENING_STOCK",
                    "INVOICE_SALE",
                    "GIN_ISSUE",
                    "ALLOCATION_OUT",
                    "BRANCH_TRANSFER_OUT",
                    "WRITE_OFF",
                    "RETURN_CONSUMED",
                    "UNIT_BREAKDOWN",
                    "MANUFACTURING_CONSUMPTION",
                ],
            ),
            OpenApiParameter(
                name="date_filter",
                type=str,
                description="Preset date filter (e.g., today, this_month, last_month).",
                required=False,
            ),
        ],
    )
    def get(self, request):
        institution = get_institution(request)

        start_date, end_date = get_date_range_from_filter(
            filter_key=request.query_params.get("date_filter", "all"),
            institution=institution,
        )

        qs = (
            StockMovementLog.objects.undeleted()
            .filter(institution=institution)
            .select_related(
                "inventory_item", "unit_of_measure", "branch", "institution"
            )
        )

        if item_uuid := request.query_params.get("inventory_item_uuid"):
            qs = qs.filter(inventory_item__base_uuid=item_uuid)
        if branch_uuid := request.query_params.get("branch_base_uuid"):
            qs = qs.filter(branch__base_uuid=branch_uuid)
        if stock_level := request.query_params.get("stock_level"):
            qs = qs.filter(stock_level=stock_level)
        if movement_type := request.query_params.get("movement_type"):
            qs = qs.filter(movement_type=movement_type)

        start_datetime, end_datetime = get_stock_movement_datetime_bounds(
            start_date,
            end_date,
        )
        if start_datetime:
            qs = qs.filter(movement_date__gte=start_datetime)
        if end_datetime:
            qs = qs.filter(movement_date__lt=end_datetime)

        paginator = CustomPageNumberPagination()
        paginated_qs = paginator.paginate_queryset(qs, request)
        serializer = StockMovementLogSerializer(paginated_qs, many=True)
        return paginator.get_paginated_response(serializer.data)


class InventorySummaryView(APIView):
    def get(self, request):
        institution = get_institution(request)

        search = request.query_params.get("search", "").strip()

        branch_uuids = [
            value.strip()
            for value in request.query_params.get("branch_uuids", "").split(",")
            if value.strip()
        ]

        branch_items = (
            BranchInventoryItem.objects.undeleted()
            .select_related("branch")
            .prefetch_related(
                Prefetch(
                    "units",
                    queryset=BranchInventoryItemUnitOfMeasure.objects.undeleted().select_related(
                        "unit_of_measure"
                    ),
                    to_attr="summary_units",
                ),
                Prefetch(
                    "stock_layers",
                    queryset=BranchInventoryItemStockLayer.objects.undeleted().select_related(
                        "unit_of_measure"
                    ),
                    to_attr="summary_stock_layers",
                ),
            )
        )

        if branch_uuids:
            branch_items = branch_items.filter(branch__base_uuid__in=branch_uuids)

        items = (
            InventoryItem.objects.undeleted()
            .filter(
                institution=institution,
                item_type="GOODS",
            )
            .search(search)
            .select_related("item_category")
            .prefetch_related(
                Prefetch(
                    "units",
                    queryset=InventoryItemUnitOfMeasure.objects.undeleted().select_related(
                        "unit_of_measure"
                    ),
                    to_attr="summary_units",
                ),
                Prefetch(
                    "stock_layers",
                    queryset=InventoryItemStockLayer.objects.undeleted().select_related(
                        "unit_of_measure"
                    ),
                    to_attr="summary_stock_layers",
                ),
                Prefetch(
                    "branch_specific_inventory",
                    queryset=branch_items,
                    to_attr="summary_branch_items",
                ),
            )
        )

        paginator = CustomPageNumberPagination()
        page = paginator.paginate_queryset(items, request)
        products = get_inventory_summary(page)
        serializer = InventorySummarySerializer(products)

        return paginator.get_paginated_response(serializer.data)


from .utils import (
    build_stock_movement_queryset,
    generate_stock_movement_file,
    get_stock_movement_datetime_bounds,
    sync_uoms_to_branch_item,
)
from utilities.helpers import get_date_range_from_filter
from reports.exporting import resolve_export_recipient


class StockMovementLogDownloadAPIView(APIView):
    permission_classes = [HasInstitutionPermission]
    required_permissions = {
        "post": "can_view_stock_movement_logs",
    }

    @extend_schema(
        request=StockMovementDownloadSerializer,
        responses={200: StockMovementDownloadSerializer},
        description="Download Stock Movement Log for all products or a specific product as Excel or PDF",
        summary="Download stock movement report",
        tags=["Stock Movement Reports"],
    )
    def post(self, request):
        serializer = StockMovementDownloadSerializer(
            data=request.data,
            context={"request": request},
        )
        serializer.is_valid(raise_exception=True)

        data = serializer.validated_data

        branch_uuid = data.get("branch_id")
        product_id = data.get("product_id")
        file_type = data.get("file_type", "pdf")
        delivery_method = data.get("delivery_method", "download")
        movement_type = data.get("movement_type")
        stock_level = data.get("stock_level")
        start_date = data.get("start_date")
        end_date = data.get("end_date")
        filter_key = data.get("date_filter", "all").lower()

        institution = get_institution(request)
        if not start_date and not end_date:
            start_date, end_date = get_date_range_from_filter(filter_key, institution)

        filters = {
            "branch_uuid": str(branch_uuid) if branch_uuid else None,
            "product_uuid": str(product_id) if product_id else None,
            "movement_type": movement_type,
            "stock_level": stock_level,
            "start_date": start_date.isoformat() if start_date else None,
            "end_date": end_date.isoformat() if end_date else None,
        }

        if delivery_method == "email":
            recipient = resolve_export_recipient(
                request,
                data.get("recipient_email"),
            )
            stock_movement_report_email_task.delay(
                institution_id=institution.id,
                recipient=recipient,
                file_type=file_type,
                filters=filters,
            )
            return Response(
                {
                    "message": (
                        "Stock movement report generation initiated. "
                        "The report will be emailed shortly."
                    )
                },
                status=status.HTTP_202_ACCEPTED,
            )

        logs = build_stock_movement_queryset(
            institution=institution,
            **filters,
        )
        if not logs.exists():
            return Response(
                {"detail": "No stock movement logs found."},
                status=status.HTTP_404_NOT_FOUND,
            )

        report = generate_stock_movement_file(
            institution=institution,
            logs=logs,
            file_type=file_type,
            start_date=start_date,
            end_date=end_date,
            filters=filters,
        )
        return report.as_download_response()
