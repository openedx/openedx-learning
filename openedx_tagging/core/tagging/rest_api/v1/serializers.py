"""
API Serializers for taxonomies
"""
from rest_framework import serializers
from rest_framework.reverse import reverse

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


class TagsSerializer(serializers.ModelSerializer):
    """
    Serializer for Tags

    Adds a link to get the sub tags
    """

    sub_tags_link = serializers.SerializerMethodField()
    children_count = serializers.SerializerMethodField()

    class Meta:
        model = Tag
        fields = (
            "id",
            "value",
            "taxonomy_id",
            "parent_id",
            "external_id",
            "sub_tags_link",
            "children_count",
        )

    def get_sub_tags_link(self, obj):
        """
        Returns URL for the list of child tags of the current tag.
        """
        if obj.children.count():
            query_params = f"?parent_tag_id={obj.id}"
            request = self.context.get("request")
            url_namespace = request.resolver_match.namespace  # get the namespace, usually "oel_tagging"
            url = (
                reverse(f"{url_namespace}:taxonomy-tags", args=[str(obj.taxonomy_id)])
                + query_params
            )
            return request.build_absolute_uri(url)
        return None

    def get_children_count(self, obj):
        """
        Returns the number of child tags of the given tag.
        """
        return obj.children.count()


class TagsWithSubTagsSerializer(serializers.ModelSerializer):
    """
    Serializer for Tags.

    Represents a tree with a list of sub tags
    """

    sub_tags = serializers.SerializerMethodField()
    children_count = serializers.SerializerMethodField()

    class Meta:
        model = Tag
        fields = (
            "id",
            "value",
            "taxonomy_id",
            "sub_tags",
            "children_count",
        )

    def get_sub_tags(self, obj):
        """
        Returns a serialized list of child tags for the given tag.
        """
        serializer = TagsWithSubTagsSerializer(
            obj.children.all().order_by("value", "id"),
            many=True,
            read_only=True,
        )
        return serializer.data

    def get_children_count(self, obj):
        """
        Returns the number of child tags of the given tag.
        """
        return obj.children.count()


class TagsForSearchSerializer(TagsWithSubTagsSerializer):
    """
    Serializer for Tags

    Used to filter sub tags of a given tag
    """

    def get_sub_tags(self, obj):
        """
        Returns a serialized list of child tags for the given tag.
        """
        serializer = TagsWithSubTagsSerializer(obj.sub_tags, many=True, read_only=True)
        return serializer.data

    def get_children_count(self, obj):
        """
        Returns the number of child tags of the given tag.
        """
        return len(obj.sub_tags)


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
