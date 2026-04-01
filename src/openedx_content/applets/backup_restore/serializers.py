"""
The serializers module for restoration of authoring data.

Please note that the serializers are defined from the perspective of the
TOML format, with the models as the "source". That is, when the model fields
and TOML fields differ, we'll declare it like this:

    my_toml_field = serializers.BlahField(source="my_model_field")
"""
from datetime import timezone

from rest_framework import serializers

from ..components import api as components_api
from ..components.models import ComponentType


class LearningPackageSerializer(serializers.Serializer):  # pylint: disable=abstract-method
    """
    Serializer for learning packages.

    Note:
        The ref/key field is serialized but is generally not trustworthy for
        restoration. During restore, a new ref may be generated or overridden.
    """

    title = serializers.CharField(required=True)
    # The model field is now LearningPackage.package_ref, but the archive format
    # still uses "key".  A future v2 format may align the name.
    key = serializers.CharField(required=True, source="package_ref")
    description = serializers.CharField(required=True, allow_blank=True)
    created = serializers.DateTimeField(required=True, default_timezone=timezone.utc)


class LearningPackageMetadataSerializer(serializers.Serializer):  # pylint: disable=abstract-method
    """
    Serializer for learning package metadata.

    Note:
        This serializer handles data exported to an archive (e.g., during backup),
        but the metadata is not restored to the database and is meant solely for inspection.
    """
    format_version = serializers.IntegerField(required=True)
    created_by = serializers.CharField(required=False, allow_null=True)
    created_by_email = serializers.EmailField(required=False, allow_null=True)
    created_at = serializers.DateTimeField(required=True, default_timezone=timezone.utc)
    origin_server = serializers.CharField(required=False, allow_null=True)


class EntitySerializer(serializers.Serializer):  # pylint: disable=abstract-method
    """
    Serializer for publishable entities.
    """

    can_stand_alone = serializers.BooleanField(required=True)
    # The model field is now PublishableEntity.entity_ref, but the archive format
    # still uses "key".  A future v2 format may align the name.
    key = serializers.CharField(required=True, source="entity_ref")
    created = serializers.DateTimeField(required=True, default_timezone=timezone.utc)


class EntityVersionSerializer(serializers.Serializer):  # pylint: disable=abstract-method
    """
    Serializer for publishable entity versions.
    """
    title = serializers.CharField(required=True)
    created = serializers.DateTimeField(required=True, default_timezone=timezone.utc)
    version_num = serializers.IntegerField(required=True)

    # Note: Unlike the fields above, `entity_ref` does not appear on the model
    # nor in the TOML.  This is just added by the validation pipeline for convenience.
    entity_ref = serializers.CharField(required=True)


class ComponentSerializer(EntitySerializer):  # pylint: disable=abstract-method
    """
    Serializer for components.
    Contains logic to convert entity_key to component_type and component_code.
    """

    def validate(self, attrs):
        """
        Custom validation logic:
        parse the entity_key into (component_type, component_code).
        """
        entity_key = attrs["entity_ref"]
        try:
            component_type_obj, component_code = _get_or_create_component_type_by_entity_key(entity_key)
            attrs["component_type"] = component_type_obj
            attrs["component_code"] = component_code
        except ValueError as exc:
            raise serializers.ValidationError({"key": str(exc)})
        return attrs


def _get_or_create_component_type_by_entity_key(entity_key: str) -> tuple[ComponentType, str]:
    """
    Get or create a ComponentType based on a full [entity].key string.

    The entity key is expected to be in the format
    ``"{namespace}:{type_name}:{component_code}"``. This function will parse out
    the ``namespace`` and ``type_name`` parts and use those to get or create the
    ComponentType.

    Raises ValueError if the entity_key is not in the expected format.

    Historical note: In Ulmo, this function was part of the public API. This was
    inappropriate because the exact format of entity_keys is just a convention
    rather than something API callers should count on. That said, it is safe to
    assume that in all "v1" archives, the components' entity keys are safe to
    parse into (namespace, type, code). So, we have moved this parsing logic
    from the public API to just this internal halper function.  Future devs,
    please do not make new external guarantees about the format of entity keys
    (aka entity_refs).  A future "v2" backup-restore format will drop this
    assumption of parse-ability..
    """
    try:
        namespace, type_name, component_code = entity_key.split(':', 2)
    except ValueError as exc:
        raise ValueError(
            f"Invalid entity_key format: {entity_key!r}. "
            "Expected format: '{namespace}:{type_name}:{component_code}'"
        ) from exc
    return components_api.get_or_create_component_type(namespace, type_name), component_code


class ComponentVersionSerializer(EntityVersionSerializer):  # pylint: disable=abstract-method
    """
    Serializer for component versions.
    """


class ContainerSerializer(EntitySerializer):  # pylint: disable=abstract-method
    """
    Serializer for containers.
    """
    container = serializers.DictField(required=True)

    def validate_container(self, value):
        """
        Custom validation logic for the container field.
        Ensures that the container dict has exactly one key which is one of
        "section", "subsection", or "unit" values.
        """
        errors = []
        if not isinstance(value, dict) or len(value) != 1:
            errors.append("Container must be a dict with exactly one key.")
        if len(value) == 1:  # Only check the key if there is exactly one
            container_type = list(value.keys())[0]
            if container_type not in ("section", "subsection", "unit"):
                errors.append(f"Invalid container value: {container_type}")
        if errors:
            raise serializers.ValidationError(errors)
        return value

    def validate(self, attrs):
        """
        Custom validation logic:
        parse the container dict to extract the container type.
        """
        container = attrs["container"]
        container_type = list(container.keys())[0]  # It is safe to do this after validate_container
        attrs["container_type"] = container_type
        attrs.pop("container")  # Remove the container field after processing
        return attrs


class ContainerVersionSerializer(EntityVersionSerializer):  # pylint: disable=abstract-method
    """
    Serializer for container versions.
    """
    container = serializers.DictField(required=True)

    def validate_container(self, value):
        """
        Custom validation logic for the container field.
        Ensures that the container dict has exactly one key "children" which is a list of strings.
        """
        errors = []
        if not isinstance(value, dict) or len(value) != 1:
            errors.append("Container must be a dict with exactly one key.")
        if "children" not in value:
            errors.append("Container must have a 'children' key.")
        if "children" in value and not isinstance(value["children"], list):
            errors.append("'children' must be a list.")
        if errors:
            raise serializers.ValidationError(errors)
        return value

    def validate(self, attrs):
        """
        Custom validation logic:
        parse the container dict to extract the children list.
        """
        children = attrs["container"]["children"]  # It is safe to do this after validate_container
        attrs["children"] = children
        attrs.pop("container")  # Remove the container field after processing
        return attrs


class CollectionSerializer(serializers.Serializer):  # pylint: disable=abstract-method
    """
    Serializer for collections.
    """
    title = serializers.CharField(required=True)
    # The model field is now Collection.collection_code, but the archive format
    # still uses "key".  A future v2 format may align the name.
    key = serializers.CharField(required=True, source="collection_code")
    description = serializers.CharField(required=True, allow_blank=True)
    entities = serializers.ListField(
        child=serializers.CharField(),
        required=True,
        allow_empty=True,
    )
