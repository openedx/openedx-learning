"""Units API.

This module provides functions to manage units.
"""
from dataclasses import dataclass
from datetime import datetime

from django.db.transaction import atomic

from openedx_learning.apps.authoring.components.models import Component, ComponentVersion

from ..publishing import api as publishing_api
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
    "get_components_in_unit",
    "get_components_in_unit",
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
    return publishing_api.create_container(
        learning_package_id,
        key,
        created,
        created_by,
        container_cls=Unit,
    )


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

    This is a very low-level API, likely only needed for import/export. In
    general, you will use `create_unit_and_version()` and
    `create_next_unit_version()` instead.

    Args:
        unit_pk: The unit ID.
        version_num: The version number.
        title: The title.
        publishable_entities_pk: The publishable entities.
        entity: The entity.
        created: The creation date.
        created_by: The user who created the unit.
    """
    return publishing_api.create_container_version(
        unit.pk,
        version_num,
        title=title,
        publishable_entities_pks=publishable_entities_pks,
        entity_version_pks=entity_version_pks,
        created=created,
        created_by=created_by,
        container_version_cls=UnitVersion,
    )


def _pub_entities_for_components(
    components: list[Component | ComponentVersion] | None,
) -> tuple[list[int], list[int | None]] | tuple[None, None]:
    """
    Helper method: given a list of Component | ComponentVersion, return the
    lists of publishable_entities_pks and entity_version_pks needed for the
    base container APIs.

    ComponentVersion is passed when we want to pin a specific version, otherwise
    Component is used for unpinned.
    """
    if components is None:
        # When these are None, that means don't change the entities in the list.
        return None, None
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
    return publishable_entities_pks, entity_version_pks


def create_next_unit_version(
    unit: Unit,
    *,
    title: str | None = None,
    components: list[Component | ComponentVersion] | None = None,
    created: datetime,
    created_by: int | None = None,
) -> UnitVersion:
    """
    [ 🛑 UNSTABLE ] Create the next unit version.

    Args:
        unit_pk: The unit ID.
        title: The title. Leave as None to keep the current title.
        components: The components, as a list of Components (unpinned) and/or ComponentVersions (pinned). Passing None
           will leave the existing components unchanged.
        created: The creation date.
        created_by: The user who created the unit.
    """
    publishable_entities_pks, entity_version_pks = _pub_entities_for_components(components)
    unit_version = publishing_api.create_next_container_version(
        unit.pk,
        title=title,
        publishable_entities_pks=publishable_entities_pks,
        entity_version_pks=entity_version_pks,
        created=created,
        created_by=created_by,
        container_version_cls=UnitVersion,
    )
    return unit_version


def create_unit_and_version(
    learning_package_id: int,
    key: str,
    *,
    title: str,
    components: list[Component | ComponentVersion] | None = None,
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
    publishable_entities_pks, entity_version_pks = _pub_entities_for_components(components)
    with atomic():
        unit = create_unit(learning_package_id, key, created, created_by)
        unit_version = create_unit_version(
            unit,
            1,
            title=title,
            publishable_entities_pks=publishable_entities_pks or [],
            entity_version_pks=entity_version_pks or [],
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


def get_components_in_unit(
    unit: Unit,
    *,
    published: bool,
) -> list[UnitListEntry]:
    """
    [ 🛑 UNSTABLE ]
    Get the list of entities and their versions in the draft or published
    version of the given Unit.

    Args:
        unit: The Unit, e.g. returned by `get_unit()`
        published: `True` if we want the published version of the unit, or
            `False` for the draft version.
    """
    assert isinstance(unit, Unit)
    components = []
    for entry in publishing_api.get_entities_in_container(unit, published=published):
        # Convert from generic PublishableEntityVersion to ComponentVersion:
        component_version = entry.entity_version.componentversion
        assert isinstance(component_version, ComponentVersion)
        components.append(UnitListEntry(component_version=component_version, pinned=entry.pinned))
    return components


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
    unit_pub_entity_version = publishing_api.get_published_version_as_of(unit.publishable_entity_id, publish_log_id)
    if unit_pub_entity_version is None:
        return None  # This unit was not published as of the given PublishLog ID.
    container_version = unit_pub_entity_version.containerversion

    entity_list = []
    rows = container_version.entity_list.entitylistrow_set.order_by("order_num")
    for row in rows:
        if row.entity_version is not None:
            component_version = row.entity_version.componentversion
            assert isinstance(component_version, ComponentVersion)
            entity_list.append(UnitListEntry(component_version=component_version, pinned=True))
        else:
            # Unpinned component - figure out what its latest published version was.
            # This is not optimized. It could be done in one query per unit rather than one query per component.
            pub_entity_version = publishing_api.get_published_version_as_of(row.entity_id, publish_log_id)
            if pub_entity_version:
                entity_list.append(UnitListEntry(component_version=pub_entity_version.componentversion, pinned=False))
    return entity_list
