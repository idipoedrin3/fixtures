from django.db import models
import json
from utilities.helpers import has_access, validation_error
from utilities.utility_base_model import SoftDeletableTimeStampedModel
from django.contrib.contenttypes.models import ContentType
from django.contrib.contenttypes.fields import GenericForeignKey
import uuid
from django.db import connection, transaction
from rest_framework.exceptions import ValidationError
from django.core.serializers.json import DjangoJSONEncoder
from django.db.models.signals import pre_save
from django.dispatch import receiver
from django.db.models import Q
from django.apps import apps
from django.forms.models import model_to_dict
from django.db.models.fields.files import FieldFile
from django.utils import timezone

# Add this with your other imports
try:
    from communication.utils import add_notification
except ImportError:
    # Graceful fallback if there's a real circular import (very rare)
    def add_notification(*args, **kwargs):
        pass  # or log it

    add_notification = staticmethod(add_notification)


class Action(SoftDeletableTimeStampedModel):
    name = models.CharField(max_length=255)
    code = models.CharField(max_length=50, unique=True, editable=False)

    ordering_fields = [
        "name",
        "code",
    ]

    search_fields = [
        "name",
        "code",
    ]

    def save(self, *args, **kwargs):
        if not self.code:
            self.code = f"ACTION-{uuid.uuid4().hex[:8].upper()}"
            super().save(*args, **kwargs)

    def __str__(self):
        return self.name

    class Meta:
        ordering = ["name"]


class ApproverGroup(SoftDeletableTimeStampedModel):
    institution = models.ForeignKey("institution.Institution", on_delete=models.CASCADE)
    name = models.CharField(max_length=255)
    roles = models.ManyToManyField(
        "users.Role", through="ApproverGroupRole", blank=True
    )
    users = models.ManyToManyField(
        "users.Profile", through="ApproverGroupUser", blank=True
    )
    is_dynamic = models.BooleanField(default=False)
    permission = models.CharField(max_length=255, null=True, blank=True)

    def __str__(self):
        return f"{self.name} - {self.institution.institution_name}"

    class Meta:
        unique_together = ["institution", "name"]

    def get_dynamic_members(self) -> set:
        if not self.is_dynamic or not self.permission:
            return set()

        from django.apps import apps

        CustomUser = apps.get_model("users", "CustomUser")
        users = set()

        permission_users = CustomUser.objects.filter(
            is_active=True,
            userpermission__permission__permission_code=self.permission,
            profile__institution=self.institution,
        ).distinct()

        users.update(permission_users)

        # 2. Add institution owner automatically (super admin privilege)
        # if self.institution and self.institution.institution_owner and self.institution.institution_owner.is_active:
        #     users.add(self.institution.institution_owner)

        return users


class ApproverGroupRole(SoftDeletableTimeStampedModel):
    approver_group = models.ForeignKey(ApproverGroup, on_delete=models.CASCADE)
    role = models.ForeignKey("users.Role", on_delete=models.CASCADE)

    def __str__(self):
        return f"{self.approver_group.name} - {self.role.name}"


class ApproverGroupUser(SoftDeletableTimeStampedModel):
    approver_group = models.ForeignKey(ApproverGroup, on_delete=models.CASCADE)
    user = models.ForeignKey("users.Profile", on_delete=models.CASCADE)

    def __str__(self):
        return f"{self.approver_group.name} - {self.user.user.fullname}"


class ApprovalDocument(SoftDeletableTimeStampedModel):
    search_fields = [
        "document_name",
        "content_type__model",
        "description",
    ]

    institution = models.ForeignKey("institution.Institution", on_delete=models.CASCADE)

    document_name = models.CharField(max_length=255, blank=True, null=True)

    content_type = models.ForeignKey(
        ContentType,
        on_delete=models.CASCADE,
        related_name="approval_documents",
    )

    scope_content_type = models.ForeignKey(
        ContentType,
        on_delete=models.CASCADE,
        null=True,
        blank=True,
        related_name="scoped_approval_documents",
    )

    actions = models.ManyToManyField(
        "Action", related_name="approval_documents", blank=True
    )

    scope_object_id = models.UUIDField(
        null=True,
        blank=True,
    )

    scope_object = GenericForeignKey(
        "scope_content_type",
        "scope_object_id",
    )

    allow_decline_to_continue = models.BooleanField(default=False)

    def __str__(self):
        if self.document_name:
            return f"Approval Document: {self.document_name}"

        return f"Approval Document for {self.content_type}"

    def clean(self):
        super().clean()

        if not self.pk:
            return

        current_actions = set(self.actions.values_list("id", flat=True))

        qs = ApprovalDocument.objects.filter(
            institution=self.institution,
            content_type=self.content_type,
            is_active=True,
        ).exclude(pk=self.pk)

        current_scope_ct = self.scope_content_type_id
        current_scope_obj = self.scope_object_id

        for doc in qs:
            doc_actions = set(doc.actions.values_list("id", flat=True))

            doc_scope_ct = doc.scope_content_type_id
            doc_scope_obj = doc.scope_object_id

            both_unscoped = (
                current_scope_ct is None
                and current_scope_obj is None
                and doc_scope_ct is None
                and doc_scope_obj is None
            )

            same_scope = (
                current_scope_ct == doc_scope_ct
                and current_scope_obj == doc_scope_obj
                and current_scope_ct is not None
                and current_scope_obj is not None
            )

            if (both_unscoped or same_scope) and current_actions == doc_actions:
                raise ValidationError(
                    {
                        "error": "An approval document with the same content type, scope, and actions already exists."
                    }
                )

    def save(self, *args, **kwargs):
        self.full_clean()
        super().save(*args, **kwargs)


class ApprovalDocumentCategory(SoftDeletableTimeStampedModel):
    institution = models.ForeignKey(
        "institution.Institution",
        on_delete=models.CASCADE,
        related_name="approval_categories",
    )
    name = models.CharField(max_length=255)
    level = models.PositiveIntegerField(null=True, blank=True)

    # In other systems that won't be having reference code on there base, Will have to define the,
    # reference_code field and description field on the model and then add it to the migration file as well.

    def __str__(self):
        return f"{self.name} - {self.institution.institution_name} - {self.level if self.level is not None else 'No Level'}"

    def clean(self):
        super().clean()

        if self.level is not None:
            if (
                ApprovalDocumentCategory.objects.filter(
                    institution=self.institution, level=self.level
                )
                .exclude(pk=self.pk)
                .exists()
            ):
                raise ValidationError(
                    {
                        "level": "Level must be unique within the institution. Please provide a different level."
                    }
                )

        if self.level is None:
            raise validation_error(
                "Level is required if you are to create an approval document category. Please provide a level."
            )

    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=["institution", "name"],
                name="unique_approval_category_name_per_institution",
                condition=Q(deleted_at__isnull=True),
            )
        ]

        verbose_name = "Approval Document Category"
        verbose_name_plural = "Approval Document Categories"
        ordering = [
            "-created_at",
            "name",
        ]


