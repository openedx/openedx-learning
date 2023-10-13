"""
Utilities for the API
"""
from edx_rest_framework_extensions.auth.jwt.authentication import JwtAuthentication  # type: ignore[import]
from edx_rest_framework_extensions.auth.session.authentication import (  # type: ignore[import]
    SessionAuthenticationAllowInactiveUser,
)


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
