"""Units API.

This module provides functions to manage units.
"""
from dataclasses import dataclass
from datetime import datetime

from django.db.transaction import atomic

from openedx_learning.apps.authoring.components.models import Component, ComponentVersion

from ..containers import api as container_api
from ..publishing.api import get_published_version_as_of
from .models import Unit, UnitVersion

# 🛑 UNSTABLE: All APIs related to containers are unstable until we've figured
#              out our approach to dynamic content (randomized, A/B tests, etc.)
__all__ = [
    "create_unit",
    "create_unit_version",
    "create_next_unit_version",
    "create_unit_and_version",
    "get_unit",
    "get_unit_version",
    "get_latest_unit_version",
    "UnitListEntry",
    "get_components_in_draft_unit",
    "get_components_in_published_unit",
    "get_components_in_published_unit_as_of",
]


def create_unit(
    learning_package_id: int, key: str, created: datetime, created_by: int | None
) -> Unit:
    """
    [ 🛑 UNSTABLE ] Create a new unit.

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
    *,
    title: str,
    publishable_entities_pks: list[int],
    entity_version_pks: list[int | None],
    created: datetime,
    created_by: int | None = None,
) -> UnitVersion:
    """
    [ 🛑 UNSTABLE ] Create a new unit version.

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
            title=title,
            publishable_entities_pks=publishable_entities_pks,
            entity_version_pks=entity_version_pks,
            entity=unit.container_entity.publishable_entity,
            created=created,
            created_by=created_by,
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
    components: list[Component | ComponentVersion],
    created: datetime,
    created_by: int | None = None,
) -> UnitVersion:
    """
    [ 🛑 UNSTABLE ] Create the next unit version.

    Args:
        unit_pk: The unit ID.
        title: The title.
        components: The components, as a list of Components (unpinned) and/or ComponentVersions (pinned)
        entity: The entity.
        created: The creation date.
        created_by: The user who created the unit.
    """
    for c in components:
        if not isinstance(c, (Component, ComponentVersion)):
            raise TypeError("Unit components must be either Component or ComponentVersion.")
    publishable_entities_pks = [
        (c.publishable_entity_id if isinstance(c, Component) else c.component.publishable_entity_id)
        for c in components
    ]
    entity_version_pks = [
        (cv.pk if isinstance(cv, ComponentVersion) else None)
        for cv in components
    ]
    with atomic():
        # TODO: how can we enforce that publishable entities must be components?
        # This currently allows for any publishable entity to be added to a unit.
        container_entity_version = container_api.create_next_container_version(
            unit.container_entity.pk,
            title=title,
            publishable_entities_pks=publishable_entities_pks,
            entity_version_pks=entity_version_pks,
            entity=unit.container_entity.publishable_entity,
            created=created,
            created_by=created_by,
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
    """
    [ 🛑 UNSTABLE ] Create a new unit and its version.

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
            title=title,
            publishable_entities_pks=[],
            entity_version_pks=[],
            created=created,
            created_by=created_by,
        )
    return unit, unit_version


def get_unit(unit_pk: int) -> Unit:
    """
    [ 🛑 UNSTABLE ] Get a unit.

    Args:
        unit_pk: The unit ID.
    """
    return Unit.objects.get(pk=unit_pk)


def get_unit_version(unit_version_pk: int) -> UnitVersion:
    """
    [ 🛑 UNSTABLE ] Get a unit version.

    Args:
        unit_version_pk: The unit version ID.
    """
    return UnitVersion.objects.get(pk=unit_version_pk)


def get_latest_unit_version(unit_pk: int) -> UnitVersion:
    """
    [ 🛑 UNSTABLE ] Get the latest unit version.

    Args:
        unit_pk: The unit ID.
    """
    return Unit.objects.get(pk=unit_pk).versioning.latest


@dataclass(frozen=True)
class UnitListEntry:
    """
    [ 🛑 UNSTABLE ]
    Data about a single entity in a container, e.g. a component in a unit.
    """
    component_version: ComponentVersion
    pinned: bool = False

    @property
    def component(self):
        return self.component_version.component


def get_components_in_draft_unit(
    unit: Unit,
) -> list[UnitListEntry]:
    """
    [ 🛑 UNSTABLE ]
    Get the list of entities and their versions in the draft version of the
    given container.
    """
    assert isinstance(unit, Unit)
    entity_list = []
    for entry in container_api.get_entities_in_draft_container(unit):
        # Convert from generic PublishableEntityVersion to ComponentVersion:
        component_version = entry.entity_version.componentversion
        assert isinstance(component_version, ComponentVersion)
        entity_list.append(UnitListEntry(component_version=component_version, pinned=entry.pinned))
    return entity_list


def get_components_in_published_unit(
    unit: Unit,
) -> list[UnitListEntry] | None:
    """
    [ 🛑 UNSTABLE ]
    Get the list of entities and their versions in the published version of the
    given container.

    Returns None if the unit was never published (TODO: should it throw instead?).
    """
    assert isinstance(unit, Unit)
    published_entities = container_api.get_entities_in_published_container(unit)
    if published_entities is None:
        return None  # There is no published version of this unit. Should this be an exception?
    entity_list = []
    for entry in published_entities:
        # Convert from generic PublishableEntityVersion to ComponentVersion:
        component_version = entry.entity_version.componentversion
        assert isinstance(component_version, ComponentVersion)
        entity_list.append(UnitListEntry(component_version=component_version, pinned=entry.pinned))
    return entity_list


def get_components_in_published_unit_as_of(
    unit: Unit,
    publish_log_id: int,
) -> list[UnitListEntry] | None:
    """
    [ 🛑 UNSTABLE ]
    Get the list of entities and their versions in the published version of the
    given container as of the given PublishLog version (which is essentially a
    version for the entire learning package).

    TODO: This API should be updated to also return the UnitVersion so we can
          see the unit title and any other metadata from that point in time.
    TODO: accept a publish log UUID, not just int ID?
    TODO: move the implementation to be a generic 'containers' implementation
          that this units function merely wraps.
    TODO: optimize, perhaps by having the publishlog store a record of all
          ancestors of every modified PublishableEntity in the publish.
    """
    assert isinstance(unit, Unit)
    unit_pub_entity_version = get_published_version_as_of(unit.publishable_entity_id, publish_log_id)
    if unit_pub_entity_version is None:
        return None  # This unit was not published as of the given PublishLog ID.
    unit_version = unit_pub_entity_version.unitversion  # type: ignore[attr-defined]

    entity_list = []
    rows = unit_version.container_entity_version.defined_list.entitylistrow_set.order_by("order_num")
    for row in rows:
        if row.entity_version is not None:
            component_version = row.entity_version.componentversion
            assert isinstance(component_version, ComponentVersion)
            entity_list.append(UnitListEntry(component_version=component_version, pinned=True))
        else:
            # Unpinned component - figure out what its latest published version was.
            # This is not optimized. It could be done in one query per unit rather than one query per component.
            pub_entity_version = get_published_version_as_of(row.entity_id, publish_log_id)
            if pub_entity_version:
                entity_list.append(UnitListEntry(component_version=pub_entity_version.componentversion, pinned=False))
    return entity_list
