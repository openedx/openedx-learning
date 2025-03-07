"""
PublishableEntity model and PublishableEntityVersion
"""
from django.conf import settings
from django.core.validators import MinValueValidator
from django.db import models

from openedx_learning.lib.fields import (
    case_insensitive_char_field,
    immutable_uuid_field,
    key_field,
    manual_date_time_field,
)

from .learning_package import LearningPackage


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
