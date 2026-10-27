from rest_framework import serializers
from django.contrib.contenttypes.models import ContentType
from django.utils import timezone
from approval.models import (
    Action,
    AllowedUser,
    ApprovalDocumentCategory,
    ApproverGroup,
    ApprovalDocument,
    ApprovalDocumentLevel,
    Approval,
    ApprovalTask,
    ApprovalTaskAction,
    ApprovalReturnRoute,
    ApproverGroupUser,
    ApproverGroupRole,
    ApprovalDocumentLevelApprovers,
    ApprovalDocumentLevelOverriders,
    BaseApprovableModel,
)
import re
from users.serializers import ProfileInstitutionSerializer
from users.models import Profile, ProfileInstitution, Role
from utilities.helpers import UUIDRelatedField, get_institution, validation_error
from users.models import CustomUser
from django.db import transaction
from django.db.models import Q

SCOPED_APPROVAL_DOCUMENT_CONTENT_TYPES = {
    ("budget", "budgetitemallocation"): {("budget", "budgettype")},
    ("budget", "budgetadjustmentitemallocation"): {("budget", "budgettype")},
    ("requisitions", "requisition"): {
        ("requisitions", "requisitiontype"),
    },
}


def _content_type_key(content_type):
    if not content_type:
        return None

    return (content_type.app_label, content_type.model)


class ActionSerializer(serializers.ModelSerializer):
    class Meta:
        model = Action
        fields = ["id", "name", "code", "description"]


class ApproverGroupUserSerializer(serializers.ModelSerializer):
    user_fullname = serializers.CharField(source="user.user.fullname", read_only=True)

    class Meta:
        model = ApproverGroupUser
        fields = ["id", "user", "user_fullname"]


class ApproverGroupRoleSerializer(serializers.ModelSerializer):
    role_name = serializers.CharField(source="role.name", read_only=True)

    class Meta:
        model = ApproverGroupRole
        fields = ["id", "role", "role_name"]


class ApproverGroupSerializer(serializers.ModelSerializer):
    users = serializers.PrimaryKeyRelatedField(
        queryset=Profile.objects.all(),
        many=True,
        required=False,
        allow_empty=True,
        write_only=True,
    )
    roles = serializers.PrimaryKeyRelatedField(
        queryset=Role.objects.all(),
        many=True,
        required=False,
        allow_empty=True,
        write_only=True,
    )
    users_display = serializers.SerializerMethodField(read_only=True)
    roles_display = serializers.SerializerMethodField(read_only=True)

    class Meta:
        model = ApproverGroup
        fields = [
            "id",
            "base_uuid",
            "institution",
            "name",
            "description",
            "users",
            "roles",
            "users_display",
            "roles_display",
        ]
        read_only_fields = ["base_uuid", "users_display", "roles_display"]

    def get_users_display(self, obj):
        from users.serializers import ProfileSerializer

        return ProfileSerializer(obj.users.all(), many=True, context=self.context).data

    def get_roles_display(self, obj):
        from users.serializers import RoleSerializer

        return RoleSerializer(obj.roles.all(), many=True, context=self.context).data

    def validate(self, data):
        request = self.context.get("request")

        institution = get_institution(request)

        if not institution:
            raise validation_error("Institution context is required.")

        data["institution"] = institution

        if request and request.method in [
            "POST",
            "PATCH",
        ]:
            institution = get_institution(request)

            users = data.get("users", [])
            roles = data.get("roles", [])

            if users:
                invalid_users = Profile.objects.filter(
                    id__in=[u.id for u in users]
                ).exclude(institution=institution)
                if invalid_users.exists():
                    raise validation_error(
                        "All users must belong to the same institution as the group."
                    )

            if roles:
                invalid_roles = Role.objects.filter(
                    id__in=[r.id for r in roles]
                ).exclude(institution=institution)
                if invalid_roles.exists():
                    raise validation_error(
                        "All roles must be associated with the same institution as the group."
                    )

        return data

    def create(self, validated_data):
        users = validated_data.pop("users", [])
        roles = validated_data.pop("roles", [])
        group = ApproverGroup.objects.create(**validated_data)
        for user in users:
            ApproverGroupUser.objects.create(approver_group=group, user=user)
        for role in roles:
            ApproverGroupRole.objects.create(approver_group=group, role=role)
        return group


class AllowedUserSerializer(serializers.ModelSerializer):
    user = ProfileInstitutionSerializer(read_only=True)
    content_type = serializers.SerializerMethodField(read_only=True)
    content_object = serializers.SerializerMethodField(read_only=True)

    class Meta:
        model = AllowedUser
        fields = [
            "id",
            "base_uuid",
            "content_type",
            "object_id",
            "content_object",
            "user",
        ]

    def get_content_type(self, obj):
        return {
            "id": obj.content_type_id,
            "app_label": obj.content_type.app_label,
            "model": obj.content_type.model,
            "name": obj.content_type.name,
        }

    def get_content_object(self, obj):
        content_object = obj.content_object

        if not content_object:
            return None

        return {
            "base_uuid": str(getattr(content_object, "base_uuid", "")),
            "reference_code": getattr(content_object, "reference_code", None),
        }


