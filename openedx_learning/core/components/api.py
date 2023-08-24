"""
Components API (warning: UNSTABLE, in progress API)

These functions are often going to be simple-looking write operations, but there
is bookkeeping logic needed across multiple models to keep state consistent. You
can read from the models directly for various queries if necessary–we do this in
the Django Admin for instance. But you should NEVER mutate this app's models
directly, since there might be other related models that you may not know about.

Please look at the models.py file for more information about the kinds of data
are stored in this app.
"""
from __future__ import annotations

from datetime import datetime
from pathlib import Path

from django.db.models import Q
from django.db.transaction import atomic

from ..publishing.api import create_publishable_entity, create_publishable_entity_version
from .models import Component, ComponentVersion, ComponentVersionRawContent


def create_component(
    learning_package_id: int,
    namespace: str,
    type: str,  # pylint: disable=redefined-builtin
    local_key: str,
    created: datetime,
    created_by: int | None,
):
    """
    Create a new Component (an entity like a Problem or Video)
    """
    key = f"{namespace}:{type}@{local_key}"
    with atomic():
        publishable_entity = create_publishable_entity(
            learning_package_id, key, created, created_by
        )
        component = Component.objects.create(
            publishable_entity=publishable_entity,
            learning_package_id=learning_package_id,
            namespace=namespace,
            type=type,
            local_key=local_key,
        )
    return component


def create_component_version(
    component_pk: int,
    version_num: int,
    title: str,
    created: datetime,
    created_by: int | None,
) -> ComponentVersion:
    """
    Create a new ComponentVersion
    """
    with atomic():
        publishable_entity_version = create_publishable_entity_version(
            entity_id=component_pk,
            version_num=version_num,
            title=title,
            created=created,
            created_by=created_by,
        )
        component_version = ComponentVersion.objects.create(
            publishable_entity_version=publishable_entity_version,
            component_id=component_pk,
        )
    return component_version


def create_component_and_version(
    learning_package_id: int,
    namespace: str,
    type: str,  # pylint: disable=redefined-builtin
    local_key: str,
    title: str,
    created: datetime,
    created_by: int | None,
):
    """
    Create a Component and associated ComponentVersion atomically
    """
    with atomic():
        component = create_component(
            learning_package_id, namespace, type, local_key, created, created_by
        )
        component_version = create_component_version(
            component.pk,
            version_num=1,
            title=title,
            created=created,
            created_by=created_by,
        )
        return (component, component_version)


def get_component_by_pk(component_pk: int) -> Component:
    return Component.objects.get(pk=component_pk)


def get_component_version_content(
    learning_package_key: str,
    component_key: str,
    version_num: int,
    key: Path,
) -> ComponentVersionRawContent:
    """
    Look up ComponentVersionRawContent by human readable keys.

    Can raise a django.core.exceptions.ObjectDoesNotExist error if there is no
    matching ComponentVersionRawContent.
    """
    return ComponentVersionRawContent.objects.select_related(
        "raw_content",
        "component_version",
        "component_version__component",
        "component_version__component__learning_package",
    ).get(
        Q(component_version__component__learning_package__key=learning_package_key)
        & Q(component_version__component__publishable_entity__key=component_key)
        & Q(component_version__publishable_entity_version__version_num=version_num)
        & Q(key=key)
    )


def add_content_to_component_version(
    component_version: ComponentVersion,
    raw_content_id: int,
    key: str,
    learner_downloadable=False,
) -> ComponentVersionRawContent:
    """
    Add a RawContent to the given ComponentVersion
    """
    cvrc, _created = ComponentVersionRawContent.objects.get_or_create(
        component_version=component_version,
        raw_content_id=raw_content_id,
        key=key,
        learner_downloadable=learner_downloadable,
    )
    return cvrc
