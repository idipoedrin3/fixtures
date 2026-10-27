from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework import status
from django.http import Http404
import re
from django.db.models import Q, OuterRef, Exists, Prefetch
from utilities.openapi import (
    SEARCH_PARAM,
    ORDERING_PARAM,
    content_type_id_param,
    object_base_uuid_param,
)
from utilities.helpers import get_institution, get_or_raise, validation_error
from .models import (
    Action,
    AllowedUser,
    ApprovalDocumentCategory,
    ApproverGroup,
    ApprovalDocument,
    ApprovalDocumentLevel,
    ApprovalDocumentLevelApprovers,
    ApprovalDocumentLevelOverriders,
    Approval,
    ApprovalTask,
    BaseApprovableModel,
)
from .serializers import (
    ActionSerializer,
    AllowedUserCreateSerializer,
    AllowedUserSerializer,
    ApprovalDocumentCategorySerializer,
    ApproverGroupSerializer,
    ApprovalDocumentSerializer,
    ApprovalDocumentLevelSerializer,
    ApprovalSerializer,
    ApprovalTaskSerializer,
    RecallApprovalTaskSerializer,
    SendBackSerializer,
)
from .risk_analysis import ApprovalRiskAnalysisService
from utilities.pagination import CustomPageNumberPagination
from rest_framework.permissions import IsAuthenticated
from drf_spectacular.utils import extend_schema, OpenApiResponse, OpenApiParameter
from drf_spectacular.types import OpenApiTypes
from users.models import Role, Profile, ProfileInstitution, UserRole
from django.utils import timezone
from datetime import timedelta
from django.db.models import Q
from django.apps import apps
from django.contrib.contenttypes.models import ContentType
from django.shortcuts import get_object_or_404
from rest_framework.exceptions import ValidationError
from django.urls import reverse, NoReverseMatch
from utilities.mixin import BranchFilterMixin, SearchOrderMixin


