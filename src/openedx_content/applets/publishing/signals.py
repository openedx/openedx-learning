"""
Low-level events/signals emitted by openedx_content
"""

from attrs import define
from openedx_events.tooling import OpenEdxPublicSignal  # type: ignore[import-untyped]

from .models.learning_package import LearningPackage
from .models.publishable_entity import PublishableEntity

# Public API available via openedx_content.api
__all__ = [
    # All event data structures should end with "...Data":
    "LearningPackageEventData",
    "UserAttributionEventData",
    "ChangeLogRecordData",
    "DraftChangeLogEventData",
    "PublishLogEventData",
    # All events:
    "LEARNING_PACKAGE_ENTITIES_CHANGED",
    "LEARNING_PACKAGE_ENTITIES_PUBLISHED",
]


@define
class LearningPackageEventData:
    """Identifies which learning package an event is associated with."""

    id: LearningPackage.ID
    title: str  # Since 'id' is not easily human-understandable, we include the title too


@define
class UserAttributionEventData:
    """Identifies which user triggered the event."""

    user_id: int | None


@define
class ChangeLogRecordData:
    """A single change that was made to a PublishableEntity"""

    entity_id: PublishableEntity.ID

    old_version: int | None
    """The old version number of this entity. None if newly-created or un-deleted."""
    old_version_id: int | None
    """
    The old version of this entity (the PublishableEntityVersion ID).
    This is None if the entity is newly created (or un-deleted).
    """

    new_version: int | None
    """The old version number of this entity. None if newly-created or un-deleted."""
    new_version_id: int | None
    """
    The new version of this entity (the PublishableEntityVersion ID.
    This is None if the entity is now deleted.
    """

    direct: bool | None = None
    """
    Did the user chose to directly publish this specific thing, or was it auto-published because it's a dependency?
    (if applicable/known)
    """


@define
class DraftChangeLogEventData:
    """Summary of a `DraftChangeLog` for event purposes"""

    draft_change_log_id: int
    changes: list[ChangeLogRecordData]


@define
class PublishLogEventData:
    """Summary of a `PublishLog` for event purposes"""

    publish_log_id: int
    changes: list[ChangeLogRecordData]


LEARNING_PACKAGE_ENTITIES_CHANGED = OpenEdxPublicSignal(
    event_type="org.openedx.content.publishing.lp_entities_changed.v1",
    data={
        "learning_package": LearningPackageEventData,
        "changed_by": UserAttributionEventData,
        "change_log": DraftChangeLogEventData,
    },
)
"""
The draft version of one or more entities in a `LearningPackage` has changed.

This is emitted when the first version of an entity is **created**, when a new
version of an entity is created (i.e. an entity is **modified**), when an entity
is **reverted** to an old version, when **a dependency is modified**, or when an
entity is **deleted**. (All referring to the draft version of the entity.)

The ``old_version`` and ``new_version`` fields can be used to distinguish among
these cases (e.g. ``old_version`` is ``None`` for newly-created entities).

This is a low-level batch event. It does not have any course or library context
information available. It does not distinguish between Containers, Components,
or other entity types.

Collections and tags are not `PublishableEntity`-based, so do not participate in
this event.

💾 This event is only emitted after any transaction has been committed.

⏳ This **batch** event is emitted **synchronously**. Handlers that do anything
per-entity or that is possibly slow should dispatch an asynchronous task for
processing the event.
"""


LEARNING_PACKAGE_ENTITIES_PUBLISHED = OpenEdxPublicSignal(
    event_type="org.openedx.content.publishing.lp_entities_published.v1",
    data={
        "learning_package": LearningPackageEventData,
        "changed_by": UserAttributionEventData,
        "change_log": PublishLogEventData,
    },
)
"""
The published version of one or more entities in a `LearningPackage` has
changed.

This is emitted when **a newly-created entity is first published**, when
**changes to an existing entity** are published, when **changes to a
dependency** (or a dependency's dependencies...) are published, when a published
entity is **reverted** to a previous version, or when **a "delete" is
published**.

The ``old_version`` and ``new_version`` fields can be used to distinguish among
these cases (e.g. ``old_version`` is ``None`` for newly-created entities).

This is a low-level batch event. It does not have any course or library context
information available. It does not distinguish between Containers, Components,
or other entity types.

Collections and tags are not `PublishableEntity`-based, so do not participate in
this event.

💾 This event is only emitted after any transaction has been committed.

⏳ This **batch** event is emitted **synchronously**. Handlers that do anything
per-entity or that is possibly slow should dispatch an asynchronous task for
processing the event.
"""
