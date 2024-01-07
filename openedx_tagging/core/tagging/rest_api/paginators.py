"""
Paginators uses by the REST API
"""
from typing import Type

from edx_rest_framework_extensions.paginators import DefaultPagination  # type: ignore[import]
from rest_framework.response import Response

from openedx_tagging.core.tagging.models import Tag, Taxonomy

# From this point, the tags begin to be paginated
MAX_FULL_DEPTH_THRESHOLD = 10_000


class ModelPermissionsPaginationMixin:
    """
    Inserts model permissions data into the top level of the paginated response.
    """
    permission_field_name = 'user_permissions'
    permission_actions = ('add', 'view', 'change', 'delete')

    def get_model(self) -> Type:
        """
        Returns the model that is being paginated.
        """
        raise NotImplementedError  # pragma: no cover

    def get_model_permissions(self) -> dict:
        """
        Returns a dict containing the request user's permissions for the current model.

        The dict contains keys named `can_<action>`, mapped to a boolean flag.
        """
        user = self.request.user  # type: ignore[attr-defined]
        model = self.get_model()
        app_label = model._meta.app_label
        model_name = model._meta.model_name
        return {
            f'can_{action}': user.has_perm(f'{app_label}.{action}_{model_name}')
            for action in self.permission_actions
        }

    def get_paginated_response(self, data) -> Response:
        """
        Injects the user's model-level permissions into the paginated response.
        """
        response_data = super().get_paginated_response(data).data  # type: ignore[misc]
        response_data[self.permission_field_name] = self.get_model_permissions()
        return Response(response_data)


class TaxonomyPagination(ModelPermissionsPaginationMixin, DefaultPagination):
    """
    Inserts permissions data for Taxonomies into the top level of the paginated response.
    """
    def get_model(self) -> Type:
        """
        Returns the model that is being paginated.
        """
        return Taxonomy


class TagsPagination(ModelPermissionsPaginationMixin, DefaultPagination):
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


class DisabledTagsPagination(ModelPermissionsPaginationMixin, DefaultPagination):
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