class AllowedUser(SoftDeletableTimeStampedModel):
    content_type = models.ForeignKey(ContentType, on_delete=models.CASCADE)
    object_id = models.UUIDField(
        null=True,
        blank=True,
    )
    content_object = GenericForeignKey("content_type", "object_id")

    user = models.ForeignKey(
        "users.ProfileInstitution",
        on_delete=models.CASCADE,
        related_name="allowed_user_links",
    )

    search_fields = ["user__profile__user__fullname", "user__profile__user__email"]

    ordering_fields = [
        "user__profile__user__fullname",
        "user__profile__user__email",
        "created_at",
    ]

    def clean(self):
        super().clean()

        if not self.content_type_id or not self.user_id:
            return

        model_class = self.content_type.model_class()
        if model_class is None:
            raise ValidationError(
                {"content_type": "Content type does not resolve to a model."}
            )

        if not hasattr(model_class, "base_uuid"):
            raise ValidationError(
                {"content_type": "Allowed user objects must have a base_uuid field."}
            )

        allowed_object = None

        if self.object_id:
            object_qs = model_class.objects.filter(base_uuid=self.object_id)

            if hasattr(model_class, "deleted_at"):
                object_qs = object_qs.filter(deleted_at__isnull=True)

            allowed_object = object_qs.first()

            if not allowed_object:
                raise ValidationError(
                    {"object_id": "Object was not found for the selected content type."}
                )

        if allowed_object and not hasattr(allowed_object, "get_institution"):
            raise ValidationError(
                {
                    "content_type": "Allowed user objects must implement get_institution()."
                }
            )

        object_institution = None

        if allowed_object:
            object_institution = allowed_object.get_institution()

        user_institution = self.user.institution

        if (
            object_institution
            and user_institution
            and object_institution.id != user_institution.id
        ):
            raise ValidationError(
                {"user": "User must belong to the same institution as the object."}
            )

        duplicate_qs = AllowedUser.objects.filter(
            content_type=self.content_type,
            object_id=self.object_id,
            user=self.user,
        )
        if self.pk:
            duplicate_qs = duplicate_qs.exclude(pk=self.pk)

        if duplicate_qs.exists():
            raise ValidationError(
                {"user": "This user is already allowed for this object."}
            )

    def save(self, *args, **kwargs):
        self.full_clean()
        super().save(*args, **kwargs)

    class Meta:
        unique_together = ("content_type", "object_id", "user")
        verbose_name = "Allowed User"
        verbose_name_plural = "Allowed Users"

    def __str__(self):
        return f"Allowed User: {self.user} for {self.content_object}"


class ApprovalDocumentLevel(SoftDeletableTimeStampedModel):

    # ****************** this is the New FK  categorizing the levels into different categories***************
    category = models.ForeignKey(
        ApprovalDocumentCategory,
        on_delete=models.CASCADE,
        related_name="levels",
        null=True,
        blank=True,
    )
    # **********************END*****************************

    level = models.PositiveIntegerField(null=True, blank=True)
    approval_document = models.ForeignKey(
        ApprovalDocument,
        on_delete=models.CASCADE,
        related_name="levels",
    )
    description = models.TextField(blank=True)
    approvers = models.ManyToManyField(
        ApproverGroup,
        through="ApprovalDocumentLevelApprovers",
        related_name="approver_levels",
        blank=True,
    )
    approver_users = models.ManyToManyField(
        "users.ProfileInstitution",
        through="ApprovalDocumentLevelApprovers",
        related_name="approver_users_levels",
        blank=True,
    )
    overriders = models.ManyToManyField(
        ApproverGroup,
        through="ApprovalDocumentLevelOverriders",
        related_name="overrider_levels",
        blank=True,
    )
    overrider_users = models.ManyToManyField(
        "users.ProfileInstitution",
        through="ApprovalDocumentLevelOverriders",
        related_name="overrider_users_levels",
        blank=True,
    )
    name = models.CharField(max_length=255, blank=True, null=True)

    is_locked = models.BooleanField(
        default=False, help_text="Prevents editing, deletion, and reordering"
    )

    search_fields = [
        "name",
        "description",
        "approval_document__document_name",
        "category__name",
    ]

    ordering_fields = [
        "name",
    ]

    def __str__(self):
        return f"Level {self.level} - {self.approval_document}"

    class Meta:
        unique_together = ("approval_document", "level")
        ordering = ["level"]

    def clean(self):
        if (
            ApprovalDocumentLevel.objects.filter(
                approval_document=self.approval_document, level=self.level
            )
            .exclude(id=self.id)
            .exists()
        ):
            raise ValidationError(
                {"error": "Level must be unique within the approval document."}
            )

        if self.category_id and self.approval_document_id:
            doc_institution = self.approval_document.institution_id
            category_institution = self.category.institution_id

            if doc_institution != category_institution:
                raise ValidationError(
                    {
                        "category": (
                            "Category must belong to the same institution "
                            "as the approval document."
                        )
                    }
                )

    def save(self, *args, **kwargs):
        if self.pk and self.is_locked:
            raise ValidationError(
                {
                    "error": "This approval level is system-locked and cannot be modified or reordered."
                }
            )
        super().save(*args, **kwargs)

    def notify_external_approval_action(
        self,
        *,
        task_action,
        external_identity=None,
    ):
        from system.tasks import notify_external_system_task
        from users.models import ExternalIdentity, ProfileInstitution

        approval = task_action.approval

        if not approval:
            return None

        profile_institution = (
            ProfileInstitution.objects.filter(
                profile__user=task_action.acted_by,
                institution=approval.document.institution,
                is_active=True,
            )
            .select_related("profile", "institution")
            .first()
        )

        if profile_institution is None:
            return None

        if external_identity is None:
            external_identity = ExternalIdentity.objects.filter(
                user=task_action.acted_by,
                institution=approval.document.institution,
                is_active=True,
            ).first()

        if external_identity is None:
            return None

        payload = {
            "approval_uuid": str(approval.base_uuid),
            "level_external_base_uuid": str(self.base_uuid),
            "status": task_action.to_status,
            "comment": task_action.comment,
            "internal_base_uuid": None,
        }

        transaction.on_commit(
            lambda payload=payload, external_identity_id=external_identity.id: (
                notify_external_system_task.delay(
                    profile_institution_id=profile_institution.id,
                    resource_type="external_approval",
                    action="update",
                    payload=payload,
                    external_identity_id=external_identity_id,
                )
            )
        )

        return payload

    def delete(self, *args, **kwargs):
        if self.is_locked:
            raise ValidationError(
                {"error": "System-locked approval levels cannot be deleted."}
            )
        super().delete(*args, **kwargs)

    def get_approver_users(self) -> set:
        users = set()

        links = ApprovalDocumentLevelApprovers.objects.filter(
            approval_document_level=self,
            is_active=True,
            deleted_at__isnull=True,
        ).select_related("approver_user__profile__user", "approver_group")

        for link in links:

            if link.approver_user:
                user = link.approver_user.profile.user
                if user and user.is_active:
                    users.add(user)

            if link.approver_group:
                group = link.approver_group

                for profile in group.users.select_related("user").filter(
                    user__is_active=True
                ):
                    users.add(profile.user)

                for role in group.roles.prefetch_related("user_roles__user"):
                    for user_role in role.user_roles.filter(user__is_active=True):
                        users.add(user_role.user)

                if group.is_dynamic and group.permission:
                    users.update(group.get_dynamic_members())

        return users

    def get_overriders(self) -> set:
        users = set()

        links = ApprovalDocumentLevelOverriders.objects.filter(
            approval_document_level=self,
            is_active=True,
            deleted_at__isnull=True,
        ).select_related("overrider_user__profile__user", "approver_group")

        for link in links:

            if link.overrider_user:
                user = link.overrider_user.profile.user
                if user and user.is_active:
                    users.add(user)

            if link.approver_group:
                group = link.approver_group

                for profile in group.users.select_related("user").filter(
                    user__is_active=True
                ):
                    users.add(profile.user)

                for role in group.roles.prefetch_related("user_roles__user"):
                    for user_role in role.user_roles.filter(user__is_active=True):
                        users.add(user_role.user)

                if group.is_dynamic and group.permission:
                    users.update(group.get_dynamic_members())

        return users


