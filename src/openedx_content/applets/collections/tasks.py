"""Celery tasks for the collections applet."""

import logging
from collections import defaultdict

from celery import shared_task  # type: ignore[import]

from ..publishing.models import PublishableEntity
from .models import Collection, CollectionPublishableEntity
from .signals import (
    LEARNING_PACKAGE_COLLECTION_CHANGED,
    CollectionChangeData,
    LearningPackageEventData,
    UserAttributionEventData,
)

logger = logging.getLogger(__name__)


@shared_task
def emit_collections_changed_for_deleted_entities_task(
    entity_ids: list[int],
    user_id: int | None,
) -> int:
    """
    Emit LEARNING_PACKAGE_COLLECTION_CHANGED for each collection that contains
    any of the given (now-deleted) entities, listing them as entities_removed.

    Triggered by LEARNING_PACKAGE_ENTITIES_CHANGED when entity drafts are deleted.
    """
    affected_cpes = (
        CollectionPublishableEntity.objects
        .filter(entity_id__in=entity_ids)
        .select_related("collection__learning_package")
        .order_by("collection_id", "entity_id")
    )

    collection_map: dict[int, Collection] = {}
    entity_map: dict[int, list[PublishableEntity.ID]] = defaultdict(list)
    for cpe in affected_cpes:
        collection_map[cpe.collection_id] = cpe.collection
        entity_map[cpe.collection_id].append(cpe.entity_id)

    emitted_events = 0
    for collection_id, collection in collection_map.items():
        # .. event_implemented_name: LEARNING_PACKAGE_COLLECTION_CHANGED
        # .. event_type: org.openedx.content.collections.lp_collection_changed.v1
        LEARNING_PACKAGE_COLLECTION_CHANGED.send_event(
            time=collection.modified,
            learning_package=LearningPackageEventData(
                id=collection.learning_package.id,
                title=collection.learning_package.title,
            ),
            changed_by=UserAttributionEventData(user_id=user_id),
            change=CollectionChangeData(
                collection_id=collection.id,
                collection_code=collection.collection_code,
                entities_removed=entity_map[collection_id],
            ),
        )
        emitted_events += 1

    logger.info(
        "Entities deleted (ids: %s): emitted LEARNING_PACKAGE_COLLECTION_CHANGED for %s collections.",
        entity_ids,
        emitted_events,
    )
    return emitted_events
