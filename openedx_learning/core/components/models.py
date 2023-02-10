"""
The model hierarchy is Component -> ComponentVersion -> Content.

A Component is an entity like a Problem or Video. It has enough information to
identify the Component and determine what the handler should be (e.g. XBlock
Problem), but little beyond that.

Components have one or more ComponentVersions, which represent saved versions of
that Component. At any time, there is at most one published ComponentVersion for
a Component in a LearningPackage (there can be zero if it's unpublished). The
publish status is tracked in PublishedComponent, with historical publish data in
ComponentPublishLogEntry.

Content is a simple model holding unversioned, raw data, along with some simple
metadata like size and MIME type.

Multiple pieces of Content may be associated with a ComponentVersion, through
the ComponentVersionContent model. ComponentVersionContent allows to specify a
Component-local identifier. We're using this like a file path by convention, but
it's possible we might want to have special identifiers later.
"""
from django.db import models
from django.conf import settings
from django.core.validators import MinValueValidator, MaxValueValidator

from openedx_learning.lib.fields import (
    hash_field,
    identifier_field,
    immutable_uuid_field,
    manual_date_time_field,
)
from ..publishing.models import LearningPackage, PublishLogEntry


class Component(models.Model):
    """
    This represents any content that has ever existed in a LearningPackage.

    A Component will have many ComponentVersions over time, and most metadata is
    associated with the ComponentVersion model. Make a foreign key to this model
    when you need a stable reference that will exist for as long as the
    LearningPackage itself exists. It is possible for an Component to have no
    published ComponentVersion, either because it was never published or because
    it's been "deleted" (made unavailable).

    A Component belongs to one and only one LearningPackage.

    The UUID should be treated as immutable. The identifier field *is* mutable,
    but changing it will affect all ComponentVersions. If you are referencing
    this model from within the same process, use a foreign key to the id. If you
    are referencing this Component from an external system, use the UUID. Do NOT
    use the identifier if you can help it, since this can be changed.

    Note: When we actually implement the ability to change identifiers, we
    should make a history table and a modified attribute on this model.
    """

    uuid = immutable_uuid_field()
    learning_package = models.ForeignKey(LearningPackage, on_delete=models.CASCADE)

    # namespace and type work together to help figure out what Component needs
    # to handle this data. A namespace is *required*. The namespace for XBlocks
    # is "xblock.v1" (to match the setup.py entrypoint naming scheme).
    namespace = models.CharField(max_length=100, null=False, blank=False)

    # type is a way to help sub-divide namespace if that's convenient. This
    # field cannot be null, but it can be blank if it's not necessary. For an
    # XBlock, type corresponds to tag, e.g. "video". It's also the block_type in
    # the UsageKey.
    type = models.CharField(max_length=100, null=False, blank=True)

    # identifier is local to a learning_package + namespace + type. For XBlocks,
    # this is the block_id part of the UsageKey, which usually shows up in the
    # OLX as the url_name attribute.
    identifier = identifier_field()

    created = manual_date_time_field()

    class Meta:
        constraints = [
            # The combination of (namespace, type, identifier) is unique within
            # a given LearningPackage. Note that this means it is possible to
            # have two Components that have the exact same identifier. An XBlock
            # would be modeled as namespace="xblock.v1" with the type as the
            # block_type, so the identifier would only be the block_id (the 
            # very last part of the UsageKey).
            models.UniqueConstraint(
                fields=[
                    "learning_package",
                    "namespace",
                    "type",
                    "identifier",
                ],
                name="component_uniq_lc_ns_type_identifier",
            )
        ]
        indexes = [
            # LearningPackage Identifier Index:
            #   * Search by identifier (without having to specify namespace and
            #     type). This kind of freeform search will likely be common.
            models.Index(
                fields=["learning_package", "identifier"],
                name="component_idx_lp_identifier",
            ),

            # Global Identifier Index:
            #   * Search by identifier across all Components on the site. This
            #     would be a support-oriented tool from Django Admin.
            models.Index(
                fields=["identifier"],
                name="component_idx_identifier",
            ),

            # LearningPackage (reverse) Created Index:
            #  * Search for most recently *created* Components for a given
            #    LearningPackage, since they're the most likely to be actively
            #    worked on.
            models.Index(
                fields=["learning_package", "-created"],
                name="component_idx_lp_rcreated",
            ),
        ]

        # These are for the Django Admin UI.
        verbose_name = "Component"
        verbose_name_plural = "Components"

    def __str__(self):
        return f"{self.identifier}"


