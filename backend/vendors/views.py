from approval.models import Approval
from audit.utils import log_action
from utilities.helpers import get_institution, get_or_raise, parse_bool_query_param
from utilities.helpers import validation_error
from .prepayment_reconciliation import reconcile_prepayments
from utilities.pagination import CustomPageNumberPagination
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework import serializers, status
from .serializers import (
    GoodsReceivedNoteLineItemSerializer,
    PrepaymentAllocationSerializer,
    SimpleVendorPurchaseOrderSerializer,
    VendorBillSerializer,
    VendorBillLineItemSerializer,
    VendorBillLineItemsAndExpensesSerializer,
    VendorPurchaseOrderLineItemSerializer,
    VendorSerializer,
    VendorPurchaseOrderSerializer,
    VendorPaymentSerializer,
    GoodsReceivedNoteSerializer,
    VendorOutstandingBalanceAdjustmentSerializer,
    ReconcilePrepaymentSerializer,
)
from .models import (
    GoodsReceivedNoteLineItem,
    PrepaymentAllocation,
    Vendor,
    VendorBill,
    VendorBillLineItem,
    VendorPurchaseOrder,
    VendorPurchaseOrderLineItem,
    VendorPayment,
    GoodsReceivedNote,
    VendorOutstandingBalanceAdjustment,
)
from drf_spectacular.utils import extend_schema, inline_serializer, OpenApiParameter
from audit.models import AuditLog
from django.contrib.contenttypes.models import ContentType
from django.db.models import Exists, F, OuterRef, Q
from django.core.exceptions import ObjectDoesNotExist
from django.contrib.contenttypes.models import ContentType
from users.permissions import HasInstitutionPermission
from utilities.helpers import serialize_value
from django.db import transaction
from system.exceptions import SystemNotFoundError
from django.shortcuts import get_object_or_404
from utilities.openapi import (
    SEARCH_PARAM,
    ORDERING_PARAM,
    vendor_base_uuid_param,
    bill_base_uuid_param,
    vendor_payment_base_uuid_param,
)
from utilities.mixin import SearchOrderMixin


class VendorBillListCreateView(APIView, SearchOrderMixin):
    permission_classes = [HasInstitutionPermission]
    required_permissions = {
        "get": "can_view_vendor_bills",
        "post": "can_create_vendor_bills",
    }

    @extend_schema(
        responses={200: VendorBillSerializer(many=True)},
        description="Retrieve a list of all vendor bills.",
        summary="List all vendor bills",
        tags=["Vendor Bills MGT"],
        parameters=[
            SEARCH_PARAM,
            ORDERING_PARAM,
            vendor_base_uuid_param(required=False),
            OpenApiParameter(
                name="get_only_not_fully_received",
                type=bool,
                location=OpenApiParameter.QUERY,
                description="Filter invoices that are not fully received.",
                required=False,
            ),
            OpenApiParameter(
                name="filter_out_fully_paid_bills",
                type=bool,
                location=OpenApiParameter.QUERY,
                description="Return only unpaid or partially paid bills with a balance due.",
                required=False,
            ),
        ],
    )
    def get(self, request):
        vendor_base_uuid = request.query_params.get("vendor_base_uuid", None)
        get_only_not_fully_received = str(
            request.query_params.get("get_only_not_fully_received", False)
        ).lower() in ("true", "1", "t", "yes")
        filter_out_fully_paid_bills = str(
            request.query_params.get("filter_out_fully_paid_bills", False)
        ).lower() in ("true", "1", "t", "yes")

        institution = get_institution(request)

        vendors_bills = VendorBill.objects.filter(
            Q(purchase_order__vendor__institution=institution)
            | Q(vendor__institution=institution),
            deleted_at__isnull=True,
        ).order_by("-created_at")

        if get_only_not_fully_received:
            vendors_bills = vendors_bills.filter(
                goods_received_note_status__in=["not_received", "partially_received"]
            )

        if filter_out_fully_paid_bills:
            vendors_bills = vendors_bills.filter(
                payment_status__in=["unpaid", "partial"],
                balance_due__gt=0,
            )

        vendors_bills = self.apply_filters(vendors_bills)
        vendors_bills = self.apply_search(vendors_bills)
        vendors_bills = self.apply_ordering(vendors_bills)

        if vendor_base_uuid:
            try:
                vendor = Vendor.objects.get(base_uuid=vendor_base_uuid)
            except ObjectDoesNotExist:
                raise SystemNotFoundError(
                    detail=f"Vendor bill with UUID '{vendor_base_uuid}' not found."
                )
            vendors_bills = vendors_bills.filter(
                Q(purchase_order__vendor=vendor) | Q(vendor=vendor)
            )

        paginator = CustomPageNumberPagination()
        paginator_qs = paginator.paginate_queryset(vendors_bills, request)
        serializer = VendorBillSerializer(paginator_qs, many=True)
        return paginator.get_paginated_response(serializer.data)

    @extend_schema(
        request=VendorBillSerializer,
        responses={201: VendorBillSerializer},
        description="Create a new vendor bill.",
        summary="Create a new vendor bill",
        tags=["Vendor Bills MGT"],
    )
    def post(self, request):
        serializer = VendorBillSerializer(
            data=request.data, context={"request": request}
        )
        if serializer.is_valid():
            bill = serializer.save()
            AuditLog.objects.create(
                content_type=ContentType.objects.get_for_model(VendorBill),
                object_id=bill.pk,
                action="CREATE",
                user=request.user if request.user.is_authenticated else None,
                description=f"Created vendor bill {bill.base_uuid}",
            )
            bill.confirm_create(
                profile_institution=request.profile_institution,
                external_identity=request.external_identity,
            )
            return Response(serializer.data, status=status.HTTP_201_CREATED)
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)