class AllowedUserCreateSerializer(serializers.Serializer):
    content_type = serializers.PrimaryKeyRelatedField(
        queryset=ContentType.objects.all(),
        required=True,
    )
    object_id = serializers.UUIDField(
        required=False,
        allow_null=True,
    )
    users = UUIDRelatedField(
        queryset=ProfileInstitution.objects.all(),
        many=True,
        required=True,
        allow_empty=True,
    )

    def validate(self, attrs):
        institution = self.context.get("institution")
        users = attrs.get("users", [])

        if institution:
            invalid_users = [
                user
                for user in users
                if user.institution_id != institution.id or user.deleted_at
            ]
            if invalid_users:
                raise validation_error(
                    {"users": "All users must belong to the current institution."}
                )

        return attrs

    def save(self, **kwargs):
        content_type = self.validated_data["content_type"]
        object_id = self.validated_data.get("object_id")
        users = self.validated_data["users"]
        user_ids = [user.id for user in users]

        with transaction.atomic():
            AllowedUser.objects.filter(
                content_type=content_type,
                object_id=object_id,
            ).exclude(user_id__in=user_ids).update(
                deleted_at=timezone.now(),
                is_active=False,
            )

            allowed_users = []
            for user in users:
                allowed_user, _ = AllowedUser.objects.get_or_create(
                    content_type=content_type,
                    object_id=object_id,
                    user=user,
                )

                if allowed_user.deleted_at or not allowed_user.is_active:
                    allowed_user.deleted_at = None
                    allowed_user.is_active = True
                    allowed_user.save(update_fields=["deleted_at", "is_active"])

                allowed_users.append(allowed_user)

        return allowed_users


class ApprovalDocumentLevelApproverSerializer(serializers.ModelSerializer):
    approver_group = serializers.SerializerMethodField(read_only=True)

    class Meta:
        model = ApprovalDocumentLevelApprovers
        fields = ["id", "approver_group"]

    def get_approver_group(self, obj):
        from .serializers import ApproverGroupSerializer

        return ApproverGroupSerializer(obj.approver_group, context=self.context).data


class ApprovalDocumentLevelOverriderSerializer(serializers.ModelSerializer):
    approver_group = serializers.SerializerMethodField(read_only=True)

    class Meta:
        model = ApprovalDocumentLevelOverriders
        fields = ["id", "approver_group"]

    def get_approver_group(self, obj):
        from .serializers import ApproverGroupSerializer

        return ApproverGroupSerializer(obj.approver_group, context=self.context).data


class ApprovalDocumentCategorySerializer(serializers.ModelSerializer):
    class Meta:
        model = ApprovalDocumentCategory
        fields = [
            "id",
            "description",
            "base_uuid",
            "reference_code",
            "name",
            "level",
        ]
        read_only_fields = ["institution"]


class ApprovalDocumentLevelListSerializer(serializers.ListSerializer):
    def create(self, validated_data):
        with transaction.atomic():
            return [self.child.create(item) for item in validated_data]


