"""
Tagging API Views
"""
from __future__ import annotations

from typing import Any

from django.db import models
from django.http import Http404, HttpResponse
from rest_framework import mixins, status
from rest_framework.decorators import action
from rest_framework.exceptions import MethodNotAllowed, PermissionDenied, ValidationError
from rest_framework.generics import ListAPIView, RetrieveUpdateDestroyAPIView
from rest_framework.request import Request
from rest_framework.response import Response
from rest_framework.viewsets import GenericViewSet, ModelViewSet

from ...api import (
    TagDoesNotExist,
    add_tag_to_taxonomy,
    create_taxonomy,
    delete_tags_from_taxonomy,
    get_object_tags,
    get_taxonomies,
    get_taxonomy,
    tag_object,
    update_tag_in_taxonomy,
)
from ...data import TagDataQuerySet
from ...import_export.api import export_tags, get_last_import_log, import_tags
from ...import_export.parsers import ParserFormat
from ...models import ObjectTag, Taxonomy
from ...rules import ObjectTagPermissionItem
from ..paginators import TAGS_THRESHOLD, DisabledTagsPagination, TagsPagination
from .permissions import ObjectTagObjectPermissions, TagObjectPermissions, TaxonomyObjectPermissions
from .serializers import (
    ObjectTagListQueryParamsSerializer,
    ObjectTagsByTaxonomySerializer,
    ObjectTagSerializer,
    ObjectTagUpdateBodySerializer,
    ObjectTagUpdateQueryParamsSerializer,
    TagDataSerializer,
    TaxonomyExportQueryParamsSerializer,
    TaxonomyImportBodySerializer,
    TaxonomyImportNewBodySerializer,
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
    View to list, create, retrieve, update, delete, export or import Taxonomies.

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

    **Import/Create Taxonomy Example Requests**
        POST /tagging/rest_api/v1/taxonomy/import/
        {
            "taxonomy_name": "Taxonomy Name",
            "taxonomy_description": "This is a description",
            "file": <file>,
        }

    **Import/Create Taxonomy Query Returns**
        * 200 - Success
        * 400 - Bad request
        * 403 - Permission denied

    **Import/Update Taxonomy Example Requests**
        PUT /tagging/rest_api/v1/taxonomy/:pk/tags/import/
        {
            "file": <file>,
        }

    **Import/Update Taxonomy Query Returns**
        * 200 - Success
        * 400 - Bad request
        * 403 - Permission denied
    """

    # System taxonomies use negative numbers for their primary keys
    lookup_value_regex = r'-?\d+'
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

    @action(detail=False, url_path="import", methods=["post"])
    def create_import(self, request: Request, **_kwargs) -> Response:
        """
        Creates a new taxonomy and imports the tags from the uploaded file.
        """
        body = TaxonomyImportNewBodySerializer(data=request.data)
        body.is_valid(raise_exception=True)

        taxonomy_name = body.validated_data["taxonomy_name"]
        taxonomy_description = body.validated_data["taxonomy_description"]
        file = body.validated_data["file"].file
        parser_format = body.validated_data["parser_format"]

        taxonomy = create_taxonomy(taxonomy_name, taxonomy_description)
        try:
            import_success = import_tags(taxonomy, file, parser_format)

            if import_success:
                serializer = self.get_serializer(taxonomy)
                return Response(serializer.data, status=status.HTTP_201_CREATED)
            else:
                import_error = get_last_import_log(taxonomy)
                taxonomy.delete()
                return Response(import_error, status=status.HTTP_400_BAD_REQUEST)
        except ValueError as e:
            return Response(str(e), status=status.HTTP_400_BAD_REQUEST)

    @action(detail=True, url_path="tags/import", methods=["put"])
    def update_import(self, request: Request, **_kwargs) -> Response:
        """
        Imports tags from the uploaded file to an already created taxonomy.
        """
        body = TaxonomyImportBodySerializer(data=request.data)
        body.is_valid(raise_exception=True)

        file = body.validated_data["file"].file
        parser_format = body.validated_data["parser_format"]

        taxonomy = self.get_object()
        try:
            import_success = import_tags(taxonomy, file, parser_format)

            if import_success:
                serializer = self.get_serializer(taxonomy)
                return Response(serializer.data)
            else:
                import_error = get_last_import_log(taxonomy)
                return Response(import_error, status=status.HTTP_400_BAD_REQUEST)
        except ValueError as e:
            return Response(str(e), status=status.HTTP_400_BAD_REQUEST)


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

        if object_id.endswith("*") or "," in object_id:  # pylint: disable=no-else-raise
            raise ValidationError("Retrieving tags from multiple objects is not yet supported.")
            # Note: This API is actually designed so that in the future it can be extended to return tags for multiple
            # objects, e.g. if object_id.endswith("*") then it results in a object_id__startswith query. However, for
            # now we have no use case for that so we retrieve tags for one object at a time.
        else:
            if not self.request.user.has_perm(
                "oel_tagging.view_objecttag",
                # The obj arg expects a model, but we are passing an object
                ObjectTagPermissionItem(taxonomy=taxonomy, object_id=object_id),  # type: ignore[arg-type]
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
        serializer = ObjectTagsByTaxonomySerializer(list(object_tags))
        response_data = serializer.data
        if self.kwargs["object_id"] not in response_data:
            # For consistency, the key with the object_id should always be present in the response, even if there
            # are no tags at all applied to this object.
            response_data[self.kwargs["object_id"]] = {"taxonomies": []}
        return Response(response_data)

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
class ObjectTagCountsView(
    mixins.RetrieveModelMixin,
    GenericViewSet,
):
    """
    View to retrieve the count of ObjectTags for all matching object IDs.

    This API does NOT bother doing any permission checks as the "# of tags" is not considered sensitive information.

    **Retrieve Parameters**
        * object_id_pattern (required): - The Object ID to retrieve ObjectTags for. Can contain '*' at the end
          for wildcard matching, or use ',' to separate multiple object IDs.

    **Retrieve Example Requests**
        GET api/tagging/v1/object_tag_counts/:object_id_pattern

    **Retrieve Query Returns**
        * 200 - Success
    """

    serializer_class = ObjectTagSerializer
    lookup_field = "object_id_pattern"

    def retrieve(self, request, *args, **kwargs) -> Response:
        """
        Retrieve the counts of object tags that belong to a given object_id pattern

        Note: We override `retrieve` here instead of `list` because we are
        passing in the Object ID (object_id) in the path (as opposed to passing
        it in as a query_param) to retrieve the ObjectTag counts.
        """
        # This API does NOT bother doing any permission checks as the # of tags is not considered sensitive information.
        object_id_pattern = self.kwargs["object_id_pattern"]
        qs: Any = ObjectTag.objects
        if object_id_pattern.endswith("*"):
            qs = qs.filter(object_id__startswith=object_id_pattern[0:len(object_id_pattern) - 1])
        elif "*" in object_id_pattern:
            raise ValidationError("Wildcard matches are only supported if the * is at the end.")
        else:
            qs = qs.filter(object_id__in=object_id_pattern.split(","))

        qs = qs.values("object_id").annotate(num_tags=models.Count("id")).order_by("object_id")
        return Response({row["object_id"]: row["num_tags"] for row in qs})


@view_auth_classes
class TaxonomyTagsView(ListAPIView, RetrieveUpdateDestroyAPIView):
    """
    View to list/create/update/delete tags of a taxonomy.

    If you specify ?root_only or ?parent_tag_value=..., only one "level" of the
    hierachy will be returned. Otherwise, several levels will be returned, in
    tree order, up to the maximum supported depth. Additional levels/depth can
    be retrieved by using ?parent_tag_value to load more data.

    Note: If the taxonomy is particularly large (> 1,000 tags), ?root_only is
    automatically set true by default and cannot be disabled. This way, users
    can more easily select which tags they want to expand in the tree, and load
    just that subset of the tree as needed. This may be changed in the future.

    **List Query Parameters**
        * id (required) - The ID of the taxonomy to retrieve tags.
        * parent_tag (optional) - Retrieve children of the tag with this value.
        * root_only (optional) - If specified, only root tags are returned.
        * include_counts (optional) - Include the count of how many times each
          tag has been used.
        * page (optional) - Page number (default: 1)
        * page_size (optional) - Number of items per page (default: 10)

    **List Example Requests**
        GET api/tagging/v1/taxonomy/:id/tags                                        - Get tags of taxonomy
        GET api/tagging/v1/taxonomy/:id/tags?parent_tag=Physics&include_counts      - Get child tags of tag

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
    pagination_class = TagsPagination
    serializer_class = TagDataSerializer

    def get_taxonomy(self, pk: int) -> Taxonomy:
        """
        Get the taxonomy from `pk` or raise 404.
        """
        taxonomy = get_taxonomy(pk)
        if not taxonomy:
            raise Http404("Taxonomy not found")
        self.check_object_permissions(self.request, taxonomy)
        return taxonomy

    def get_serializer_context(self):
        context = super().get_serializer_context()
        context.update({
            "request": self.request,
            "taxonomy_id": int(self.kwargs["pk"]),
        })
        return context

    def get_queryset(self) -> TagDataQuerySet:
        """
        Builds and returns the queryset to be paginated.
        """
        taxonomy_id = int(self.kwargs.get("pk"))
        taxonomy = self.get_taxonomy(taxonomy_id)
        parent_tag_value = self.request.query_params.get("parent_tag", None)
        root_only = "root_only" in self.request.query_params
        include_counts = "include_counts" in self.request.query_params
        search_term = self.request.query_params.get("search_term", None)

        if parent_tag_value:
            # Fetching tags below a certain parent is always paginated and only returns the direct children
            depth = 1
            if root_only:
                raise ValidationError("?root_only and ?parent_tag cannot be used together")
        else:
            if root_only:
                depth = 1  # User Explicitly requested to load only the root tags for now
            elif search_term:
                depth = None  # For search, default to maximum depth but use normal pagination
            elif taxonomy.tag_set.count() > TAGS_THRESHOLD:
                # This is a very large taxonomy. Only load the root tags at first, so users can choose what to load.
                depth = 1
            else:
                # We can load and display all the tags in the taxonomy at once:
                self.pagination_class = DisabledTagsPagination
                depth = None  # Maximum depth

        return taxonomy.get_filtered_tags(
            parent_tag_value=parent_tag_value,
            search_term=search_term,
            depth=depth,
            include_counts=include_counts,
        )

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
