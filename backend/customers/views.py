from rest_framework.views import APIView
from approval.models import Approval
from rest_framework.response import Response
from rest_framework import status
from .deposit_reconciliation import reconcile_customer_prepayments
from items.models import InventoryItem, InventoryItemUnitOfMeasure
from taxation.models import TaxApplicationBreakDown
from institution.utils import filter_queryset_by_branches
from utilities.helpers import (
    get_date_range_from_filter,
    get_institution,
    get_or_raise,
    parse_bool_query_param,
    serialize_value,
    validation_error,
)
from django.utils.dateparse import parse_date
from .serializers import (
    CreditDebitNoteSerializer,
    CreditDebitNoteLineItemSerializer,
    CustomerBalanceAdjustmentSerializer,
    CustomerPaymentSerializer,
    CustomerPurchaseOrderPaymentSerializer,
    CustomerSerializer,
    DemandNoticeSerializer,
    DepositAllocationSerializer,
    GoodsIssuedNoteLineItemSerializer,
    InvoiceLineItemSerializer,
    InvoiceLineItemListResponseSerializer,
    ItemReturnItemSerializer,
    QuotationSerializer,
    QuotationLineItemSerializer,
    CustomerPurchaseOrderLineItemSerializer,
    CustomerPurchaseOrderListSerializer,
    CustomerPurchaseOrderSerializer,
    InvoiceSerializer,
    PaymentTermSerializer,
    ReconcileCustomerPrepaymentsSerializer,
    SalesPersonSerializer,
    SalesPersonCommissionEntrySerializer,
    ItemReturnSerializer,
    RecurringInvoiceSerializer,
    RecurringInvoiceItemSerializer,
    TaxCalculationPreviewSerializer,
    GoodsIssuedNoteSerializer,
)
from .models import (
    CreditDebitNote,
    Customer,
    CustomerBalanceAdjustment,
    CustomerDepositAllocation,
    CustomerPayment,
    CustomerPurchaseOrderPayment,
    GoodsIssuedNoteLineItem,
    Quotation,
    QuotationLineItem,
    CustomerPurchaseOrder,
    CustomerPurchaseOrderLineItem,
    Invoice,
    InvoiceLineItem,
    PaymentTerm,
    SalesPerson,
    SalesPersonCommissionEntry,
    ItemReturn,
    ItemReturnItem,
    RecurringInvoice,
    RecurringInvoiceItem,
    GoodsIssuedNote,
)
from drf_spectacular.utils import extend_schema, OpenApiParameter
from audit.utils import log_action
from django.contrib.contenttypes.models import ContentType
from system.models import ForeignExchange
from utilities.pagination import CustomPageNumberPagination
from django.db.models import (
    Count,
    DecimalField,
    Exists,
    F,
    IntegerField,
    OuterRef,
    Q,
    Subquery,
    Sum,
    Value,
    Prefetch,
)
from django.db.models.functions import Coalesce
from django.core.exceptions import ObjectDoesNotExist
from customers.models import Invoice, Customer
from institution.models import Institution, InstitutionItemReturnReason
from decimal import Decimal
from django.shortcuts import get_object_or_404
from django.db import transaction

from system.exceptions import (
    SystemNotFoundError,
)
from users.permissions import HasInstitutionPermission
from utilities.openapi import (
    SEARCH_PARAM,
    ORDERING_PARAM,
    branch_uuids_param,
    customer_base_uuid_param,
    customer_payment_base_uuid_param,
    customer_purchase_order_base_uuid_param,
    return_reason_uuid_param,
    sales_person_base_uuid_param,
)
from utilities.mixin import SearchOrderMixin
from .utils import (
    get_complete_invoice_data_for_pdf,
    generate_invoice_pdf_response,
    preview_tax_for_item,
    preview_taxes,
    get_complete_quotation_data_for_pdf,
    get_complete_purchase_order_data_for_pdf,
    generate_quotation_pdf_response,
    generate_purchase_order_pdf_response,
)
from .helpers import (
    get_complete_item_return_data_for_pdf,
    generate_item_return_pdf_response,
    get_complete_credit_debit_note_data_for_pdf,
    generate_credit_debit_note_pdf_response,
)
from uuid import UUID


def scope_to_institution(queryset, institution, *lookups):
    institution_filter = Q()

    for lookup in lookups:
        institution_filter |= Q(**{lookup: institution})

    return queryset.filter(institution_filter).distinct()


class CustomerListView(SearchOrderMixin, APIView):
    queryset = Customer.objects.all()
    permission_classes = [HasInstitutionPermission]
    required_permissions = {"get": "can_view_customers", "post": "can_create_customers"}
    required_features = {"customer_management"}

    @extend_schema(
        request=CustomerSerializer,
        responses={200: CustomerSerializer(many=True)},
        description="Retrieve a list of all customers. Supports searching by customer name or other fields using the 'search' query parameter.",
        summary="List all customers",
        tags=["Customer Management"],
        parameters=[
            SEARCH_PARAM,
            ORDERING_PARAM,
            OpenApiParameter(
                name="active_without_ongoing_approval",
                type=bool,
                location=OpenApiParameter.QUERY,
                description="Return only active customers with active approval status and no ongoing approvals.",
                required=False,
            ),
            OpenApiParameter(
                name="has_invoices",
                type=bool,
                location=OpenApiParameter.QUERY,
                description="Return only customers with or without at least one invoice.",
                required=False,
            ),
            OpenApiParameter(
                name="has_credit_notes",
                type=bool,
                location=OpenApiParameter.QUERY,
                description="Return only customers with or without sales credit notes.",
                required=False,
            ),
            OpenApiParameter(
                name="has_quotations",
                type=bool,
                location=OpenApiParameter.QUERY,
                description="Return only customers with or without quotations.",
                required=False,
            ),
            OpenApiParameter(
                name="has_sales_orders",
                type=bool,
                location=OpenApiParameter.QUERY,
                description="Return only customers with or without sales orders.",
                required=False,
            ),
        ],
    )
    def get(self, request):
        institution = get_institution(request)
        active_without_ongoing_approval = parse_bool_query_param(
            request.query_params.get("active_without_ongoing_approval"),
            "active_without_ongoing_approval",
        )
        has_invoices = parse_bool_query_param(
            request.query_params.get("has_invoices"),
            "has_invoices",
        )
        has_credit_notes = parse_bool_query_param(
            request.query_params.get("has_credit_notes"),
            "has_credit_notes",
        )
        has_quotations = parse_bool_query_param(
            request.query_params.get("has_quotations"),
            "has_quotations",
        )
        has_sales_orders = parse_bool_query_param(
            request.query_params.get("has_sales_orders"),
            "has_sales_orders",
        )

        customers = Customer.objects.undeleted().filter(
            institution=institution,
        )

        if active_without_ongoing_approval is True:
            ongoing_approvals = Approval.objects.filter(
                content_type=ContentType.objects.get_for_model(Customer),
                object_id=OuterRef("pk"),
                status="ongoing",
            )
            customers = customers.filter(
                is_active=True,
                approval_status="active",
            ).filter(~Exists(ongoing_approvals))

        if has_invoices is not None:
            eligible_invoices = filter_queryset_by_branches(
                Invoice.objects.filter(deleted_at__isnull=True),
                request,
            ).filter(
                Q(customer=OuterRef("pk"))
                | Q(purchase_order__customer=OuterRef("pk"))
                | Q(purchase_order__quotation__customer=OuterRef("pk"))
                | Q(quotation__customer=OuterRef("pk"))
                | Q(recurring_invoice__customer=OuterRef("pk"))
            )

            invoice_exists = Exists(eligible_invoices)
            customers = (
                customers.filter(invoice_exists)
                if has_invoices
                else customers.filter(~invoice_exists)
            )

        if has_credit_notes is not None:
            eligible_credit_notes = filter_queryset_by_branches(
                CreditDebitNote.objects.filter(
                    type="CREDIT",
                    falls_under="SALES",
                    deleted_at__isnull=True,
                    invoice__customer=OuterRef("pk"),
                ),
                request,
            )

            credit_note_exists = Exists(eligible_credit_notes)
            customers = (
                customers.filter(credit_note_exists)
                if has_credit_notes
                else customers.filter(~credit_note_exists)
            )

        if has_quotations is not None:
            eligible_quotations = filter_queryset_by_branches(
                Quotation.objects.filter(deleted_at__isnull=True),
                request,
            ).filter(customer=OuterRef("pk"))

            quotation_exists = Exists(eligible_quotations)
            customers = (
                customers.filter(quotation_exists)
                if has_quotations
                else customers.filter(~quotation_exists)
            )

        if has_sales_orders is not None:
            eligible_sales_orders = filter_queryset_by_branches(
                CustomerPurchaseOrder.objects.filter(deleted_at__isnull=True),
                request,
            ).filter(Q(customer=OuterRef("pk")) | Q(quotation__customer=OuterRef("pk")))

            sales_order_exists = Exists(eligible_sales_orders)
            customers = (
                customers.filter(sales_order_exists)
                if has_sales_orders
                else customers.filter(~sales_order_exists)
            )

        customers = self.apply_search(customers)
        customers = self.apply_ordering(customers)

        paginator = CustomPageNumberPagination()
        paginator_qs = paginator.paginate_queryset(customers, request)
        serializer = CustomerSerializer(paginator_qs, many=True)
        return paginator.get_paginated_response(serializer.data)

    @extend_schema(
        request=CustomerSerializer,
        responses={201: CustomerSerializer},
        description="Create a new customer.",
        summary="Create a new customer",
        tags=["Customer Management"],
    )
    def post(self, request):
        serializer = CustomerSerializer(data=request.data, context={"request": request})
        if serializer.is_valid():
            customer = serializer.save()
            log_action(
                model_class=Customer,
                object_id=customer.pk,
                action="CREATE",
                user=request.user,
                description=f"Created Customer: {customer.customer_name}",
            )
            customer.confirm_create(
                profile_institution=request.profile_institution,
                external_identity=request.external_identity,
            )
            return Response(serializer.data, status=status.HTTP_201_CREATED)
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)


class CustomerDetailView(APIView):
    permission_classes = [HasInstitutionPermission]
    required_permissions = {
        "get": "can_view_customers",
        "patch": "can_edit_customers",
        "delete": "can_delete_customers",
    }
    required_features = {"customer_management"}

    def get_object(self, request, base_uuid, *, for_update=False):
        queryset = Customer.objects.filter(institution=get_institution(request))
        if for_update:
            queryset = queryset.filter(deleted_at__isnull=True).select_for_update()
        try:
            return queryset.get(base_uuid=base_uuid)
        except Customer.DoesNotExist:
            raise SystemNotFoundError(
                detail=f"Customer with UUID '{base_uuid}' not found.",
                status_code=status.HTTP_404_NOT_FOUND,
            )

    @extend_schema(
        responses={200: CustomerSerializer},
        description="Retrieve details of a specific customer.",
        summary="Get customer details",
        tags=["Customer Management"],
    )
    def get(self, request, base_uuid):
        customer = self.get_object(request, base_uuid)
        if not customer:
            return Response(status=status.HTTP_404_NOT_FOUND)

        serializer = CustomerSerializer(customer)
        return Response(serializer.data)

    @extend_schema(
        request=CustomerSerializer,
        responses={200: CustomerSerializer},
        description="Partially update details of a specific customer. If an approval workflow is configured, the update will be routed for approval.",
        summary="Partially update customer details",
        tags=["Customer Management"],
    )
    @transaction.atomic
    def patch(self, request, base_uuid):
        customer = self.get_object(request, base_uuid, for_update=True)
        if not customer:
            return Response(status=status.HTTP_404_NOT_FOUND)

        customer.ensure_changes_allowed()

        serializer_context = {"request": request}
        old_data = CustomerSerializer(customer, context=serializer_context).data

        serializer = CustomerSerializer(
            customer, data=request.data, partial=True, context=serializer_context
        )
        if serializer.is_valid():
            customer.original_data = customer.get_serializable_data()
            customer.approval_status = "under_update"
            updated_customer = serializer.save()

            new_data = CustomerSerializer(
                updated_customer, context=serializer_context
            ).data
            changes = {
                key: {"old": old_data.get(key), "new": new_data.get(key)}
                for key in request.data.keys()
                if old_data.get(key) != new_data.get(key)
            }

            log_action(
                model_class=Customer,
                object_id=updated_customer.id,
                action="UPDATE",
                user=request.user if request.user.is_authenticated else None,
                changes=changes,
                description=f"Updated customer {updated_customer.customer_name} ({updated_customer.base_uuid})",
            )

            updated_customer.confirm_update(
                profile_institution=request.profile_institution,
                external_identity=request.external_identity,
            )
            return Response(serializer.data)
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

    @transaction.atomic
    @extend_schema(
        responses={204: None},
        description="Delete a specific customer. If an approval workflow is configured, the deletion will be routed for approval.",
        summary="Delete a customer",
        tags=["Customer Management"],
    )
    def delete(self, request, base_uuid):
        customer = self.get_object(request, base_uuid, for_update=True)
        if not customer:
            return Response(status=status.HTTP_404_NOT_FOUND)

        customer.ensure_no_ongoing_approval(attempted_action="delete")

        customer_data = CustomerSerializer(customer).data
        customer_id = customer.id

        customer.confirm_delete(
            profile_institution=request.profile_institution,
            external_identity=request.external_identity,
        )

        log_action(
            model_class=Customer,
            object_id=customer_id,
            action="DELETE",
            user=request.user if request.user.is_authenticated else None,
            changes=customer_data,
            description=f"Requested deletion of customer {customer_data['customer_name']} ({base_uuid})",
        )
        return Response(status=status.HTTP_204_NO_CONTENT)


class CustomerDemandNoticeView(APIView):
    permission_classes = [HasInstitutionPermission]
    required_permissions = {"post": "can_edit_customers"}

    @extend_schema(
        request=DemandNoticeSerializer,
        description="Trigger a demand notice email to the customer listing specified invoices.",
        summary="Send demand notice email",
        tags=["Customer Management"],
    )
    def post(self, request):
        serializer = DemandNoticeSerializer(
            data=request.data,
            context={"request": request},
        )
        serializer.is_valid(raise_exception=True)

        customer = serializer.validated_data["customer"]
        invoices = serializer.validated_data["invoices"]
        institution = get_institution(request)

        if customer.institution_id != institution.id or any(
            invoice.branch.institution_id != institution.id for invoice in invoices
        ):
            raise SystemNotFoundError(
                detail="Customer or invoice not found.",
                status_code=status.HTTP_404_NOT_FOUND,
            )

        from .tasks import send_demand_notice_task

        send_demand_notice_task.delay(
            customer.id,
            invoice_ids=[inv.id for inv in invoices],
        )

        return Response(
            {
                "detail": f"Demand notice delivery initiated for {customer.customer_name}."
            },
            status=status.HTTP_200_OK,
        )