class VendorBillDetailView(APIView):
    permission_classes = [HasInstitutionPermission]
    required_permissions = {
        "get": "can_view_vendor_bills",
        "patch": "can_edit_vendor_bills",
        "delete": "can_delete_vendor_bills",
    }

    def _get_vendor_bill(self, request, base_uuid):
        institution = get_institution(request)

        return get_or_raise(
            VendorBill.objects.undeleted().filter(
                Q(purchase_order__vendor__institution=institution)
                | Q(vendor__institution=institution)
            ),
            message=f"Vendor bill with UUID '{base_uuid}' not found.",
            base_uuid=base_uuid,
        )

    @extend_schema(
        responses={200: VendorBillSerializer},
        description="Retrieve details of a specific vendor bill.",
        summary="Get vendor bill details",
        tags=["Vendor Bills MGT"],
    )
    def get(self, request, base_uuid):
        vendor_bill = self._get_vendor_bill(request, base_uuid)
        serializer = VendorBillSerializer(vendor_bill)
        return Response(serializer.data)

    @extend_schema(
        request=VendorBillSerializer,
        responses={200: VendorBillSerializer},
        description="Partially update details of a specific vendor bill.",
        summary="Partially update vendor bill details",
        tags=["Vendor Bills MGT"],
    )
    def patch(self, request, base_uuid):
        vendor_bill = self._get_vendor_bill(request, base_uuid)

        old_data = VendorBillSerializer(vendor_bill).data
        vendor_bill.approval_status = "under_update"
        serializer = VendorBillSerializer(
            vendor_bill, data=request.data, partial=True, context={"request": request}
        )
        if serializer.is_valid():
            with transaction.atomic():
                updated_vendor_bill = serializer.save()
                new_data = VendorBillSerializer(updated_vendor_bill).data
                changes = {
                    key: {"old": old_data.get(key), "new": new_data.get(key)}
                    for key in request.data.keys()
                    if old_data.get(key) != new_data.get(key)
                }
                cleaned_changes = serialize_value(changes)
                AuditLog.objects.create(
                    content_type=ContentType.objects.get_for_model(VendorBill),
                    object_id=updated_vendor_bill.pk,
                    action="UPDATE",
                    user=request.user if request.user.is_authenticated else None,
                    changes=cleaned_changes,
                    description=f"Updated vendor bill {updated_vendor_bill.base_uuid}",
                )
                updated_vendor_bill.confirm_update(
                    profile_institution=request.profile_institution,
                    external_identity=request.external_identity,
                )
                return Response(serializer.data)
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

    @extend_schema(
        responses={204: None},
        description="Delete a specific vendor bill.",
        summary="Delete a vendor bill",
        tags=["Vendor Bills MGT"],
    )
    def delete(self, request, base_uuid):
        vendor_bill = self._get_vendor_bill(request, base_uuid)
        vendor_bill.approval_status = "under_deletion"
        vendor_bill.save(update_fields=["approval_status"])
        vendor_bill.confirm_delete(
            profile_institution=request.profile_institution,
            external_identity=request.external_identity,
        )
        return Response(status=status.HTTP_204_NO_CONTENT)


class VendorListView(APIView, SearchOrderMixin):

    permission_classes = [HasInstitutionPermission]
    required_permissions = {
        "get": "can_view_vendors",
        "post": "can_create_vendors",
    }

    queryset = Vendor.objects.undeleted()

    @extend_schema(
        request=VendorSerializer,
        responses={200: VendorSerializer(many=True)},
        description="Retrieve a list of all vendors.",
        summary="List all vendors",
        tags=["Vendor Management"],
        parameters=[
            SEARCH_PARAM,
            ORDERING_PARAM,
            vendor_base_uuid_param(required=False),
            OpenApiParameter(
                name="without_requisition_beneficiary",
                required=False,
                description=(
                    "When true, return only vendors that are not linked to a "
                    "requisition beneficiary."
                ),
                type=bool,
                location=OpenApiParameter.QUERY,
            ),
            OpenApiParameter(
                name="has_purchase_orders",
                required=False,
                description="Return only vendors with or without purchase orders.",
                type=bool,
                location=OpenApiParameter.QUERY,
            ),
            OpenApiParameter(
                name="has_vendor_bills",
                required=False,
                description="Return only vendors with or without vendor bills.",
                type=bool,
                location=OpenApiParameter.QUERY,
            ),
            OpenApiParameter(
                name="active_without_ongoing_approval",
                type=bool,
                location=OpenApiParameter.QUERY,
                description="Return only active vendors with active approval status and no ongoing approvals.",
                required=False,
            ),
        ],
    )
    def get(self, request):
        institution = get_institution(request)

        without_requisition_beneficiary = parse_bool_query_param(
            request.query_params.get("without_requisition_beneficiary"),
            "without_requisition_beneficiary",
        )
        has_purchase_orders = parse_bool_query_param(
            request.query_params.get("has_purchase_orders"),
            "has_purchase_orders",
        )
        has_vendor_bills = parse_bool_query_param(
            request.query_params.get("has_vendor_bills"),
            "has_vendor_bills",
        )
        active_without_ongoing_approval = parse_bool_query_param(
            request.query_params.get("active_without_ongoing_approval"),
            "active_without_ongoing_approval",
        )

        vendors = self.queryset.filter(
            institution=institution,
        )

        if active_without_ongoing_approval is True:
            ongoing_approvals = Approval.objects.filter(
                content_type=ContentType.objects.get_for_model(Vendor),
                object_id=OuterRef("pk"),
                status="ongoing",
            )
            vendors = vendors.filter(
                is_active=True,
                approval_status="active",
            ).filter(~Exists(ongoing_approvals))

        if without_requisition_beneficiary is True:
            vendors = vendors.filter(requisition_beneficiary_id__isnull=True)

        if has_purchase_orders is not None:
            eligible_purchase_orders = VendorPurchaseOrder.objects.undeleted().filter(
                vendor=OuterRef("pk"),
            )

            purchase_order_exists = Exists(eligible_purchase_orders)
            vendors = (
                vendors.filter(purchase_order_exists)
                if has_purchase_orders
                else vendors.filter(~purchase_order_exists)
            )

        if has_vendor_bills is not None:
            eligible_vendor_bills = VendorBill.objects.undeleted().filter(
                Q(vendor=OuterRef("pk")) | Q(purchase_order__vendor=OuterRef("pk"))
            )

            vendor_bill_exists = Exists(eligible_vendor_bills)
            vendors = (
                vendors.filter(vendor_bill_exists)
                if has_vendor_bills
                else vendors.filter(~vendor_bill_exists)
            )

        vendor_base_uuid = request.query_params.get("vendor_base_uuid", None)

        if vendor_base_uuid:
            vendors = vendors.filter(base_uuid=vendor_base_uuid)

        vendors = self.apply_search(vendors)
        vendors = self.apply_ordering(vendors)
        vendors = self.apply_filters(vendors)

        paginator = CustomPageNumberPagination()
        paginator_qs = paginator.paginate_queryset(vendors, request)
        serializer = VendorSerializer(paginator_qs, many=True)
        return paginator.get_paginated_response(serializer.data)

    @extend_schema(
        request=VendorSerializer,
        responses={201: VendorSerializer},
        description="Create a new vendor.",
        summary="Create a new vendor",
        tags=["Vendor Management"],
    )
    def post(self, request):
        serializer = VendorSerializer(
            data=request.data,
            context={"request": request},
        )
        if serializer.is_valid():
            vendor = serializer.save()

            log_action(
                model_class=Vendor,
                object_id=serializer.instance.pk,
                action="CREATE",
                user=request.user if request.user.is_authenticated else None,
                description=f"Created vendor {serializer.instance.vendor_name} ({serializer.instance.base_uuid})",
            )

            vendor.confirm_create(
                profile_institution=request.profile_institution,
                external_identity=request.external_identity,
            )

            return Response(serializer.data, status=status.HTTP_201_CREATED)
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)


