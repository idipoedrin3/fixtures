import csv
import uuid

from decimal import Decimal, InvalidOperation

from django.contrib.contenttypes.models import ContentType
from django.db import transaction
from django.http import HttpResponse
from django.shortcuts import get_object_or_404
from drf_spectacular.utils import extend_schema
from rest_framework import serializers, status
from rest_framework.response import Response
from rest_framework.views import APIView

from audit.models import AuditLog
from users.permissions import HasInstitutionPermission
from utilities.helpers import get_institution, serialize_value
from utilities.mixin import SearchOrderMixin
from utilities.pagination import CustomPageNumberPagination

from .models import Lender, Loan, LoanRepayment, LoanRepaymentSchedule
from .serializers import LenderSerializer, LoanRepaymentSerializer, LoanSerializer
from .services import (
    LoanRepaymentScheduleService,
    LoanRepaymentService,
    LoanService,
)


class LenderViewMixin:
    permission_classes = [HasInstitutionPermission]

    def get_queryset(self, request):
        return Lender.objects.filter(
            institution=get_institution(request),
            deleted_at__isnull=True,
        ).select_related("institution")

    def get_lender(self, request, base_uuid, *, lock=False):
        queryset = self.get_queryset(request)
        if lock:
            queryset = queryset.select_for_update(of=("self",))
        return get_object_or_404(queryset, base_uuid=base_uuid)

    def approval_context(self, request):
        return {
            "profile_institution": getattr(request, "profile_institution", None),
            "external_identity": getattr(request, "external_identity", None),
        }

    def audit(self, request, lender, action, description, changes=None):
        AuditLog.objects.create(
            content_type=ContentType.objects.get_for_model(Lender),
            object_id=lender.pk,
            action=action,
            user=request.user if request.user.is_authenticated else None,
            description=description,
            changes=serialize_value(changes) if changes is not None else None,
        )


class LenderListCreateView(LenderViewMixin, APIView, SearchOrderMixin):
    required_permissions = {
        "get": "can_view_lenders",
        "post": "can_create_lenders",
    }

    @extend_schema(responses=LenderSerializer(many=True), tags=["Lenders"])
    def get(self, request):
        queryset = self.apply_ordering(self.apply_search(self.get_queryset(request)))
        paginator = CustomPageNumberPagination()
        page = paginator.paginate_queryset(queryset, request)
        serializer = LenderSerializer(page, many=True, context={"request": request})
        return paginator.get_paginated_response(serializer.data)

    @extend_schema(
        request=LenderSerializer,
        responses={201: LenderSerializer},
        tags=["Lenders"],
    )
    @transaction.atomic
    def post(self, request):
        serializer = LenderSerializer(data=request.data, context={"request": request})
        serializer.is_valid(raise_exception=True)
        lender = serializer.save()
        lender.confirm_create(**self.approval_context(request))
        lender.refresh_from_db()
        self.audit(request, lender, "CREATE", f"Created lender {lender.name}.")
        return Response(
            LenderSerializer(lender, context={"request": request}).data,
            status=status.HTTP_201_CREATED,
        )


