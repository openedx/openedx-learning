"""
The serializers module for restoration of authoring data.
"""
from openedx_learning.apps.authoring.components import api as components_api


class BaseSerializer:
    """
    The base class for all serializers.
    Contains basic validation logic.
    """
    required_fields: list[str] = []

    def __init__(self, data: dict):
        self.initial_data = data
        self._validated_data: dict | None = None
        self.errors: list[str] = []

    def is_valid(self) -> bool:
        self._validated_data = self.validate(self.initial_data)
        return not self.errors

    def validate(self, data: dict) -> dict:
        """Override in subclass"""
        validated = {}
        for field in self.required_fields:
            if field not in data:
                self.errors.append(f"Missing required field: {field}")
            else:
                validated[field] = data[field]
        return validated

    @property
    def validated_data(self) -> dict:
        if self._validated_data is None:
            raise ValueError("Call is_valid() before accessing validated_data")
        return self._validated_data


class ComponentSerializer(BaseSerializer):
    """
    Serializer for components.
    Contains logic to convert entity_key to component_type and local_key.
    """
    required_fields = ["can_stand_alone", "key", "created", "created_by"]

    def validate(self, data: dict) -> dict:
        """Override in subclass"""
        validated = {}
        for field in self.required_fields:
            if field not in data:
                self.errors.append(f"Missing required field: {field}")
            else:
                validated[field] = data[field]
        entity_key = validated["key"]
        try:
            component_type_obj, local_key = components_api.get_or_create_component_type_by_entity_key(entity_key)
            validated["component_type"] = component_type_obj
            validated["local_key"] = local_key
        except ValueError as exc:
            self.errors.append(str(exc))
        return validated


class ComponentVersionSerializer(BaseSerializer):
    """
    Serializer for component versions.
    """
    required_fields = ["title", "entity_key", "created", "created_by", "content_to_replace"]