class VendorDetailView(APIView):
    permission_classes = [HasInstitutionPermission]
    required_permissions = {
        "get": "can_view_vendors",
        "patch": "can_edit_vendors",
        "delete": "can_delete_vendors",
    }

    def _get_vendor(self, request, base_uuid):
        institution = get_institution(request)

        return get_or_raise(
            Vendor.objects.undeleted().filter(institution=institution),
            message=f"Vendor with UUID '{base_uuid}' not found.",
            base_uuid=base_uuid,
        )

    @extend_schema(
        responses={200: VendorSerializer},
        description="Retrieve details of a specific vendor.",
        summary="Get vendor details",
        tags=["Vendor Management"],
    )
    def get(self, request, base_uuid):
        vendor = self._get_vendor(request, base_uuid)
        serializer = VendorSerializer(vendor)
        return Response(serializer.data)

    @extend_schema(
        request=VendorSerializer,
        responses={200: VendorSerializer},
        description="Partially update details of a specific vendor.",
        summary="Partially update vendor details",
        tags=["Vendor Management"],
    )
    def patch(self, request, base_uuid):
        vendor = self._get_vendor(request, base_uuid)

        old_data = VendorSerializer(vendor).data
        vendor.approval_status = "under_update"
        serializer = VendorSerializer(
            vendor, data=request.data, partial=True, context={"request": request}
        )
        if serializer.is_valid():
            updated_vendor = serializer.save()
            new_data = VendorSerializer(vendor).data
            changes = {
                key: {"old": old_data.get(key), "new": new_data.get(key)}
                for key in request.data.keys()
                if old_data.get(key) != new_data.get(key)
            }
            log_action(
                model_class=Vendor,
                object_id=vendor.id,
                action="UPDATE",
                user=request.user if request.user.is_authenticated else None,
                changes=changes,
                description=f"Updated vendor {vendor.vendor_name} ({vendor.base_uuid})",
            )
            updated_vendor.confirm_update(
                profile_institution=request.profile_institution,
                external_identity=request.external_identity,
            )
            return Response(serializer.data)
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

    @extend_schema(
        responses={204: None},
        description="Delete a specific vendor.",
        summary="Delete a vendor",
        tags=["Vendor Management"],
    )
    def delete(self, request, base_uuid):
        vendor = self._get_vendor(request, base_uuid)
        vendor.approval_status = "under_deletion"
        vendor.save(update_fields=["approval_status"])

        log_action(
            model_class=Vendor,
            object_id=vendor.id,
            action="DELETE",
            user=request.user if request.user.is_authenticated else None,
            description=f"Deleted vendor {vendor.vendor_name} ({vendor.base_uuid})",
        )

        vendor.confirm_delete(
            profile_institution=request.profile_institution,
            external_identity=request.external_identity,
        )
        return Response(status=status.HTTP_204_NO_CONTENT)


