"""
Tagging API Views
"""
from __future__ import annotations

from django.db import models
from django.http import Http404
from rest_framework import mixins
from rest_framework.exceptions import MethodNotAllowed, PermissionDenied, ValidationError
from rest_framework.response import Response
from rest_framework.generics import ListAPIView
from rest_framework.viewsets import GenericViewSet, ModelViewSet

from openedx_tagging.core.tagging.models.base import Tag

from ...api import (
    create_taxonomy,
    get_children_tags,
    get_object_tags,
    get_root_tags,
    get_taxonomies,
    get_taxonomy,
    search_tags,
    tag_object,
)
from ...models import Taxonomy
from ...rules import ChangeObjectTagPermissionItem
from ..paginators import SEARCH_TAGS_THRESHOLD, TAGS_THRESHOLD, DisabledTagsPagination, TagsPagination
from .permissions import ObjectTagObjectPermissions, TagListPermissions, TaxonomyObjectPermissions
from .serializers import (
    ObjectTagListQueryParamsSerializer,
    ObjectTagSerializer,
    ObjectTagUpdateBodySerializer,
    ObjectTagUpdateQueryParamsSerializer,
    TagsForSearchSerializer,
    TagsSerializer,
    TagsWithSubTagsSerializer,
    TaxonomyListQueryParamsSerializer,
    TaxonomySerializer,
)


class TaxonomyView(ModelViewSet):
    """
    View to list, create, retrieve, update, or delete Taxonomies.

    **List Query Parameters**
        * enabled (optional) - Filter by enabled status. Valid values: true,
          false, 1, 0, "true", "false", "1"
        * page (optional) - Page number (default: 1)
        * page_size (optional) - Number of items per page (default: 10)

    **List Example Requests**
        GET api/tagging/v1/taxonomy                - Get all taxonomies
        GET api/tagging/v1/taxonomy?enabled=true   - Get all enabled taxonomies
        GET api/tagging/v1/taxonomy?enabled=false  - Get all disabled taxonomies

    **List Query Returns**
        * 200 - Success
        * 400 - Invalid query parameter
        * 403 - Permission denied

    **Retrieve Parameters**
        * pk (required): - The pk of the taxonomy to retrieve

    **Retrieve Example Requests**
        GET api/tagging/v1/taxonomy/:pk            - Get a specific taxonomy

    **Retrieve Query Returns**
        * 200 - Success
        * 404 - Taxonomy not found or User does not have permission to access
          the taxonomy

    **Create Parameters**
        * name (required): User-facing label used when applying tags from this
          taxonomy to Open edX objects.
        * description (optional): Provides extra information for the user when
          applying tags from this taxonomy to an object.
        * enabled (optional): Only enabled taxonomies will be shown to authors
          (default: true).
        * required (optional): Indicates that one or more tags from this
          taxonomy must be added to an object (default: False).
        * allow_multiple (optional): Indicates that multiple tags from this
          taxonomy may be added to an object (default: False).
        * allow_free_text (optional): Indicates that tags in this taxonomy need
          not be predefined; authors may enter their own tag values (default:
          False).

    **Create Example Requests**
        POST api/tagging/v1/taxonomy               - Create a taxonomy
        {
            "name": "Taxonomy Name",
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
        * name (optional): User-facing label used when applying tags from this
          taxonomy to Open edX objects.
        * description (optional): Provides extra information for the user when
          applying tags from this taxonomy to an object.
        * enabled (optional): Only enabled taxonomies will be shown to authors.
        * required (optional): Indicates that one or more tags from this
          taxonomy must be added to an object.
        * allow_multiple (optional): Indicates that multiple tags from this
          taxonomy may be added to an object.
        * allow_free_text (optional): Indicates that tags in this taxonomy need
          not be predefined; authors may enter their own tag values.

    **Update Example Requests**
        PUT api/tagging/v1/taxonomy/:pk            - Update a taxonomy
        {
            "name": "Taxonomy New Name",
            "description": "This is a new description",
            "enabled": False,
            "required": False,
            "allow_multiple": False,
            "allow_free_text": True,
        }
        PATCH api/tagging/v1/taxonomy/:pk          - Partially update a taxonomy
        {
            "name": "Taxonomy New Name",
        }

    **Update Query Returns**
        * 200 - Success
        * 403 - Permission denied

    **Delete Parameters**
        * pk (required): - The pk of the taxonomy to delete

    **Delete Example Requests**
        DELETE api/tagging/v1/taxonomy/:pk         - Delete a taxonomy

    **Delete Query Returns**
        * 200 - Success
        * 404 - Taxonomy not found
        * 403 - Permission denied

    """

    serializer_class = TaxonomySerializer
    permission_classes = [TaxonomyObjectPermissions]

    def get_object(self) -> Taxonomy:
        """
        Return the requested taxonomy object, if the user has appropriate
        permissions.
        """
        pk = int(self.kwargs["pk"])
        taxonomy = get_taxonomy(pk)
        if not taxonomy:
            raise Http404("Taxonomy not found")
        self.check_object_permissions(self.request, taxonomy)

        return taxonomy

    def get_queryset(self) -> models.QuerySet:
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

    def perform_create(self, serializer) -> None:
        """
        Create a new taxonomy.
        """
        serializer.instance = create_taxonomy(**serializer.validated_data)


