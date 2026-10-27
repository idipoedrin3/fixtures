from rest_framework.parsers import MultiPartParser, FormParser
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework import status
from drf_spectacular.utils import extend_schema, OpenApiParameter
from rest_framework.permissions import AllowAny
from django.contrib.contenttypes.models import ContentType
from institution.services import IdentityService
from utilities.openapi import (
    SEARCH_PARAM,
    ORDERING_PARAM,
    business_document_category_uuid_param,
    institution_role_uuid_param,
    parent_branch_base_uuid_param,
    branch_base_uuid_param_base,
)
from system.authentication import PartnerSystemAuthentication
from users.services import RoleAssignmentService
from utilities.helpers import (
    build_password_link,
    get_or_raise,
    send_password_link_to_user,
    create_and_institution_token,
    get_institution,
    parse_bool_query_param,
    serialize_value,
)
from users.models import ExternalIdentity, ProfileInstitution
from audit.models import AuditLog

from utilities.helpers import get_institution
from django.db import transaction
from datetime import timezone
from django.db.models import CharField, Q
from django.db.models import Func

from .models import (
    BranchSupportedCurrency,
    Institution,
    Branch,
    InstitutionBaisoftPayConfiguration,
    InstitutionNotificationSetting,
    InstitutionSupportedBankingInstitution,
    UserBranch,
    BusinessFinancialDocuments,
    BusinessDocumentCategory,
    InstitutionItemReturnReason,
    Announcement,
    AnnouncementTargetUser,
    UserAnnouncementAcknowledgment,
    AnnouncementTargetRole,
    Notes,
    InstitutionFeatureStatus,
    InstitutionSupportedCurrency,
    InstitutionReferenceSequence,
    BranchAdmin,
    InstitutionKYCDocument,
)
from users.serializers import (
    InstitutionStaffMemberSerializer,
    ProfileInstitutionSerializer,
)
from .serializers import (
    BranchSupportedCurrencySerializer,
    BranchSupportedCurrencyInputSerializer,
    InstitutionBaisoftPayConfigurationSerializer,
    InstitutionNotificationSettingInputSerializer,
    InstitutionNotificationSettingSerializer,
    InstitutionOwnerShipTransferSerializer,
    InstitutionSerializer,
    BranchSerializer,
    InstitutionSupportedBankingInstitutionSerializer,
    RecycleBinItemSerializer,
    UserBranchSerializer,
    BusinessFinancialDocumentsSerializer,
    BusinessDocumentCategorySerializer,
    InstitutionItemReturnReasonSerializer,
    ActSupraledgerActivationSerializer,
    AnnouncementSerializer,
    AnnouncementTargetUserSerializer,
    UserAnnouncementAcknowledgmentSerializer,
    AnnouncementTargetRoleSerializer,
    NoteSerializer,
    InstitutionFeatureStatusSerializer,
    InstitutionSupportedCurrencySerial,
    InstitutionSupportedBankingInstitutionSerializer,
    InstitutionReferenceSequenceSerializer,
    BranchAdminSerializer,
    InstitutionKYCDocumentSerializer,
)
from django.shortcuts import get_object_or_404
from system.services import BaisoftPayService, BaisoftPayServiceError
from .utils import (
    InstitutionCreationParser,
    generate_compliant_password,
)
from utilities.pagination import CustomPageNumberPagination
from django.db.models import Q
from rest_framework.parsers import JSONParser, FormParser, MultiPartParser
from system.exceptions import (
    SystemAuthenticationFailed,
    SystemNotFoundError,
    SystemPermissionDeniedError,
    SystemValidationError,
)
from utilities.helpers import get_institution, validation_error
from django.utils import timezone
from institution.utils import CurrencyConversionSerializer, get_model_from_name
from system.services import FxRateService
from rest_framework.exceptions import ValidationError
from utilities.mixin import SearchOrderMixin
from users.permissions import HasInstitutionPermission
from django.db.models import Q


class ActSupraledgerActivationView(APIView):
    permission_classes = [AllowAny]
    throttle_scope = "supraledger_activation"

    @extend_schema(
        request=ActSupraledgerActivationSerializer,
        description="Activate Supraledger for an institution.",
        summary="Activate Supraledger",
        tags=["Supra-Activation"],
    )
    def post(self, request):
        partner_auth_tuple = PartnerSystemAuthentication().authenticate(request)
        if not partner_auth_tuple:
            raise SystemAuthenticationFailed(
                detail="Invalid or missing API key.",
                status_code=status.HTTP_401_UNAUTHORIZED,
            )

        system = partner_auth_tuple[1]

        if not system.is_active:
            raise SystemPermissionDeniedError(
                detail="System is not active.",
                status_code=status.HTTP_403_FORBIDDEN,
            )

        serializer = ActSupraledgerActivationSerializer(
            data=request.data, context={"partner_system": system}
        )

        if not serializer.is_valid():
            raise SystemValidationError(
                detail=serializer.errors,
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            )

        instance = serializer.save()

        if instance.get("already_exists"):
            return Response(
                {
                    "message": "Institution already exists. Supraledger activation considered successful."
                },
                status=status.HTTP_200_OK,
            )

        return Response(serializer.data, status=status.HTTP_201_CREATED)


class InstitutionItemReturnReasonListView(APIView, SearchOrderMixin):

    permission_classes = [HasInstitutionPermission]
    required_permissions = {
        "get": "can_view_institution_item_return_reason",
        "post": "can_create_institution_item_return_reason",
    }

    queryset = InstitutionItemReturnReason.objects.undeleted()

    @extend_schema(
        request=InstitutionItemReturnReasonSerializer,
        responses={200: InstitutionItemReturnReasonSerializer(many=True)},
        description="Retrieve a list of all institution item return reasons for a specific institution.",
        summary="List all institution item return reasons by institution",
        tags=["Institution Return Reasons"],
        parameters=[
            SEARCH_PARAM,
            ORDERING_PARAM,
        ],
    )
    def get(self, request):
        institution = get_institution(request)

        if not institution:
            raise SystemNotFoundError(
                detail=f"Institution not found.",
                status_code=status.HTTP_404_NOT_FOUND,
            )

        return_reasons = self.queryset.filter(
            institution=institution,
        )

        return_reasons = self.apply_search(return_reasons)
        return_reasons = self.apply_ordering(return_reasons)
        return_reasons = self.apply_filters(return_reasons)

        paginator = CustomPageNumberPagination()
        paginator_qs = paginator.paginate_queryset(return_reasons, request)
        serializer = InstitutionItemReturnReasonSerializer(paginator_qs, many=True)
        return paginator.get_paginated_response(serializer.data)

    @extend_schema(
        request=InstitutionItemReturnReasonSerializer,
        responses={201: InstitutionItemReturnReasonSerializer},
        description="Create a new institution item return reason for a specific institution.",
        summary="Create a new institution item return reason by institution",
        tags=["Institution Return Reasons"],
    )
    def post(self, request):
        institution = get_institution(request)
        if not institution:
            raise SystemNotFoundError(
                detail=f"Institution not found.",
                status_code=status.HTTP_404_NOT_FOUND,
            )

        serializer = InstitutionItemReturnReasonSerializer(
            data=request.data,
            context={"request": request},
        )
        if serializer.is_valid():
            return_reason = serializer.save(institution=institution)
            AuditLog.objects.create(
                content_type=ContentType.objects.get_for_model(
                    InstitutionItemReturnReason
                ),
                object_id=return_reason.pk,
                action="CREATE",
                user=request.user,
                description=f"Created Institution Item Return Reason: {return_reason.return_reason_name}",
            )
            return_reason.confirm_create(
                profile_institution=request.profile_institution,
                external_identity=request.external_identity,
            )
            return Response(serializer.data, status=status.HTTP_201_CREATED)
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)


class InstitutionItemReturnReasonDetailView(APIView):

    permission_classes = [HasInstitutionPermission]
    required_permissions = {
        "get": "can_view_institution_item_return_reason",
        "patch": "can_edit_institution_item_return_reason",
        "delete": "can_delete_institution_item_return_reason",
    }

    def get_return_reason_object(self, base_uuid, request):
        institution = get_institution(request)

        return get_or_raise(
            queryset=InstitutionItemReturnReason.objects.undeleted(),
            message=f"Institution Item return reason with UUID {base_uuid} not found",
            base_uuid=base_uuid,
            institution=institution,
        )

    @extend_schema(
        responses={200: InstitutionItemReturnReasonSerializer},
        description="Retrieve details of a specific institution item return reason.",
        summary="Get institution item return reason details",
        tags=["Institution Return Reasons"],
    )
    def get(self, request, base_uuid):

        return_reason = self.get_return_reason_object(base_uuid, request)

        if not return_reason:
            return SystemNotFoundError(status_code=status.HTTP_404_NOT_FOUND)

        serializer = InstitutionItemReturnReasonSerializer(return_reason)
        return Response(serializer.data)

    @extend_schema(
        request=InstitutionItemReturnReasonSerializer,
        responses={200: InstitutionItemReturnReasonSerializer},
        description="Partially update details of a specific institution item return reason.",
        summary="Partially update institution item return reason details",
        tags=["Institution Return Reasons"],
    )
    def patch(self, request, base_uuid):
        return_reason = self.get_return_reason_object(base_uuid, request)
        old_data = InstitutionItemReturnReasonSerializer(return_reason).data
        serializer = InstitutionItemReturnReasonSerializer(
            return_reason,
            data=request.data,
            partial=True,
            context={
                "institution": get_institution(request),
                "request": request,
            },
        )
        if serializer.is_valid():
            updated_return_reason = serializer.save()

            new_data = InstitutionItemReturnReasonSerializer(updated_return_reason).data
            changes = {
                key: {"old": old_data.get(key), "new": new_data.get(key)}
                for key in request.data.keys()
                if old_data.get(key) != new_data.get(key)
            }

            AuditLog.objects.create(
                content_type=ContentType.objects.get_for_model(
                    InstitutionItemReturnReason
                ),
                object_id=updated_return_reason.id,
                action="UPDATE",
                user=request.user,
                changes=changes,
                description=f"Updated institution item return reason {updated_return_reason.return_reason_name} ({updated_return_reason.base_uuid})",
            )
            return Response(serializer.data)
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

    @extend_schema(
        responses={204: None},
        description="Delete a specific  institution item return reason.",
        summary="Delete a  institution item return reason",
        tags=["Institution Return Reasons"],
    )
    def delete(self, request, base_uuid):
        return_reason = self.get_return_reason_object(base_uuid, request)

        return_reason_data = InstitutionItemReturnReasonSerializer(return_reason).data
        return_reason_id = return_reason.id

        return_reason.delete()

        AuditLog.objects.create(
            content_type=ContentType.objects.get_for_model(InstitutionItemReturnReason),
            object_id=return_reason_id,
            action="DELETE",
            user=request.user,
            changes=return_reason_data,
            description=f"Deleted institution item return reason {return_reason_data['return_reason_name']} ({base_uuid})",
        )
        return Response(status=status.HTTP_204_NO_CONTENT)


class InstitutionListAPIView(APIView):

    parser_classes = [InstitutionCreationParser, JSONParser]
    # permission_classes = [HasInstitutionPermission]
    # required_permissions = {
    # "get": "can_view_institution",
    # "post": "can_create_institution",
    # }

    @extend_schema(
        request=InstitutionSerializer,
        responses={201: InstitutionSerializer},
        description="Create a new institution with name, address, and owner.",
        summary="Create a new institution",
        tags=["Institution Management"],
    )
    @transaction.atomic()
    def post(self, request):
        # if Institution.objects.filter(
        #     institution_owner__id=request.data.get("institution_owner_id"),
        #     institution_name=request.data.get("institution_name"),
        # ).exists():
        #     return Response(
        #         {"detail": "User Already has an Institution with the same name."},
        #         status=status.HTTP_409_CONFLICT,
        #     )

        print(
            "\n\n-------------------------------------------------------------------------"
        )

        print("request.data", request.data)

        print(
            "-------------------------------------------------------------------------\n\n"
        )

        serializer = InstitutionSerializer(
            data=request.data, context={"request": request}
        )
        if serializer.is_valid():
            # pass

            institution = serializer.save()
            institution.create_default_role()
            return Response(
                InstitutionSerializer(institution).data,
                status=status.HTTP_201_CREATED,
            )

        return Response(
            {"detail": serializer.errors}, status=status.HTTP_400_BAD_REQUEST
        )

    @extend_schema(
        responses={200: InstitutionSerializer(many=True)},
        description="Retrieve all institutions.",
        summary="Get all institutions",
        tags=["Institution Management"],
    )
    def get(
        self,
        request,
    ):

        return Response(
            {"detail": "Resource not found."},
            status=status.HTTP_501_NOT_IMPLEMENTED,
        )

        if request.user.is_staff:
            institutions = Institution.objects.all()
        else:
            institutions = Institution.objects.filter(institution_owner=request.user)
        serializer = InstitutionSerializer(institutions, many=True)
        return Response(serializer.data)


class InstitutionDetailAPIView(APIView):

    parser_classes = [JSONParser, FormParser, MultiPartParser]
    # permission_classes = [HasInstitutionPermission]
    # required_permissions = {
    #     "get": "can_view_institution",
    #     "patch": "can_edit_institution",
    #     "delete": "can_delete_institution",
    # }

    @extend_schema(
        responses={200: InstitutionSerializer},
        description="Retrieve an institution.",
        summary="Get an institution",
        tags=["Institution Management"],
    )
    def get(self, request, institution_uuid):
        institution = Institution.objects.get(base_uuid=institution_uuid)

        if not institution:
            raise validation_error("Institution Not Found")

        serializer = InstitutionSerializer(institution)
        return Response(serializer.data)

    @extend_schema(
        request=InstitutionSerializer,
        responses={200: InstitutionSerializer},
        description="Update an existing institution.",
        summary="Update an institution",
        tags=["Institution Management"],
    )
    def patch(self, request, institution_uuid):

        try:
            institution = Institution.objects.get(base_uuid=institution_uuid)
        except Institution.DoesNotExist:
            return SystemNotFoundError(
                detail=f"Institution not found.", status_code=status.HTTP_404_NOT_FOUND
            )

        serializer = InstitutionSerializer(
            institution,
            data=request.data,
            partial=True,
            context={"request": request},
        )

        if serializer.is_valid():
            updated_institution = serializer.save()

            from system.tasks import notify_external_system_task

            notify_external_system_task.delay(
                profile_institution_id=request.profile_institution.id,
                resource_type="institution",
                action="update",
                payload={
                    "external_base_uuid": serialize_value(
                        updated_institution.base_uuid
                    ),
                    "internal_base_uuid": serialize_value(
                        updated_institution.external_base_uuid
                    ),
                    "theme_color": updated_institution.theme_color,
                    "institution_name": updated_institution.institution_name,
                    "first_phone_number": updated_institution.first_phone_number,
                    "second_phone_number": updated_institution.second_phone_number,
                    "user_inactivity_time": updated_institution.user_inactivity_time,
                    "date_format": updated_institution.date_format,
                    "default_pagination_page_size": updated_institution.default_pagination_page_size,
                    "location": updated_institution.location,
                },
            )

            return Response(serializer.data)
        return Response(
            {"detail": serializer.errors}, status=status.HTTP_400_BAD_REQUEST
        )

    @extend_schema(
        responses={204: None},
        description="Delete an existing institution.",
        summary="Delete as institution",
        tags=["Institution Management"],
    )
    def delete(self, request, institution_id):
        try:
            institution = Institution.objects.get(id=institution_id)
            if institution.institution_owner != request.user:
                return Response({"detail": "Access denied."}, status=403)
            institution.delete()
            return Response(status=status.HTTP_204_NO_CONTENT)
        except Institution.DoesNotExist:
            return SystemNotFoundError(
                detail=f"Institution not found.", status_code=status.HTTP_404_NOT_FOUND
            )


