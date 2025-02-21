"""
Containers API.

This module provides a set of functions to interact with the containers
models in the Open edX Learning platform.
"""
from dataclasses import dataclass
from datetime import datetime

from django.core.exceptions import ValidationError
from django.db.models import QuerySet
from django.db.transaction import atomic

from openedx_learning.apps.authoring.containers.models_mixin import ContainerEntityMixin

from ..containers.models import ContainerEntity, ContainerEntityVersion, EntityList, EntityListRow
from ..publishing import api as publishing_api
from ..publishing.models import PublishableEntity, PublishableEntityVersion

# 🛑 UNSTABLE: All APIs related to containers are unstable until we've figured
#              out our approach to dynamic content (randomized, A/B tests, etc.)
__all__ = [
    "create_container",
    "create_container_version",
    "create_next_container_version",
    "create_container_and_version",
    "get_container",
    "ContainerEntityListEntry",
    "get_entities_in_draft_container",
    "get_entities_in_published_container",
    "contains_unpublished_changes",
]


def create_container(
    learning_package_id: int,
    key: str,
    created: datetime,
    created_by: int | None,
) -> ContainerEntity:
    """
    [ 🛑 UNSTABLE ]
    Create a new container.

    Args:
        learning_package_id: The ID of the learning package that contains the container.
        key: The key of the container.
        created: The date and time the container was created.
        created_by: The ID of the user who created the container

    Returns:
        The newly created container.
    """
    with atomic():
        publishable_entity = publishing_api.create_publishable_entity(
            learning_package_id, key, created, created_by
        )
        container = ContainerEntity.objects.create(
            publishable_entity=publishable_entity,
        )
    return container


def create_entity_list() -> EntityList:
    """
    [ 🛑 UNSTABLE ]
    Create a new entity list. This is an structure that holds a list of entities
    that will be referenced by the container.

    Returns:
        The newly created entity list.
    """
    return EntityList.objects.create()


def create_entity_list_with_rows(
    entity_pks: list[int],
    entity_version_pks: list[int | None],
) -> EntityList:
    """
    [ 🛑 UNSTABLE ]
    Create new entity list rows for an entity list.

    Args:
        entity_pks: The IDs of the publishable entities that the entity list rows reference.
        entity_version_pks: The IDs of the versions of the entities
            (PublishableEntityVersion) that the entity list rows reference, or
            Nones for "unpinned" (default).

    Returns:
        The newly created entity list.
    """
    order_nums = range(len(entity_pks))
    with atomic():
        entity_list = create_entity_list()
        EntityListRow.objects.bulk_create(
            [
                EntityListRow(
                    entity_list=entity_list,
                    entity_id=entity_pk,
                    order_num=order_num,
                    entity_version_id=entity_version_pk,
                )
                for order_num, entity_pk, entity_version_pk in zip(
                    order_nums, entity_pks, entity_version_pks
                )
            ]
        )
    return entity_list


def get_entity_list_with_pinned_versions(
    rows: QuerySet[EntityListRow],
) -> EntityList:
    """
    [ 🛑 UNSTABLE ]
    Copy rows from an existing entity list to a new entity list.

    Args:
        entity_list: The entity list to copy the rows to.
        rows: The rows to copy to the new entity list.

    Returns:
        The newly created entity list.
    """
    entity_list = create_entity_list()
    with atomic():
        _ = EntityListRow.objects.bulk_create(
            [
                EntityListRow(
                    entity_list=entity_list,
                    entity_id=row.entity.id,
                    order_num=row.order_num,
                    entity_version_id=None,  # For simplicity, we are not copying the pinned versions
                )
                for row in rows
            ]
        )

    return entity_list