class QuotationListView(APIView, SearchOrderMixin):
    permission_classes = [HasInstitutionPermission]
    required_permissions = {
        "get": "can_view_customer_quotation",
        "post": "can_create_customer_quotation",
    }
    required_features = {"quotation_management"}

    @extend_schema(
        request=QuotationSerializer,
        responses={200: QuotationSerializer(many=True)},
        description="Retrieve a list of all quotations. Supports searching by quotation number or customer name using the 'search' query parameter.",
        summary="List all quotations",
        tags=["Quotation Management"],
        parameters=[
            SEARCH_PARAM,
            ORDERING_PARAM,
            branch_uuids_param(required=True),
            OpenApiParameter(
                name="without_purchase_order",
                type=bool,
                location=OpenApiParameter.QUERY,
                description="Return quotations without a purchase order attached to them.",
                required=False,
            ),
            OpenApiParameter(
                name="get_approved_or_draft",
                type=bool,
                location=OpenApiParameter.QUERY,
                description="Return approved or draft quotations.",
                required=False,
            ),
            OpenApiParameter(
                name="active_without_ongoing_approval",
                type=bool,
                location=OpenApiParameter.QUERY,
                description="Return only active quotations with active approval status and no ongoing approvals.",
                required=False,
            ),
        ],
    )
    def get(self, request):
        without_purchase_order = parse_bool_query_param(
            request.query_params.get("without_purchase_order"),
            "without_purchase_order",
        )
        get_approved_or_draft = parse_bool_query_param(
            request.query_params.get("get_approved_or_draft"),
            "get_approved_or_draft",
        )
        active_without_ongoing_approval = parse_bool_query_param(
            request.query_params.get("active_without_ongoing_approval"),
            "active_without_ongoing_approval",
        )

        quotations = Quotation.objects.undeleted().filter(
            customer__institution=get_institution(request)
        )

        quotations = filter_queryset_by_branches(quotations, request)

        if active_without_ongoing_approval is True:
            ongoing_approvals = Approval.objects.filter(
                content_type=ContentType.objects.get_for_model(Quotation),
                object_id=OuterRef("pk"),
                status="ongoing",
            )
            quotations = quotations.filter(
                is_active=True,
                approval_status="active",
            ).filter(~Exists(ongoing_approvals))

        if get_approved_or_draft is True:
            quotations = quotations.filter(
                status__in=[
                    "approved",
                    "draft",
                    "sent",
                ]
            )

        if without_purchase_order is True:
            quotations = quotations.annotate(
                has_po=Exists(
                    CustomerPurchaseOrder.objects.filter(quotation=OuterRef("pk"))
                )
            ).filter(has_po=False)

        quotations = self.apply_filters(quotations)
        quotations = self.apply_search(quotations)
        quotations = self.apply_ordering(quotations)

        paginator = CustomPageNumberPagination()
        paginator_qs = paginator.paginate_queryset(quotations, request)
        serializer = QuotationSerializer(paginator_qs, many=True)
        return paginator.get_paginated_response(serializer.data)

    @extend_schema(
        request=QuotationSerializer,
        responses={201: QuotationSerializer},
        description="Create a new quotation.",
        summary="Create a new quotation",
        tags=["Quotation Management"],
    )
    @transaction.atomic
    def post(self, request):
        serializer = QuotationSerializer(
            data=request.data,
            context={"request": request},
        )
        if serializer.is_valid():
            quotation = serializer.save()
            log_action(
                model_class=Quotation,
                object_id=quotation.pk,
                action="CREATE",
                user=request.user,
                description=f"Created Quotation: {quotation.reference_code}",
            )
            quotation.confirm_create(
                profile_institution=request.profile_institution,
                external_identity=request.external_identity,
            )
            return Response(serializer.data, status=status.HTTP_201_CREATED)
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)


class QuotationDetailView(APIView):
    permission_classes = [HasInstitutionPermission]
    required_permissions = {
        "get": "can_view_customer_quotation",
        "patch": "can_edit_customer_quotation",
        "delete": "can_delete_customer_quotation",
    }

    def get_object(self, request, base_uuid):
        return get_or_raise(
            queryset=scope_to_institution(
                Quotation.objects.undeleted(),
                get_institution(request),
                "branch__institution",
                "customer__institution",
            ),
            message=f"Quotation with UUID '{base_uuid}' not found.",
            base_uuid=base_uuid,
        )

    @extend_schema(
        responses={200: QuotationSerializer},
        description="Retrieve details of a specific quotation.",
        summary="Get quotation details",
        tags=["Quotation Management"],
    )
    def get(self, request, base_uuid):
        quotation = self.get_object(request, base_uuid)
        if not quotation:
            return Response(
                {"detail": "Quotation not found."}, status=status.HTTP_404_NOT_FOUND
            )
        serializer = QuotationSerializer(quotation)
        return Response(serializer.data)

    @extend_schema(
        request=QuotationSerializer,
        responses={200: QuotationSerializer},
        description="Partially update details of a specific quotation.",
        summary="Partially update quotation details",
        tags=["Quotation Management"],
    )
    @transaction.atomic
    def patch(self, request, base_uuid):
        quotation = self.get_object(request, base_uuid)
        if not quotation:
            return Response(status=status.HTTP_404_NOT_FOUND)

        quotation = Quotation.objects.select_for_update().get(pk=quotation.pk)
        quotation.ensure_no_ongoing_approval(attempted_action="update")

        old_data = QuotationSerializer(quotation).data

        serializer = QuotationSerializer(
            quotation, data=request.data, partial=True, context={"request": request}
        )
        if serializer.is_valid():
            quotation.approval_status = "under_update"
            updated_quotation = serializer.save()
            new_data = QuotationSerializer(updated_quotation).data
            changes = {
                key: {
                    "old": serialize_value(old_data.get(key)),
                    "new": serialize_value(new_data.get(key)),
                }
                for key in request.data.keys()
                if old_data.get(key) != new_data.get(key)
            }
            log_action(
                model_class=Quotation,
                object_id=updated_quotation.id,
                action="UPDATE",
                user=request.user if request.user.is_authenticated else None,
                changes=changes,
                description=f"Updated quotation {updated_quotation.reference_code} ({updated_quotation.base_uuid})",
            )
            updated_quotation.confirm_update(
                profile_institution=request.profile_institution,
                external_identity=request.external_identity,
            )
            return Response(serializer.data)
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

    @extend_schema(
        responses={204: None},
        description="Delete a specific quotation.",
        summary="Delete a quotation",
        tags=["Quotation Management"],
    )
    @transaction.atomic
    def delete(self, request, base_uuid):
        quotation = self.get_object(request, base_uuid)
        if not quotation:
            return Response(status=status.HTTP_404_NOT_FOUND)

        quotation = Quotation.objects.select_for_update().get(pk=quotation.pk)
        quotation_data = QuotationSerializer(quotation).data
        quotation_id = quotation.id
        quotation.confirm_delete(
            profile_institution=request.profile_institution,
            external_identity=request.external_identity,
        )
        log_action(
            model_class=Quotation,
            object_id=quotation_id,
            action="DELETE",
            user=request.user if request.user.is_authenticated else None,
            changes=serialize_value(quotation_data),
            description=f"Requested deletion of quotation {quotation_data['reference_code']} ({base_uuid})",
        )
        return Response(status=status.HTTP_204_NO_CONTENT)


class QuotationLineItemListView(APIView, SearchOrderMixin):
    permission_classes = [HasInstitutionPermission]
    required_permissions = {
        "get": "can_view_customer_quotation_line_item",
        "post": "can_create_customer_quotation_line_item",
    }

    def _get_quotation(self, request, quotation_base_uuid):
        return get_or_raise(
            queryset=scope_to_institution(
                Quotation.objects.undeleted(),
                get_institution(request),
                "branch__institution",
                "customer__institution",
            ),
            message=f"Quotation with UUID '{quotation_base_uuid}' not found.",
            base_uuid=quotation_base_uuid,
        )

    @extend_schema(
        request=QuotationLineItemSerializer,
        responses={200: QuotationLineItemSerializer(many=True)},
        description="Retrieve a list of all quotation line items for a specific quotation.",
        summary="List all quotation line items",
        parameters=[
            SEARCH_PARAM,
            ORDERING_PARAM,
        ],
        tags=["Quotation Line Item Management"],
    )
    def get(self, request, quotation_base_uuid):
        quotation = self._get_quotation(request, quotation_base_uuid)
        line_items = QuotationLineItem.objects.filter(quotation=quotation)
        line_items = self.apply_search(line_items)
        line_items = self.apply_ordering(line_items)

        paginator = CustomPageNumberPagination()
        paginator_qs = paginator.paginate_queryset(line_items, request)
        serializer = QuotationLineItemSerializer(paginator_qs, many=True)
        return paginator.get_paginated_response(serializer.data)


class QuotationLineItemDetailView(APIView):

    permission_classes = [HasInstitutionPermission]
    required_permissions = {
        "get": "can_view_customer_quotation_line_item",
        "patch": "can_edit_customer_quotation_line_item",
        "delete": "can_delete_customer_quotation_line_item",
    }

    def get_object(self, request, base_uuid):
        return get_or_raise(
            queryset=scope_to_institution(
                QuotationLineItem.objects.all(),
                get_institution(request),
                "quotation__branch__institution",
                "quotation__customer__institution",
            ),
            message=f"Quotation Item with UUID '{base_uuid}' not found.",
            base_uuid=base_uuid,
        )

    @extend_schema(
        responses={200: QuotationLineItemSerializer},
        description="Retrieve details of a specific quotation line item.",
        summary="Get quotation line item details",
        tags=["Quotation Line Item Management"],
    )
    def get(self, request, base_uuid):
        line_item = self.get_object(request, base_uuid)
        if not line_item:
            return Response(status=status.HTTP_404_NOT_FOUND)
        serializer = QuotationLineItemSerializer(line_item)
        return Response(serializer.data)

    @extend_schema(
        request=QuotationLineItemSerializer,
        responses={200: QuotationLineItemSerializer},
        description="Partially update details of a specific quotation line item.",
        summary="Partially update quotation line item details",
        tags=["Quotation Line Item Management"],
    )
    def patch(self, request, base_uuid):
        line_item = self.get_object(request, base_uuid)
        if not line_item:
            return Response(status=status.HTTP_404_NOT_FOUND)

        old_data = QuotationLineItemSerializer(line_item).data
        serializer = QuotationLineItemSerializer(
            line_item, data=request.data, partial=True
        )
        if serializer.is_valid():
            updated_line_item = serializer.save()
            new_data = QuotationLineItemSerializer(updated_line_item).data
            changes = {
                key: {"old": old_data.get(key), "new": new_data.get(key)}
                for key in request.data.keys()
                if old_data.get(key) != new_data.get(key)
            }
            log_action(
                model_class=QuotationLineItem,
                object_id=updated_line_item.id,
                action="UPDATE",
                user=request.user if request.user.is_authenticated else None,
                changes=changes,
                description=f"Updated quotation line item for Quotation {updated_line_item.quotation.reference_code} ({updated_line_item.base_uuid})",
            )
            return Response(serializer.data)
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

    @extend_schema(
        responses={204: None},
        description="Delete a specific quotation line item.",
        summary="Delete a quotation line item",
        tags=["Quotation Line Item Management"],
    )
    def delete(self, request, base_uuid):
        line_item = self.get_object(request, base_uuid)
        if not line_item:
            return Response(status=status.HTTP_404_NOT_FOUND)

        line_item_data = QuotationLineItemSerializer(line_item).data
        line_item_id = line_item.id
        line_item.delete()
        log_action(
            model_class=QuotationLineItem,
            object_id=line_item_id,
            action="DELETE",
            user=request.user if request.user.is_authenticated else None,
            changes=line_item_data,
            description=f"Deleted quotation line item for Quotation {line_item_data['quotation']['reference_code']} ({base_uuid})",
        )
        return Response(status=status.HTTP_204_NO_CONTENT)


class CustomerPurchaseOrderListView(APIView, SearchOrderMixin):
    permission_classes = [HasInstitutionPermission]
    required_permissions = {
        "get": "can_view_customer_purchase_orders",
        "post": "can_create_customer_purchase_orders",
    }
    required_features = {"sales_orders"}

    queryset = CustomerPurchaseOrder.objects.undeleted()

    @extend_schema(
        request=CustomerPurchaseOrderSerializer,
        responses={200: CustomerPurchaseOrderListSerializer(many=True)},
        description="Retrieve a list of all purchase orders. Supports searching by purchase order number or customer name using the 'search' query parameter.",
        summary="List all purchase orders",
        tags=["Purchase Order Management"],
        parameters=[
            SEARCH_PARAM,
            ORDERING_PARAM,
            branch_uuids_param(required=True),
            OpenApiParameter(
                name="status",
                type=str,
                location=OpenApiParameter.QUERY,
                description="Filter purchase orders by status (draft, approved, completed, canceled)",
                required=False,
            ),
            OpenApiParameter(
                name="line_item_base_uuid",
                type=str,
                location=OpenApiParameter.QUERY,
                description="Filter purchase orders by the Base UUID of a contained line item (inventory item/service).",
                required=False,
            ),
            OpenApiParameter(
                name="get_only_not_full_issued",
                type=bool,
                location=OpenApiParameter.QUERY,
                description="Filter sales orders that are not fully issued.",
                required=False,
            ),
            OpenApiParameter(
                name="get_only_not_full_invoiced",
                type=bool,
                location=OpenApiParameter.QUERY,
                description="Filter purchase orders that are not fully invoiced (not_invoiced or partially_invoiced).",
                required=False,
            ),
            OpenApiParameter(
                name="has_returnable_items",
                type=bool,
                location=OpenApiParameter.QUERY,
                description="Return only GINs with or without returnable quantities.",
                required=False,
            ),
        ],
    )
    def get(self, request):
        get_only_not_full_issued = str(
            request.query_params.get("get_only_not_full_issued", False)
        ).lower() in ("true", "1", "t", "yes")
        get_only_not_full_invoiced = str(
            request.query_params.get("get_only_not_full_invoiced", False)
        ).lower() in ("true", "1", "t", "yes")
        status_filter = request.query_params.get("status", None)

        line_item_uuid_filter = request.query_params.get("line_item_base_uuid", None)

        purchase_orders = (
            scope_to_institution(
                CustomerPurchaseOrder.objects.undeleted(),
                get_institution(request),
                "branch__institution",
                "customer__institution",
                "quotation__branch__institution",
                "quotation__customer__institution",
            )
            .select_related(
                "branch__institution__currency",
                "customer",
                "quotation__customer",
            )
            .annotate(
                line_items_count=Count(
                    "line_items",
                    filter=Q(line_items__deleted_at__isnull=True),
                    distinct=True,
                ),
                annotated_total_price=Coalesce(
                    Sum(
                        "line_items__line_total",
                        filter=Q(line_items__deleted_at__isnull=True),
                    ),
                    Value(0),
                    output_field=DecimalField(max_digits=50, decimal_places=20),
                ),
            )
        )

        if get_only_not_full_issued:
            purchase_orders = (
                purchase_orders.exclude(goods_issued_note_status="not_required")
                .filter(
                    goods_issued_note_status__in=["not_issued", "partially_issued"],
                    line_items__line_item__inventory_item__item_type="GOODS",
                    line_items__deleted_at__isnull=True,
                )
                .distinct()
            )

        if get_only_not_full_invoiced:
            purchase_orders = purchase_orders.filter(
                invoice_status__in=["not_invoiced", "partially_invoiced"]
            )

        purchase_orders = filter_queryset_by_branches(purchase_orders, request)

        if (
            parse_bool_query_param(
                request.query_params.get("active_without_ongoing_approval"),
                "active_without_ongoing_approval",
            )
            is True
        ):
            ongoing_approvals = Approval.objects.filter(
                content_type=ContentType.objects.get_for_model(CustomerPurchaseOrder),
                object_id=OuterRef("pk"),
                status="ongoing",
            )
            purchase_orders = purchase_orders.filter(
                is_active=True,
                approval_status="active",
            ).filter(~Exists(ongoing_approvals))

        if line_item_uuid_filter:
            purchase_orders = purchase_orders.filter(
                line_items__line_item__base_uuid__exact=line_item_uuid_filter
            ).distinct()

        if status_filter:
            purchase_orders = purchase_orders.filter(status=status_filter)

        purchase_orders = self.apply_filters(purchase_orders)
        purchase_orders = self.apply_search(purchase_orders)
        purchase_orders = self.apply_ordering(purchase_orders)

        paginator = CustomPageNumberPagination()
        paginator_qs = paginator.paginate_queryset(purchase_orders, request)

        order_ids = [purchase_order.id for purchase_order in paginator_qs]
        content_type = ContentType.objects.get_for_model(CustomerPurchaseOrder)
        exchange_rates = {}

        for exchange_rate in (
            ForeignExchange.objects.filter(
                content_type=content_type,
                object_id__in=order_ids,
            )
            .select_related("to_currency")
            .order_by("object_id", "-created_at")
        ):
            exchange_rates.setdefault(exchange_rate.object_id, exchange_rate)

        serializer = CustomerPurchaseOrderListSerializer(
            paginator_qs,
            many=True,
            context={"exchange_rates": exchange_rates},
        )
        return paginator.get_paginated_response(serializer.data)

    @extend_schema(
        request=CustomerPurchaseOrderSerializer,
        responses={201: CustomerPurchaseOrderSerializer},
        description="Create a new purchase order.",
        summary="Create a new purchase order",
        tags=["Purchase Order Management"],
    )
    @transaction.atomic
    def post(self, request):
        serializer = CustomerPurchaseOrderSerializer(
            data=request.data,
            context={"request": request},
        )
        if serializer.is_valid():
            purchase_order = serializer.save()

            log_action(
                model_class=CustomerPurchaseOrder,
                object_id=purchase_order.pk,
                action="CREATE",
                user=request.user if request.user.is_authenticated else None,
                description=f"Created Purchase Order: {purchase_order.reference_code}",
            )

            purchase_order.confirm_create(
                profile_institution=request.profile_institution,
                external_identity=request.external_identity,
            )

            return Response(serializer.data, status=status.HTTP_201_CREATED)

        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)