class BranchListAPIView(SearchOrderMixin, APIView):

    permission_classes = [HasInstitutionPermission]
    required_permissions = {
        "get": "can_view_branch",
        "post": "can_create_branch",
    }

    @extend_schema(
        request=BranchSerializer,
        responses={201: BranchSerializer},
        description="Create a new branch.",
        summary="Create a new branch",
        tags=["Branch Management"],
    )
    def post(self, request):
        serializer = BranchSerializer(data=request.data, context={"request": request})
        if serializer.is_valid():
            branch = serializer.save()

            if request.should_notify:
                from system.tasks import notify_external_system_task

                notify_external_system_task.delay(
                    profile_institution_id=request.profile_institution.id,
                    resource_type="institution_branches",
                    action="create",
                    payload={
                        "branch_name": branch.branch_name,
                        "branch_phone_number": branch.branch_phone_number,
                        "branch_location": branch.branch_location,
                        "branch_email": branch.branch_email,
                        "branch_opening_time": serialize_value(
                            branch.branch_opening_time
                        ),
                        "branch_closing_time": serialize_value(
                            branch.branch_closing_time
                        ),
                        "branch_latitude": serialize_value(branch.branch_latitude),
                        "branch_longitude": serialize_value(branch.branch_longitude),
                        "external_base_uuid": serialize_value(branch.base_uuid),
                    },
                )

            return Response(
                BranchSerializer(branch, context={"request": request}).data,
                status=status.HTTP_201_CREATED,
            )

        return Response(
            {"detail": serializer.errors}, status=status.HTTP_400_BAD_REQUEST
        )

    @extend_schema(
        responses={200: BranchSerializer(many=True)},
        description="Retrieve branches filtered by parent branch or top-level branches.",
        summary="Get all branches",
        tags=["Branch Management"],
        parameters=[
            SEARCH_PARAM,
            ORDERING_PARAM,
            parent_branch_base_uuid_param(),
            OpenApiParameter(
                name="has_expenses",
                required=False,
                description="Filter branches by whether they have undeleted expenses.",
                type=bool,
                location=OpenApiParameter.QUERY,
            ),
            OpenApiParameter(
                name="has_requisitions",
                required=False,
                description=(
                    "Filter branches by whether they are attached to at least "
                    "one active requisition in the current institution."
                ),
                type=bool,
                location=OpenApiParameter.QUERY,
            ),
        ],
    )
    def get(self, request):
        institution = get_institution(request)
        if not institution:
            raise SystemNotFoundError(
                detail="Institution not found.",
                status_code=status.HTTP_404_NOT_FOUND,
            )

        parent_base_uuid = request.query_params.get("parent_base_uuid", None)
        has_expenses = parse_bool_query_param(
            request.query_params.get("has_expenses"),
            "has_expenses",
        )
        has_requisitions = parse_bool_query_param(
            request.query_params.get("has_requisitions"),
            "has_requisitions",
        )

        parent_branch = (
            get_object_or_404(
                Branch,
                base_uuid=parent_base_uuid,
                deleted_at__isnull=True,
                institution=institution,
            )
            if parent_base_uuid
            else None
        )

        if parent_branch:
            if parent_branch.branch_type in ["BRANCH", "DIVISION"]:
                raise validation_error(
                    "Branches of type BRANCH or DIVISION cannot have sub branches."
                )

            branches = Branch.objects.filter(
                institution=institution,
                parent=parent_branch,
                deleted_at__isnull=True,
            )

        else:
            branches = Branch.objects.filter(
                institution=institution,
                parent__isnull=True,
                deleted_at__isnull=True,
            )

        if has_expenses is True:
            branches = branches.filter(
                expenses__deleted_at__isnull=True,
                expenses__institution=institution,
            ).distinct()
        elif has_expenses is False:
            branches = branches.exclude(
                expenses__deleted_at__isnull=True,
                expenses__institution=institution,
            )

        if has_requisitions is True:
            branches = branches.filter(
                requisition__deleted_at__isnull=True,
                requisition__requisition_type__institution=institution,
            ).distinct()
        elif has_requisitions is False:
            branches = branches.exclude(
                requisition__deleted_at__isnull=True,
                requisition__requisition_type__institution=institution,
            )

        branches = self.apply_search(branches)
        branches = self.apply_ordering(branches)

        paginator = CustomPageNumberPagination()
        paginator_qs = paginator.paginate_queryset(branches, request)
        serializer = BranchSerializer(
            paginator_qs,
            many=True,
            context={"request": request},
        )
        return paginator.get_paginated_response(serializer.data)


class BranchDetailAPIView(APIView):

    permission_classes = [HasInstitutionPermission]
    required_permissions = {
        "get": "can_view_branch",
        "patch": "can_edit_branch",
        "delete": "can_delete_branch",
    }

    @extend_schema(
        responses={200: BranchSerializer},
        description="Retrieve a branch.",
        summary="Get a branch",
        tags=["Branch Management"],
    )
    def get(self, request, branch_base_uuid):
        try:
            branch = Branch.objects.get(base_uuid=branch_base_uuid)
            if (
                not request.user.is_staff
                and branch.institution.institution_owner != request.user
            ):
                return Response({"detail": "Access denied."}, status=403)
            serializer = BranchSerializer(branch)
            return Response(serializer.data)
        except Branch.DoesNotExist:
            return SystemNotFoundError(
                detail=f"Branch not found.", status_code=status.HTTP_404_NOT_FOUND
            )

    @extend_schema(
        request=BranchSerializer,
        responses={200: BranchSerializer},
        description="Update an existing branch.",
        summary="Update a branch",
        tags=["Branch Management"],
    )
    def patch(self, request, branch_base_uuid):
        print(request.data)
        try:
            branch = Branch.objects.get(base_uuid=branch_base_uuid)
            if (
                not request.user.is_staff
                and branch.institution.institution_owner != request.user
            ):
                return Response({"detail": "Access denied."}, status=403)
        except Branch.DoesNotExist:
            return SystemNotFoundError(
                detail=f"Branch not found.", status_code=status.HTTP_404_NOT_FOUND
            )

        final_data = serialize_value(request.data)

        print(final_data)

        serializer = BranchSerializer(
            branch, data=final_data, partial=True, context={"request": request}
        )

        if serializer.is_valid():
            serializer.save()

            # NOTE : Since provision to act to act on some things will be disable if institution is integrated, theres no need to send updated data
            # get updated model object
            # obj = serializer.instance

            # from system.utils import notify_external_system

            # notify_external_system(
            #     request,
            #     resource_type="institution_branches",
            #     action="update",
            #     payload={
            #         "branch_name": obj.branch_name,
            #         "branch_phone_number": obj.branch_phone_number,
            #         "branch_location": obj.branch_location,
            #         "branch_email": obj.branch_email,
            #         "branch_opening_time": obj.branch_opening_time,
            #         "branch_closing_time": obj.branch_closing_time,
            #         "external_base_uuid": serialize_value(obj.external_base_uuid),
            #     },
            # )

            return Response(serializer.data)

        return Response(
            {"detail": serializer.errors}, status=status.HTTP_400_BAD_REQUEST
        )

    @extend_schema(
        responses={204: None},
        description="Delete an existing branch.",
        summary="Delete a branch",
        tags=["Branch Management"],
    )
    def delete(self, request, branch_base_uuid):
        try:
            branch = Branch.objects.get(base_uuid=branch_base_uuid)
            if (
                not request.user.is_staff
                and branch.institution.institution_owner != request.user
            ):
                return Response({"detail": "Access denied."}, status=403)
            branch.delete()

            from system.tasks import notify_external_system_task

            notify_external_system_task.delay(
                profile_institution_id=request.profile_institution.id,
                resource_type="institution_branches",
                action="delete",
                payload={
                    "external_base_uuid": serialize_value(branch.base_uuid),
                    "internal_base_uuid": serialize_value(branch.external_base_uuid),
                },
            )

            return Response(status=status.HTTP_204_NO_CONTENT)
        except Branch.DoesNotExist:
            return SystemNotFoundError(
                detail=f"Branch with UUID {branch_base_uuid} not found.",
                status_code=status.HTTP_404_NOT_FOUND,
            )


class UserProfileListAPIView(APIView):
    @extend_schema(
        summary="List user profiles",
        description=(
            "Retrieve a paginated list of user profiles belonging to the current "
            "institution. Access is restricted to institution owners, staff users, "
            "or users whose profile belongs to the institution."
        ),
        tags=["Institution User Management"],
        responses={
            200: ProfileInstitutionSerializer(many=True),
        },
        parameters=[
            SEARCH_PARAM,
            ORDERING_PARAM,
            institution_role_uuid_param(required=False),
            OpenApiParameter(
                name="permission_code",
                required=False,
                description=(
                    "Filter profiles by a specific permission code. Returns profiles "
                    "that have the specified permission through their assigned roles."
                ),
                type=str,
            ),
            OpenApiParameter(
                name="has_ever_initiated_a_requisition",
                required=False,
                description=(
                    "Filter profiles by whether they have ever initiated a requisition. Returns profiles "
                    "that have initiated at least one requisition if set to true, or profiles that have never "
                    "initiated a requisition if set to false."
                ),
                type=bool,
            ),
            OpenApiParameter(
                name="without_requisition_beneficiary",
                required=False,
                description=(
                    "When true, return only institution profiles that are not "
                    "linked to a requisition beneficiary."
                ),
                type=bool,
                location=OpenApiParameter.QUERY,
            ),
        ],
    )
    def get(self, request):
        search = request.query_params.get("search", "").strip()
        permission_code = request.query_params.get("permission_code", None)
        has_ever_initiated_a_requisition = parse_bool_query_param(
            request.query_params.get("has_ever_initiated_a_requisition"),
            "has_ever_initiated_a_requisition",
        )
        without_requisition_beneficiary = parse_bool_query_param(
            request.query_params.get("without_requisition_beneficiary"),
            "without_requisition_beneficiary",
        )

        role_uuid = request.query_params.get("institution_role_uuid", None)

        institution = get_institution(request)

        profiles = (
            ProfileInstitution.objects.active()
            .filter(institution=institution)
            .prefetch_related("user_permissions__permission")
        )

        if without_requisition_beneficiary is True:
            profiles = profiles.filter(requisition_beneficiary_id__isnull=True)

        if has_ever_initiated_a_requisition is True:
            profiles = profiles.filter(
                allowed_user_links__requested_requisitions__requisition_type__institution=institution,
            ).distinct()
        elif has_ever_initiated_a_requisition is False:
            profiles = profiles.exclude(
                allowed_user_links__requested_requisitions__requisition_type__institution=institution,
            )

        if permission_code:
            profiles = profiles.filter(
                Q(user_permissions__permission__permission_code=permission_code)
                | Q(profile__user=institution.institution_owner)
                | Q(
                    profile__user__user_roles__role__permissions__permission__permission_code=permission_code
                )
            ).distinct()

        if role_uuid:
            profiles = profiles.filter(
                institution=institution,
                profile__user__user_roles__role__base_uuid=role_uuid,
                profile__user__user_roles__role__institution=institution,
            ).distinct()

        if search:
            for token in search.split():
                profiles = profiles.filter(
                    Q(profile__user__fullname__icontains=token)
                    | Q(profile__user__email__icontains=token)
                )

        paginator = CustomPageNumberPagination()
        paginator_qs = paginator.paginate_queryset(profiles, request)
        serializer = ProfileInstitutionSerializer(
            paginator_qs,
            many=True,
        )
        return paginator.get_paginated_response(serializer.data)

    @extend_schema(
        request=InstitutionStaffMemberSerializer,
        responses={201: ProfileInstitutionSerializer},
        description=(
            "Create a new user and profile within the institution. "
            "A temporary password is generated and a password setup link "
            "is emailed to the user."
        ),
        summary="Create a new user profile",
        tags=["Institution User Management"],
    )
    def post(self, request):
        institution = get_institution(request)
        serializer = InstitutionStaffMemberSerializer(
            data=request.data, context={"request": request}
        )
        serializer.is_valid(raise_exception=True)
        validated_data = serializer.validated_data

        with transaction.atomic():
            user = IdentityService.get_or_create_user(
                email=validated_data.get("email"),
                username=validated_data.get("username"),
                phone_number=validated_data.get("phone_number"),
                defaults={
                    "fullname": validated_data["fullname"],
                    "is_active": True,
                },
            )

            if not user.has_usable_password():
                user.set_password(generate_compliant_password())
                user.save(update_fields=["password"])

            profile = IdentityService.ensure_profile(user)

            profile_institution, _ = IdentityService.ensure_profile_institution(
                profile=profile,
                institution=institution,
            )

            profile_institution.bio = validated_data.get("bio", "")
            profile_institution.save(update_fields=["bio"])

            branches = validated_data.get("branches", [])

            UserBranch.objects.bulk_create(
                [UserBranch(user=user, branch=branch) for branch in branches]
            )

            RoleAssignmentService.assign_institution_role(
                user=user, role=validated_data["role"]
            )

            token = create_and_institution_token(
                user=user, purpose="registration", expiry_minutes=15
            )
            password_link = build_password_link(request=request, token=token)
            send_password_link_to_user(user=user, link=password_link)

            return Response(
                ProfileInstitutionSerializer(
                    profile_institution, context={"request": request}
                ).data,
                status=status.HTTP_201_CREATED,
            )


class InstitutionUserProfileUpdateMixin:
    def update_profile(self, request, profile_institution):
        serializer = InstitutionStaffMemberSerializer(
            profile_institution,
            data=request.data,
            partial=True,
            context={"request": request},
        )
        serializer.is_valid(raise_exception=True)
        profile_institution = serializer.save()

        return Response(
            ProfileInstitutionSerializer(
                profile_institution,
                context={"request": request},
            ).data
        )


