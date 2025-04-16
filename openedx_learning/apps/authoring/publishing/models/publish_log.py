"""
PublishLog and PublishLogRecord models
"""
from django.conf import settings
from django.db import models

from openedx_learning.lib.fields import case_insensitive_char_field, immutable_uuid_field, manual_date_time_field

from .learning_package import LearningPackage
from .publishable_entity import PublishableEntity, PublishableEntityVersion


class PublishLog(models.Model):
    """
    There is one row in this table for every time content is published.

    Each PublishLog has 0 or more PublishLogRecords describing exactly which
    PublishableEntites were published and what the version changes are. A
    PublishLog is like a git commit in that sense, with individual
    PublishLogRecords representing the files changed.

    Open question: Empty publishes are allowed at this time, and might be useful
    for "fake" publishes that are necessary to invoke other post-publish
    actions. It's not clear at this point how useful this will actually be.

    The absence of a ``version_num`` field in this model is intentional, because
    having one would potentially cause write contention/locking issues when
    there are many people working on different entities in a very large library.
    We already see some contention issues occuring in ModuleStore for courses,
    and we want to support Libraries that are far larger.

    If you need a LearningPackage-wide indicator for version and the only thing
    you care about is "has *something* changed?", you can make a foreign key to
    the most recent PublishLog, or use the most recent PublishLog's primary key.
    This should be monotonically increasing, though there will be large gaps in
    values, e.g. (5, 190, 1291, etc.). Be warned that this value will not port
    across sites. If you need site-portability, the UUIDs for this model are a
    safer bet, though there's a lot about import/export that we haven't fully
    mapped out yet.
    """

    uuid = immutable_uuid_field()
    learning_package = models.ForeignKey(LearningPackage, on_delete=models.CASCADE)
    message = case_insensitive_char_field(max_length=500, blank=True, default="")
    published_at = manual_date_time_field()
    published_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
    )

    class Meta:
        verbose_name = "Publish Log"
        verbose_name_plural = "Publish Logs"


class PublishLogRecord(models.Model):
    """
    A record for each publishable entity version changed, for each publish.

    To revert a publish, we would make a new publish that swaps ``old_version``
    and ``new_version`` field values.
    """

    publish_log = models.ForeignKey(
        PublishLog,
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
            # A Publishable can have only one PublishLogRecord per PublishLog.
            # You can't simultaneously publish two different versions of the
            # same publishable.
            models.UniqueConstraint(
                fields=[
                    "publish_log",
                    "entity",
                ],
                name="oel_plr_uniq_pl_publishable",
            )
        ]
        indexes = [
            # Publishable (reverse) Publish Log Index:
            #   * Find the history of publishes for a given Publishable,
            #     starting with the most recent (since IDs are ascending ints).
            models.Index(
                fields=["entity", "-publish_log"],
                name="oel_plr_idx_entity_rplr",
            ),
        ]
        verbose_name = "Publish Log Record"
        verbose_name_plural = "Publish Log Records"


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
