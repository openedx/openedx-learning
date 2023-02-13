"""
Public API for querying and manipulating Components.

This API is still under construction and should not be considered "stable" until
this repo hits a 1.0 release.
"""
from django.db.models import Q
from pathlib import Path

from .models import ComponentVersionRawContent


def get_component_version_content(
    learning_package_identifier: str,
    component_identifier: str,
    version_num: int,
    identifier: Path,
) -> ComponentVersionRawContent:
    """
    Look up ComponentVersionRawContent by human readable identifiers.

    Notes:

    1. This function is returning a model, which we generally frown upon.
    2. I'd like to experiment with different lookup methods
       (see https://github.com/openedx/openedx-learning/issues/34)

    Can raise a django.core.exceptions.ObjectDoesNotExist error if there is no
    matching ComponentVersionRawContent.
    """
    return ComponentVersionRawContent.objects.select_related(
        "raw_content",
        "component_version",
        "component_version__component",
        "component_version__component__learning_package",
    ).get(
        Q(
            component_version__component__learning_package__identifier=learning_package_identifier
        )
        & Q(component_version__component__identifier=component_identifier)
        & Q(component_version__version_num=version_num)
        & Q(identifier=identifier)
    )