class ExternalInstitutionUserProfileAPIView(
    InstitutionUserProfileUpdateMixin,
    APIView,
):
    @extend_schema(
        request=InstitutionStaffMemberSerializer,
        responses={200: ProfileInstitutionSerializer},
        tags=["Institution User Management"],
        description=(
            "Update an external user's profile within the institution. "
            "This endpoint is used to update the profile of a user who is not "
            "directly associated with the institution but has been granted access."
        ),
        summary="Update external user profile",
    )
    def patch(self, request, base_uuid):
        institution = get_institution(request)

        external_identity = (
            ExternalIdentity.objects.select_related("user")
            .filter(
                base_uuid=base_uuid,
                institution=institution,
                is_active=True,
            )
            .first()
        )
        if not external_identity:
            raise SystemNotFoundError(
                detail="External identity not found.",
                status_code=status.HTTP_404_NOT_FOUND,
            )

        profile_institution = (
            ProfileInstitution.objects.active()
            .filter(
                institution=institution,
                profile__user=external_identity.user,
            )
            .first()
        )

        if not profile_institution:
            raise SystemNotFoundError(
                detail="Institution user profile not found.",
                status_code=status.HTTP_404_NOT_FOUND,
            )

        return self.update_profile(request, profile_institution)


class InstitutionUserProfileAPIView(
    InstitutionUserProfileUpdateMixin,
    APIView,
):
    def get_profile(self, request, base_uuid):
        try:
            return ProfileInstitution.objects.active().get(
                base_uuid=base_uuid,
                institution=get_institution(request),
            )
        except ProfileInstitution.DoesNotExist:
            raise SystemNotFoundError(
                detail="Institution user profile not found.",
                status_code=status.HTTP_404_NOT_FOUND,
            )

    @extend_schema(
        responses={200: ProfileInstitutionSerializer},
        description="Retrieve details of a specific institution user profile.",
        summary="Get institution user profile details",
        tags=["Institution User Management"],
    )
    def get(self, request, base_uuid):
        institution_profile = self.get_profile(request, base_uuid)
        serializer = ProfileInstitutionSerializer(
            institution_profile,
            context={"request": request},
        )
        return Response(serializer.data)

    @extend_schema(
        request=InstitutionStaffMemberSerializer,
        responses={200: ProfileInstitutionSerializer},
        description="Update a institution user's profile (partial update).",
        summary="Update institution user details",
        tags=["Institution User Management"],
    )
    def patch(self, request, base_uuid):
        institution_profile = self.get_profile(request, base_uuid)
        return self.update_profile(request, institution_profile)

    @extend_schema(
        responses={204: None},
        description="Deactivate an institution user's profile.",
        summary="Deactivate institution user profile",
        tags=["Institution User Management"],
    )
    def delete(self, request, base_uuid):
        institution_profile = self.get_profile(request, base_uuid)
        institution_profile.delete()

        return Response(status=status.HTTP_204_NO_CONTENT)


class InstitutionUserSignatureResetAPIView(APIView):
    permission_classes = [HasInstitutionPermission]
    required_permissions = {"delete": "can_edit_user"}

    @extend_schema(
        responses={204: None},
        description="Reset a user's signature for the current institution.",
        summary="Reset institution user signature",
        tags=["Institution User Management"],
    )
    @transaction.atomic
    def delete(self, request, base_uuid):
        institution_profile = get_object_or_404(
            ProfileInstitution.objects.select_for_update(),
            base_uuid=base_uuid,
            institution=get_institution(request),
            is_active=True,
        )
        institution_profile.signature_base64 = None
        institution_profile.save(update_fields=["signature_base64"])
        return Response(status=status.HTTP_204_NO_CONTENT)


class InstitutionUserProfilePhotoResetAPIView(APIView):
    permission_classes = [HasInstitutionPermission]
    required_permissions = {"delete": "can_edit_user"}

    @extend_schema(
        responses={204: None},
        description="Reset a user's profile picture for the current institution.",
        summary="Reset institution user profile picture",
        tags=["Institution User Management"],
    )
    @transaction.atomic
    def delete(self, request, base_uuid):
        institution_profile = get_object_or_404(
            ProfileInstitution.objects.select_for_update(),
            base_uuid=base_uuid,
            institution=get_institution(request),
            is_active=True,
        )
        institution_profile.profile_photo_base64 = None
        institution_profile.save(update_fields=["profile_photo_base64"])
        return Response(status=status.HTTP_204_NO_CONTENT)


class UserBranchListCreateView(APIView):

    permission_classes = [HasInstitutionPermission]
    required_permissions = {
        "get": "can_view_user_branch",
        "post": "can_create_user_branch",
    }

    @extend_schema(
        request=UserBranchSerializer,
        responses={201: UserBranchSerializer},
        description="Create a new user-branch relationship.",
        summary="Create a new user-branch relationship",
        tags=["User Management"],
    )
    def post(self, request):
        serializer = UserBranchSerializer(
            data=request.data, context={"request": request}
        )
        if serializer.is_valid():
            user_branch = serializer.save()
            return Response(
                UserBranchSerializer(user_branch).data,
                status=status.HTTP_201_CREATED,
            )
        return Response(
            {"detail": serializer.errors}, status=status.HTTP_400_BAD_REQUEST
        )

    @extend_schema(
        responses={200: UserBranchSerializer(many=True)},
        description="Retrieve all user-branch relationships.",
        summary="Get all user-branch relationships",
        tags=["User Management"],
    )
    def get(self, request):
        user_branches = UserBranch.objects.all()
        serializer = UserBranchSerializer(user_branches, many=True)
        return Response(serializer.data)


class UserBranchDetailAPIView(APIView):

    permission_classes = [HasInstitutionPermission]
    required_permissions = {
        "get": "can_view_user_branch",
        "patch": "can_edit_user_branch",
        "delete": "can_delete_user_branch",
    }

    @extend_schema(
        responses={200: UserBranchSerializer},
        description="Retrieve a user-branch relationship.",
        summary="Get a user-branch relationship",
        tags=["User Management"],
    )
    def get(self, request, base_uuid):
        try:
            user_branch = UserBranch.objects.get(base_uuid=base_uuid)
            serializer = UserBranchSerializer(user_branch)
            return Response(serializer.data)
        except UserBranch.DoesNotExist:
            return SystemNotFoundError(
                detail=f"User-branch relationship not found.",
                status_code=status.HTTP_404_NOT_FOUND,
            )

    @extend_schema(
        request=UserBranchSerializer,
        responses={200: UserBranchSerializer},
        description="Update an existing user-branch relationship.",
        summary="Update a user-branch relationship",
        tags=["User Management"],
    )
    def patch(self, request, base_uuid):
        user_branch = get_object_or_404(UserBranch, base_uuid=base_uuid)
        serializer = UserBranchSerializer(user_branch, data=request.data, partial=True)
        if serializer.is_valid():
            serializer.save()
            return Response(serializer.data)
        return Response(
            {"detail": serializer.errors}, status=status.HTTP_400_BAD_REQUEST
        )


class UserBranchDeleteByIdsAPIView(APIView):
    permission_classes = [HasInstitutionPermission]
    required_permissions = {
        "delete": "can_delete_user_branch",
    }

    @extend_schema(
        responses={204: None},
        description="Delete an existing user-branch relationship by user and branch IDs.",
        summary="Delete a user-branch relationship by user and branch",
        tags=["User Management"],
    )
    def delete(self, request, user_id, branch_id):
        try:
            user_branch = UserBranch.objects.get(user_id=user_id, branch_id=branch_id)
            user_branch.delete()
            return Response(status=status.HTTP_204_NO_CONTENT)
        except UserBranch.DoesNotExist:
            raise SystemNotFoundError(
                detail=f"User-branch relationship not found.",
                status_code=status.HTTP_404_NOT_FOUND,
            )


class BusinessFinancialDocumentsListCreateView(APIView, SearchOrderMixin):
    permission_classes = [HasInstitutionPermission]
    required_permissions = {
        "get": "can_view_business_financial_document",
        "post": "can_create_business_financial_document",
    }

    queryset = BusinessFinancialDocuments.objects.undeleted()

    @extend_schema(
        responses={200: BusinessFinancialDocumentsSerializer(many=True)},
        description="List business financial documents belonging to the institution.",
        summary="List Financial Documents",
        tags=["Business Financial Documents"],
        parameters=[
            SEARCH_PARAM,
            ORDERING_PARAM,
            branch_base_uuid_param_base(required=False),
            business_document_category_uuid_param(required=False),
        ],
    )
    def get(self, request):
        branch_base_uuid = request.query_params.get("branch_base_uuid")

        category_base_uuid = request.query_params.get(
            "business_document_category_base_uuid"
        )

        institution = get_institution(request)

        base_filter = Q(category__institution=institution, deleted_at__isnull=True)

        document_filter = Q()

        if branch_base_uuid:
            document_filter = Q(branch__base_uuid=branch_base_uuid)

        if category_base_uuid:
            category = get_or_raise(
                queryset=BusinessDocumentCategory.objects.undeleted(),
                message=f"Business document category with base_uuid {category_base_uuid} not found.",
                base_uuid=category_base_uuid,
            )
            document_filter &= Q(category=category)

        documents_qs = BusinessFinancialDocuments.objects.filter(
            base_filter & document_filter
        )

        documents_qs = self.apply_search(documents_qs)
        documents_qs = self.apply_ordering(documents_qs)
        documents_qs = self.apply_filters(documents_qs)

        paginator = CustomPageNumberPagination()
        paginated_qs = paginator.paginate_queryset(documents_qs, request)

        serializer = BusinessFinancialDocumentsSerializer(paginated_qs, many=True)
        return paginator.get_paginated_response(serializer.data)

    @extend_schema(
        request=BusinessFinancialDocumentsSerializer,
        responses={201: BusinessFinancialDocumentsSerializer},
        description="Create a new business financial document.",
        summary="Create Financial Document",
        tags=["Business Financial Documents"],
    )
    def post(self, request):
        serializer = BusinessFinancialDocumentsSerializer(
            data=request.data,
            context={"request": request},
        )
        if serializer.is_valid():
            document = serializer.save()
            AuditLog.objects.create(
                content_type=ContentType.objects.get_for_model(
                    BusinessFinancialDocuments
                ),
                object_id=document.pk,
                action="CREATE",
                user=request.user,
                description=f"Created Financial Document: {document.name}",
            )
            document.confirm_create(
                profile_institution=request.profile_institution,
                external_identity=request.external_identity,
            )
            return Response(serializer.data, status=status.HTTP_201_CREATED)
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)


class BusinessFinancialDocumentsDetailView(APIView):
    permission_classes = [HasInstitutionPermission]
    required_permissions = {
        "get": "can_view_business_financial_document",
        "patch": "can_edit_business_financial_document",
        "delete": "can_delete_business_financial_document",
    }

    def _get_object(self, base_uuid):
        return get_object_or_404(
            BusinessFinancialDocuments.objects.undeleted(),
            base_uuid=base_uuid,
            category__institution=get_institution(self.request),
        )

    @extend_schema(
        responses={200: BusinessFinancialDocumentsSerializer},
        description="Retrieve a specific business financial document.",
        summary="Retrieve Financial Document",
        tags=["Business Financial Documents"],
    )
    def get(self, request, base_uuid):
        document = self._get_object(base_uuid)
        serializer = BusinessFinancialDocumentsSerializer(document)
        return Response(serializer.data)

    @extend_schema(
        request=BusinessFinancialDocumentsSerializer,
        responses={200: BusinessFinancialDocumentsSerializer},
        description="Update a business financial document.",
        summary="Update Financial Document",
        tags=["Business Financial Documents"],
    )
    def patch(self, request, base_uuid):
        document = self._get_object(base_uuid)

        document.approval_status = "under_update"

        old_data = BusinessFinancialDocumentsSerializer(document).data

        serializer = BusinessFinancialDocumentsSerializer(
            document, data=request.data, partial=True
        )

        if serializer.is_valid():
            document = serializer.save()

            new_data = BusinessFinancialDocumentsSerializer(document).data

            changes = {
                key: {"old": old_data.get(key), "new": new_data.get(key)}
                for key in request.data.keys()
                if old_data.get(key) != new_data.get(key)
            }

            AuditLog.objects.create(
                content_type=ContentType.objects.get_for_model(
                    BusinessFinancialDocuments
                ),
                object_id=document.pk,
                action="UPDATE",
                user=request.user,
                changes=changes,
                description=f"Updated Financial Document: {document.name}",
            )
            document.confirm_update(
                profile_institution=request.profile_institution,
                external_identity=request.external_identity,
            )
            return Response(serializer.data)
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

    @extend_schema(
        responses={204: None},
        description="Soft-delete a business financial document (marks for deletion).",
        summary="Delete Financial Document",
        tags=["Business Financial Documents"],
    )
    def delete(self, request, base_uuid):
        document = self._get_object(base_uuid)

        document.approval_status = "under_deletion"
        document.save(update_fields=["approval_status"])

        AuditLog.objects.create(
            content_type=ContentType.objects.get_for_model(BusinessFinancialDocuments),
            object_id=document.pk,
            action="DELETE",
            user=request.user,
            description=f"Marked Financial Document for deletion: {document.name}",
        )
        document.confirm_delete(
            profile_institution=request.profile_institution,
            external_identity=request.external_identity,
        )
        return Response(status=status.HTTP_204_NO_CONTENT)


class BusinessDocumentCategoryListCreateView(APIView, SearchOrderMixin):
    permission_classes = [HasInstitutionPermission]
    required_permissions = {
        "get": "can_view_business_document_category",
        "post": "can_create_business_document_category",
    }

    queryset = BusinessDocumentCategory.objects.undeleted()

    @extend_schema(
        responses={200: BusinessDocumentCategorySerializer(many=True)},
        description="List business category documents belonging to the institution.",
        summary="List Business Document Categories",
        tags=["Business Document Category"],
        parameters=[
            SEARCH_PARAM,
            ORDERING_PARAM,
        ],
    )
    def get(self, request):

        documents_qs = self.queryset.filter(institution=get_institution(request))

        documents_qs = self.apply_search(documents_qs)
        documents_qs = self.apply_ordering(documents_qs)
        documents_qs = self.apply_filters(documents_qs)

        paginator = CustomPageNumberPagination()
        paginated_qs = paginator.paginate_queryset(documents_qs, request)
        serializer = BusinessDocumentCategorySerializer(paginated_qs, many=True)
        return paginator.get_paginated_response(serializer.data)

    @extend_schema(
        request=BusinessDocumentCategorySerializer(many=True),
        responses={201: BusinessDocumentCategorySerializer(many=True)},
        description="Create one or more business document categories.",
        summary="Create Business Document Category (bulk supported)",
        tags=["Business Document Category"],
    )
    def post(self, request):
        is_many = isinstance(request.data, list)

        serializer = BusinessDocumentCategorySerializer(
            data=request.data,
            many=is_many,
            context={"request": request},
        )
        serializer.is_valid(raise_exception=True)

        documents = serializer.save()

        if not is_many:
            documents = [documents]

        for document in documents:
            AuditLog.objects.create(
                content_type=ContentType.objects.get_for_model(
                    BusinessDocumentCategory
                ),
                object_id=document.pk,
                action="CREATE",
                user=request.user if request.user.is_authenticated else None,
                description=f"Created Business Document Category: {document.name}",
            )
            document.confirm_create(
                profile_institution=request.profile_institution,
                external_identity=request.external_identity,
            )

        return Response(serializer.data, status=status.HTTP_201_CREATED)