class CustomerPurchaseOrderLineItemListView(APIView, SearchOrderMixin):
    permission_classes = [HasInstitutionPermission]
    required_permissions = {
        "get": "can_view_customer_purchase_orders",
    }
    required_features = {"sales_orders"}

    @extend_schema(
        responses={200: CustomerPurchaseOrderLineItemSerializer(many=True)},
        description="List the line items belonging to a specific sales order.",
        summary="List sales order line items",
        tags=["Purchase Order Management"],
        parameters=[SEARCH_PARAM, ORDERING_PARAM],
    )
    def get(self, request, base_uuid):
        purchase_orders = filter_queryset_by_branches(
            CustomerPurchaseOrder.objects.undeleted().filter(
                base_uuid=base_uuid,
            ),
            request,
        )
        purchase_order = get_object_or_404(purchase_orders)

        billed_quantity = (
            InvoiceLineItem.objects.undeleted()
            .filter(
                invoice__purchase_order=purchase_order,
                line_item_id=OuterRef("line_item_id"),
            )
            .values("line_item_id")
            .annotate(total=Sum("quantity"))
            .values("total")[:1]
        )

        line_items = (
            CustomerPurchaseOrderLineItem.objects.undeleted()
            .filter(
                purchase_order=purchase_order,
            )
            .select_related(
                "purchase_order",
                "line_item__branch",
                "line_item__inventory_item__item_category",
                "unit_of_measure__unit_of_measure",
            )
            .annotate(
                annotated_quantity_billed=Coalesce(
                    Subquery(
                        billed_quantity,
                        output_field=DecimalField(max_digits=50, decimal_places=20),
                    ),
                    Value(0),
                    output_field=DecimalField(max_digits=50, decimal_places=20),
                )
            )
        )

        line_items = self.apply_search(line_items)
        line_items = self.apply_ordering(line_items)

        paginator = CustomPageNumberPagination()
        page = paginator.paginate_queryset(line_items, request)
        serializer = CustomerPurchaseOrderLineItemSerializer(page, many=True)
        return paginator.get_paginated_response(serializer.data)


class CustomerPurchaseOrderDetailView(APIView):
    permission_classes = [HasInstitutionPermission]
    required_permissions = {
        "get": "can_view_customer_purchase_orders",
        "patch": "can_edit_customer_purchase_orders",
        "delete": "can_delete_customer_purchase_orders",
    }
    required_features = {"sales_orders"}

    def get_object(self, request, base_uuid):
        return get_or_raise(
            queryset=scope_to_institution(
                CustomerPurchaseOrder.objects.undeleted(),
                get_institution(request),
                "branch__institution",
                "customer__institution",
                "quotation__branch__institution",
                "quotation__customer__institution",
            ),
            message=f"Customer purchase order with UUID {base_uuid} not found.",
            base_uuid=base_uuid,
        )

    @extend_schema(
        responses={200: CustomerPurchaseOrderSerializer},
        description="Retrieve details of a specific purchase order.",
        summary="Get purchase order details",
        tags=["Purchase Order Management"],
    )
    def get(self, request, base_uuid):
        purchase_order = self.get_object(request, base_uuid)
        if not purchase_order:
            return Response(status=status.HTTP_404_NOT_FOUND)
        serializer = CustomerPurchaseOrderSerializer(purchase_order)
        return Response(serializer.data)

    @extend_schema(
        request=CustomerPurchaseOrderSerializer,
        responses={200: CustomerPurchaseOrderSerializer},
        description="Partially update details of a specific purchase order.",
        summary="Partially update purchase order details",
        tags=["Purchase Order Management"],
    )
    @transaction.atomic
    def patch(self, request, base_uuid):
        purchase_order = self.get_object(request, base_uuid)
        if not purchase_order:
            return Response(status=status.HTTP_404_NOT_FOUND)

        purchase_order = CustomerPurchaseOrder.objects.select_for_update().get(
            pk=purchase_order.pk
        )
        purchase_order.ensure_no_ongoing_approval(attempted_action="update")
        old_data = CustomerPurchaseOrderSerializer(purchase_order).data
        serializer = CustomerPurchaseOrderSerializer(
            purchase_order,
            data=request.data,
            partial=True,
            context={"request": request},
        )
        if serializer.is_valid():
            purchase_order.approval_status = "under_update"
            updated_purchase_order = serializer.save()
            new_data = CustomerPurchaseOrderSerializer(updated_purchase_order).data
            changes = {
                key: {
                    "old": serialize_value(old_data.get(key)),
                    "new": serialize_value(new_data.get(key)),
                }
                for key in request.data.keys()
                if old_data.get(key) != new_data.get(key)
            }
            log_action(
                model_class=CustomerPurchaseOrder,
                object_id=updated_purchase_order.id,
                action="UPDATE",
                user=request.user if request.user.is_authenticated else None,
                changes=changes,
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
        summary="Delete a purchase order",
        tags=["Purchase Order Management"],
    )
    @transaction.atomic
    def delete(self, request, base_uuid):
        purchase_order = self.get_object(request, base_uuid)
        if not purchase_order:
            return Response(status=status.HTTP_404_NOT_FOUND)

        purchase_order = CustomerPurchaseOrder.objects.select_for_update().get(
            pk=purchase_order.pk
        )
        purchase_order_data = CustomerPurchaseOrderSerializer(purchase_order).data
        purchase_order_id = purchase_order.id
        purchase_order.confirm_delete(
            profile_institution=request.profile_institution,
            external_identity=request.external_identity,
        )
        log_action(
            model_class=CustomerPurchaseOrder,
            object_id=purchase_order_id,
            action="DELETE",
            user=request.user if request.user.is_authenticated else None,
            changes=serialize_value(purchase_order_data),
            description=f"Requested deletion of purchase order {purchase_order_data['reference_code']} ({base_uuid})",
        )
        return Response(status=status.HTTP_204_NO_CONTENT)


class CustomerPurchaseOrderPaymentListCreateView(APIView, SearchOrderMixin):
    permission_classes = [HasInstitutionPermission]
    required_permissions = {
        "get": "can_view_customer_purchase_order_payments",
        "post": "can_create_customer_purchase_order_payments",
    }
    required_features = {"sales_orders"}

    @extend_schema(
        request=CustomerPurchaseOrderPaymentSerializer,
        responses={200: CustomerPurchaseOrderPaymentSerializer(many=True)},
        description="Retrieve a list of all payments",
        parameters=[
            SEARCH_PARAM,
            ORDERING_PARAM,
            branch_uuids_param(required=True),
            customer_purchase_order_base_uuid_param(required=False),
        ],
    )
    def get(self, request):
        institution = get_institution(request)

        customer_purchase_order_base_uuid = request.query_params.get(
            "customer_purchase_order_base_uuid", None
        )

        payments = CustomerPurchaseOrderPayment.objects.undeleted().filter(
            Q(sales_order__customer__institution=institution)
            | Q(sales_order__quotation__customer__institution=institution)
            | Q(sales_order__quotation__branch__institution=institution)
            | Q(sales_order__branch__institution=institution)
        )

        if customer_purchase_order_base_uuid:
            sales_order = get_or_raise(
                queryset=scope_to_institution(
                    CustomerPurchaseOrder.objects.undeleted(),
                    institution,
                    "branch__institution",
                    "customer__institution",
                    "quotation__branch__institution",
                    "quotation__customer__institution",
                ),
                message=f"Customer Purchase Order with base UUID '{customer_purchase_order_base_uuid}' not found.",
                base_uuid=customer_purchase_order_base_uuid,
            )

            payments = payments.filter(sales_order=sales_order)

        payments = self.apply_search(payments)
        payments = self.apply_ordering(payments)

        paginator = CustomPageNumberPagination()
        paginated_qs = paginator.paginate_queryset(payments, request)
        serializer = CustomerPurchaseOrderPaymentSerializer(
            paginated_qs, many=True, context={"request": request}
        )
        return paginator.get_paginated_response(serializer.data)

    @extend_schema(
        request=CustomerPurchaseOrderPaymentSerializer,
        responses={200: CustomerPurchaseOrderPaymentSerializer},
        description="Create a new sales order payment",
        parameters=[
            customer_purchase_order_base_uuid_param(required=True),
        ],
    )
    def post(self, request):
        institution = get_institution(request)

        purchase_order_base_uuid = request.query_params.get(
            "customer_purchase_order_base_uuid"
        )

        if not purchase_order_base_uuid:
            raise validation_error(
                {
                    "customer_purchase_order_base_uuid": (
                        "Customer purchase order is required."
                    )
                }
            )

        purchase_order = get_or_raise(
            queryset=CustomerPurchaseOrder.objects.undeleted().filter(
                Q(customer__institution=institution)
                | Q(quotation__customer__institution=institution)
                | Q(quotation__branch__institution=institution)
                | Q(branch__institution=institution)
            ),
            message=(
                "Customer Purchase Order with base UUID "
                f"'{purchase_order_base_uuid}' was not found."
            ),
            base_uuid=purchase_order_base_uuid,
        )

        serializer = CustomerPurchaseOrderPaymentSerializer(
            data=request.data,
            context={
                "request": request,
                "purchase_order": purchase_order,
            },
        )
        serializer.is_valid(raise_exception=True)

        payment = serializer.save()

        payment.confirm_create(
            profile_institution=request.profile_institution,
            external_identity=request.external_identity,
        )

        return Response(
            CustomerPurchaseOrderPaymentSerializer(
                payment,
                context={"request": request},
            ).data,
            status=status.HTTP_201_CREATED,
        )


class InvoiceListView(SearchOrderMixin, APIView):
    queryset = Invoice.objects.all()

    permission_classes = [HasInstitutionPermission]
    required_permissions = {
        "get": "can_view_customer_invoices",
        "post": "can_create_customer_invoices",
    }

    @extend_schema(
        request=InvoiceSerializer,
        responses={200: InvoiceSerializer(many=True)},
        description="Retrieve a list of all invoices. Supports searching by invoice number or customer name using the 'search' query parameter.",
        summary="List all invoices",
        tags=["Invoice Management"],
        parameters=[
            SEARCH_PARAM,
            ORDERING_PARAM,
            customer_base_uuid_param(required=False),
            sales_person_base_uuid_param(required=False),
            branch_uuids_param(required=True),
            OpenApiParameter(
                name="returned",
                type=bool,
                location=OpenApiParameter.QUERY,
                description="Filter invoices tied to a item return.",
                required=False,
            ),
            OpenApiParameter(
                name="filter_out_fully_paid_invoices",
                type=bool,
                location=OpenApiParameter.QUERY,
                description="Filters invoices to return only those that are unpaid or partially paid.",
                required=False,
            ),
            OpenApiParameter(
                name="is_recurring",
                type=bool,
                location=OpenApiParameter.QUERY,
                description="Filter invoices that belong to a recurring invoice",
                required=False,
            ),
            OpenApiParameter(
                name="get_only_not_full_issued",
                type=bool,
                location=OpenApiParameter.QUERY,
                description="Filter invoices that are not fully issued.",
                required=False,
            ),
            OpenApiParameter(
                name="get_only_not_full_invoiced",
                type=bool,
                location=OpenApiParameter.QUERY,
                description="Filter invoices that are not fully invoiced (unpaid or partially paid).",
                required=False,
            ),
        ],
    )
    def get(self, request):
        try:
            invoice_on_return_item = request.query_params.get("returned", None)
            customer_base_uuid = request.query_params.get("customer_base_uuid", None)
            sales_person_base_uuid = request.query_params.get(
                "sales_person_base_uuid", None
            )
            filter_out_fully_paid_invoices = str(
                request.query_params.get("filter_out_fully_paid_invoices", False)
            ).lower() in ("true", "1", "t", "yes")
            is_recurring = request.query_params.get("is_recurring", None)
            get_only_not_full_issued = str(
                request.query_params.get("get_only_not_full_issued", False)
            ).lower() in ("true", "1", "t", "yes")
            get_only_not_full_invoiced = str(
                request.query_params.get("get_only_not_fully_invoiced", False)
            ).lower() in ("true", "1", "t", "yes")

            if is_recurring is not None:
                is_recurring = str(is_recurring).lower() in ("true", "1", "t", "yes")

            invoices = scope_to_institution(
                Invoice.objects.filter(deleted_at__isnull=True),
                get_institution(request),
                "branch__institution",
                "customer__institution",
                "quotation__branch__institution",
                "quotation__customer__institution",
                "purchase_order__branch__institution",
                "purchase_order__customer__institution",
                "purchase_order__quotation__branch__institution",
                "purchase_order__quotation__customer__institution",
                "recurring_invoice__branch__institution",
                "recurring_invoice__customer__institution",
                "sales_person__institution",
            ).order_by("-created_at")
            invoices = filter_queryset_by_branches(invoices, request)

            if filter_out_fully_paid_invoices:
                invoices = invoices.exclude(invoice_status="canceled").filter(
                    invoice_payment_status__in=["unpaid", "partially_paid"],
                    amount_due__gt=0,
                )

            if get_only_not_full_issued:
                invoices = (
                    invoices.exclude(goods_issued_note_status="not_required")
                    .filter(
                        goods_issued_note_status__in=[
                            "not_issued",
                            "partially_issued",
                        ],
                        line_items__line_item__inventory_item__item_type="GOODS",
                        line_items__deleted_at__isnull=True,
                    )
                    .distinct()
                )

            if get_only_not_full_invoiced:
                invoices = invoices.filter(
                    invoice_payment_status__in=["unpaid", "partially_paid"]
                )

            if customer_base_uuid:
                customer = get_object_or_404(
                    Customer,
                    base_uuid=customer_base_uuid,
                    institution=get_institution(request),
                )
                invoices = invoices.filter(
                    Q(customer=customer)
                    | Q(purchase_order__customer=customer)
                    | Q(purchase_order__quotation__customer=customer)
                    | Q(quotation__customer=customer)
                    | Q(recurring_invoice__customer=customer)
                )

            if sales_person_base_uuid:
                sales_person = get_or_raise(
                    queryset=SalesPerson.objects.undeleted(),
                    message=f"Sales person with base UUID '{sales_person_base_uuid}' not found.",
                    base_uuid=sales_person_base_uuid,
                    institution=get_institution(request),
                )
                invoices = invoices.filter(sales_person=sales_person)

            if invoice_on_return_item:
                invoices = invoices.filter(item_return__isnull=True)

            if is_recurring is not None:
                if is_recurring:
                    invoices = invoices.filter(recurring_invoice__isnull=False)

                else:
                    invoices = invoices.filter(recurring_invoice__isnull=True)

            invoices = self.apply_filters(invoices)
            invoices = self.apply_search(invoices)
            invoices = self.apply_ordering(invoices)

            paginator = CustomPageNumberPagination()
            paginator_qs = paginator.paginate_queryset(invoices, request)
            serializer = InvoiceSerializer(paginator_qs, many=True)
            return paginator.get_paginated_response(serializer.data)

        except ObjectDoesNotExist:
            raise SystemNotFoundError(
                detail="Error fetching Invoices", status_code=status.HTTP_404_NOT_FOUND
            )

    @extend_schema(
        request=InvoiceSerializer,
        responses={201: InvoiceSerializer},
        description="Create a new invoice.",
        summary="Create a new invoice",
        tags=["Invoice Management"],
    )
    @transaction.atomic()
    def post(self, request):
        serializer = InvoiceSerializer(
            data=request.data,
            context={"request": request},
        )
        if serializer.is_valid():
            invoice = serializer.save()
            log_action(
                model_class=Invoice,
                object_id=invoice.pk,
                action="CREATE",
                user=request.user,
                description=f"Created Invoice: {invoice.reference_code}",
            )
            invoice.confirm_create(
                profile_institution=request.profile_institution,
                external_identity=request.external_identity,
            )
            return Response(serializer.data, status=status.HTTP_201_CREATED)
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)


