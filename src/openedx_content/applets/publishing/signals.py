"""
Low-level events/signals emitted by openedx_content
"""

from attrs import define
from openedx_events.tooling import OpenEdxPublicSignal  # type: ignore[import-untyped]

from .models.learning_package import LearningPackage
from .models.publishable_entity import PublishableEntity

# Public API available via openedx_content.api
__all__ = [
    "LearningPackageEventData",
    "UserAttributionEventData",
    "ChangeLogRecordData",
    "DraftChangeLogEventData",
    "LEARNING_PACKAGE_ENTITIES_CHANGED",
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
    """
    The old version_num of this entity (not the PublishableEntityVersion ID).
    This is None if the entity is newly created.
    """

    new_version: int | None
    """
    The new version_num of this entity (not the PublishableEntityVersion ID).
    This is None if the entity is now deleted.
    """

    # Future: direct? https://github.com/openedx/openedx-core/pull/539


@define
class DraftChangeLogEventData:
    """Summary of a `DraftChangeLog`"""

    draft_change_log_id: int
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

This is emitted for when the first version of an entity is **created**, when a
new version of an entity is created (i.e. an entity is **modified**), when an
entity is **reverted** to an old version, or when an entity is **deleted**.
(All referring to the draft version of the entity.) The ``old_version`` and
``new_version`` fields can be used to distinguish among these cases.

This is a low-level batch event. It does not have any course or library context
information available. It does not distinguish between Containers, Components,
or other entity types.

Collections and tags are not `PublishableEntity`-based, so do not participate in
this event.

⏳ This **batch** event is emitted **synchronously**. Handlers that do anything
per-entity or that is possibly slow should dispatch an asynchronous task for
processing the event.
"""
