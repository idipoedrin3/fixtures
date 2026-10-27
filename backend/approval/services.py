from django.db import transaction
from approval.models import Action, Approval
from django.contrib.contenttypes.models import ContentType

from audit.models import AuditLog
from system.models import ExternalApprovalTitleTemplate
from users.models import ExternalIdentity
from system.tasks import notify_external_system_task
from utilities.helpers import validation_error


class ApprovalService:
    @staticmethod
    @transaction.atomic
    def complete_without_tasks(
        instance,
        action_name,
        *,
        reason,
        source_approval=None,
    ):
        action = Action.objects.get(name=action_name)
        content_type = ContentType.objects.get_for_model(instance.__class__)

        instance.ensure_no_ongoing_approval(
            attempted_action=action_name,
        )

        if source_approval:
            if source_approval.status != "completed":
                raise validation_error("The source approval must be completed.")

            source_instance = source_approval.content_object

            if source_instance.get_institution() != instance.get_institution():
                raise validation_error(
                    "The source approval must belong to the same institution."
                )

        approval = Approval.objects.create(
            status="completed",
            document=None,
            action=action,
            content_type=content_type,
            object_id=instance.id,
            completion_mode="inherited",
            description=reason,
        )

        AuditLog.objects.create(
            content_type=content_type,
            object_id=instance.pk,
            action="AUTO_APPROVE",
            description=reason,
            changes={
                "source_approval_id": (source_approval.pk if source_approval else None),
                "approval_action": action_name,
            },
        )

        instance.finish_workflow(
            approval=approval,
        )

        return approval


class ExternalApprovalService:
    @staticmethod
    def get_default_external_approval_title(instance):
        resource_name = instance._meta.verbose_name.title()
        resource_reference = (
            getattr(instance, "reference_code", None)
            or getattr(instance, "name", None)
            or getattr(instance, "title", None)
            or str(instance)
        )

        return f"{resource_name} {resource_reference} requires your approval."

    @staticmethod
    def render_external_approval_title(instance, approval):
        content_type = ContentType.objects.get_for_model(instance)

        default_title = ExternalApprovalService.get_default_external_approval_title(
            instance
        )

        try:
            template = ExternalApprovalTitleTemplate.objects.get(
                content_type=content_type,
                is_active=True,
                is_deleted=False,
            )
        except ExternalApprovalTitleTemplate.DoesNotExist:
            return default_title

        context = {
            field.name: getattr(instance, field.name) for field in instance._meta.fields
        }

        context["approval"] = approval
        context["resource_uuid"] = getattr(instance, "base_uuid", None)

        try:
            return template.title_template.format(**context)
        except (KeyError, IndexError, AttributeError, ValueError):
            return default_title

    @staticmethod
    def build_external_approval_payload(
        instance,
        approval,
        approvers,
    ):
        resource_uuid = getattr(instance, "base_uuid", None)

        resource_name = instance._meta.verbose_name.title()
        description = (
            getattr(instance, "description", "")
            or f"{resource_name} approval from accounting"
        )

        return {
            "approval_uuid": str(approval.base_uuid),
            "external_base_uuid": str(approval.base_uuid),
            "action_name": "Approve",
            "resource_type": instance._meta.model_name,
            "resource_id": str(instance.pk),
            "resource_uuid": (str(resource_uuid) if resource_uuid else None),
            "title": ExternalApprovalService.render_external_approval_title(
                instance,
                approval,
            ),
            "description": description,
            "approvers": approvers,
        }

    @staticmethod
    def build_approval_levels(
        approval_document,
        institution,
        external_identity,
    ):
        levels_payload = []

        levels = approval_document.levels.filter(
            is_active=True,
            deleted_at__isnull=True,
        ).order_by("level")

        for level in levels:
            approver_users = level.get_approver_users()

            profile_ids = []

            for user in approver_users:
                user_external_identity = ExternalIdentity.objects.filter(
                    user=user,
                    partner_system=external_identity.partner_system,
                    institution=institution,
                ).first()

                if not user_external_identity:
                    continue

                profile_id = user_external_identity.external_base_uuid
                if isinstance(profile_id, str) and profile_id.isdigit():
                    profile_id = int(profile_id)

                profile_ids.append(profile_id)

            levels_payload.append(
                {
                    "level": level.level,
                    "external_base_uuid": str(level.base_uuid),
                    "name": level.name or f"Level {level.level}",
                    "profile_ids": profile_ids,
                }
            )

        return levels_payload

    @classmethod
    def submit_accounting_resource_for_external_approval(
        cls,
        *,
        instance,
        approval,
        profile_institution,
        approval_document,
        external_identity=None,
    ):
        if external_identity is None:
            external_identity = (
                ExternalIdentity.objects.select_related("partner_system")
                .filter(
                    user=profile_institution.profile.user,
                    institution=profile_institution.institution,
                    is_active=True,
                )
                .first()
            )

        if external_identity is None:
            return None

        approvers = cls.build_approval_levels(
            approval_document=approval_document,
            institution=profile_institution.institution,
            external_identity=external_identity,
        )

        payload = cls.build_external_approval_payload(
            instance=instance,
            approval=approval,
            approvers=approvers,
        )

        transaction.on_commit(
            lambda payload=payload, external_identity_id=external_identity.id: (
                notify_external_system_task.delay(
                    profile_institution_id=profile_institution.id,
                    resource_type="external_approval",
                    action="create",
                    payload=payload,
                    external_identity_id=external_identity_id,
                )
            )
        )

        return payload
