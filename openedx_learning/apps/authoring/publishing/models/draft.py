"""
Models relating to the creation and management of Draft information.
"""
from django.conf import settings
from django.db import models
from django.utils.translation import gettext_lazy as _

from openedx_learning.lib.fields import immutable_uuid_field, manual_date_time_field

from .learning_package import LearningPackage
from .publishable_entity import PublishableEntity, PublishableEntityVersion


class Draft(models.Model):
    """
    Find the active draft version of an entity (usually most recently created).

    This model mostly only exists to allow us to join against a bunch of
    PublishableEntity objects at once and get all their latest drafts. You might
    use this together with Published in order to see which Drafts haven't been
    published yet.

    A Draft entry should be created whenever a new PublishableEntityVersion is
    created. This means there are three possible states:

    1. No Draft entry for a PublishableEntity: This means a PublishableEntity
       was created, but no PublishableEntityVersion was ever made for it, so
       there was never a Draft version.
    2. A Draft entry exists and points to a PublishableEntityVersion: This is
       the most common state.
    3. A Draft entry exists and points to a null version: This means a version
       used to be the draft, but it's been functionally "deleted". The versions
       still exist in our history, but we're done using it.

    It would have saved a little space to add this data to the Published model
    (and possibly call the combined model something else). Split Modulestore did
    this with its active_versions table. I keep it separate here to get a better
    separation of lifecycle events: i.e. this table *only* changes when drafts
    are updated, not when publishing happens. The Published model only changes
    when something is published.
    """
    # If we're removing a PublishableEntity entirely, also remove the Draft
    # entry for it. This isn't a normal operation, but can happen if you're
    # deleting an entire LearningPackage.
    entity = models.OneToOneField(
        PublishableEntity,
        on_delete=models.CASCADE,
        primary_key=True,
    )
    version = models.OneToOneField(
        PublishableEntityVersion,
        on_delete=models.RESTRICT,
        null=True,
        blank=True,
    )


class DraftChangeSet(models.Model):
    """
    There is one row in this table for every time Drafts are created/modified.

    Most of the time we'll only be changing one Draft at a time, and this will
    be 1:1 with DraftChange. But there are some operations that affect many
    Drafts at once, such as discarding changes (i.e. reset to the published
    version) or doing an import.
    """
    uuid = immutable_uuid_field()
    learning_package = models.ForeignKey(LearningPackage, on_delete=models.CASCADE)
    changed_at = manual_date_time_field()
    changed_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
    )

    class Meta:
        verbose_name = "Draft Change Set"
        verbose_name_plural = "Draft Change Sets"


class DraftChange(models.Model):
    """
    A single change in the Draft version of a Publishable Entity.

    We have one unusual convention here, which is that if we have a DraftChange
    where the old_version == new_version, it means that a Draft's defined
    version hasn't changed, but the data associated with the Draft has changed
    because some other entity has changed.

    The main example we have of this are containers. Imagine that we have a
    Unit that is at version 1, and has unpinned references to various Components
    that are its children. The Unit's version does not get incremented when the
    Components are edited, because the Unit container is defined to always get
    the most recent version of those Components. We would only make a new
    version of the Unit if we changed the metadata of the Unit itself (e.g. the
    title), or if we added, removed, or reordered the children.

    Yet updating a Component intuitively changes what we think of as the content
    of the Unit. Users who are working on Units also expect that a change to a
    Component will be reflected when looking at a Unit's "last updated" info.

    TODO: Add more info here, especially about how we're going to store multiple
    layers of hierarchy. And speculation on other dependency types.
    """
    change_set = models.ForeignKey(
        DraftChangeSet,
        on_delete=models.CASCADE,
        related_name="changes",
    )
    entity = models.ForeignKey(PublishableEntity, on_delete=models.RESTRICT)
    old_version = models.ForeignKey(
        PublishableEntityVersion,
        on_delete=models.RESTRICT,
        null=True,
        blank=True,
        related_name="+",
    )
    new_version = models.ForeignKey(
        PublishableEntityVersion, on_delete=models.RESTRICT, null=True, blank=True
    )

    class Meta:
        constraints = [
            # A PublishableEntity can have only one DraftLogRecord per DraftLog.
            # You can't simultaneously change the same thing in two different
            # ways, e.g. set the Draft to version 1 and version 2 at the same
            # time; or delete a Draft and set it to version 2 at the same time.
            models.UniqueConstraint(
                fields=[
                    "change_set",
                    "entity",
                ],
                name="oel_dc_uniq_changeset_entity",
            )
        ]
        indexes = [
            # Entity (reverse) DraftLog Index:
            #   * Find the history of draft changes for a given entity, starting
            #     with the most recent (since IDs are ascending ints).
            models.Index(
                fields=["entity", "-change_set"],
                name="oel_dc_idx_entity_rchangeset",
            ),
        ]
        verbose_name = "Draft Change"
        verbose_name_plural = "Draft Changes"


class DraftChangeSideEffect(models.Model):
    """
    Model to track when a change in one Draft may affect other Drafts.

    Our first use case for this is that changes involving child components are
    thought to affect parent Units, even if the Unit's version doesn't change.
    So this model allows us to do a query that amounts to, "Tell me the last
    time this container or any descendent of this container was modified."

    The DraftChanged caused by a DraftChangeSideEffect will have its old_version
    set to be the same as its new_version to denote that the Draft version
    itself hasn't changed. See the docstring for DraftChange for more details.

    Some notes:

    1. An entry only shows up here if the side-effect draft does not already
       have a DraftChange entry in the current DraftChangeSet. So for instance,
       if a DraftChangeSet changes a Unit's metadata and updates a child
       Component at the same time, then the Unit's DraftChange (e.g. v1->v2)
       already exists and no DraftChangeSideEffect is needed to denote that the
       Unit was changed due to the child Component update.
    """
    source_change = models.ForeignKey(DraftChange, on_delete=models.RESTRICT, related_name='+')
    causes_change = models.ForeignKey(DraftChange, on_delete=models.RESTRICT, related_name='+')
