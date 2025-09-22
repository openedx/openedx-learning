"""
The serializers module for restoration of authoring data.
"""
from rest_framework import serializers

from openedx_learning.apps.authoring.components import api as components_api


class ComponentSerializer(serializers.Serializer):  # pylint: disable=abstract-method
    """
    Serializer for components.
    Contains logic to convert entity_key to component_type and local_key.
    """
    can_stand_alone = serializers.BooleanField(required=True)
    key = serializers.CharField(required=True)
    created = serializers.DateTimeField(required=True)
    created_by = serializers.CharField(required=True, allow_null=True)

    def validate(self, attrs):
        """
        Custom validation logic:
        parse the entity_key into (component_type, local_key).
        """
        entity_key = attrs["key"]
        try:
            component_type_obj, local_key = components_api.get_or_create_component_type_by_entity_key(entity_key)
            attrs["component_type"] = component_type_obj
            attrs["local_key"] = local_key
        except ValueError as exc:
            raise serializers.ValidationError({"key": str(exc)})
        return attrs


class ComponentVersionSerializer(serializers.Serializer):  # pylint: disable=abstract-method
    """
    Serializer for component versions.
    """
    title = serializers.CharField(required=True)
    entity_key = serializers.CharField(required=True)
    created = serializers.DateTimeField(required=True)
    created_by = serializers.CharField(required=True, allow_null=True)
    content_to_replace = serializers.DictField(child=serializers.CharField(), required=True)