class VendorPurchaseOrderListView(APIView, SearchOrderMixin):

    permission_classes = [HasInstitutionPermission]
    required_permissions = {
        "get": "can_view_vendor_purchase_orders",
        "post": "can_create_vendor_purchase_orders",
    }

    @extend_schema(
        request=VendorPurchaseOrderSerializer,
        responses={200: SimpleVendorPurchaseOrderSerializer(many=True)},
        description="Retrieve a list of all purchase orders. Supports searching by purchase order number or vendor name.",
        summary="List all purchase orders",
        tags=["Vendor Purchase Order Management"],
        parameters=[
            SEARCH_PARAM,
            ORDERING_PARAM,
            vendor_base_uuid_param(required=False),
            OpenApiParameter(
                name="active_without_ongoing_approval",
                type=bool,
                location=OpenApiParameter.QUERY,
                description="Return only active purchase orders with no ongoing approvals.",
                required=False,
            ),
            OpenApiParameter(
                name="get_only_not_full_billed",
                type=bool,
                location=OpenApiParameter.QUERY,
                description="Filter purchase orders that are not fully billed (not_billed or partially_billed).",
                required=False,
            ),
            OpenApiParameter(
                name="get_only_not_full_received",
                type=bool,
                location=OpenApiParameter.QUERY,
                description="Filter purchase orders that are not fully received (not_received or partially_received).",
                required=False,
            ),
            OpenApiParameter(
                name="only_approved",
                type=bool,
                location=OpenApiParameter.QUERY,
                description="Filter purchase orders that are approved.",
                required=False,
            ),
        ],
    )
    def get(self, request):
        institution = get_institution(request)

        vendor_base_uuid = request.query_params.get("vendor_base_uuid", None)
        get_only_not_full_billed = str(
            request.query_params.get("get_only_not_full_billed", False)
        ).lower() in ("true", "1", "t", "yes")

        get_only_not_full_received = str(
            request.query_params.get("get_only_not_full_received", False)
        ).lower() in ("true", "1", "t", "yes")

        only_approved = str(
            request.query_params.get("only_approved", False)
        ).lower() in ("true", "1", "t", "yes")

        purchase_orders = VendorPurchaseOrder.objects.undeleted().filter(
            vendor__institution=institution,
        )

        if vendor_base_uuid:
            purchase_orders = purchase_orders.filter(vendor__base_uuid=vendor_base_uuid)

        if get_only_not_full_billed:
            purchase_orders = purchase_orders.filter(
                bill_status__in=["not_billed", "partially_billed"]
            )

        if get_only_not_full_received:
            purchase_orders = purchase_orders.filter(
                goods_received_note_status__in=["not_received", "partially_received"]
            )

        if only_approved:
            purchase_orders = purchase_orders.filter(status="approved")

        if (
            parse_bool_query_param(
                request.query_params.get("active_without_ongoing_approval"),
                "active_without_ongoing_approval",
            )
            is True
        ):
            ongoing_approvals = Approval.objects.filter(
                content_type=ContentType.objects.get_for_model(VendorPurchaseOrder),
                object_id=OuterRef("pk"),
                status="ongoing",
            )
            purchase_orders = purchase_orders.filter(
                is_active=True,
                approval_status="active",
            ).filter(~Exists(ongoing_approvals))

        purchase_orders = self.apply_filters(purchase_orders)
        purchase_orders = self.apply_search(purchase_orders)
        purchase_orders = self.apply_ordering(purchase_orders)

        paginator = CustomPageNumberPagination()
        paginator_qs = paginator.paginate_queryset(purchase_orders, request)
        serializer = SimpleVendorPurchaseOrderSerializer(paginator_qs, many=True)
        return paginator.get_paginated_response(serializer.data)

    @extend_schema(
        request=VendorPurchaseOrderSerializer,
        responses={201: VendorPurchaseOrderSerializer},
        description="Create a new purchase order.",
        summary="Create a new purchase order",
        tags=["Vendor Purchase Order Management"],
    )
    @transaction.atomic
    def post(self, request):
        serializer = VendorPurchaseOrderSerializer(
            data=request.data, context={"request": request}
        )
        if serializer.is_valid():
            purchase_order = serializer.save()

            log_action(
                model_class=VendorPurchaseOrder,
                object_id=purchase_order.pk,
                action="CREATE",
                user=request.user,
                description=f"Created Purchase Order: {purchase_order.reference_code}",
            )
            purchase_order.confirm_create(
                profile_institution=request.profile_institution,
                external_identity=request.external_identity,
            )
            return Response(serializer.data, status=status.HTTP_201_CREATED)
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)


class VendorPurchaseOrderPDFDownloadView(APIView):
    permission_classes = [HasInstitutionPermission]
    required_permissions = {"get": "can_view_vendor_purchase_orders"}

    def get(self, request, base_uuid):
        from django.http import HttpResponse
        from django.template.loader import render_to_string
        from django.utils.http import content_disposition_header
        from weasyprint import HTML

        institution = get_institution(request)
        purchase_order = get_object_or_404(
            VendorPurchaseOrder.objects.select_related(
                "vendor", "vendor__currency", "currency", "branch"
            ),
            base_uuid=base_uuid,
            vendor__institution=institution,
            deleted_at__isnull=True,
        )
        currency = (
            purchase_order.currency
            or purchase_order.vendor.currency
            or institution.currency
        )
        html = render_to_string(
            "_vendor_purchase_order.html",
            {
                "institution": institution,
                "order": purchase_order,
                "vendor": purchase_order.vendor,
                "currency": currency,
                "line_items": purchase_order.get_line_items(),
                "net_total": purchase_order.get_net_total(),
                "tax_total": purchase_order.get_tax_total(),
                "total": purchase_order.get_total_amount(),
            },
            request=request,
        )
        response = HttpResponse(
            HTML(string=html, base_url=request.build_absolute_uri("/")).write_pdf(),
            content_type="application/pdf",
        )
        filename = f"PurchaseOrder-{purchase_order.reference_code}.pdf"
        response["Content-Disposition"] = content_disposition_header(
            True, filename.replace("/", "-")
        )
        return response


class VendorPurchaseOrderDetailView(APIView):
    permission_classes = [HasInstitutionPermission]
    required_permissions = {
        "get": "can_view_vendor_purchase_orders",
        "patch": "can_create_vendor_purchase_orders",
        "delete": "can_delete_vendor_purchase_orders",
    }

    def get_object(self, request, base_uuid):
        institution = get_institution(request)

        return get_or_raise(
            VendorPurchaseOrder.objects.undeleted().filter(
                vendor__institution=institution
            ),
            message=f"Vendor purchase order with UUID '{base_uuid}' not found.",
            base_uuid=base_uuid,
        )

    @extend_schema(
        responses={200: VendorPurchaseOrderSerializer},
        description="Retrieve details of a specific purchase order.",
        summary="Get purchase order details",
        tags=["Vendor Purchase Order Management"],
    )
    def get(self, request, base_uuid):
        purchase_order = self.get_object(request, base_uuid)

        serializer = VendorPurchaseOrderSerializer(purchase_order)
        return Response(serializer.data)

    @extend_schema(
        request=VendorPurchaseOrderSerializer,
        responses={200: VendorPurchaseOrderSerializer},
        description="Partially update details of a specific purchase order.",
        summary="Partially update purchase order details",
        tags=["Vendor Purchase Order Management"],
    )
    @transaction.atomic
    def patch(self, request, base_uuid):
        purchase_order = self.get_object(request, base_uuid)
        if not purchase_order:
            return Response(status=status.HTTP_404_NOT_FOUND)
        purchase_order = VendorPurchaseOrder.objects.select_for_update().get(
            pk=purchase_order.pk
        )
        purchase_order.ensure_no_ongoing_approval(attempted_action="update")
        old_data = VendorPurchaseOrderSerializer(purchase_order).data
        serializer = VendorPurchaseOrderSerializer(
            purchase_order,
            data=request.data,
            partial=True,
            context={"request": request},
        )
        if serializer.is_valid():
            purchase_order.approval_status = "under_update"
            updated_purchase_order = serializer.save()
            new_data = VendorPurchaseOrderSerializer(updated_purchase_order).data
            audit_fields = {
                key: (
                    key.replace("_line_items", "_items")
                    if key in VendorPurchaseOrderSerializer.LINE_ITEM_FIELDS
                    else key
                )
                for key in request.data
            }
            changes = {
                key: {"old": old_data.get(output_key), "new": new_data.get(output_key)}
                for key, output_key in audit_fields.items()
                if old_data.get(output_key) != new_data.get(output_key)
            }
            cleaned_changes = serialize_value(changes)
            log_action(
                model_class=VendorPurchaseOrder,
                object_id=updated_purchase_order.id,
                action="UPDATE",
                user=request.user if request.user.is_authenticated else None,
                changes=cleaned_changes,
                description=f"Updated purchase order {updated_purchase_order.reference_code} ({updated_purchase_order.base_uuid})",
            )
            updated_purchase_order.confirm_update(
                profile_institution=request.profile_institution,
                external_identity=request.external_identity,
            )
            return Response(serializer.data)
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

    @extend_schema(
        responses={204: None},
        description="Delete a specific purchase order.",
        summary="Delete a purchase order (vendor workflow)",
        tags=["Vendor Purchase Order Management"],
    )
    @transaction.atomic
    def delete(self, request, base_uuid):
        purchase_order = self.get_object(request, base_uuid)
        if not purchase_order:
            return Response(status=status.HTTP_404_NOT_FOUND)

        purchase_order = VendorPurchaseOrder.objects.select_for_update().get(
            pk=purchase_order.pk
        )
        purchase_order_id = purchase_order.id
        purchase_order_data = VendorPurchaseOrderSerializer(purchase_order).data
        purchase_order.confirm_delete(
            profile_institution=request.profile_institution,
            external_identity=request.external_identity,
        )
        log_action(
            model_class=VendorPurchaseOrder,
            object_id=purchase_order_id,
            action="DELETE",
            user=request.user if request.user.is_authenticated else None,
            changes=purchase_order_data,
            description=f"Requested deletion of purchase order {purchase_order_data['reference_code']} ({base_uuid})",
        )
        return Response(status=status.HTTP_204_NO_CONTENT)