class LenderDetailView(LenderViewMixin, APIView):
    required_permissions = {
        "get": "can_view_lenders",
        "patch": "can_edit_lenders",
        "delete": "can_delete_lenders",
    }

    @extend_schema(responses=LenderSerializer, tags=["Lenders"])
    def get(self, request, base_uuid):
        lender = self.get_lender(request, base_uuid)
        return Response(LenderSerializer(lender, context={"request": request}).data)

    @extend_schema(
        request=LenderSerializer,
        responses=LenderSerializer,
        tags=["Lenders"],
    )
    @transaction.atomic
    def patch(self, request, base_uuid):
        lender = self.get_lender(request, base_uuid, lock=True)
        lender.ensure_no_ongoing_approval(attempted_action="update")
        before = LenderSerializer(lender, context={"request": request}).data
        serializer = LenderSerializer(
            lender, data=request.data, partial=True, context={"request": request}
        )
        serializer.is_valid(raise_exception=True)
        lender.approval_status = "under_update"
        lender = serializer.save()
        lender.confirm_update(**self.approval_context(request))
        lender.refresh_from_db()
        after = LenderSerializer(lender, context={"request": request}).data
        changes = {
            name: {"old": before.get(name), "new": after.get(name)}
            for name in serializer.validated_data
            if before.get(name) != after.get(name)
        }
        self.audit(
            request,
            lender,
            "UPDATE",
            f"Submitted update for lender {lender.name}.",
            changes,
        )
        return Response(after)

    @extend_schema(responses={202: LenderSerializer, 204: None}, tags=["Lenders"])
    @transaction.atomic
    def delete(self, request, base_uuid):
        lender = self.get_lender(request, base_uuid, lock=True)
        lender.confirm_delete(**self.approval_context(request))
        lender.refresh_from_db()
        self.audit(
            request,
            lender,
            "DELETE",
            f"Requested deletion of lender {lender.name}.",
        )
        if lender.deleted_at is not None:
            return Response(status=status.HTTP_204_NO_CONTENT)
        return Response(
            LenderSerializer(lender, context={"request": request}).data,
            status=status.HTTP_202_ACCEPTED,
        )


class LoanViewMixin:
    permission_classes = [HasInstitutionPermission]

    def get_queryset(self, request):
        return Loan.objects.filter(
            institution=get_institution(request),
            deleted_at__isnull=True,
        ).select_related(
            "institution",
            "branch",
            "currency__currency",
            "cash_account",
            "liability_receivable_account",
            "opening_balance_account",
            "initial_journal",
            "party_content_type",
        )

    def get_loan(self, request, base_uuid, *, lock=False):
        queryset = self.get_queryset(request)
        if lock:
            queryset = queryset.select_for_update(of=("self",))
        return get_object_or_404(queryset, base_uuid=base_uuid)

    def approval_context(self, request):
        return {
            "profile_institution": getattr(request, "profile_institution", None),
            "external_identity": getattr(request, "external_identity", None),
        }

    def audit(self, request, loan, action, description, changes=None):
        AuditLog.objects.create(
            content_type=ContentType.objects.get_for_model(Loan),
            object_id=loan.pk,
            action=action,
            user=request.user if request.user.is_authenticated else None,
            description=description,
            changes=serialize_value(changes) if changes is not None else None,
        )


class LoanListCreateView(LoanViewMixin, APIView, SearchOrderMixin):
    required_permissions = {
        "get": "can_view_loans",
        "post": "can_create_loans",
    }

    @extend_schema(responses=LoanSerializer(many=True), tags=["Loans"])
    def get(self, request):
        queryset = self.apply_ordering(self.apply_search(self.get_queryset(request)))
        paginator = CustomPageNumberPagination()
        page = paginator.paginate_queryset(queryset, request)
        serializer = LoanSerializer(page, many=True, context={"request": request})
        return paginator.get_paginated_response(serializer.data)

    @extend_schema(
        request=LoanSerializer,
        responses={201: LoanSerializer},
        tags=["Loans"],
    )
    @transaction.atomic
    def post(self, request):
        serializer = LoanSerializer(data=request.data, context={"request": request})
        serializer.is_valid(raise_exception=True)
        loan = serializer.save()
        loan.confirm_create(**self.approval_context(request))
        loan.refresh_from_db()
        self.audit(request, loan, "CREATE", f"Created loan {loan.reference_code}.")
        return Response(
            LoanSerializer(loan, context={"request": request}).data,
            status=status.HTTP_201_CREATED,
        )


