"""
Utilities for the API
"""
from typing import Type

from edx_rest_framework_extensions.auth.jwt.authentication import JwtAuthentication  # type: ignore[import]
from edx_rest_framework_extensions.auth.session.authentication import (  # type: ignore[import]
    SessionAuthenticationAllowInactiveUser,
)
from rest_framework.request import Request


def view_auth_classes(func_or_class):
    """
    Function and class decorator that abstracts the authentication classes for api views.
    """
    def _decorator(func_or_class):
        """
        Requires either OAuth2 or Session-based authentication;
        are the same authentication classes used on edx-platform
        """
        func_or_class.authentication_classes = (
            JwtAuthentication,
            SessionAuthenticationAllowInactiveUser,
        )
        return func_or_class
    return _decorator(func_or_class)


class UserPermissionsHelper:
    """
    Provides helper methods for serializing user permissions.
    """
    @property
    def _model(self) -> Type:
        """
        Returns the model used when checking permissions.
        """
        raise NotImplementedError  # pragma: no cover

    @property
    def _request(self) -> Request:
        """
        Returns the current request.
        """
        raise NotImplementedError  # pragma: no cover

    def _can(self, action: str, instance=None) -> bool:
        """
        Returns True if the current `request.user` may perform the given `action` on the `instance` object.
        """
        assert action in ("add", "view", "change", "delete")
        request = self._request
        assert request and request.user
        model = self._model
        assert model

        app_label = model._meta.app_label
        model_name = model._meta.model_name
        perm_name = f'{app_label}.{action}_{model_name}'
        return request.user.has_perm(perm_name, instance)

    def get_can_add(self, _instance=None) -> bool:
        """
        Returns True if the current user is allowed to add new instances.

        Note: we omit the actual instance from the permissions check; most tagging models prefer this.
        """
        return self._can('add')

    def get_can_view(self, instance) -> bool:
        """
        Returns True if the current user is allowed to view/see this instance.
        """
        return self._can('view', instance)

    def get_can_change(self, instance) -> bool:
        """
        Returns True if the current user is allowed to edit/change this instance.
        """
        return self._can('change', instance)

    def get_can_delete(self, instance) -> bool:
        """
        Returns True if the current user is allowed to delete this instance.
        """
        return self._can('delete', instance)
