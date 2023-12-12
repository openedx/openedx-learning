"""
API to manipulate Collections.

This API sacrifices some power in order to try to keep things simpler. For
instance, ``add_to_collection`` and ``remove_from_collection`` each create a
new CollectionChangeSet when they're invoked. The data model supports doing
multiple operations at the same time–in theory you could publish some entities,
add some entities, and delete them in the same operation. But then we could
bring

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
    """
    Get a Collection by ID.
    """
    return Collection.objects.get(id=collection_id)


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

    with atomic():
        change_set = CollectionChangeSet.objects.create(
            collection_id=collection_id,
            version_num=next_version_num,
            created=created,
        )

        # Add the joins so we can efficiently query what the published versions are.
        qset = pub_entities_qset.select_related('published', 'published__version')

        # We're going to build our relationship models into big lists and then use
        # bulk_create on them in order to reduce the number of queries required for
        # this as the size of Collections grow. This should be reasonable for up to
        # hundreds of PublishableEntities, but we may have to look into more complex
        # chunking and async processing if we go beyond that.
        change_set_adds = []
        collection_pub_entities = []
        for pub_ent in qset.all():
            if hasattr(pub_ent, 'published'):
                published_version = pub_ent.published
            else:
                published_version = None

            # These will be associated with the ChangeSet for history tracking.
            change_set_adds.append(
                AddToCollection(
                    change_set=change_set,
                    entity=pub_ent,
                    published_version=published_version,
                )
            )

            # These are the direct Collection <-> PublishableEntity M2M mappings
            collection_pub_entities.append(
                CollectionPublishableEntity(
                    collection_id=collection_id,
                    entity_id=pub_ent.id,
                )
            )

        AddToCollection.objects.bulk_create(change_set_adds)
        CollectionPublishableEntity.objects.bulk_create(collection_pub_entities)

    return change_set


def remove_from_collection(collection_id: int, pub_entities_qset: QuerySet) -> CollectionChangeSet:
    pass