class LoanSchedulePreviewView(LoanViewMixin, APIView):
    required_permissions = {"post": "can_create_loans"}

    @extend_schema(request=LoanSerializer, tags=["Loans"])
    def post(self, request):
        serializer = LoanSerializer(data=request.data, context={"request": request})
        serializer.is_valid(raise_exception=True)
        loan = Loan(**serializer.validated_data)
        rows = LoanRepaymentScheduleService._build_schedule(loan)
        if request.query_params.get("download") == "csv":
            response = HttpResponse(content_type="text/csv; charset=utf-8")
            response["Content-Disposition"] = (
                'attachment; filename="loan-repayment-schedule.csv"'
            )
            response.write("\ufeff")
            writer = csv.writer(response)
            writer.writerow(
                [
                    "Installment",
                    "Due Date",
                    "Currency",
                    "Opening Principal",
                    "Principal",
                    "Interest",
                    "Payment",
                    "Closing Principal",
                ]
            )
            for row in rows:
                writer.writerow(
                    [
                        row["installation_number"],
                        row["due_date"].isoformat(),
                        loan.currency.currency.code,
                        row["opening_principal"],
                        row["principal_due"],
                        row["interest_due"],
                        row["principal_due"] + row["interest_due"],
                        row["opening_principal"] - row["principal_due"],
                    ]
                )
            return response
        principal_total = sum((row["principal_due"] for row in rows), Decimal("0"))
        interest_total = sum((row["interest_due"] for row in rows), Decimal("0"))
        paginator = CustomPageNumberPagination()
        page = paginator.paginate_queryset(rows, request)
        response = paginator.get_paginated_response(
            [
                {
                    "number": row["installation_number"],
                    "due_date": row["due_date"].isoformat(),
                    "opening_principal": str(row["opening_principal"]),
                    "principal": str(row["principal_due"]),
                    "interest": str(row["interest_due"]),
                    "payment": str(row["principal_due"] + row["interest_due"]),
                    "closing_principal": str(
                        row["opening_principal"] - row["principal_due"]
                    ),
                }
                for row in page
            ]
        )
        response.data["totals"] = {
            "principal": str(principal_total),
            "interest": str(interest_total),
            "payment": str(principal_total + interest_total),
        }
        response.data["currency"] = loan.currency.currency.code
        return response


class LoanDetailView(LoanViewMixin, APIView):
    required_permissions = {
        "get": "can_view_loans",
        "patch": "can_edit_loans",
        "delete": "can_delete_loans",
    }

    @extend_schema(responses=LoanSerializer, tags=["Loans"])
    def get(self, request, base_uuid):
        loan = self.get_loan(request, base_uuid)
        return Response(LoanSerializer(loan, context={"request": request}).data)

    @extend_schema(
        request=LoanSerializer,
        responses=LoanSerializer,
        tags=["Loans"],
    )
    @transaction.atomic
    def patch(self, request, base_uuid):
        loan = self.get_loan(request, base_uuid, lock=True)
        loan.ensure_no_ongoing_approval(attempted_action="update")
        before = LoanSerializer(loan, context={"request": request}).data
        serializer = LoanSerializer(
            loan, data=request.data, partial=True, context={"request": request}
        )
        serializer.is_valid(raise_exception=True)
        loan.approval_status = "under_update"
        loan = serializer.save()
        loan.confirm_update(**self.approval_context(request))
        loan.refresh_from_db()
        after = LoanSerializer(loan, context={"request": request}).data
        changes = {
            name: {"old": before.get(name), "new": after.get(name)}
            for name in serializer.validated_data
            if before.get(name) != after.get(name)
        }
        self.audit(
            request,
            loan,
            "UPDATE",
            f"Submitted update for loan {loan.reference_code}.",
            changes,
        )
        return Response(after)

    @extend_schema(responses={202: LoanSerializer, 204: None}, tags=["Loans"])
    @transaction.atomic
    def delete(self, request, base_uuid):
        loan = self.get_loan(request, base_uuid, lock=True)
        LoanService.validate_delete(loan)
        loan.confirm_delete(**self.approval_context(request))
        loan.refresh_from_db()
        self.audit(
            request,
            loan,
            "DELETE",
            f"Requested deletion of loan {loan.reference_code}.",
        )
        if loan.deleted_at is not None:
            return Response(status=status.HTTP_204_NO_CONTENT)
        return Response(
            LoanSerializer(loan, context={"request": request}).data,
            status=status.HTTP_202_ACCEPTED,
        )


class LoanRepaymentViewMixin(LoanViewMixin):
    def get_repayments(self, loan, *, lock=False):
        queryset = (
            LoanRepayment.objects.filter(loan=loan, deleted_at__isnull=True)
            .select_related("loan")
            .prefetch_related("allocations__repayment_schedule")
        )
        if lock:
            queryset = queryset.select_for_update(of=("self",))
        return queryset

    def audit_repayment(self, request, payment, action, description, changes=None):
        AuditLog.objects.create(
            content_type=ContentType.objects.get_for_model(LoanRepayment),
            object_id=payment.pk,
            action=action,
            user=request.user if request.user.is_authenticated else None,
            description=description,
            changes=serialize_value(changes) if changes is not None else None,
        )


