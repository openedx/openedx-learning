"""
The model hierarchy is Component -> Content.

Content is a simple model holding unversioned, raw data, along with some simple
metadata like size and MIME type.

Multiple pieces of Content may be associated with a Component. A Component is a
versioned thing that maps to a single Component Handler. This might be a Video,
a Problem, or some explanatatory HTML.
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
    active ComponentVersion (i.e. this content was at some point removed).

    A Component belongs to one and only one LearningPackage.

    The UUID should be treated as immutable. The identifier field *is* mutable,
    but changing it will affect all ComponentVersions.
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
    modified = manual_date_time_field()

    class Meta:
        constraints = [
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
        verbose_name = "Component"
        verbose_name_plural = "Components"

    def __str__(self):
        return f"{self.identifier}"


class ComponentVersion(models.Model):
    """
    A particular version of a Component.

    A new ComponentVersion should be created anytime there is either a change to
    the content or a change to the policy around a piece of content (e.g.
    schedule change).

    Each ComponentVersion belongs to one and only one Component.
    """

    uuid = immutable_uuid_field()
    component = models.ForeignKey(Component, on_delete=models.CASCADE)
    title = models.CharField(max_length=1000, default="", null=False, blank=True)
    version_num = models.PositiveBigIntegerField(
        null=False,
        validators=[MinValueValidator(1)],  # Versions start with 1
    )
    created = manual_date_time_field()

    # For later consideration:
    # created_by = models.ForeignKey(
    #    settings.AUTH_USER_MODEL,
    #    # Don't delete content when the user who created it had their account removed.
    #    on_delete=models.SET_NULL,
    #

    contents = models.ManyToManyField(
        "Content",
        through="ComponentVersionContent",
        related_name="component_versions",
    )

    def __str__(self):
        return f"v{self.version_num}: {self.title}"

    class Meta:
        constraints = [
            # We give every ComponentVersion a sequential version_num, and
            # constrain it here. This is both a convenience so that people can
            # refer to
            models.UniqueConstraint(
                fields=[
                    "component",
                    "version_num",
                ],
                name="cv_uniq_component_version_num",
            )
        ]
        indexes = [
            # Make it cheap to find the most recently created ComponentVersion
            # for a given Component.
            models.Index(
                fields=["component", "-created"],
                name="cv_component_rev_created",
            ),
        ]
        verbose_name = "Component Version"
        verbose_name_plural = "Component Versions"


class ComponentPublishLogEntry(models.Model):
    """
    This is a historical record of Component publishing.
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
    show up in this table).
    """

    component = models.OneToOneField(
        Component,
        on_delete=models.RESTRICT,
        primary_key=True
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

    # Per RFC 4288, MIME type and sub-type may each be 127 chars.
    media_type = models.CharField(max_length=127, blank=False, null=False)
    media_subtype = models.CharField(max_length=127, blank=False, null=False)

    size = models.PositiveBigIntegerField(
        validators=[MaxValueValidator(MAX_SIZE)],
    )

    # This should be manually set so that multiple Content rows being set in the
    # same transaction are created with the same timestamp. The timestamp should
    # be UTC.
    created = manual_date_time_field()

    data = models.BinaryField(null=False, max_length=MAX_SIZE)

    @property
    def mime_type(self):
        return f"{self.media_type}/{self.media_subtype}"

    class Meta:
        constraints = [
            # Make sure we don't store duplicates of this raw data within the
            # same LearningPackage, unless they're of different mime types.
            models.UniqueConstraint(
                fields=[
                    "learning_package",
                    "media_type",
                    "media_subtype",
                    "hash_digest",
                ],
                name="content_uniq_lc_hd",
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