class AllowedUserListAPIView(APIView, SearchOrderMixin):
    def _get_content_type_from_request(self, request):

        content_type_id = request.query_params.get("content_type_id")

        if not content_type_id:
            return None, Response(
                {"detail": "content_type_id query parameter is required."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        try:
            return ContentType.objects.get(id=content_type_id), None
        except (ValueError, ContentType.DoesNotExist):
            return None, Response(
                {"detail": "Content type with provided content_type_id was not found."},
                status=status.HTTP_404_NOT_FOUND,
            )

    @extend_schema(
        tags=["Allowed Users"],
        parameters=[
            OpenApiParameter(
                name="content_type_id",
                type=str,
                location=OpenApiParameter.QUERY,
                required=True,
                description="ContentType ID.",
            ),
            SEARCH_PARAM,
            ORDERING_PARAM,
            OpenApiParameter(
                name="object_id",
                type=int,
                required=False,
                description="Filter by the specific object ID of the content type.",
            ),
        ],
        responses={200: AllowedUserSerializer(many=True)},
    )
    def get(self, request):
        institution = get_institution(request)

        object_id = request.query_params.get("object_id", None)

        content_type, error_response = self._get_content_type_from_request(request)
        if error_response:
            return error_response

        if object_id:
            filters = Q(
                content_type=content_type,
                object_id=object_id,
                user__institution=institution,
            )
        else:
            filters = Q(content_type=content_type, user__institution=institution)

        allowed_users = (
            AllowedUser.objects.undeleted()
            .filter(
                filters,
            )
            .select_related(
                "content_type",
                "user",
                "user__profile",
                "user__profile__user",
                "user__institution",
            )
        )

        allowed_users = self.apply_search(allowed_users)
        allowed_users = self.apply_ordering(allowed_users)

        paginator = CustomPageNumberPagination()
        paginated_qs = paginator.paginate_queryset(allowed_users, request)
        serializer = AllowedUserSerializer(paginated_qs, many=True)
        return paginator.get_paginated_response(serializer.data)

    @extend_schema(
        tags=["Allowed Users"],
        request=AllowedUserCreateSerializer,
        responses={201: AllowedUserSerializer(many=True)},
    )
    def post(self, request):
        institution = get_institution(request)

        serializer = AllowedUserCreateSerializer(
            data=request.data,
            context={"institution": institution},
        )

        serializer.is_valid(raise_exception=True)

        allowed_users = serializer.save()

        output_serializer = AllowedUserSerializer(allowed_users, many=True)
        return Response(output_serializer.data, status=status.HTTP_201_CREATED)


class ActionListAPIView(APIView, SearchOrderMixin):
    @extend_schema(
        tags=["Actions"],
        parameters=[
            SEARCH_PARAM,
            ORDERING_PARAM,
        ],
    )
    def get(self, request):

        institution = get_institution(request)

        if not institution:
            return Response(
                {"detail": "Institution not found."},
                status=status.HTTP_404_NOT_FOUND,
            )

        actions = Action.objects.undeleted()

        actions = self.apply_search(actions)
        actions = self.apply_ordering(actions)

        serializer = ActionSerializer(actions, many=True)
        return Response(serializer.data)

    @extend_schema(tags=["Actions"])
    def post(self, request):
        serializer = ActionSerializer(data=request.data)
        if serializer.is_valid():
            serializer.save()
            return Response(serializer.data, status=status.HTTP_201_CREATED)
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)


class ApproverGroupListAPIView(APIView, SearchOrderMixin):
    @extend_schema(
        tags=["Approver Groups"],
        parameters=[
            SEARCH_PARAM,
            ORDERING_PARAM,
        ],
    )
    def get(self, request):
        institution = get_institution(request)

        groups = ApproverGroup.objects.undeleted().filter(
            institution=institution,
        )

        groups = self.apply_search(groups)
        groups = self.apply_ordering(groups)

        paginator = CustomPageNumberPagination()
        paginated_qs = paginator.paginate_queryset(groups, request)
        serializer = ApproverGroupSerializer(paginated_qs, many=True)
        return paginator.get_paginated_response(serializer.data)

    @extend_schema(tags=["Approver Groups"])
    def post(self, request):
        serializer = ApproverGroupSerializer(
            data=request.data,
            context={
                "request": request,
            },
        )
        serializer.is_valid(raise_exception=True)
        serializer.save()
        return Response(serializer.data, status=status.HTTP_201_CREATED)


class ApproverGroupDetailAPIView(APIView):
    def _get_object(self, request, base_uuid):

        institution = get_institution(request)

        return get_or_raise(
            ApproverGroup.objects.undeleted(),
            message=f"Approver group with base_uuid {base_uuid} not found for this logged-in user's institution.",
            base_uuid=base_uuid,
            institution=institution,
        )

    @extend_schema(tags=["Approver Groups"])
    def get(self, request, base_uuid):
        group = self._get_object(request, base_uuid)
        serializer = ApproverGroupSerializer(group)
        return Response(serializer.data)

    @extend_schema(tags=["Approver Groups"])
    def patch(self, request, base_uuid):
        group = self._get_object(request, base_uuid)
        serializer = ApproverGroupSerializer(
            group,
            data=request.data,
            partial=True,
            context={"request": request},
        )
        if serializer.is_valid():
            serializer.save()
            return Response(serializer.data)
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

    @extend_schema(tags=["Approver Groups"])
    def delete(self, request, base_uuid):
        group = self._get_object(request, base_uuid)
        group.delete()
        return Response(status=status.HTTP_204_NO_CONTENT)


class ApprovalDocumentListAPIView(APIView, SearchOrderMixin):
    @extend_schema(
        tags=["Approval Documents"],
        parameters=[
            SEARCH_PARAM,
            ORDERING_PARAM,
            OpenApiParameter(
                name="content_type_id",
                type=int,
                location=OpenApiParameter.QUERY,
                required=False,
                description="Filter by ContentType ID",
            ),
            OpenApiParameter(
                name="app_label",
                type=str,
                location=OpenApiParameter.QUERY,
                required=False,
                description="Filter by ContentType app_label (must be used with model)",
            ),
            OpenApiParameter(
                name="model",
                type=str,
                location=OpenApiParameter.QUERY,
                required=False,
                description="Filter by ContentType model (must be used with app_label)",
            ),
        ],
    )
    def get(self, request):
        institution = get_institution(request)

        content_type_id = request.query_params.get("content_type_id", None)
        app_label = request.query_params.get("app_label", None)
        model = request.query_params.get("model", None)

        documents = ApprovalDocument.objects.filter(
            institution=institution, deleted_at__isnull=True
        )

        if content_type_id:
            try:
                documents = documents.filter(content_type__id=content_type_id)
            except ValueError:
                return Response(
                    {"detail": "Invalid content_type_id provided."},
                    status=status.HTTP_400_BAD_REQUEST,
                )

        if app_label and model:
            try:
                content_type = ContentType.objects.get(app_label=app_label, model=model)
                documents = documents.filter(content_type=content_type)
            except ContentType.DoesNotExist:
                return Response(
                    {
                        "detail": "ContentType with provided app_label and model not found."
                    },
                    status=status.HTTP_404_NOT_FOUND,
                )
        elif app_label or model:
            return Response(
                {"detail": "Both app_label and model must be provided together."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        documents = self.apply_search(documents)
        documents = self.apply_ordering(documents)

        profiles = Profile.objects.select_related("user").prefetch_related(
            "institutions",
            "user__groups",
            "user__user_permissions",
            Prefetch(
                "user__user_roles",
                queryset=UserRole.objects.select_related("role"),
                to_attr="prefetched_user_roles",
            ),
        )
        groups = ApproverGroup.objects.prefetch_related(
            "roles",
            Prefetch("users", queryset=profiles),
        )
        approver_links = ApprovalDocumentLevelApprovers.objects.filter(
            is_active=True,
            deleted_at__isnull=True,
        ).prefetch_related(
            Prefetch("approver_group", queryset=groups),
        )
        overrider_links = ApprovalDocumentLevelOverriders.objects.filter(
            is_active=True,
            deleted_at__isnull=True,
        ).prefetch_related(
            Prefetch("approver_group", queryset=groups),
        )
        levels = (
            ApprovalDocumentLevel.objects.filter(
                is_active=True,
                deleted_at__isnull=True,
            )
            .select_related("category")
            .prefetch_related(
                Prefetch(
                    "approvaldocumentlevelapprovers_set",
                    queryset=approver_links,
                    to_attr="prefetched_approver_links",
                ),
                Prefetch(
                    "approvaldocumentleveloverriders_set",
                    queryset=overrider_links,
                    to_attr="prefetched_overrider_links",
                ),
            )
            .order_by("level")
        )
        documents = documents.select_related(
            "institution", "content_type"
        ).prefetch_related(
            "actions",
            Prefetch("levels", queryset=levels, to_attr="prefetched_levels"),
        )

        paginator = CustomPageNumberPagination()
        paginated_qs = paginator.paginate_queryset(documents, request)

        page_levels = [
            level for document in paginated_qs for level in document.prefetched_levels
        ]
        user_ids = {
            link.approver_user_id
            for level in page_levels
            for link in level.prefetched_approver_links
            if link.approver_user_id is not None
        } | {
            link.overrider_user_id
            for level in page_levels
            for link in level.prefetched_overrider_links
            if link.overrider_user_id is not None
        }
        users = list(
            ProfileInstitution.objects.filter(id__in=user_ids).prefetch_related(
                Prefetch("profile", queryset=profiles),
            )
        )
        for level in page_levels:
            approver_ids = {
                link.approver_user_id for link in level.prefetched_approver_links
            }
            overrider_ids = {
                link.overrider_user_id for link in level.prefetched_overrider_links
            }
            level.prefetched_approver_users = [
                user for user in users if user.pk in approver_ids
            ]
            level.prefetched_overrider_users = [
                user for user in users if user.pk in overrider_ids
            ]

        serializer = ApprovalDocumentSerializer(paginated_qs, many=True)
        return paginator.get_paginated_response(serializer.data)

    @extend_schema(
        tags=["Approval Documents"],
        request=ApprovalDocumentSerializer,
        responses={201: ApprovalDocumentSerializer},
    )
    def post(self, request):
        serializer = ApprovalDocumentSerializer(
            data=request.data,
            context={"request": request},
        )
        if serializer.is_valid():
            serializer.save()
            return Response(serializer.data, status=status.HTTP_201_CREATED)
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)


class ApprovalDocumentDetailAPIView(APIView):
    def _get_approval_document_object(self, request, base_uuid):
        institution = get_institution(request)
        return get_or_raise(
            queryset=ApprovalDocument.objects.undeleted(),
            message=f"Approval Document with base uuid  {base_uuid} is not found for this logged-in-user's institution",
            base_uuid=base_uuid,
            institution=institution,
        )

    @extend_schema(
        tags=["Approval Documents"],
        responses={200: ApprovalDocumentSerializer},
    )
    def get(self, request, base_uuid):
        document = self._get_approval_document_object(request, base_uuid)
        serializer = ApprovalDocumentSerializer(document)
        return Response(serializer.data)

    @extend_schema(
        operation_id="approval_document_partial_update",
        summary="Partially update an Approval Document",
        description="Update specific fields of an approval document. Only provided fields will be updated.",
        tags=["Approval Documents"],
        responses={200: ApprovalDocumentSerializer},
    )
    def patch(self, request, base_uuid):
        approval_document = self._get_approval_document_object(request, base_uuid)
        serializer = ApprovalDocumentSerializer(
            approval_document,
            data=request.data,
            partial=True,
            context={"request": request},
        )
        serializer.is_valid(raise_exception=True)
        serializer.save()
        return Response(serializer.data, status=status.HTTP_200_OK)

    @extend_schema(tags=["Approval Documents"])
    def delete(self, request, base_uuid):
        document = self.get_approval_document_object(request, base_uuid)
        document.delete()
        return Response(status=status.HTTP_204_NO_CONTENT)


class ApprovalDocumentCategoryListAPIView(APIView, SearchOrderMixin):
    @extend_schema(
        tags=["Approval Document Categories"],
        responses={200: ApprovalDocumentCategorySerializer(many=True)},
        parameters=[
            SEARCH_PARAM,
            ORDERING_PARAM,
        ],
    )
    def get(self, request):
        institution = get_institution(request)

        categories = ApprovalDocumentCategory.objects.undeleted().filter(
            institution=institution,
        )

        categories = self.apply_search(categories)
        categories = self.apply_ordering(categories)

        serializer = ApprovalDocumentCategorySerializer(categories, many=True)
        return Response(serializer.data)

    @extend_schema(
        request=ApprovalDocumentCategorySerializer,
        responses={201: ApprovalDocumentCategorySerializer},
        tags=["Approval Document Categories"],
    )
    def post(self, request):
        serializer = ApprovalDocumentCategorySerializer(data=request.data)
        if serializer.is_valid():
            serializer.save(institution=get_institution(request))
            return Response(serializer.data, status=status.HTTP_201_CREATED)
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)


class ApprovalDocumentCategoryDetailAPIView(APIView):
    def _get_approval_document_category_object(self, request, base_uuid):
        return get_or_raise(
            ApprovalDocumentCategory.objects.undeleted(),
            message=f"Approval Document Category with base uuid {base_uuid} is not found for this logged-in-user's institution",
            base_uuid=base_uuid,
            institution=get_institution(request),
        )

    @extend_schema(tags=["Approval Document Categories"])
    def get(self, request, base_uuid):
        category = self._get_approval_document_category_object(request, base_uuid)
        serializer = ApprovalDocumentCategorySerializer(category)
        return Response(serializer.data)

    @extend_schema(tags=["Approval Document Categories"])
    def patch(self, request, base_uuid):
        category = self._get_approval_document_category_object(request, base_uuid)
        serializer = ApprovalDocumentCategorySerializer(
            category, data=request.data, partial=True, context={"request": request}
        )
        if serializer.is_valid():
            serializer.save()
            return Response(serializer.data)
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

    @extend_schema(tags=["Approval Document Categories"])
    def delete(self, request, base_uuid):
        category = self._get_approval_document_category_object(request, base_uuid)
        category.delete()
        return Response(status=status.HTTP_204_NO_CONTENT)


class ApprovalDocumentLevelListAPIView(APIView, SearchOrderMixin):
    @extend_schema(
        tags=["Approval Document Levels"],
        parameters=[
            SEARCH_PARAM,
            ORDERING_PARAM,
        ],
    )
    def get(self, request):

        institution = get_institution(request)

        levels = ApprovalDocumentLevel.objects.undeleted().filter(
            approval_document__institution=institution, deleted_at__isnull=True
        )

        levels = self.apply_search(levels)
        levels = self.apply_ordering(levels)

        paginator = CustomPageNumberPagination()
        paginated_qs = paginator.paginate_queryset(levels, request)
        serializer = ApprovalDocumentLevelSerializer(paginated_qs, many=True)
        return paginator.get_paginated_response(serializer.data)

    @extend_schema(
        tags=["Approval Document Levels"],
        request=ApprovalDocumentLevelSerializer(many=True),
        responses={201: ApprovalDocumentLevelSerializer(many=True)},
    )
    def post(self, request):
        is_bulk_request = isinstance(request.data, list)
        serializer = ApprovalDocumentLevelSerializer(
            data=request.data,
            many=is_bulk_request,
            context={"request": request},
        )
        if serializer.is_valid():
            serializer.save()
            return Response(serializer.data, status=status.HTTP_201_CREATED)
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)


