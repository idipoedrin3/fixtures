# ─────────────────────────────────────────────────────────────────────────────
# file_utils.py
# Shared backend file utilities — used by all serializers across the project.
# ─────────────────────────────────────────────────────────────────────────────

import base64
import binascii
from typing import Optional

from django.core.files.base import ContentFile

# ─── Exceptions ───────────────────────────────────────────────────────────────


class FileDecodeError(Exception):
    """Raised when base64 file data cannot be decoded."""

    pass


class InvalidFilePayloadError(Exception):
    """Raised when the incoming file payload is missing required fields."""

    pass


# ─── Validation ───────────────────────────────────────────────────────────────

REQUIRED_FILE_FIELDS = {"file_name", "mime_type", "file_data"}


def validate_file_payload(data: dict) -> None:
    """
    Validates that a file payload dict has all required fields.
    Raises InvalidFilePayloadError if any are missing.

    Usage:
        validate_file_payload(request.data.get("profile_photo"))
    """
    if not isinstance(data, dict):
        raise InvalidFilePayloadError("File payload must be a JSON object.")

    missing = REQUIRED_FILE_FIELDS - data.keys()
    if missing:
        raise InvalidFilePayloadError(
            f"File payload is missing required fields: {', '.join(missing)}"
        )


# ─── Core Decoder ─────────────────────────────────────────────────────────────


def decode_file(data: dict, field_name: str = "file") -> ContentFile:
    """
    Decodes a base64 file payload dict into a Django ContentFile.

    Args:
        data: Dict with keys: file_name, mime_type, file_data (base64 string)
        field_name: Used in error messages to identify which field failed.

    Returns:
        A Django ContentFile ready to assign to any FileField or ImageField.

    Raises:
        InvalidFilePayloadError: If required fields are missing.
        FileDecodeError: If base64 decoding fails.

    Usage:
        content_file = decode_file(request.data["profile_photo"], "profile_photo")
        instance.profile_photo.save(content_file.name, content_file)
    """
    validate_file_payload(data)

    try:
        file_bytes = base64.b64decode(data["file_data"])
    except (binascii.Error, ValueError) as e:
        raise FileDecodeError(f"Invalid base64 data in field '{field_name}': {str(e)}")

    return ContentFile(file_bytes, name=data["file_name"])


def decode_file_or_none(
    data: Optional[dict], field_name: str = "file"
) -> Optional[ContentFile]:
    """
    Like decode_file, but returns None if data is None or empty.
    Use this for optional file fields.

    Usage:
        content_file = decode_file_or_none(request.data.get("profile_photo"))
    """
    if not data:
        return None
    return decode_file(data, field_name)


def decode_files(data_list: list, field_name: str = "files") -> list[ContentFile]:
    """
    Decodes a list of base64 file payload dicts into a list of ContentFiles.
    Use for many=True file serializers.

    Usage:
        files = decode_files(request.data.get("files", []))
    """
    if not isinstance(data_list, list):
        raise InvalidFilePayloadError(f"'{field_name}' must be a list of file objects.")
    return [decode_file(item, field_name) for item in data_list]


# ─── Serializer Mixin ─────────────────────────────────────────────────────────


class Base64FileFieldMixin:
    """
    Mixin for DRF serializers that have one or more base64-encoded file fields.

    Declare your file fields in `base64_file_fields` as a list of field names.
    The mixin will automatically decode them during validated_data processing.

    Usage:
        class CustomerSerializer(Base64FileFieldMixin, serializers.ModelSerializer):
            base64_file_fields = ["profile_photo"]

            class Meta:
                model = Customer
                fields = "__all__"

    The serializer will:
    - Accept { profile_photo: { file_name, mime_type, file_data } } in JSON input
    - Decode and convert to Django ContentFile before save
    - Handle optional (null) file fields gracefully
    """

    base64_file_fields: list[str] = []

    def to_internal_value(self, data):
        file_data_map = {}
        for field_name in self.base64_file_fields:
            if field_name in data:
                file_data_map[field_name] = (
                    data.pop(field_name)
                    if isinstance(data, dict)
                    else data.get(field_name)
                )

        result = super().to_internal_value(data)

        for field_name, file_payload in file_data_map.items():
            try:
                result[field_name] = decode_file_or_none(file_payload, field_name)
            except (InvalidFilePayloadError, FileDecodeError) as e:
                from rest_framework import serializers

                raise validation_error({field_name: str(e)})

        return result

    def create(self, validated_data):
        instance = self.Meta.model()
        file_fields = {}

        for field_name in self.base64_file_fields:
            if field_name in validated_data:
                file_fields[field_name] = validated_data.pop(field_name)

        for attr, value in validated_data.items():
            setattr(instance, attr, value)

        instance.save()

        for field_name, content_file in file_fields.items():
            if content_file:
                getattr(instance, field_name).save(
                    content_file.name, content_file, save=False
                )

        instance.save()
        return instance

    def update(self, instance, validated_data):
        file_fields = {}

        for field_name in self.base64_file_fields:
            if field_name in validated_data:
                file_fields[field_name] = validated_data.pop(field_name)

        for attr, value in validated_data.items():
            setattr(instance, attr, value)

        for field_name, content_file in file_fields.items():
            if content_file:
                getattr(instance, field_name).save(
                    content_file.name, content_file, save=False
                )
            elif content_file is None:
                getattr(instance, field_name).delete(save=False)

        instance.save()
        return instance