class VendorPurchaseOrderLineItemListView(APIView, SearchOrderMixin):
    permission_classes = [HasInstitutionPermission]
    required_permissions = {
        "get": "can_view_vendor_purchase_orders",
    }

    @extend_schema(
        responses={200: VendorPurchaseOrderLineItemSerializer(many=True)},
        description="List the line items belonging to a vendor purchase order.",
        summary="List vendor purchase order line items",
        tags=["Vendor Purchase Order Management"],
        parameters=[SEARCH_PARAM, ORDERING_PARAM],
    )
    def get(self, request, base_uuid):
        institution = get_institution(request)

        purchase_order = get_or_raise(
            queryset=VendorPurchaseOrder.objects.undeleted(),
            message=f"Vendor purchase order with UUID '{base_uuid}' not found.",
            base_uuid=base_uuid,
            institution=institution,
        )

        line_items = purchase_order.line_items

        line_items = (
            VendorPurchaseOrderLineItem.objects.undeleted()
            .filter(purchase_order=purchase_order)
            .select_related(
                "purchase_order",
                "inventory_item",
                "inventory_item__item_category",
                "unit_of_measure",
                "unit_of_measure__unit_of_measure",
                "asset_category",
            )
            .prefetch_related("tax_breakdowns__tax")
        )

        line_items = self.apply_search(line_items)
        line_items = self.apply_ordering(line_items)

        paginator = CustomPageNumberPagination()
        paginator_qs = paginator.paginate_queryset(line_items, request)
        serializer = VendorPurchaseOrderLineItemSerializer(
            paginator_qs,
            many=True,
            context={"request": request},
        )
        return paginator.get_paginated_response(serializer.data)


class VendorBillLineItemListView(APIView, SearchOrderMixin):
    permission_classes = [HasInstitutionPermission]
    required_permissions = {
        "get": "can_view_vendor_bills",
    }

    @extend_schema(
        responses={200: VendorBillLineItemsAndExpensesSerializer},
        description="List the line items and expenses belonging to a vendor bill.",
        summary="List vendor bill line items and expenses",
        tags=["Vendor Bills MGT"],
        parameters=[SEARCH_PARAM, ORDERING_PARAM],
    )
    def get(self, request, base_uuid):
        institution = get_institution(request)

        vendor_bill = get_or_raise(
            queryset=VendorBill.objects.undeleted().filter(
                Q(purchase_order__vendor__institution=institution)
                | Q(vendor__institution=institution)
            ),
            message=f"Vendor bill with UUID '{base_uuid}' not found.",
            base_uuid=base_uuid,
        )

        line_items = (
            VendorBillLineItem.objects.undeleted()
            .filter(bill=vendor_bill)
            .select_related(
                "bill",
                "inventory_item",
                "inventory_item__item_category",
                "unit_of_measure",
                "unit_of_measure__unit_of_measure",
                "asset_category",
            )
            .prefetch_related("tax_breakdowns__tax")
        )
        line_items = self.apply_search(line_items)
        line_items = self.apply_ordering(line_items)

        if parse_bool_query_param(
            request.query_params.get("paginated"),
            "paginated",
        ):
            paginator = CustomPageNumberPagination()
            paginated_items = paginator.paginate_queryset(line_items, request)
            serializer = VendorBillLineItemSerializer(
                paginated_items,
                many=True,
                context={"request": request},
            )
            return paginator.get_paginated_response(serializer.data)

        expenses = (
            vendor_bill.order_expenses.select_related(
                "account_to_record_expense",
            )
            .prefetch_related("tax_breakdowns__tax")
            .order_by("created_at")
        )

        serializer = VendorBillLineItemsAndExpensesSerializer(
            {
                "line_items": line_items,
                "expenses": expenses,
            },
            context={"request": request},
        )
        return Response(serializer.data)