class ComponentVersion(models.Model):
    """
    A particular version of a Component.

    This holds the title (because that's versioned information) and the contents
    via a M:M relationship with Content via ComponentVersionContent.

    * Each ComponentVersion belongs to one and only one Component.
    * ComponentVersions have a version_num that should increment by one with
      each new version. 
    """

    uuid = immutable_uuid_field()
    component = models.ForeignKey(Component, on_delete=models.CASCADE)

    # Blank titles are allowed because some Components are built to be used from
    # a particular Unit, and the title would be redundant in that context (e.g.
    # a "Welcome" video in a "Welcome" Unit).
    title = models.CharField(max_length=1000, default="", null=False, blank=True)

    # The version_num starts at 1 and increments by 1 with each new version for
    # a given Component. Doing it this way makes it more convenient for users to
    # refer to than a hash or UUID value.
    version_num = models.PositiveBigIntegerField(
        null=False,
        validators=[MinValueValidator(1)],
    )

    # All ComponentVersions created as part of the same publish should have the
    # exact same created datetime (not off by a handful of microseconds).
    created = manual_date_time_field()

    # User who created the ContentVersion. This can be null if the user is later
    # removed. Open edX in general doesn't let you remove users, but we should
    # try to model it so that this is possible eventually.
    created_by = models.ForeignKey(
       settings.AUTH_USER_MODEL,
       on_delete=models.SET_NULL,
       null=True,
    )

    # The contents hold the actual interesting data associated with this
    # ComponentVersion.
    contents = models.ManyToManyField(
        "Content",
        through="ComponentVersionContent",
        related_name="component_versions",
    )

    def __str__(self):
        return f"v{self.version_num}: {self.title}"

    class Meta:
        constraints = [
            # Prevent the situation where we have multiple ComponentVersions
            # claiming to be the same version_num for a given Component. This
            # can happen if there's a race condition between concurrent editors
            # in different browsers, working on the same Component. With this
            # constraint, one of those processes will raise an IntegrityError.
            models.UniqueConstraint(
                fields=[
                    "component",
                    "version_num",
                ],
                name="cv_uniq_component_version_num",
            )
        ]
        indexes = [
            # LearningPackage (reverse) Created Index:
            #   * Make it cheap to find the most recently created
            #     ComponentVersions for a given LearningPackage. This represents
            #     the most recently saved work for a LearningPackage and would
            #     be the most likely areas to get worked on next.
            models.Index(
                fields=["component", "-created"],
                name="cv_idx_component_rcreated",
            ),

            # Title Index:
            #   * Search by title.
            models.Index(
                fields=["title",],
                name="cv_idx_title",
            ),
        ]

        # These are for the Django Admin UI.
        verbose_name = "Component Version"
        verbose_name_plural = "Component Versions"


class ComponentPublishLogEntry(models.Model):
    """
    This is a historical record of Component publishing.

    When a ComponentVersion is initially created, it's considered a draft. The
    act of publishing means we're marking a ContentVersion as the official,
    ready-for-use version of this Component.
    """

    publish_log_entry = models.ForeignKey(PublishLogEntry, on_delete=models.CASCADE)
    component = models.ForeignKey(Component, on_delete=models.RESTRICT)
    component_version = models.ForeignKey(
        ComponentVersion, on_delete=models.RESTRICT, null=True
    )


class PublishedComponent(models.Model):
    """
    For any given Component, what is the currently published ComponentVersion.

    It may be possible for a Component to exist only as a Draft (and thus not
    show up in this table). There is only ever one published ComponentVersion
    per Component at any given time.

    TODO: Do we need to create a (redundant) title field in this model so that
    we can more efficiently search across titles within a LearningPackage?
    Probably not an immediate concern because the number of rows currently
    shouldn't be > 10,000 in the more extreme cases.
    """

    component = models.OneToOneField(
        Component, on_delete=models.RESTRICT, primary_key=True
    )
    component_version = models.OneToOneField(
        ComponentVersion,
        on_delete=models.RESTRICT,
        null=True,
    )
    component_publish_log_entry = models.ForeignKey(
        ComponentPublishLogEntry,
        on_delete=models.RESTRICT,
    )

    class Meta:
        verbose_name = "Published Component"
        verbose_name_plural = "Published Components"