def create_container_version(
    container_pk: int,
    version_num: int,
    *,
    title: str,
    publishable_entities_pks: list[int],
    entity_version_pks: list[int | None],
    entity: PublishableEntity,
    created: datetime,
    created_by: int | None,
) -> ContainerEntityVersion:
    """
    [ 🛑 UNSTABLE ]
    Create a new container version.

    Args:
        container_pk: The ID of the container that the version belongs to.
        version_num: The version number of the container.
        title: The title of the container.
        publishable_entities_pks: The IDs of the members of the container.
        entity: The entity that the container belongs to.
        created: The date and time the container version was created.
        created_by: The ID of the user who created the container version.

    Returns:
        The newly created container version.
    """
    with atomic():
        publishable_entity_version = publishing_api.create_publishable_entity_version(
            entity.pk,
            version_num=version_num,
            title=title,
            created=created,
            created_by=created_by,
        )
        entity_list = create_entity_list_with_rows(
            entity_pks=publishable_entities_pks,
            entity_version_pks=entity_version_pks,
        )
        container_version = ContainerEntityVersion.objects.create(
            publishable_entity_version=publishable_entity_version,
            container_id=container_pk,
            entity_list=entity_list,
        )
    return container_version


def create_next_container_version(
    container_pk: int,
    *,
    title: str,
    publishable_entities_pks: list[int],
    entity_version_pks: list[int | None],
    entity: PublishableEntity,
    created: datetime,
    created_by: int | None,
) -> ContainerEntityVersion:
    """
    [ 🛑 UNSTABLE ]
    Create the next version of a container. A new version of the container is created
    only when its metadata changes:

    * Something was added to the Container.
    * We re-ordered the rows in the container.
    * Something was removed from the container.
    * The Container's metadata changed, e.g. the title.
    * We pin to different versions of the Container.

    Args:
        container_pk: The ID of the container to create the next version of.
        title: The title of the container.
        publishable_entities_pks: The IDs of the members current members of the container.
        entity: The entity that the container belongs to.
        created: The date and time the container version was created.
        created_by: The ID of the user who created the container version.

    Returns:
        The newly created container version.
    """
    # Do a quick check that the given entities are in the right learning package:
    if PublishableEntity.objects.filter(
        pk__in=publishable_entities_pks,
    ).exclude(
        learning_package_id=entity.learning_package_id,
    ).exists():
        raise ValidationError("Container entities must be from the same learning package.")
    with atomic():
        container = ContainerEntity.objects.get(pk=container_pk)
        last_version = container.versioning.latest
        next_version_num = last_version.version_num + 1
        publishable_entity_version = publishing_api.create_publishable_entity_version(
            entity.pk,
            version_num=next_version_num,
            title=title,
            created=created,
            created_by=created_by,
        )
        next_entity_list = create_entity_list_with_rows(
            entity_pks=publishable_entities_pks,
            entity_version_pks=entity_version_pks,
        )
        next_container_version = ContainerEntityVersion.objects.create(
            publishable_entity_version=publishable_entity_version,
            container_id=container_pk,
            entity_list=next_entity_list,
        )

    return next_container_version


def create_container_and_version(
    learning_package_id: int,
    key: str,
    *,
    created: datetime,
    created_by: int | None,
    title: str,
    publishable_entities_pks: list[int],
    entity_version_pks: list[int | None],
) -> tuple[ContainerEntity, ContainerEntityVersion]:
    """
    [ 🛑 UNSTABLE ]
    Create a new container and its first version.

    Args:
        learning_package_id: The ID of the learning package that contains the container.
        key: The key of the container.
        created: The date and time the container was created.
        created_by: The ID of the user who created the container.
        version_num: The version number of the container.
        title: The title of the container.
        members_pk: The IDs of the members of the container.

    Returns:
        The newly created container version.
    """
    with atomic():
        container = create_container(learning_package_id, key, created, created_by)
        container_version = create_container_version(
            container_pk=container.publishable_entity.pk,
            version_num=1,
            title=title,
            publishable_entities_pks=publishable_entities_pks,
            entity_version_pks=entity_version_pks,
            entity=container.publishable_entity,
            created=created,
            created_by=created_by,
        )
    return (container, container_version)


def get_container(pk: int) -> ContainerEntity:
    """
    [ 🛑 UNSTABLE ]
    Get a container by its primary key.

    Args:
        pk: The primary key of the container.

    Returns:
        The container with the given primary key.
    """
    # TODO: should this use with_publishing_relations as in components?
    return ContainerEntity.objects.get(pk=pk)