class ApprovalDocumentLevelDetailAPIView(APIView):
    def get_approval_document_level_object(self, request, base_uuid):
        institution = get_institution(request)

        return get_or_raise(
            queryset=ApprovalDocumentLevel.objects.undeleted(),
            message=f"Approval Document Level with base uuid {base_uuid} is not found for this logged-in-user's institution",
            base_uuid=base_uuid,
            approval_document__institution=institution,
        )

    @extend_schema(tags=["Approval Document Levels"])
    def get(self, request, base_uuid):
        level = self.get_approval_document_level_object(request, base_uuid)
        serializer = ApprovalDocumentLevelSerializer(level)
        return Response(serializer.data)

    @extend_schema(tags=["Approval Document Levels"])
    def patch(self, request, base_uuid):
        level = self.get_approval_document_level_object(request, base_uuid)
        serializer = ApprovalDocumentLevelSerializer(
            level, data=request.data, partial=True
        )
        if serializer.is_valid():
            serializer.save()
            return Response(serializer.data)
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

    @extend_schema(tags=["Approval Document Levels"])
    def delete(self, request, base_uuid):
        level = self.get_approval_document_level_object(request, base_uuid)
        level.delete()
        return Response(status=status.HTTP_204_NO_CONTENT)


class ApprovalListAPIView(APIView, SearchOrderMixin):
    @extend_schema(
        responses={200: ApprovalSerializer(many=True)},
        summary="List of approvals",
        tags=["Approvals"],
        parameters=[
            OpenApiParameter(
                name="status",
                type=str,
                location=OpenApiParameter.QUERY,
                required=False,
                description="Filter by approval status",
            ),
            SEARCH_PARAM,
            ORDERING_PARAM,
            object_base_uuid_param(required=False),
            content_type_id_param(required=False),
        ],
    )
    def _get_content_object(self, request):
        object_base_uuid = request.query_params.get("object_base_uuid", None)
        content_type_id = request.query_params.get("content_type_id", None)

        if not object_base_uuid and not content_type_id:
            return None

        if not object_base_uuid or not content_type_id:
            raise validation_error(
                "content_type_id and object_base_uuid must be provided together."
            )

        try:
            content_type = ContentType.objects.get(pk=content_type_id)
        except (ContentType.DoesNotExist, TypeError, ValueError):
            raise validation_error("Invalid content_type_id provided.")

        model_class = content_type.model_class()

        if not model_class or not issubclass(model_class, BaseApprovableModel):
            raise validation_error(
                "The provided content type does not support approvals."
            )

        try:
            content_object = model_class.objects.undeleted().get(
                base_uuid=object_base_uuid
            )
        except (model_class.DoesNotExist, TypeError, ValueError):
            raise validation_error(
                "The requested object does not exist or has been deleted."
            )

        institution = get_institution(request)

        object_institution = content_object.get_institution()

        if (
            not object_institution
            or getattr(object_institution, "pk", None) != institution.pk
        ):
            raise validation_error(
                "The requested object does not belong to your institution."
            )

        return content_object, content_type

    def get(self, request):
        status_filter = request.query_params.get("status", None)
        institution = get_institution(request)
        content_object_details = self._get_content_object(request)

        approvals = (
            Approval.objects.undeleted()
            .filter(document__institution=institution)
            .select_related("document", "action", "content_type")
        )

        if content_object_details:
            content_object, content_type = content_object_details
            approvals = approvals.filter(
                content_type=content_type,
                object_id=content_object.pk,
            )

        if status_filter:
            approvals = approvals.filter(status=status_filter)

        approvals = self.apply_search(approvals)
        approvals = self.apply_ordering(approvals)

        paginator = CustomPageNumberPagination()
        paginated_qs = paginator.paginate_queryset(approvals, request)
        serializer = ApprovalSerializer(
            paginated_qs,
            many=True,
            context={"request": request},
        )
        return paginator.get_paginated_response(serializer.data)

    @extend_schema(tags=["Approvals"])
    def post(self, request):
        return Response(
            {"detail": "Creating approvals via this endpoint is not allowed."},
            status=status.HTTP_405_METHOD_NOT_ALLOWED,
        )

        serializer = ApprovalSerializer(data=request.data)
        if serializer.is_valid():
            serializer.save()
            return Response(serializer.data, status=status.HTTP_201_CREATED)
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)


