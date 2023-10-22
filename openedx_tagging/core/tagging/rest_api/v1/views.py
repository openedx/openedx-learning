"""
Tagging API Views
"""
from __future__ import annotations

from django.db import models
from django.http import Http404, HttpResponse
from rest_framework import mixins, status
from rest_framework.decorators import action
from rest_framework.exceptions import MethodNotAllowed, PermissionDenied, ValidationError
from rest_framework.generics import ListAPIView, RetrieveUpdateDestroyAPIView
from rest_framework.response import Response
from rest_framework.viewsets import GenericViewSet, ModelViewSet

from openedx_tagging.core.tagging.models.base import Tag

from ...api import (
    TagDoesNotExist,
    add_tag_to_taxonomy,
    create_taxonomy,
    delete_tags_from_taxonomy,
    get_children_tags,
    get_object_tags,
    get_root_tags,
    get_taxonomies,
    get_taxonomy,
    search_tags,
    tag_object,
    update_tag_in_taxonomy,
)
from ...import_export.api import export_tags
from ...import_export.parsers import ParserFormat
from ...models import Taxonomy
from ...rules import ObjectTagPermissionItem
from ..paginators import SEARCH_TAGS_THRESHOLD, TAGS_THRESHOLD, DisabledTagsPagination, TagsPagination
from .permissions import ObjectTagObjectPermissions, TagObjectPermissions, TaxonomyObjectPermissions
from .serializers import (
    ObjectTagListQueryParamsSerializer,
    ObjectTagSerializer,
    ObjectTagUpdateBodySerializer,
    ObjectTagUpdateQueryParamsSerializer,
    TagsForSearchSerializer,
    TagsSerializer,
    TagsWithSubTagsSerializer,
    TaxonomyExportQueryParamsSerializer,
    TaxonomyListQueryParamsSerializer,
    TaxonomySerializer,
    TaxonomyTagCreateBodySerializer,
    TaxonomyTagDeleteBodySerializer,
    TaxonomyTagUpdateBodySerializer,
)
from .utils import view_auth_classes