class ApprovalDocumentLevelSerializer(serializers.ModelSerializer):
    FINAL_CATEGORY_LEVEL_LIMIT_MESSAGE = (
        "The final approval category can contain only one level."
    )

    approval_document = serializers.PrimaryKeyRelatedField(
        queryset=ApprovalDocument.objects.all(),
    )
    category = UUIDRelatedField(
        queryset=ApprovalDocumentCategory.objects.all(),
    )
    approvers = UUIDRelatedField(
        queryset=ApproverGroup.objects.all(),
        many=True,
        required=False,
        allow_empty=True,
        write_only=True,
    )
    approver_users = UUIDRelatedField(
        queryset=ProfileInstitution.objects.all(),
        many=True,
        required=False,
        allow_empty=True,
        write_only=True,
    )
    overriders = UUIDRelatedField(
        queryset=ApproverGroup.objects.all(),
        many=True,
        required=False,
        allow_empty=True,
        write_only=True,
    )
    overrider_users = UUIDRelatedField(
        queryset=ProfileInstitution.objects.all(),
        many=True,
        required=False,
        allow_empty=True,
        write_only=True,
    )
    approvers_detail = serializers.SerializerMethodField()
    overriders_detail = serializers.SerializerMethodField()

    class Meta:
        model = ApprovalDocumentLevel
        fields = "__all__"
        list_serializer_class = ApprovalDocumentLevelListSerializer
        read_only_fields = [
            "level",
            "approvers_detail",
            "overriders_detail",
            "is_deleted",
            "created_at",
            "updated_at",
            "external_base_uuid",
            "created_by",
            "updated_by",
            "base_uuid",
            "deleted_at",
            "is_active",
        ]

    def validate(self, data):
        request = self.context.get("request")
        institution = get_institution(request) if request else None
        approval_document = self.context.get("approval_document") or data.get(
            "approval_document"
        )
        category = data.get(
            "category",
            getattr(self.instance, "category", None),
        )

        final_category = (
            ApprovalDocumentCategory.objects.filter(
                institution=category.institution,
                is_active=True,
                deleted_at__isnull=True,
            )
            .order_by("-level", "-id")
            .first()
            if category
            else None
        )

        if approval_document and category and category == final_category:
            existing_final_level = ApprovalDocumentLevel.objects.filter(
                approval_document=approval_document,
                category=final_category,
                is_active=True,
                deleted_at__isnull=True,
            )

            if self.instance:
                existing_final_level = existing_final_level.exclude(pk=self.instance.pk)

            if existing_final_level.exists():
                raise validation_error(
                    {"category": self.FINAL_CATEGORY_LEVEL_LIMIT_MESSAGE}
                )

        require_approval_document = self.context.get("require_approval_document", False)

        if require_approval_document and not approval_document:
            raise validation_error(
                {"error": "Approval document must be injected via context."}
            )

        if request and request.method in ["POST", "PATCH"]:
            if (
                approval_document
                and institution
                and approval_document.institution_id != institution.id
            ):
                raise validation_error(
                    {
                        "approval_document": (
                            "Approval document must belong to the same institution."
                        )
                    }
                )

            if category and institution and category.institution_id != institution.id:
                raise validation_error(
                    {"category": "Category must belong to the same institution."}
                )

            approvers = data.get("approvers", [])
            approver_users = data.get("approver_users", [])
            overriders = data.get("overriders", [])
            overrider_users = data.get("overrider_users", [])

            if institution:
                if approvers:
                    invalid = ApproverGroup.objects.filter(
                        id__in=[a.id for a in approvers]
                    ).exclude(institution=institution)
                    if invalid.exists():
                        raise validation_error(
                            {"error": "Approvers must belong to same institution."}
                        )

                if approver_users:
                    invalid = ProfileInstitution.objects.filter(
                        id__in=[u.id for u in approver_users]
                    ).exclude(institution=institution)
                    if invalid.exists():
                        raise validation_error(
                            {"error": "Approver users must belong to same institution."}
                        )

                if overriders:
                    invalid = ApproverGroup.objects.filter(
                        id__in=[o.id for o in overriders]
                    ).exclude(institution=institution)
                    if invalid.exists():
                        raise validation_error(
                            {"error": "Overriders must belong to same institution."}
                        )

                if overrider_users:
                    invalid = ProfileInstitution.objects.filter(
                        id__in=[u.id for u in overrider_users]
                    ).exclude(institution=institution)
                    if invalid.exists():
                        raise validation_error(
                            {
                                "error": "Overrider users must belong to same institution."
                            }
                        )

        return data

    def create(self, validated_data):
        approvers = validated_data.pop("approvers", [])
        approver_users = validated_data.pop("approver_users", [])
        overriders = validated_data.pop("overriders", [])
        overrider_users = validated_data.pop("overrider_users", [])

        approval_document = validated_data["approval_document"]
        category = validated_data["category"]

        final_category = (
            ApprovalDocumentCategory.objects.filter(
                institution=category.institution,
                is_active=True,
                deleted_at__isnull=True,
            )
            .order_by("-level", "-id")
            .first()
        )

        if category == final_category:
            if ApprovalDocumentLevel.objects.filter(
                approval_document=approval_document,
                category=final_category,
                is_active=True,
                deleted_at__isnull=True,
            ).exists():
                raise validation_error(
                    {"category": self.FINAL_CATEGORY_LEVEL_LIMIT_MESSAGE}
                )

        with transaction.atomic():
            level = ApprovalDocumentLevel.objects.create(**validated_data)

            for approver in approvers:
                record = ApprovalDocumentLevelApprovers.objects.create(
                    approval_document_level=level,
                    approver_group=approver,
                    approver_user=None,
                )
                record.clean()

            for user in approver_users:
                record = ApprovalDocumentLevelApprovers.objects.create(
                    approval_document_level=level,
                    approver_group=None,
                    approver_user=user,
                )
                record.clean()

            for overrider in overriders:
                record = ApprovalDocumentLevelOverriders.objects.create(
                    approval_document_level=level,
                    approver_group=overrider,
                    overrider_user=None,
                )
                record.clean()

            for user in overrider_users:
                record = ApprovalDocumentLevelOverriders.objects.create(
                    approval_document_level=level,
                    approver_group=None,
                    overrider_user=user,
                )
                record.clean()

            return level

    def get_approvers_detail(self, instance):
        links = getattr(instance, "prefetched_approver_links", None)
        if links is None:
            links = ApprovalDocumentLevelApprovers.objects.filter(
                approval_document_level=instance,
                is_active=True,
                deleted_at__isnull=True,
            )
        return ApprovalDocumentLevelApproverSerializer(
            links,
            many=True,
            context=self.context,
        ).data

    def get_overriders_detail(self, instance):
        links = getattr(instance, "prefetched_overrider_links", None)
        if links is None:
            links = ApprovalDocumentLevelOverriders.objects.filter(
                approval_document_level=instance,
                is_active=True,
                deleted_at__isnull=True,
            )
        return ApprovalDocumentLevelOverriderSerializer(
            links,
            many=True,
            context=self.context,
        ).data

    def to_representation(self, instance):
        from users.serializers import ProfileInstitutionSerializer

        repr = super().to_representation(instance)

        approver_users = getattr(instance, "prefetched_approver_users", None)
        if approver_users is None:
            approver_user_ids = ApprovalDocumentLevelApprovers.objects.filter(
                approval_document_level=instance,
                approver_user__isnull=False,
                is_active=True,
                deleted_at__isnull=True,
            ).values_list("approver_user_id", flat=True)
            approver_users = ProfileInstitution.objects.filter(id__in=approver_user_ids)

        overrider_users = getattr(instance, "prefetched_overrider_users", None)
        if overrider_users is None:
            overrider_user_ids = ApprovalDocumentLevelOverriders.objects.filter(
                approval_document_level=instance,
                overrider_user__isnull=False,
                is_active=True,
                deleted_at__isnull=True,
            ).values_list("overrider_user_id", flat=True)
            overrider_users = ProfileInstitution.objects.filter(
                id__in=overrider_user_ids
            )

        repr["approver_users"] = ProfileInstitutionSerializer(
            approver_users,
            many=True,
            context=self.context,
        ).data
        repr["overrider_users"] = ProfileInstitutionSerializer(
            overrider_users,
            many=True,
            context=self.context,
        ).data
        repr["category"] = ApprovalDocumentCategorySerializer(
            instance.category, context=self.context
        ).data
        return repr


