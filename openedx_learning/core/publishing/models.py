"""
The data models here are intended to be used by other apps to publish different
types of content, such as Components, Units, Sections, etc. These models should
support the logic for the management of the publishing process:

* The relationship between publishable entities and their many versions.
* The management of drafts.
* Publishing specific versions of publishable entities.
* Finding the currently published versions.
* The act of publishing, and doing so atomically.
* Managing reverts.
* Storing and querying publish history.
"""
from django.conf import settings
from django.core.validators import MinValueValidator
from django.db import models

from openedx_learning.lib.fields import (
    MultiCollationTextField,
    case_insensitive_char_field,
    immutable_uuid_field,
    key_field,
    manual_date_time_field,
)


class LearningPackage(models.Model):  # type: ignore[django-manager-missing]
    """
    Top level container for a grouping of authored content.

    Each PublishableEntity belongs to exactly one LearningPackage.
    """
    # Explictly declare a 4-byte ID instead of using the app-default 8-byte ID.
    # We do not expect to have more than 2 billion LearningPackages on a given
    # site. Furthermore, many, many things have foreign keys to this model and
    # uniqueness indexes on those foreign keys + their own fields, so the 4
    # bytes saved will add up over time.
    id = models.AutoField(primary_key=True)

    uuid = immutable_uuid_field()

    # "key" is a reserved word for MySQL, so we're temporarily using the column
    # name of "_key" to avoid breaking downstream tooling. There's an open
    # question as to whether this field needs to exist at all, or whether the
    # top level library key it's currently used for should be entirely in the
    # LibraryContent model.
    key = key_field(db_column="_key")

    title = case_insensitive_char_field(max_length=500, blank=False)

    # TODO: We should probably defer this field, since many things pull back
    # LearningPackage as select_related. Usually those relations only care about
    # the UUID and key, so maybe it makes sense to separate the model at some
    # point.
    description = MultiCollationTextField(
        blank=True,
        null=False,
        default="",
        max_length=10_000,
        # We don't really expect to ever sort by the text column, but we may
        # want to do case-insensitive searches, so it's useful to have a case
        # and accent insensitive collation.
        db_collations={
            "sqlite": "NOCASE",
            "mysql": "utf8mb4_unicode_ci",
        }
    )

    created = manual_date_time_field()
    updated = manual_date_time_field()

    def __str__(self):
        return f"{self.key}"

    class Meta:
        constraints = [
            # LearningPackage keys must be globally unique. This is something
            # that might be relaxed in the future if this system were to be
            # extensible to something like multi-tenancy, in which case we'd tie
            # it to something like a Site or Org.
            models.UniqueConstraint(
                fields=["key"],
                name="oel_publishing_lp_uniq_key",
            )
        ]
        verbose_name = "Learning Package"
        verbose_name_plural = "Learning Packages"


class PublishableEntity(models.Model):
    """
    This represents any publishable thing that has ever existed in a
    LearningPackage. It serves as a stable model that will not go away even if
    these things are later unpublished or deleted.

    A PublishableEntity belongs to exactly one LearningPackage.

    Examples of Publishable Entities
    --------------------------------

    Components (e.g. VideoBlock, ProblemBlock), Units, and Sections/Subsections
    would all be considered Publishable Entites. But anything that can be
    imported, exported, published, and reverted in a course or library could be
    modeled as a PublishableEntity, including things like Grading Policy or
    possibly Taxonomies (?).

    How to use this model
    ---------------------

    The publishing app understands that publishable entities exist, along with
    their drafts and published versions. It has some basic metadata, such as
    identifiers, who created it, and when it was created. It's meant to
    encapsulate the draft and publishing related aspects of your content, but
    the ``publishing`` app doesn't know anything about the actual content being
    referenced.

    You have to provide actual meaning to PublishableEntity by creating your own
    models that will represent your particular content and associating them to
    PublishableEntity via a OneToOneField with primary_key=True. The easiest way
    to do this is to have your model inherit from PublishableEntityMixin.

    Identifiers
    -----------
    The UUID is globally unique and should be treated as immutable.

    The key field *is* mutable, but changing it will affect all
    PublishedEntityVersions. They are locally unique within the LearningPackage.

    If you are referencing this model from within the same process, use a
    foreign key to the id. If you are referencing this PublishedEntity from an
    external system/service, use the UUID. The key is the part that is most
    likely to be human-readable, and may be exported/copied, but try not to rely
    on it, since this value may change.

    Note: When we actually implement the ability to change identifiers, we
    should make a history table and a modified attribute on this model.

    Why are Identifiers in this Model?
    ----------------------------------

    A PublishableEntity never stands alone–it's always intended to be used with
    a 1:1 model like Component or Unit. So why have all the identifiers in this
    model instead of storing them in those other models? Two reasons:

    * Published things need to have the right identifiers so they can be used
    throughout the system, and the UUID is serving the role of ISBN in physical
    book publishing.
    * We want to be able to enforce the idea that "key" is locally unique across
    all PublishableEntities within a given LearningPackage. Component and Unit
    can't do that without a shared model.

    That being said, models that build on PublishableEntity are free to add
    their own identifiers if it's useful to do so.

    Why not Inherit from this Model?
    --------------------------------

    Django supports multi-table inheritance:

      https://docs.djangoproject.com/en/4.2/topics/db/models/#multi-table-inheritance

    We don't use that, primarily because we want to more clearly decouple
    publishing concerns from the rest of the logic around Components, Units,
    etc. If you made a Component and ComponentVersion models that subclassed
    PublishableEntity and PublishableEntityVersion, and then accessed
    ``component.versions``, you might expect ComponentVersions to come back and
    be surprised when you get EntityVersions instead.

    In general, we want freedom to add new Publishing models, fields, and
    methods without having to worry about the downstream name collisions with
    other apps (many of which might live in other repositories). The helper
    mixins will provide a little syntactic sugar to make common access patterns
    more convenient, like file access.
    """

    uuid = immutable_uuid_field()
    learning_package = models.ForeignKey(
        LearningPackage,
        on_delete=models.CASCADE,
        related_name="publishable_entities",
    )

    # "key" is a reserved word for MySQL, so we're temporarily using the column
    # name of "_key" to avoid breaking downstream tooling. Consider renaming
    # this later.
    key = key_field(db_column="_key")

    created = manual_date_time_field()
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
    )

    class Meta:
        constraints = [
            # Keys are unique within a given LearningPackage.
            models.UniqueConstraint(
                fields=[
                    "learning_package",
                    "key",
                ],
                name="oel_pub_ent_uniq_lp_key",
            )
        ]
        indexes = [
            # Global Key Index:
            #   * Search by key across all PublishableEntities on the site. This
            #     would be a support-oriented tool from Django Admin.
            models.Index(
                fields=["key"],
                name="oel_pub_ent_idx_key",
            ),
            # LearningPackage (reverse) Created Index:
            #  * Search for most recently *created* PublishableEntities for a
            #    given LearningPackage, since they're the most likely to be
            #    actively worked on.
            models.Index(
                fields=["learning_package", "-created"],
                name="oel_pub_ent_idx_lp_rcreated",
            ),
        ]
        # These are for the Django Admin UI.
        verbose_name = "Publishable Entity"
        verbose_name_plural = "Publishable Entities"

    def __str__(self):
        return f"{self.key}"


