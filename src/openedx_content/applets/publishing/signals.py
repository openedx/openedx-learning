"""
Low-level events/signals emitted by openedx_content
"""

from attrs import define
from openedx_events.tooling import OpenEdxPublicSignal  # type: ignore[import-untyped]

from .models.learning_package import LearningPackage


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
class DraftChangeLogEventData:
    """Summary of a `DraftChangeLog`"""
    draft_change_log_id: int


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

This is a low-level batch event. It does not have any course or library context
information available. It does not distinguish between Containers, Components,
or other entity types.

Collections and tags are not `PublishableEntity`-based, so do not participate in
this event.
"""
