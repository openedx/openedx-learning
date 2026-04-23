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
    "LEARNING_PACKAGE_CREATED",
    "LEARNING_PACKAGE_UPDATED",
    "LEARNING_PACKAGE_DELETED",
    "ENTITIES_DRAFT_CHANGED",
    "ENTITIES_PUBLISHED",
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


LEARNING_PACKAGE_CREATED = OpenEdxPublicSignal(
    event_type="org.openedx.content.publishing.lp_created.v1",
    data={
        "learning_package": LearningPackageEventData,
    },
)
"""
A new ``LearningPackage`` has been created.

This is emitted exactly once per ``LearningPackage``, after the row is inserted
in the database. This is a low-level event. It's most likely that the Learning
Package is still being prepared/populated, and any necessary relationships,
entities, metadata, or other data may not yet exist at the time this event is
emitted.

💾 This event is only emitted after the enclosing database transaction has
been committed. If the transaction is rolled back, no event is emitted.

⏳ This event is emitted synchronously.
"""


LEARNING_PACKAGE_UPDATED = OpenEdxPublicSignal(
    event_type="org.openedx.content.publishing.lp_updated.v1",
    data={
        "learning_package": LearningPackageEventData,
    },
)
"""
A ``LearningPackage``'s own metadata (key, title, and/or description) has been
changed.

This is emitted only when the ``update_learning_package`` API is called, with at
least one field change that actually modifies the row.

This event covers changes to the ``LearningPackage`` row itself (its ``key``,
``title``, and ``description``). Changes to the content inside the package
(entities, versions, drafts, publishes) are covered by
``ENTITIES_DRAFT_CHANGED`` and ``ENTITIES_PUBLISHED`` instead.

The ``learning_package`` payload reflects the ``id`` and the post-update
``title`` of the package.

💾 This event is only emitted after the enclosing database transaction has
been committed. If the transaction is rolled back, no event is emitted.

⏳ This event is emitted synchronously.
"""


LEARNING_PACKAGE_DELETED = OpenEdxPublicSignal(
    event_type="org.openedx.content.publishing.lp_deleted.v1",
    data={
        "learning_package": LearningPackageEventData,
    },
)
"""
A ``LearningPackage`` has been deleted.

This is emitted exactly once per ``LearningPackage``, after the row has been
removed from the database. It is emitted regardless of how the row was deleted
(via a direct ORM ``.delete()`` call, via the Django admin, or as part of a
``QuerySet.delete()``), because it is fired by a Django ``post_delete`` signal
on the ``LearningPackage`` model.

Note: at the time this event is emitted, the ``LearningPackage`` and all of
its related content (entities, versions, drafts, publishes, etc.) have already
been removed from the database. Handlers cannot look up the learning package
by ID — they only get the ``id`` and ``title`` that are captured in the
``LearningPackageEventData`` payload.

🗑️ Unlike other ``publishing`` events, the effects of this deletion are
completely irreversible and the LearningPackage cannot be restored/un-deleted.

💾 This event is only emitted after the enclosing database transaction has
been committed. If the transaction is rolled back, no event is emitted.

⏳ This event is emitted synchronously.
"""


ENTITIES_DRAFT_CHANGED = OpenEdxPublicSignal(
    event_type="org.openedx.content.publishing.entities_draft_changed.v1",
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

💾 This event is only emitted after the enclosing database transaction has
been committed. If the transaction is rolled back, no event is emitted.

⏳ This **batch** event is emitted **synchronously**. Handlers that do anything
per-entity or that is possibly slow should dispatch an asynchronous task for
processing the event.
"""


ENTITIES_PUBLISHED = OpenEdxPublicSignal(
    event_type="org.openedx.content.publishing.entities_published.v1",
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

💾 This event is only emitted after the enclosing database transaction has
been committed. If the transaction is rolled back, no event is emitted.

⏳ This **batch** event is emitted **synchronously**. Handlers that do anything
per-entity or that is possibly slow should dispatch an asynchronous task for
processing the event.
"""
