"""
Low-level events/signals emitted by openedx_content
"""

from attrs import define, field
from openedx_events.tooling import OpenEdxPublicSignal  # type: ignore[import-untyped]

from ..publishing.models.publishable_entity import PublishableEntity
from ..publishing.signals import LearningPackageEventData, UserAttributionEventData

# Public API available via openedx_content.api
__all__ = [
    # All event data structures should end with "...Data":
    "CollectionChangeData",
    # All events:
    "COLLECTION_CHANGED",
]


@define
class CollectionChangeData:
    """Summary of changes to a collection, for event purposes"""

    collection_id: int
    collection_code: str
    created: bool = False
    """The collection is newly-created, or un-deleted. Some entities may be added simultaneously."""
    metadata_modified: bool = False
    """The collection's title/description has changed. Does not indicate whether or not entities were added/removed."""
    deleted: bool = False
    """
    The collection has been deleted. When this is true, the entities_removed list will have all entity IDs.
    Does not distinguish between "soft" and "hard" deletion.
    """
    entities_added: list[PublishableEntity.ID] = field(factory=list)
    entities_removed: list[PublishableEntity.ID] = field(factory=list)


COLLECTION_CHANGED = OpenEdxPublicSignal(
    event_type="org.openedx.content.collections.collection_changed.v1",
    data={
        "learning_package": LearningPackageEventData,
        "changed_by": UserAttributionEventData,
        "change": CollectionChangeData,
    },
)
"""
A ``Collection`` has been created, modified, or deleted, or its entities have
changed.

This is a low-level batch event. It does not have any course or library context
information available. It does not distinguish between Containers, Components,
or other entity types.

💾 This event is only emitted after any transaction has been committed.

⏳ This **batch** event is emitted **synchronously**. Handlers that do anything
per-entity or that is possibly slow should dispatch an asynchronous task for
processing the event.
"""

# Note: at present, the openedx_tagging code (in this repo) emits a
# CONTENT_OBJECT_ASSOCIATIONS_CHANGED event whenever an entity's tags change.
# But we do NOT emit the same event when an entity's collections change; rather
# we expect code in the platform to listen for COLLECTION_CHANGED and then
# re-emit '...ASSOCIATIONS_CHANGED' as needed.
# The reason we don't emit the '...ASSOCIATIONS_CHANGED' event here
# is simple: we know the entity IDs but not their opaque keys, and all of the
# code that listens for that event expects the entity's opaque keys.
# The tagging code can do it here because the `object_id` in the tagging models
# _is_ the opaque key ("lb:..."), but the collections code is too low-level to
# know about opaque keys of the entities. We don't even know which learning
# context (which content library) a given entity is in.