class BusinessDocumentCategoryDetailView(APIView):

    permission_classes = [HasInstitutionPermission]
    required_permissions = {
        "get": "can_view_business_document_category",
        "patch": "can_edit_business_document_category",
        "delete": "can_delete_business_document_category",
    }

    def get_object(self, request, base_uuid):
        return get_object_or_404(
            BusinessDocumentCategory.objects.undeleted(),
            base_uuid=base_uuid,
            institution=get_institution(request),
        )

    @extend_schema(
        responses={200: BusinessDocumentCategorySerializer},
        description="Retrieve a specific business document category.",
        summary="Retrieve Business Document Category",
        tags=["Business Document Category"],
    )
    def get(self, request, base_uuid):
        document = self.get_object(request, base_uuid)
        serializer = BusinessDocumentCategorySerializer(document)
        return Response(serializer.data)

    @extend_schema(
        request=BusinessDocumentCategorySerializer,
        responses={200: BusinessDocumentCategorySerializer},
        description="Update a business document category.",
        summary="Update Business Document Category",
        tags=["Business Document Category"],
    )
    def patch(self, request, base_uuid):
        document = self.get_object(request, base_uuid)
        document.approval_status = "under_update"

        old_data = BusinessDocumentCategorySerializer(document).data

        serializer = BusinessDocumentCategorySerializer(
            document, data=request.data, partial=True
        )

        if serializer.is_valid():
            document = serializer.save()

            new_data = BusinessDocumentCategorySerializer(document).data

            changes = {
                key: {"old": old_data.get(key), "new": new_data.get(key)}
                for key in request.data.keys()
                if old_data.get(key) != new_data.get(key)
            }

            AuditLog.objects.create(
                content_type=ContentType.objects.get_for_model(
                    BusinessDocumentCategory
                ),
                object_id=document.pk,
                action="UPDATE",
                user=request.user,
                changes=changes,
                description=f"Updated Business Document Category: {document.name}",
            )
            document.confirm_update(
                profile_institution=request.profile_institution,
                external_identity=request.external_identity,
            )
            return Response(serializer.data)
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

    @extend_schema(
        responses={204: None},
        description="Soft-delete a business document category (marks for deletion).",
        summary="Delete Business Document Category",
        tags=["Business Document Category"],
    )
    def delete(self, request, base_uuid):
        document = self.get_object(request, base_uuid)

        document.approval_status = "under_deletion"
        document.save(update_fields=["approval_status"])

        AuditLog.objects.create(
            content_type=ContentType.objects.get_for_model(BusinessDocumentCategory),
            object_id=document.pk,
            action="DELETE",
            user=request.user,
            description=f"Marked Business Document Category for deletion: {document.name}",
        )
        document.confirm_delete(
            profile_institution=request.profile_institution,
            external_identity=request.external_identity,
        )
        return Response(status=status.HTTP_204_NO_CONTENT)


class AnnouncementTargetUserListView(APIView):
    permission_classes = [HasInstitutionPermission]
    required_permissions = {
        "get": "can_view_announcement_target_user",
        "post": "can_create_announcement_target_user",
    }

    @extend_schema(
        request=AnnouncementTargetUserSerializer,
        responses={200: AnnouncementTargetUserSerializer(many=True)},
        description="Retrieve a list of all target announcements for an institution. Supports searching by title or content.",
        summary="List all announcement targets",
        tags=["Announcement Target Management"],
        parameters=[
            OpenApiParameter(
                name="search",
                type=str,
                location=OpenApiParameter.QUERY,
                description="Search term to filter announcement targets by title or content",
                required=False,
            ),
        ],
    )
    def get(self, request):
        institution = get_institution(request)

        search_query = request.query_params.get("search", None)

        announcement_targets = AnnouncementTargetUser.objects.filter(
            announcement__institution=institution
        ).order_by("-announcement__created_at")

        if search_query:
            announcement_targets = announcement_targets.filter(
                Q(announcement__title__icontains=search_query)
                | Q(announcement__content__icontains=search_query)
            )

        paginator = CustomPageNumberPagination()
        paginator_qs = paginator.paginate_queryset(announcement_targets, request)
        serializer = AnnouncementTargetUserSerializer(paginator_qs, many=True)

        return paginator.get_paginated_response(serializer.data)

    @extend_schema(
        request=AnnouncementTargetUserSerializer,
        responses={201: AnnouncementTargetUserSerializer},
        description="Create a new announcement target",
        summary="Create a new announcement target",
        tags=["Announcement Target Management"],
    )
    def post(self, request):
        serializer = AnnouncementTargetUserSerializer(
            data=request.data, context={"request": request}
        )

        if serializer.is_valid():
            validated_data = serializer.validated_data

            announcement_obj = validated_data["announcement"]
            user_obj = validated_data["user"]

            existing_target = AnnouncementTargetUser.objects.filter(
                announcement=announcement_obj, user=user_obj
            ).first()

            if existing_target:

                existing_serializer = AnnouncementTargetUserSerializer(existing_target)
                return Response(existing_serializer.data, status=status.HTTP_200_OK)

            institution = get_institution(request)
            if announcement_obj.institution != institution:
                raise SystemValidationError(
                    detail={
                        "announcement": [
                            "Announcement must belong to the current institution."
                        ]
                    },
                    status_code=status.HTTP_400_BAD_REQUEST,
                )

            announcement_target = serializer.save()

            AuditLog.objects.create(
                content_type=ContentType.objects.get_for_model(AnnouncementTargetUser),
                object_id=announcement_target.pk,
                action="CREATE",
                user=request.user,
                description=f"Created Announcement Target link (PK: {announcement_target.pk}) for Announcement ID: {announcement_target.announcement_id}",
            )
            return Response(serializer.data, status=status.HTTP_201_CREATED)

        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)


class AnnouncementTargetUserDetailView(APIView):
    """
    Handles retrieval, update, and deletion of a specific Announcement.
    """

    permission_classes = [HasInstitutionPermission]
    required_permissions = {
        "get": "can_view_announcement_target_user",
        "patch": "can_edit_announcement_target_user",
        "delete": "can_delete_announcement_target_user",
    }

    def get_object(self, id, user):
        """Fetches the Announcement Target by UUID, filtered by institution."""
        try:
            return AnnouncementTargetUser.objects.get(
                id=id, announcement__institution=user.profile.institution
            )
        except AnnouncementTargetUser.DoesNotExist:
            raise SystemNotFoundError(
                detail=f"Announcement Target with ID '{id}' not found in institution.",
                status_code=status.HTTP_404_NOT_FOUND,
            )

    @extend_schema(
        responses={200: AnnouncementTargetUserSerializer},
        description="Retrieve details of a specific announcement target.",
        summary="Get announcement target details",
        tags=["Announcement Target Management"],
    )
    def get(self, request, id):
        announcement_target = self.get_object(id, request.user)

        serializer = AnnouncementTargetUserSerializer(announcement_target)
        return Response(serializer.data)

    @extend_schema(
        request=AnnouncementTargetUserSerializer,
        responses={200: AnnouncementTargetUserSerializer},
        description="Partially update details of a specific announcement target.",
        summary="Partially update announcement target details",
        tags=["Announcement Target Management"],
    )
    def patch(self, request, id):
        announcement_target = self.get_object(id, request.user)

        old_data = AnnouncementTargetUserSerializer(announcement_target).data

        serializer = AnnouncementTargetUserSerializer(
            announcement_target, data=request.data, partial=True
        )
        if serializer.is_valid():
            updated_announcement_target = serializer.save()

            new_data = AnnouncementTargetUserSerializer(
                updated_announcement_target
            ).data
            changes = {
                key: {"old": old_data.get(key), "new": new_data.get(key)}
                for key in request.data.keys()
                if old_data.get(key) != new_data.get(key)
            }

            AuditLog.objects.create(
                content_type=ContentType.objects.get_for_model(AnnouncementTargetUser),
                object_id=updated_announcement_target.id,
                action="UPDATE",
                user=request.user,
                changes=changes,
                description=f"Updated announcement {updated_announcement_target.pk}",
            )
            return Response(serializer.data)

        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

    @extend_schema(
        responses={204: None},
        description="Delete a specific announcement (soft delete).",
        summary="Delete an announcement target",
        tags=["Announcement Target Management"],
    )
    def delete(self, request, id):
        announcement_target = self.get_object(id, request.user)

        announcement_target_data = AnnouncementTargetUserSerializer(
            announcement_target
        ).data
        announcement_target_id = announcement_target_data.get("id")

        announcement_target.delete()

        AuditLog.objects.create(
            content_type=ContentType.objects.get_for_model(AnnouncementTargetUser),
            object_id=announcement_target_id,
            action="DELETE",
            user=request.user,
            changes=announcement_target_data,
            description=f"Deleted announcement: {id}",
        )
        return Response(status=status.HTTP_204_NO_CONTENT)


class AnnouncementListView(APIView, SearchOrderMixin):
    """
    Handles listing and creation of Announcements for the user's institution.
    """

    permission_classes = [HasInstitutionPermission]
    required_permissions = {
        "get": "can_view_announcement",
        "post": "can_create_announcement",
    }

    @extend_schema(
        request=AnnouncementSerializer,
        responses={200: AnnouncementSerializer(many=True)},
        description="Retrieve a list of all announcements for the logged-in institution. Supports searching by title or content.",
        summary="List all announcements",
        tags=["Announcement Management"],
        parameters=[
            SEARCH_PARAM,
            ORDERING_PARAM,
        ],
    )
    def get(self, request):
        try:
            institution = get_institution(request)

            announcements = Announcement.objects.filter(
                institution=institution, deleted_at__isnull=True
            ).order_by("-created_at")

            announcements = self.apply_search(announcements)
            announcements = self.apply_ordering(announcements)

            paginator = CustomPageNumberPagination()
            paginator_qs = paginator.paginate_queryset(announcements, request)
            serializer = AnnouncementSerializer(paginator_qs, many=True)

            return paginator.get_paginated_response(serializer.data)
        except Exception:
            raise SystemNotFoundError(
                detail="Error fetching announcements.",
                status_code=status.HTTP_404_NOT_FOUND,
            )

    @extend_schema(
        request=AnnouncementSerializer,
        responses={201: AnnouncementSerializer},
        description="Create a new announcement.",
        summary="Create a new announcement",
        tags=["Announcement Management"],
    )
    def post(self, request):

        serializer = AnnouncementSerializer(
            data=request.data, context={"request": request}
        )
        if serializer.is_valid():
            announcement = serializer.save(institution=get_institution(request))

            AuditLog.objects.create(
                content_type=ContentType.objects.get_for_model(Announcement),
                object_id=announcement.pk,
                action="CREATE",
                user=request.user,
                description=f"Created Announcement: {announcement.title}",
            )
            return Response(serializer.data, status=status.HTTP_201_CREATED)

        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)


class AnnouncementDetailView(APIView):
    """
    Handles retrieval, update, and deletion of a specific Announcement.
    """

    permission_classes = [HasInstitutionPermission]
    required_permissions = {
        "get": "can_view_announcement",
        "patch": "can_edit_announcement",
        "delete": "can_delete_announcement",
    }

    def get_object(self, base_uuid, user):
        """Fetches the Announcement by UUID, filtered by institution."""
        try:
            return Announcement.objects.get(
                base_uuid=base_uuid, institution=user.profile.institution
            )
        except Announcement.DoesNotExist:
            raise SystemNotFoundError(
                detail=f"Announcement with UUID '{base_uuid}' not found in institution.",
                status_code=status.HTTP_404_NOT_FOUND,
            )

    @extend_schema(
        responses={200: AnnouncementSerializer},
        description="Retrieve details of a specific announcement.",
        summary="Get announcement details",
        tags=["Announcement Management"],
    )
    def get(self, request, base_uuid):
        announcement = self.get_object(base_uuid, request.user)

        serializer = AnnouncementSerializer(announcement)
        return Response(serializer.data)

    @extend_schema(
        request=AnnouncementSerializer,
        responses={200: AnnouncementSerializer},
        description="Partially update details of a specific announcement.",
        summary="Partially update announcement details",
        tags=["Announcement Management"],
    )
    def patch(self, request, base_uuid):
        announcement = self.get_object(base_uuid, request.user)

        old_data = AnnouncementSerializer(announcement).data

        serializer = AnnouncementSerializer(
            announcement, data=request.data, partial=True
        )
        if serializer.is_valid():
            updated_announcement = serializer.save()

            new_data = AnnouncementSerializer(updated_announcement).data
            changes = {
                key: {"old": old_data.get(key), "new": new_data.get(key)}
                for key in request.data.keys()
                if old_data.get(key) != new_data.get(key)
            }

            AuditLog.objects.create(
                content_type=ContentType.objects.get_for_model(Announcement),
                object_id=updated_announcement.id,
                action="UPDATE",
                user=request.user,
                changes=changes,
                description=f"Updated announcement {updated_announcement.title} ({updated_announcement.base_uuid})",
            )
            return Response(serializer.data)

        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

    @extend_schema(
        responses={204: None},
        description="Delete a specific announcement (soft delete).",
        summary="Delete an announcement",
        tags=["Announcement Management"],
    )
    def delete(self, request, base_uuid):
        announcement = self.get_object(base_uuid, request.user)

        announcement_data = AnnouncementSerializer(announcement).data
        announcement_id = announcement.id

        announcement.delete()

        AuditLog.objects.create(
            content_type=ContentType.objects.get_for_model(Announcement),
            object_id=announcement_id,
            action="DELETE",
            user=request.user,
            changes=announcement_data,
            description=f"Deleted announcement {announcement_data['title']} ({base_uuid})",
        )
        return Response(status=status.HTTP_204_NO_CONTENT)