class VendorPaymentListCreateView(APIView, SearchOrderMixin):
    permission_classes = [HasInstitutionPermission]
    required_permissions = {
        "get": "can_view_vendor_payment_terms",
        "post": "can_create_vendor_payment_terms",
    }

    @extend_schema(
        responses={200: VendorPaymentSerializer(many=True)},
        description="Retrieve a list of all vendor payments.",
        summary="List all vendor payments",
        tags=["Vendor Payments MGT"],
        parameters=[
            SEARCH_PARAM,
            ORDERING_PARAM,
            vendor_base_uuid_param(required=False),
            bill_base_uuid_param(required=False),
            OpenApiParameter(
                name="has_bill",
                type=bool,
                location=OpenApiParameter.QUERY,
                required=False,
                description="Filter payments that have bill attachment (true/false)",
            ),
            OpenApiParameter(
                name="only_paid",
                type=bool,
                location=OpenApiParameter.QUERY,
                required=False,
                description="Filter payments that have been paid (true/false)",
            ),
        ],
    )
    def get(self, request):
        institution = get_institution(request)
        vendor_base_uuid = request.query_params.get("vendor_base_uuid")
        bill_base_uuid = request.query_params.get("bill_base_uuid")
        available_prepayments = request.query_params.get("available_prepayments")
        has_bill = request.query_params.get("has_bill")
        only_paid = request.query_params.get("only_paid")

        vendors_payments = (
            VendorPayment.objects.filter(deleted_at__isnull=True)
            .filter(
                Q(vendor__institution=institution) | Q(bill__institution=institution)
            )
            .distinct()
        )

        if vendor_base_uuid:
            try:
                vendor = Vendor.objects.get(
                    base_uuid=vendor_base_uuid, institution=institution
                )
            except Vendor.DoesNotExist:
                raise SystemNotFoundError(
                    detail=f"Vendor with UUID '{vendor_base_uuid}' not found."
                )

            vendors_payments = vendors_payments.filter(vendor=vendor)

        if bill_base_uuid:
            try:
                bill = VendorBill.objects.filter(
                    base_uuid=bill_base_uuid,
                    deleted_at__isnull=True,
                ).get(
                    Q(vendor__institution=institution)
                    | Q(purchase_order__vendor__institution=institution)
                )
            except VendorBill.DoesNotExist:
                raise SystemNotFoundError(
                    detail=f"Vendor Bill with UUID '{bill_base_uuid}' not found."
                )

            vendors_payments = vendors_payments.filter(bill=bill)

        if has_bill is not None:
            if has_bill.lower() == "true":
                vendors_payments = vendors_payments.filter(bill__isnull=False)
            elif has_bill.lower() == "false":
                vendors_payments = vendors_payments.filter(bill__isnull=True)

        if only_paid is not None:
            if only_paid.lower() == "true":
                vendors_payments = vendors_payments.filter(payment_status="PAID")
            elif only_paid.lower() == "false":
                vendors_payments = vendors_payments.exclude(payment_status="PAID")

        if available_prepayments is not None:
            if available_prepayments.lower() == "true":
                vendors_payments = vendors_payments.filter(
                    bill__isnull=True,
                    amount__gt=F("amount_reconciled"),
                    vendor=vendor,
                )

        vendors_payments = self.apply_search(vendors_payments)
        vendors_payments = self.apply_ordering(vendors_payments)

        paginator = CustomPageNumberPagination()
        paginator_qs = paginator.paginate_queryset(vendors_payments, request)
        serializer = VendorPaymentSerializer(paginator_qs, many=True)

        return paginator.get_paginated_response(serializer.data)

    @extend_schema(
        request=VendorPaymentSerializer,
        responses={201: VendorPaymentSerializer(many=True)},
        description="Create a new vendor payment.",
        summary="Create a new vendor payment",
        tags=["Vendor Payments MGT"],
    )
    def post(self, request):
        serializer = VendorPaymentSerializer(
            data=request.data, context={"request": request}
        )
        if serializer.is_valid():
            payment = serializer.save()
            AuditLog.objects.create(
                content_type=ContentType.objects.get_for_model(VendorPayment),
                object_id=payment.pk,
                action="CREATE",
                user=request.user if request.user.is_authenticated else None,
                description=f"Created vendor payment {payment.base_uuid}",
            )
            payment.confirm_create(
                profile_institution=request.profile_institution,
                external_identity=request.external_identity,
            )
            return Response(serializer.data, status=status.HTTP_201_CREATED)
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)


class VendorPaymentDetailView(APIView):
    permission_classes = [HasInstitutionPermission]
    required_permissions = {
        "get": "can_view_vendor_payment_terms",
        "patch": "can_edit_vendor_payment_terms",
        "delete": "can_delete_vendor_payment_terms",
    }

    def get_object(self, request, base_uuid):
        institution = get_institution(request)

        return get_or_raise(
            VendorPayment.objects.undeleted().filter(
                Q(vendor__institution=institution) | Q(bill__institution=institution)
            ),
            message=f"Vendor payment with UUID '{base_uuid}' not found.",
            base_uuid=base_uuid,
        )

    @extend_schema(
        responses={200: VendorPaymentSerializer},
        description="Retrieve details of a specific vendor payment.",
        summary="Get vendor payment details",
        tags=["Vendor Payments MGT"],
    )
    def get(self, request, base_uuid):
        vendor_payment = self.get_object(request, base_uuid)
        serializer = VendorPaymentSerializer(vendor_payment)
        return Response(serializer.data)

    @extend_schema(
        request=VendorPaymentSerializer,
        responses={200: VendorPaymentSerializer},
        description="Partially update details of a specific vendor payment.",
        summary="Partially update vendor payment details",
        tags=["Vendor Payments MGT"],
    )
    def patch(self, request, base_uuid):
        vendor_payment = self.get_object(request, base_uuid)
        old_data = VendorPaymentSerializer(vendor_payment).data
        vendor_payment.approval_status = "under_update"
        serializer = VendorPaymentSerializer(
            vendor_payment,
            data=request.data,
            partial=True,
            context={"request": request},
        )
        if serializer.is_valid():
            with transaction.atomic():
                updated_vendor_payment = serializer.save()
                new_data = VendorPaymentSerializer(updated_vendor_payment).data
                changes = {
                    key: {
                        "old": serialize_value(old_data.get(key)),
                        "new": serialize_value(new_data.get(key)),
                    }
                    for key in request.data.keys()
                    if old_data.get(key) != new_data.get(key)
                }
                AuditLog.objects.create(
                    content_type=ContentType.objects.get_for_model(VendorPayment),
                    object_id=vendor_payment.id,
                    action="UPDATE",
                    user=request.user if request.user.is_authenticated else None,
                    changes=changes,
                    description=f"Updated vendor payment {vendor_payment.base_uuid}",
                )
                updated_vendor_payment.confirm_update(
                    profile_institution=request.profile_institution,
                    external_identity=request.external_identity,
                )
                return Response(serializer.data)
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

    @extend_schema(
        responses={204: None},
        description="Delete a specific vendor payment.",
        summary="Delete a vendor payment",
        tags=["Vendor Payments MGT"],
    )
    def delete(self, request, base_uuid):
        vendor_payment = self.get_object(request, base_uuid)
        vendor_payment.approval_status = "under_deletion"
        vendor_payment.save(update_fields=["approval_status"])
        vendor_payment.confirm_delete(
            profile_institution=request.profile_institution,
            external_identity=request.external_identity,
        )
        return Response(status=status.HTTP_204_NO_CONTENT)


