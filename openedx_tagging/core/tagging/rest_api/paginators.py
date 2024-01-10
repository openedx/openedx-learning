"""
Paginators uses by the REST API
"""
from typing import Type

from edx_rest_framework_extensions.paginators import DefaultPagination  # type: ignore[import]
from rest_framework.response import Response

from openedx_tagging.core.tagging.models import Tag, Taxonomy

# From this point, the tags begin to be paginated
MAX_FULL_DEPTH_THRESHOLD = 10_000


class CanAddPermissionMixin:
    """
    Inserts a field into the top level of the paginated response indicating whether the request user has permission to
    add new instances of the current model.
    """
    field_name = 'can_add'

    def get_model(self) -> Type:
        """
        Returns the model that is being paginated.
        """
        raise NotImplementedError  # pragma: no cover

    def get_can_add(self) -> bool:
        """
        Returns True if the current user can add models.
        """
        user = self.request.user  # type: ignore[attr-defined]
        model = self.get_model()
        app_label = model._meta.app_label
        model_name = model._meta.model_name
        return user.has_perm(f'{app_label}.add_{model_name}')

    def get_paginated_response(self, data) -> Response:
        """
        Injects the user's model-level permissions into the paginated response.
        """
        response_data = super().get_paginated_response(data).data  # type: ignore[misc]
        response_data[self.field_name] = self.get_can_add()
        return Response(response_data)


class TaxonomyPagination(CanAddPermissionMixin, DefaultPagination):
    """
    Inserts permissions data for Taxonomies into the top level of the paginated response.
    """
    page_size = 500
    max_page_size = 500

    def get_model(self) -> Type:
        """
        Returns the model that is being paginated.
        """
        return Taxonomy


class TagsPagination(CanAddPermissionMixin, DefaultPagination):
    """
    Custom pagination configuration for taxonomies
    with a large number of tags. Used on the get tags API view.
    """
    page_size = 10
    max_page_size = 300

    def get_model(self) -> Type:
        """
        Returns the model that is being paginated.
        """
        return Tag


class DisabledTagsPagination(CanAddPermissionMixin, DefaultPagination):
    """
    Custom pagination configuration for taxonomies
    with a small number of tags. Used on the get tags API view

    This class allows to bring all the tags of the taxonomy.
    It should be used if the number of tags within
    the taxonomy does not exceed `TAGS_THRESHOLD`.
    """
    page_size = MAX_FULL_DEPTH_THRESHOLD
    max_page_size = MAX_FULL_DEPTH_THRESHOLD + 1

    def get_model(self) -> Type:
        """
        Returns the model that is being paginated.
        """
        return Tag
