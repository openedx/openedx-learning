"""
API Serializers for taxonomies
"""

from rest_framework import serializers
from rest_framework.reverse import reverse

from openedx_tagging.core.tagging.models import ObjectTag, Tag, Taxonomy


class TaxonomyListQueryParamsSerializer(serializers.Serializer):
    """
    Serializer for the query params for the GET view
    """

    enabled = serializers.BooleanField(required=False)


class TaxonomySerializer(serializers.ModelSerializer):
    class Meta:
        model = Taxonomy
        fields = [
            "id",
            "name",
            "description",
            "enabled",
            "required",
            "allow_multiple",
            "allow_free_text",
            "system_defined",
            "visible_to_authors",
        ]


class ObjectTagListQueryParamsSerializer(serializers.Serializer):
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
            "tag_ref",
            "is_valid",
        ]


class ObjectTagUpdateBodySerializer(serializers.Serializer):
    """
    Serializer of the body for the ObjectTag UPDATE view
    """

    tags = serializers.ListField(child=serializers.CharField(), required=True)


class ObjectTagUpdateQueryParamsSerializer(serializers.Serializer):
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
            "sub_tags_link",
            "children_count",
        )

    def get_sub_tags_link(self, obj):
        if obj.children.count():
            query_params = f"?parent_tag_id={obj.id}"
            url = (
                reverse("oel_tagging:taxonomy-tags", args=[str(obj.taxonomy_id)])
                + query_params
            )
            request = self.context.get("request")
            return request.build_absolute_uri(url)

    def get_children_count(self, obj):
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
        serializer = TagsWithSubTagsSerializer(
            obj.children.all().order_by("value", "id"),
            many=True,
            read_only=True,
        )
        return serializer.data

    def get_children_count(self, obj):
        return obj.children.count()


class TagsForSearchSerializer(TagsWithSubTagsSerializer):
    """
    Serializer for Tags

    Used to filter sub tags of a given tag
    """

    def get_sub_tags(self, obj):
        serializer = TagsWithSubTagsSerializer(obj.sub_tags, many=True, read_only=True)
        return serializer.data

    def get_children_count(self, obj):
        return len(obj.sub_tags)
