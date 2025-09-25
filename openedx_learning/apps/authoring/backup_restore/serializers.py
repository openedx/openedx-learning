"""
The serializers module for restoration of authoring data.
"""
from rest_framework import serializers

from openedx_learning.apps.authoring.components import api as components_api


class EntitySerializer(serializers.Serializer):  # pylint: disable=abstract-method
    """
    Serializer for publishable entities.
    """
    can_stand_alone = serializers.BooleanField(required=True)
    key = serializers.CharField(required=True)
    created = serializers.DateTimeField(required=True)
    created_by = serializers.CharField(required=True, allow_null=True)


class EntityVersionSerializer(serializers.Serializer):  # pylint: disable=abstract-method
    """
    Serializer for publishable entity versions.
    """
    title = serializers.CharField(required=True)
    entity_key = serializers.CharField(required=True)
    created = serializers.DateTimeField(required=True)
    created_by = serializers.CharField(required=True, allow_null=True)


class ComponentSerializer(EntitySerializer):  # pylint: disable=abstract-method
    """
    Serializer for components.
    Contains logic to convert entity_key to component_type and local_key.
    """

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


class ComponentVersionSerializer(EntityVersionSerializer):  # pylint: disable=abstract-method
    """
    Serializer for component versions.
    """
    content_to_replace = serializers.DictField(child=serializers.CharField(), required=True)


class ContainerSerializer(EntitySerializer):  # pylint: disable=abstract-method
    """
    Serializer for containers.
    """
    container = serializers.DictField(child=serializers.DictField(), required=True)

    def validate(self, attrs):
        """
        Custom validation logic:
        parse the entity_key into (component_type, local_key).
        """
        try:
            container = attrs["container"]
            container_type = list(container.keys())[0]
            if container_type not in ("section", "subsection", "unit"):
                raise ValueError(f"Invalid container type: {container_type}")
            attrs["container_type"] = container_type
            attrs.pop("container")  # Remove the container field after processing
        except ValueError as exc:
            raise serializers.ValidationError({"key": str(exc)})
        return attrs


class ContainerVersionSerializer(EntityVersionSerializer):  # pylint: disable=abstract-method
    """
    Serializer for container versions.
    """
    container = serializers.DictField(child=serializers.ListField(child=serializers.CharField()), required=True)

    def validate(self, attrs):
        """
        Custom validation logic:
        parse the entity_key into (component_type, local_key).
        """
        try:
            container = attrs["container"]
            if "children" not in container:
                raise ValueError("Missing 'children' in container")
            children = container["children"]
            if not isinstance(children, list):
                raise ValueError("'children' must be a list")
            attrs["children"] = children
            attrs.pop("container")  # Remove the container field after processing
        except ValueError as exc:
            raise serializers.ValidationError({"key": str(exc)})
        return attrs