class GoodsReceivedNoteListCreateView(APIView, SearchOrderMixin):
    permission_classes = [HasInstitutionPermission]
    required_permissions = {
        "get": "can_view_goods_received_notes",
        "post": "can_create_goods_received_notes",
    }

    queryset = GoodsReceivedNote.objects.undeleted()

    @extend_schema(
        responses={200: GoodsReceivedNoteSerializer(many=True)},
        description="Retrieve a list of all goods received notes.",
        summary="List all goods received notes",
        tags=["Goods Received Notes Management"],
        parameters=[
            SEARCH_PARAM,
            ORDERING_PARAM,
        ],
    )
    def get(self, request):
        institution = get_institution(request)
        bill_base_uuid = request.query_params.get("bill_base_uuid", None)

        grns = GoodsReceivedNote.objects.filter(
            Q(bill__vendor__institution=institution)
            | Q(bill__purchase_order__vendor__institution=institution)
            | Q(purchase_order__vendor__institution=institution),
            deleted_at__isnull=True,
        ).select_related("bill")

        grns = self.apply_search(grns)
        grns = self.apply_ordering(grns)
        grns = self.apply_filters(grns)

        if bill_base_uuid:
            grns = grns.filter(bill__base_uuid=bill_base_uuid)

        paginator = CustomPageNumberPagination()
        paginator_qs = paginator.paginate_queryset(grns, request)
        serializer = GoodsReceivedNoteSerializer(paginator_qs, many=True)
        return paginator.get_paginated_response(serializer.data)

    @extend_schema(
        request=GoodsReceivedNoteSerializer,
        responses={201: GoodsReceivedNoteSerializer},
        description="Create a new goods received note.",
        summary="Create a new goods received note",
        tags=["Goods Received Notes Management"],
    )
    @transaction.atomic
    def post(self, request):
        serializer = GoodsReceivedNoteSerializer(
            data=request.data,
            context={"request": request},
        )

        if serializer.is_valid():
            grn = serializer.save()

            AuditLog.objects.create(
                content_type=ContentType.objects.get_for_model(GoodsReceivedNote),
                object_id=grn.pk,
                action="CREATE",
                user=request.user if request.user.is_authenticated else None,
                description=f"Created goods received note {grn.base_uuid}",
            )

            grn.confirm_create(
                profile_institution=request.profile_institution,
                external_identity=request.external_identity,
            )

            return Response(serializer.data, status=status.HTTP_201_CREATED)

        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)


class GoodsReceivedNoteDetailView(APIView):
    permission_classes = [HasInstitutionPermission]
    required_permissions = {
        "get": "can_view_goods_received_notes",
        "patch": "can_edit_goods_received_notes",
        "delete": "can_delete_goods_received_notes",
    }

    def get_object(self, request, base_uuid):
        return get_or_raise(
            queryset=GoodsReceivedNote.objects.undeleted().filter(
                Q(bill__vendor__institution=get_institution(request))
                | Q(bill__purchase_order__vendor__institution=get_institution(request))
                | Q(purchase_order__vendor__institution=get_institution(request))
                | Q(branch__institution=get_institution(request))
            ),
            message=f"Goods Received Note with UUID '{base_uuid}' not found.",
            base_uuid=base_uuid,
        )

    @extend_schema(
        responses={200: GoodsReceivedNoteSerializer},
        description="Retrieve details of a specific Goods Received Note (GRN).",
        summary="Get GRN details",
        tags=["Goods Received Notes Management"],
    )
    def get(self, request, base_uuid):
        grn = self.get_object(request, base_uuid)
        serializer = GoodsReceivedNoteSerializer(grn)
        return Response(serializer.data)

    @extend_schema(
        request=GoodsReceivedNoteSerializer,
        responses={200: GoodsReceivedNoteSerializer},
        description="Partially update a specific GRN.",
        summary="Partially update GRN details",
        tags=["Goods Received Notes Management"],
    )
    @transaction.atomic
    def patch(self, request, base_uuid):
        grn = self.get_object(request, base_uuid)

        grn.approval_status = "under_update"
        old_data = GoodsReceivedNoteSerializer(grn).data

        serializer = GoodsReceivedNoteSerializer(
            grn, data=request.data, partial=True, context={"request": request}
        )
        if serializer.is_valid():
            updated_grn = serializer.save()
            new_data = GoodsReceivedNoteSerializer(updated_grn).data

            changes = {
                key: {"old": old_data.get(key), "new": new_data.get(key)}
                for key in request.data.keys()
                if old_data.get(key) != new_data.get(key)
            }
            cleaned_changes = serialize_value(changes)

            AuditLog.objects.create(
                content_type=ContentType.objects.get_for_model(GoodsReceivedNote),
                object_id=updated_grn.id,
                action="UPDATE",
                user=request.user if request.user.is_authenticated else None,
                changes=cleaned_changes,
                description=f"Updated GRN {updated_grn.reference_code} ({updated_grn.base_uuid})",
            )

            updated_grn.confirm_update(
                profile_institution=request.profile_institution,
                external_identity=request.external_identity,
            )
            return Response(serializer.data)

        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

    @extend_schema(
        responses={204: None},
        description="Delete a specific GRN.",
        summary="Delete a GRN",
        tags=["Goods Received Notes Management"],
    )
    @transaction.atomic
    def delete(self, request, base_uuid):
        grn = self.get_object(request, base_uuid)

        grn.approval_status = "under_deletion"
        grn.save(update_fields=["approval_status"])

        grn_data = GoodsReceivedNoteSerializer(grn).data
        grn.confirm_delete(
            profile_institution=request.profile_institution,
            external_identity=request.external_identity,
        )

        AuditLog.objects.create(
            content_type=ContentType.objects.get_for_model(GoodsReceivedNote),
            object_id=grn.id,
            action="DELETE",
            user=request.user if request.user.is_authenticated else None,
            changes=grn_data,
            description=f"Deleted GRN {grn.reference_code} ({grn.base_uuid})",
        )

        return Response(status=status.HTTP_204_NO_CONTENT)