class UserAnnouncementAcknowledgmentListCreateView(APIView):
    """
    Handles listing the current user's announcement acknowledgments (GET)
    and creating a new acknowledgment (POST).
    """

    permission_classes = [HasInstitutionPermission]
    required_permissions = {
        "get": "can_view_user_announcement_acknowledgment",
        "post": "can_create_user_announcement_acknowledgment",
    }

    @extend_schema(
        responses={200: UserAnnouncementAcknowledgmentSerializer(many=True)},
        description="Retrieve a list of all announcements acknowledged by the current user.",
        summary="List all user acknowledgments",
        tags=["Announcement Acknowledgment"],
    )
    def get(self, request):
        """List all announcements acknowledged by the current user."""
        try:
            acknowledgments = UserAnnouncementAcknowledgment.objects.filter(
                user=request.user,
                announcement__institution=request.user.profile.institution,
            ).order_by("-acknowledged_at")

            paginator = CustomPageNumberPagination()
            paginator_qs = paginator.paginate_queryset(acknowledgments, request)
            serializer = UserAnnouncementAcknowledgmentSerializer(
                paginator_qs, many=True
            )

            return paginator.get_paginated_response(serializer.data)

        except Exception as e:
            raise SystemError(
                detail=f"Error fetching announcement acknowledgments: {e}",
                status_code=status.HTTP_400_BAD_REQUEST,
            )

    @extend_schema(
        request=UserAnnouncementAcknowledgmentSerializer,
        responses={201: UserAnnouncementAcknowledgmentSerializer},
        description="Acknowledge an announcement. The 'user' field is automatically set to the authenticated user.",
        summary="Acknowledge an announcement",
        tags=["Announcement Acknowledgment"],
    )
    def post(self, request):
        """Acknowledge a specific announcement (creates the link if it doesn't exist)."""

        data = request.data.copy()
        data["user"] = request.user.id

        announcement_id = data.get("announcement")
        if not announcement_id:
            return Response(
                {"announcement": ["This field is required."]},
                status=status.HTTP_400_BAD_REQUEST,
            )

        try:
            Announcement.objects.get(
                id=announcement_id, institution=request.user.profile.institution
            )
        except Announcement.DoesNotExist:
            return Response(
                {
                    "announcement": [
                        f"Announcement {announcement_id} not found or inaccessible in your institution."
                    ]
                },
                status=status.HTTP_404_NOT_FOUND,
            )

        serializer = UserAnnouncementAcknowledgmentSerializer(
            data=data, context={"request": request}
        )
        if serializer.is_valid():
            acknowledgment_instance = serializer.save()

            # Determine status code based on whether the instance was created or fetched
            # We check if the instance already existed (serializer.instance is set before save() returns)
            is_created = serializer.instance is None
            status_code = status.HTTP_201_CREATED if is_created else status.HTTP_200_OK

            return Response(
                UserAnnouncementAcknowledgmentSerializer(acknowledgment_instance).data,
                status=status_code,
            )

        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)


class UserAnnouncementAcknowledgmentDetailView(APIView):
    """
    Handles retrieval, update (e.g., revoking acknowledgment), and deletion
    of a specific User Announcement Acknowledgment instance.
    """

    permission_classes = [HasInstitutionPermission]
    required_permissions = {
        "get": "can_view_user_announcement_acknowledgment",
        "patch": "can_edit_user_announcement_acknowledgment",
        "delete": "can_delete_user_announcement_acknowledgment",
    }

    def get_object(self, pk, user):
        """
        Fetches the Acknowledgment by ID (pk), strictly scoped to the
        authenticated user and their institution.
        """
        try:
            return UserAnnouncementAcknowledgment.objects.get(
                pk=pk, user=user, announcement__institution=user.profile.institution
            )
        except UserAnnouncementAcknowledgment.DoesNotExist:
            raise SystemNotFoundError(
                detail=f"Acknowledgment with ID '{pk}' not found or inaccessible.",
                status_code=status.HTTP_404_NOT_FOUND,
            )

    @extend_schema(
        responses={200: UserAnnouncementAcknowledgmentSerializer},
        description="Retrieve details of a specific user announcement acknowledgment.",
        summary="Get user acknowledgment details",
        tags=["Announcement Acknowledgment"],
    )
    def get(self, request, pk):
        """Retrieve a specific acknowledgment instance."""
        acknowledgment = self.get_object(pk, request.user)
        serializer = UserAnnouncementAcknowledgmentSerializer(acknowledgment)
        return Response(serializer.data)

    @extend_schema(
        request=UserAnnouncementAcknowledgmentSerializer,
        responses={200: UserAnnouncementAcknowledgmentSerializer},
        description="Update a specific acknowledgment (e.g., revoking the acknowledgment).",
        summary="Update (Revoke) user acknowledgment",
        tags=["Announcement Acknowledgment"],
    )
    def patch(self, request, pk):
        """Update a specific acknowledgment instance (e.g., setting 'acknowledged' to False)."""
        acknowledgment = self.get_object(pk, request.user)

        serializer = UserAnnouncementAcknowledgmentSerializer(
            acknowledgment, data=request.data, partial=True
        )
        if serializer.is_valid():
            updated_acknowledgment = serializer.save()

            return Response(serializer.data)

        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

    @extend_schema(
        responses={204: None},
        description="Delete (revoke) a specific user announcement acknowledgment.",
        summary="Delete user acknowledgment",
        tags=["Announcement Acknowledgment"],
    )
    def delete(self, request, pk):
        """Hard delete of the acknowledgment instance."""
        acknowledgment = self.get_object(pk, request.user)

        acknowledgment_data = UserAnnouncementAcknowledgmentSerializer(
            acknowledgment
        ).data

        acknowledgment.delete()

        AuditLog.objects.create(
            content_type=ContentType.objects.get_for_model(
                UserAnnouncementAcknowledgment
            ),
            object_id=acknowledgment.pk,
            action="DELETE",
            user=request.user,
            changes=acknowledgment_data,
            description=f"Deleted user announcement acknowledgment link: {acknowledgment.pk}",
        )

        return Response(status=status.HTTP_204_NO_CONTENT)


class AnnouncementTargetRoleListCreateView(APIView):
    """
    Handles listing the target roles for a specific announcement (GET)
    and creating a new role target link (POST).
    """

    permission_classes = [HasInstitutionPermission]
    required_permissions = {
        "get": "can_view_announcement_target_role",
        "patch": "can_edit_announcement_target_role",
        "delete": "can_delete_announcement_target_role",
    }

    @extend_schema(
        responses={200: AnnouncementTargetRoleSerializer(many=True)},
        description="Retrieve a list of all roles targeted by a specific announcement.",
        summary="List all target roles for an announcement",
        tags=["Announcement Targeting"],
    )
    def get(self, request):
        """List all target roles associated with a specific announcement."""
        try:
            target_roles = (
                AnnouncementTargetRole.objects.filter(
                    announcement__institution=request.user.profile.institution,
                    announcement__deleted_at__isnull=True,
                )
                .select_related("role")
                .order_by("role__name")
            )

            paginator = CustomPageNumberPagination()
            paginator_qs = paginator.paginate_queryset(target_roles, request)
            serializer = AnnouncementTargetRoleSerializer(paginator_qs, many=True)

            return paginator.get_paginated_response(serializer.data)

        except Exception as e:
            raise SystemNotFoundError(
                detail=f"Error fetching target roles for announcement",
                status_code=status.HTTP_400_BAD_REQUEST,
            )

    @extend_schema(
        request=AnnouncementTargetRoleSerializer,
        responses={
            status.HTTP_201_CREATED: AnnouncementTargetRoleSerializer,
            status.HTTP_400_BAD_REQUEST: {
                "description": "Validation failed (e.g., missing fields)."
            },
            status.HTTP_409_CONFLICT: {
                "description": "The role is already a target for this announcement (Unique Constraint Failure)."
            },
        },
        description="Link a specific role (by ID) to the announcement. The announcement ID is taken from the URL.",
        summary="Add a target role to an announcement",
        tags=["Announcement Targeting"],
    )
    def post(self, request):
        """Create a new AnnouncementTargetRole link."""

        serializer = AnnouncementTargetRoleSerializer(
            data=request.data, context={"request": request}
        )
        if serializer.is_valid():
            try:
                instance = serializer.save()
                return Response(serializer.data, status=status.HTTP_201_CREATED)
            except SystemNotFoundError:
                return Response(
                    {"detail": "This role is already a target for this announcement."},
                    status=status.HTTP_409_CONFLICT,
                )

        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)


class AnnouncementTargetRoleDetailView(APIView):
    """
    Handles retrieval and deletion of a specific Announcement Target Role instance.
    """

    permission_classes = [HasInstitutionPermission]
    required_permissions = {
        "get": "can_view_announcement_target_role",
        "patch": "can_edit_announcement_target_role",
        "delete": "can_delete_announcement_target_role",
    }

    def get_object(self, pk, user):
        """
        Fetches the Announcement Target Role by ID (pk), strictly scoped to the
        authenticated user's institution via the linked announcement.
        """
        try:
            return AnnouncementTargetRole.objects.get(
                pk=pk, announcement__institution=user.profile.institution
            )
        except AnnouncementTargetRole.DoesNotExist:
            raise SystemNotFoundError(
                detail=f"Announcement Target Role with ID '{pk}' not found or inaccessible.",
                status_code=status.HTTP_404_NOT_FOUND,
            )

    @extend_schema(
        responses={200: AnnouncementTargetRoleSerializer},
        description="Retrieve details of a specific role link, ensuring it is accessible via the user's institution.",
        summary="Get details of a target role link",
        tags=["Announcement Targeting"],
    )
    def get(self, request, pk):
        """Retrieve a specific target role instance."""
        target_role = self.get_object(pk, request.user)
        serializer = AnnouncementTargetRoleSerializer(target_role)
        return Response(serializer.data)

    @extend_schema(
        request=AnnouncementTargetRoleSerializer,
        responses={200: AnnouncementTargetRoleSerializer},
        description="Update details of a specific role link, ensuring it is accessible via the user's institution.",
        summary="Update details of a target role link",
        tags=["Announcement Targeting"],
    )
    def patch(self, request, pk):
        """Update a specific target role instance."""
        target_role = self.get_object(pk, request.user)

        old_data = AnnouncementTargetRoleSerializer(target_role).data
        serializer = AnnouncementTargetRoleSerializer(
            target_role, data=request.data, partial=True
        )
        if serializer.is_valid():
            updated_target_role = serializer.save()

            new_data = AnnouncementTargetRoleSerializer(updated_target_role).data
            changes = {
                key: {"old": old_data.get(key), "new": new_data.get(key)}
                for key in request.data.keys()
                if old_data.get(key) != new_data.get(key)
            }

            AuditLog.objects.create(
                content_type=ContentType.objects.get_for_model(AnnouncementTargetRole),
                object_id=updated_target_role.id,
                action="UPDATE",
                user=request.user,
                changes=changes,
                description=f"Updated target_role {updated_target_role.pk}",
            ),
            return Response(serializer.data)

        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

    @extend_schema(
        responses={204: None},
        description="Removes the link between an announcement and a target role.",
        summary="Remove target role link",
        tags=["Announcement Targeting"],
    )
    def delete(self, request, pk):
        """Hard delete of the Announcement Target Role instance (removes the link)."""
        target_role = self.get_object(pk, request.user)

        target_role_data = AnnouncementTargetRoleSerializer(target_role).data

        target_role.delete()

        return Response(status=status.HTTP_204_NO_CONTENT)


class NoteListCreateView(APIView, SearchOrderMixin):
    permission_classes = [HasInstitutionPermission]
    required_permissions = {
        "get": "can_view_notes",
        "post": "can_create_notes",
    }

    @extend_schema(
        responses={200: NoteSerializer(many=True)},
        description="Retrieve a list of all active notes for the current authenticated user. Supports searching by title/content and filtering by pin status.",
        summary="List user notes",
        tags=["Notes"],
        parameters=[
            SEARCH_PARAM,
            ORDERING_PARAM,
            OpenApiParameter(
                name="is_pinned",
                type=bool,
                location=OpenApiParameter.QUERY,
                description="Filter notes by pinned status (True or False).",
                required=False,
            ),
        ],
    )
    def get(self, request):
        try:
            notes = Notes.objects.filter(
                user=request.user,
                is_active=True,
            )

            is_pinned_param = request.query_params.get("is_pinned", None)

            if is_pinned_param is not None:
                is_pinned_bool = is_pinned_param.lower() in ["true", "1"]
                notes = notes.filter(is_pinned=is_pinned_bool)

            notes = notes.order_by("-is_pinned", "-created_at")

            notes = self.apply_search(notes)
            notes = self.apply_ordering(notes)

            paginator = CustomPageNumberPagination()
            paginator_qs = paginator.paginate_queryset(notes, request)
            serializer = NoteSerializer(paginator_qs, many=True)

            return paginator.get_paginated_response(serializer.data)

        except Exception as e:
            raise SystemNotFoundError(
                detail=f"Error fetching notes: {e}",
                status_code=status.HTTP_400_BAD_REQUEST,
            )

    @extend_schema(
        request=NoteSerializer,
        responses={201: NoteSerializer},
        description="Create a new note. The 'user' field is automatically set to the authenticated user.",
        summary="Create a new note",
        tags=["Notes"],
    )
    def post(self, request):
        serializer = NoteSerializer(
            data=request.data,
            context={"request": request},
        )
        if serializer.is_valid():
            note_instance = serializer.save()

            return Response(
                NoteSerializer(note_instance).data, status=status.HTTP_201_CREATED
            )

        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)


class NoteDetailView(APIView):
    permission_classes = [HasInstitutionPermission]
    required_permissions = {
        "get": "can_view_notes",
        "patch": "can_edit_notes",
        "delete": "can_delete_notes",
    }

    def get_object(self, base_uuid, user):
        try:
            return Notes.objects.get(
                base_uuid=base_uuid,
                user=user,
                is_active=True,
            )
        except Notes.DoesNotExist:
            raise SystemNotFoundError(
                detail=f"Note with UUID '{base_uuid}' not found or inaccessible.",
                status_code=status.HTTP_404_NOT_FOUND,
            )

    @extend_schema(
        responses={200: NoteSerializer},
        description="Retrieve details of a specific note using its base_uuid.",
        summary="Get note details",
        tags=["Notes"],
    )
    def get(self, request, base_uuid):
        note = self.get_object(base_uuid, request.user)
        serializer = NoteSerializer(note)
        return Response(serializer.data)

    @extend_schema(
        request=NoteSerializer,
        responses={200: NoteSerializer},
        description="Update a specific note (title, content, or is_pinned) using its base_uuid.",
        summary="Update note",
        tags=["Notes"],
    )
    @extend_schema(
        request=NoteSerializer,
        responses={200: NoteSerializer},
        description="Update a specific note (title, content, or is_pinned) using its base_uuid.",
        summary="Update note",
        tags=["Notes"],
    )
    def patch(self, request, base_uuid):
        note = self.get_object(base_uuid, request.user)

        old_data = NoteSerializer(note).data

        serializer = NoteSerializer(note, data=request.data, partial=True)
        if serializer.is_valid():
            updated_note = serializer.save()

            new_data = NoteSerializer(updated_note).data

            changes = {
                key: {"old": old_data.get(key), "new": new_data.get(key)}
                for key in request.data.keys()
                if old_data.get(key) != new_data.get(key)
            }

            AuditLog.objects.create(
                content_type=ContentType.objects.get_for_model(Notes),
                object_id=updated_note.pk,
                action="UPDATE",
                user=request.user,
                changes=changes,
                description=f"Updated note '{updated_note.title}' ({updated_note.base_uuid})",
            )

            return Response(serializer.data)

        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

    @extend_schema(
        responses={204: None},
        description="Soft-deletes a specific note using its base_uuid.",
        summary="Delete note (soft-delete)",
        tags=["Notes"],
    )
    def delete(self, request, base_uuid):
        note = self.get_object(base_uuid, request.user)

        note_data = NoteSerializer(note).data
        note_pk = note.pk

        note.delete()

        AuditLog.objects.create(
            content_type=ContentType.objects.get_for_model(Notes),
            object_id=note_pk,
            action="DELETE",
            user=request.user,
            changes=note_data,
            description=f"Soft-deleted note '{note_data['title']}' ({base_uuid})",
        )

        return Response(status=status.HTTP_204_NO_CONTENT)