@receiver(pre_save, sender=ApprovalDocumentLevel)
def set_approval_level(sender, instance, **kwargs):
    if not instance.pk and not instance.level:
        max_level = (
            ApprovalDocumentLevel.objects.filter(
                approval_document=instance.approval_document
            ).aggregate(models.Max("level"))["level__max"]
            or 0
        )
        instance.level = max_level + 1


class ApprovalDocumentLevelApprovers(SoftDeletableTimeStampedModel):
    approval_document_level = models.ForeignKey(
        ApprovalDocumentLevel, on_delete=models.CASCADE
    )
    approver_group = models.ForeignKey(
        ApproverGroup, on_delete=models.CASCADE, blank=True, null=True
    )
    approver_user = models.ForeignKey(
        "users.ProfileInstitution", on_delete=models.CASCADE, blank=True, null=True
    )

    class Meta:
        unique_together = ("approval_document_level", "approver_group", "approver_user")
        verbose_name = "Approval Document Level Approver"
        verbose_name_plural = "Approval Document Level Approvers"

    def clean(self):
        super().clean()
        if self.approver_group is None and self.approver_user is None:
            raise ValidationError(
                {
                    "error": "At least one of approver_group or approver_user must be set."
                }
            )


class ApprovalDocumentLevelOverriders(SoftDeletableTimeStampedModel):
    approval_document_level = models.ForeignKey(
        ApprovalDocumentLevel, on_delete=models.CASCADE
    )
    approver_group = models.ForeignKey(
        ApproverGroup, on_delete=models.CASCADE, null=True, blank=True
    )
    overrider_user = models.ForeignKey(
        "users.ProfileInstitution", on_delete=models.CASCADE, blank=True, null=True
    )

    class Meta:
        unique_together = (
            "approval_document_level",
            "approver_group",
            "overrider_user",
        )
        verbose_name = "Approval Document Level Overrider"
        verbose_name_plural = "Approval Document Level Overriders"

    def clean(self):
        super().clean()
        if self.approver_group is None and self.overrider_user is None:
            raise ValidationError(
                {
                    "error": "At least one of overrider_group or overrider_user must be set."
                }
            )


class Approval(SoftDeletableTimeStampedModel):
    STATUS_CHOICES = [
        ("ongoing", "Ongoing"),
        ("rejected", "Rejected"),
        ("completed", "Completed"),
    ]

    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default="ongoing")
    document = models.ForeignKey(
        ApprovalDocument,
        on_delete=models.CASCADE,
        null=True,
        blank=True,
    )
    action = models.ForeignKey(Action, on_delete=models.CASCADE)
    object_id = models.PositiveIntegerField()
    content_type = models.ForeignKey(ContentType, on_delete=models.CASCADE)
    content_object = GenericForeignKey("content_type", "object_id")

    completion_mode = models.CharField(
        choices=[
            ("workflow", "Workflow"),
            ("inherited", "Inherited"),
        ],
        default="workflow",
        max_length=20,
    )

    completion_risk_score = models.PositiveSmallIntegerField(
        null=True,
        blank=True,
        editable=False,
    )
    completion_risk_rating = models.CharField(
        max_length=20,
        null=True,
        blank=True,
        editable=False,
    )
    completion_risk_analysis = models.JSONField(
        null=True,
        blank=True,
        editable=False,
    )
    risk_assessed_at = models.DateTimeField(
        null=True,
        blank=True,
        editable=False,
    )

    search_fields = [
        "status",
        "document__document_name",
        "action__name",
        "content_type__model",
        "content_type__app_label",
    ]

    def save(self, *args, **kwargs):
        should_capture_risk = (
            self.status == "completed" and self.completion_risk_analysis is None
        )

        super().save(*args, **kwargs)

        if should_capture_risk:
            self.capture_completion_risk()

    def capture_completion_risk(self):
        if self.status != "completed" or self.completion_risk_analysis is not None:
            return self.completion_risk_analysis

        from approval.risk_analysis import ApprovalRiskAnalysisService

        analysis = ApprovalRiskAnalysisService(self).analyse()
        snapshot = json.loads(json.dumps(analysis, cls=DjangoJSONEncoder))
        assessed_at = timezone.now()

        Approval.objects.filter(
            pk=self.pk,
            completion_risk_analysis__isnull=True,
        ).update(
            completion_risk_score=analysis["score"],
            completion_risk_rating=analysis["rating"],
            completion_risk_analysis=snapshot,
            risk_assessed_at=assessed_at,
        )

        self.completion_risk_score = analysis["score"]
        self.completion_risk_rating = analysis["rating"]
        self.completion_risk_analysis = snapshot
        self.risk_assessed_at = assessed_at

        return snapshot

    def __str__(self):
        return f"Approval {self.object_id} - {self.status}"


