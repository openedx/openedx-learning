"""
Tagging REST API exception handling utilities.
"""

import logging
import traceback

from django.conf import settings
from django.http import Http404
from rest_framework import status
from rest_framework.exceptions import APIException, PermissionDenied
from rest_framework.response import Response
from rest_framework.views import exception_handler

log = logging.getLogger(__name__)


def _custom_exception_handler(exc: Exception, context: dict) -> Response | None:
    """
    Return standard DRF errors for APIException and a generic 500 otherwise.
    This exception handler should eventually be replaced by a more top-level
    exception handler in the openedx-platform repo after the ADR for it is accepted:
    https://github.com/openedx/openedx-platform/pull/38246
    """
    # For exceptions expected by DRF return the standard DRF error response:
    # Instances of APIException, subclasses of APIException, Django's Http404 exception,
    # and Django's PermissionDenied exception.
    is_expected_exception = isinstance(
        exc, (APIException, Http404, PermissionDenied)
    )
    if is_expected_exception:
        return exception_handler(exc, context)

    # DRF always calls exception handlers from within an `except:` block, so we can assume
    # that `log.exception` will automatically insert those exception details and a stack trace.
    log.exception("Unexpected exception while handling API request")

    if settings.DEBUG:
        description_with_traceback = f"{exc.__class__.__name__}: {str(exc)}\n\nTraceback:\n{traceback.format_exc()}"

        return Response(
            {"detail": description_with_traceback},
            status=status.HTTP_500_INTERNAL_SERVER_ERROR,
        )

    return Response(
        {"detail": "An unexpected error occurred while processing the request."},
        status=status.HTTP_500_INTERNAL_SERVER_ERROR,
    )


class TaggingExceptionHandlerMixin:
    """
    Scope custom exception handling to tagging API views only.
    """

    def get_exception_handler(self):
        return _custom_exception_handler