class InvoiceDetailView(APIView):
    permission_classes = [HasInstitutionPermission]
    required_permissions = {
        "get": "can_view_customer_invoices",
        "patch": "can_edit_customer_invoices",
        "delete": "can_delete_customer_invoices",
    }

    def get_object(self, request, base_uuid):
        return get_or_raise(
            queryset=scope_to_institution(
                Invoice.objects.filter(deleted_at__isnull=True),
                get_institution(request),
                "branch__institution",
                "customer__institution",
                "quotation__branch__institution",
                "quotation__customer__institution",
                "purchase_order__branch__institution",
                "purchase_order__customer__institution",
                "purchase_order__quotation__branch__institution",
                "purchase_order__quotation__customer__institution",
                "recurring_invoice__branch__institution",
                "recurring_invoice__customer__institution",
                "sales_person__institution",
            ),
            message=f"Invoice with UUID '{base_uuid}' not found.",
            base_uuid=base_uuid,
        )

    @extend_schema(
        responses={200: InvoiceSerializer},
        description="Retrieve details of a specific invoice.",
        summary="Get invoice details",
        tags=["Invoice Management"],
    )
    def get(self, request, base_uuid):
        invoice = self.get_object(request, base_uuid)
        if not invoice:
            return Response(status=status.HTTP_404_NOT_FOUND)
        serializer = InvoiceSerializer(invoice)
        return Response(serializer.data)

    @extend_schema(
        request=InvoiceSerializer,
        responses={200: InvoiceSerializer},
        description="Partially update details of a specific invoice.",
        summary="Partially update invoice details",
        tags=["Invoice Management"],
    )
    def patch(self, request, base_uuid):
        with transaction.atomic():
            invoice = self.get_object(request, base_uuid)
            if not invoice:
                return Response(status=status.HTTP_404_NOT_FOUND)
            invoice = Invoice.objects.select_for_update().get(pk=invoice.pk)
            invoice.ensure_no_ongoing_approval(attempted_action="update")
            invoice.approval_status = "under_update"
            old_data = InvoiceSerializer(invoice).data
            serializer = InvoiceSerializer(
                invoice, data=request.data, partial=True, context={"request": request}
            )
            if serializer.is_valid():
                updated_invoice = serializer.save()
                new_data = InvoiceSerializer(updated_invoice).data
                changes = {
                    key: {
                        "old": serialize_value(old_data.get(key)),
                        "new": serialize_value(new_data.get(key)),
                    }
                    for key in request.data.keys()
                    if old_data.get(key) != new_data.get(key)
                }
                log_action(
                    model_class=Invoice,
                    object_id=updated_invoice.id,
                    action="UPDATE",
                    user=request.user if request.user.is_authenticated else None,
                    changes=changes,
                    description=f"Updated invoice {updated_invoice.reference_code} ({updated_invoice.base_uuid})",
                )
                updated_invoice.confirm_update(
                    profile_institution=request.profile_institution,
                    external_identity=request.external_identity,
                )
                return Response(serializer.data)
            return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

    @extend_schema(
        responses={204: None},
        description="Delete a specific invoice.",
        summary="Delete a invoice",
        tags=["Invoice Management"],
    )
    @transaction.atomic
    def delete(self, request, base_uuid):
        invoice = self.get_object(request, base_uuid)
        if not invoice:
            return Response(status=status.HTTP_404_NOT_FOUND)

        invoice = Invoice.objects.select_for_update().get(pk=invoice.pk)

        invoice_data = InvoiceSerializer(invoice).data
        invoice_id = invoice.id
        invoice.confirm_delete(
            profile_institution=request.profile_institution,
            external_identity=request.external_identity,
        )
        log_action(
            model_class=Invoice,
            object_id=invoice_id,
            action="DELETE",
            user=request.user if request.user.is_authenticated else None,
            changes=serialize_value(invoice_data),
            description=f"Deleted invoice {invoice_data['reference_code']} ({base_uuid})",
        )
        return Response(status=status.HTTP_204_NO_CONTENT)


class InvoiceLineItemListView(APIView, SearchOrderMixin):
    permission_classes = [HasInstitutionPermission]
    required_permissions = {
        "get": "can_view_customer_invoices",
    }
    queryset = InvoiceLineItem.objects.undeleted()

    def _get_invoice(self, request, invoice_base_uuid):
        return get_or_raise(
            Invoice.objects.undeleted(),
            message=f"Invoice with base UUID '{invoice_base_uuid}' not found.",
            base_uuid=invoice_base_uuid,
            branch__institution=get_institution(request),
        )

    def _get_line_items(self, invoice):
        unit_queryset = InventoryItemUnitOfMeasure.objects.undeleted().select_related(
            "unit_of_measure"
        )

        return (
            self.queryset.filter(invoice=invoice)
            .select_related(
                "line_item",
                "line_item__inventory_item",
                "line_item__inventory_item__item_category",
                "unit_of_measure",
                "unit_of_measure__unit_of_measure",
            )
            .prefetch_related(
                Prefetch(
                    "line_item__inventory_item__units",
                    queryset=unit_queryset,
                )
            )
        )

    @extend_schema(
        responses={200: InvoiceLineItemListResponseSerializer},
        description="Retrieve a list of all invoice line items for a specific invoice.",
        summary="List all invoice line items by invoice",
        tags=["Invoice Management"],
        parameters=[
            SEARCH_PARAM,
            ORDERING_PARAM,
            OpenApiParameter(
                name="exclude_returned_items",
                type=bool,
                location=OpenApiParameter.QUERY,
                description="Exclude invoice lines connected to approved item returns.",
                required=False,
            ),
        ],
    )
    def get(self, request, invoice_base_uuid):
        invoice = self._get_invoice(request, invoice_base_uuid)

        line_items = self._get_line_items(invoice)

        exclude_returned_items = parse_bool_query_param(
            request.query_params.get("exclude_returned_items"),
            "exclude_returned_items",
        )

        if exclude_returned_items:
            approved_returns = ItemReturnItem.objects.filter(
                Q(
                    goods_issued_note_line__source_invoice_line=OuterRef("pk"),
                )
                | Q(
                    goods_issued_note_line__source_purchase_order_line=OuterRef(
                        "source_purchase_order_line_id"
                    ),
                    goods_issued_note_line__source_purchase_order_line__isnull=False,
                ),
                item_return__return_status="APPROVED",
                item_return__are_initial_journal_entries_made=True,
                item_return__deleted_at__isnull=True,
                deleted_at__isnull=True,
            )

            line_items = line_items.annotate(
                has_approved_return=Exists(approved_returns),
            ).filter(has_approved_return=False)

        line_items = self.apply_filters(line_items)
        line_items = self.apply_search(line_items)
        line_items = self.apply_ordering(line_items)

        paginator = CustomPageNumberPagination()
        paginator_qs = paginator.paginate_queryset(line_items, request)

        line_item_content_type = ContentType.objects.get_for_model(InvoiceLineItem)
        tax_breakdowns_by_line_id = {}

        tax_breakdowns = (
            TaxApplicationBreakDown.objects.undeleted()
            .filter(
                content_type=line_item_content_type,
                object_id__in=[item.id for item in paginator_qs],
            )
            .select_related("tax")
        )

        for tax_breakdown in tax_breakdowns:
            tax_breakdowns_by_line_id.setdefault(
                tax_breakdown.object_id,
                [],
            ).append(tax_breakdown)

        serializer = InvoiceLineItemSerializer(
            paginator_qs,
            many=True,
            context={
                "request": request,
                "tax_breakdowns_by_line_id": tax_breakdowns_by_line_id,
            },
        )
        return paginator.get_paginated_response(serializer.data)


class PaymentTermListView(APIView, SearchOrderMixin):
    permission_classes = [HasInstitutionPermission]
    required_permissions = {
        "get": "can_view_payment_terms",
        "post": "can_create_payment_terms",
    }

    queryset = PaymentTerm.objects.undeleted()

    @extend_schema(
        request=PaymentTermSerializer,
        responses={200: PaymentTermSerializer(many=True)},
        description="Retrieve a list of all payment terms for a specific institution.",
        summary="List all payment terms by institution",
        tags=["Customer Management"],
        parameters=[
            SEARCH_PARAM,
            ORDERING_PARAM,
        ],
    )
    def get(self, request):
        payment_terms = self.queryset.filter(
            institution=get_institution(request),
        )

        payment_terms = self.apply_search(payment_terms)
        payment_terms = self.apply_ordering(payment_terms)
        payment_terms = self.apply_filters(payment_terms)

        paginator = CustomPageNumberPagination()
        paginator_qs = paginator.paginate_queryset(payment_terms, request)
        serializer = PaymentTermSerializer(paginator_qs, many=True)
        return paginator.get_paginated_response(serializer.data)

    @extend_schema(
        request=PaymentTermSerializer(many=True),
        responses={201: PaymentTermSerializer(many=True)},
        description="Create one or more payment terms for a specific institution.",
        summary="Create payment terms by institution",
        tags=["Customer Management"],
    )
    def post(self, request):
        institution = get_institution(request)

        if not institution:
            return Response(
                {"error": "Institution not found."},
                status=status.HTTP_404_NOT_FOUND,
            )

        is_many = isinstance(request.data, list)

        serializer = PaymentTermSerializer(
            data=request.data,
            many=is_many,
            context={"request": request, "institution": institution},
        )

        if serializer.is_valid():
            payment_terms = serializer.save(institution=institution)

            if not isinstance(payment_terms, list):
                payment_terms = [payment_terms]

            for term in payment_terms:
                log_action(
                    model_class=PaymentTerm,
                    object_id=term.pk,
                    action="CREATE",
                    user=request.user,
                    description=f"Created Customer Payment Term: {term.term_name}",
                )
                term.confirm_create(
                    profile_institution=request.profile_institution,
                    external_identity=request.external_identity,
                )

            return Response(
                PaymentTermSerializer(payment_terms, many=True).data,
                status=status.HTTP_201_CREATED,
            )

        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)


class PaymentTermDetailView(APIView):
    permission_classes = [HasInstitutionPermission]
    required_permissions = {
        "get": "can_view_payment_terms",
        "patch": "can_edit_payment_terms",
        "delete": "can_delete_payment_terms",
    }

    def _get_payment_term_object(self, request, base_uuid):
        return get_or_raise(
            PaymentTerm.objects.undeleted(),
            message=f"Payment Term with identifier {base_uuid} is not found",
            base_uuid=base_uuid,
            institution=get_institution(request),
        )

    @extend_schema(
        responses={200: PaymentTermSerializer},
        description="Retrieve details of a specific payment term.",
        summary="Get customer payment term details",
        tags=["Customer Management"],
    )
    def get(self, request, base_uuid):
        payment_term = self._get_payment_term_object(
            request,
            base_uuid,
        )
        serializer = PaymentTermSerializer(payment_term)
        return Response(serializer.data)

    @extend_schema(
        request=PaymentTermSerializer,
        responses={200: PaymentTermSerializer},
        description="Partially update details of a specific customer payment term.",
        summary="Partially update payment term details",
        tags=["Customer Management"],
    )
    def patch(self, request, base_uuid):
        payment_term = self._get_payment_term_object(request, base_uuid)
        old_data = PaymentTermSerializer(payment_term).data
        serializer = PaymentTermSerializer(
            payment_term,
            data=request.data,
            partial=True,
            context={"institution": get_institution(request)},
        )
        if serializer.is_valid():
            updated_payment_term = serializer.save()

            new_data = PaymentTermSerializer(updated_payment_term).data
            changes = {
                key: {"old": old_data.get(key), "new": new_data.get(key)}
                for key in request.data.keys()
                if old_data.get(key) != new_data.get(key)
            }

            log_action(
                model_class=PaymentTerm,
                object_id=updated_payment_term.id,
                action="UPDATE",
                user=request.user,
                changes=changes,
                description=f"Updated payment term {updated_payment_term.term_name} ({updated_payment_term.base_uuid})",
            )
            return Response(serializer.data)
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

    @extend_schema(
        responses={204: None},
        description="Delete a specific  payment term.",
        summary="Delete a  payment term",
        tags=["Customer Management"],
    )
    def delete(self, request, base_uuid):

        payment_term = self._get_payment_term_object(request, base_uuid)
        payment_term_data = PaymentTermSerializer(payment_term).data
        payment_term_id = payment_term.id

        payment_term.confirm_delete(
            profile_institution=request.profile_institution,
            external_identity=request.external_identity,
        )

        log_action(
            model_class=PaymentTerm,
            object_id=payment_term_id,
            action="DELETE",
            user=request.user,
            changes=payment_term_data,
            description=f"Deleted customer payment term {payment_term_data['term_name']} ({base_uuid})",
        )
        return Response(status=status.HTTP_204_NO_CONTENT)


class SalesPersonListView(APIView, SearchOrderMixin):
    permission_classes = [HasInstitutionPermission]
    required_permissions = {
        "get": "can_view_sales_persons",
        "post": "can_create_sales_persons",
    }

    @extend_schema(
        request=SalesPersonSerializer,
        responses={200: SalesPersonSerializer(many=True)},
        description="Retrieve a list of all salespersons. Supports searching by name or email.",
        summary="List all salespersons",
        tags=["Sales Person Management"],
        parameters=[
            SEARCH_PARAM,
            ORDERING_PARAM,
        ],
    )
    def get(self, request):
        institution = get_institution(request)

        sales_persons = SalesPerson.objects.undeleted().filter(
            institution=institution,
        )

        sales_persons = self.apply_search(sales_persons)
        sales_persons = self.apply_ordering(sales_persons)

        paginator = CustomPageNumberPagination()
        paginator_qs = paginator.paginate_queryset(sales_persons, request)
        serializer = SalesPersonSerializer(paginator_qs, many=True)
        return paginator.get_paginated_response(serializer.data)

    @extend_schema(
        request=SalesPersonSerializer,
        responses={201: SalesPersonSerializer},
        description="Create a new salesperson.",
        summary="Create a new salesperson",
        tags=["Sales Person Management"],
    )
    def post(self, request):
        institution = get_institution(request)

        serializer = SalesPersonSerializer(
            data=request.data, context={"institution": institution}
        )

        if serializer.is_valid():
            sales_person = serializer.save()
            log_action(
                model_class=SalesPerson,
                object_id=sales_person.pk,
                action="CREATE",
                user=request.user,
                description=f"Created SalesPerson: {sales_person.name}",
            )
            sales_person.confirm_create(
                profile_institution=request.profile_institution,
                external_identity=request.external_identity,
            )
            return Response(serializer.data, status=status.HTTP_201_CREATED)
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)