class ApprovalTask(SoftDeletableTimeStampedModel):
    STATUS_CHOICES = [
        ("not_started", "Not Started"),
        ("pending", "Pending"),
        ("rejected", "Rejected"),
        ("approved", "Approved"),
        ("terminated", "Terminated"),
        ("overridden", "Overridden"),
    ]

    approval = models.ForeignKey(
        Approval, on_delete=models.CASCADE, related_name="tasks"
    )
    level = models.ForeignKey(ApprovalDocumentLevel, on_delete=models.CASCADE)

    sequence = models.PositiveIntegerField(null=True, blank=True, db_index=True)
    status = models.CharField(
        max_length=20, choices=STATUS_CHOICES, default="not_started"
    )
    comment = models.TextField(blank=True, null=True)
    approved_by = models.ForeignKey(
        "users.CustomUser", null=True, blank=True, on_delete=models.SET_NULL
    )
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return f"Task for Level {self.effective_sequence} - {self.status}"

    @property
    def effective_sequence(self):
        if self.sequence is not None:
            return self.sequence
        return self.level.level

    def get_next_not_started_task(self):
        candidates = self.approval.tasks.filter(
            status="not_started",
            deleted_at__isnull=True,
        ).select_related("level")
        candidates = [
            task
            for task in candidates
            if task.effective_sequence > self.effective_sequence
        ]
        return min(
            candidates,
            key=lambda task: task.effective_sequence,
            default=None,
        )

    class Meta:
        unique_together = ("approval", "level")
        ordering = [
            models.F("sequence").asc(nulls_first=True),
            "level__level",
        ]

    @property
    def object_id(self):
        """Returns the ID of the content_object, or None."""
        content_object = self.approval.content_object
        return str(self.approval.object_id) if content_object else None

    @property
    def object_base_uuid(self):
        """Returns the base_uuid of the content_object, or None."""
        content_object = self.approval.content_object
        return (
            str(content_object.base_uuid)
            if content_object and hasattr(content_object, "base_uuid")
            else None
        )

    def _latest_recallable_action(self):
        return (
            self.actions.filter(
                action__in=["approved", "rejected", "overridden"],
                deleted_at__isnull=True,
            )
            .select_related("acted_by")
            .order_by("-created_at", "-pk")
            .first()
        )

    def _tasks_after_this_level(self):
        tasks = list(
            self.approval.tasks.filter(
                deleted_at__isnull=True,
            ).select_related("level")
        )
        return [
            task for task in tasks if task.effective_sequence > self.effective_sequence
        ]

    def can_be_recalled_by(self, profile_institution):
        if not profile_institution:
            return False

        user = profile_institution.profile.user
        institution = self.approval.document.institution

        if not user.is_active or profile_institution.institution_id != institution.id:
            return False

        if self.status not in {"approved", "rejected", "overridden"}:
            return False

        if self.approval.status == "rejected":
            return False

        decision = self._latest_recallable_action()

        if not decision:
            return False

        is_decision_actor = decision.acted_by_id == user.id
        has_recall_access = has_access(
            user,
            institution,
            "can_recall_approval_decisions",
            profile_institution=profile_institution,
        )

        if not is_decision_actor and not has_recall_access:
            return False

        later_tasks = self._tasks_after_this_level()
        later_task_ids = [task.pk for task in later_tasks]

        if (
            later_task_ids
            and ApprovalTaskAction.objects.filter(
                task_id__in=later_task_ids,
                created_at__gt=decision.created_at,
                deleted_at__isnull=True,
            ).exists()
        ):
            return False

        if later_tasks:
            next_task = min(
                later_tasks,
                key=lambda task: task.effective_sequence,
            )
            return next_task.status in {"pending", "not_started"}

        if self.approval.status != "completed":
            return False

        content_object = self.approval.content_object

        can_recall = getattr(
            content_object,
            "can_recall_completed_approval",
            None,
        )

        return bool(can_recall and can_recall(self.approval))

    def recall(self, profile_institution, comment):
        with transaction.atomic():
            task = (
                ApprovalTask.objects.select_for_update()
                .select_related("approval", "level")
                .get(pk=self.pk)
            )

            if not (comment or "").strip():
                raise ValidationError(
                    {"comment": "A reason is required when recalling an approval."}
                )

            if not task.can_be_recalled_by(profile_institution):
                raise ValidationError(
                    {
                        "error": (
                            "This decision cannot be recalled because a later "
                            "level has acted, the workflow was rejected, or you "
                            "are not authorised to recall the decision."
                        )
                    }
                )

            later_tasks = task._tasks_after_this_level()

            if later_tasks:
                next_task = min(
                    later_tasks,
                    key=lambda candidate: candidate.effective_sequence,
                )
                next_task.status = "not_started"
                next_task.approved_by = None
                next_task.save(update_fields=["status", "approved_by", "updated_at"])
            else:
                content_object = task.approval.content_object
                recall_completed = getattr(
                    content_object,
                    "recall_completed_approval",
                    None,
                )
                if not recall_completed:
                    raise ValidationError(
                        {
                            "error": (
                                "Completed recall is not supported for this "
                                "type of approval."
                            )
                        }
                    )

                recall_completed(task.approval)

                task.approval.status = "ongoing"
                task.approval.completion_risk_score = None
                task.approval.completion_risk_rating = None
                task.approval.completion_risk_analysis = None
                task.approval.risk_assessed_at = None
                task.approval.save(
                    update_fields=[
                        "status",
                        "completion_risk_score",
                        "completion_risk_rating",
                        "completion_risk_analysis",
                        "risk_assessed_at",
                        "updated_at",
                    ]
                )

            from_status = task.status
            task.status = "pending"
            task.approved_by = None
            task.comment = None
            task.save(
                update_fields=[
                    "status",
                    "approved_by",
                    "comment",
                    "updated_at",
                ]
            )

            task._record_action(
                action="recalled",
                acted_by=profile_institution.profile.user,
                from_status=from_status,
                to_status="pending",
                from_level=task.effective_sequence,
                to_level=task.effective_sequence,
                comment=comment.strip(),
            )

            return task

    def _check_user_is_approver(self, user):
        """Check if user is authorized as an approver for this level (via groups, direct user, or institution owner)"""
        institution = self.approval.document.institution

        if user == institution.institution_owner:
            return True

        if user in self.level.get_approver_users():
            return True

        raise ValidationError(
            {"error": "User is not authorized to approve/reject tasks at this level"}
        )

    def _check_user_is_overrider(self, user):
        institution = self.approval.document.institution

        if user == institution.institution_owner:
            return True

        if user in self.level.get_overriders():
            return True

        raise ValidationError(
            {"error": "User is not authorized to override tasks at this level"}
        )

    def _check_user_has_signature(self, user):
        from users.models import ProfileInstitution

        profile_institution = (
            ProfileInstitution.objects.filter(
                profile__user=user,
                institution=self.approval.document.institution,
                is_active=True,
            )
            .only("signature_base64")
            .first()
        )

        signature = (
            profile_institution.signature_base64
            if profile_institution is not None
            else None
        )

        if not signature or not signature.strip():
            raise ValidationError(
                {"signature": "Please add your signature to continue."}
            )

        return True

    def mark_completed(
        self,
        user,
        comment: str = None,
        external_identity=None,
        as_override: bool = False,
    ):
        """Complete the current level and advance the approval workflow."""
        with transaction.atomic():
            if self.status != "pending":
                raise ValidationError(
                    {"error": "Task must be in pending state to be completed"}
                )

            if as_override:
                self._check_user_is_overrider(user)
            else:
                self._check_user_is_approver(user)
            self._check_user_has_signature(user)

            active_return_route = (
                ApprovalReturnRoute.objects.select_for_update()
                .select_related("source_task", "source_task__level")
                .filter(
                    approval=self.approval,
                    target_task=self,
                    status="awaiting_correction",
                )
                .order_by("-created_at")
                .first()
            )

            from_status = self.status
            self.status = "overridden" if as_override else "approved"
            self.approved_by = user
            if comment:
                self.comment = comment
            self.save(update_fields=["status", "updated_at", "comment", "approved_by"])

            current_level = self.effective_sequence

            next_task = (
                active_return_route.source_task
                if active_return_route
                else self.get_next_not_started_task()
            )

            self._record_action(
                action="overridden" if as_override else "approved",
                acted_by=user,
                from_status=from_status,
                to_status=self.status,
                from_level=current_level,
                to_level=next_task.effective_sequence if next_task else None,
                comment=comment,
                return_route=active_return_route,
                external_identity=external_identity,
            )

            # Get model_name and object_id for content_object
            content_object = self.approval.content_object
            model_name = (
                ContentType.objects.get_for_model(content_object).model
                if content_object
                else None
            )
            object_id = str(content_object.id) if content_object else None

            if next_task:
                next_task.status = "pending"
                next_task.save(update_fields=["status", "updated_at"])

                if active_return_route:
                    active_return_route.status = "returned"
                    active_return_route.returned_at = timezone.now()
                    active_return_route.save(
                        update_fields=[
                            "status",
                            "returned_at",
                            "updated_at",
                        ]
                    )

                # Notify next approvers
                object_desc = str(content_object) if content_object else "an object"
                if active_return_route:
                    message = (
                        f"Corrections for {object_desc} have been completed and "
                        f"returned to level {next_task.effective_sequence}."
                    )
                else:
                    message = (
                        f"A new approval task is pending for you: "
                        f"Approve {object_desc} at level {next_task.effective_sequence}."
                    )

                for approver_user in next_task.level.get_approver_users():
                    add_notification(
                        user_id=approver_user,
                        message=message,
                        model_name=model_name,
                        object_id=object_id,
                    )
            else:
                ApprovalReturnRoute.objects.filter(
                    approval=self.approval, status="awaiting_correction"
                ).update(
                    status="cancelled",
                    cancelled_at=timezone.now(),
                )
                self.approval.status = "completed"
                self.approval.save()
                if content_object:
                    content_object.finish_workflow(self.approval)
                # Notify approval completion
                if (
                    hasattr(self.approval.content_object, "created_by")
                    and self.approval.content_object.created_by
                ):
                    add_notification(
                        user_id=self.approval.content_object.created_by,
                        message=f"Your {self.approval.content_object._meta.verbose_name} has been approved.",
                        model_name=model_name,
                        object_id=object_id,
                    )

    def mark_rejected(
        self,
        user,
        comment: str = None,
        external_identity=None,
    ):
        with transaction.atomic():
            if self.status != "pending":
                raise ValidationError(
                    {"error": "Task must be in pending state to be rejected"}
                )

            self._check_user_is_approver(user)
            self._check_user_has_signature(user)

            from_status = self.status
            self.status = "rejected"
            self.approved_by = user
            if comment:
                self.comment = comment
            self.save(update_fields=["status", "updated_at", "comment", "approved_by"])

            ApprovalReturnRoute.objects.filter(
                approval=self.approval,
                target_task=self,
                status="awaiting_correction",
            ).update(
                status="cancelled",
                cancelled_at=timezone.now(),
            )

            self._record_action(
                action="rejected",
                acted_by=user,
                from_status=from_status,
                to_status=self.status,
                from_level=self.effective_sequence,
                comment=comment,
                external_identity=external_identity,
            )

            if (
                self.approval.document
                and self.approval.document.allow_decline_to_continue
            ):
                current_level = self.effective_sequence
                next_task = self.get_next_not_started_task()

                content_object = self.approval.content_object
                model_name = (
                    ContentType.objects.get_for_model(content_object).model
                    if content_object
                    else None
                )
                object_id = str(content_object.id) if content_object else None

                if next_task:
                    next_task.status = "pending"
                    next_task.save(update_fields=["status", "updated_at"])

                    object_desc = str(content_object) if content_object else "an object"
                    message = (
                        f"A new approval task is pending for you: "
                        f"Approve {object_desc} at level {next_task.effective_sequence}."
                    )
                    for approver_user in next_task.level.get_approver_users():
                        add_notification(
                            user_id=approver_user,
                            message=message,
                            model_name=model_name,
                            object_id=object_id,
                        )
                else:
                    self.approval.status = "rejected"
                    self.approval.save()
                    if content_object:
                        content_object.finish_workflow(self.approval)

                    if (
                        hasattr(self.approval.content_object, "created_by")
                        and self.approval.content_object.created_by
                    ):
                        add_notification(
                            user_id=self.approval.content_object.created_by,
                            message=(
                                f"Your {self.approval.content_object._meta.verbose_name} "
                                f"has been rejected."
                            ),
                            model_name=model_name,
                            object_id=object_id,
                        )
                return

            self.approval.status = "rejected"
            self.approval.save()

            ApprovalReturnRoute.objects.filter(
                approval=self.approval,
                status="awaiting_correction",
            ).update(
                status="cancelled",
                cancelled_at=timezone.now(),
            )

            terminated_tasks = self.approval.tasks.exclude(id=self.id).filter(
                status__in=["not_started", "pending"]
            )
            terminated_tasks.update(status="terminated")

            content_object = self.approval.content_object
            model_name = (
                ContentType.objects.get_for_model(content_object).model
                if content_object
                else None
            )
            object_id = str(content_object.id) if content_object else None

            if content_object:
                content_object.finish_workflow(self.approval)

            object_desc = str(content_object) if content_object else "an object"
            if (
                hasattr(self.approval.content_object, "created_by")
                and self.approval.content_object.created_by
            ):
                add_notification(
                    user_id=self.approval.content_object.created_by,
                    message=f"Your approval request for {object_desc} has been rejected at level {self.effective_sequence}.",
                    model_name=model_name,
                    object_id=object_id,
                )

    def _record_action(
        self,
        action,
        acted_by=None,
        from_status=None,
        to_status=None,
        from_level=None,
        to_level=None,
        comment=None,
        return_route=None,
        external_identity=None,
    ):
        task_action = ApprovalTaskAction.objects.create(
            approval=self.approval,
            task=self,
            action=action,
            acted_by=acted_by,
            from_status=from_status,
            to_status=to_status,
            from_level=from_level,
            to_level=to_level,
            comment=comment,
            return_route=return_route,
        )

        if action in {"approved", "rejected", "overridden", "sent_back"}:
            self.level.notify_external_approval_action(
                task_action=task_action,
                external_identity=external_identity,
            )

        return task_action

    def send_back(
        self,
        user,
        target_level: int = None,
        comment: str = None,
        return_to_sender: bool = False,
        external_identity=None,
    ):
        with transaction.atomic():
            if self.status != "pending":
                raise ValidationError(
                    {"error": "Task must be in pending state to be sent back"}
                )

            self._check_user_is_approver(user)
            self._check_user_has_signature(user)

            current_level = self.effective_sequence

            if current_level is None:
                raise ValidationError(
                    {"error": "Current task level must have a level number"}
                )

            if target_level is None:
                target_level = current_level - 1

            try:
                target_level = int(target_level)
            except (TypeError, ValueError):
                raise ValidationError(
                    {"target_level": "Target level must be a valid number"}
                )

            if target_level < 1 or target_level >= current_level:
                raise ValidationError(
                    {
                        "target_level": (
                            "Target level must be behind the current approval level"
                        )
                    }
                )

            approval_tasks = self.approval.tasks.select_for_update().select_related(
                "level"
            )
            target_task = next(
                (
                    task
                    for task in approval_tasks
                    if task.effective_sequence == target_level
                ),
                None,
            )

            if not target_task:
                raise ValidationError(
                    {"target_level": "No approval task exists for the target level"}
                )

            if return_to_sender and not (comment or "").strip():
                raise ValidationError(
                    {
                        "comment": (
                            "A comment is required when the corrected "
                            "approval must return to the sender."
                        )
                    }
                )

            return_route = None
            if return_to_sender:
                has_active_outgoing_route = (
                    ApprovalReturnRoute.objects.select_for_update()
                    .filter(
                        approval=self.approval,
                        source_task=self,
                        status="awaiting_correction",
                    )
                    .exists()
                )
                if has_active_outgoing_route:
                    raise ValidationError(
                        {
                            "return_to_sender": (
                                "This task already has an active correction route."
                            )
                        }
                    )

                parent_route = (
                    ApprovalReturnRoute.objects.select_for_update()
                    .filter(
                        approval=self.approval,
                        target_task=self,
                        status="awaiting_correction",
                    )
                    .order_by("-created_at")
                    .first()
                )

                return_route = ApprovalReturnRoute.objects.create(
                    approval=self.approval,
                    source_task=self,
                    target_task=target_task,
                    parent_route=parent_route,
                    description=comment.strip(),
                    sent_by=user,
                )

            self._record_action(
                action="sent_back",
                acted_by=user,
                from_status=self.status,
                to_status="not_started",
                from_level=current_level,
                to_level=target_level,
                comment=comment,
                return_route=return_route,
                external_identity=external_identity,
            )

            if return_to_sender:
                reset_tasks = approval_tasks.filter(pk__in=[target_task.pk, self.pk])
            else:
                reset_task_ids = [
                    task.pk
                    for task in approval_tasks
                    if target_level <= task.effective_sequence <= current_level
                ]
                reset_tasks = approval_tasks.filter(pk__in=reset_task_ids)

            for task in reset_tasks:
                from_status = task.status
                task.status = "not_started"
                task.approved_by = None
                task.save(update_fields=["status", "approved_by", "updated_at"])
                # The source task already has a "sent_back" audit entry.
                # Only record "reset" for the other workflow tasks reopened
                # as a consequence of the send-back.
                if task.pk != self.pk:
                    task._record_action(
                        action="reset",
                        acted_by=user,
                        from_status=from_status,
                        to_status=task.status,
                        from_level=task.effective_sequence,
                        to_level=target_level,
                        comment=comment,
                    )

            target_task.status = "pending"
            target_task.save(update_fields=["status", "updated_at"])

            if self.approval.status != "ongoing":
                self.approval.status = "ongoing"
                self.approval.save(update_fields=["status"])

            content_object = self.approval.content_object
            model_name = (
                ContentType.objects.get_for_model(content_object).model
                if content_object
                else None
            )
            object_id = str(content_object.id) if content_object else None
            object_desc = str(content_object) if content_object else "an object"

            for approver_user in target_task.level.get_approver_users():
                message = (
                    f"Approval for {object_desc} was sent back to level "
                    f"{target_level}."
                )
                if return_to_sender:
                    message += (
                        f" Comment: {comment.strip()} After completion, "
                        f"it will return directly to level {current_level}."
                    )

                add_notification(
                    user_id=approver_user,
                    message=message,
                    model_name=model_name,
                    object_id=object_id,
                )

            return target_task

    def mark_overridden(
        self,
        user,
        comment: str = None,
        external_identity=None,
    ):
        """Override only the current level and continue the workflow."""
        return self.mark_completed(
            user,
            comment,
            external_identity=external_identity,
            as_override=True,
        )

    def can_user_approve_or_reject(self, user):
        """Check if user can approve or reject this task"""
        try:
            self._check_user_is_approver(user)
            return True
        except ValidationError:
            return False

    def can_user_override(self, user):
        """Check if user can override this task"""
        try:
            self._check_user_is_overrider(user)
            return True
        except ValidationError:
            return False

    def get_user_permissions(self, user):
        """Get user's permissions for this task"""
        institution = self.approval.document.institution
        is_institution_owner = user == institution.institution_owner

        return {
            "can_approve_or_reject": self.can_user_approve_or_reject(user),
            "can_override": self.can_user_override(user),
            "can_act": self.status == "pending",
            "is_institution_owner": is_institution_owner,
        }


