"""
API Serializers for taxonomies
"""
from __future__ import annotations

from rest_framework import serializers
from rest_framework.reverse import reverse

from openedx_tagging.core.tagging.data import TagData
from openedx_tagging.core.tagging.import_export.parsers import ParserFormat
from openedx_tagging.core.tagging.models import ObjectTag, Tag, Taxonomy


class TaxonomyListQueryParamsSerializer(serializers.Serializer):  # pylint: disable=abstract-method
    """
    Serializer for the query params for the GET view
    """

    enabled = serializers.BooleanField(required=False)


class TaxonomyExportQueryParamsSerializer(serializers.Serializer):  # pylint: disable=abstract-method
    """
    Serializer for the query params for the GET view
    """
    download = serializers.BooleanField(required=False, default=False)
    output_format = serializers.RegexField(r"(?i)^(json|csv)$", allow_blank=False)


class TaxonomySerializer(serializers.ModelSerializer):
    """
    Serializer for the Taxonomy model.
    """
    class Meta:
        model = Taxonomy
        fields = [
            "id",
            "name",
            "description",
            "enabled",
            "allow_multiple",
            "allow_free_text",
            "system_defined",
            "visible_to_authors",
        ]

    def to_representation(self, instance):
        """
        Cast the taxonomy before serialize
        """
        instance = instance.cast()
        return super().to_representation(instance)


class ObjectTagListQueryParamsSerializer(serializers.Serializer):  # pylint: disable=abstract-method
    """
    Serializer for the query params for the ObjectTag GET view
    """

    taxonomy = serializers.PrimaryKeyRelatedField(
        queryset=Taxonomy.objects.all(), required=False
    )


class ObjectTagSerializer(serializers.ModelSerializer):
    """
    Serializer for the ObjectTag model.
    """

    class Meta:
        model = ObjectTag
        fields = [
            "name",
            "value",
            "taxonomy_id",
            # If the Tag or Taxonomy has been deleted, this ObjectTag shouldn't be shown to users.
            "is_deleted",
        ]


class ObjectTagUpdateBodySerializer(serializers.Serializer):  # pylint: disable=abstract-method
    """
    Serializer of the body for the ObjectTag UPDATE view
    """

    tags = serializers.ListField(child=serializers.CharField(), required=True)


class ObjectTagUpdateQueryParamsSerializer(serializers.Serializer):  # pylint: disable=abstract-method
    """
    Serializer of the query params for the ObjectTag UPDATE view
    """

    taxonomy = serializers.PrimaryKeyRelatedField(
        queryset=Taxonomy.objects.all(), required=True
    )


class TagDataSerializer(serializers.Serializer):
    """
    Serializer for TagData dicts. Also can serialize Tag instances.

    Adds a link to get the sub tags
    """
    value = serializers.CharField()
    external_id = serializers.CharField(allow_null=True)
    child_count = serializers.IntegerField()
    depth = serializers.IntegerField()
    parent_value = serializers.CharField(allow_null=True)
    usage_count = serializers.IntegerField(required=False)
    # Internal database ID, if any. Generally should not be used; prefer 'value' which is unique within each taxonomy.
    # Free text taxonomies never have '_id' for their tags.
    _id = serializers.IntegerField(allow_null=True)

    sub_tags_url = serializers.SerializerMethodField()

    def get_sub_tags_url(self, obj: TagData | Tag):
        """
        Returns URL for the list of child tags of the current tag.
        """
        child_count = obj.child_count if isinstance(obj, Tag) else obj["child_count"]
        if child_count > 0 and "taxonomy_id" in self.context:
            value = obj.value if isinstance(obj, Tag) else obj["value"]
            query_params = f"?parent_tag={value}"
            request = self.context["request"]
            url_namespace = request.resolver_match.namespace  # get the namespace, usually "oel_tagging"
            url = (
                reverse(f"{url_namespace}:taxonomy-tags", args=[str(self.context["taxonomy_id"])])
                + query_params
            )
            return request.build_absolute_uri(url)
        return None

    def to_representation(self, instance: TagData | Tag) -> dict:
        """
        Convert this TagData (or Tag model instance) to the serialized dictionary
        """
        data = super().to_representation(instance)
        if isinstance(instance, Tag):
            data["_id"] = instance.pk  # The ID field won't otherwise be detected.
            data["parent_value"] = instance.parent.value if instance.parent else None
        return data

    def update(self, instance, validated_data):
        raise RuntimeError('`update()` is not supported by the TagData serializer.')

    def create(self, validated_data):
        raise RuntimeError('`create()` is not supported by the TagData serializer.')


class TaxonomyTagCreateBodySerializer(serializers.Serializer):  # pylint: disable=abstract-method
    """
    Serializer of the body for the Taxonomy Tags CREATE request
    """

    tag = serializers.CharField(required=True)
    parent_tag_value = serializers.CharField(required=False)
    external_id = serializers.CharField(required=False)


class TaxonomyTagUpdateBodySerializer(serializers.Serializer):  # pylint: disable=abstract-method
    """
    Serializer of the body for the Taxonomy Tags UPDATE request
    """

    tag = serializers.CharField(required=True)
    updated_tag_value = serializers.CharField(required=True)


class TaxonomyTagDeleteBodySerializer(serializers.Serializer):  # pylint: disable=abstract-method
    """
    Serializer of the body for the Taxonomy Tags DELETE request
    """

    tags = serializers.ListField(
        child=serializers.CharField(), required=True
    )
    with_subtags = serializers.BooleanField(required=False)


class TaxonomyImportBodySerializer(serializers.Serializer):  # pylint: disable=abstract-method
    """
    Serializer of the body for the Taxonomy Import action
    """
    taxonomy_name = serializers.CharField(required=True)
    taxonomy_description = serializers.CharField(default="")
    file = serializers.FileField(required=True)

    def get_parser_format(self, obj):
        """
        Returns the ParserFormat based on the file extension
        """
        filename = obj["file"].name
        ext = filename.split('.')[-1]
        if ext.lower() == 'csv':
            return ParserFormat.CSV
        elif ext.lower() == 'json':
            return ParserFormat.JSON
        else:
            raise serializers.ValidationError(f'File type not supported: ${ext.lower()}')

    def to_internal_value(self, data):
        """
        Adds the parser_format to the validated data
        """
        validated_data = super().to_internal_value(data)
        validated_data['parser_format'] = self.get_parser_format(data)
        return validated_data