class ApprovalDocumentSerializer(serializers.ModelSerializer):
    institution_name = serializers.CharField(
        source="institution.institution_name", read_only=True
    )
    levels = serializers.SerializerMethodField()

    content_type_name = serializers.SerializerMethodField()
    actions = serializers.PrimaryKeyRelatedField(
        queryset=Action.objects.all(),
        many=True,
        required=False,
        allow_empty=True,
    )
    scope_content_type = serializers.PrimaryKeyRelatedField(
        queryset=ContentType.objects.all(),
        required=False,
        allow_null=True,
    )
    scope_object = serializers.UUIDField(
        source="scope_object_id",
        required=False,
        allow_null=True,
        write_only=True,
    )

    class Meta:
        model = ApprovalDocument
        fields = [
            "id",
            "base_uuid",
            "institution",
            "institution_name",
            "description",
            "document_name",
            "content_type",
            "content_type_name",
            "actions",
            "allow_decline_to_continue",
            "scope_content_type",
            "scope_object",
            "scope_object_id",
            "levels",
        ]
        read_only_fields = ["base_uuid", "institution", "scope_object_id"]

    def get_levels(self, instance):
        levels = getattr(instance, "prefetched_levels", None)
        if levels is None:
            levels = instance.levels.filter(
                is_active=True,
                deleted_at__isnull=True,
            ).order_by("level")
        return ApprovalDocumentLevelSerializer(
            levels,
            many=True,
            context=self.context,
        ).data

    def validate(self, attrs):
        request = self.context.get("request")
        institution = (
            get_institution(request) if request else self.context.get("institution")
        )

        if institution:
            attrs["institution"] = institution

        content_type = attrs.get(
            "content_type",
            getattr(self.instance, "content_type", None),
        )
        scope_content_type = attrs.get(
            "scope_content_type",
            getattr(self.instance, "scope_content_type", None),
        )
        scope_object_id = attrs.get(
            "scope_object_id",
            getattr(self.instance, "scope_object_id", None),
        )

        has_scope_content_type = scope_content_type is not None
        has_scope_object = scope_object_id is not None

        if has_scope_content_type != has_scope_object:
            raise validation_error(
                {
                    "scope": "scope_content_type and scope_object must be provided together."
                }
            )

        if not has_scope_content_type and not has_scope_object:
            return attrs

        allowed_scope_content_types = SCOPED_APPROVAL_DOCUMENT_CONTENT_TYPES.get(
            _content_type_key(content_type),
        )

        if not allowed_scope_content_types:
            raise validation_error(
                {
                    "scope_content_type": "This content type does not support scoped approval documents."
                }
            )

        scope_content_type_key = _content_type_key(scope_content_type)

        if scope_content_type_key not in allowed_scope_content_types:
            allowed = [
                f"{app_label}.{model}"
                for app_label, model in sorted(allowed_scope_content_types)
            ]
            raise validation_error(
                {
                    "scope_content_type": f"Invalid scope content type. Allowed: {', '.join(allowed)}."
                }
            )

        scope_model = scope_content_type.model_class()

        if not scope_model:
            raise validation_error(
                {
                    "scope_content_type": "Scope content type does not resolve to a model."
                }
            )

        scope_qs = scope_model.objects.filter(base_uuid=scope_object_id)

        if hasattr(scope_model, "deleted_at"):
            scope_qs = scope_qs.filter(deleted_at__isnull=True)

        scope_object = scope_qs.first()

        if not scope_object:
            raise validation_error(
                {
                    "scope_object": "Scope object was not found for the selected scope content type."
                }
            )

        if institution and hasattr(scope_object, "institution_id"):
            if scope_object.institution_id != institution.id:
                raise validation_error(
                    {
                        "scope_object": "Scope object must belong to the current institution."
                    }
                )

        return attrs

    def get_content_type_name(self, obj):
        model_class = obj.content_type.model_class()
        if not model_class:
            return obj.content_type.name
        name = model_class.__name__
        name = re.sub(r"(?<!^)(?=[A-Z])", " ", name)
        return name.strip()

    def create(self, validated_data):
        actions = validated_data.pop("actions", [])

        with transaction.atomic():
            document = ApprovalDocument.objects.create(**validated_data)
            document.actions.set(actions)
            document.full_clean()

        return document

    def update(self, instance, validated_data):
        actions = validated_data.pop("actions", None)

        with transaction.atomic():
            for attr, value in validated_data.items():
                setattr(instance, attr, value)

            instance.save()

            if actions is not None:
                instance.actions.set(actions)
                instance.full_clean()

        return instance

    def to_representation(self, instance):
        representation = super().to_representation(instance)
        representation["content_type"] = {
            "id": instance.content_type_id,
            "name": self.get_content_type_name(instance),
        }
        representation["actions"] = [
            {"id": action.id, "name": action.name} for action in instance.actions.all()
        ]
        return representation


class ApprovalReturnRouteSerializer(serializers.ModelSerializer):
    source_level = serializers.SerializerMethodField()
    target_level = serializers.SerializerMethodField()

    def get_source_level(self, obj):
        return obj.source_task.effective_sequence

    def get_target_level(self, obj):
        return obj.target_task.effective_sequence

    sent_by_fullname = serializers.CharField(
        source="sent_by.fullname",
        read_only=True,
        allow_null=True,
    )

    class Meta:
        model = ApprovalReturnRoute
        fields = [
            "id",
            "base_uuid",
            "approval",
            "source_task",
            "source_level",
            "target_task",
            "target_level",
            "parent_route",
            "description",
            "status",
            "sent_by",
            "sent_by_fullname",
            "returned_at",
            "cancelled_at",
            "created_at",
        ]
        read_only_fields = fields


