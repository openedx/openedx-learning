"""
Collections API (warning: UNSTABLE, in progress API)
"""

from __future__ import annotations

from datetime import datetime, timezone
from functools import partial

from django.core.exceptions import ValidationError
from django.db.models import QuerySet
from django.db.transaction import on_commit

from ..publishing import api as publishing_api
from ..publishing.models import PublishableEntity
from . import signals
from .models import Collection, CollectionPublishableEntity, LearningPackage

# The public API that will be re-exported by openedx_content.api
# is listed in the __all__ entries below. Internal helper functions that are
# private to this module should start with an underscore. If a function does not
# start with an underscore AND it is not in __all__, that function is considered
# to be callable only by other apps in the authoring package.
__all__ = [
    "add_to_collection",
    "create_collection",
    "delete_collection",
    "get_collection",
    "get_collections",
    "get_entity_collections",
    "get_collection_entities",
    "remove_from_collection",
    "restore_collection",
    "update_collection",
    "set_collections",
]


def _queue_change_event(
    collection: Collection,
    *,
    created: bool = False,
    metadata_modified: bool = False,
    deleted: bool = False,
    entities_added: list[PublishableEntity.ID] | None = None,
    entities_removed: list[PublishableEntity.ID] | None = None,
    user_id: int | None = None,
) -> None:
    """Helper for emitting the event when a collection has changed."""

    learning_package_id = collection.learning_package.id
    learning_package_title = collection.learning_package.title

    # Send out an event immediately after this database transaction commits.
    on_commit(partial(
        signals.COLLECTION_CHANGED.send_event,
        time=collection.modified,
        learning_package=signals.LearningPackageEventData(id=learning_package_id, title=learning_package_title),
        changed_by=signals.UserAttributionEventData(user_id=user_id),
        change=signals.CollectionChangeData(
            collection_id=collection.id,
            collection_code=collection.collection_code,
            created=created,
            metadata_modified=metadata_modified,
            deleted=deleted,
            entities_added=entities_added or [],
            entities_removed=entities_removed or [],
        ),
    ))


def create_collection(
    learning_package_id: LearningPackage.ID,
    collection_code: str,
    *,
    title: str,
    created_by: int | None,
    description: str = "",
    enabled: bool = True,
) -> Collection:
    """
    Create a new Collection
    """
    collection = Collection(
        learning_package_id=learning_package_id,
        collection_code=collection_code,
        title=title,
        created_by_id=created_by,
        description=description,
        enabled=enabled,
    )
    collection.full_clean()
    collection.save()
    if enabled:
        _queue_change_event(collection, created=True, user_id=created_by)
    return collection


def get_collection(learning_package_id: LearningPackage.ID, collection_code: str) -> Collection:
    """
    Get a Collection by ID
    """
    return Collection.objects.get_by_code(learning_package_id, collection_code)


def update_collection(
    learning_package_id: LearningPackage.ID,
    collection_code: str,
    *,
    title: str | None = None,
    description: str | None = None,
) -> Collection:
    """
    Update a Collection identified by the learning_package_id + collection_code.
    """
    collection = get_collection(learning_package_id, collection_code)

    # If no changes were requested, there's nothing to update, so just return
    # the Collection as-is
    if all(field is None for field in [title, description]):
        return collection

    if title is not None:
        collection.title = title
    if description is not None:
        collection.description = description

    collection.save()
    _queue_change_event(collection, metadata_modified=True)
    return collection


def delete_collection(
    learning_package_id: LearningPackage.ID,
    collection_code: str,
    *,
    hard_delete=False,
) -> Collection:
    """
    Disables or deletes a collection identified by the given learning_package + collection_code.

    By default (hard_delete=False), the collection is "soft deleted", i.e disabled.
    Soft-deleted collections can be re-enabled using restore_collection.
    """
    collection = get_collection(learning_package_id, collection_code)
    entities_removed = list(collection.entities.order_by("id").values_list("id", flat=True))
    was_already_soft_deleted = not collection.enabled

    if hard_delete:
        collection.modified = datetime.now(tz=timezone.utc)  # For the event timestamp; won't get saved to the DB
        if not was_already_soft_deleted:  # Send the deleted event unless this was already soft deleted.
            _queue_change_event(collection, deleted=True, entities_removed=entities_removed)
        # Delete after enqueing the event:
        collection.delete()
    elif not was_already_soft_deleted:
        # Soft delete:
        collection.enabled = False
        collection.save()
        _queue_change_event(collection, deleted=True, entities_removed=entities_removed)
    return collection


def restore_collection(
    learning_package_id: LearningPackage.ID,
    collection_code: str,
) -> Collection:
    """
    Undo a "soft delete" by re-enabling a Collection.
    """
    collection = get_collection(learning_package_id, collection_code)
    entities_added = list(collection.entities.order_by("id").values_list("id", flat=True))

    collection.enabled = True
    collection.save()
    _queue_change_event(collection, created=True, entities_added=entities_added)
    return collection