class ApprovalTaskAction(SoftDeletableTimeStampedModel):
    ACTION_CHOICES = [
        ("approved", "Approved"),
        ("rejected", "Rejected"),
        ("sent_back", "Sent Back"),
        ("reset", "Reset"),
        ("overridden", "Overridden"),
        ("recalled", "Recalled"),
    ]

    approval = models.ForeignKey(
        Approval,
        on_delete=models.CASCADE,
        related_name="task_actions",
    )
    task = models.ForeignKey(
        ApprovalTask,
        on_delete=models.CASCADE,
        related_name="actions",
    )
    action = models.CharField(max_length=30, choices=ACTION_CHOICES)
    acted_by = models.ForeignKey(
        "users.CustomUser",
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
    )
    from_status = models.CharField(max_length=20, blank=True, null=True)
    to_status = models.CharField(max_length=20, blank=True, null=True)
    from_level = models.PositiveIntegerField(null=True, blank=True)
    to_level = models.PositiveIntegerField(null=True, blank=True)
    comment = models.TextField(blank=True, null=True)

    return_route = models.ForeignKey(
        "ApprovalReturnRoute",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="actions",
    )

    class Meta:
        ordering = ["-created_at"]

    def __str__(self):
        return f"{self.action} - Level {self.from_level}"