class SalesPersonDetailView(APIView):

    permission_classes = [HasInstitutionPermission]
    required_permissions = {
        "get": "can_view_sales_persons",
        "patch": "can_edit_sales_persons",
        "delete": "can_delete_sales_persons",
    }

    def _get_sales_person_object(self, base_uuid, institution):
        return get_or_raise(
            queryset=SalesPerson.objects.undeleted(),
            message=f"Sales Person with UUID '{base_uuid}' not found.",
            base_uuid=base_uuid,
            institution=institution,
        )

    @extend_schema(
        responses={200: SalesPersonSerializer},
        description="Retrieve details of a specific salesperson.",
        summary="Get salesperson details",
        tags=["Sales Person Management"],
    )
    def get(self, request, base_uuid):
        institution = get_institution(request)
        if not institution:
            return Response(
                {"error": "User does not belong to an institution."},
                status=status.HTTP_403_FORBIDDEN,
            )

        sales_person = self._get_sales_person_object(base_uuid, institution)
        if not sales_person:
            return Response(status=status.HTTP_404_NOT_FOUND)

        serializer = SalesPersonSerializer(sales_person)
        return Response(serializer.data)

    @extend_schema(
        request=SalesPersonSerializer,
        responses={200: SalesPersonSerializer},
        description="Partially update details of a specific salesperson.",
        summary="Partially update salesperson details",
        tags=["Sales Person Management"],
    )
    def patch(self, request, base_uuid):
        institution = get_institution(request)

        try:
            sales_person = self._get_sales_person_object(base_uuid, institution)
        except ObjectDoesNotExist:
            raise SystemNotFoundError(
                detail=f"Sales Person with UUID '{base_uuid}' not found.",
                status_code=status.HTTP_404_NOT_FOUND,
            )

        sales_person.approval_status = "under_update"

        old_data = SalesPersonSerializer(sales_person).data

        serializer = SalesPersonSerializer(
            sales_person,
            data=request.data,
            partial=True,
            context={"institution": institution},
        )
        if serializer.is_valid():
            updated_sales_person = serializer.save()

            new_data = SalesPersonSerializer(updated_sales_person).data
            changes = {
                key: {"old": old_data.get(key), "new": new_data.get(key)}
                for key in request.data.keys()
                if old_data.get(key) != new_data.get(key)
            }

            log_action(
                model_class=SalesPerson,
                object_id=updated_sales_person.id,
                action="UPDATE",
                user=request.user,
                changes=changes,
                description=f"Updated salesperson {updated_sales_person.name} ({updated_sales_person.base_uuid})",
            )
            updated_sales_person.confirm_update(
                profile_institution=request.profile_institution,
                external_identity=request.external_identity,
            )
            return Response(serializer.data)
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

    @extend_schema(
        responses={204: None},
        description="Delete a specific salesperson.",
        summary="Delete a salesperson",
        tags=["Sales Person Management"],
    )
    def delete(self, request, base_uuid):
        institution = get_institution(request)
        if not institution:
            return Response(
                {"error": "User does not belong to an institution."},
                status=status.HTTP_403_FORBIDDEN,
            )

        sales_person = self._get_sales_person_object(base_uuid, institution)
        sales_person.approval_status = "under_deletion"
        sales_person.save(update_fields=["approval_status"])
        if not sales_person:
            return Response(status=status.HTTP_404_NOT_FOUND)

        sales_person_data = SalesPersonSerializer(sales_person).data
        sales_person_id = sales_person.id

        sales_person.confirm_delete(
            profile_institution=request.profile_institution,
            external_identity=request.external_identity,
        )

        log_action(
            model_class=SalesPerson,
            object_id=sales_person_id,
            action="DELETE",
            user=request.user,
            changes=sales_person_data,
            description=f"Deleted salesperson {sales_person_data['name']} ({base_uuid})",
        )
        return Response(status=status.HTTP_204_NO_CONTENT)


class SalesPersonCommissionView(APIView, SearchOrderMixin):
    permission_classes = [HasInstitutionPermission]
    required_permissions = {
        "get": "can_view_sales_person_commissions",
        "post": "can_create_sales_person_commissions",
    }

    @extend_schema(
        responses={200: SalesPersonCommissionEntrySerializer(many=True)},
        description="Retrieve the total commission earned for all salespersons.",
        summary="List all salespersons' commissions",
        tags=["Commission"],
        parameters=[
            SEARCH_PARAM,
            ORDERING_PARAM,
        ],
    )
    def get(self, request):

        institution = get_institution(request)

        if not institution:
            return Response(
                {"error": "User does not belong to an institution."},
                status=status.HTTP_403_FORBIDDEN,
            )

        sales_persons = SalesPersonCommissionEntry.objects.filter(
            sales_person__institution=institution, deleted_at__isnull=True
        )

        sales_persons = self.apply_search(sales_persons)
        sales_persons = self.apply_ordering(sales_persons)

        serializer = SalesPersonCommissionEntrySerializer(sales_persons, many=True)
        return Response(serializer.data)

    @extend_schema(
        request=SalesPersonCommissionEntrySerializer,
        responses={201: SalesPersonCommissionEntrySerializer},
        description="Record a new commission transaction (earnings or payments) for a salesperson.",
        summary="Create a commission transaction",
        tags=["Commission"],
    )
    def post(self, request):
        data = request.data

        sales_person_id = data.get("sales_person")
        amount = Decimal(data.get("amount"))

        try:
            found = SalesPerson.objects.get(
                id=sales_person_id,
                institution=get_institution(request),
            )
            balance = Decimal(found.balance)

            if amount > balance:
                return Response(
                    {"error": "Amount to redeem exceeds available balance."},
                    status=status.HTTP_400_BAD_REQUEST,
                )
            else:
                balance -= amount
                found.balance = balance

                SalesPersonCommissionEntry.objects.create(
                    sales_person=found,
                    amount=amount,
                    commission_type="payments",
                )

                found.save()
                return Response(
                    {
                        "success": "Commission payment recorded.",
                        "new_balance": balance,
                    },
                    status=status.HTTP_201_CREATED,
                )
        except SalesPerson.DoesNotExist:
            raise SystemNotFoundError(
                detail=f"Sales person with '{sales_person_id}' not found.",
                status_code=status.HTTP_404_NOT_FOUND,
            )
        except Exception as e:
            pass


class CustomerPaymentListCreateView(APIView, SearchOrderMixin):
    permission_classes = [HasInstitutionPermission]
    required_permissions = {
        "get": "can_view_customer_payments",
        "post": "can_create_customer_payments",
    }

    queryset = CustomerPayment.objects.undeleted()

    @extend_schema(
        responses={200: CustomerPaymentSerializer(many=True)},
        description="Retrieve customer invoice payments and prepayments.",
        summary="List customer payments",
        tags=["Customer Payments MGT"],
        parameters=[
            OpenApiParameter("customer_base_uuid", type=str),
            OpenApiParameter("invoice_base_uuid", type=str),
            OpenApiParameter(
                "payment_type",
                type=str,
                enum=["invoice_payment", "prepayment"],
            ),
            OpenApiParameter("payment_status", type=str),
            SEARCH_PARAM,
            ORDERING_PARAM,
        ],
    )
    def get(self, request):
        institution = get_institution(request)
        customer_base_uuid = request.query_params.get("customer_base_uuid")
        invoice_base_uuid = request.query_params.get("invoice_base_uuid")
        payment_type = request.query_params.get("payment_type")
        payment_status = request.query_params.get("payment_status")

        payments = (
            self.queryset.filter(institution=institution)
            .select_related(
                "customer",
                "invoice",
                "invoice__customer",
                "branch",
                "coa_cash_account",
            )
            .order_by("-created_at")
        )

        if customer_base_uuid:
            payments = payments.filter(
                Q(customer__base_uuid=customer_base_uuid)
                | Q(invoice__customer__base_uuid=customer_base_uuid)
            )

        if invoice_base_uuid:
            payments = payments.filter(invoice__base_uuid=invoice_base_uuid)

        if payment_type == "prepayment":
            payments = payments.filter(
                customer__isnull=False,
                invoice__isnull=True,
            )
        elif payment_type == "invoice_payment":
            payments = payments.filter(invoice__isnull=False)

        if payment_status:
            payments = payments.filter(payment_status=payment_status)

        payments = self.apply_search(payments)
        payments = self.apply_ordering(payments)

        paginator = CustomPageNumberPagination()
        paginated_qs = paginator.paginate_queryset(payments, request)
        serializer = CustomerPaymentSerializer(
            paginated_qs,
            many=True,
            context={"request": request},
        )
        return paginator.get_paginated_response(serializer.data)

    @extend_schema(
        request=CustomerPaymentSerializer,
        responses={201: CustomerPaymentSerializer},
        description="Create an invoice payment or customer prepayment.",
        summary="Create customer payment",
        tags=["Customer Payments MGT"],
    )
    def post(self, request):
        institution = get_institution(request)
        serializer = CustomerPaymentSerializer(
            data=request.data,
            context={"request": request},
        )
        serializer.is_valid(raise_exception=True)

        if serializer.validated_data["institution"].pk != institution.pk:
            raise validation_error(
                "The selected customer or invoice does not belong to "
                "your institution."
            )

        with transaction.atomic():
            payment = serializer.save()

            log_action(
                model_class=CustomerPayment,
                object_id=payment.pk,
                action="CREATE",
                user=request.user if request.user.is_authenticated else None,
                description=f"Created customer payment {payment.reference_code}",
            )
            payment.confirm_create(
                profile_institution=request.profile_institution,
                external_identity=request.external_identity,
            )

        return Response(
            CustomerPaymentSerializer(
                payment,
                context={"request": request},
            ).data,
            status=status.HTTP_201_CREATED,
        )


class CustomerPaymentDetailView(APIView):
    permission_classes = [HasInstitutionPermission]
    required_permissions = {
        "get": "can_view_customer_payments",
        "patch": "can_edit_customer_payments",
        "delete": "can_delete_customer_payments",
    }

    def get_object(self, request, base_uuid):
        return get_object_or_404(
            CustomerPayment.objects.undeleted().select_related(
                "customer",
                "invoice",
                "invoice__customer",
                "branch",
                "coa_cash_account",
            ),
            base_uuid=base_uuid,
            institution=get_institution(request),
        )

    @extend_schema(
        responses={200: CustomerPaymentSerializer},
        description="Retrieve a customer payment.",
        summary="Retrieve customer payment",
        tags=["Customer Payments MGT"],
    )
    def get(self, request, base_uuid):
        payment = self.get_object(request, base_uuid)
        return Response(
            CustomerPaymentSerializer(
                payment,
                context={"request": request},
            ).data
        )

    @extend_schema(
        request=CustomerPaymentSerializer,
        responses={200: CustomerPaymentSerializer},
        description="Partially update a customer payment.",
        summary="Update customer payment",
        tags=["Customer Payments MGT"],
    )
    def patch(self, request, base_uuid):
        institution = get_institution(request)

        with transaction.atomic():
            payment = self.get_object(request, base_uuid)

            if payment.is_externally_managed:
                raise validation_error(
                    "Externally managed customer payments cannot be edited manually."
                )

            if payment.are_initial_journal_entries_made:
                raise validation_error(
                    "A posted receipt cannot be edited. Reverse it and create "
                    "a replacement receipt instead."
                )
            old_data = CustomerPaymentSerializer(
                payment,
                context={"request": request},
            ).data

            serializer = CustomerPaymentSerializer(
                payment,
                data=request.data,
                partial=True,
                context={"request": request},
            )
            serializer.is_valid(raise_exception=True)

            if serializer.validated_data["institution"].pk != institution.pk:
                raise validation_error(
                    "The selected customer or invoice does not belong to "
                    "your institution."
                )

            updated_payment = serializer.save(approval_status="under_update")
            new_data = CustomerPaymentSerializer(
                updated_payment,
                context={"request": request},
            ).data

            changes = {
                key: {
                    "old": serialize_value(old_data.get(key)),
                    "new": serialize_value(new_data.get(key)),
                }
                for key in request.data.keys()
                if old_data.get(key) != new_data.get(key)
            }

            log_action(
                model_class=CustomerPayment,
                object_id=updated_payment.pk,
                action="UPDATE",
                user=request.user if request.user.is_authenticated else None,
                changes=changes,
                description=(
                    f"Updated customer payment " f"{updated_payment.reference_code}"
                ),
            )
            updated_payment.confirm_update(
                profile_institution=request.profile_institution,
                external_identity=request.external_identity,
            )

        return Response(
            CustomerPaymentSerializer(
                updated_payment,
                context={"request": request},
            ).data
        )

    @extend_schema(
        responses={204: None},
        description="Request deletion of a customer payment.",
        summary="Delete customer payment",
        tags=["Customer Payments MGT"],
    )
    def delete(self, request, base_uuid):
        with transaction.atomic():
            payment = self.get_object(request, base_uuid)

            if payment.is_externally_managed:
                raise validation_error(
                    "Externally managed customer payments cannot be deleted manually."
                )

            if payment.are_initial_journal_entries_made:
                raise validation_error(
                    "A posted receipt cannot be deleted. Reverse it before "
                    "removing the receipt."
                )

            log_action(
                model_class=CustomerPayment,
                object_id=payment.pk,
                action="DELETE",
                user=request.user if request.user.is_authenticated else None,
                changes=CustomerPaymentSerializer(
                    payment,
                    context={"request": request},
                ).data,
                description=f"Deleted customer payment {payment.reference_code}",
            )

            payment.approval_status = "under_deletion"
            payment.save(update_fields=["approval_status"])
            payment.confirm_delete(
                profile_institution=request.profile_institution,
                external_identity=request.external_identity,
            )

        return Response(status=status.HTTP_204_NO_CONTENT)


class RecurringInvoiceListCreateView(APIView, SearchOrderMixin):
    permission_classes = [HasInstitutionPermission]
    required_permissions = {
        "get": "can_view_recurring_invoices",
        "post": "can_create_recurring_invoices",
    }

    @extend_schema(
        request=RecurringInvoiceSerializer,
        responses={201: RecurringInvoiceSerializer},
        description="Create a new recurring invoice.",
        summary="Create a new recurring invoice",
        tags=["Recurring Invoices"],
    )
    def post(self, request):
        serializer = RecurringInvoiceSerializer(
            data=request.data, context={"request": request}
        )
        serializer.is_valid(raise_exception=True)

        recurring_invoice = serializer.save()

        log_action(
            model_class=RecurringInvoice,
            object_id=recurring_invoice.pk,
            action="CREATE",
            user=request.user,
            description=f"Created recurring invoice: {recurring_invoice.reference_code}",
        )
        recurring_invoice.confirm_create(
            profile_institution=request.profile_institution,
            external_identity=request.external_identity,
        )
        return Response(
            RecurringInvoiceSerializer(recurring_invoice).data,
            status=status.HTTP_201_CREATED,
        )

    @extend_schema(
        responses={200: RecurringInvoiceSerializer(many=True)},
        description="Retrieve a list of all recurring invoices.",
        summary="List all recurring invoices",
        tags=["Recurring Invoices"],
        parameters=[
            SEARCH_PARAM,
            ORDERING_PARAM,
            customer_base_uuid_param(required=False),
            branch_uuids_param(required=True),
        ],
    )
    def get(self, request):
        customer_base_uuid = request.query_params.get("customer_base_uuid", None)

        recurring_invoices = scope_to_institution(
            RecurringInvoice.objects.filter(deleted_at__isnull=True),
            get_institution(request),
            "branch__institution",
            "customer__institution",
        ).order_by("-created_at")

        recurring_invoices = filter_queryset_by_branches(recurring_invoices, request)

        if (
            parse_bool_query_param(
                request.query_params.get("active_without_ongoing_approval"),
                "active_without_ongoing_approval",
            )
            is True
        ):
            ongoing_approvals = Approval.objects.filter(
                content_type=ContentType.objects.get_for_model(RecurringInvoice),
                object_id=OuterRef("pk"),
                status="ongoing",
            )
            recurring_invoices = recurring_invoices.filter(
                is_active=True,
                approval_status="active",
            ).filter(~Exists(ongoing_approvals))

        if customer_base_uuid:
            try:
                customer = Customer.objects.get(
                    base_uuid=customer_base_uuid,
                    institution=get_institution(request),
                    deleted_at__isnull=True,
                )
                recurring_invoices = recurring_invoices.filter(customer=customer)
            except Customer.DoesNotExist:
                raise SystemNotFoundError(
                    detail=f"Customer not found.", status_code=status.HTTP_404_NOT_FOUND
                )

        recurring_invoices = self.apply_search(recurring_invoices)
        recurring_invoices = self.apply_ordering(recurring_invoices)

        paginator = CustomPageNumberPagination()
        paginator_qs = paginator.paginate_queryset(recurring_invoices, request)
        serializer = RecurringInvoiceSerializer(paginator_qs, many=True)
        return paginator.get_paginated_response(serializer.data)