class ApprovalDetailAPIView(APIView):
    def get_approval_object(self, request, base_uuid):
        institution = get_institution(request)

        return get_or_raise(
            Approval.objects.undeleted(),
            message=f"Approval with base uuid {base_uuid} is not found for this logged-in-user's institution",
            base_uuid=base_uuid,
            document__institution=institution,
        )

    @extend_schema(tags=["Approvals"])
    def get(self, request, base_uuid):
        approval = self.get_approval_object(request, base_uuid)
        serializer = ApprovalSerializer(approval)
        return Response(serializer.data)

    @extend_schema(tags=["Approvals"])
    def patch(self, request, base_uuid):
        approval = self.get_approval_object(request, base_uuid)
        serializer = ApprovalSerializer(approval, data=request.data, partial=True)
        if serializer.is_valid():
            serializer.save()
            return Response(serializer.data)
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

    @extend_schema(tags=["Approvals"])
    def delete(self, request, base_uuid):
        approval = self.get_approval_object(request, base_uuid)
        approval.delete()
        return Response(status=status.HTTP_204_NO_CONTENT)


class ApprovalRiskAnalysisAPIView(APIView):
    permission_classes = [IsAuthenticated]

    @extend_schema(
        tags=["Approvals"],
        responses={200: OpenApiTypes.OBJECT},
        summary="Analyse approval workflow risk",
    )
    def get(self, request, base_uuid):
        approval = get_object_or_404(
            Approval.objects.select_related("document"),
            base_uuid=base_uuid,
            document__institution=get_institution(request),
            deleted_at__isnull=True,
        )

        if approval.status == "completed":
            if approval.completion_risk_analysis is None:
                approval.capture_completion_risk()

            analysis = {
                **approval.completion_risk_analysis,
                "is_snapshot": True,
                "assessed_at": approval.risk_assessed_at,
            }
        else:
            analysis = {
                **ApprovalRiskAnalysisService(approval).analyse(),
                "is_snapshot": False,
                "assessed_at": None,
            }

        return Response(analysis)


