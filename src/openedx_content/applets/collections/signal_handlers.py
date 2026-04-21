"""Signal handlers for collections-related updates."""

from functools import partial

from django.db import transaction
from django.dispatch import receiver

from ..publishing.signals import LEARNING_PACKAGE_ENTITIES_CHANGED, DraftChangeLogEventData, UserAttributionEventData
from .tasks import emit_collections_changed_for_deleted_entities_task


@receiver(LEARNING_PACKAGE_ENTITIES_CHANGED)
def on_entities_changed(
    change_log: DraftChangeLogEventData,
    changed_by: UserAttributionEventData,
    **kwargs,
):
    """
    When entity drafts are deleted, update all affected collections.

    Finds all deleted entities (new_version=None) from the change log and
    dispatches a task to emit LEARNING_PACKAGE_COLLECTION_CHANGED for any
    collections that contain those entities.
    """
    deleted_entity_ids = [record.entity_id for record in change_log.changes if record.new_version is None]

    if not deleted_entity_ids:
        return

    transaction.on_commit(
        partial(
            emit_collections_changed_for_deleted_entities_task.delay,
            entity_ids=deleted_entity_ids,
            user_id=changed_by.user_id,
        )
    )