def add_to_collection(
    learning_package_id: LearningPackage.ID,
    collection_code: str,
    entities_qset: QuerySet[PublishableEntity],
    created_by: int | None = None,
) -> Collection:
    """
    Adds a QuerySet of PublishableEntities to a Collection.

    These Entities must belong to the same LearningPackage as the Collection, or a ValidationError will be raised.

    PublishableEntities already in the Collection are silently ignored.

    The Collection object's modified date is updated.

    Returns the updated Collection object.
    """
    # Disallow adding entities outside the collection's learning package
    invalid_entity = entities_qset.exclude(learning_package_id=learning_package_id).first()
    if invalid_entity:
        raise ValidationError(
            f"Cannot add entity {invalid_entity.id} in learning package {invalid_entity.learning_package_id} "
            f"to collection {collection_code} in learning package {learning_package_id}."
        )

    collection = get_collection(learning_package_id, collection_code)
    existing_ids = set(collection.entities.values_list("id", flat=True))
    ids_to_add = entities_qset.values_list("id", flat=True)
    collection.entities.add(*ids_to_add, through_defaults={"created_by_id": created_by})
    collection.modified = datetime.now(tz=timezone.utc)
    collection.save()
    _queue_change_event(collection, entities_added=sorted(list(set(ids_to_add) - existing_ids)), user_id=created_by)

    return collection


def remove_from_collection(
    learning_package_id: LearningPackage.ID,
    collection_code: str,
    entities_qset: QuerySet[PublishableEntity],
) -> Collection:
    """
    Removes a QuerySet of PublishableEntities from a Collection.

    PublishableEntities are deleted (in bulk).

    The Collection's modified date is updated (even if nothing was removed).

    Returns the updated Collection.
    """
    collection = get_collection(learning_package_id, collection_code)

    ids_to_remove = list(entities_qset.values_list("id", flat=True))
    entities_removed = sorted(list(collection.entities.filter(id__in=ids_to_remove).values_list("id", flat=True)))
    collection.entities.remove(*ids_to_remove)
    collection.modified = datetime.now(tz=timezone.utc)
    collection.save()
    _queue_change_event(collection, entities_removed=entities_removed)

    return collection


def get_entity_collections(learning_package_id: LearningPackage.ID, entity_ref: str) -> QuerySet[Collection]:
    """
    Get all collections in the given learning package which contain this entity.

    Only enabled collections are returned.
    """
    entity = publishing_api.get_publishable_entity_by_ref(
        learning_package_id,
        entity_ref=entity_ref,
    )
    return entity.collections.filter(enabled=True).order_by("pk")


def get_collection_entities(
    learning_package_id: LearningPackage.ID,
    collection_code: str,
) -> QuerySet[PublishableEntity]:
    """
    Returns a QuerySet of PublishableEntities in a Collection.

    This is the same as `collection.entities.all()`
    """
    return PublishableEntity.objects.filter(
        learning_package_id=learning_package_id,
        collections__collection_code=collection_code,
    ).order_by("pk")


def get_collections(learning_package_id: LearningPackage.ID, enabled: bool | None = True) -> QuerySet[Collection]:
    """
    Get all collections for a given learning package

    Enabled collections are returned by default.
    """
    qs = Collection.objects.filter(learning_package_id=learning_package_id)
    if enabled is not None:
        qs = qs.filter(enabled=enabled)
    return qs.select_related("learning_package").order_by("pk")


def set_collections(
    publishable_entity: PublishableEntity,
    collection_qset: QuerySet[Collection],
    created_by: int | None = None,
) -> set[Collection]:
    """
    Set collections for a given publishable entity.

    These Collections must belong to the same LearningPackage as the PublishableEntity,
    or a ValidationError will be raised.

    Modified date of all collections related to entity is updated.

    Returns the updated collections.
    """
    # Disallow adding entities outside the collection's learning package
    if collection_qset.exclude(learning_package_id=publishable_entity.learning_package_id).count():
        raise ValidationError(
            "Collection entities must be from the same learning package as the collection.",
        )
    current_relations = CollectionPublishableEntity.objects.filter(entity=publishable_entity).select_related(
        "collection"
    )
    # Clear other collections for given entity and add only new collections from collection_qset
    removed_collections = set(r.collection for r in current_relations.exclude(collection__in=collection_qset))
    new_collections = set(collection_qset.exclude(id__in=current_relations.values_list("collection", flat=True)))
    # Triggers a m2m_changed signal
    publishable_entity.collections.set(
        objs=collection_qset,
        through_defaults={"created_by_id": created_by},
    )
    # Update modified date:
    affected_collections = removed_collections | new_collections
    Collection.objects.filter(id__in=[collection.id for collection in affected_collections]).update(
        modified=datetime.now(tz=timezone.utc)
    )

    # Emit one event per affected collection. Re-fetch with select_related so _queue_change_event
    # can read collection.learning_package without extra queries; the re-fetch also picks up the
    # updated modified timestamp from the bulk update above.
    removed_ids = {c.id for c in removed_collections}
    for collection in Collection.objects.filter(id__in=[c.id for c in affected_collections]).select_related(
        "learning_package"
    ):
        # TODO: test performance of this and potentially send these async if > 1 affected collection.
        if collection.id in removed_ids:
            _queue_change_event(collection, entities_removed=[publishable_entity.id], user_id=created_by)
        else:
            _queue_change_event(collection, entities_added=[publishable_entity.id], user_id=created_by)

    return affected_collections