class RecurringInvoiceDetailView(APIView):
    permission_classes = [HasInstitutionPermission]
    required_permissions = {
        "get": "can_view_recurring_invoices",
        "patch": "can_edit_recurring_invoices",
        "delete": "can_delete_recurring_invoices",
    }

    def get_object(self, request, base_uuid):
        return get_or_raise(
            queryset=scope_to_institution(
                RecurringInvoice.objects.filter(deleted_at__isnull=True),
                get_institution(request),
                "branch__institution",
                "customer__institution",
            ),
            message=f"Recurring invoice with UUID {base_uuid} not found.",
            base_uuid=base_uuid,
        )

    @extend_schema(
        responses={200: RecurringInvoiceSerializer()},
        description="Retrieve a specific recurring invoice.",
        summary="Retrieve recurring invoice",
        tags=["Recurring Invoices"],
    )
    def get(self, request, base_uuid):
        recurring_invoice = self.get_object(request, base_uuid)
        return Response(RecurringInvoiceSerializer(recurring_invoice).data)

    @extend_schema(
        request=RecurringInvoiceSerializer,
        responses={200: RecurringInvoiceSerializer()},
        description="Update a specific recurring invoice.",
        summary="Update recurring invoice",
        tags=["Recurring Invoices"],
    )
    def patch(self, request, base_uuid):
        with transaction.atomic():
            recurring_invoice = self.get_object(request, base_uuid)
            serializer = RecurringInvoiceSerializer(
                recurring_invoice,
                data=request.data,
                partial=True,
                context={"request": request},
            )
            if serializer.is_valid():
                serializer.save()
                return Response(serializer.data)
            return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

    @extend_schema(
        responses={204: None},
        description="Delete a specific recurring invoice.",
        summary="Delete recurring invoice",
        tags=["Recurring Invoices"],
    )
    def delete(self, request, base_uuid):
        recurring_invoice = self.get_object(request, base_uuid)
        recurring_invoice.delete()
        return Response(
            {"detail": "Recurring invoice deleted."},
            status=status.HTTP_204_NO_CONTENT,
        )