class ApprovalReturnRoute(SoftDeletableTimeStampedModel):
    STATUS_CHOICES = [
        ("awaiting_correction", "Awaiting Correction"),
        ("returned", "Returned"),
        ("cancelled", "Cancelled"),
    ]

    approval = models.ForeignKey(
        Approval,
        on_delete=models.CASCADE,
        related_name="return_routes",
    )
    source_task = models.ForeignKey(
        ApprovalTask,
        on_delete=models.CASCADE,
        related_name="outgoing_return_routes",
    )
    target_task = models.ForeignKey(
        ApprovalTask,
        on_delete=models.CASCADE,
        related_name="incoming_return_routes",
    )

    parent_route = models.ForeignKey(
        "self",
        on_delete=models.SET_NULL,
        related_name="child_routes",
        null=True,
        blank=True,
    )

    status = models.CharField(
        max_length=30,
        choices=STATUS_CHOICES,
        default="awaiting_correction",
    )

    sent_by = models.ForeignKey(
        "users.CustomUser",
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="+",
    )

    returned_at = models.DateTimeField(null=True, blank=True)
    cancelled_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        ordering = ["-created_at"]
        constraints = [
            models.UniqueConstraint(
                fields=["approval", "source_task"],
                condition=Q(status="awaiting_correction"),
                name="unique_active_outgoing_approval_return",
            ),
            models.UniqueConstraint(
                fields=["approval", "target_task"],
                condition=Q(status="awaiting_correction"),
                name="unique_active_incoming_approval_return",
            ),
        ]

    def __str__(self):
        return (
            f"Approval {self.approval_id}: "
            f"level {self.source_task.effective_sequence} "
            f"to level {self.target_task.effective_sequence}"
        )


