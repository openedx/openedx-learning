"""
API to manipulate Collections.
"""
from __future__ import annotations

from datetime import datetime, timezone

from django.db.models import F, QuerySet
from django.db.transaction import atomic

from ..publishing.models import PublishableEntity
from .models import (
    Collection, CollectionPublishableEntity, ChangeSet,
    AddEntity, RemoveEntity, UpdateEntities,
)
from ..publishing.signals import PUBLISHED_PRE_COMMIT


def create_collection(
    learning_package_id: int,
    key: str,
    title: str,
    pub_entities_qset: QuerySet = PublishableEntity.objects.none, # default to empty qset
    created: datetime | None = None,
    created_by_id: int | None = None,
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
            created_by_id=created_by_id,
        )
        collection.full_clean()
        collection.save()

        # add_to_collection is what creates our initial CollectionChangeSet, so
        # we always call it, even if we're just creating an empty Collection.
        add_to_collection(collection.id, pub_entities_qset, created=created)

    return collection

def get_collection(collection_id: int) -> Collection:
    """
    Get a Collection by ID.
    """
    return Collection.objects.get(id=collection_id)

def get_collections_matching_entities(entity_ids_qs: QuerySet) -> QuerySet:
    """
    Get a QuerySet of Collections that have any of these PublishableEntities.
    """
    return Collection.objects.filter(publishable_entities__in=entity_ids_qs).distinct()

def get_last_change_set(collection_id: int) -> ChangeSet | None:
    """
    Get the most recent ChangeSet for this Collection.

    This may return None if there is no matching ChangeSet (i.e. this is a newly
    created Collection).
    """
    return ChangeSet.objects \
                    .filter(collection_id=collection_id) \
                    .order_by('-version_num') \
                    .first()

def get_next_version_num(collection_id: int) -> int:
    last_change_set = get_last_change_set(collection_id=collection_id)
    return last_change_set.version_num + 1 if last_change_set else 1


def update_collection_with_publish_log(collection_id: int, publish_log) -> ChangeSet:
    change_set = create_next_change_set(collection_id, publish_log.published_at)
    UpdateEntities.objects.create(change_set=change_set, publish_log=publish_log)
    return change_set


def create_next_change_set(collection_id: int, created: datetime | None) -> ChangeSet:
    return ChangeSet.objects.create(
        collection_id=collection_id,
        version_num=get_next_version_num(collection_id),
        created=created,
    )

def create_update_entities():
    pass



def add_to_collection(
    collection_id: int,
    pub_entities_qset: QuerySet,
    created: datetime | None = None
)-> ChangeSet:
    """
    Add a QuerySet of PublishableEntities to a Collection.
    """
    next_version_num = get_next_version_num(collection_id)
    with atomic():
        change_set = ChangeSet.objects.create(
            collection_id=collection_id,
            version_num=next_version_num,
            created=created,
        )

        # Add the joins so we can efficiently query the published versions.
        qset = pub_entities_qset.select_related('published', 'published__version')

        # We're going to build our relationship models into big lists and then
        # use bulk_create on them in order to reduce the number of queries
        # required for this as the size of Collections grow. This should be
        # reasonable for up to hundreds of PublishableEntities, but we may have
        # to look into more complex chunking and async processing if we go
        # beyond that.
        change_set_adds = []
        collection_pub_entities = []
        for pub_ent in qset.all():
            if hasattr(pub_ent, 'published'):
                published_version = pub_ent.published.version
            else:
                published_version = None

            # These will be associated with the ChangeSet for history tracking.
            change_set_adds.append(
                AddEntity(
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

        AddEntity.objects.bulk_create(change_set_adds)
        CollectionPublishableEntity.objects.bulk_create(collection_pub_entities)

    return change_set


def remove_from_collection(
    collection_id: int,
    pub_entities_qset: QuerySet,
    created: datetime | None = None
) -> ChangeSet:
    next_version_num = get_next_version_num(collection_id)

    with atomic():
        change_set = ChangeSet.objects.create(
            collection_id=collection_id,
            version_num=next_version_num,
            created=created,
        )