@dataclass(frozen=True)
class ContainerEntityListEntry:
    """
    [ 🛑 UNSTABLE ]
    Data about a single entity in a container, e.g. a component in a unit.
    """
    entity_version: PublishableEntityVersion
    pinned: bool

    @property
    def entity(self):
        return self.entity_version.entity


def get_entities_in_draft_container(
    container: ContainerEntity | ContainerEntityMixin,
) -> list[ContainerEntityListEntry]:
    """
    [ 🛑 UNSTABLE ]
    Get the list of entities and their versions in the draft version of the
    given container.
    """
    if isinstance(container, ContainerEntityMixin):
        container = container.container_entity
    assert isinstance(container, ContainerEntity)
    entity_list = []
    for row in container.versioning.draft.entity_list.entitylistrow_set.order_by("order_num"):
        entity_version = row.entity_version or row.entity.draft.version
        if entity_version is not None:  # As long as this hasn't been soft-deleted:
            entity_list.append(ContainerEntityListEntry(
                entity_version=row.entity_version or row.entity.draft.version,
                pinned=row.entity_version is not None,
            ))
        # else should we indicate somehow a deleted item was here?
    return entity_list


def get_entities_in_published_container(
    container: ContainerEntity | ContainerEntityMixin,
) -> list[ContainerEntityListEntry] | None:
    """
    [ 🛑 UNSTABLE ]
    Get the list of entities and their versions in the draft version of the
    given container.
    """
    if isinstance(container, ContainerEntityMixin):
        cev = container.container_entity.versioning.published
    elif isinstance(container, ContainerEntity):
        cev = container.versioning.published
    else:
        raise TypeError(f"Expected ContainerEntity or ContainerEntityMixin; got {type(container)}")
    if cev is None:
        return None  # There is no published version of this container. Should this be an exception?
    assert isinstance(cev, ContainerEntityVersion)
    entity_list = []
    for row in cev.entity_list.entitylistrow_set.order_by("order_num"):
        entity_version = row.entity_version or row.entity.published.version
        if entity_version is not None:  # As long as this hasn't been soft-deleted:
            entity_list.append(ContainerEntityListEntry(
                entity_version=entity_version,
                pinned=row.entity_version is not None,
            ))
        # else should we indicate somehow a deleted item was here?
    return entity_list


def contains_unpublished_changes(
    container: ContainerEntity | ContainerEntityMixin,
) -> bool:
    """
    [ 🛑 UNSTABLE ]
    Check recursively if a container has any unpublished changes.

    Note: container.versioning.has_unpublished_changes only checks if the container
    itself has unpublished changes, not if its contents do.
    """
    if isinstance(container, ContainerEntityMixin):
        # The query below pre-loads the data we need but is otherwise the same thing as:
        #     container = container.container_entity
        container = ContainerEntity.objects.select_related(
            "publishable_entity",
            "publishable_entity__draft",
            "publishable_entity__draft__version",
            "publishable_entity__draft__version__containerentityversion__entity_list",
        ).get(pk=container.container_entity_id)
    else:
        pass  # TODO: select_related if we're given a raw ContainerEntity rather than a ContainerEntityMixin like Unit?
    assert isinstance(container, ContainerEntity)

    if container.versioning.has_unpublished_changes:
        return True

    # We only care about children that are un-pinned, since published changes to pinned children don't matter
    entity_list = container.versioning.draft.entity_list

    # TODO: This is a naive inefficient implementation but hopefully correct.
    # Once we know it's correct and have a good test suite, then we can optimize.
    # We will likely change to a tracking-based approach rather than a "scan for changes" based approach.
    for row in entity_list.entitylistrow_set.filter(entity_version=None).select_related(
        "entity__containerentity",
        "entity__draft__version",
        "entity__published__version",
    ):
        try:
            child_container = row.entity.containerentity
        except ContainerEntity.DoesNotExist:
            child_container = None
        if child_container:
            child_container = row.entity.containerentity
            # This is itself a container - check recursively:
            if child_container.versioning.has_unpublished_changes or contains_unpublished_changes(child_container):
                return True
        else:
            # This is not a container:
            draft_pk = row.entity.draft.version_id if row.entity.draft else None
            published_pk = row.entity.published.version_id if hasattr(row.entity, "published") else None
            if draft_pk != published_pk:
                return True
    return False