class RecurringInvoiceItemListCreateView(APIView):
    permission_classes = [HasInstitutionPermission]
    required_permissions = {
        "get": "can_view_recurring_invoice_items",
        "post": "can_create_recurring_invoice_items",
    }

    @extend_schema(
        request=RecurringInvoiceItemSerializer,
        responses={201: RecurringInvoiceItemSerializer},
        description="Create a new recurring invoice item.",
        summary="Create recurring invoice item",
        tags=["Recurring Invoice Items"],
    )
    def post(self, request):

        recurring_invoice_uuid = request.data.get("recurring_invoice")
        if not recurring_invoice_uuid:
            return Response(
                {"recurring_invoice": "This field is required."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        invoice = get_or_raise(
            queryset=scope_to_institution(
                RecurringInvoice.objects.filter(deleted_at__isnull=True),
                get_institution(request),
                "branch__institution",
                "customer__institution",
            ),
            message="Recurring invoice not found.",
            base_uuid=recurring_invoice_uuid,
        )

        payload = request.data.copy()
        payload.pop("recurring_invoice", None)

        serializer = RecurringInvoiceItemSerializer(data=payload)
        serializer.is_valid(raise_exception=True)
        item = serializer.save(recurring_invoice=invoice)

        return Response(
            RecurringInvoiceItemSerializer(item).data,
            status=status.HTTP_201_CREATED,
        )

    @extend_schema(
        responses={200: RecurringInvoiceItemSerializer(many=True)},
        description="Retrieve recurring invoice items.",
        summary="List recurring invoice items",
        tags=["Recurring Invoice Items"],
        parameters=[OpenApiParameter("recurring_invoice_base_uuid", type=str)],
    )
    def get(self, request):
        recurring_invoice_base_uuid = request.query_params.get(
            "recurring_invoice_base_uuid"
        )

        items = scope_to_institution(
            RecurringInvoiceItem.objects.all(),
            get_institution(request),
            "recurring_invoice__branch__institution",
            "recurring_invoice__customer__institution",
        )

        if recurring_invoice_base_uuid:
            recurring_invoice = get_or_raise(
                queryset=scope_to_institution(
                    RecurringInvoice.objects.filter(deleted_at__isnull=True),
                    get_institution(request),
                    "branch__institution",
                    "customer__institution",
                ),
                message="Recurring invoice not found.",
                base_uuid=recurring_invoice_base_uuid,
            )
            items = items.filter(recurring_invoice=recurring_invoice)

        serializer = RecurringInvoiceItemSerializer(items, many=True)
        return Response(serializer.data)


class RecurringInvoiceItemDetailView(APIView):
    permission_classes = [HasInstitutionPermission]
    required_permissions = {
        "get": "can_view_recurring_invoice_items",
        "patch": "can_edit_recurring_invoice_items",
        "delete": "can_delete_recurring_invoice_items",
    }
    import logging

    logger = logging.getLogger(__name__)

    def get_object(self, request, base_uuid):
        try:
            uuid_obj = UUID(str(base_uuid))
        except ValueError:
            raise get_object_or_404(RecurringInvoiceItem, base_uuid=None)

        return get_or_raise(
            queryset=scope_to_institution(
                RecurringInvoiceItem.objects.all(),
                get_institution(request),
                "recurring_invoice__branch__institution",
                "recurring_invoice__customer__institution",
            ),
            message=f"Recurring invoice item with UUID {base_uuid} not found.",
            base_uuid=uuid_obj,
        )

    @extend_schema(
        responses={200: RecurringInvoiceItemSerializer()},
        description="Retrieve a specific recurring invoice item.",
        summary="Retrieve recurring invoice item",
        tags=["Recurring Invoice Items"],
    )
    def get(self, request, base_uuid):
        item = self.get_object(request, base_uuid)
        serializer = RecurringInvoiceItemSerializer(item)
        return Response(serializer.data)

    @extend_schema(
        request=RecurringInvoiceItemSerializer,
        responses={200: RecurringInvoiceItemSerializer()},
        description="Update a specific recurring invoice item.",
        summary="Update recurring invoice item",
        tags=["Recurring Invoice Items"],
    )
    def patch(self, request, base_uuid):
        item = self.get_object(request, base_uuid)
        serializer = RecurringInvoiceItemSerializer(
            item, data=request.data, partial=True
        )
        if serializer.is_valid():
            serializer.save()
            return Response(serializer.data)
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

    @extend_schema(
        responses={204: None},
        description="Delete a specific recurring invoice item.",
        summary="Delete recurring invoice item",
        tags=["Recurring Invoice Items"],
    )
    def delete(self, request, base_uuid):
        item = self.get_object(request, base_uuid)
        item.delete()
        return Response(status=status.HTTP_204_NO_CONTENT)


class CustomerBalanceAdjustmentListAPIView(APIView):
    permission_classes = [HasInstitutionPermission]
    required_permissions = {
        "get": "can_view_customer_balance_adjustments",
    }

    @extend_schema(
        responses={200: CustomerBalanceAdjustmentSerializer(many=True)},
        description="Retrieve a list of all balance adjustments for a specific customer.",
        summary="List all balance adjustments for a customer",
        tags=["Customer Management"],
        parameters=[
            OpenApiParameter(
                name="balance_adjusted",
                type=str,
                description="Filters adjustments based on the type of balance adjusted OUTSTANDING_RECEIVABLE_BALANCE or DEPOSIT_BALANCE.",
                enum=[
                    "OUTSTANDING_RECEIVABLE_BALANCE",
                    "DEPOSIT_BALANCE",
                ],
            ),
        ],
    )
    def get(self, request, base_uuid):
        try:
            customer = Customer.objects.get(
                base_uuid=base_uuid,
                institution=get_institution(request),
            )
        except Customer.DoesNotExist:
            raise SystemNotFoundError(
                detail=f"Customer balance adjustment with UUID {base_uuid} not found",
                status_code=status.HTTP_404_NOT_FOUND,
            )

        adjustments = CustomerBalanceAdjustment.objects.filter(
            customer=customer,
            deleted_at__isnull=True,
        )

        if balance_adjusted := request.query_params.get("balance_adjusted", None):
            adjustments = adjustments.filter(balance_adjusted=balance_adjusted)

        paginator = CustomPageNumberPagination()
        paginator_qs = paginator.paginate_queryset(adjustments, request)
        serializer = CustomerBalanceAdjustmentSerializer(paginator_qs, many=True)
        return paginator.get_paginated_response(serializer.data)


class SendQuotationView(APIView):
    permission_classes = [HasInstitutionPermission]
    required_permissions = {
        "post": "can_send_quotations",
    }

    @extend_schema(
        responses={
            200: {"detail": "Quotation sent and status updated to 'sent'."},
            400: {"detail": "Error message."},
        },
        description="Sends the quotation to the customer and moves the status from 'draft' to 'sent'.",
        summary="Send Quotation to Customer",
        tags=["Quotation Management"],
    )
    def post(self, request, base_uuid):

        quotation = get_or_raise(
            queryset=scope_to_institution(
                Quotation.objects.undeleted(),
                get_institution(request),
                "branch__institution",
                "customer__institution",
            ),
            message=f"Quotation with UUID '{base_uuid}' not found.",
            base_uuid=base_uuid,
        )

        already_sent = "False"

        if quotation.status == "sent":
            already_sent = True

        if already_sent:
            quotation.send_quotation_email()

        quotation.status = "sent"
        quotation.save(update_fields=["status"])

        return Response(
            {
                "detail": f"Quotation {quotation.reference_code} sent and status updated to 'sent'."
            },
            status=status.HTTP_200_OK,
        )


class CreditDebitNoteListView(APIView, SearchOrderMixin):

    permission_classes = [HasInstitutionPermission]
    required_permissions = {
        "get": "can_view_credit_debit_notes",
        "post": "can_create_credit_debit_notes",
    }

    queryset = CreditDebitNote.objects.undeleted()

    @extend_schema(
        request=CreditDebitNoteSerializer,
        responses={201: CreditDebitNoteSerializer},
        description="Create a new credit debit note.",
        summary="Create a new credit debit note",
        tags=["Credit Debit Note Management"],
    )
    @transaction.atomic
    def post(self, request):
        serializer = CreditDebitNoteSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        credit_debit_note = serializer.save()

        log_action(
            model_class=CreditDebitNote,
            object_id=credit_debit_note.pk,
            action="CREATE",
            user=request.user,
            description=f"Created credit/debit note: {credit_debit_note.description}",
        )
        credit_debit_note.confirm_create(
            profile_institution=request.profile_institution,
            external_identity=request.external_identity,
        )
        return Response(
            CreditDebitNoteSerializer(credit_debit_note).data,
            status=status.HTTP_201_CREATED,
        )

    @extend_schema(
        responses={200: CreditDebitNoteSerializer(many=True)},
        description="Retrieve a filtered list of credit and debit notes.",
        summary="List all credit debit notes",
        tags=["Credit Debit Note Management"],
        parameters=[
            OpenApiParameter(
                name="type",
                type=str,
                description="Type of CREDIT or DEBIT.",
            ),
            OpenApiParameter(
                name="falls_under",
                type=str,
                description="Category of credit/debit note (SALES or PURCHASE).",
            ),
            OpenApiParameter(
                name="invoice",
                type=str,
                description="Base UUID of the selected Invoice e.g. 123e4567-e89b-12d3-a456-426614174000.",
                required=False,
            ),
            OpenApiParameter(
                name="bill_base_uuid",
                type=str,
                description="Base UUID of the selected Bill e.g. 123e4567-e89b-12d3-a456-426614174000.",
                required=False,
            ),
            SEARCH_PARAM,
            ORDERING_PARAM,
            branch_uuids_param(required=False),
        ],
    )
    def get(self, request):
        note_type = request.query_params.get("type")
        falls_under = request.query_params.get("falls_under")
        note_status = request.query_params.get("status")
        invoice_base_uuid = request.query_params.get("invoice")
        bill_base_uuid = request.query_params.get(
            "bill_base_uuid"
        ) or request.query_params.get("bill")
        branch_uuids = request.query_params.get(
            "branch_uuids"
        ) or request.query_params.get("branch_base_uuid")

        institution = get_institution(request)

        is_parent_lookup = invoice_base_uuid or bill_base_uuid
        has_list_filters = note_type and falls_under and branch_uuids

        if not is_parent_lookup and not has_list_filters:
            return Response(
                {
                    "detail": (
                        "Provide invoice or bill_base_uuid, or provide type, "
                        "falls_under, and branch_uuids."
                    )
                },
                status=status.HTTP_400_BAD_REQUEST,
            )

        credit_debit_notes = self.queryset.filter(
            Q(branch__institution=institution)
            | Q(
                branch__isnull=True,
                bill__vendor__institution=institution,
            )
            | Q(branch__isnull=True, bill__institution=institution)
            | Q(
                branch__isnull=True,
                bill__purchase_order__branch__institution=institution,
            )
        ).distinct()

        if branch_uuids:
            credit_debit_notes = filter_queryset_by_branches(
                credit_debit_notes,
                request,
                additional_branch_filter=Q(
                    branch__isnull=True,
                    bill__branch__isnull=True,
                    bill__purchase_order__branch__isnull=True,
                ),
            )

        if note_type:
            credit_debit_notes = credit_debit_notes.filter(
                type=note_type,
            )

        if falls_under:
            credit_debit_notes = credit_debit_notes.filter(
                falls_under=falls_under,
            )

        if note_status:
            credit_debit_notes = credit_debit_notes.filter(
                status=note_status,
            )

        date_filter = request.query_params.get("issue_date_period")
        issue_date_from = request.query_params.get("issue_date_from")
        issue_date_to = request.query_params.get("issue_date_to")

        if date_filter:
            issue_date_from, issue_date_to = get_date_range_from_filter(
                date_filter,
                institution,
            )
        else:
            issue_date_from = parse_date(issue_date_from) if issue_date_from else None
            issue_date_to = parse_date(issue_date_to) if issue_date_to else None

        if issue_date_from:
            credit_debit_notes = credit_debit_notes.filter(
                issue_date__gte=issue_date_from,
            )

        if issue_date_to:
            credit_debit_notes = credit_debit_notes.filter(
                issue_date__lte=issue_date_to,
            )

        if invoice_base_uuid:
            credit_debit_notes = credit_debit_notes.filter(
                invoice__base_uuid=invoice_base_uuid
            )

        if bill_base_uuid:
            credit_debit_notes = credit_debit_notes.filter(
                bill__base_uuid=bill_base_uuid
            )

        credit_debit_notes = self.apply_search(credit_debit_notes)
        credit_debit_notes = self.apply_ordering(credit_debit_notes)
        credit_debit_notes = self.apply_filters(credit_debit_notes)

        paginator = CustomPageNumberPagination()
        paginator_qs = paginator.paginate_queryset(credit_debit_notes, request)
        serializer = CreditDebitNoteSerializer(paginator_qs, many=True)
        return paginator.get_paginated_response(serializer.data)


class CreditDebitNoteDetailView(APIView):
    permission_classes = [HasInstitutionPermission]
    required_permissions = {
        "get": "can_view_credit_debit_notes",
        "patch": "can_edit_credit_debit_notes",
        "delete": "can_delete_credit_debit_notes",
    }

    def _get_object(self, institution, base_uuid, for_update=False):
        queryset = CreditDebitNote.objects.undeleted()

        queryset = queryset.filter(
            Q(branch__institution=institution)
            | Q(
                branch__isnull=True,
                bill__vendor__institution=institution,
            )
            | Q(
                branch__isnull=True,
                bill__purchase_order__branch__institution=institution,
            )
        ).distinct()

        if for_update:
            eligible_ids = queryset.filter(base_uuid=base_uuid).order_by().values("pk")
            queryset = (
                CreditDebitNote.objects.undeleted()
                .filter(pk__in=eligible_ids)
                .select_for_update(of=("self",))
            )

        return get_or_raise(
            queryset,
            message=f"Credit/debit note with UUID '{base_uuid}' not found.",
            base_uuid=base_uuid,
        )

    @extend_schema(
        responses={200: CreditDebitNoteSerializer()},
        description="Retrieve a specific credit/debit note.",
        summary="Retrieve credit/debit note",
        tags=["Credit Debit Note Management"],
    )
    def get(self, request, base_uuid):
        credit_debit_note = self._get_object(get_institution(request), base_uuid)
        serializer = CreditDebitNoteSerializer(credit_debit_note)
        return Response(serializer.data)

    @extend_schema(
        responses={200: CreditDebitNoteSerializer()},
        description="Retrieve a specific credit/debit note.",
        summary="Retrieve credit/debit note",
        tags=["Credit Debit Note Management"],
    )
    @transaction.atomic
    def patch(self, request, base_uuid):
        credit_debit_note = self._get_object(
            get_institution(request), base_uuid, for_update=True
        )
        serializer = CreditDebitNoteSerializer(
            credit_debit_note,
            data=request.data,
            partial=True,
        )

        if not serializer.is_valid():
            return Response(
                serializer.errors,
                status=status.HTTP_400_BAD_REQUEST,
            )

        with transaction.atomic():
            old_data = CreditDebitNoteSerializer(credit_debit_note).data
            updated_credit_debit = serializer.save()

            updated_credit_debit.approval_status = "under_update"
            updated_credit_debit.save(update_fields=["approval_status"])

            new_data = CreditDebitNoteSerializer(updated_credit_debit).data
            changes = {
                key: {
                    "old": old_data.get(key),
                    "new": new_data.get(key),
                }
                for key in request.data.keys()
                if old_data.get(key) != new_data.get(key)
            }

            log_action(
                model_class=CreditDebitNote,
                object_id=updated_credit_debit.id,
                action="UPDATE",
                user=request.user,
                changes=changes,
                description=f"Updated credit/debit note {updated_credit_debit.reference_code} ({updated_credit_debit.base_uuid})",
            )

            updated_credit_debit.confirm_update(
                profile_institution=request.profile_institution,
                external_identity=request.external_identity,
            )

        return Response(serializer.data)

    @extend_schema(
        responses={200: CreditDebitNoteSerializer()},
        description="Delete a specific credit/debit note.",
        summary="Delete credit/debit note",
        tags=["Credit Debit Note Management"],
    )
    @transaction.atomic
    def delete(self, request, base_uuid):
        credit_debit_note = self._get_object(
            get_institution(request), base_uuid, for_update=True
        )
        credit_debit_note.approval_status = "under_deletion"
        credit_debit_note.save(update_fields=["approval_status"])

        with transaction.atomic():
            log_action(
                model_class=CreditDebitNote,
                object_id=credit_debit_note.id,
                action="DELETE",
                user=request.user,
                changes=serialize_value(
                    CreditDebitNoteSerializer(credit_debit_note).data
                ),
                description=f"Deleted credit/debit note {credit_debit_note.reference_code} ({base_uuid})",
            )

        credit_debit_note.confirm_delete(
            profile_institution=request.profile_institution,
            external_identity=request.external_identity,
        )

        return Response(
            {"detail": "Credit/debit note deleted."},
            status=status.HTTP_204_NO_CONTENT,
        )


class CreditDebitNoteLineItemListView(APIView):
    permission_classes = [HasInstitutionPermission]
    required_permissions = {
        "get": "can_view_credit_debit_notes",
    }

    @extend_schema(
        responses={200: CreditDebitNoteLineItemSerializer(many=True)},
        description="Retrieve line items for a specific credit or debit note.",
        summary="List credit/debit note line items",
        tags=["Credit Debit Note Management"],
    )
    def get(self, request, base_uuid):
        credit_debit_note = get_or_raise(
            CreditDebitNote.objects.undeleted(),
            message=f"Credit/debit note with UUID '{base_uuid}' not found.",
            base_uuid=base_uuid,
            branch__institution=get_institution(request),
        )

        line_items = (
            credit_debit_note.line_items.undeleted()
            .select_related(
                "account",
                "invoice_line_item",
                "invoice_line_item__line_item",
                "invoice_line_item__line_item__inventory_item",
                "bill_line_item",
            )
            .order_by("created_at")
        )

        paginator = CustomPageNumberPagination()
        paginated_items = paginator.paginate_queryset(line_items, request)
        serializer = CreditDebitNoteLineItemSerializer(
            paginated_items,
            many=True,
        )
        return paginator.get_paginated_response(serializer.data)


class ItemReturnListView(APIView, SearchOrderMixin):
    permission_classes = [HasInstitutionPermission]
    required_permissions = {
        "get": "can_view_item_returns",
        "post": "can_create_item_returns",
    }

    queryset = ItemReturn.objects.undeleted()

    @extend_schema(
        request=ItemReturnSerializer,
        responses={200: ItemReturnSerializer(many=True)},
        description="Retrieve a list of all item returns. Supports searching by item return number or customer name using the 'search' query parameter.",
        summary="List all item returns",
        tags=["Item Return Management"],
        parameters=[
            SEARCH_PARAM,
            ORDERING_PARAM,
            return_reason_uuid_param(required=False),
        ],
    )
    def get(self, request):
        institution = get_institution(request)

        return_reason_uuid = request.query_params.get("return_reason_uuid", None)

        item_returns = scope_to_institution(
            self.queryset,
            institution,
            "goods_issued_note__branch__institution",
            "goods_issued_note__invoice__branch__institution",
            "goods_issued_note__invoice__customer__institution",
            "goods_issued_note__purchase_order__branch__institution",
            "goods_issued_note__purchase_order__customer__institution",
        )

        if return_reason_uuid is not None:
            return_reason = get_object_or_404(
                InstitutionItemReturnReason,
                base_uuid=return_reason_uuid,
                institution=institution,
            )

            item_returns = item_returns.filter(
                item_return_items__return_reason=return_reason
            ).distinct()

        item_returns = self.apply_search(item_returns)
        item_returns = self.apply_ordering(item_returns)
        item_returns = self.apply_filters(item_returns)

        paginator = CustomPageNumberPagination()
        paginator_qs = paginator.paginate_queryset(item_returns, request)
        serializer = ItemReturnSerializer(paginator_qs, many=True)
        return paginator.get_paginated_response(serializer.data)

    @extend_schema(
        request=ItemReturnSerializer,
        responses={201: ItemReturnSerializer},
        description="Create a new item return.",
        summary="Create a new item return",
        tags=["Item Return Management"],
    )
    def post(self, request):
        serializer = ItemReturnSerializer(
            data=request.data, context={"request": request}
        )
        if serializer.is_valid():
            item_return = serializer.save()
            log_action(
                model_class=ItemReturn,
                object_id=item_return.pk,
                action="CREATE",
                user=request.user,
                description=f"Created Item Return: {item_return.reference_code}",
            )
            item_return.confirm_create(
                profile_institution=request.profile_institution,
                external_identity=request.external_identity,
            )
            return Response(serializer.data, status=status.HTTP_201_CREATED)
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)


class ItemReturnDetailView(APIView):
    permission_classes = [HasInstitutionPermission]
    required_permissions = {
        "get": "can_view_item_returns",
        "patch": "can_edit_item_returns",
        "delete": "can_delete_item_returns",
    }

    def get_object(self, request, base_uuid):
        institution = get_institution(request)
        return get_or_raise(
            queryset=scope_to_institution(
                ItemReturn.objects.filter(deleted_at__isnull=True),
                institution,
                "goods_issued_note__branch__institution",
                "goods_issued_note__invoice__branch__institution",
                "goods_issued_note__invoice__customer__institution",
                "goods_issued_note__purchase_order__branch__institution",
                "goods_issued_note__purchase_order__customer__institution",
            ),
            message=f"Item return with UUID {base_uuid} not found.",
            base_uuid=base_uuid,
        )

    @extend_schema(
        responses={200: ItemReturnSerializer},
        description="Retrieve details of a specific item return.",
        summary="Get item return details",
        tags=["Item Return Management"],
    )
    def get(self, request, base_uuid):
        item_return = self.get_object(request, base_uuid)
        if not item_return:
            return Response(
                {"detail": "Item return not found."}, status=status.HTTP_404_NOT_FOUND
            )
        serializer = ItemReturnSerializer(item_return)
        return Response(serializer.data)

    @extend_schema(
        request=ItemReturnSerializer,
        responses={200: ItemReturnSerializer},
        description="Partially update details of a specific item return.",
        summary="Partially update item return details",
        tags=["Item Return Management"],
    )
    def patch(self, request, base_uuid):
        item_return = self.get_object(request, base_uuid)
        if not item_return:
            return Response(status=status.HTTP_404_NOT_FOUND)

        old_data = ItemReturnSerializer(item_return).data
        serializer = ItemReturnSerializer(item_return, data=request.data, partial=True)
        if serializer.is_valid():
            updated_item_return = serializer.save()
            new_data = ItemReturnSerializer(updated_item_return).data
            changes = {
                key: {"old": old_data.get(key), "new": new_data.get(key)}
                for key in request.data.keys()
                if old_data.get(key) != new_data.get(key)
            }
            log_action(
                model_class=ItemReturn,
                object_id=updated_item_return.id,
                action="UPDATE",
                user=request.user if request.user.is_authenticated else None,
                changes=changes,
                description=f"Updated item return {updated_item_return.item_return_number} ({updated_item_return.base_uuid})",
            )
            return Response(serializer.data)
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

    @extend_schema(
        responses={204: None},
        description="Delete a specific item return.",
        summary="Delete an item return",
        tags=["Item Return Management"],
    )
    def delete(self, request, base_uuid):
        item_return = self.get_object(request, base_uuid)
        if not item_return:
            return Response(status=status.HTTP_404_NOT_FOUND)

        item_return.approval_status = "under_deletion"
        item_return.save(update_fields=["approval_status"])

        item_return_data = ItemReturnSerializer(item_return).data
        item_return_id = item_return.id

        with transaction.atomic():

            reference_code = item_return_data.get("return_reference_code", base_uuid)

            log_action(
                model_class=ItemReturn,
                object_id=item_return_id,
                action="DELETE",
                user=request.user if request.user.is_authenticated else None,
                changes=item_return_data,
                description=f"Deleted item return {reference_code} ({base_uuid})",
            )

            item_return.confirm_delete(
                profile_institution=request.profile_institution,
                external_identity=request.external_identity,
            )

        return Response(status=status.HTTP_204_NO_CONTENT)


class ItemReturnLineItemListView(APIView):
    permission_classes = [HasInstitutionPermission]
    required_permissions = {
        "get": "can_view_item_returns",
    }

    @extend_schema(
        responses={200: ItemReturnItemSerializer(many=True)},
        description="Retrieve a list of all line items for a specific item return.",
        summary="List all line items for an item return",
        tags=["Item Return Management"],
    )
    def get(self, request, base_uuid):
        item_return = get_or_raise(
            queryset=ItemReturn.objects.undeleted(),
            message=f"Item return with UUID {base_uuid} not found.",
            base_uuid=base_uuid,
            institution=get_institution(request),
        )

        line_items = item_return.item_return_items.undeleted().select_related(
            "goods_issued_note_line",
            "goods_issued_note_line__line_item",
            "goods_issued_note_line__line_item__inventory_item",
            "goods_issued_note_line__line_item__inventory_item__item_category",
            "return_reason",
            "unit_of_measure",
            "unit_of_measure__unit_of_measure",
        )

        pagination = CustomPageNumberPagination()
        paginated_line_items = pagination.paginate_queryset(line_items, request)
        serializer = ItemReturnItemSerializer(paginated_line_items, many=True)
        return pagination.get_paginated_response(serializer.data)


class InvoicePDFDownloadView(APIView):
    permission_classes = [HasInstitutionPermission]
    required_permissions = {
        "get": "can_view_customer_invoices",
    }

    @extend_schema(
        responses={
            200: {"description": "PDF file"},
            404: {"description": "Invoice not found"},
            403: {"description": "Permission denied"},
            400: {"description": "Invalid request"},
        },
        description="Download invoice as PDF in professional format",
        summary="Download invoice PDF",
        tags=["Invoice Report Management"],
    )
    def get(self, request, base_uuid):
        """
        Download invoice as PDF
        """
        try:
            institution = get_institution(request)

            invoice = get_object_or_404(
                Invoice, base_uuid=base_uuid, branch__institution=institution
            )

            invoice_data = get_complete_invoice_data_for_pdf(
                invoice=invoice, request=request
            )

            response = generate_invoice_pdf_response(invoice_data)
            # response = Response(invoice_data)

            invoice_number = invoice_data["invoice_info"]["number"]
            filename = f"Invoice_{invoice_number}.pdf"
            response["Content-Disposition"] = f'attachment; filename="{filename}"'

            response["Cache-Control"] = "no-cache, no-store, must-revalidate"
            response["Pragma"] = "no-cache"
            response["Expires"] = "0"

            return response

        except ObjectDoesNotExist:
            return Response(
                {"detail": "Invoice not found"}, status=status.HTTP_404_NOT_FOUND
            )
        except PermissionError:
            return Response(
                {"detail": "You don't have permission to access this invoice"},
                status=status.HTTP_403_FORBIDDEN,
            )
        except Exception as e:

            return Response(
                {"detail": f"Error generating PDF: {str(e)}"},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR,
            )


class QuotationPDFDownloadView(APIView):
    permission_classes = [HasInstitutionPermission]
    required_permissions = {
        "get": "can_view_customer_quotations",
    }

    @extend_schema(
        responses={
            200: {"description": "PDF file"},
            404: {"description": "Quotation not found"},
            403: {"description": "Permission denied"},
            400: {"description": "Invalid request"},
        },
        description="Download quotation as PDF in professional format",
        summary="Download quotation PDF",
        tags=["Quotation Report Management"],
    )
    def get(self, request, base_uuid):
        """
        Download quotation as PDF
        """
        try:
            institution = get_institution(request)

            quotation = get_object_or_404(
                Quotation, base_uuid=base_uuid, branch__institution=institution
            )

            quotation_data = get_complete_quotation_data_for_pdf(
                quotation=quotation, request=request
            )

            response = generate_quotation_pdf_response(quotation_data, request)

            return response

        except ObjectDoesNotExist:
            return Response(
                {"detail": "Quotation not found"}, status=status.HTTP_404_NOT_FOUND
            )
        except PermissionError:
            return Response(
                {"detail": "You don't have permission to access this quotation"},
                status=status.HTTP_403_FORBIDDEN,
            )
        except Exception as e:
            return Response(
                {"detail": f"Error generating PDF: {str(e)}"},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR,
            )


class CustomerPurchaseOrderPDFDownloadView(APIView):
    permission_classes = [HasInstitutionPermission]
    required_permissions = {
        "get": "can_view_customer_purchase_orders",
    }

    @extend_schema(
        responses={
            200: {"description": "PDF file"},
            404: {"description": "Purchase Order not found"},
            403: {"description": "Permission denied"},
            400: {"description": "Invalid request"},
        },
        description="Download purchase order as PDF in professional format",
        summary="Download purchase order PDF",
        tags=["Purchase Order Report Management"],
    )
    def get(self, request, base_uuid):
        """
        Download purchase order as PDF
        """
        try:
            institution = get_institution(request)

            purchase_order = get_object_or_404(
                CustomerPurchaseOrder,
                base_uuid=base_uuid,
                branch__institution=institution,
            )

            po_data = get_complete_purchase_order_data_for_pdf(
                po=purchase_order, request=request
            )

            response = generate_purchase_order_pdf_response(po_data, request)

            return response

        except ObjectDoesNotExist:
            return Response(
                {"detail": "Purchase Order not found"}, status=status.HTTP_404_NOT_FOUND
            )
        except PermissionError:
            return Response(
                {"detail": "You don't have permission to access this purchase order"},
                status=status.HTTP_403_FORBIDDEN,
            )
        except Exception as e:
            return Response(
                {"detail": f"Error generating PDF: {str(e)}"},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR,
            )


class TaxCalculationPreviewView(APIView):
    @extend_schema(
        request=TaxCalculationPreviewSerializer,
        responses={200: dict},
        description=(
            "Preview taxes for an amount using an item's configured taxes "
            "or explicitly supplied taxes."
        ),
        summary="Preview a tax calculation",
        tags=["Tax Calculation"],
    )
    def post(self, request):
        serializer = TaxCalculationPreviewSerializer(data=request.data)

        if serializer.is_valid():
            amount = serializer.validated_data["amount"]
            base_uuid = serializer.validated_data.get("base_uuid")
            tax_type = serializer.validated_data.get("type", None)
            applicable_taxes = serializer.validated_data.get("applicable_taxes", [])

            if applicable_taxes:
                result = preview_taxes(amount, applicable_taxes)
            elif base_uuid and tax_type:
                from items.models import BranchInventoryItem

                if tax_type == "sales":
                    item = get_object_or_404(
                        BranchInventoryItem,
                        base_uuid=base_uuid,
                        branch__institution=get_institution(request),
                    )
                else:
                    item = get_object_or_404(
                        InventoryItem,
                        base_uuid=base_uuid,
                        institution=get_institution(request),
                    )

                result = preview_tax_for_item(item, tax_type, amount)
            else:
                result = preview_taxes(amount)

            return Response(result, status=status.HTTP_200_OK)

        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)