class PublishableEntityVersion(models.Model):
    """
    A particular version of a PublishableEntity.

    This model has its own ``uuid`` so that it can be referenced directly. The
    ``uuid`` should be treated as immutable.

    PublishableEntityVersions are created once and never updated. So for
    instance, the ``title`` should never be modified.

    Like PublishableEntity, the data in this model is only enough to cover the
    parts that are most important for the actual process of managing drafts and
    publishes. You will want to create your own models to represent the actual
    content data that's associated with this PublishableEntityVersion, and
    connect them using a OneToOneField with primary_key=True. The easiest way to
    do this is to inherit from PublishableEntityVersionMixin. Be sure to treat
    these versioned models in your app as immutable as well.
    """

    uuid = immutable_uuid_field()
    entity = models.ForeignKey(
        PublishableEntity, on_delete=models.CASCADE, related_name="versions"
    )

    # Most publishable things will have some sort of title, but blanks are
    # allowed for those that don't require one.
    title = case_insensitive_char_field(max_length=500, blank=True, default="")

    # The version_num starts at 1 and increments by 1 with each new version for
    # a given PublishableEntity. Doing it this way makes it more convenient for
    # users to refer to than a hash or UUID value. It also helps us catch race
    # conditions on save, by setting a unique constraint on the entity and
    # version_num.
    version_num = models.PositiveIntegerField(
        null=False,
        validators=[MinValueValidator(1)],
    )

    # All PublishableEntityVersions created as part of the same publish should
    # have the exact same created datetime (not off by a handful of
    # microseconds).
    created = manual_date_time_field()

    # User who created the PublishableEntityVersion. This can be null if the
    # user is later removed. Open edX in general doesn't let you remove users,
    # but we should try to model it so that this is possible eventually.
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
    )

    class Meta:
        constraints = [
            # Prevent the situation where we have multiple
            # PublishableEntityVersions claiming to be the same version_num for
            # a given PublishableEntity. This can happen if there's a race
            # condition between concurrent editors in different browsers,
            # working on the same Publishable. With this constraint, one of
            # those processes will raise an IntegrityError.
            models.UniqueConstraint(
                fields=[
                    "entity",
                    "version_num",
                ],
                name="oel_pv_uniq_entity_version_num",
            )
        ]
        indexes = [
            # LearningPackage (reverse) Created Index:
            #   * Make it cheap to find the most recently created
            #     PublishableEntityVersions for a given LearningPackage. This
            #     represents the most recently saved work for a LearningPackage
            #     and would be the most likely areas to get worked on next.
            models.Index(
                fields=["entity", "-created"],
                name="oel_pv_idx_entity_rcreated",
            ),
            # Title Index:
            #   * Search by title.
            models.Index(
                fields=[
                    "title",
                ],
                name="oel_pv_idx_title",
            ),
        ]

        # These are for the Django Admin UI.
        verbose_name = "Publishable Entity Version"
        verbose_name_plural = "Publishable Entity Versions"


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
