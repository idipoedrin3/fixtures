from rest_framework import serializers


class WriteableNestedSerializer(serializers.PrimaryKeyRelatedField):
    def __init__(self, serializer=None, **kwargs):
        self.serializer = serializer
        assert self.serializer is not None, "serializer argument is required"
        super().__init__(**kwargs)

    def to_representation(self, value):
        serializer_instance = self.serializer(value, context=self.context)
        return serializer_instance.data

    def to_internal_value(self, data):
        if isinstance(data, dict):
            serializer = self.serializer(data=data, context=self.context)
            serializer.is_valid(raise_exception=True)
            if "id" in data and data["id"]:
                return self.get_queryset().get(pk=data["id"])
            else:
                return serializer.save()
        return super().to_internal_value(data)