class LoanRepaymentListCreateView(LoanRepaymentViewMixin, APIView, SearchOrderMixin):
    required_permissions = {"get": "can_view_loans", "post": "can_edit_loans"}

    @extend_schema(responses=LoanRepaymentSerializer(many=True), tags=["Loan Repayments"])
    def get(self, request, base_uuid):
        loan = self.get_loan(request, base_uuid)
        queryset = self.apply_ordering(self.apply_search(self.get_repayments(loan)))
        paginator = CustomPageNumberPagination()
        page = paginator.paginate_queryset(queryset, request)
        serializer = LoanRepaymentSerializer(
            page, many=True, context={"request": request, "loan": loan}
        )
        return paginator.get_paginated_response(serializer.data)

    @extend_schema(
        request=LoanRepaymentSerializer,
        responses={201: LoanRepaymentSerializer},
        tags=["Loan Repayments"],
    )
    @transaction.atomic
    def post(self, request, base_uuid):
        loan = self.get_loan(request, base_uuid, lock=True)
        context = {"request": request, "loan": loan}
        serializer = LoanRepaymentSerializer(data=request.data, context=context)
        serializer.is_valid(raise_exception=True)
        payment = serializer.save()
        payment.confirm_create(**self.approval_context(request))
        payment.refresh_from_db()
        self.audit_repayment(
            request,
            payment,
            "CREATE",
            f"Recorded repayment {payment.reference_code} of {payment.amount} "
            f"on loan {loan.reference_code}.",
        )
        return Response(
            LoanRepaymentSerializer(payment, context=context).data,
            status=status.HTTP_201_CREATED,
        )


class LoanRepaymentDetailView(LoanRepaymentViewMixin, APIView):
    required_permissions = {
        "get": "can_view_loans",
        "patch": "can_edit_loans",
        "delete": "can_edit_loans",
    }

    @extend_schema(responses=LoanRepaymentSerializer, tags=["Loan Repayments"])
    def get(self, request, base_uuid, repayment_uuid):
        loan = self.get_loan(request, base_uuid)
        payment = get_object_or_404(
            self.get_repayments(loan), base_uuid=repayment_uuid
        )
        return Response(
            LoanRepaymentSerializer(
                payment, context={"request": request, "loan": loan}
            ).data
        )

    @extend_schema(
        request=LoanRepaymentSerializer,
        responses=LoanRepaymentSerializer,
        tags=["Loan Repayments"],
    )
    @transaction.atomic
    def patch(self, request, base_uuid, repayment_uuid):
        loan = self.get_loan(request, base_uuid, lock=True)
        payment = get_object_or_404(
            self.get_repayments(loan, lock=True), base_uuid=repayment_uuid
        )
        payment.ensure_no_ongoing_approval(attempted_action="update")
        context = {"request": request, "loan": loan}
        before = LoanRepaymentSerializer(payment, context=context).data
        serializer = LoanRepaymentSerializer(
            payment, data=request.data, partial=True, context=context
        )
        serializer.is_valid(raise_exception=True)
        payment.approval_status = "under_update"
        payment = serializer.save()
        payment.confirm_update(**self.approval_context(request))
        payment.refresh_from_db()
        after = LoanRepaymentSerializer(payment, context=context).data
        changes = {
            name: {"old": before.get(name), "new": after.get(name)}
            for name in serializer.validated_data
            if name != "allocations" and before.get(name) != after.get(name)
        }
        if before.get("allocations") != after.get("allocations"):
            changes["allocations"] = {
                "old": before.get("allocations"),
                "new": after.get("allocations"),
            }
        self.audit_repayment(
            request,
            payment,
            "UPDATE",
            f"Submitted update for repayment {payment.reference_code}.",
            changes,
        )
        return Response(after)

    @extend_schema(
        responses={202: LoanRepaymentSerializer, 204: None}, tags=["Loan Repayments"]
    )
    @transaction.atomic
    def delete(self, request, base_uuid, repayment_uuid):
        loan = self.get_loan(request, base_uuid, lock=True)
        payment = get_object_or_404(
            self.get_repayments(loan, lock=True), base_uuid=repayment_uuid
        )
        payment.confirm_delete(**self.approval_context(request))
        payment.refresh_from_db()
        self.audit_repayment(
            request,
            payment,
            "DELETE",
            f"Requested deletion of repayment {payment.reference_code}.",
        )
        if payment.deleted_at is not None:
            return Response(status=status.HTTP_204_NO_CONTENT)
        return Response(
            LoanRepaymentSerializer(
                payment, context={"request": request, "loan": loan}
            ).data,
            status=status.HTTP_202_ACCEPTED,
        )