class ObjectTagView(
    mixins.RetrieveModelMixin,
    mixins.UpdateModelMixin,
    mixins.ListModelMixin,
    GenericViewSet,
):
    """
    View to retrieve ObjectTags for a provided Object ID (object_id).

    **Retrieve Parameters**
        * object_id (required): - The Object ID to retrieve ObjectTags for.

    **Retrieve Query Parameters**
        * taxonomy (optional) - PK of taxonomy to filter ObjectTags for.

    **Retrieve Example Requests**
        GET api/tagging/v1/object_tags/:object_id
        GET api/tagging/v1/object_tags/:object_id?taxonomy=1

    **Retrieve Query Returns**
        * 200 - Success
        * 400 - Invalid query parameter
        * 403 - Permission denied

    **Create Query Returns**
        * 403 - Permission denied
        * 405 - Method not allowed

    **Update Parameters**
        * object_id (required): - The Object ID to add ObjectTags for.

    **Update Request Body**
        * tags: List of tags to be applied to a object id. Must be a list of Tag ids or Tag values.

    **Update Query Returns**
        * 200 - Success
        * 403 - Permission denied
        * 405 - Method not allowed

    **Delete Query Returns**
        * 403 - Permission denied
        * 405 - Method not allowed
    """

    serializer_class = ObjectTagSerializer
    permission_classes = [ObjectTagObjectPermissions]
    lookup_field = "object_id"

    def get_queryset(self) -> models.QuerySet:
        """
        Return a queryset of object tags for a given object.

        If a taxonomy is passed in, object tags are limited to that taxonomy.
        """
        object_id: str = self.kwargs["object_id"]
        query_params = ObjectTagListQueryParamsSerializer(
            data=self.request.query_params.dict()
        )
        query_params.is_valid(raise_exception=True)
        taxonomy_id = query_params.data.get("taxonomy", None)
        return get_object_tags(object_id, taxonomy_id)

    def retrieve(self, request, object_id=None):
        """
        Retrieve ObjectTags that belong to a given object_id

        Note: We override `retrieve` here instead of `list` because we are
        passing in the Object ID (object_id) in the path (as opposed to passing
        it in as a query_param) to retrieve the related ObjectTags.
        By default retrieve would expect an ObjectTag ID to be passed in the
        path and returns a it as a single result however that is not
        behavior we want.
        """
        object_tags = self.get_queryset()
        serializer = ObjectTagSerializer(object_tags, many=True)
        return Response(serializer.data)

    def update(self, request, object_id, partial=False):
        """
        Update ObjectTags that belong to a given object_id

        Pass a list of Tag ids or Tag values to be applied to an object id in the
        body `tag` parameter. Passing an empty list will remove all tags from
        the object id.

        **Example Body Requests**

        PUT api/tagging/v1/object_tags/:object_id

        **Example Body Requests**
        ```json
        {
            "tags": [1, 2, 3]
        },
        {
            "tags": ["Tag 1", "Tag 2"]
        },
        {
            "tags": []
        }
        """

        if partial:
            raise MethodNotAllowed("PATCH", detail="PATCH not allowed")

        query_params = ObjectTagUpdateQueryParamsSerializer(
            data=request.query_params.dict()
        )
        query_params.is_valid(raise_exception=True)
        taxonomy = query_params.validated_data.get("taxonomy", None)
        taxonomy = taxonomy.cast()

        perm = f"{taxonomy._meta.app_label}.change_objecttag"

        perm_obj = ChangeObjectTagPermissionItem(
            taxonomy=taxonomy,
            object_id=object_id,
        )

        if not request.user.has_perm(perm, perm_obj):
            raise PermissionDenied(
                "You do not have permission to change object tags for this taxonomy or object_id."
            )

        body = ObjectTagUpdateBodySerializer(data=request.data)
        body.is_valid(raise_exception=True)

        tags = body.data.get("tags", [])
        try:
            tag_object(taxonomy, tags, object_id)
        except ValueError as e:
            raise ValidationError(e)

        return self.retrieve(request, object_id)