class InstitutionFeatureStatusListView(APIView, SearchOrderMixin):

    permission_classes = [HasInstitutionPermission]
    required_permissions = {"get": "can_view_institution_feature_status"}

    @extend_schema(
        responses={200: InstitutionFeatureStatusSerializer(many=True)},
        description="List all available system features and their enabled/disabled status for the institution.",
        summary="List institution features",
        tags=["Institution Features"],
        parameters=[
            SEARCH_PARAM,
            ORDERING_PARAM,
            OpenApiParameter(
                name="show_all",
                type=bool,
                description="Show all features, including mandatory ones",
                required=False,
            ),
        ],
    )
    def get(self, request):
        show_all = request.query_params.get("show_all", "false").lower() in [
            "true",
            "1",
        ]

        institution = get_institution(request)

        feature_statuses = InstitutionFeatureStatus.objects.filter(
            institution=institution,
        ).select_related("system_feature")

        if not show_all:
            feature_statuses = feature_statuses.filter(
                system_feature__is_mandatory=False
            )

        feature_statuses = self.apply_search(feature_statuses)
        feature_statuses = self.apply_ordering(feature_statuses)

        paginator = CustomPageNumberPagination()
        paginator_qs = paginator.paginate_queryset(feature_statuses, request)
        serializer = InstitutionFeatureStatusSerializer(paginator_qs, many=True)
        return paginator.get_paginated_response(serializer.data)


class InstitutionFeatureStatusDetailView(APIView):

    permission_classes = [HasInstitutionPermission]
    required_permissions = {"patch": "can_edit_institution_feature_status"}

    @extend_schema(
        responses={200: InstitutionFeatureStatusSerializer},
        description="Enable or disable a specific feature for the institution.",
        summary="Update institution feature status",
        tags=["Institution Features"],
    )
    @transaction.atomic
    def patch(self, request, base_uuid):
        institution = get_institution(request)
        feature = get_object_or_404(
            InstitutionFeatureStatus,
            base_uuid=base_uuid,
            institution=institution,
        )
        is_enabled = request.data.get("is_enabled", None)
        if is_enabled is not None:
            feature.is_enabled = is_enabled
            feature.save()
        serializer = InstitutionFeatureStatusSerializer(feature)
        return Response(serializer.data)


class CurrencyConversionView(APIView):
    @extend_schema(
        request=CurrencyConversionSerializer,
        summary="Convert currency",
        description=(
            "Converts an amount from the institution base currency to an object's "
            "or explicitly selected transaction currency."
        ),
        tags=["Currency Conversion"],
    )
    def post(self, request):
        institution = get_institution(request)

        serializer = CurrencyConversionSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        data = serializer.validated_data

        obj = None
        model_name = data.get("model_name")
        object_uuid = data.get("object_uuid")
        currency = data.get("currency")
        explicit_target_currency = data.get("target_currency")
        override_rate = data.get("override_rate")
        exchange_rate = data.get("exchange_rate")

        if explicit_target_currency:
            if obj:
                raise ValidationError(
                    "Object conversion cannot be combined with target_currency."
                )
            if not currency:
                raise ValidationError(
                    "currency is required when target_currency is provided."
                )

            canonical_rate = FxRateService.resolve_pair_rate(
                institution=institution,
                from_currency=currency,
                to_currency=explicit_target_currency,
                rate_input=exchange_rate,
                supplied_rate=override_rate,
            )
            converted_amount = FxRateService.translate(
                data["amount"],
                canonical_rate,
            )

            return Response(
                {
                    "original_amount": data["amount"],
                    "converted_amount": converted_amount,
                    "from_currency": currency.code,
                    "to_currency": explicit_target_currency.code,
                    "canonical_rate": canonical_rate,
                    "exchange_rate": {
                        "one_side": {
                            "currency": {
                                "id": currency.pk,
                                "code": currency.code,
                                "name": currency.name,
                                "symbol": currency.symbol,
                            },
                            "value": "1",
                        },
                        "other_side": {
                            "currency": {
                                "id": explicit_target_currency.pk,
                                "code": explicit_target_currency.code,
                                "name": explicit_target_currency.name,
                                "symbol": explicit_target_currency.symbol,
                            },
                            "value": format(canonical_rate, "f"),
                        },
                    },
                }
            )

        if model_name or object_uuid:
            if not model_name or not object_uuid:
                raise ValidationError(
                    "Both 'model_name' and 'object_uuid' must be provided together."
                )
            model_class = get_model_from_name(model_name)
            try:
                obj = model_class.objects.get(base_uuid=object_uuid)
            except model_class.DoesNotExist:
                raise ValidationError(f"{model_name} object not found.")

            object_institution = obj.get_institution()
            if object_institution.pk != institution.pk:
                raise ValidationError(
                    "The selected object does not belong to the current institution."
                )

            target_currency, _ = obj.get_currency()

        elif not currency:
            raise ValidationError(
                "Either 'model_name' + 'object_uuid' or 'currency' must be provided."
            )
        else:
            target_currency = currency

        if not institution.currency_id:
            raise ValidationError("Institution base currency is not configured.")

        canonical_rate = FxRateService.resolve_base_rate(
            institution=institution,
            currency=target_currency,
            rate_input=exchange_rate,
            supplied_rate=override_rate,
        )

        converted_amount = FxRateService.convert_from_base(
            data["amount"],
            canonical_rate,
        )

        return Response(
            {
                "original_amount": data["amount"],
                "converted_amount": converted_amount,
                "from_currency": institution.currency.code,
                "to_currency": target_currency.code,
                "canonical_rate": canonical_rate,
                "exchange_rate": {
                    "one_side": {
                        "currency": {
                            "id": target_currency.pk,
                            "code": target_currency.code,
                            "name": target_currency.name,
                            "symbol": target_currency.symbol,
                        },
                        "value": "1",
                    },
                    "other_side": {
                        "currency": {
                            "id": institution.currency.pk,
                            "code": institution.currency.code,
                            "name": institution.currency.name,
                            "symbol": institution.currency.symbol,
                        },
                        "value": format(canonical_rate, "f"),
                    },
                },
            }
        )


class InstitutionSupportedBankListCreateView(APIView, SearchOrderMixin):
    permission_classes = [HasInstitutionPermission]
    required_permissions = {
        "get": "can_view_institution_supported_banks",
        "post": "can_create_institution_supported_banks",
    }

    @extend_schema(
        responses={200: InstitutionSupportedBankingInstitutionSerializer(many=True)},
        description="List supported banks for the current institution.",
        summary="List institution supported banks",
        tags=["Institution Supported Banks"],
        parameters=[SEARCH_PARAM, ORDERING_PARAM],
    )
    def get(self, request):
        supported_banks = (
            InstitutionSupportedBankingInstitution.objects.undeleted().filter(
                institution=get_institution(request),
            )
        )
        supported_banks = self.apply_search(supported_banks)
        supported_banks = self.apply_ordering(supported_banks)

        paginator = CustomPageNumberPagination()
        page = paginator.paginate_queryset(supported_banks, request)
        serializer = InstitutionSupportedBankingInstitutionSerializer(
            page,
            many=True,
            context={"request": request},
        )
        return paginator.get_paginated_response(serializer.data)

    @extend_schema(
        request=InstitutionSupportedBankingInstitutionSerializer,
        responses={201: InstitutionSupportedBankingInstitutionSerializer},
        description="Add a supported bank to the current institution.",
        summary="Create institution supported bank",
        tags=["Institution Supported Banks"],
    )
    def post(self, request):
        serializer = InstitutionSupportedBankingInstitutionSerializer(
            data=request.data,
            context={"request": request},
        )
        serializer.is_valid(raise_exception=True)
        serializer.save()
        return Response(serializer.data, status=status.HTTP_201_CREATED)


class InstitutionSupportedBankDetailView(APIView):
    permission_classes = [HasInstitutionPermission]
    required_permissions = {
        "get": "can_view_institution_supported_banks",
        "patch": "can_edit_institution_supported_banks",
        "delete": "can_delete_institution_supported_banks",
    }

    def get_object(self, request, base_uuid):
        return get_object_or_404(
            InstitutionSupportedBankingInstitution.objects.undeleted(),
            base_uuid=base_uuid,
            institution=get_institution(request),
        )

    @extend_schema(
        responses={200: InstitutionSupportedBankingInstitutionSerializer},
        description="Retrieve a supported bank for the current institution.",
        summary="Retrieve institution supported bank",
        tags=["Institution Supported Banks"],
    )
    def get(self, request, base_uuid):
        supported_bank = self.get_object(request, base_uuid)
        serializer = InstitutionSupportedBankingInstitutionSerializer(
            supported_bank,
            context={"request": request},
        )
        return Response(serializer.data, status=status.HTTP_200_OK)

    @extend_schema(
        request=InstitutionSupportedBankingInstitutionSerializer,
        responses={200: InstitutionSupportedBankingInstitutionSerializer},
        description="Update a supported bank for the current institution.",
        summary="Update institution supported bank",
        tags=["Institution Supported Banks"],
    )
    def patch(self, request, base_uuid):
        supported_bank = self.get_object(request, base_uuid)
        serializer = InstitutionSupportedBankingInstitutionSerializer(
            supported_bank,
            data=request.data,
            partial=True,
            context={"request": request},
        )
        serializer.is_valid(raise_exception=True)
        serializer.save()
        return Response(serializer.data, status=status.HTTP_200_OK)

    @extend_schema(
        responses={204: None},
        description="Soft-delete a supported bank from the current institution.",
        summary="Delete institution supported bank",
        tags=["Institution Supported Banks"],
    )
    def delete(self, request, base_uuid):
        supported_bank = self.get_object(request, base_uuid)
        supported_bank.delete()
        return Response(status=status.HTTP_204_NO_CONTENT)


class InstitutionSupportedCurrencyListView(APIView, SearchOrderMixin):

    permission_classes = [HasInstitutionPermission]
    required_permissions = {"get": "can_view_institution_supported_currency"}

    @extend_schema(
        responses={200: InstitutionSupportedCurrencySerial(many=True)},
        description="List all supported currencies for the institution.",
        summary="List institution supported currencies",
        tags=["Institution Supported Currency"],
    )
    def get(self, request):
        institution = get_institution(request)

        supported_currencies = InstitutionSupportedCurrency.objects.filter(
            institution=institution,
        )

        supported_currencies = self.apply_search(supported_currencies)
        supported_currencies = self.apply_ordering(supported_currencies)

        paginator = CustomPageNumberPagination()
        paginator_qs = paginator.paginate_queryset(supported_currencies, request)
        serializer = InstitutionSupportedCurrencySerial(paginator_qs, many=True)
        return paginator.get_paginated_response(serializer.data)


class InstitutionSupportedCurrencyDetailView(APIView):

    permission_classes = [HasInstitutionPermission]
    required_permissions = {
        "get": "can_view_institution_supported_currency",
        "patch": "can_edit_institution_supported_currency",
        "delete": "can_delete_institution_supported_currency",
    }

    @extend_schema(
        responses={200: InstitutionSupportedCurrencySerial},
        description="Retrieve a specific supported currency using its base_uuid.",
        summary="Get Institution Supported Currency details",
        tags=["Institution Supported Currency"],
    )
    def get(self, request, base_uuid):
        institution = get_institution(request)

        supported_currency = get_object_or_404(
            InstitutionSupportedCurrency,
            base_uuid=base_uuid,
            institution=institution,
        )

        serializer = InstitutionSupportedCurrencySerial(supported_currency)
        return Response(serializer.data, status=status.HTTP_200_OK)

    @extend_schema(
        request=InstitutionSupportedCurrencySerial,
        responses={200: InstitutionSupportedCurrencySerial},
        description="Update a specific supported currency using its base_uuid.",
        summary="Update Institution Supported Currency",
        tags=["Institution Supported Currency"],
    )
    def patch(self, request, base_uuid):

        institution = get_institution(request)

        supported_currency = get_object_or_404(
            InstitutionSupportedCurrency,
            base_uuid=base_uuid,
            institution=institution,
        )
        serializer = InstitutionSupportedCurrencySerial(
            supported_currency,
            data=request.data,
            partial=True,
        )

        serializer.is_valid(raise_exception=True)
        serializer.save()

        return Response(serializer.data, status=status.HTTP_200_OK)

    @extend_schema(
        responses={204: None},
        description="Delete a specific supported currency using its base_uuid.",
        summary="Delete Institution Supported Currency",
        tags=["Institution Supported Currency"],
    )
    def delete(self, request, base_uuid):
        institution = get_institution(request)

        supported_currency = get_object_or_404(
            InstitutionSupportedCurrency,
            base_uuid=base_uuid,
            institution=institution,
        )
        supported_currency.delete()
        return Response(status=status.HTTP_204_NO_CONTENT)


class BranchSupportedCurrencyListView(APIView, SearchOrderMixin):

    permission_classes = [HasInstitutionPermission]
    required_permissions = {
        "get": "can_view_branch_supported_currency",
        "post": "can_create_branch_supported_currency",
    }

    @extend_schema(
        responses={200: BranchSupportedCurrencySerializer(many=True)},
        description="Retrieve supported currencies for a branch.",
        summary="List Branch Supported Currencies",
        tags=["Branch Supported Currency"],
        parameters=[
            SEARCH_PARAM,
            ORDERING_PARAM,
            branch_base_uuid_param_base(required=True),
        ],
    )
    def get(self, request):
        institution = get_institution(request)
        if not institution:
            raise SystemNotFoundError(
                detail="Institution not found.",
                status_code=status.HTTP_404_NOT_FOUND,
            )

        branch_base_uuid = request.query_params.get("branch_base_uuid")
        if not branch_base_uuid:
            raise validation_error("branch_base_uuid query parameter is required.")

        try:
            branch = Branch.objects.get(
                base_uuid=branch_base_uuid,
                institution=institution,
                is_deleted=False,
            )
        except Branch.DoesNotExist:
            raise validation_error("Branch not found or inactive.")

        qs = BranchSupportedCurrency.objects.filter(
            branch=branch,
            deleted_at__isnull=True,
        )

        qs = self.apply_search(qs)
        qs = self.apply_ordering(qs)

        paginator = CustomPageNumberPagination()
        page = paginator.paginate_queryset(qs, request)

        serializer = BranchSupportedCurrencySerializer(page, many=True)
        return paginator.get_paginated_response(serializer.data)

    @extend_schema(
        request=BranchSupportedCurrencyInputSerializer,
        responses={201: BranchSupportedCurrencySerializer},
        description="Add a supported currency to a branch.",
        summary="Add Branch Supported Currency",
        tags=["Branch Supported Currency"],
    )
    def post(self, request):
        serializer = BranchSupportedCurrencyInputSerializer(
            data=request.data,
            context={"request": request},
        )
        serializer.is_valid(raise_exception=True)

        obj = serializer.save()

        return Response(
            BranchSupportedCurrencySerializer(obj).data,
            status=status.HTTP_201_CREATED,
        )


