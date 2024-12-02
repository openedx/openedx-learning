"""Units API.

This module provides functions to manage units.
"""

from django.db.transaction import atomic

from openedx_learning.apps.authoring.containers.models import EntityListRow
from ..publishing import api as publishing_api
from ..containers import api as container_api
from .models import Unit, UnitVersion
from django.db.models import QuerySet


from datetime import datetime

__all__ = [
    "create_unit",
    "create_unit_version",
    "create_next_unit_version",
    "create_unit_and_version",
    "get_unit",
    "get_unit_version",
    "get_latest_unit_version",
    "get_user_defined_list_in_unit_version",
    "get_initial_list_in_unit_version",
    "get_frozen_list_in_unit_version",
]


def create_unit(
    learning_package_id: int, key: str, created: datetime, created_by: int | None
) -> Unit:
    """Create a new unit.

    Args:
        learning_package_id: The learning package ID.
        key: The key.
        created: The creation date.
        created_by: The user who created the unit.
    """
    with atomic():
        container = container_api.create_container(
            learning_package_id, key, created, created_by
        )
        unit = Unit.objects.create(
            container_entity=container,
            publishable_entity=container.publishable_entity,
        )
    return unit


def create_unit_version(
    unit: Unit,
    version_num: int,
    title: str,
    publishable_entities_pks: list[int],
    draft_version_pks: list[int | None],
    published_version_pks: list[int | None],
    created: datetime,
    created_by: int | None = None,
) -> Unit:
    """Create a new unit version.

    Args:
        unit_pk: The unit ID.
        version_num: The version number.
        title: The title.
        publishable_entities_pk: The publishable entities.
        entity: The entity.
        created: The creation date.
        created_by: The user who created the unit.
    """
    with atomic():
        container_entity_version = container_api.create_container_version(
            unit.container_entity.pk,
            version_num,
            title,
            publishable_entities_pks,
            draft_version_pks,
            published_version_pks,
            unit.container_entity.publishable_entity,
            created,
            created_by,
        )
        unit_version = UnitVersion.objects.create(
            unit=unit,
            container_entity_version=container_entity_version,
            publishable_entity_version=container_entity_version.publishable_entity_version,
        )
    return unit_version


def create_next_unit_version(
    unit: Unit,
    title: str,
    publishable_entities_pks: list[int],
    draft_version_pks: list[int | None],
    published_version_pks: list[int | None],
    created: datetime,
    created_by: int | None = None,
) -> Unit:
    """Create the next unit version.

    Args:
        unit_pk: The unit ID.
        title: The title.
        publishable_entities_pk: The components.
        entity: The entity.
        created: The creation date.
        created_by: The user who created the unit.
    """
    with atomic():
        # TODO: how can we enforce that publishable entities must be components?
        # This currently allows for any publishable entity to be added to a unit.
        container_entity_version = container_api.create_next_container_version(
            unit.container_entity.pk,
            title,
            publishable_entities_pks,
            draft_version_pks,
            published_version_pks,
            unit.container_entity.publishable_entity,
            created,
            created_by,
        )
        unit_version = UnitVersion.objects.create(
            unit=unit,
            container_entity_version=container_entity_version,
            publishable_entity_version=container_entity_version.publishable_entity_version,
        )
    return unit_version


def create_unit_and_version(
    learning_package_id: int,
    key: str,
    title: str,
    created: datetime,
    created_by: int | None = None,
) -> tuple[Unit, UnitVersion]:
    """Create a new unit and its version.

    Args:
        learning_package_id: The learning package ID.
        key: The key.
        created: The creation date.
        created_by: The user who created the unit.
    """
    with atomic():
        unit = create_unit(learning_package_id, key, created, created_by)
        unit_version = create_unit_version(
            unit,
            1,
            title,
            [],
            [],
            [],
            created,
            created_by,
        )
    return unit, unit_version


def get_unit(unit_pk: int) -> Unit:
    """Get a unit.

    Args:
        unit_pk: The unit ID.
    """
    return Unit.objects.get(pk=unit_pk)


def get_unit_version(unit_version_pk: int) -> UnitVersion:
    """Get a unit version.

    Args:
        unit_version_pk: The unit version ID.
    """
    return UnitVersion.objects.get(pk=unit_version_pk)


def get_latest_unit_version(unit_pk: int) -> UnitVersion:
    """Get the latest unit version.

    Args:
        unit_pk: The unit ID.
    """
    return Unit.objects.get(pk=unit_pk).versioning.latest


def get_user_defined_list_in_unit_version(unit_version_pk: int) -> QuerySet[EntityListRow]:
    """Get the list in a unit version.

    Args:
        unit_version_pk: The unit version ID.
    """
    unit_version = UnitVersion.objects.get(pk=unit_version_pk)
    return container_api.get_defined_list_rows_for_container_version(unit_version.container_entity_version)


def get_initial_list_in_unit_version(unit_version_pk: int) -> list[int]:
    """Get the initial list in a unit version.

    Args:
        unit_version_pk: The unit version ID.
    """
    unit_version = UnitVersion.objects.get(pk=unit_version_pk)
    return container_api.get_initial_list_rows_for_container_version(unit_version.container_entity_version)


def get_frozen_list_in_unit_version(unit_version_pk: int) -> list[int]:
    """Get the frozen list in a unit version.

    Args:
        unit_version_pk: The unit version ID.
    """
    unit_version = UnitVersion.objects.get(pk=unit_version_pk)
    return container_api.get_frozen_list_rows_for_container_version(unit_version.container_entity_version)