class ApprovalTaskActionSerializer(serializers.ModelSerializer):
    acted_by_fullname = serializers.CharField(
        source="acted_by.fullname", read_only=True, allow_null=True
    )

    class Meta:
        model = ApprovalTaskAction
        fields = [
            "id",
            "base_uuid",
            "action",
            "acted_by",
            "acted_by_fullname",
            "from_status",
            "to_status",
            "from_level",
            "to_level",
            "comment",
            "return_route",
            "created_at",
        ]
        read_only_fields = fields


class ApprovalTaskSerializer(serializers.ModelSerializer):
    level_name = serializers.CharField(source="level.name", read_only=True)
    approval_document_description = serializers.CharField(
        source="approval.document.description", read_only=True
    )
    approved_by_fullname = serializers.CharField(
        source="approved_by.fullname", read_only=True, allow_null=True
    )
    level = ApprovalDocumentLevelSerializer(read_only=True)

    object_id = serializers.CharField(read_only=True)
    object_base_uuid = serializers.CharField(read_only=True)
    actions = ApprovalTaskActionSerializer(many=True, read_only=True)
    active_return_route = serializers.SerializerMethodField()
    timing = serializers.SerializerMethodField()
    can_recall = serializers.SerializerMethodField()

    def get_can_recall(self, obj):
        request = self.context.get("request")
        profile_institution = (
            getattr(request, "profile_institution", None) if request else None
        )
        return obj.can_be_recalled_by(profile_institution)

    def get_timing(self, obj):
        return getattr(obj, "_workflow_timing", None)

    def get_active_return_route(self, obj):
        route = (
            obj.incoming_return_routes.filter(
                status="awaiting_correction",
            )
            .select_related(
                "source_task__level",
                "target_task__level",
                "sent_by",
            )
            .order_by("-created_at")
            .first()
        )
        return ApprovalReturnRouteSerializer(route).data if route else None

    class Meta:
        model = ApprovalTask
        fields = [
            "id",
            "base_uuid",
            "sequence",
            "status",
            "comment",
            "approved_by",
            "approved_by_fullname",
            "updated_at",
            "level",
            "level_name",
            "approval_document_description",
            "object_id",
            "object_base_uuid",
            "actions",
            "active_return_route",
            "timing",
            "can_recall",
        ]
        read_only_fields = ["approved_by", "updated_at"]


class RecallApprovalTaskSerializer(serializers.Serializer):
    comment = serializers.CharField(
        required=True,
        allow_blank=False,
        trim_whitespace=True,
        max_length=500,
    )

    def save(self, **kwargs):
        task = self.context["task"]
        request = self.context["request"]
        return task.recall(
            profile_institution=request.profile_institution,
            comment=self.validated_data["comment"],
        )


class ApprovalSerializer(serializers.ModelSerializer):
    tasks = serializers.SerializerMethodField()
    return_routes = serializers.SerializerMethodField()
    document = ApprovalDocumentSerializer(read_only=True)
    action = ActionSerializer(read_only=True)
    initiation = serializers.SerializerMethodField()

    def get_initiation(self, instance):
        content_object = instance.content_object
        if not content_object:
            return None

        created_by = getattr(content_object, "created_by", None)

        return {
            "created_at": getattr(
                content_object,
                "created_at",
                instance.created_at,
            ),
            "created_by_fullname": (
                created_by.fullname or created_by.username or created_by.email
                if created_by
                else "System"
            ),
        }

    def get_tasks(self, instance):
        now = timezone.now()
        tasks = list(
            instance.tasks.filter(
                deleted_at__isnull=True,
            ).select_related("level", "level__category")
        )
        tasks.sort(
            key=lambda task: (
                task.sequence is not None,
                task.effective_sequence,
            )
        )

        actions = list(
            ApprovalTaskAction.objects.undeleted()
            .filter(approval=instance)
            .select_related("task")
            .order_by("created_at", "pk")
        )

        terminal_action_by_status = {
            "approved": "approved",
            "rejected": "rejected",
            "overridden": "overridden",
        }

        for task in tasks:
            task._workflow_timing = None

            if task.status == "pending":
                previous_actions = [
                    action for action in actions if action.created_at <= task.updated_at
                ]
                previous_action = previous_actions[-1] if previous_actions else None
                started_at = task.updated_at

                task._workflow_timing = {
                    "state": "waiting",
                    "started_at": started_at,
                    "ended_at": None,
                    "elapsed_seconds": max(
                        0,
                        int((now - started_at).total_seconds()),
                    ),
                    "started_by": (
                        previous_action.action
                        if previous_action
                        else "workflow_initiated"
                    ),
                }
                continue

            expected_action = terminal_action_by_status.get(task.status)
            if not expected_action:
                continue

            task_actions = [
                action
                for action in actions
                if action.task_id == task.pk and action.action == expected_action
            ]
            if not task_actions:
                continue

            completed_action = task_actions[-1]
            previous_actions = [
                action
                for action in actions
                if action.created_at < completed_action.created_at
            ]
            previous_action = previous_actions[-1] if previous_actions else None
            started_at = (
                previous_action.created_at if previous_action else instance.created_at
            )

            task._workflow_timing = {
                "state": "completed",
                "started_at": started_at,
                "ended_at": completed_action.created_at,
                "elapsed_seconds": max(
                    0,
                    int((completed_action.created_at - started_at).total_seconds()),
                ),
                "started_by": (
                    previous_action.action if previous_action else "workflow_initiated"
                ),
            }

        return ApprovalTaskSerializer(
            tasks,
            many=True,
            context=self.context,
        ).data

    def get_return_routes(self, instance):
        routes = instance.return_routes.filter(
            deleted_at__isnull=True,
        )
        return ApprovalReturnRouteSerializer(
            routes,
            many=True,
            context=self.context,
        ).data

    class Meta:
        model = Approval
        fields = [
            "created_at",
            "id",
            "base_uuid",
            "status",
            "completion_risk_score",
            "completion_risk_rating",
            "risk_assessed_at",
            "document",
            "action",
            "content_type",
            "object_id",
            "tasks",
            "return_routes",
            "initiation",
        ]


