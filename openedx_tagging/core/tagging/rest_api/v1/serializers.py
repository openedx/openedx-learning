"""
API Serializers for taxonomies
"""

from rest_framework import serializers

from openedx_tagging.core.tagging.models import Taxonomy


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
