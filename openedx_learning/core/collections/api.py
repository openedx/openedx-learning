"""
API to manipulate Collections.

This API sacrifices some power in order to try to keep things simpler. For
instance, ``add_to_collection`` and ``remove_from_collection`` each create a
new CollectionChangeSet when they're invoked. The data model supports having

"""
from __future__ import annotations

from datetime import datetime, timezone

from django.db.models import F, QuerySet
from django.db.transaction import atomic

from .models import (
    Collection, CollectionPublishableEntity, CollectionChangeSet,
    AddToCollection, RemoveFromCollection, PublishEntity,
)


def create_collection(
    learning_package_id: int,
    key: str,
    title: str,
    pub_entities_qset: QuerySet | None = None,
    created: datetime | None = None,
    created_by: int | None = None,
) -> Collection:
    """
    Create a Collection and populate with a QuerySet of PublishableEntity.
    """
    if not created:
        created = datetime.now(tz=timezone.utc)

    with atomic():
        collection = Collection(
            learning_package_id=learning_package_id,
            key=key,
            title=title,
            created=created,
            created_by=created_by,
        )
        collection.full_clean()
        collection.save()

        # add_to_collection is what creates our initial CollectionChangeSet, so
        # we always call it, even if we're just creating an empty Collection.
        if pub_entities_qset is None:
            pub_entities_qset = PublishEntity.objects.none

        add_to_collection(collection.id, pub_entities_qset, created=created)

    return collection


def get_collection(collection_id: int) -> Collection:
    pass


def add_to_collection(
    collection_id: int,
    pub_entities_qset: QuerySet,
    created: datetime | None = None
)-> CollectionChangeSet:
    last_change_set = CollectionChangeSet.objects \
                            .filter(collection_id=collection_id) \
                            .order_by('-version_num') \
                            .first()
    if last_change_set:
        next_version_num = last_change_set.version_num + 1
    else:
        next_version_num = 1

    change_set = CollectionChangeSet.objects.create(
        collection_id=collection_id,
        version_num=next_version_num,
        created=created,
    )

    # Add the joins so we can efficiently query what the published versions are.
    qset = pub_entities_qset.select_related('published', 'published__version')
    adds = (
        AddToCollection(
            change_set=change_set,
            entity=pub_ent,
            published_version=pub_ent.published.version,
        )
        for pub_ent in qset.all()
    )
    # bulk_create will cast ``adds`` into a list and fully evaluate it.
    # This will likely be okay to start, and if Collections stay in the
    # hundreds. When it gets bigger, we might want to switch to
    # something fancier that only reads in chunks.
    #
    # We don't need to use atomic() here because bulk_create already works
    # atomically. If we got fancier with processing these in chunks, we'd need
    # to wrap it in an atomic() context.
    AddToCollection.objects.bulk_create(adds)

    return change_set


def remove_from_collection(collection_id: int, pub_entities_qset: QuerySet) -> CollectionChangeSet:
    pass