class ItemReturnPDFDownloadView(APIView):
    permission_classes = [HasInstitutionPermission]
    required_permissions = {
        "get": "can_view_customer_invoices",
    }

    @extend_schema(
        responses={
            200: {"description": "PDF file"},
            404: {"description": "Item Return not found"},
            403: {"description": "Permission denied"},
            400: {"description": "Invalid request"},
        },
        description="Download item return as PDF in professional format",
        summary="Download item return PDF",
        tags=["Item Return Report Management"],
    )
    def get(self, request, base_uuid):
        """
        Download item return as PDF
        """
        try:
            institution = get_institution(request)

            item_return = get_object_or_404(
                ItemReturn,
                base_uuid=base_uuid,
                goods_issued_note__branch__institution=institution,
            )

            return_data = get_complete_item_return_data_for_pdf(
                item_return=item_return, request=request
            )

            response = generate_item_return_pdf_response(return_data, request)

            return response

        except ObjectDoesNotExist:
            return Response(
                {"detail": "Item Return not found"}, status=status.HTTP_404_NOT_FOUND
            )
        except PermissionError:
            return Response(
                {"detail": "You don't have permission to access this item return"},
                status=status.HTTP_403_FORBIDDEN,
            )
        except Exception as e:
            return Response(
                {"detail": f"Error generating PDF: {str(e)}"},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR,
            )


class CreditDebitNotePDFDownloadView(APIView):
    permission_classes = [HasInstitutionPermission]
    required_permissions = {
        "get": "can_view_credit_debit_notes",
    }

    @extend_schema(
        responses={
            200: {"description": "PDF file"},
            404: {"description": "Credit/Debit Note not found"},
            403: {"description": "Permission denied"},
            400: {"description": "Invalid request"},
        },
        description="Download credit/debit note as PDF in professional format",
        summary="Download credit/debit note PDF",
        tags=["Credit/Debit Note Report Management"],
    )
    def get(self, request, base_uuid):
        """
        Download credit/debit note as PDF
        """
        try:
            institution = get_institution(request)

            credit_debit_note = get_object_or_404(
                CreditDebitNote, base_uuid=base_uuid, branch__institution=institution
            )

            note_data = get_complete_credit_debit_note_data_for_pdf(
                credit_debit_note=credit_debit_note, request=request
            )

            response = generate_credit_debit_note_pdf_response(note_data, request)

            return response

        except ObjectDoesNotExist:
            return Response(
                {"detail": "Credit/Debit Note not found"},
                status=status.HTTP_404_NOT_FOUND,
            )
        except PermissionError:
            return Response(
                {
                    "detail": "You don't have permission to access this credit/debit note"
                },
                status=status.HTTP_403_FORBIDDEN,
            )
        except Exception as e:
            return Response(
                {"detail": f"Error generating PDF: {str(e)}"},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR,
            )


class GoodsIssuedNoteListView(APIView, SearchOrderMixin):
    permission_classes = [HasInstitutionPermission]
    required_permissions = {
        "get": "can_view_goods_issued_notes",
        "post": "can_create_goods_issued_notes",
    }

    queryset = GoodsIssuedNote.objects.undeleted()

    @extend_schema(
        request=GoodsIssuedNoteSerializer,
        responses={200: GoodsIssuedNoteSerializer(many=True)},
        description="Retrieve a list of all goods issued notes. Supports searching by reference number or customer name using the 'search' query parameter.",
        summary="List all goods issued notes",
        tags=["Goods Issued Note Management"],
        parameters=[
            SEARCH_PARAM,
            ORDERING_PARAM,
            branch_uuids_param(required=True),
            OpenApiParameter(
                name="status",
                type=str,
                location=OpenApiParameter.QUERY,
                description="Filter by status (draft, confirmed, etc.)",
                required=False,
            ),
        ],
    )
    def get(self, request):

        status = request.query_params.get("status", None)
        has_returnable_items = parse_bool_query_param(
            request.query_params.get("has_returnable_items"),
            "has_returnable_items",
        )

        goods_issued_notes = scope_to_institution(
            GoodsIssuedNote.objects.filter(deleted_at__isnull=True),
            get_institution(request),
            "branch__institution",
            "invoice__branch__institution",
            "invoice__customer__institution",
            "purchase_order__branch__institution",
            "purchase_order__customer__institution",
        )

        goods_issued_notes = filter_queryset_by_branches(goods_issued_notes, request)

        if status:
            goods_issued_notes = goods_issued_notes.filter(status=status)

        if has_returnable_items is not None:
            processed_returns = (
                ItemReturnItem.objects.filter(
                    goods_issued_note_line=OuterRef("pk"),
                    item_return__return_status="APPROVED",
                    item_return__are_initial_journal_entries_made=True,
                    item_return__deleted_at__isnull=True,
                    deleted_at__isnull=True,
                )
                .values("goods_issued_note_line")
                .annotate(total=Sum("quantity"))
                .values("total")
            )

            returnable_lines = (
                GoodsIssuedNoteLineItem.objects.filter(
                    goods_issued_note=OuterRef("pk"),
                    deleted_at__isnull=True,
                )
                .annotate(
                    processed_return_quantity=Coalesce(
                        Subquery(
                            processed_returns,
                            output_field=IntegerField(),
                        ),
                        Value(0),
                    )
                )
                .filter(quantity__gt=F("processed_return_quantity"))
            )

            goods_issued_notes = goods_issued_notes.annotate(
                has_returnable_items=Exists(returnable_lines)
            ).filter(has_returnable_items=has_returnable_items)

        goods_issued_notes = self.apply_search(goods_issued_notes)
        goods_issued_notes = self.apply_ordering(goods_issued_notes)
        goods_issued_notes = self.apply_filters(goods_issued_notes)

        paginator = CustomPageNumberPagination()
        paginator_qs = paginator.paginate_queryset(goods_issued_notes, request)
        serializer = GoodsIssuedNoteSerializer(paginator_qs, many=True)
        return paginator.get_paginated_response(serializer.data)

    @extend_schema(
        request=GoodsIssuedNoteSerializer,
        responses={201: GoodsIssuedNoteSerializer},
        description="Create a new goods issued note.",
        summary="Create a new goods issued note",
        tags=["Goods Issued Note Management"],
    )
    @transaction.atomic()
    def post(self, request):
        serializer = GoodsIssuedNoteSerializer(
            data=request.data,
            context={
                "request": request,
                "institution": get_institution(request),
            },
        )
        if serializer.is_valid():
            goods_issued_note = serializer.save()
            log_action(
                model_class=GoodsIssuedNote,
                object_id=goods_issued_note.pk,
                action="CREATE",
                user=request.user,
                description=f"Created Goods Issued Note: {goods_issued_note.reference_code}",
            )
            goods_issued_note.confirm_create(
                profile_institution=request.profile_institution,
                external_identity=request.external_identity,
            )
            return Response(serializer.data, status=status.HTTP_201_CREATED)
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)


class GoodsIssuedNoteDetailView(APIView):
    permission_classes = [HasInstitutionPermission]
    required_permissions = {
        "get": "can_view_goods_issued_notes",
        "patch": "can_edit_goods_issued_notes",
        "delete": "can_delete_goods_issued_notes",
    }

    def get_object(self, request, base_uuid):
        return get_or_raise(
            queryset=scope_to_institution(
                GoodsIssuedNote.objects.filter(deleted_at__isnull=True),
                get_institution(request),
                "branch__institution",
                "invoice__branch__institution",
                "invoice__customer__institution",
                "purchase_order__branch__institution",
                "purchase_order__customer__institution",
            ),
            message=f"Goods issued note with UUID '{base_uuid}' not found.",
            base_uuid=base_uuid,
        )

    @extend_schema(
        responses={200: GoodsIssuedNoteSerializer},
        description="Retrieve details of a specific goods issued note.",
        summary="Get goods issued note details",
        tags=["Goods Issued Note Management"],
    )
    def get(self, request, base_uuid):
        goods_issued_note = self.get_object(request, base_uuid)
        if not goods_issued_note:
            return Response(status=status.HTTP_404_NOT_FOUND)
        serializer = GoodsIssuedNoteSerializer(goods_issued_note)
        return Response(serializer.data)

    @extend_schema(
        request=GoodsIssuedNoteSerializer,
        responses={200: GoodsIssuedNoteSerializer},
        description="Partially update details of a specific goods issued note.",
        summary="Partially update goods issued note details",
        tags=["Goods Issued Note Management"],
    )
    def patch(self, request, base_uuid):
        with transaction.atomic():
            goods_issued_note = self.get_object(request, base_uuid)
            if not goods_issued_note:
                return Response(status=status.HTTP_404_NOT_FOUND)
            goods_issued_note.approval_status = "under_update"
            old_data = GoodsIssuedNoteSerializer(goods_issued_note).data
            serializer = GoodsIssuedNoteSerializer(
                goods_issued_note,
                data=request.data,
                partial=True,
                context={"request": request, "institution": get_institution(request)},
            )
            if serializer.is_valid():
                updated_goods_issued_note = serializer.save()
                new_data = GoodsIssuedNoteSerializer(updated_goods_issued_note).data
                changes = {
                    key: {"old": old_data.get(key), "new": new_data.get(key)}
                    for key in request.data.keys()
                    if old_data.get(key) != new_data.get(key)
                }
                log_action(
                    model_class=GoodsIssuedNote,
                    object_id=updated_goods_issued_note.id,
                    action="UPDATE",
                    user=request.user if request.user.is_authenticated else None,
                    changes=serialize_value(changes),
                    description=f"Updated goods issued note {updated_goods_issued_note.reference_code} ({updated_goods_issued_note.base_uuid})",
                )
                updated_goods_issued_note.confirm_update(
                    profile_institution=request.profile_institution,
                    external_identity=request.external_identity,
                )
                return Response(serializer.data)
            return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

    @extend_schema(
        responses={204: None},
        description="Delete a specific goods issued note.",
        summary="Delete a goods issued note",
        tags=["Goods Issued Note Management"],
    )
    def delete(self, request, base_uuid):
        goods_issued_note = self.get_object(request, base_uuid)
        if not goods_issued_note:
            return Response(status=status.HTTP_404_NOT_FOUND)

        goods_issued_note.approval_status = "under_deletion"
        goods_issued_note.save(update_fields=["approval_status"])

        goods_issued_note_data = GoodsIssuedNoteSerializer(goods_issued_note).data
        goods_issued_note_id = goods_issued_note.id
        goods_issued_note.confirm_delete(
            profile_institution=request.profile_institution,
            external_identity=request.external_identity,
        )
        log_action(
            model_class=GoodsIssuedNote,
            object_id=goods_issued_note_id,
            action="DELETE",
            user=request.user if request.user.is_authenticated else None,
            changes=serialize_value(goods_issued_note_data),
            description=f"Deleted goods issued note {goods_issued_note_data['reference_code']} ({base_uuid})",
        )
        return Response(status=status.HTTP_204_NO_CONTENT)


class GoodsIssuedNoteLineItemListView(APIView):
    permission_classes = [HasInstitutionPermission]
    required_permissions = {
        "get": "can_view_goods_issued_notes",
    }

    @extend_schema(
        responses={200: GoodsIssuedNoteLineItemSerializer(many=True)},
        description="Retrieve a list of all line items for a specific goods issued note.",
        summary="List all line items for a goods issued note",
        tags=["Goods Issued Note Management"],
    )
    def get(self, request, base_uuid):
        goods_issued_note = get_or_raise(
            queryset=GoodsIssuedNote.objects.undeleted(),
            message=f"Goods issued note with UUID {base_uuid} not found.",
            base_uuid=base_uuid,
            branch__institution=get_institution(request),
        )

        search = request.query_params.get("search", "").strip()

        line_items = GoodsIssuedNoteLineItem.objects.filter(
            goods_issued_note=goods_issued_note,
            deleted_at__isnull=True,
        ).select_related(
            "line_item",
            "line_item__inventory_item",
            "unit_of_measure",
            "unit_of_measure__unit_of_measure",
        )

        if search:
            line_items = line_items.filter(
                Q(line_item__inventory_item__item_name__icontains=search)
                | Q(line_item__inventory_item__reference_code__icontains=search)
            )

        paginator = CustomPageNumberPagination()
        paginated_qs = paginator.paginate_queryset(line_items, request)
        serializer = GoodsIssuedNoteLineItemSerializer(paginated_qs, many=True)
        return paginator.get_paginated_response(serializer.data)


class CustomerPaymentReconcileView(APIView):
    permission_classes = [HasInstitutionPermission]
    required_permissions = {"post": "can_create_customer_payments"}

    @extend_schema(
        request=ReconcileCustomerPrepaymentsSerializer,
        responses={200: "Reconciliation successful"},
        description=(
            "Allocate one or more approved customer prepayments against "
            "one or more invoices belonging to the same customer."
        ),
        summary="Reconcile customer prepayments against invoices",
        tags=["Customer Payments MGT"],
    )
    def post(self, request):
        serializer = ReconcileCustomerPrepaymentsSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        data = serializer.validated_data

        reconcile_customer_prepayments(
            prepayment_uuids=data["prepayment_uuids"],
            invoice_uuids=data["invoice_uuids"],
            institution=get_institution(request),
        )

        return Response(
            {
                "detail": "Customer prepayments applied successfully.",
            },
            status=status.HTTP_200_OK,
        )


class DepositAllocationListView(APIView):
    permission_classes = [HasInstitutionPermission]
    required_permissions = {
        "get": "can_view_deposit_allocations",
    }

    @extend_schema(
        responses={200: DepositAllocationSerializer(many=True)},
        description="Retrieve allocations for a specific customer prepayment.",
        summary="List customer prepayment allocations",
        tags=["Customer Payments MGT"],
        parameters=[
            customer_payment_base_uuid_param(required=True),
        ],
    )
    def get(self, request):
        payment_base_uuid = request.query_params.get("customer_payment_base_uuid")

        if not payment_base_uuid:
            return validation_error(
                "The 'customer_payment_base_uuid' query parameter is required "
                "and must be a valid customer payment UUID."
            )

        prepayment = get_object_or_404(
            CustomerPayment,
            base_uuid=payment_base_uuid,
            institution=get_institution(request),
            invoice__isnull=True,
            deleted_at__isnull=True,
        )

        allocations = CustomerDepositAllocation.objects.filter(
            prepayment=prepayment,
        ).select_related("invoice", "prepayment")

        paginator = CustomPageNumberPagination()
        paginated_qs = paginator.paginate_queryset(allocations, request)

        serializer = DepositAllocationSerializer(paginated_qs, many=True)

        return paginator.get_paginated_response(serializer.data)
