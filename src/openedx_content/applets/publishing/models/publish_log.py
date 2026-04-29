"""
PublishLog and PublishLogRecord models
"""
from django.conf import settings
from django.db import models
from django.utils.translation import gettext_lazy as _

from openedx_django_lib.fields import (
    case_insensitive_char_field,
    hash_field,
    immutable_uuid_field,
    manual_date_time_field,
)

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

    If the old_version and new_version of a PublishLogRecord match, it means
    that the definition of the entity itself did not change (i.e. no new
    PublishableEntityVersion was created), but something else was published that
    had the side-effect of changing the published state of this entity. For
    instance, if a Unit has unpinned references to its child Components (which
    it almost always will), then publishing one of those Components will alter
    the published state of the Unit, even if the UnitVersion does not change.
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

    # The dependencies_hash_digest is used when the version alone isn't enough
    # to let us know the full draft state of an entity. This happens any time a
    # Published version has dependencies (see the
    # PublishableEntityVersionDependency model), because changes in those
    # dependencies will cause changes to the state of the Draft. The main
    # example of this is containers, where changing an unpinned child affects
    # the state of the parent container, even if that container's definition
    # (and thus version) does not change.
    #
    # If a Published version has no dependencies, then its entire state is
    # captured by its version, and the dependencies_hash_digest is blank. (Blank
    # is slightly more convenient for database comparisons than NULL.)
    #
    # Note: There is an equivalent of this field in the Draft model and the
    # the values may drift away from each other.
    dependencies_hash_digest = hash_field(blank=True, default='', max_length=8)

    # The "direct" field captures user intent during the publishing process. It
    # is True if the user explicitly requested to publish the entity represented
    # by this PublishLogRecord—i.e. they clicked "publish" on this entity or
    # selected it for bulk publish.
    #
    # This field is False if this entity was indirectly published either as a
    # child/dependency or side-effect of a directly published entity.
    #
    # If this field is None, that means that this PublishLogRecord was created
    # before we started capturing user intent (pre-Verawood release), and we
    # cannot reliably infer what the user clicked on. For example, say we had a
    # Subsection > Unit > Component arrangement where the Component had an
    # unpublished change. The user is allowed to press the "publish" button at
    # the Subsection, Unit, or Component levels in the UI. Before we started
    # recording this field, the resulting PublishLogs would have looked
    # identical in all three cases: a version change PublishLogRecord for
    # Component, and side-effect records for the Unit and Subsection. Therefore,
    # we cannot accurately backfill this field.
    #
    # Here are some examples to illustrate how "direct" gets set and why:
    #
    # Example 1: The user clicks "publish" on a Component that's in a Unit.
    #
    #   The Component has direct=True, but the side-effect PublishLogRecord for
    #   the Unit has direct=False. Likewise, any side-effect records at higher
    #   levels (subsection, section) also have direct=False.
    #
    # Example 2: The user clicks "publish" on a Unit, where both the Unit and
    # Component have unpublished changes:
    #
    #   In this case, the Unit has direct=True, and the Component has
    #   direct=False. The draft status of the Component is irrelevant. The user
    #   asked for the Unit to the published, so the Unit's PublishLogRecord is
    #   the only thing that gets direct=True.
    #
    # Example 3: The user clicks "publish" on a Unit that has no changes of its
    # own (draft version == published version), but the Unit contains a Component
    # that has changes.
    #
    #   Again, only the PublishLogRecord for the Unit has direct=True. The
    #   Component's PublishLogRecord has direct=False. Even though the Unit's
    #   published version_num does not change (i.e. it is purely a side-effect
    #   publish), the user intent was to publish the Unit (and anything it
    #   contains), so the Unit gets direct=True.
    #
    # Example 4: The user selects multiple entities for bulk publishing.
    #
    #   Those exact entities that the user selected get direct=True. It does not
    #   matter if some of those entities are children of other selected items or
    #   not. Other entries like dependencies or side-effects have direct=False.
    #
    # Example 5: The user selects "publish all".
    #
    #   Selecting "publish all" in our system currently translates into "publish
    #   all the entities that have a draft version that is different from its
    #   published version". Those entities would get PublishLogRecords with
    #   direct=True, while all side-effects would get records with direct=False.
    #   So if a Unit's draft and published versions match, and one of its
    #   Components has unpublished changes, then "publish all" would cause the
    #   Component's record to have direct=True and the Unit's record to have
    #   direct=False.
    direct = models.BooleanField(
        null=True,
        blank=True,
        default=False,
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

    def __str__(self):
        old_version_num = None if self.old_version is None else self.old_version.version_num
        new_version_num = None if self.new_version is None else self.new_version.version_num
        return f"PublishLogRecord: {self.entity} ({old_version_num} -> {new_version_num})"


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

    @property
    def log_record(self):
        return self.publish_log_record

    class Meta:
        verbose_name = "Published Entity"
        verbose_name_plural = "Published Entities"


class PublishSideEffect(models.Model):
    """
    Model to track when a change in one Published entity affects others.

    Our first use case for this is that changes involving child components are
    thought to affect parent Units, even if the parent's version doesn't change.

    Side-effects are recorded in a collapsed form that only captures one level.
    So if Components C1 and C2 are both published and they are part of Unit U1,
    which is in turn a part of Subsection SS1, then the PublishSideEffect
    entries are::

      (C1, U1)
      (C2, U1)
      (U1, SS1)

    We do not keep entries for (C1, SS1) or (C2, SS1). This is to make the model
    simpler, so we don't have to differentiate between direct side-effects and
    transitive side-effects in the model.

    .. no_pii:
    """
    cause = models.ForeignKey(
        PublishLogRecord,
        on_delete=models.RESTRICT,
        related_name='causes',
    )
    effect = models.ForeignKey(
        PublishLogRecord,
        on_delete=models.RESTRICT,
        related_name='affected_by',
    )

    class Meta:
        constraints = [
            # Duplicate entries for cause & effect are just redundant. This is
            # here to guard against weird bugs that might introduce this state.
            models.UniqueConstraint(
                fields=["cause", "effect"],
                name="oel_pub_pse_uniq_c_e",
            )
        ]
        verbose_name = _("Publish Side Effect")
        verbose_name_plural = _("Publish Side Effects")