class LoanRepaymentAllocationPreviewView(LoanRepaymentViewMixin, APIView):
    required_permissions = {"post": "can_edit_loans"}

    @staticmethod
    def parse_uuid(value, field):
        try:
            return uuid.UUID(str(value))
        except (ValueError, AttributeError, TypeError):
            raise serializers.ValidationError({field: "Enter a valid identifier."})

    @staticmethod
    def serialize_line(item):
        balance, parts = item["balance"], item["parts"]
        schedule = balance["schedule"]
        return {
            "repayment_schedule": str(schedule.base_uuid),
            "installation_number": schedule.installation_number,
            "due_date": schedule.due_date.isoformat(),
            "principal_outstanding": str(balance["principal_outstanding"]),
            "interest_outstanding": str(balance["interest_outstanding"]),
            "fees_outstanding": str(balance["fees_outstanding"]),
            "principal_amount": str(parts["principal"]),
            "interest_amount": str(parts["interest"]),
            "fee_amount": str(parts["fees"]),
        }

    @extend_schema(tags=["Loan Repayments"])
    def post(self, request, base_uuid):
        loan = self.get_loan(request, base_uuid)
        LoanRepaymentService.validate_loan_ready(loan)

        payment = None
        if request.data.get("payment"):
            payment = get_object_or_404(
                self.get_repayments(loan),
                base_uuid=self.parse_uuid(request.data["payment"], "payment"),
            )

        first_schedule = None
        if request.data.get("repayment_schedule"):
            first_schedule = get_object_or_404(
                LoanRepaymentSchedule._base_manager.filter(
                    loan=loan, deleted_at__isnull=True
                ),
                base_uuid=self.parse_uuid(
                    request.data["repayment_schedule"], "repayment_schedule"
                ),
            )

        raw_amount = request.data.get("amount")
        if raw_amount in (None, "") and payment is not None:
            lines = LoanRepaymentService.payment_lines(loan, payment)
            unallocated = Decimal("0")
        else:
            try:
                amount = Decimal(str(raw_amount))
            except (InvalidOperation, TypeError, ValueError):
                amount = None
            if amount is None or not amount.is_finite() or amount <= 0:
                raise serializers.ValidationError(
                    {"amount": "Enter an amount greater than zero."}
                )
            lines, unallocated = LoanRepaymentService.suggest_allocations(
                loan,
                amount,
                first_schedule=first_schedule,
                exclude_payment_id=payment.pk if payment else None,
            )
        return Response(
            {
                "allocations": [self.serialize_line(item) for item in lines],
                "unallocated": str(unallocated),
            }
        )


class LoanScheduleView(LoanRepaymentViewMixin, APIView):
    required_permissions = {"get": "can_view_loans"}

    @extend_schema(tags=["Loans"])
    def get(self, request, base_uuid):
        loan = self.get_loan(request, base_uuid)
        rows, notice = LoanRepaymentScheduleService.get_loan_schedule(loan)
        paginator = CustomPageNumberPagination()
        page = paginator.paginate_queryset(rows, request)
        totals, described = LoanRepaymentService.schedule_overview(loan, rows, page)
        response = paginator.get_paginated_response(described)
        response.data["totals"] = totals
        response.data["currency"] = loan.currency.currency.code
        response.data["notice"] = notice
        return response