class AuditUserSerializer(serializers.ModelSerializer):
    class Meta:
        model = CustomUser
        fields = [
            "id",
            "fullname",
            "base_uuid",
            "reference_code",
            "email",
        ]


class CreatedByProfileSerializer(serializers.ModelSerializer):
    fullname = serializers.CharField(source="profile.user.fullname", read_only=True)
    base_uuid = serializers.UUIDField(source="profile.user.base_uuid", read_only=True)

    class Meta:
        model = ProfileInstitution
        fields = ["fullname", "base_uuid", "profile_photo_base64"]
        read_only_fields = fields


class ContentTypeIdSerializerMixin(serializers.ModelSerializer):
    allow_changes = serializers.SerializerMethodField()

    DEFAULT_READ_ONLY_FIELDS = [
        "id",
        "base_uuid",
        "is_deleted",
        "updated_at",
        "created_at",
        "deleted_at",
        "is_active",
        "updated_by",
        "created_by",
        "model_content_type_id",
        "allow_changes",
    ]

    model_content_type_id = serializers.SerializerMethodField(read_only=True)
    is_approvable = serializers.SerializerMethodField(read_only=True)

    created_by = serializers.SerializerMethodField()

    def get_model_content_type_id(self, obj):
        model_class = getattr(obj, "model", None) or obj.__class__
        return ContentType.objects.get_for_model(model_class).id

    def get_is_approvable(self, obj):
        model_class = getattr(obj, "model", None) or obj.__class__
        return issubclass(model_class, BaseApprovableModel)

    def get_allow_changes(self, obj):
        return obj.allows_changes() if hasattr(obj, "allows_changes") else False

    def get_created_by(self, obj):
        created_by = getattr(obj, "created_by", None)

        if not created_by:
            return None

        request = self.context.get("request")
        institution = get_institution(request) if request else None

        if institution:
            profile_institution = (
                ProfileInstitution.objects.undeleted()
                .filter(
                    profile__user=created_by,
                    institution=institution,
                )
                .select_related("profile__user")
                .only(
                    "profile__user__fullname",
                    "profile__user__base_uuid",
                    "profile_photo_base64",
                )
                .first()
            )

            if profile_institution:
                return CreatedByProfileSerializer(profile_institution).data

        return AuditUserSerializer(created_by, context=self.context).data

    def get_extra_kwargs(self):
        extra_kwargs = super().get_extra_kwargs()
        for field in self.DEFAULT_READ_ONLY_FIELDS:
            extra_kwargs.setdefault(field, {})["read_only"] = True
        return extra_kwargs

    class Meta:
        abstract = True


class BaseApprovableSerializer(ContentTypeIdSerializerMixin):
    approvals = serializers.SerializerMethodField()

    updated_by = AuditUserSerializer(read_only=True)

    allow_changes = serializers.SerializerMethodField()

    DEFAULT_READ_ONLY_FIELDS = [
        "id",
        "base_uuid",
        "is_deleted",
        "updated_at",
        "created_at",
        "approvals",
        "approval_status",
        "deleted_at",
        "is_active",
        "original_data",
        "updated_by",
        "created_by",
        "model_content_type_id",
        "allow_changes",
    ]

    def create(self, validated_data):
        request = self.context.get("request")
        user = getattr(request, "user", None) if request else None

        if user and user.is_authenticated:
            validated_data.setdefault("created_by", user)
            validated_data.setdefault("updated_by", user)

        return super().create(validated_data)

    def save(self, **kwargs):
        request = self.context.get("request")
        user = getattr(request, "user", None) if request else None

        if user and user.is_authenticated:
            if self.instance is None:
                kwargs.setdefault("created_by", user)
                kwargs.setdefault("updated_by", user)
            else:
                kwargs["updated_by"] = user

        return super().save(**kwargs)

    def get_approvals(self, obj):
        model_class = getattr(obj, "model", None) or obj.__class__
        content_type = ContentType.objects.get_for_model(model_class)

        object_id = getattr(obj, "pk", None)
        if object_id is None:
            return []

        approvals = (
            Approval.objects.filter(
                content_type=content_type,
                object_id=obj.pk,
                deleted_at__isnull=True,
                tasks__isnull=False,
                tasks__deleted_at__isnull=True,
            )
            .select_related("document", "action", "content_type")
            .prefetch_related("tasks__level", "document__levels")
            .distinct()
        )

        return ApprovalSerializer(
            approvals,
            many=True,
            context=self.context,
        ).data

    def get_extra_kwargs(self):
        extra_kwargs = super().get_extra_kwargs()
        for field in self.DEFAULT_READ_ONLY_FIELDS:
            extra_kwargs.setdefault(field, {})["read_only"] = True
        return extra_kwargs

    def get_allow_changes(self, obj):
        return obj.allows_changes()

    class Meta:
        abstract = True
        fields = [
            "id",
            "approval_status",
            "approvals",
            "created_by",
            "updated_by",
            "model_content_type_id",
            "allow_changes",
        ]


