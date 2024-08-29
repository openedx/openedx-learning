"""
Collections API (warning: UNSTABLE, in progress API)
"""
from __future__ import annotations

from django.db.models import QuerySet
from django.db.transaction import atomic
from django.utils import timezone

from ..publishing import api as publishing_api
from ..publishing.models import PublishableEntity
from .models import Collection, CollectionPublishableEntity

# The public API that will be re-exported by openedx_learning.apps.authoring.api
# is listed in the __all__ entries below. Internal helper functions that are
# private to this module should start with an underscore. If a function does not
# start with an underscore AND it is not in __all__, that function is considered
# to be callable only by other apps in the authoring package.
__all__ = [
    "add_to_collections",
    "create_collection",
    "get_collection",
    "get_collections",
    "get_entity_collections",
    "remove_from_collections",
    "update_collection",
]


def create_collection(
    learning_package_id: int,
    title: str,
    created_by: int | None,
    description: str = "",
    entities_qset: QuerySet[PublishableEntity] = PublishableEntity.objects.none(),  # default to empty set,
) -> Collection:
    """
    Create a new Collection
    """

    with atomic():
        collection = Collection.objects.create(
            learning_package_id=learning_package_id,
            title=title,
            created_by_id=created_by,
            description=description,
        )

        added = add_to_collections(
            Collection.objects.filter(id=collection.id),
            entities_qset,
            created_by,
        )
        if added:
            collection.refresh_from_db()  # fetch updated modified date

    return collection


def get_collection(collection_id: int) -> Collection:
    """
    Get a Collection by ID
    """
    return Collection.objects.get(id=collection_id)


def update_collection(
    collection_id: int,
    title: str | None = None,
    description: str | None = None,
) -> Collection:
    """
    Update a Collection
    """
    collection = Collection.objects.get(id=collection_id)

    # If no changes were requested, there's nothing to update, so just return
    # the Collection as-is
    if all(field is None for field in [title, description]):
        return collection

    if title is not None:
        collection.title = title
    if description is not None:
        collection.description = description

    collection.save()
    return collection


def add_to_collections(
    collections_qset: QuerySet[Collection],
    entities_qset: QuerySet[PublishableEntity],
    created_by: int | None = None,
) -> int:
    """
    Adds a QuerySet of PublishableEntities to a QuerySet of Collections.

    Records are created in bulk, and so integrity errors are deliberately ignored: they indicate that the entity(s)
    have already been added to the collection(s).

    Returns the number of entities added (including any that already exist).
    """
    collection_entities = []
    entity_ids = entities_qset.values_list("pk", flat=True)
    collection_ids = collections_qset.values_list("pk", flat=True)

    for collection_id in collection_ids:
        for entity_id in entity_ids:
            collection_entities.append(
                CollectionPublishableEntity(
                    collection_id=collection_id,
                    entity_id=entity_id,
                    created_by_id=created_by,
                )
            )

    created = []
    if collection_entities:
        created = CollectionPublishableEntity.objects.bulk_create(
            collection_entities,
            ignore_conflicts=True,
        )

        # Update the modified date for all the provided Collections.
        # (Ignoring conflicts means we don't know which ones were modified.)
        collections_qset.update(modified=timezone.now())

    return len(created)


def remove_from_collections(
    collections_qset: QuerySet[Collection],
    entities_qset: QuerySet[PublishableEntity],
) -> int:
    """
    Removes a QuerySet of PublishableEntities from a QuerySet of Collections.

    PublishableEntities are deleted from each Collection, in bulk.

    Collections which had entities removed are marked with modified=now().

    Returns the total number of entities deleted.
    """
    total_deleted = 0
    entity_ids = entities_qset.values_list("pk", flat=True)
    collection_ids = collections_qset.values_list("pk", flat=True)
    modified_collection_ids = []

    for collection_id in collection_ids:
        num_deleted, _ = CollectionPublishableEntity.objects.filter(
            collection_id=collection_id,
            entity__in=entity_ids,
        ).delete()

        if num_deleted:
            modified_collection_ids.append(collection_id)

        total_deleted += num_deleted

    # Update the modified date for the affected Collections
    Collection.objects.filter(id__in=modified_collection_ids).update(modified=timezone.now())

    return total_deleted


def get_entity_collections(learning_package_id: int, entity_key: str) -> QuerySet[Collection]:
    """
    Get all collections in the given learning package which contain this entity.

    Only enabled collections are returned.
    """
    entity = publishing_api.get_publishable_entity_by_key(
        learning_package_id,
        key=entity_key,
    )
    return entity.collections.filter(enabled=True).order_by("pk")


def get_collections(learning_package_id: int, enabled: bool | None = True) -> QuerySet[Collection]:
    """
    Get all collections for a given learning package

    Only enabled collections are returned
    """
    qs = Collection.objects.filter(learning_package_id=learning_package_id)
    if enabled is not None:
        qs = qs.filter(enabled=enabled)
    return qs.select_related("learning_package").order_by('pk')
