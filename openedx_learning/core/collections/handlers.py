"""
Signal handlers for Collections.

This is to catch updates when things are published. The reason that we use
signals to do this kind of updating is because the ``publishing`` app exists at
a lower layer than the ``collections`` app, i.e. ``publishing`` should not know
that ``collections`` exists. If ``publishing`` updated Collections directly, it
would introduce a circular dependency.
"""
from django.db.transaction import atomic

from .api import (
    get_collections_matching_entities,
    update_collection_with_publish_log,
)


def update_collections_from_publish(sender, publish_log=None, **kwargs):
    """
    Update all Collections affected by the publish described by publish_log.
    """
    # Find all Collections that had at least one PublishableEntity that was
    # published in this PublishLog.
    affected_collections = get_collections_matching_entities(
        publish_log.records.values('entity__id')
    )
    with atomic():
        for collection in affected_collections:
            update_collection_with_publish_log(collection.id, publish_log)