class BaseApprovableModel(SoftDeletableTimeStampedModel):
    usage_access_field = None

    STATUS_CHOICES = [
        ("under_creation", "Under Creation"),
        ("under_update", "Under Update"),
        ("under_deletion", "Under Deletion"),
        ("active", "Active"),
    ]
    original_data = models.JSONField(null=True, blank=True, encoder=DjangoJSONEncoder)
    approval_status = models.CharField(
        max_length=20, choices=STATUS_CHOICES, default="under_creation"
    )

    class Meta:
        abstract = True

    def get_institution(self):
        raise ValidationError({"error": "Institution not found for this object"})

    def can_use(self, user_institution_profile):
        if not self.usage_access_field:
            return False

        if user_institution_profile is None or user_institution_profile.pk is None:
            return False

        institution = self.get_institution()
        if (
            institution is None
            or institution.pk is None
            or user_institution_profile.institution_id != institution.pk
        ):
            return False

        if getattr(self, self.usage_access_field, False):
            return True

        return (
            AllowedUser.objects.undeleted()
            .filter(
                content_type=ContentType.objects.get_for_model(self),
                object_id=self.base_uuid,
                user=user_institution_profile,
            )
            .exists()
        )

    def get_scope(self):
        return None, None

    def requires_scope(self):
        return False

    @transaction.atomic
    def _get_applicable_approval_document(self, action, content_type, institution):
        scope_ct, scope_obj_id = self.get_scope()

        base_qs = (
            ApprovalDocument.objects.select_for_update()
            .filter(
                institution=institution,
                content_type=content_type,
                actions=action,
                is_active=True,
                deleted_at__isnull=True,
            )
            .order_by("-created_at")
        )

        if scope_ct and scope_obj_id:
            scoped = base_qs.filter(
                scope_content_type=scope_ct,
                scope_object_id=scope_obj_id,
            ).first()

            if scoped:
                return scoped

            if self.requires_scope():
                raise ValidationError(
                    {"error": "Scoped approval document required but not found."}
                )

        return base_qs.filter(
            scope_content_type__isnull=True,
            scope_object_id__isnull=True,
        ).first()

    def _get_ongoing_approval_queryset(self):
        content_type = ContentType.objects.get_for_model(self.__class__)

        return Approval.objects.filter(
            content_type=content_type, object_id=self.pk, status="ongoing"
        )

    def has_ongoing_approval(self):
        if not self.pk:
            return False

        return self._get_ongoing_approval_queryset().exists()

    def allows_changes(self):
        if not self.pk:
            return True

        ongoing_approval = (
            self._get_ongoing_approval_queryset()
            .select_related("action")
            .order_by("-id")
            .first()
        )

        if not ongoing_approval:
            return True

        first_task = (
            ongoing_approval.tasks.filter(deleted_at__isnull=True)
            .select_related("level")
            .order_by(
                models.F("sequence").asc(nulls_first=True),
                "level__level",
            )
            .first()
        )

        return (
            ongoing_approval.action_id is not None
            and ongoing_approval.action.name == "create"
            and first_task is not None
            and first_task.status == "pending"
        )

    def ensure_changes_allowed(self):
        self.ensure_no_ongoing_approval(attempted_action="update")

    def ensure_no_ongoing_approval(self, attempted_action: str = None):
        if not self.pk:
            return

        ongoing_approvals = (
            self._get_ongoing_approval_queryset()
            .select_related("action")
            .order_by("-id")
        )

        if connection.in_atomic_block:
            ongoing_approvals = ongoing_approvals.select_for_update()

        ongoing_approval = ongoing_approvals.first()

        if not ongoing_approval:
            return

        first_task = (
            ongoing_approval.tasks.select_related("level")
            .order_by(
                models.F("sequence").asc(nulls_first=True),
                "level__level",
            )
            .first()
        )

        current_action = (
            ongoing_approval.action.name
            if ongoing_approval.action_id and ongoing_approval.action
            else "another action"
        )

        attempted = attempted_action or "another action"

        can_update_create_at_first_level = (
            attempted.lower() == "update"
            and current_action.lower() == "create"
            and first_task is not None
            and first_task.status == "pending"
        )

        if can_update_create_at_first_level:
            return ongoing_approval

        raise validation_error(
            f"This object already has an ongoing approval for {current_action}. "
            f"You cannot perform {attempted} until the current approval is completed or rejected."
        )

    @transaction.atomic
    def _trigger_approval(
        self,
        action_name: str,
        profile_institution=None,
        external_identity=None,
    ):

        print("\n\n Processing at the start of trigger")

        action = Action.objects.get(name=action_name)
        content_type = ContentType.objects.get_for_model(self.__class__)
        institution = self.get_institution()

        if not institution:
            raise ValidationError({"error": "No institution for this object"})

        self.ensure_no_ongoing_approval(attempted_action=action_name)

        has_custom_logic = getattr(self, "has_custom_logic", False)

        if has_custom_logic:
            document = self._get_applicable_approval_document(
                action=action,
                content_type=content_type,
                institution=institution,
            )
            if not document:
                permission_code = getattr(
                    self.__class__, "FINAL_APPROVAL_PERMISSION", None
                )
                if not permission_code:
                    raise ValidationError("Model missing FINAL_APPROVAL_PERMISSION")

                model_name = content_type.model.replace("_", " ").title()
                dynamic_group, _ = ApproverGroup.objects.get_or_create(
                    institution=institution,
                    permission=permission_code,
                    is_dynamic=True,
                    defaults={
                        "name": f"[Auto] Final Approvers: {model_name}",
                        "description": f"Users with permission to approve {model_name}",
                    },
                )
                with transaction.atomic():
                    document = ApprovalDocument.objects.create(
                        institution=institution,
                        content_type=content_type,
                        description=f"Auto-generated workflow for {model_name} ({action_name})",
                    )
                    document.actions.add(action)
                    level = ApprovalDocumentLevel.objects.create(
                        approval_document=document,
                        name="Final Approval (System Locked)",
                        description=f"Final approval by users with '{permission_code}'",
                        is_locked=True,
                    )
                    ApprovalDocumentLevelApprovers.objects.create(
                        approval_document_level=level, approver_group=dynamic_group
                    )

        else:
            document = self._get_applicable_approval_document(
                action=action,
                content_type=content_type,
                institution=institution,
            )

            if document:
                pass
            else:
                if action_name in ["create", "update"]:
                    self.approval_status = "active"
                    self.is_active = True
                    self.deleted_at = None
                    self.save(
                        update_fields=["approval_status", "is_active", "deleted_at"]
                    )
                elif action_name == "delete":
                    self.approval_status = "under_deletion"
                    self.save(update_fields=["approval_status"])
                    self.delete(using_soft_delete=True)

                dummy_approval = Approval(
                    status="completed",
                    action=action,
                    document=None,
                    content_type=content_type,
                    object_id=self.pk,
                )
                self.finish_workflow(dummy_approval)
                return

        with transaction.atomic():
            if action_name != "delete":
                self.is_active = False
                self.save(update_fields=["is_active"])

            approval = Approval.objects.create(
                status="ongoing",
                document=document,
                action=action,
                content_type=content_type,
                object_id=self.pk,
            )

            levels = document.levels.filter(
                is_active=True,
                deleted_at__isnull=True,
            ).order_by("level")
            if not levels.exists():
                approval.status = "completed"
                approval.save()
                self.finish_workflow(approval)
                return

            for i, lvl in enumerate(levels):
                status = "pending" if i == 0 else "not_started"
                ApprovalTask.objects.create(
                    approval=approval,
                    level=lvl,
                    sequence=i + 1,
                    status=status,
                )

            first_task = approval.tasks.filter(status="pending").first()
            if first_task:
                approvers = first_task.level.get_approver_users()
                message = f"New {str(self)} requires approval for {action_name}."
                for user in approvers:
                    add_notification(
                        user_id=user,
                        message=message,
                        model_name=content_type.model,
                        object_id=str(self.pk),
                    )

            if profile_institution and external_identity:
                from .services import ExternalApprovalService

                ExternalApprovalService.submit_accounting_resource_for_external_approval(
                    instance=self,
                    approval=approval,
                    profile_institution=profile_institution,
                    approval_document=document,
                    external_identity=external_identity,
                )

    def confirm_create(
        self,
        *,
        inherit_from=None,
        completion_reason=None,
        profile_institution=None,
        external_identity=None,
    ):
        if self.approval_status != "under_creation":
            raise ValidationError(
                {"error": "Object must be under_creation to confirm create"}
            )

        if inherit_from:
            from .services import ApprovalService

            return ApprovalService.complete_without_tasks(
                self,
                "create",
                reason=completion_reason or "Creation confirmed.",
                source_approval=inherit_from,
            )

        self._trigger_approval(
            "create",
            profile_institution=profile_institution,
            external_identity=external_identity,
        )

    @transaction.atomic
    def confirm_update(
        self,
        *,
        profile_institution=None,
        external_identity=None,
    ):
        if self.approval_status != "under_update":
            raise ValidationError(
                {"error": "Object must be under_update to confirm update"}
            )

        ongoing_create_approval = self.ensure_no_ongoing_approval(
            attempted_action="update"
        )

        if ongoing_create_approval:
            self.approval_status = "under_creation"
            self.original_data = None
            self.save(
                update_fields=[
                    "approval_status",
                    "original_data",
                ]
            )
            return ongoing_create_approval

        self._trigger_approval(
            "update",
            profile_institution=profile_institution,
            external_identity=external_identity,
        )

    @transaction.atomic
    def confirm_delete(
        self,
        *,
        profile_institution=None,
        external_identity=None,
    ):
        allowed_states = ["active", "under_update", "under_deletion"]

        if self.approval_status not in allowed_states:
            raise ValidationError(
                {
                    "error": f"Can only delete from states: {', '.join(allowed_states)}. "
                    f"Current state: '{self.approval_status}'"
                }
            )

        if self.approval_status != "under_deletion":
            self.approval_status = "under_deletion"
            self.save(update_fields=["approval_status"])

        self.ensure_no_ongoing_approval(attempted_action="delete")
        self._trigger_approval(
            "delete",
            profile_institution=profile_institution,
            external_identity=external_identity,
        )

    def finish_workflow(self, approval: Approval):

        with transaction.atomic():
            if approval.status == "completed":
                if approval.action.name in ["create", "update"]:
                    self.approval_status = "active"
                    self.is_active = True
                    self.deleted_at = None
                    self.original_data = None

                elif approval.action.name == "delete":
                    self.delete(using_soft_delete=True)

            elif approval.status == "rejected":
                if approval.action.name == "create":
                    self.delete(using_soft_delete=True)

                elif approval.action.name in ["update", "delete"]:
                    self.approval_status = "active"
                    self.is_active = True
                    self.deleted_at = None
                    if approval.action.name == "update" and self.original_data:
                        self.restore_from_data(self.original_data)
                        self.original_data = None
                    self.save(
                        update_fields=[
                            "approval_status",
                            "is_active",
                            "deleted_at",
                            "original_data",
                        ]
                    )

    def save(self, *args, **kwargs):
        with transaction.atomic():
            if (
                self.pk
                and self.approval_status in ["under_update", "under_deletion"]
                and self.has_ongoing_approval()
            ):
                attempted_action = (
                    "delete" if self.approval_status == "under_deletion" else "update"
                )
                self.ensure_no_ongoing_approval(attempted_action=attempted_action)

            if (
                self.pk
                and self.approval_status == "under_update"
                and self.original_data is None
            ):
                original = type(self).objects.get(pk=self.pk)
                self.original_data = original.get_serializable_data()

            super().save(*args, **kwargs)

    def get_serializable_data(self):
        exclude = {
            "original_data",
            "approval_status",
            "is_active",
            "created_at",
            "updated_at",
            "deleted_at",
        }
        data = model_to_dict(self)
        for field in exclude:
            data.pop(field, None)

        for field in self._meta.many_to_many:
            if field.name in data:
                data[field.name] = [related.pk for related in data[field.name]]

        return {
            field: (value.name or "") if isinstance(value, FieldFile) else value
            for field, value in data.items()
        }

    def restore_from_data(self, data: dict):
        for field, value in data.items():
            model_field = self._meta.get_field(field)
            if model_field.many_to_many:
                getattr(self, field).set(value)
            elif isinstance(model_field, models.ForeignKey):
                setattr(self, model_field.attname, value)
            else:
                setattr(self, field, value)