class BaseUnApprovableSerializer(ContentTypeIdSerializerMixin):
    DEFAULT_READ_ONLY_FIELDS = [
        "id",
        "base_uuid",
        "is_deleted",
        "updated_at",
        "created_at",
        "deleted_at",
        "is_active",
        "updated_by",
        "created_by",
        "model_content_type_id",
    ]

    def save(self, **kwargs):
        request = self.context.get("request")
        user = getattr(request, "user", None) if request else None

        if self.instance is None:
            if user and "created_by" not in kwargs:
                kwargs["created_by"] = user

        else:
            if user:
                kwargs["updated_by"] = user

        return super().save(**kwargs)

    def get_extra_kwargs(self):
        extra_kwargs = super().get_extra_kwargs()
        for field in self.DEFAULT_READ_ONLY_FIELDS:
            extra_kwargs.setdefault(field, {})["read_only"] = True
        return extra_kwargs

    class Meta:
        abstract = True
        fields = [
            "id",
            "created_by",
            "updated_by",
            "model_content_type_id",
        ]


class SendBackSerializer(serializers.Serializer):

    target_level = serializers.IntegerField(required=False, min_value=1)
    comment = serializers.CharField(
        required=True,
        allow_blank=False,
        trim_whitespace=True,
    )
    return_to_sender = serializers.BooleanField(required=False, default=False)

    def validate(self, attrs):
        if attrs.get("return_to_sender") and not attrs.get("comment", "").strip():
            raise validation_error(
                "An instruction is required when the corrected approval must return to the sender."
            )

        return attrs

    def save(self, **kwargs):
        request = self.context.get("request")
        task = self.context.get("task")

        if not task:
            raise validation_error("Task is required.")

        target_level = self.validated_data.get("target_level")
        comment = self.validated_data.get("comment")
        return_to_sender = self.validated_data.get("return_to_sender", False)

        target_task = task.send_back(
            request.user,
            target_level,
            comment,
            return_to_sender=return_to_sender,
            external_identity=getattr(request, "external_identity", None),
        )
        self.return_route = (
            target_task.incoming_return_routes.filter(
                status="awaiting_correction",
            )
            .order_by("-created_at")
            .first()
            if return_to_sender
            else None
        )
        self.target_task = target_task

        return target_task


class ScopedApprovalLevelInputSerializer(serializers.Serializer):
    base_uuid = serializers.UUIDField(required=False)
    category = UUIDRelatedField(
        queryset=ApprovalDocumentCategory.objects.all(),
    )
    name = serializers.CharField(required=False, allow_blank=True, allow_null=True)
    description = serializers.CharField(required=False, allow_blank=True, default="")
    approvers = UUIDRelatedField(
        queryset=ApproverGroup.objects.all(),
        many=True,
        required=False,
        allow_empty=True,
    )
    approver_users = UUIDRelatedField(
        queryset=ProfileInstitution.objects.all(),
        many=True,
        required=False,
        allow_empty=True,
    )
    overriders = UUIDRelatedField(
        queryset=ApproverGroup.objects.all(),
        many=True,
        required=False,
        allow_empty=True,
    )
    overrider_users = UUIDRelatedField(
        queryset=ProfileInstitution.objects.all(),
        many=True,
        required=False,
        allow_empty=True,
    )