class Content(models.Model):
    """
    This is the most basic piece of raw content data, with no version metadata.

    Content stores data in an immutable Binary BLOB `data` field. This data is
    not auto-normalized in any way, meaning that pieces of content that are
    semantically equivalent (e.g. differently spaced/sorted JSON) will result in
    new entries. This model is intentionally ignorant of what these things mean,
    because it expects supplemental data models to build on top of it.

    Two Content instances _can_ have the same hash_digest if they are of
    different MIME types. For instance, an empty text file and an empty SRT file
    will both hash the same way, but be considered different entities.

    The other fields on Content are for data that is intrinsic to the file data
    itself (e.g. the size). Any smart parsing of the contents into more
    structured metadata should happen in other models that hang off of Content.

    Content models are not versioned in any way. The concept of versioning only
    exists at a higher level.

    Since this model uses a BinaryField to hold its data, we have to be careful
    about scalability issues. For instance, video files should not be stored
    here directly. There is a 10 MB limit set for the moment, to accomodate
    things like PDF files and images, but the itention is for the vast majority
    of rows to be much smaller than that.
    """

    # Cap item size at 10 MB for now.
    MAX_SIZE = 10_000_000

    learning_package = models.ForeignKey(LearningPackage, on_delete=models.CASCADE)
    hash_digest = hash_field()

    # MIME type, such as "text/html", "image/png", etc. Per RFC 4288, MIME type
    # and sub-type may each be 127 chars, making a max of 255 (including the "/"
    # in between).
    #
    # DO NOT STORE parameters here, e.g. "charset=". We can make a new field if
    # that becomes necessary.
    mime_type = models.CharField(max_length=255, blank=False, null=False)

    size = models.PositiveBigIntegerField(
        validators=[MaxValueValidator(MAX_SIZE)],
    )

    # This should be manually set so that multiple Content rows being set in the
    # same transaction are created with the same timestamp. The timestamp should
    # be UTC.
    created = manual_date_time_field()

    data = models.BinaryField(null=False, max_length=MAX_SIZE)

    class Meta:
        constraints = [
            # Make sure we don't store duplicates of this raw data within the
            # same LearningPackage, unless they're of different MIME types.
            models.UniqueConstraint(
                fields=[
                    "learning_package",
                    "mime_type",
                    "hash_digest",
                ],
                name="content_uniq_lc_mime_type_hash_digest",
            ),
        ]
        indexes = [
            # LearningPackage MIME type Index:
            #   * Break down Content counts by type/subtype within a 
            #     LearningPackage.
            #   * Find all the Content in a LearningPackage that matches a
            #     certain MIME type (e.g. "image/png", "application/pdf".
            models.Index(
                fields=["learning_package", "mime_type"],
                name="content_idx_lp_mime_type",
            ),
            # LearningPackage (reverse) Size Index:
            #   * Find largest Content in a LearningPackage.
            #   * Find the sum of Content size for a given LearningPackage.
            models.Index(
                fields=["learning_package", "-size"],
                name="content_idx_lp_rsize",
            ),
            # LearningPackage (reverse) Created Index:
            #   * Find most recently added Content.
            models.Index(
                fields=["learning_package", "-created"],
                name="content_idx_lp_rcreated",
            )
        ]


class ComponentVersionContent(models.Model):
    """
    Determines the Content for a given ComponentVersion.

    An ComponentVersion may be associated with multiple pieces of binary data.
    For instance, a Video ComponentVersion might be associated with multiple
    transcripts in different languages.

    When Content is associated with an ComponentVersion, it has some local
    identifier that is unique within the the context of that ComponentVersion.
    This allows the ComponentVersion to do things like store an image file and
    reference it by a "path" identifier.

    Content is immutable and sharable across multiple ComponentVersions and even
    across LearningPackages.
    """

    component_version = models.ForeignKey(ComponentVersion, on_delete=models.CASCADE)
    content = models.ForeignKey(Content, on_delete=models.RESTRICT)
    identifier = identifier_field()

    class Meta:
        constraints = [
            # Uniqueness is only by ComponentVersion and identifier. If for some
            # reason a ComponentVersion wants to associate the same piece of
            # content with two different identifiers, that is permitted.
            models.UniqueConstraint(
                fields=["component_version", "identifier"],
                name="componentversioncontent_uniq_cv_id",
            ),
        ]
        indexes = [
            models.Index(
                fields=["content", "component_version"],
                name="componentversioncontent_c_cv",
            ),
            models.Index(
                fields=["component_version", "content"],
                name="componentversioncontent_cv_d",
            ),
        ]
