"""Signal handlers for collections-related updates."""

from functools import partial

from django.db import transaction
from django.dispatch import receiver

from ..publishing.signals import ENTITIES_DRAFT_CHANGED, DraftChangeLogEventData, UserAttributionEventData
from .tasks import emit_collections_changed_for_entity_changes_task


@receiver(ENTITIES_DRAFT_CHANGED)
def on_entities_changed(
    change_log: DraftChangeLogEventData,
    changed_by: UserAttributionEventData,
    **kwargs,
):
    """
    When entity drafts are deleted or restored, notify affected collections.

    Dispatches a task to emit COLLECTION_CHANGED for any
    collections that contain the changed entities.
    """
    removed_entity_ids = [record.entity_id for record in change_log.changes if record.new_version_id is None]
    # old_version_id=None covers both brand-new entities and restored soft-deletes; we can't distinguish
    # them here without a DB query. The task is a no-op for new entities (not yet in any collection).
    # TODO: if ChangeLogRecordData gains a 'restored' flag, filter to only restored entities here.
    # (Newly-created entities cannot be part of collections yet, so we only care about entities that
    # were previously in collections, then deleted and then restored.)
    added_entity_ids = [
        record.entity_id
        for record in change_log.changes
        if record.old_version_id is None and record.new_version_id is not None
    ]

    if not removed_entity_ids and not added_entity_ids:
        return

    transaction.on_commit(
        partial(
            emit_collections_changed_for_entity_changes_task.delay,
            removed_entity_ids=removed_entity_ids,
            added_entity_ids=added_entity_ids,
            user_id=changed_by.user_id,
        )
    )
