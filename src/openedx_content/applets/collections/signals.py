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
    "LEARNING_PACKAGE_COLLECTION_CHANGED",
]


@define
class CollectionChangeData:
    """Summary of changes to a collection, for event purposes"""

    collection_id: int
    collection_code: str
    created: bool = False
    """The collection is newly-created, or un-deleted. Some entities may be added simultaneously."""
    modified: bool = False
    """The collection's title/description has changed. Does not indicate whether or not entities were added/removed."""
    deleted: bool = False
    """
    The collection has been deleted. When this is true, the entities_removed list will have all entity IDs.
    Does not distinguish between "soft" and "hard" deletion.
    """
    entities_added: list[PublishableEntity.ID] = field(factory=list)
    entities_removed: list[PublishableEntity.ID] = field(factory=list)


LEARNING_PACKAGE_COLLECTION_CHANGED = OpenEdxPublicSignal(
    event_type="org.openedx.content.collections.lp_collection_changed.v1",
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

⏳ This **batch** event is emitted **synchronously**. Handlers that do anything
per-entity or that is possibly slow should dispatch an asynchronous task for
processing the event.
"""
# TODO: also emit an ENTITIES_META_CHANGED for this and tag changes?
