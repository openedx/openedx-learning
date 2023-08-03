"""
Tagging API Views
"""
from django.http import Http404
from rest_framework.viewsets import ModelViewSet

from ...api import (
    create_taxonomy,
    get_taxonomy,
    get_taxonomies,
)
from .pagination import TaggingPagination
from .permissions import TaxonomyObjectPermissions
from .serializers import TaxonomyListQueryParamsSerializer, TaxonomySerializer


class TaxonomyView(ModelViewSet):
    """
    View to list, create, retrieve, update, or delete Taxonomies.

    **List Query Parameters**
        * enabled (optional) - Filter by enabled status. Valid values: true, false, 1, 0, "true", "false", "1"
        * page (optional) - Page number (default: 1)
        * page_size (optional) - Number of items per page (default: 100)

    **List Example Requests**
        GET api/tagging/v1/taxonomy                                                 - Get all taxonomies
        GET api/tagging/v1/taxonomy?enabled=true                                    - Get all enabled taxonomies
        GET api/tagging/v1/taxonomy?enabled=false                                   - Get all disabled taxonomies

    **List Query Returns**
        * 200 - Success
        * 400 - Invalid query parameter
        * 403 - Permission denied

    **Retrieve Parameters**
        * pk (required): - The pk of the taxonomy to retrieve

    **Retrieve Example Requests**
        GET api/tagging/v1/taxonomy/:pk                                             - Get a specific taxonomy

    **Retrieve Query Returns**
        * 200 - Success
        * 404 - Taxonomy not found or User does not have permission to access the taxonomy

    **Create Parameters**
        * name (required): User-facing label used when applying tags from this taxonomy to Open edX objects.
        * description (optional): Provides extra information for the user when applying tags from this taxonomy to an object.
        * enabled (optional): Only enabled taxonomies will be shown to authors (default: true).
        * required (optional): Indicates that one or more tags from this taxonomy must be added to an object (default: False).
        * allow_multiple (optional): Indicates that multiple tags from this taxonomy may be added to an object (default: False).
        * allow_free_text (optional): Indicates that tags in this taxonomy need not be predefined; authors may enter their own tag values (default: False).

    **Create Example Requests**
        POST api/tagging/v1/taxonomy                                                - Create a taxonomy
        {
            "name": "Taxonomy Name",                    - User-facing label used when applying tags from this taxonomy to Open edX objects."
            "description": "This is a description",
            "enabled": True,
            "required": True,
            "allow_multiple": True,
            "allow_free_text": True,
        }

    **Create Query Returns**
        * 201 - Success
        * 403 - Permission denied

    **Update Parameters**
        * pk (required): - The pk of the taxonomy to update

    **Update Request Body**
        * name (optional): User-facing label used when applying tags from this taxonomy to Open edX objects.
        * description (optional): Provides extra information for the user when applying tags from this taxonomy to an object.
        * enabled (optional): Only enabled taxonomies will be shown to authors.
        * required (optional): Indicates that one or more tags from this taxonomy must be added to an object.
        * allow_multiple (optional): Indicates that multiple tags from this taxonomy may be added to an object.
        * allow_free_text (optional): Indicates that tags in this taxonomy need not be predefined; authors may enter their own tag values.

    **Update Example Requests**
        PUT api/tagging/v1/taxonomy/:pk                                            - Update a taxonomy
        {
            "name": "Taxonomy New Name",
            "description": "This is a new description",
            "enabled": False,
            "required": False,
            "allow_multiple": False,
            "allow_free_text": True,
        }
        PATCH api/tagging/v1/taxonomy/:pk                                          - Partially update a taxonomy
        {
            "name": "Taxonomy New Name",
        }

    **Update Query Returns**
        * 200 - Success
        * 403 - Permission denied

    **Delete Parameters**
        * pk (required): - The pk of the taxonomy to delete

    **Delete Example Requests**
        DELETE api/tagging/v1/taxonomy/:pk                                         - Delete a taxonomy

    **Delete Query Returns**
        * 200 - Success
        * 404 - Taxonomy not found
        * 403 - Permission denied

    """

    pagination_class = TaggingPagination
    serializer_class = TaxonomySerializer
    permission_classes = [TaxonomyObjectPermissions]

    def get_object(self):
        """
        Return the requested taxonomy object, if the user has appropriate
        permissions.
        """
        pk = self.kwargs.get("pk")
        taxonomy = get_taxonomy(pk)
        if not taxonomy:
            raise Http404("Taxonomy not found")
        self.check_object_permissions(self.request, taxonomy)

        return taxonomy

    def get_queryset(self):
        """
        Return a list of taxonomies.

        Returns all taxonomies by default.
        If you want the disabled taxonomies, pass enabled=False.
        If you want the enabled taxonomies, pass enabled=True.
        """
        query_params = TaxonomyListQueryParamsSerializer(
            data=self.request.query_params.dict()
        )
        query_params.is_valid(raise_exception=True)
        enabled = query_params.data.get("enabled", None)

        return get_taxonomies(enabled)

    def perform_create(self, serializer):
        """
        Create a new taxonomy.
        """
        serializer.instance = create_taxonomy(**serializer.validated_data)