class ApprovalTaskListAPIView(APIView, BranchFilterMixin, SearchOrderMixin):
    @extend_schema(
        tags=["Approval Tasks"],
        request=ApprovalTaskSerializer,
        responses={200: ApprovalTaskSerializer(many=True)},
        parameters=[
            SEARCH_PARAM,
            ORDERING_PARAM,
            OpenApiParameter(
                name="status",
                type=str,
                location=OpenApiParameter.QUERY,
                required=False,
                description="Filter by task status",
            ),
            OpenApiParameter(
                name="assigned_to",
                type=int,
                location=OpenApiParameter.QUERY,
                required=False,
                description="Filter by assigned user ID",
            ),
            OpenApiParameter(
                name="type",
                type=str,
                location=OpenApiParameter.QUERY,
                required=False,
                description="Filter by task type: incoming, open, critical, expired, outgoing",
            ),
        ],
    )
    def get(self, request):
        user = request.user

        institution = get_institution(request)

        tasks_qs = (
            ApprovalTask.objects.filter(
                approval__document__institution=institution, deleted_at__isnull=True
            )
            .select_related(
                "approval",
                "level",
                "approval__document",
                "approval__content_type",
                "approved_by",
            )
            .prefetch_related(
                "level__approvers", "level__approvaldocumentlevelapprovers_set"
            )
        )

        level_access = {}

        def can_access_level(level):
            if level.pk not in level_access:
                level_access[level.pk] = (
                    user in level.get_approver_users() or user in level.get_overriders()
                )
            return level_access[level.pk]

        authorized_task_ids = [
            task.pk for task in tasks_qs if can_access_level(task.level)
        ]

        tasks = tasks_qs.filter(pk__in=authorized_task_ids)

        status_filter = request.query_params.get("status")
        task_type = request.query_params.get("type")

        if status_filter:
            tasks = tasks.filter(status=status_filter)

        now = timezone.now()

        if task_type == "open":
            tasks = tasks.filter(status="pending", approval__status="ongoing")

        elif task_type == "incoming":
            tasks = tasks.filter(
                status="pending",
                approval__status="ongoing",
            )
            incoming_tasks = []
            for task in tasks:
                future_tasks = task.approval.tasks.filter(
                    status__in=["pending", "not_started"],
                    deleted_at__isnull=True,
                ).select_related("level")
                if any(
                    future_task.effective_sequence > task.effective_sequence
                    and can_access_level(future_task.level)
                    for future_task in future_tasks
                ):
                    incoming_tasks.append(task.pk)
            tasks = tasks.filter(pk__in=incoming_tasks)

        elif task_type == "critical":
            tasks = tasks.filter(
                status="pending",
                approval__status="ongoing",
                created_at__lt=now - timedelta(days=7),
                created_at__gte=now - timedelta(days=30),
            )

        elif task_type == "expired":
            tasks = tasks.filter(
                status="pending",
                approval__status="ongoing",
                created_at__lt=now - timedelta(days=30),
            )

        elif task_type == "outgoing":
            tasks = (
                tasks.filter(
                    approved_by=user,
                    status__in=["approved", "rejected", "overridden"],
                    approval__status="ongoing",
                )
                .annotate(
                    has_next=Exists(
                        ApprovalTask.objects.filter(
                            approval=OuterRef("approval"),
                            sequence__gt=OuterRef("sequence"),
                            status__in=["pending", "not_started"],
                            deleted_at__isnull=True,
                        )
                    )
                )
                .filter(has_next=True)
            )

        tasks = self.apply_search(tasks)
        tasks = self.apply_ordering(tasks)

        paginator = CustomPageNumberPagination()
        page = paginator.paginate_queryset(tasks, request)
        serializer = ApprovalTaskSerializer(page, many=True)

        data = serializer.data
        for item, task in zip(data, page):
            approval = task.approval
            ct = approval.content_type
            obj_id = approval.object_id

            item["content_object"] = {
                "app_label": ct.app_label,
                "model": ct.model,
                "object_id": obj_id,
                "url": None,
            }
            try:
                url_name = f"{ct.app_label}-{ct.model}-detail"
                item["content_object"]["url"] = reverse(url_name, kwargs={"pk": obj_id})
            except NoReverseMatch:
                pass

            item["action_display"] = dict(ApprovalTask.STATUS_CHOICES).get(
                task.status, task.status
            )

        return paginator.get_paginated_response(data)

    @extend_schema(tags=["Approval Tasks"])
    def post(self, request):
        serializer = ApprovalTaskSerializer(data=request.data)
        if serializer.is_valid():
            serializer.save()
            return Response(serializer.data, status=status.HTTP_201_CREATED)
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)


