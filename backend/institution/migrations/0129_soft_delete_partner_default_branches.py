from django.db import migrations
from django.utils import timezone


def soft_delete_partner_default_branches(apps, schema_editor):
    Institution = apps.get_model("institution", "Institution")
    Branch = apps.get_model("institution", "Branch")

    partner_institution_ids = Institution.objects.filter(
        external_base_uuid__isnull=False,
    ).values_list("id", flat=True)

    institution_ids_with_external_branches = (
        Branch.objects.filter(
            institution_id__in=partner_institution_ids,
            external_base_uuid__isnull=False,
            deleted_at__isnull=True,
        )
        .values_list("institution_id", flat=True)
        .distinct()
    )

    Branch.objects.filter(
        institution_id__in=institution_ids_with_external_branches,
        external_base_uuid__isnull=True,
        deleted_at__isnull=True,
    ).update(deleted_at=timezone.now())


def reverse_noop(apps, schema_editor):
    pass


class Migration(migrations.Migration):

    dependencies = [
        (
            "institution",
            "0128_institution_cash_account_reconciliation_automatch_threshold_percent",
        ),
    ]

    operations = [
        migrations.RunPython(
            soft_delete_partner_default_branches,
            reverse_noop,
        ),
    ]
