from django.db import models
from django.utils import timezone
from uuid import uuid4
from .search_util import BaseManager


def check_base_uuid_uniqueness(model, base_uuid, instance_id=None):
    qs = model.objects.filter(base_uuid=base_uuid)
    if instance_id:
        qs = qs.exclude(id=instance_id)
    return not qs.exists()


class BaseTimeStamp(models.Model):
    is_deleted = models.BooleanField(default=False)
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(default=timezone.now)

    description = models.TextField(blank=True, null=True)

    updated_at = models.DateTimeField(auto_now=True)
    created_by = models.ForeignKey(
        "users.CustomUser",
        related_name="%(app_label)s_%(class)s_creates",
        on_delete=models.CASCADE,
        null=True,
        blank=True,
    )
    updated_by = models.ForeignKey(
        "users.CustomUser",
        related_name="%(app_label)s_%(class)s_updates",
        on_delete=models.CASCADE,
        null=True,
        blank=True,
    )
    base_uuid = models.UUIDField(
        default=uuid4,
        editable=True,
        db_index=True,
        unique=True,
    )
    external_base_uuid = models.CharField(
        max_length=255,
        editable=True,
        null=True,
        blank=True,
        db_index=True,
    )

    reference_code = models.CharField(
        max_length=100, editable=True, null=True, blank=True
    )

    reference_prefix = None

    objects = BaseManager()

    base_search_fields = [
        "reference_code",
    ]

    ordering_fields = [
        "created_at",
        "updated_at",
        "reference_code",
    ]
    filterset_fields = []

    class Meta:
        abstract = True
        ordering = ["-created_at"]

    def get_reference_sequence(self):
        default_prefix = self.reference_prefix or "UNK"
        get_institution = getattr(self, "get_institution", None)

        if not callable(get_institution):
            return None, default_prefix

        institution = get_institution()

        if institution is None:
            return None, default_prefix

        from django.contrib.contenttypes.models import ContentType
        from institution.models import InstitutionReferenceSequence

        content_type = ContentType.objects.get_for_model(
            self,
            for_concrete_model=False,
        )

        sequence = (
            InstitutionReferenceSequence.objects.undeleted()
            .filter(
                institution=institution,
                content_type=content_type,
                is_active=True,
                is_deleted=False,
            )
            .first()
        )

        if sequence and sequence.prefix:
            return sequence, sequence.prefix

        return None, default_prefix

    def generate_reference_code(self):
        from utilities.helpers import generate_unique_code

        sequence, prefix = self.get_reference_sequence()

        if sequence is None or sequence.sequence_type == "alpha":
            return generate_unique_code(prefix)

        try:
            has_last_value = sequence.last_value not in (None, "")
            raw_seed_value = (
                str(sequence.last_value)
                if has_last_value
                else str(sequence.starting_value or 0)
            )
            seed_value = (
                int(raw_seed_value) if has_last_value else int(raw_seed_value) - 1
            )
            next_number = seed_value + 1
        except ValueError:
            raw_seed_value = ""
            next_number = 1

        last_value_width = (
            len(raw_seed_value)
            if sequence.last_value not in (None, "") and raw_seed_value.isdigit()
            else 0
        )
        padding_digits = max(int(sequence.padding_digits or 0), last_value_width)
        formatted_number = (
            str(next_number).zfill(padding_digits)
            if padding_digits > 0
            else str(next_number)
        )

        while self.__class__.objects.filter(
            reference_code=f"{prefix}-{formatted_number}"
        ).exists():
            next_number += 1
            formatted_number = (
                str(next_number).zfill(padding_digits)
                if padding_digits > 0
                else str(next_number)
            )

        self._pending_reference_sequence = sequence
        self._pending_reference_value = formatted_number

        return f"{prefix}-{formatted_number}"

    def save(self, *args, **kwargs):
        is_new = self._state.adding
        self._pending_reference_sequence = None
        self._pending_reference_value = None

        if is_new and not self.reference_code:
            self.reference_code = self.generate_reference_code()

        if is_new:
            while not self.base_uuid or not check_base_uuid_uniqueness(
                self.__class__, self.base_uuid
            ):
                self.base_uuid = uuid4()

        get_institution = getattr(self, "get_institution", None)

        if callable(get_institution) and self.reference_code:
            institution = get_institution()
            qs = self.__class__.objects.filter(reference_code=self.reference_code)

            if self.pk:
                qs = qs.exclude(pk=self.pk)

            reference_exists = any(
                callable(getattr(instance, "get_institution", None))
                and instance.get_institution() == institution
                for instance in qs
            )

            if reference_exists:
                raise ValueError(
                    f"Reference code '{self.reference_code}' already exists for this institution."
                )

        super().save(*args, **kwargs)

        if self._pending_reference_sequence is not None:
            sequence = self._pending_reference_sequence
            sequence.last_value = self._pending_reference_value
            sequence.save(update_fields=["last_value"])

    @classmethod
    def get_ordering_fields(cls):
        return list(getattr(cls, "ordering_fields", []))