class InstitutionApprovalTaskMixin:
    def get_object(self, request, base_uuid):
        institution = get_institution(request)

        return get_or_raise(
            ApprovalTask.objects.filter(
                approval__document__institution=institution,
                level__approval_document__institution=institution,
                deleted_at__isnull=True,
            ),
            message=f"Approval task with UUID '{base_uuid}' not found.",
            base_uuid=base_uuid,
        )


class ApprovalTaskDetailAPIView(InstitutionApprovalTaskMixin, APIView):

    @extend_schema(tags=["Approval Tasks"])
    def get(self, request, base_uuid):
        task = self.get_object(request, base_uuid)
        serializer = ApprovalTaskSerializer(task)
        return Response(serializer.data)

    @extend_schema(tags=["Approval Tasks"])
    def patch(self, request, base_uuid):
        task = self.get_object(request, base_uuid)
        serializer = ApprovalTaskSerializer(task, data=request.data, partial=True)
        if serializer.is_valid():
            serializer.save()
            return Response(serializer.data)
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

    @extend_schema(tags=["Approval Tasks"])
    def delete(self, request, base_uuid):
        task = self.get_object(request, base_uuid)
        task.delete()
        return Response(status=status.HTTP_204_NO_CONTENT)


class ApprovalTaskApproveAPIView(InstitutionApprovalTaskMixin, APIView):

    @extend_schema(
        tags=["Approval Tasks"],
        parameters=[
            OpenApiParameter(
                name="comment",
                type=str,
                location=OpenApiParameter.QUERY,
                required=True,
            )
        ],
    )
    def patch(self, request, base_uuid):
        task = self.get_object(request, base_uuid)
        comment = (request.query_params.get("comment") or "").strip()
        if not comment:
            return Response(
                {"comment": "A comment is required when approving."},
                status=status.HTTP_400_BAD_REQUEST,
            )
        try:
            task.mark_completed(
                request.user,
                comment,
                external_identity=getattr(request, "external_identity", None),
            )
            return Response({"status": "approved"}, status=status.HTTP_200_OK)
        except ValueError as e:
            return Response({"error": str(e)}, status=status.HTTP_400_BAD_REQUEST)