class TaxonomyTagsView(ListAPIView):
    """
    View to list tags of a taxonomy.

    **List Query Parameters**
        * pk (required) - The pk of the taxonomy to retrieve tags.
        * parent_tag_id (optional) - Id of the tag to retrieve children tags.
        * page (optional) - Page number (default: 1)
        * page_size (optional) - Number of items per page (default: 10)

    **List Example Requests**
        GET api/tagging/v1/taxonomy/:pk/tags                                        - Get tags of taxonomy
        GET api/tagging/v1/taxonomy/:pk/tags?parent_tag_id=30                       - Get children tags of tag

    **List Query Returns**
        * 200 - Success
        * 400 - Invalid query parameter
        * 403 - Permission denied
        * 404 - Taxonomy not found
    """

    permission_classes = [TagListPermissions]
    pagination_enabled = True

    def __init__(self):
        # Initialized here to avoid errors on type hints
        self.serializer_class = TagsSerializer

    def get_pagination_class(self):
        """
        Get the corresponding class depending if the pagination is enabled.

        It is necessary to call this function before returning the data.
        """
        if self.pagination_enabled:
            return TagsPagination
        else:
            return DisabledTagsPagination

    def get_taxonomy(self, pk: int) -> Taxonomy:
        """
        Get the taxonomy from `pk` or raise 404.
        """
        taxonomy = get_taxonomy(pk)
        if not taxonomy:
            raise Http404("Taxonomy not found")
        self.check_object_permissions(self.request, taxonomy)
        return taxonomy

    def _build_search_tree(self, tags: list[Tag]) -> list[Tag]:
        """
        Builds a tree with the result tags for a search.

        The retult is a pruned tree that contains
        the path from root tags to tags that match the search.
        """
        tag_ids = [tag.id for tag in tags]

        # Get missing parents.
        # Not all parents are in the search result.
        # This occurs when a child tag is on the search result, but its parent not,
        # we need to add the parent to show the tree from the root to the child.
        for tag in tags:
            if tag.parent and tag.parent_id and tag.parent_id not in tag_ids:
                tag_ids.append(tag.parent_id)
                tags.append(tag.parent)  # Our loop will iterate over this new parent tag too.

        groups: dict[int, list[Tag]] = {}
        roots: list[Tag] = []

        # Group tags by parent
        for tag in tags:
            if tag.parent_id is not None:
                if tag.parent_id not in groups:
                    groups[tag.parent_id] = []
                groups[tag.parent_id].append(tag)
            else:
                roots.append(tag)

        for tag in tags:
            # Used to serialize searched childrens
            tag.sub_tags = groups.get(tag.id, [])  # type: ignore[attr-defined]

        return roots

    def get_matching_tags(
        self,
        taxonomy_id: int,
        parent_tag_id: str | None = None,
        search_term: str | None = None,
    ) -> list[Tag]:
        """
        Returns a list of tags for the given taxonomy.

        The pagination can be enabled or disabled depending of the taxonomy size.
        You can read the desicion '0014_*' to more info about this logic.
        Also, determines the serializer to be used.

        Use `parent_tag_id` to get the children of the given tag.

        Use `search_term` to filter tags values that contains the given term.
        """
        taxonomy = self.get_taxonomy(taxonomy_id)
        if parent_tag_id:
            # Get children of a tag.

            # If you need to get the children, then the roots are
            # paginated, so we need to paginate the childrens too.
            self.pagination_enabled = True

            # Normal serializer, with children link.
            self.serializer_class = TagsSerializer
            return get_children_tags(
                taxonomy,
                int(parent_tag_id),
                search_term=search_term,
            )
        else:
            if search_term:
                # Search tags
                result = search_tags(
                    taxonomy,
                    search_term,
                )
                # Checks the result size to determine whether
                # to turn pagination on or off.
                self.pagination_enabled = len(result) > SEARCH_TAGS_THRESHOLD

                # Use the special serializer to only show the tree
                # of the search result.
                self.serializer_class = TagsForSearchSerializer

                result = self._build_search_tree(result)
            else:
                # Get root tags of taxonomy

                # Checks the taxonomy size to determine whether
                # to turn pagination on or off.
                self.pagination_enabled = taxonomy.tag_set.count() > TAGS_THRESHOLD

                if self.pagination_enabled:
                    # If pagination is enabled, use the normal serializer
                    # with children link.
                    self.serializer_class = TagsSerializer
                else:
                    # If pagination is disabled, use the special serializer
                    # to show children. In this case, we return all taxonomy tags
                    # in a tree structure.
                    self.serializer_class = TagsWithSubTagsSerializer

                result = get_root_tags(taxonomy)

            return result

    def get_queryset(self) -> list[Tag]:  # type: ignore[override]
        """
        Builds and returns the queryset to be paginated.

        The return type is not a QuerySet because the tagging python api functions
        return lists, and on this point convert the list to a query set
        is an unnecesary operation.
        """
        pk = self.kwargs.get("pk")
        parent_tag_id = self.request.query_params.get("parent_tag_id", None)
        search_term = self.request.query_params.get("search_term", None)

        result = self.get_matching_tags(
            pk,
            parent_tag_id=parent_tag_id,
            search_term=search_term,
        )

        # This function is not called automatically
        self.pagination_class = self.get_pagination_class()

        return result