class BranchSupportedCurrencyDetailView(APIView):

    permission_classes = [HasInstitutionPermission]
    required_permissions = {
        "get": "can_view_branch_supported_currency",
        "patch": "can_edit_branch_supported_currency",
        "delete": "can_delete_branch_supported_currency",
    }

    @extend_schema(
        responses={200: BranchSupportedCurrencySerializer},
        description="Retrieve a specific supported currency using its base_uuid.",
        summary="Get Branch Supported Currency details",
        tags=["Branch Supported Currency"],
    )
    def get(self, request, base_uuid):
        try:
            branch_supported_currency = BranchSupportedCurrency.objects.get(
                base_uuid=base_uuid,
                deleted_at__isnull=True,
            )
        except BranchSupportedCurrency.DoesNotExist:
            raise validation_error("No Branch Supported Currency matches this UUID.")

        serializer = BranchSupportedCurrencySerializer(branch_supported_currency)
        return Response(serializer.data)

    @extend_schema(
        responses={200: BranchSupportedCurrencySerializer},
        description="Update a specific supported currency using its base_uuid.",
        summary="Update Branch Supported Currency details",
        tags=["Branch Supported Currency"],
    )
    def patch(self, request, base_uuid):
        branch_supported_currency = get_object_or_404(
            BranchSupportedCurrency, base_uuid=base_uuid
        )
        serializer = BranchSupportedCurrencySerializer(
            branch_supported_currency, data=request.data, partial=True
        )
        if serializer.is_valid():
            serializer.save()
            return Response(serializer.data)
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

    @extend_schema(
        responses={204: None},
        description="Delete a specific supported currency using its base_uuid.",
        summary="Delete Branch Supported Currency",
        tags=["Branch Supported Currency"],
    )
    def delete(self, request, base_uuid):
        branch_supported_currency = get_object_or_404(
            BranchSupportedCurrency, base_uuid=base_uuid
        )
        branch_supported_currency.delete()
        return Response(status=status.HTTP_204_NO_CONTENT)


class BranchAdminListCreateView(APIView, SearchOrderMixin):

    permission_classes = [HasInstitutionPermission]
    required_permissions = {
        "get": "can_view_branch_admin",
        "post": "can_create_branch_admin",
    }

    @extend_schema(
        responses={200: BranchAdminSerializer(many=True)},
        description="Retrieve a list of branch admins",
        summary="List branch admins",
        tags=["Branch Admins"],
        parameters=[
            SEARCH_PARAM,
            ORDERING_PARAM,
            branch_base_uuid_param_base(required=True),
        ],
    )
    def get(self, request):
        institution = get_institution(request)
        if not institution:
            raise SystemNotFoundError(
                detail="Institution not found.",
                status_code=status.HTTP_404_NOT_FOUND,
            )

        branch_base_uuid = request.query_params.get("branch_base_uuid")
        if not branch_base_uuid:
            raise validation_error("branch_base_uuid query parameter is required.")

        try:
            branch = Branch.objects.get(
                base_uuid=branch_base_uuid,
                institution=institution,
                deleted_at__isnull=True,
            )
        except Branch.DoesNotExist:
            raise validation_error("Branch not found or inactive.")

        if branch.branch_type in ["BRANCH", "DIVISION"]:
            raise validation_error("Cannot retrieve admins for branch-based units.")

        branch_admins = BranchAdmin.objects.filter(
            branch=branch,
            deleted_at__isnull=True,
        )

        branch_admins = self.apply_search(branch_admins)
        branch_admins = self.apply_ordering(branch_admins)

        paginator = CustomPageNumberPagination()
        page = paginator.paginate_queryset(branch_admins, request)
        serializer = BranchAdminSerializer(page, many=True)

        return paginator.get_paginated_response(serializer.data)

    @extend_schema(
        request=BranchAdminSerializer,
        responses={201: BranchAdminSerializer},
        description="Create a new branch admin.",
        summary="Create a branch admin",
        tags=["Branch Admins"],
    )
    def post(self, request):
        serializer = BranchAdminSerializer(
            data=request.data,
            context={"request": request},
        )
        serializer.is_valid(raise_exception=True)
        branch_admin = serializer.save()

        return Response(
            BranchAdminSerializer(branch_admin).data,
            status=status.HTTP_201_CREATED,
        )


class BranchAdminDetailView(APIView):

    permission_classes = [HasInstitutionPermission]
    required_permissions = {
        "get": "can_view_branch_admin",
        "patch": "can_edit_branch_admin",
        "delete": "can_delete_branch_admin",
    }

    @extend_schema(
        responses={200: BranchAdminSerializer},
        description="Retrieve details of a single branch admin.",
        summary="Branch admin details",
        tags=["Branch Admins"],
        parameters=[
            OpenApiParameter(
                name="base_uuid",
                type=str,
                location=OpenApiParameter.PATH,
                description="The base UUID of the branch admin.",
                required=True,
            ),
        ],
    )
    def get(self, request, base_uuid):
        institution = get_institution(request)
        if not institution:
            raise SystemNotFoundError(
                detail="Institution not found.",
                status_code=status.HTTP_404_NOT_FOUND,
            )

        try:
            branch_admin = BranchAdmin.objects.get(
                base_uuid=base_uuid,
                branch__institution=institution,
                deleted_at__isnull=True,
            )
        except BranchAdmin.DoesNotExist:
            raise validation_error("Branch Admin does not exist.")

        serializer = BranchAdminSerializer(branch_admin)
        return Response(serializer.data)

    @extend_schema(
        request=BranchAdminSerializer,
        responses={200: BranchAdminSerializer},
        description="Update a branch admin.",
        summary="Update branch admin",
        tags=["Branch Admins"],
    )
    def patch(self, request, base_uuid):
        institution = get_institution(request)
        branch_admin = get_object_or_404(
            BranchAdmin,
            base_uuid=base_uuid,
            branch__institution=institution,
            deleted_at__isnull=True,
        )

        serializer = BranchAdminSerializer(
            branch_admin,
            data=request.data,
            partial=True,
            context={"request": request, "branch": branch_admin.branch},
        )
        serializer.is_valid(raise_exception=True)
        branch_admin = serializer.save()

        return Response(BranchAdminSerializer(branch_admin).data)

    @extend_schema(
        responses={204: None},
        description="Soft delete a branch admin.",
        summary="Delete branch admin",
        tags=["Branch Admins"],
    )
    def delete(self, request, base_uuid):
        institution = get_institution(request)
        branch_admin = get_object_or_404(
            BranchAdmin,
            base_uuid=base_uuid,
            branch__institution=institution,
            deleted_at__isnull=True,
        )

        branch_admin.deleted_at = timezone.now()
        branch_admin.save(update_fields=["deleted_at"])
        return Response(status=status.HTTP_204_NO_CONTENT)


class InstitutionKYCDocumentListCreateView(APIView):
    """
    Handles listing and creating Institution KYC Documents.
    Allows filtering by category.
    """

    permission_classes = [HasInstitutionPermission]
    required_permissions = {
        "get": "can_view_institution_kyc_document",
        "post": "can_create_institution_kyc_document",
    }

    @extend_schema(
        responses={200: InstitutionKYCDocumentSerializer(many=True)},
        description="List KYC documents belonging to the institution.",
        summary="List Institution KYC Documents",
        tags=["Institution KYC Documents"],
    )
    def get(self, request):
        institution = get_institution(request)
        category_id = request.query_params.get("category_id")

        base_filter = Q(institution=institution, deleted_at__isnull=True)

        if category_id:
            base_filter &= Q(category_id=category_id)

        documents_qs = InstitutionKYCDocument.objects.filter(base_filter).order_by(
            "-created_at"
        )

        paginator = CustomPageNumberPagination()
        paginated_qs = paginator.paginate_queryset(documents_qs, request)

        serializer = InstitutionKYCDocumentSerializer(paginated_qs, many=True)
        return paginator.get_paginated_response(serializer.data)

    @extend_schema(
        request=InstitutionKYCDocumentSerializer,
        responses={201: InstitutionKYCDocumentSerializer},
        description="Create a new KYC document for the institution.",
        summary="Create Institution KYC Document",
        tags=["Institution KYC Documents"],
    )
    def post(self, request):
        institution = get_institution(request)
        serializer = InstitutionKYCDocumentSerializer(
            data=request.data,
            context={"request": request, "institution": institution},
        )
        if serializer.is_valid():
            document = serializer.save()

            AuditLog.objects.create(
                content_type=ContentType.objects.get_for_model(InstitutionKYCDocument),
                object_id=document.pk,
                action="CREATE",
                user=request.user,
                description=f"Created KYC Document: {document.document_name}",
            )
            document.confirm_create(
                profile_institution=request.profile_institution,
                external_identity=request.external_identity,
            )
            return Response(serializer.data, status=status.HTTP_201_CREATED)
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)


class InstitutionKYCDocumentDetailView(APIView):
    """
    Handles retrieval, updating, and soft deletion of a single KYC document instance.
    """

    permission_classes = [HasInstitutionPermission]
    required_permissions = {
        "get": "can_view_institution_kyc_document",
        "patch": "can_edit_institution_kyc_document",
        "delete": "can_delete_institution_kyc_document",
    }

    def get_object(self, base_uuid):
        """Retrieve the KYC document or raise 404."""
        institution = get_institution(self.request)
        return get_object_or_404(
            InstitutionKYCDocument,
            base_uuid=base_uuid,
            institution=institution,
            deleted_at__isnull=True,
        )

    @extend_schema(
        responses={200: InstitutionKYCDocumentSerializer},
        description="Retrieve a specific KYC document.",
        summary="Retrieve Institution KYC Document",
        tags=["Institution KYC Documents"],
    )
    def get(self, request, base_uuid):
        try:
            document = self.get_object(base_uuid)
        except Exception as e:
            raise validation_error(str(e))
        serializer = InstitutionKYCDocumentSerializer(document)
        return Response(serializer.data)

    @extend_schema(
        request=InstitutionKYCDocumentSerializer,
        responses={200: InstitutionKYCDocumentSerializer},
        description="Update a KYC document.",
        summary="Update Institution KYC Document",
        tags=["Institution KYC Documents"],
    )
    def patch(self, request, base_uuid):
        try:
            document = self.get_object(base_uuid)
        except Exception as e:
            raise validation_error(str(e))

        document.approval_status = "under_update"

        old_data = InstitutionKYCDocumentSerializer(document).data

        serializer = InstitutionKYCDocumentSerializer(
            document, data=request.data, partial=True, context={"request": request}
        )

        if serializer.is_valid():
            with transaction.atomic():
                document = serializer.save()

                new_data = InstitutionKYCDocumentSerializer(document).data

                changes = {
                    key: {"old": old_data.get(key), "new": new_data.get(key)}
                    for key in request.data.keys()
                    if old_data.get(key) != new_data.get(key)
                }

                AuditLog.objects.create(
                    content_type=ContentType.objects.get_for_model(
                        InstitutionKYCDocument
                    ),
                    object_id=document.pk,
                    action="UPDATE",
                    user=request.user,
                    changes=changes,
                    description=f"Updated KYC Document: {document.document_name}",
                )

            document.confirm_update(
                profile_institution=request.profile_institution,
                external_identity=request.external_identity,
            )
            return Response(serializer.data)

        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

    @extend_schema(
        responses={204: None},
        description="Soft-delete a KYC document (marks for deletion).",
        summary="Delete Institution KYC Document",
        tags=["Institution KYC Documents"],
    )
    def delete(self, request, base_uuid):
        try:
            document = self.get_object(base_uuid)
        except Exception as e:
            raise validation_error(str(e))

        document.approval_status = "under_deletion"
        document.save(update_fields=["approval_status"])

        AuditLog.objects.create(
            content_type=ContentType.objects.get_for_model(InstitutionKYCDocument),
            object_id=document.pk,
            action="DELETE",
            user=request.user,
            description=f"Deleted KYC Document: {document.document_name}",
        )
        document.confirm_delete(
            profile_institution=request.profile_institution,
            external_identity=request.external_identity,
        )
        return Response(status=status.HTTP_204_NO_CONTENT)


# TODO To be revised...!
def _get_bin_queryset(request):
    institution = get_institution(request)
    bin_obj = institution.get_institution_bin()

    # print("\n\nbin_obj", bin_obj)

    return bin_obj.items.select_related("content_type", "deleted_by")


# TODO To be revised...!
class RecycleBinListView(APIView):
    def get(self, request):
        search = request.query_params.get("search", "").strip()
        items = _get_bin_queryset(request)

        if search:
            items = items.annotate(
                data_text=Func(
                    "data",
                    function="CAST",
                    template="%(function)s(%(expressions)s AS TEXT)",
                    output_field=CharField(),
                )
            ).filter(
                Q(reference_code__icontains=search)
                | Q(content_type__app_label__icontains=search)
                | Q(content_type__model__icontains=search)
                | Q(deleted_by__email__icontains=search)
                | Q(deleted_by__fullname__icontains=search)
                | Q(data_text__icontains=search)
            )

        paginator = CustomPageNumberPagination()
        paginated_qs = paginator.paginate_queryset(items, request)
        serializer = RecycleBinItemSerializer(paginated_qs, many=True)
        return paginator.get_paginated_response(serializer.data)


# TODO To be revised...!
class RecycleBinRestoreView(APIView):
    def post(self, request, base_uuid):
        item = get_object_or_404(_get_bin_queryset(request), base_uuid=base_uuid)

        try:
            restored = item.restore(user=request.user)
            return Response(
                {
                    "detail": f"{restored.__class__.__name__} restored successfully.",
                    "base_uuid": str(restored.base_uuid),
                },
                status=status.HTTP_200_OK,
            )
        except Exception as exc:
            return Response({"detail": str(exc)}, status=status.HTTP_400_BAD_REQUEST)


class RecycleBinPermanentDeleteView(APIView):
    def delete(self, request, base_uuid):
        item = get_object_or_404(_get_bin_queryset(request), base_uuid=base_uuid)
        item.hard_delete(user=request.user)
        return Response(status=status.HTTP_204_NO_CONTENT)


def _get_bulk_recycle_bin_items(request):
    base_uuids = request.data.get("base_uuids") or request.data.get("object_uuids")

    if not isinstance(base_uuids, list) or not base_uuids:
        return None, Response(
            {"detail": "Provide a non-empty base_uuids list."},
            status=status.HTTP_400_BAD_REQUEST,
        )

    items = list(_get_bin_queryset(request).filter(base_uuid__in=base_uuids))
    found = {str(item.base_uuid) for item in items}
    missing = [
        str(base_uuid) for base_uuid in base_uuids if str(base_uuid) not in found
    ]

    if missing:
        return None, Response(
            {
                "detail": "Some recycle bin items were not found.",
                "missing_base_uuids": missing,
            },
            status=status.HTTP_404_NOT_FOUND,
        )

    return items, None


