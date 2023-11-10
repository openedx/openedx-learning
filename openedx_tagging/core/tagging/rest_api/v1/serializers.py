"""
API Serializers for taxonomies
"""
from __future__ import annotations

from typing import Any

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


class ObjectTagMinimalSerializer(serializers.ModelSerializer):
    """
    Minimal serializer for the ObjectTag model.
    """

    class Meta:
        model = ObjectTag
        fields = ["value", "lineage"]

    lineage = serializers.ListField(child=serializers.CharField(), source="get_lineage", read_only=True)


class ObjectTagSerializer(ObjectTagMinimalSerializer):
    """
    Serializer for the ObjectTag model.
    """
    class Meta:
        model = ObjectTag
        fields = ObjectTagMinimalSerializer.Meta.fields + [
            # The taxonomy name
            "name",
            "taxonomy_id",
            # If the Tag or Taxonomy has been deleted, this ObjectTag shouldn't be shown to users.
            "is_deleted",
        ]


class ObjectTagsByTaxonomySerializer(serializers.ModelSerializer):
    """
    Serialize a group of ObjectTags, grouped by taxonomy
    """
    def to_representation(self, instance: list[ObjectTag]) -> dict:
        """
        Convert this list of ObjectTags to the serialized dictionary, grouped by Taxonomy
        """
        by_object: dict[str, dict[str, Any]] = {}
        for obj_tag in instance:
            if obj_tag.object_id not in by_object:
                by_object[obj_tag.object_id] = {
                    "taxonomies": []
                }
            taxonomies = by_object[obj_tag.object_id]["taxonomies"]
            tax_entry = next((t for t in taxonomies if t["taxonomy_id"] == obj_tag.taxonomy_id), None)
            if tax_entry is None:
                tax_entry = {
                    "name": obj_tag.name,
                    "taxonomy_id": obj_tag.taxonomy_id,
                    "editable": (not obj_tag.taxonomy.cast().system_defined) if obj_tag.taxonomy else False,
                    "tags": []
                }
                taxonomies.append(tax_entry)
            tax_entry["tags"].append(ObjectTagMinimalSerializer(obj_tag).data)
        return by_object


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
    Serializer of the body for the Taxonomy Import request
    """
    file = serializers.FileField(required=True)

    def validate(self, attrs):
        """
        Validates the file extension and add parser_format to the data
        """
        filename = attrs["file"].name
        ext = filename.split('.')[-1]
        parser_format = getattr(ParserFormat, ext.upper(), None)
        if not parser_format:
            raise serializers.ValidationError({"file": f'File type not supported: {ext.lower()}'}, 'file')

        attrs['parser_format'] = parser_format
        return attrs


class TaxonomyImportNewBodySerializer(TaxonomyImportBodySerializer):  # pylint: disable=abstract-method
    """
    Serializer of the body for the Taxonomy Create and Import request
    """
    taxonomy_name = serializers.CharField(required=True)
    taxonomy_description = serializers.CharField(default="")
