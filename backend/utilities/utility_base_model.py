from django.db import models
from django.utils import timezone
from utilities.common_models import BaseTimeStamp
from django.contrib.contenttypes.models import ContentType
from django.core import serializers


def _get_current_user():
    try:
        from crum import get_current_user

        return get_current_user()
    except ImportError:
        return None


class TimeStampedModel(models.Model):
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    is_active = models.BooleanField(default=True)

    class Meta:
        abstract = True


class SoftDeletableTimeStampedModel(BaseTimeStamp):
    deleted_at = models.DateTimeField(null=True, blank=True, db_index=True)

    class Meta(BaseTimeStamp.Meta):
        abstract = True

    def delete(self, *args, using_soft_delete=True, **kwargs):
        if not using_soft_delete:
            super().delete(*args, **kwargs)
            return

        print("\n\nUsing soft delete for instance: ", self, "\n\n")

        self.deleted_at = timezone.now()
        self.is_active = False
        self.save(update_fields=["deleted_at", "is_active"])
        self._save_to_recycle_bin()

    def _save_to_recycle_bin(self):
        print("\n\nSaving to recycle bin for instance: ", self, "\n\n")

        from institution.models import RecycleBin, RecycleBinItem

        if not hasattr(self, "get_institution"):
            print("\n\nNo get_institution method found for instance: ", self, "\n\n")
            return

        institution = self.get_institution()

        if institution is None:
            print("\n\nNo institution found for instance: ", self, "\n\n")
            return

        print("\n\nInstitution found for instance: ", institution, "\n\n")

        user = _get_current_user()
        print("\n\nCurrent user for instance: ", user, "\n\n")
        bin_obj, _ = RecycleBin.objects.get_or_create(institution=institution)

        content_type = ContentType.objects.get_for_model(self.__class__)

        RecycleBinItem.objects.update_or_create(
            recycle_bin=bin_obj,
            content_type=content_type,
            object_uuid=self.base_uuid,
            defaults={
                "deleted_by": user,
                "deleted_at": timezone.now(),
                "data": serializers.serialize("json", [self])[1:-1],
            },
        )

        print("\n\nRecycle bin item created for instance: ", self, "\n\n")