class ApprovalTaskRejectAPIView(InstitutionApprovalTaskMixin, APIView):

    @extend_schema(
        tags=["Approval Tasks"],
        parameters=[
            OpenApiParameter(
                name="comment",
                type=str,
                location=OpenApiParameter.QUERY,
                required=True,
            )
        ],
    )
    def patch(self, request, base_uuid):
        task = self.get_object(request, base_uuid)
        comment = (request.query_params.get("comment") or "").strip()
        if not comment:
            return Response(
                {"comment": "A comment is required when declining an approval."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        try:
            task.mark_rejected(
                request.user,
                comment,
                external_identity=getattr(request, "external_identity", None),
            )
            return Response({"status": "rejected"}, status=status.HTTP_200_OK)
        except ValueError as e:
            return Response({"error": str(e)}, status=status.HTTP_400_BAD_REQUEST)


class ApprovalTaskSendBackAPIView(APIView):
    def get_object(self, base_uuid):

        from utilities.helpers import get_or_raise

        return get_or_raise(
            ApprovalTask.objects.undeleted(),
            "No Approval Task with the provided UUID",
            base_uuid=base_uuid,
        )

    @extend_schema(
        request=SendBackSerializer,
        tags=["Approval Tasks"],
        description=(
            "Sends an approval task to a previous level. When "
            "return_to_sender is true, only the source and target are reset "
            "and the corrected task returns directly to the source."
        ),
    )
    def post(self, request, base_uuid):
        task = self.get_object(base_uuid)

        serializer = SendBackSerializer(
            data=request.data,
            context={
                "request": request,
                "task": task,
            },
        )

        if not serializer.is_valid():
            return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

        target_task = serializer.save()

        return Response(
            {
                "status": "sent_back",
                "target_task_id": target_task.id,
                "return_route_id": (
                    serializer.return_route.id if serializer.return_route else None
                ),
            },
            status=status.HTTP_200_OK,
        )


class ApprovalTaskRecallAPIView(APIView):
    permission_classes = [IsAuthenticated]

    @extend_schema(
        request=RecallApprovalTaskSerializer,
        responses={200: ApprovalTaskSerializer},
        tags=["Approval Tasks"],
        summary="Recall an untouched approval decision",
    )
    def post(self, request, base_uuid):
        task = get_object_or_404(
            ApprovalTask.objects.select_related(
                "approval",
                "approval__document",
                "level",
            ),
            base_uuid=base_uuid,
            approval__document__institution=get_institution(request),
            deleted_at__isnull=True,
        )

        serializer = RecallApprovalTaskSerializer(
            data=request.data,
            context={"request": request, "task": task},
        )
        serializer.is_valid(raise_exception=True)
        recalled_task = serializer.save()

        return Response(
            ApprovalTaskSerializer(
                recalled_task,
                context={"request": request},
            ).data,
            status=status.HTTP_200_OK,
        )


class PendingApprovalTasksListView(APIView):
    permission_classes = [IsAuthenticated]

    @extend_schema(
        responses={
            200: OpenApiResponse(
                response=ApprovalTaskSerializer(many=True),
                description="List of pending approval tasks for the user.",
            ),
        },
        tags=["Approval Workflow"],
    )
    def get(self, request):
        user = request.user
        profile = user.profile

        # Get roles of the user
        user_roles = Role.objects.filter(user_roles__user=user)

        # Get groups the user belongs to directly or via roles
        user_groups = ApproverGroup.objects.filter(
            Q(users=profile) | Q(roles__in=user_roles)
        ).distinct()

        # Find levels where these groups are approvers
        levels = ApprovalDocumentLevel.objects.filter(
            approvers__in=user_groups
        ).distinct()

        # Find pending tasks in those levels
        tasks = ApprovalTask.objects.filter(
            level__in=levels, status="pending", approval__status="ongoing"
        ).order_by("updated_at")

        serializer = ApprovalTaskSerializer(tasks, many=True)
        return Response(serializer.data, status=status.HTTP_200_OK)


class ApprovalTasksDashboardAPIView(APIView, BranchFilterMixin):
    permission_classes = [IsAuthenticated]

    @extend_schema(
        responses={200: OpenApiTypes.OBJECT},
        description="""
        Dashboard counts with FULL dynamic group support:
        - incoming: User will act in a future level
        - open: Current pending task belongs to user (via static OR dynamic group)
        - critical: Open tasks 7–30 days old
        - expired: Open tasks ≥30 days old
        - outgoing: User has already acted AND later levels still pending
        """,
        tags=["Approval Workflow"],
    )
    def get(self, request):
        user = request.user

        institution = get_institution(request)

        now = timezone.now()
        seven_days_ago = now - timedelta(days=7)
        thirty_days_ago = now - timedelta(days=30)

        base_tasks = ApprovalTask.objects.filter(
            approval__status="ongoing",
            approval__document__institution=institution,
            deleted_at__isnull=True,
        ).select_related("level", "approval", "approval__document")

        open_task_ids = []
        incoming_task_ids = []
        outgoing_task_ids = []

        for task in base_tasks:
            level = task.level

            user_can_approve = user in level.get_approver_users()
            user_can_override = user in level.get_overriders()
            user_can_act = user_can_approve or user_can_override

            if task.status == "pending" and user_can_act:
                open_task_ids.append(task.pk)

            if task.status in ("pending", "not_started"):
                current_level = task.effective_sequence
                if current_level is None:
                    continue

                future_tasks = task.approval.tasks.filter(
                    status__in=["pending", "not_started"],
                    deleted_at__isnull=True,
                ).select_related("level")

                if any(
                    future_task.effective_sequence > current_level
                    and (
                        user in future_task.level.get_approver_users()
                        or user in future_task.level.get_overriders()
                    )
                    for future_task in future_tasks
                ):
                    incoming_task_ids.append(task.pk)

            if task.approved_by == user and task.status in [
                "approved",
                "rejected",
                "overridden",
            ]:
                has_future = any(
                    future_task.effective_sequence > task.effective_sequence
                    for future_task in task.approval.tasks.filter(
                        status__in=["pending", "not_started"],
                        deleted_at__isnull=True,
                    ).select_related("level")
                )
                if has_future:
                    outgoing_task_ids.append(task.pk)

        open_tasks = base_tasks.filter(pk__in=open_task_ids)
        incoming_tasks = base_tasks.filter(pk__in=incoming_task_ids)
        outgoing_tasks = base_tasks.filter(pk__in=outgoing_task_ids)

        critical_tasks = open_tasks.filter(
            created_at__lt=seven_days_ago, created_at__gte=thirty_days_ago
        )
        expired_tasks = open_tasks.filter(created_at__lt=thirty_days_ago)

        data = {
            "incoming": {"count": incoming_tasks.count()},
            "open": {"count": open_tasks.count()},
            "critical": {"count": critical_tasks.count()},
            "expired": {"count": expired_tasks.count()},
            "outgoing": {"count": outgoing_tasks.count()},
        }

        return Response(data, status=200)


class ApprovableContentTypesListAPIView(APIView):

    @extend_schema(
        tags=["Approval Documents"],
        description="List all available content types for models that inherit from BaseApprovableModel.",
        parameters=[
            OpenApiParameter(
                name="page",
                type=int,
                location=OpenApiParameter.QUERY,
                required=False,
                description="Page number",
            ),
            SEARCH_PARAM,
        ],
        responses={200: OpenApiTypes.OBJECT},
    )
    def get(self, request):
        search_param = request.query_params.get("search", None)

        all_models = apps.get_models()

        approvable_models = [
            m
            for m in all_models
            if issubclass(m, BaseApprovableModel) and not m._meta.abstract
        ]

        if search_param:
            approvable_models = [
                m
                for m in approvable_models
                if search_param.lower() in m.__name__.lower()
            ]

        def humanize_model_name(name):
            name = re.sub(r"([a-z])([A-Z])", r"\1 \2", name)
            return name.title()

        content_types = []

        for model in sorted(approvable_models, key=lambda m: m.__name__):
            ct = ContentType.objects.get_for_model(model)

            humanized_name = humanize_model_name(model.__name__)
            humanized_plural = (
                humanized_name + "s"
                if not humanized_name.endswith("s")
                else humanized_name + "es"
            )

            content_types.append(
                {
                    "id": ct.id,
                    "app_label": ct.app_label,
                    "model": ct.model,
                    "name": humanized_name,
                    "plural_name": humanized_plural,
                }
            )

        paginator = CustomPageNumberPagination()
        paginated_qs = paginator.paginate_queryset(content_types, request)

        return paginator.get_paginated_response(paginated_qs)


class ApprovableContentTypeDetailAPIView(APIView):
    @extend_schema(
        tags=["Approval Documents"],
        description="Retrieve details for a specific content type corresponding to a model that inherits from BaseApprovableModel. The details include the humanized name and other metadata. The content type must be valid and linked to an approvable model.",
        responses={200: OpenApiTypes.OBJECT},
    )
    def get(self, request, pk):
        try:
            ct = ContentType.objects.get(pk=pk)
        except ContentType.DoesNotExist:
            return Response(
                {"error": "Content type not found"}, status=status.HTTP_404_NOT_FOUND
            )

        model = ct.model_class()
        if not (
            model
            and issubclass(model, BaseApprovableModel)
            and not model._meta.abstract
        ):
            return Response(
                {"error": "This Model doest not correspond to an approvable model"},
                status=status.HTTP_400_BAD_REQUEST,
            )

        # Add the success response
        return Response(
            {
                "id": ct.id,
                "name": ct.name,
                "model": ct.model,
                "app_label": ct.app_label,
                "humanized_name": model._meta.verbose_name.title(),
                # Add any other metadata you want to return
            },
            status=status.HTTP_200_OK,
        )


class ApprovalTaskOverrideAPIView(APIView):
    permission_classes = [IsAuthenticated]

    def get_object(self, pk):
        try:
            return ApprovalTask.objects.get(pk=pk)
        except ApprovalTask.DoesNotExist:
            raise Http404

    @extend_schema(
        tags=["Approval Tasks"],
        parameters=[
            OpenApiParameter(
                name="comment",
                type=str,
                location=OpenApiParameter.QUERY,
                required=True,
                description="Required comment explaining the override action",
            )
        ],
        description="Allows an authorized overrider to override the approval task, marking the entire approval process as completed and terminating all remaining tasks.",
    )
    def patch(self, request, pk):
        task = self.get_object(pk)
        comment = (request.query_params.get("comment") or "").strip()
        if not comment:
            return Response(
                {"comment": "A comment is required when overriding an approval."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        try:
            task.mark_overridden(
                request.user,
                comment,
                external_identity=getattr(request, "external_identity", None),
            )
            return Response({"status": "overridden"}, status=status.HTTP_200_OK)
        except ValidationError as e:
            return Response({"error": str(e)}, status=status.HTTP_400_BAD_REQUEST)