class GoodsReceivedNoteLineItemListView(APIView):
    permission_classes = [HasInstitutionPermission]
    required_permissions = {
        "get": "can_view_goods_received_notes",
    }

    @extend_schema(
        responses={
            200: inline_serializer(
                name="PaginatedGoodsReceivedNoteLineItems",
                fields={
                    "count": serializers.IntegerField(),
                    "next": serializers.URLField(allow_null=True),
                    "previous": serializers.URLField(allow_null=True),
                    "results": GoodsReceivedNoteLineItemSerializer(many=True),
                    "meta": serializers.DictField(),
                },
            ),
        },
        description="Retrieve a list of all line items for a specific goods received note.",
        summary="List all line items for a goods received note",
        tags=["Goods Received Notes Management"],
    )
    def get(self, request, base_uuid):
        goods_received_note = get_or_raise(
            queryset=GoodsReceivedNote.objects.undeleted(),
            message=f"Goods received note with UUID {base_uuid} not found.",
            base_uuid=base_uuid,
            branch__institution=get_institution(request),
        )

        search = request.query_params.get("search", "").strip()

        line_items = GoodsReceivedNoteLineItem.objects.filter(
            goods_received_note=goods_received_note,
            deleted_at__isnull=True,
        ).select_related(
            "inventory_item",
            "unit_of_measure",
            "unit_of_measure__unit_of_measure",
        )

        if search:
            line_items = line_items.filter(
                Q(inventory_item__item_name__icontains=search)
                | Q(inventory_item__reference_code__icontains=search)
            )

        paginator = CustomPageNumberPagination()
        paginated_qs = paginator.paginate_queryset(line_items, request)
        serializer = GoodsReceivedNoteLineItemSerializer(paginated_qs, many=True)
        return paginator.get_paginated_response(serializer.data)


class VendorOutstandingBalanceAdjustmentListAPIView(APIView):
    permission_classes = [HasInstitutionPermission]
    required_permissions = {
        "get": "can_view_vendor_balance_adjustments",
    }

    @extend_schema(
        responses={200: VendorOutstandingBalanceAdjustmentSerializer(many=True)},
        description="Retrieve a list of all outstanding balance adjustments for a specific vendor.",
        summary="List all outstanding balance adjustments for a vendor",
        tags=["Vendor Management"],
        parameters=[
            OpenApiParameter(
                name="balance_adjusted",
                type=str,
                description="Filter by payable or deposit balance adjustments.",
                enum=[
                    "OUTSTANDING_PAYABLE_BALANCE",
                    "DEPOSIT_BALANCE",
                ],
            ),
        ],
    )
    def get(self, request, base_uuid):
        try:
            vendor = Vendor.objects.get(base_uuid=base_uuid)
        except Vendor.DoesNotExist:
            raise SystemNotFoundError(
                detail=f"Vendor with UUID {base_uuid} not found",
                status_code=status.HTTP_404_NOT_FOUND,
            )

        adjustments = VendorOutstandingBalanceAdjustment.objects.filter(
            vendor=vendor
        ).order_by("-created_at")

        if balance_adjusted := request.query_params.get("balance_adjusted"):
            adjustments = adjustments.filter(balance_adjusted=balance_adjusted)

        paginator = CustomPageNumberPagination()
        paginated_qs = paginator.paginate_queryset(adjustments, request)

        serializer = VendorOutstandingBalanceAdjustmentSerializer(
            paginated_qs, many=True
        )

        return paginator.get_paginated_response(serializer.data)


class VendorPaymentReconcileView(APIView):
    permission_classes = [HasInstitutionPermission]
    required_permissions = {"post": "can_reconcile_vendor_payments"}

    @extend_schema(
        request=ReconcilePrepaymentSerializer,
        responses={200: "Reconciliation successful"},
        description=(
            "Allocate one or more approved prepayments against one or more approved "
            "vendor bills. The vendor is derived from the prepayments themselves — "
            "all prepayments must belong to the same vendor, and all bills must "
            "belong to that same vendor. Partial allocations are supported."
        ),
        summary="Reconcile prepayments against bills",
        tags=["Vendor Payments MGT"],
    )
    def post(self, request):
        serializer = ReconcilePrepaymentSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        data = serializer.validated_data

        reconcile_prepayments(
            prepayment_uuids=data["prepayment_uuids"],
            bill_uuids=data["bill_uuids"],
            institution=get_institution(request),
        )

        return Response(
            {
                "detail": "Reconciliation successful.",
            },
            status=status.HTTP_200_OK,
        )


class PrepaymentAllocationListView(APIView):
    permission_classes = [HasInstitutionPermission]
    required_permissions = {
        "get": "can_view_prepayment_allocations",
    }

    @extend_schema(
        responses={200: PrepaymentAllocationSerializer(many=True)},
        description="Retrieve a list of all prepayment allocations for a specific vendor.",
        summary="List all prepayment allocations for a vendor",
        tags=["Vendor Payments MGT"],
        parameters=[
            vendor_payment_base_uuid_param(required=True),
        ],
    )
    def get(self, request):

        prepayment_base_uuid = request.query_params.get(
            "vendor_payment_base_uuid", None
        )

        if not prepayment_base_uuid:
            return validation_error(
                "The 'vendor_payment_base_uuid' query parameter is required and must be a valid vendor payment UUID."
            )

        prepayment = get_object_or_404(
            VendorPayment,
            base_uuid=prepayment_base_uuid,
            institution=get_institution(request),
            deleted_at__isnull=True,
            bill__isnull=True,
        )

        allocations = PrepaymentAllocation.objects.filter(
            prepayment=prepayment,
            deleted_at__isnull=True,
        ).select_related("prepayment", "bill")

        paginator = CustomPageNumberPagination()
        paginated_qs = paginator.paginate_queryset(allocations, request)

        serializer = PrepaymentAllocationSerializer(paginated_qs, many=True)

        return paginator.get_paginated_response(serializer.data)