class ScopedApprovalLevelEditorMixin:
    def _save_approval_levels(self, approval_levels, approval_document, base_context):
        for index, level_data in enumerate(approval_levels, start=1):
            level_serializer = ApprovalDocumentLevelSerializer(
                context={
                    **base_context,
                    "approval_document": approval_document,
                    "require_approval_document": True,
                }
            )
            level_serializer.create(
                {
                    **level_data,
                    "level": index,
                    "approval_document": approval_document,
                }
            )

    def _update_approval_levels(
        self,
        approval_levels,
        approval_document,
        base_context,
        affect_inflight_approvals=False,
    ):
        all_levels = list(
            approval_document.levels.select_for_update().order_by("level")
        )
        existing_levels = [
            level
            for level in all_levels
            if level.is_active and level.deleted_at is None
        ]
        existing_levels_by_uuid = {
            str(level.base_uuid): level for level in existing_levels
        }
        retained_level_ids = set()
        affected_approval_ids = set()

        highest_existing_level = max(
            (level.level or 0 for level in all_levels),
            default=0,
        )

        temporary_start = max(highest_existing_level, len(approval_levels)) + 1

        for offset, level in enumerate(all_levels):
            if level.is_locked:
                continue
            level.level = temporary_start + offset
            level.save(update_fields=["level"])

        for index, level_data in enumerate(approval_levels, start=1):
            level_data = dict(level_data)
            level_uuid = level_data.pop("base_uuid", None)
            approvers = level_data.get("approvers", [])
            approver_users = level_data.get("approver_users", [])
            overriders = level_data.get("overriders", [])
            overrider_users = level_data.get("overrider_users", [])

            level = None
            if level_uuid:
                level = existing_levels_by_uuid.get(str(level_uuid))
                if not level:
                    raise validation_error(
                        {
                            "approval_levels": (
                                f"Approval level {level_uuid} does not belong "
                                "to this approval document."
                            )
                        }
                    )

            if level:
                if level.is_locked:
                    raise validation_error(
                        {
                            "approval_levels": (
                                f"Approval level {level.level} is system-locked "
                                "and cannot be updated."
                            )
                        }
                    )

                retained_level_ids.add(level.id)
                level.category = level_data["category"]
                level.name = level_data.get("name")
                level.description = level_data.get("description", "")
                level.level = index
                level.save(
                    update_fields=[
                        "category",
                        "name",
                        "description",
                        "level",
                    ]
                )

                if affect_inflight_approvals:
                    ApprovalTask.objects.filter(
                        approval__document=approval_document,
                        approval__status="ongoing",
                        level=level,
                        status__in=["pending", "not_started"],
                        deleted_at__isnull=True,
                    ).update(sequence=index)

                existing_approver_links = ApprovalDocumentLevelApprovers.objects.filter(
                    approval_document_level=level,
                    deleted_at__isnull=True,
                )
                for link in existing_approver_links:
                    link.delete()

                existing_overrider_links = (
                    ApprovalDocumentLevelOverriders.objects.filter(
                        approval_document_level=level,
                        deleted_at__isnull=True,
                    )
                )
                for link in existing_overrider_links:
                    link.delete()

                for approver in approvers:
                    ApprovalDocumentLevelApprovers.objects.create(
                        approval_document_level=level,
                        approver_group=approver,
                    )

                for approver_user in approver_users:
                    ApprovalDocumentLevelApprovers.objects.create(
                        approval_document_level=level,
                        approver_user=approver_user,
                    )

                for overrider in overriders:
                    ApprovalDocumentLevelOverriders.objects.create(
                        approval_document_level=level,
                        approver_group=overrider,
                    )

                for overrider_user in overrider_users:
                    ApprovalDocumentLevelOverriders.objects.create(
                        approval_document_level=level,
                        overrider_user=overrider_user,
                    )
                continue

            level_serializer = ApprovalDocumentLevelSerializer(
                context={
                    **base_context,
                    "approval_document": approval_document,
                    "require_approval_document": True,
                }
            )
            level = level_serializer.create(
                {
                    **level_data,
                    "level": index,
                    "approval_document": approval_document,
                }
            )
            retained_level_ids.add(level.id)

            if affect_inflight_approvals:
                ongoing_approvals = list(
                    Approval.objects.select_for_update().filter(
                        document=approval_document,
                        status="ongoing",
                        deleted_at__isnull=True,
                    )
                )
                affected_approval_ids.update(
                    approval.id for approval in ongoing_approvals
                )
                ApprovalTask.objects.bulk_create(
                    [
                        ApprovalTask(
                            approval=approval,
                            level=level,
                            sequence=index,
                            status="not_started",
                        )
                        for approval in ongoing_approvals
                    ]
                )

        removed_levels = [
            level for level in existing_levels if level.id not in retained_level_ids
        ]

        for level in removed_levels:
            if level.is_locked:
                raise validation_error(
                    {
                        "approval_levels": (
                            f"Approval level {level.level} is system-locked "
                            "and cannot be removed."
                        )
                    }
                )

            if affect_inflight_approvals:
                unfinished_tasks = ApprovalTask.objects.select_for_update().filter(
                    approval__document=approval_document,
                    approval__status="ongoing",
                    level=level,
                    status__in=["pending", "not_started"],
                    deleted_at__isnull=True,
                )
                affected_approval_ids.update(
                    unfinished_tasks.values_list("approval_id", flat=True)
                )
                for task in unfinished_tasks:
                    task.delete()

            level.delete()

        if affect_inflight_approvals:
            stale_tasks = (
                ApprovalTask.objects.select_for_update()
                .filter(
                    approval__document=approval_document,
                    approval__status="ongoing",
                    status__in=["pending", "not_started"],
                    deleted_at__isnull=True,
                )
                .filter(Q(level__is_active=False) | Q(level__deleted_at__isnull=False))
            )

            affected_approval_ids.update(
                stale_tasks.values_list("approval_id", flat=True)
            )

            for task in stale_tasks:
                task.delete()

        affected_approvals = Approval.objects.select_for_update().filter(
            id__in=affected_approval_ids,
            status="ongoing",
        )
        for approval in affected_approvals:
            active_unfinished_tasks = list(
                approval.tasks.filter(
                    status__in=["pending", "not_started"],
                    deleted_at__isnull=True,
                    level__is_active=True,
                    level__deleted_at__isnull=True,
                ).select_related("level")
            )

            if not active_unfinished_tasks:
                approval.status = "completed"
                approval.save(update_fields=["status"])
                if approval.content_object:
                    approval.content_object.finish_workflow(approval)
                continue

            next_task = min(
                active_unfinished_tasks,
                key=lambda task: (
                    task.sequence is not None,
                    task.effective_sequence,
                ),
            )

            tasks_to_update = []
            for task in active_unfinished_tasks:
                expected_status = (
                    "pending" if task.id == next_task.id else "not_started"
                )
                if task.status != expected_status:
                    task.status = expected_status
                    tasks_to_update.append(task)

            if tasks_to_update:
                ApprovalTask.objects.bulk_update(
                    tasks_to_update,
                    ["status", "updated_at"],
                )
