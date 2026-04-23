"""Celery tasks for the collections applet."""

import logging
from collections import defaultdict

from celery import shared_task  # type: ignore[import]

from ..publishing.models import PublishableEntity
from .models import Collection, CollectionPublishableEntity
from .signals import COLLECTION_CHANGED, CollectionChangeData, LearningPackageEventData, UserAttributionEventData

logger = logging.getLogger(__name__)


@shared_task
def emit_collections_changed_for_entity_changes_task(
    removed_entity_ids: list[int],
    added_entity_ids: list[int],
    user_id: int | None,
) -> int:
    """
    Emit COLLECTION_CHANGED for each collection affected by entity draft
    deletions or restorations.

    For each collection that contains any of the given entities, emits one event
    with entities_removed (for deletions) and/or entities_added (for
    restorations). A single event covers both if the same collection has
    entities in both lists.

    Triggered by ENTITIES_DRAFT_CHANGED. New entities (old_version_id=None,
    new_version_id is not None) that aren't in any collection result in a no-op.
    """
    all_entity_ids = list(set(removed_entity_ids) | set(added_entity_ids))
    if not all_entity_ids:
        return 0

    affected_cpes = (
        CollectionPublishableEntity.objects.filter(entity_id__in=all_entity_ids)
        .select_related("collection__learning_package")
        .order_by("collection_id", "entity_id")
    )

    collection_map: dict[int, Collection] = {}
    removed_map: dict[int, list[PublishableEntity.ID]] = defaultdict(list)
    added_map: dict[int, list[PublishableEntity.ID]] = defaultdict(list)
    removed_set = set(removed_entity_ids)
    added_set = set(added_entity_ids)

    for cpe in affected_cpes:
        collection_map[cpe.collection_id] = cpe.collection
        if cpe.entity_id in removed_set:
            removed_map[cpe.collection_id].append(cpe.entity_id)
        if cpe.entity_id in added_set:
            added_map[cpe.collection_id].append(cpe.entity_id)

    emitted_events = 0
    for collection_id, collection in collection_map.items():
        # .. event_implemented_name: COLLECTION_CHANGED
        # .. event_type: org.openedx.content.collections.collection_changed.v1
        COLLECTION_CHANGED.send_event(
            time=collection.modified,
            learning_package=LearningPackageEventData(
                id=collection.learning_package.id,
                title=collection.learning_package.title,
            ),
            changed_by=UserAttributionEventData(user_id=user_id),
            change=CollectionChangeData(
                collection_id=collection.id,
                collection_code=collection.collection_code,
                entities_removed=removed_map[collection_id],
                entities_added=added_map[collection_id],
            ),
        )
        emitted_events += 1

    if emitted_events:
        logger.info(
            "Entity draft changes (removed=%s, added=%s): emitted COLLECTION_CHANGED for %s collections.",
            removed_entity_ids,
            added_entity_ids,
            emitted_events,
        )
    return emitted_events
