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


class DraftChangeLog(models.Model):
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

    @property
    def changes(self):
        """
        Alias for "records".

        We use "records" for consistency with PublishLogRecord, but somteimes
        it's more natural to call these "changes".
        """
        return self.records

    class Meta:
        verbose_name = "Draft Change Log"
        verbose_name_plural = "Draft Change Logs"


class DraftChangeLogRecord(models.Model):
    """
    A single change in the Draft version of a Publishable Entity.

    We have one unusual convention here, which is that if we have a
    DraftChangeLogRecord where the old_version == new_version, it means that a 
    Draft's defined version hasn't changed, but the data associated with the
    Draft has changed because some other entity has changed.

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
    The old_version == new_version convention lets us represent that in a useful
    way because that Unit *is* a part of the change set represented by a
    DraftChangeLog, even if its own versioned data hasn't changed.
    """
    draft_change_log = models.ForeignKey(
        DraftChangeLog,
        on_delete=models.CASCADE,
        related_name="records",
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
                    "draft_change_log",
                    "entity",
                ],
                name="oel_dlr_uniq_dcl",
            )
        ]
        indexes = [
            # Entity (reverse) DraftLog Index:
            #   * Find the history of draft changes for a given entity, starting
            #     with the most recent (since IDs are ascending ints).
            models.Index(
                fields=["entity", "-draft_change_log"],
                name="oel_dlr_idx_entity_rdcl",
            ),
        ]
        verbose_name = "Draft Log"
        verbose_name_plural = "Draft Log"


class DraftSideEffect(models.Model):
    """
    Model to track when a change in one Draft affects other Drafts.

    Our first use case for this is that changes involving child components are
    thought to affect parent Units, even if the parent's version doesn't change.

    Side-effects are recorded in a collapsed form that only captures one level.
    So if Components C1 and C2 are both changed and they are part of Unit U1,
    which is in turn a part of Subsection SS1, then the DraftSideEffect entries
    are::

      (C1, U1)
      (C2, U1)
      (U1, SS1)

    We do not keep entries for (C1, SS1) or (C2, SS1). This is to make the model
    simpler, so we don't have to differentiate between direct side-effects and
    transitive side-effects in the model.
    """
    cause = models.ForeignKey(
        DraftChangeLogRecord,
        on_delete=models.RESTRICT,
        related_name='causes',
    )
    effect = models.ForeignKey(
        DraftChangeLogRecord,
        on_delete=models.RESTRICT,
        related_name='caused_by',
    )

    class Meta:
        constraints = [
            # Duplicate entries for cause & effect are just redundant. This is
            # here to guard against weird bugs that might introduce this state. 
            models.UniqueConstraint(
                fields=["cause", "effect"],
                name="oel_pub_dse_uniq_c_e",
            )
        ]
