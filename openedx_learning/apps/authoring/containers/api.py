"""
Containers API.

This module provides a set of functions to interact with the containers
models in the Open edX Learning platform.
"""

from django.db.transaction import atomic
from django.db.models import QuerySet

from datetime import datetime
from ..containers.models import (
    ContainerEntity,
    ContainerEntityVersion,
    EntityList,
    EntityListRow,
)
from ..publishing.models import PublishableEntity
from ..publishing import api as publishing_api


__all__ = [
    "create_container",
    "create_container_version",
    "create_next_container_version",
    "create_container_and_version",
    "get_container",
    "get_defined_list_for_container_version",
    "get_initial_list_for_container_version",
    "get_frozen_list_for_container_version",
]


def create_container(
    learning_package_id: int,
    key: str,
    created: datetime,
    created_by: int | None,
) -> ContainerEntity:
    """
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
    Create a new entity list. This is an structure that holds a list of entities
    that will be referenced by the container.

    Returns:
        The newly created entity list.
    """
    return EntityList.objects.create()


def create_entity_list_row(
    entity_list: EntityList,
    entity_pk: int,
    order_num: int,
    draft_version_pk: int | None,
    published_version_pk: int | None,
) -> EntityListRow:
    """
    Create a new entity list row. This is a row in an entity list that references
    publishable entities.

    Args:
        entity_list: The entity list that the entity list row belongs to.
        entity: The ID of the publishable entity that the entity list row references.
        order_num: The order_num of the entity list row in the entity list.
        draft_version_pk: The ID of the draft version of the entity (PublishableEntityVersion) that the entity list row references.
        published_version_pk: The ID of the published version of the entity (PublishableEntityVersion) that the entity list row references

    Returns:
        The newly created entity list row.
    """
    return EntityListRow.objects.create(
        entity_list=entity_list,
        entity_id=entity_pk,
        order_num=order_num,
        draft_version_id=draft_version_pk,
        published_version_id=published_version_pk,
    )


def create_entity_list_with_rows(
    entity_pks: list[int],
    draft_version_pks: list[int | None],
    published_version_pks: list[int | None],
) -> EntityList:
    """
    Create a new entity list with rows.

    Args:
        entity_pks: The IDs of the publishable entities that the entity list rows reference.
        order_nums: The order_nums of the entity list rows in the entity list.
        draft_version_pks: The IDs of the draft versions of the entities (PublishableEntityVersion) that the entity list rows reference.
        published_version_pks: The IDs of the published versions of the entities (PublishableEntityVersion) that the entity list rows reference.

    Returns:
        The newly created entity list.
    """
    entity_list = create_entity_list()
    order_nums = range(len(entity_pks))
    for entity_pk, order_num, draft_version_pk, published_version_pk in zip(
        entity_pks, order_nums, draft_version_pks, published_version_pks
    ):
        create_entity_list_row(
            entity_list=entity_list,
            entity_pk=entity_pk,
            order_num=order_num,
            draft_version_pk=draft_version_pk,
            published_version_pk=published_version_pk,
        )
    return entity_list


def create_container_version(
    container_pk: int,
    version_num: int,
    title: str,
    publishable_entities_pk: list[int],
    entity: PublishableEntity,
    created: datetime,
    created_by: int | None,
) -> ContainerEntityVersion:
    """
    Create a new container version.

    Args:
        container_pk: The ID of the container that the version belongs to.
        version_num: The version number of the container.
        title: The title of the container.
        publishable_entities_pk: The IDs of the members of the container.
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
        # This implementation assumes:
        # 1. We are creating the first version of the container, so the defined list is the same as the initial list.
        # 2. The frozen list is empty because this is the first version.
        # 3. Published and draft versions are always the latest for all members.
        entity_list = create_entity_list_with_rows(
            entity_pks=publishable_entities_pk,
            draft_version_pks=[None] * len(publishable_entities_pk),
            published_version_pks=[None] * len(publishable_entities_pk),
        )
        container_version = ContainerEntityVersion.objects.create(
            publishable_entity_version=publishable_entity_version,
            container_id=container_pk,
            defined_list=entity_list,
            initial_list=entity_list,
            frozen_list=None,
        )
    return container_version


def create_next_container_version(
    container_pk: int,
    title: str,
    publishable_entities_pk: list[int],
    entity: PublishableEntity,
    created: datetime,
    created_by: int | None,
) -> ContainerEntityVersion:
    """
    Create the next version of a container.

    Args:
        container_pk: The ID of the container to create the next version of.
        title: The title of the container.
        publishable_entities_pk: The IDs of the members of the container.
        entity: The entity that the container belongs to.
        created: The date and time the container version was created.
        created_by: The ID of the user who created the container version.

    Returns:
        The newly created container version.
    """
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
        # This implementation assumes:
        # 1. The changes provoking a new version are the addition, removal of members or reordering.
        # 2. Published and draft versions are always the latest for all members.
        # 3. When creating a new version, a new user-defined entity list is created to preserve the latest state as the previous user-defined list.
        # TODO: instead consider copying the previous user-defined list as the frozen list, and add/remove to the previous user-defined list.
        # If it's a reordering, the previous user-defined list is copied as the frozen and a new user-defined list is created with the new order.
        new_user_defined_list = create_entity_list_with_rows(
            entity_pks=publishable_entities_pk,
            draft_version_pks=[None] * len(publishable_entities_pk),
            published_version_pks=[None] * len(publishable_entities_pk),
        )
        container_version = ContainerEntityVersion.objects.create(
            publishable_entity_version=publishable_entity_version,
            container_id=container_pk,
            defined_list=new_user_defined_list,
            initial_list=last_version.initial_list,
            frozen_list=last_version.defined_list,
        )
    return container_version


def create_container_and_version(
    learning_package_id: int,
    key: str,
    created: datetime,
    created_by: int | None,
    title: str,
    publishable_entities_pk: list[int],
) -> ContainerEntityVersion:
    """
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
            publishable_entities_pk=publishable_entities_pk,
            entity=container.publishable_entity,
            created=created,
            created_by=created_by,
        )
    return (container, container_version)


def get_container(pk: int) -> ContainerEntity:
    """
    Get a container by its primary key.

    Args:
        pk: The primary key of the container.

    Returns:
        The container with the given primary key.

    TODO: should this use with_publishing_relations as in components?
    """
    return ContainerEntity.objects.get(pk=pk)


def get_defined_list_for_container_version(
    container_version: ContainerEntityVersion,
) -> QuerySet[EntityListRow]:
    """
    Get the user-defined members of a container version.

    Args:
        container_version: The container version to get the members of.

    Returns:
        The members of the container version.
    """
    return container_version.defined_list.entitylistrow_set.all()


def get_initial_list_for_container_version(
    container_version: ContainerEntityVersion,
) -> QuerySet[EntityListRow]:
    """
    Get the initial members of a container version.

    Args:
        container_version: The container version to get the initial members of.

    Returns:
        The initial members of the container version.
    """
    return container_version.initial_list.entitylistrow_set.all()


def get_frozen_list_for_container_version(
    container_version: ContainerEntityVersion,
) -> QuerySet[EntityListRow]:
    """
    Get the frozen members of a container version.

    Args:
        container_version: The container version to get the frozen members of.

    Returns:
        The frozen members of the container version.
    """
    return container_version.frozen_list.entitylistrow_set.all()