class RecycleBinBulkRestoreView(APIView):
    def post(self, request):
        items, error_response = _get_bulk_recycle_bin_items(request)
        if error_response:
            return error_response

        restored = []
        errors = []

        for item in items:
            try:
                restored_item = item.restore(user=request.user)
                restored.append(str(restored_item.base_uuid))
            except Exception as exc:
                errors.append({"base_uuid": str(item.base_uuid), "detail": str(exc)})

        status_code = status.HTTP_207_MULTI_STATUS if errors else status.HTTP_200_OK
        return Response(
            {
                "detail": f"{len(restored)} item(s) restored.",
                "restored": restored,
                "errors": errors,
            },
            status=status_code,
        )


class RecycleBinBulkPermanentDeleteView(APIView):
    def post(self, request):
        items, error_response = _get_bulk_recycle_bin_items(request)
        if error_response:
            return error_response

        count = 0
        for item in items:
            item.hard_delete(user=request.user)
            count += 1

        return Response(
            {"detail": f"{count} item(s) permanently deleted."},
            status=status.HTTP_200_OK,
        )


class RecycleBinEmptyView(APIView):
    def delete(self, request):
        items = _get_bin_queryset(request)
        count = items.count()
        for item in items:
            item.hard_delete(user=request.user)
        return Response(
            {"detail": f"Recycle bin emptied. {count} items permanently deleted."},
            status=status.HTTP_200_OK,
        )


class InstitutionNotificationSettingListCreateView(APIView):

    @extend_schema(
        responses={200: InstitutionNotificationSettingSerializer(many=True)},
    )
    def get(self, request):
        institution = get_institution(request)

        notifications = (
            InstitutionNotificationSetting.objects.filter(
                institution=institution,
                deleted_at__isnull=True,
            )
            .select_related("system_notification")
            .prefetch_related("target_users")
        )

        paginator = CustomPageNumberPagination()
        paginated_qs = paginator.paginate_queryset(notifications, request)
        serializer = InstitutionNotificationSettingSerializer(paginated_qs, many=True)
        return paginator.get_paginated_response(serializer.data)

    @extend_schema(
        request=InstitutionNotificationSettingInputSerializer(many=True),
        responses={201: InstitutionNotificationSettingSerializer(many=True)},
    )
    def post(self, request):
        institution = get_institution(request)

        serializer = InstitutionNotificationSettingInputSerializer(
            data=request.data, many=True
        )
        serializer.is_valid(raise_exception=True)

        created_objects = []

        with transaction.atomic():
            for data in serializer.validated_data:
                notification = data.get("notification")
                is_enabled = data.get("is_enabled", True)
                target_users = data.get("target_user_uuids", [])

                setting, created = InstitutionNotificationSetting.objects.get_or_create(
                    institution=institution,
                    system_notification=notification,
                    defaults={"is_enabled": is_enabled},
                )

                if not created:
                    setting.is_enabled = is_enabled
                    setting.save()

                if target_users is not None:
                    setting.target_users.set(target_users)

                created_objects.append(setting)

        output_serializer = InstitutionNotificationSettingSerializer(
            created_objects,
            many=True,
        )
        return Response(output_serializer.data, status=status.HTTP_201_CREATED)


class InstitutionNotificationSettingDetailView(APIView):

    @extend_schema(
        request=InstitutionNotificationSettingInputSerializer,
        responses={200: InstitutionNotificationSettingSerializer},
    )
    def patch(self, request, base_uuid):
        institution = get_institution(request)

        setting = get_object_or_404(
            InstitutionNotificationSetting,
            base_uuid=base_uuid,
            institution=institution,
            deleted_at__isnull=True,
        )
        serializer = InstitutionNotificationSettingInputSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        data = serializer.validated_data

        notification = data.get("notification", setting.system_notification)
        is_enabled = data.get("is_enabled", setting.is_enabled)
        target_users = data.get("target_user_uuids", None)

        with transaction.atomic():
            setting.system_notification = notification
            setting.is_enabled = is_enabled
            setting.save()

            if target_users is not None:
                setting.target_users.set(target_users)

        output_serializer = InstitutionNotificationSettingSerializer(setting)
        return Response(output_serializer.data, status=status.HTTP_200_OK)


class InstitutionBaisoftPayConfigurationListCreateView(APIView):
    permission_classes = [HasInstitutionPermission]
    required_permissions = {
        "get": "can_view_institution_settings",
        "post": "can_view_institution_settings",
    }

    @extend_schema(
        responses={200: InstitutionBaisoftPayConfigurationSerializer(many=True)},
        summary="List institution BaisoftPay configurations",
        tags=["Institution BaisoftPay Configuration"],
    )
    def get(self, request):
        institution = get_institution(request)

        configurations = (
            InstitutionBaisoftPayConfiguration.objects.undeleted()
            .filter(institution=institution)
            .select_related("institution", "branch")
            .order_by("branch__branch_name", "created_at")
        )

        paginator = CustomPageNumberPagination()
        paginated_configurations = paginator.paginate_queryset(
            configurations,
            request,
        )
        serializer = InstitutionBaisoftPayConfigurationSerializer(
            paginated_configurations,
            many=True,
            context={"request": request},
        )
        return paginator.get_paginated_response(serializer.data)

    @extend_schema(
        request=InstitutionBaisoftPayConfigurationSerializer,
        responses={201: InstitutionBaisoftPayConfigurationSerializer},
        summary="Create an institution BaisoftPay configuration",
        tags=["Institution BaisoftPay Configuration"],
    )
    def post(self, request):
        serializer = InstitutionBaisoftPayConfigurationSerializer(
            data=request.data,
            context={"request": request},
        )
        serializer.is_valid(raise_exception=True)
        configuration = serializer.save()
        return Response(
            InstitutionBaisoftPayConfigurationSerializer(
                configuration,
                context={"request": request},
            ).data,
            status=status.HTTP_201_CREATED,
        )


class InstitutionBaisoftPayConfigurationDetailView(APIView):
    permission_classes = [HasInstitutionPermission]
    required_permissions = {
        "get": "can_view_institution_settings",
        "patch": "can_view_institution_settings",
        "delete": "can_view_institution_settings",
    }

    def get_object(self, request, base_uuid):
        return get_object_or_404(
            InstitutionBaisoftPayConfiguration.objects.undeleted().select_related(
                "institution", "branch"
            ),
            base_uuid=base_uuid,
            institution=get_institution(request),
        )

    def get(self, request, base_uuid):
        configuration = self.get_object(request, base_uuid)
        serializer = InstitutionBaisoftPayConfigurationSerializer(
            configuration,
            context={"request": request},
        )
        return Response(serializer.data, status=status.HTTP_200_OK)

    def patch(self, request, base_uuid):
        configuration = self.get_object(request, base_uuid)
        serializer = InstitutionBaisoftPayConfigurationSerializer(
            configuration,
            data=request.data,
            partial=True,
            context={"request": request},
        )
        serializer.is_valid(raise_exception=True)
        configuration = serializer.save()
        return Response(
            InstitutionBaisoftPayConfigurationSerializer(
                configuration,
                context={"request": request},
            ).data,
            status=status.HTTP_200_OK,
        )

    def delete(self, request, base_uuid):
        configuration = self.get_object(request, base_uuid)
        configuration.updated_by = request.user
        configuration.save(update_fields=["updated_by", "updated_at"])
        configuration.delete()
        return Response(status=status.HTTP_204_NO_CONTENT)


class InstitutionBaisoftPayConfigurationVerifyView(APIView):
    permission_classes = [HasInstitutionPermission]
    required_permissions = {
        "post": "can_view_institution_settings",
    }

    @extend_schema(
        request=None,
        responses={200: dict},
        summary="Verify institution BaisoftPay credentials",
        tags=["Institution BaisoftPay Configuration"],
    )
    def post(self, request, base_uuid):
        configuration = get_object_or_404(
            InstitutionBaisoftPayConfiguration.objects.undeleted(),
            base_uuid=base_uuid,
            institution=get_institution(request),
            is_active=True,
        )

        try:
            service = BaisoftPayService(
                api_key=configuration.api_key,
                signing_key=configuration.signing_key,
            )
            service.get_payment_methods(
                params={
                    "page": 1,
                    "page_size": 1,
                }
            )
        except BaisoftPayServiceError as exc:
            raise validation_error(
                {
                    "credentials": (
                        "BaisoftPay could not verify these credentials. "
                        f"{str(exc).strip()}"
                    )
                }
            )

        configuration.last_verified_at = timezone.now()
        configuration.updated_by = request.user
        configuration.save(
            update_fields=[
                "last_verified_at",
                "updated_by",
                "updated_at",
            ]
        )

        return Response(
            {
                "success": True,
                "detail": "BaisoftPay credentials verified successfully.",
                "last_verified_at": configuration.last_verified_at,
            },
            status=status.HTTP_200_OK,
        )


class InstitutionReferenceSequenceListCreateView(APIView, SearchOrderMixin):
    permission_classes = [HasInstitutionPermission]
    required_permissions = {
        "get": "can_view_institution_reference_sequences",
        "post": "can_create_institution_reference_sequences",
    }

    @extend_schema(
        responses={200: InstitutionReferenceSequenceSerializer(many=True)},
        description="List reference sequence configurations for the current institution.",
        summary="List Institution Reference Sequences",
        tags=["Institution Reference Sequences"],
        parameters=[SEARCH_PARAM, ORDERING_PARAM],
    )
    def get(self, request):
        institution = get_institution(request)

        sequences = (
            InstitutionReferenceSequence.objects.undeleted()
            .filter(institution=institution)
            .select_related("institution", "content_type")
        )
        sequences = self.apply_search(sequences)
        sequences = self.apply_ordering(sequences)

        paginator = CustomPageNumberPagination()
        paginated_qs = paginator.paginate_queryset(sequences, request)
        serializer = InstitutionReferenceSequenceSerializer(paginated_qs, many=True)
        return paginator.get_paginated_response(serializer.data)

    @extend_schema(
        request=InstitutionReferenceSequenceSerializer,
        responses={201: InstitutionReferenceSequenceSerializer},
        description="Create a reference sequence configuration for the current institution.",
        summary="Create Institution Reference Sequence",
        tags=["Institution Reference Sequences"],
    )
    def post(self, request):
        institution = get_institution(request)

        serializer = InstitutionReferenceSequenceSerializer(
            data=request.data,
            context={"request": request},
        )
        serializer.is_valid(raise_exception=True)
        sequence = serializer.save(institution=institution)

        output_serializer = InstitutionReferenceSequenceSerializer(sequence)
        return Response(output_serializer.data, status=status.HTTP_201_CREATED)


class InstitutionReferenceSequenceStatusView(APIView):
    permission_classes = [HasInstitutionPermission]
    required_permissions = {
        "get": "can_view_institution_reference_sequences",
    }

    @extend_schema(
        description=(
            "Check whether a reference sequence exists for a content type, "
            "including soft-deleted sequences."
        ),
        summary="Get Institution Reference Sequence Status",
        tags=["Institution Reference Sequences"],
        parameters=[
            OpenApiParameter(
                name="content_type",
                type=int,
                location=OpenApiParameter.QUERY,
                required=True,
                description="Content type ID to check.",
            )
        ],
    )
    def get(self, request):
        institution = get_institution(request)
        content_type_value = request.query_params.get("content_type")

        if not content_type_value:
            raise ValidationError({"content_type": "This query parameter is required."})

        try:
            content_type_id = int(content_type_value)
        except (TypeError, ValueError):
            raise ValidationError(
                {"content_type": "A valid content type ID is required."}
            )

        if not ContentType.objects.filter(pk=content_type_id).exists():
            raise ValidationError(
                {"content_type": "The selected content type does not exist."}
            )

        sequence = (
            InstitutionReferenceSequence.objects.filter(
                institution=institution,
                content_type_id=content_type_id,
            )
            .select_related("institution", "content_type")
            .first()
        )

        if sequence is None:
            return Response(
                {
                    "exists": False,
                    "is_deleted": False,
                    "can_change_starting_value": True,
                    "sequence": None,
                },
                status=status.HTTP_200_OK,
            )

        return Response(
            {
                "exists": True,
                "is_deleted": sequence.deleted_at is not None,
                "can_change_starting_value": sequence.last_value in (None, ""),
                "sequence": InstitutionReferenceSequenceSerializer(sequence).data,
            },
            status=status.HTTP_200_OK,
        )


class InstitutionReferenceSequenceDetailView(APIView):
    permission_classes = [HasInstitutionPermission]
    required_permissions = {
        "get": "can_view_institution_reference_sequences",
        "patch": "can_edit_institution_reference_sequences",
        "delete": "can_delete_institution_reference_sequences",
    }

    def get_object(self, request, base_uuid):
        institution = get_institution(request)
        return get_object_or_404(
            InstitutionReferenceSequence.objects.undeleted().select_related(
                "institution",
                "content_type",
            ),
            base_uuid=base_uuid,
            institution=institution,
        )

    @extend_schema(
        responses={200: InstitutionReferenceSequenceSerializer},
        description="Retrieve a specific reference sequence configuration.",
        summary="Get Institution Reference Sequence",
        tags=["Institution Reference Sequences"],
    )
    def get(self, request, base_uuid):
        sequence = self.get_object(request, base_uuid)
        serializer = InstitutionReferenceSequenceSerializer(sequence)
        return Response(serializer.data, status=status.HTTP_200_OK)

    @extend_schema(
        request=InstitutionReferenceSequenceSerializer,
        responses={200: InstitutionReferenceSequenceSerializer},
        description="Update a reference sequence configuration. last_value is system-managed.",
        summary="Update Institution Reference Sequence",
        tags=["Institution Reference Sequences"],
    )
    def patch(self, request, base_uuid):
        sequence = self.get_object(request, base_uuid)
        serializer = InstitutionReferenceSequenceSerializer(
            sequence,
            data=request.data,
            partial=True,
            context={"request": request},
        )
        serializer.is_valid(raise_exception=True)
        sequence = serializer.save()

        output_serializer = InstitutionReferenceSequenceSerializer(sequence)
        return Response(output_serializer.data, status=status.HTTP_200_OK)

    @extend_schema(
        responses={204: None},
        description="Delete a reference sequence configuration.",
        summary="Delete Institution Reference Sequence",
        tags=["Institution Reference Sequences"],
    )
    def delete(self, request, base_uuid):
        sequence = self.get_object(request, base_uuid)
        sequence.delete()
        return Response(status=status.HTTP_204_NO_CONTENT)


class InstitutionOwnerShipTransferView(APIView):
    permission_classes = [AllowAny]

    @extend_schema(
        request=InstitutionOwnerShipTransferSerializer,
        responses={200: InstitutionOwnerShipTransferSerializer},
        description="Transfer institution ownership from the current owner to a new owner.",
        summary="Transfer Institution Ownership",
        tags=["Supra-Activation"],
    )
    def post(self, request):
        serializer = InstitutionOwnerShipTransferSerializer(
            data=request.data,
            context={"request": request},
        )

        print("\n\n\ndata", request.data)

        if not serializer.is_valid():

            print("\n\nserializer error", serializer.errors)
            raise SystemValidationError(
                detail=serializer.errors,
            )

        serializer.save()

        return Response(serializer.data, status=status.HTTP_200_OK)