@view_auth_classes
class TaxonomyView(ModelViewSet):
    """
    View to list, create, retrieve, update, delete or export Taxonomies.

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
        * allow_multiple (optional): Indicates that multiple tags from this
          taxonomy may be added to an object (default: True).
        * allow_free_text (optional): Indicates that tags in this taxonomy need
          not be predefined; authors may enter their own tag values (default:
          False).

    **Create Example Requests**
        POST api/tagging/v1/taxonomy               - Create a taxonomy
        {
            "name": "Taxonomy Name",
            "description": "This is a description",
            "enabled": True,
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

    **Export Query Parameters**
        * output_format - Define the output format. Valid values: json, csv
        * download (optional) - Add headers on the response to let the browser
          automatically download the file.

    **Export Example Requests**
        GET api/tagging/v1/taxonomy/:pk/export?output_format=csv                - Export taxonomy as CSV
        GET api/tagging/v1/taxonomy/:pk/export?output_format=json               - Export taxonomy as JSON
        GET api/tagging/v1/taxonomy/:pk/export?output_format=csv&download=1     - Export and downloads taxonomy as CSV
        GET api/tagging/v1/taxonomy/:pk/export?output_format=json&download=1    - Export and downloads taxonomy as JSON

    **Export Query Returns**
        * 200 - Success
        * 400 - Invalid query parameter
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

    @action(detail=True, methods=["get"])
    def export(self, request, **_kwargs) -> HttpResponse:
        """
        Export a taxonomy.
        """
        taxonomy = self.get_object()
        perm = "oel_tagging.export_taxonomy"
        if not request.user.has_perm(perm, taxonomy):
            raise PermissionDenied("You do not have permission to export this taxonomy.")
        query_params = TaxonomyExportQueryParamsSerializer(
            data=request.query_params.dict()
        )
        query_params.is_valid(raise_exception=True)
        output_format = query_params.data.get("output_format")
        assert output_format is not None
        if output_format.lower() == "json":
            parser_format = ParserFormat.JSON
            content_type = "application/json"
        else:
            parser_format = ParserFormat.CSV
            if query_params.data.get("download"):
                content_type = "text/csv"
            else:
                content_type = "text"

        tags = export_tags(taxonomy, parser_format)
        if query_params.data.get("download"):
            response = HttpResponse(tags.encode('utf-8'), content_type=content_type)
            response["Content-Disposition"] = f'attachment; filename="{taxonomy.name}{parser_format.value}"'
            return response

        return HttpResponse(tags, content_type=content_type)


@view_auth_classes
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
        taxonomy = query_params.validated_data.get("taxonomy", None)
        taxonomy_id = None
        if taxonomy:
            taxonomy = taxonomy.cast()
            taxonomy_id = taxonomy.id

        perm = "oel_tagging.view_objecttag"
        perm_obj = ObjectTagPermissionItem(
            taxonomy=taxonomy,
            object_id=object_id,
        )

        if not self.request.user.has_perm(
            perm,
            # The obj arg expects a model, but we are passing an object
            perm_obj,  # type: ignore[arg-type]
        ):
            raise PermissionDenied(
                "You do not have permission to view object tags for this taxonomy or object_id."
            )

        return get_object_tags(object_id, taxonomy_id)

    def retrieve(self, request, *args, **kwargs) -> Response:
        """
        Retrieve ObjectTags that belong to a given object_id

        Note: We override `retrieve` here instead of `list` because we are
        passing in the Object ID (object_id) in the path (as opposed to passing
        it in as a query_param) to retrieve the related ObjectTags.
        By default retrieve would expect an ObjectTag ID to be passed in the
        path and returns a it as a single result however that is not
        behavior we want.
        """
        object_tags = self.filter_queryset(self.get_queryset())
        serializer = ObjectTagSerializer(object_tags, many=True)
        return Response(serializer.data)

    def update(self, request, *args, **kwargs) -> Response:
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

        partial = kwargs.pop('partial', False)
        if partial:
            raise MethodNotAllowed("PATCH", detail="PATCH not allowed")

        query_params = ObjectTagUpdateQueryParamsSerializer(
            data=request.query_params.dict()
        )
        query_params.is_valid(raise_exception=True)
        taxonomy = query_params.validated_data.get("taxonomy", None)
        taxonomy = taxonomy.cast()

        perm = "oel_tagging.change_objecttag"

        object_id = kwargs.pop('object_id')
        perm_obj = ObjectTagPermissionItem(
            taxonomy=taxonomy,
            object_id=object_id,
        )

        if not request.user.has_perm(
            perm,
            # The obj arg expects a model, but we are passing an object
            perm_obj,  # type: ignore[arg-type]
        ):
            raise PermissionDenied(
                "You do not have permission to change object tags for this taxonomy or object_id."
            )

        body = ObjectTagUpdateBodySerializer(data=request.data)
        body.is_valid(raise_exception=True)

        tags = body.data.get("tags", [])
        try:
            tag_object(taxonomy, tags, object_id)
        except TagDoesNotExist as e:
            raise ValidationError from e
        except ValueError as e:
            raise ValidationError from e

        return self.retrieve(request, object_id)


@view_auth_classes
class TaxonomyTagsView(ListAPIView, RetrieveUpdateDestroyAPIView):
    """
    View to list/create/update/delete tags of a taxonomy.

    **List Query Parameters**
        * id (required) - The ID of the taxonomy to retrieve tags.
        * parent_tag_id (optional) - Id of the tag to retrieve children tags.
        * page (optional) - Page number (default: 1)
        * page_size (optional) - Number of items per page (default: 10)

    **List Example Requests**
        GET api/tagging/v1/taxonomy/:id/tags                                        - Get tags of taxonomy
        GET api/tagging/v1/taxonomy/:id/tags?parent_tag_id=30                       - Get children tags of tag

    **List Query Returns**
        * 200 - Success
        * 400 - Invalid query parameter
        * 403 - Permission denied
        * 404 - Taxonomy not found

    **Create Query Parameters**
        * id (required) - The ID of the taxonomy to create a Tag for

    **Create Request Body**
        * tag (required): The value of the Tag that should be added to
          the Taxonomy
        * parent_tag_value (optional): The value of the parent tag that the new
          Tag should fall under
        * extenal_id (optional): The external id for the new Tag

    **Create Example Requests**
        POST api/tagging/v1/taxonomy/:id/tags                                       - Create a Tag in taxonomy
        {
            "value": "New Tag",
            "parent_tag_value": "Parent Tag"
            "external_id": "abc123",
        }

    **Create Query Returns**
        * 201 - Success
        * 400 - Invalid parameters provided
        * 403 - Permission denied
        * 404 - Taxonomy not found

    **Update Query Parameters**
        * id (required) - The ID of the taxonomy to update a Tag in

    **Update Request Body**
        * tag (required): The value (identifier) of the Tag to be updated
        * updated_tag_value (required): The updated value of the Tag

    **Update Example Requests**
        PATCH api/tagging/v1/taxonomy/:id/tags                                      - Update a Tag in Taxonomy
        {
            "tag": "Tag 1",
            "updated_tag_value": "Updated Tag Value"
        }

    **Update Query Returns**
        * 200 - Success
        * 400 - Invalid parameters provided
        * 403 - Permission denied
        * 404 - Taxonomy, Tag or Parent Tag not found

    **Delete Query Parameters**
        * id (required) - The ID of the taxonomy to Delete Tag(s) in

    **Delete Request Body**
        * tags (required): The values (identifiers) of Tags that should be
                           deleted from Taxonomy
        * with_subtags (optional): If a Tag in the provided ids contains
                                   children (subtags), deletion will fail unless
                                   set to `True`. Defaults to `False`.

    **Delete Example Requests**
        DELETE api/tagging/v1/taxonomy/:id/tags                                     - Delete Tag(s) in Taxonomy
        {
            "tags": ["Tag 1", "Tag 2", "Tag 3"],
            "with_subtags": True
        }

    **Delete Query Returns**
        * 200 - Success
        * 400 - Invalid parameters provided
        * 403 - Permission denied
        * 404 - Taxonomy not found

    """

    permission_classes = [TagObjectPermissions]
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

    def get_queryset(self) -> models.QuerySet[Tag]:  # type: ignore[override]
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

        # Convert the results back to a QuerySet for permissions to apply
        # Due to the conversion we lose the populated `sub_tags` attribute,
        # in the case of using the special search serializer so we
        # need to repopulate it again
        if self.serializer_class == TagsForSearchSerializer:
            results_dict = {tag.id: tag for tag in result}

            result_queryset = Tag.objects.filter(id__in=results_dict.keys())

            for tag in result_queryset:
                sub_tags = results_dict[tag.id].sub_tags  # type: ignore[attr-defined]
                tag.sub_tags = sub_tags  # type: ignore[attr-defined]

        else:
            result_queryset = Tag.objects.filter(id__in=[tag.id for tag in result])

        # This function is not called automatically
        self.pagination_class = self.get_pagination_class()

        return result_queryset

    def post(self, request, *args, **kwargs):
        """
        Creates new Tag in Taxonomy and returns the newly created Tag.
        """
        pk = self.kwargs.get("pk")
        taxonomy = self.get_taxonomy(pk)

        body = TaxonomyTagCreateBodySerializer(data=request.data)
        body.is_valid(raise_exception=True)

        tag = body.data.get("tag")
        parent_tag_value = body.data.get("parent_tag_value", None)
        external_id = body.data.get("external_id", None)

        try:
            new_tag = add_tag_to_taxonomy(
                taxonomy, tag, parent_tag_value, external_id
            )
        except TagDoesNotExist as e:
            raise Http404("Parent Tag not found") from e
        except ValueError as e:
            raise ValidationError(e) from e

        self.serializer_class = TagsSerializer
        serializer_context = self.get_serializer_context()
        return Response(
            self.serializer_class(new_tag, context=serializer_context).data,
            status=status.HTTP_201_CREATED
        )

    def update(self, request, *args, **kwargs):
        """
        Updates a Tag that belongs to the Taxonomy and returns it.
        Currently only updating the Tag value is supported.
        """
        pk = self.kwargs.get("pk")
        taxonomy = self.get_taxonomy(pk)

        body = TaxonomyTagUpdateBodySerializer(data=request.data)
        body.is_valid(raise_exception=True)

        tag = body.data.get("tag")
        updated_tag_value = body.data.get("updated_tag_value")

        try:
            updated_tag = update_tag_in_taxonomy(taxonomy, tag, updated_tag_value)
        except TagDoesNotExist as e:
            raise Http404("Tag not found") from e
        except ValueError as e:
            raise ValidationError(e) from e

        self.serializer_class = TagsSerializer
        serializer_context = self.get_serializer_context()
        return Response(
            self.serializer_class(updated_tag, context=serializer_context).data,
            status=status.HTTP_200_OK
        )

    def delete(self, request, *args, **kwargs):
        """
        Deletes Tag(s) in Taxonomy. If any of the Tags have children and
        the `with_subtags` is not set to `True` it will fail, otherwise
        the sub-tags will be deleted as well.
        """
        pk = self.kwargs.get("pk")
        taxonomy = self.get_taxonomy(pk)

        body = TaxonomyTagDeleteBodySerializer(data=request.data)
        body.is_valid(raise_exception=True)

        tags = body.data.get("tags")
        with_subtags = body.data.get("with_subtags")

        try:
            delete_tags_from_taxonomy(taxonomy, tags, with_subtags)
        except ValueError as e:
            raise ValidationError(e) from e

        return Response(status=status.HTTP_200_OK)
