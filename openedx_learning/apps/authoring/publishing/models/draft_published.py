"""
Draft and Published models
"""
from django.db import models

from .publish_log import PublishLogRecord
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


class Published(models.Model):
    """
    Find the currently published version of an entity.

    Notes:

    * There is only ever one published PublishableEntityVersion per
      PublishableEntity at any given time.
    * It may be possible for a PublishableEntity to exist only as a Draft (and thus
      not show up in this table).
    * If a row exists for a PublishableEntity, but the ``version`` field is
      None, it means that the entity was published at some point, but is no
      longer published now–i.e. it's functionally "deleted", even though all
      the version history is preserved behind the scenes.

    TODO: Do we need to create a (redundant) title field in this model so that
    we can more efficiently search across titles within a LearningPackage?
    Probably not an immediate concern because the number of rows currently
    shouldn't be > 10,000 in the more extreme cases.

    TODO: Do we need to make a "most_recently" published version when an entry
    is unpublished/deleted?
    """

    entity = models.OneToOneField(
        PublishableEntity,
        on_delete=models.CASCADE,
        primary_key=True,
    )
    version = models.OneToOneField(
        PublishableEntityVersion,
        on_delete=models.RESTRICT,
        null=True,
    )
    publish_log_record = models.ForeignKey(
        PublishLogRecord,
        on_delete=models.RESTRICT,
    )

    class Meta:
        verbose_name = "Published Entity"
        verbose_name_plural = "Published Entities"
