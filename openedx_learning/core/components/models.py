"""
The model hierarchy is Component -> ComponentVersion -> RawContent.

A Component is an entity like a Problem or Video. It has enough information to
identify the Component and determine what the handler should be (e.g. XBlock
Problem), but little beyond that.

Components have one or more ComponentVersions, which represent saved versions of
that Component. At any time, there is at most one published ComponentVersion for
a Component in a LearningPackage (there can be zero if it's unpublished). The
publish status is tracked in PublishedComponent, with historical publish data in
ComponentPublishLogEntry.

RawContent is a simple model holding unversioned, raw data, along with some
simple metadata like size and MIME type.

Multiple pieces of RawContent may be associated with a ComponentVersion, through
the ComponentVersionRawContent model. ComponentVersionRawContent allows to
specify a Component-local identifier. We're using this like a file path by
convention, but it's possible we might want to have special identifiers later.
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
    This represents any Component that has ever existed in a LearningPackage.

    What is a Component
    -------------------

    A Component is an entity like a Problem or Video. It has enough information
    to identify itself and determine what the handler should be (e.g. XBlock
    Problem), but little beyond that.

    A Component will have many ComponentVersions over time, and most metadata is
    associated with the ComponentVersion model and the RawContent that
    ComponentVersions are associated with.

    A Component belongs to one and only one LearningPackage.

    How to use this model
    ---------------------

    Make a foreign key to the Component model when you need a stable reference
    that will exist for as long as the LearningPackage itself exists. It is
    possible for an Component to have no published ComponentVersion, either
    because it was never published or because it's been "deleted" (made
    unavailable) at some point, but the Component will continue to exist.

    The UUID should be treated as immutable.

    The identifier field *is* mutable, but changing it will affect all
    ComponentVersions.

    If you are referencing this model from within the same process, use a
    foreign key to the id. If you are referencing this Component from an
    external system/service, use the UUID. The identifier is the part that is
    most likely to be human-readable, and may be exported/copied, but try not to
    rely on it, since this value may change.

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
    via a M:M relationship with RawContent via ComponentVersionRawContent.

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
    raw_contents = models.ManyToManyField(
        "RawContent",
        through="ComponentVersionRawContent",
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
                fields=[
                    "title",
                ],
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


class RawContent(models.Model):
    """
    This is the most basic piece of raw content data, with no version metadata.

    RawContent stores data using the "file" field. This data is not
    auto-normalized in any way, meaning that pieces of content that are
    semantically equivalent (e.g. differently spaced/sorted JSON) may result in
    new entries. This model is intentionally ignorant of what these things mean,
    because it expects supplemental data models to build on top of it.

    Two RawContent instances _can_ have the same hash_digest if they are of
    different MIME types. For instance, an empty text file and an empty SRT file
    will both hash the same way, but be considered different entities.

    The other fields on RawContent are for data that is intrinsic to the file
    data itself (e.g. the size). Any smart parsing of the contents into more
    structured metadata should happen in other models that hang off of
    RawContent.

    RawContent models are not versioned in any way. The concept of versioning
    only exists at a higher level.

    RawContent is optimized for cheap storage, not low latency. It stores
    content in a FileField. If you need faster text access across multiple rows,
    add a TextContent entry that corresponds to the relevant RawContent.

    If you need to transform this RawContent into more structured data for your
    application, create a model with a OneToOneField(primary_key=True)
    relationship to RawContent. Just remember that *you should always create the
    RawContent entry* first, to ensure content is always exportable, even if
    your app goes away in the future.
    """

    # 50 MB is our current limit, based on the current Open edX Studio file
    # upload size limit.
    MAX_FILE_SIZE = 50_000_000

    learning_package = models.ForeignKey(LearningPackage, on_delete=models.CASCADE)

    # This hash value may be calculated using create_hash_digest from the
    # openedx.lib.fields module.
    hash_digest = hash_field()

    # MIME type, such as "text/html", "image/png", etc. Per RFC 4288, MIME type
    # and sub-type may each be 127 chars, making a max of 255 (including the "/"
    # in between).
    #
    # DO NOT STORE parameters here, e.g. "charset=". We can make a new field if
    # that becomes necessary.
    mime_type = models.CharField(max_length=255, blank=False, null=False)

    # This is the size of the raw data file in bytes. This can be different than
    # the character length, since UTF-8 encoding can use anywhere between 1-4
    # bytes to represent any given character.
    size = models.PositiveBigIntegerField(
        validators=[MaxValueValidator(MAX_FILE_SIZE)],
    )

    # This should be manually set so that multiple RawContent rows being set in
    # the same transaction are created with the same timestamp. The timestamp
    # should be UTC.
    created = manual_date_time_field()

    # All content for the LearningPackage should be stored in files. See model
    # docstring for more details on how to store this data in supplementary data
    # models that offer better latency guarantees.
    file = models.FileField(
        null=True,
        storage=settings.OPENEDX_LEARNING.get(
            "STORAGE",
            settings.DEFAULT_FILE_STORAGE,
        ),
    )

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
            #   * Break down Content counts by type/subtype with in a
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
            ),
        ]
        verbose_name = "Raw Content"
        verbose_name_plural = "Raw Contents"


class TextContent(models.Model):
    """
    TextContent supplements RawContent to give an in-table text copy.

    This model exists so that we can have lower-latency access to this data,
    particularly if we're pulling back multiple rows at once.

    Apps are encouraged to create their own data models that further extend this
    one with a more intelligent, parsed data model. For example, individual
    XBlocks might parse the OLX in this model into separate data models for
    VideoBlock, ProblemBlock, etc.

    The reason this is built directly into the Learning Core data model is
    because we want to be able to easily access and browse this data even if the
    app-extended models get deleted (e.g. if they are deprecated and removed).
    """

    # 100K is our limit for text data, like OLX. This means 100K *characters*,
    # not bytes. Since UTF-8 encodes characters using as many as 4 bytes, this
    # couled be as much as 400K of data if we had nothing but emojis.
    MAX_TEXT_LENGTH = 100_000

    raw_content = models.OneToOneField(
        RawContent,
        on_delete=models.CASCADE,
        primary_key=True,
        related_name="text_content",
    )
    text = models.TextField(null=False, blank=True, max_length=MAX_TEXT_LENGTH)
    length = models.PositiveIntegerField(null=False)


class ComponentVersionRawContent(models.Model):
    """
    Determines the RawContent for a given ComponentVersion.

    An ComponentVersion may be associated with multiple pieces of binary data.
    For instance, a Video ComponentVersion might be associated with multiple
    transcripts in different languages.

    When RawContent is associated with an ComponentVersion, it has some local
    identifier that is unique within the the context of that ComponentVersion.
    This allows the ComponentVersion to do things like store an image file and
    reference it by a "path" identifier.

    RawContent is immutable and sharable across multiple ComponentVersions and
    even across LearningPackages.
    """

    raw_content = models.ForeignKey(RawContent, on_delete=models.RESTRICT)
    component_version = models.ForeignKey(ComponentVersion, on_delete=models.CASCADE)

    uuid = immutable_uuid_field()
    identifier = identifier_field()

    # Is this RawContent downloadable during the learning experience? This is
    # NOT about public vs. private permissions on course assets, as that will be
    # a policy that can be changed independently of new versions of the content.
    # For instance, a course team could decide to flip their course assets from
    # private to public for CDN caching reasons, and that should not require
    # new ComponentVersions to be created.
    #
    # What the ``learner_downloadable`` field refers to is whether this asset is
    # supposed to *ever* be directly downloadable by browsers during the
    # learning experience. This will be True for things like images, PDFs, and
    # video transcript files. This field will be False for things like:
    #
    # * Problem Block OLX will contain the answers to the problem. The XBlock
    #   runtime and ProblemBlock will use this information to generate HTML and
    #   grade responses, but the the user's browser is never permitted to
    #   actually download the raw OLX itself.
    # * Many courses include a python_lib.zip file holding custom Python code
    #   to be used by codejail to assess student answers. This code will also
    #   potentially reveal answers, and is never intended to be downloadable by
    #   the student's browser.
    # * Some course teams will upload other file formats that their OLX is
    #   derived from (e.g. specially formatted LaTeX files). These files will
    #   likewise contain answers and should never be downloadable by the
    #   student.
    # * Other custom metadata may be attached as files in the import, such as
    #   custom identifiers, author information, etc.
    #
    # Even if ``learner_downloadble`` is True, the LMS may decide that this
    # particular student isn't allowed to see this particular piece of content
    # yet–e.g. because they are not enrolled, or because the exam this Component
    # is a part of hasn't started yet. That's a matter of LMS permissions and
    # policy that is not intrinsic to the content itself, and exists at a layer
    # above this.
    learner_downloadable = models.BooleanField(default=False)

    class Meta:
        constraints = [
            # Uniqueness is only by ComponentVersion and identifier. If for some
            # reason a ComponentVersion wants to associate the same piece of
            # content with two different identifiers, that is permitted.
            models.UniqueConstraint(
                fields=["component_version", "identifier"],
                name="cvrawcontent_uniq_cv_id",
            ),
        ]
        indexes = [
            models.Index(
                fields=["raw_content", "component_version"],
                name="cvrawcontent_c_cv",
            ),
            models.Index(
                fields=["component_version", "raw_content"],
                name="cvrawcontent_cv_d",
            ),
        ]
