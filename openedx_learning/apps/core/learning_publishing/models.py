"""

"""
from django.db import models
from model_utils.models import TimeStampedModel

from openedx_learning.lib.fields import hash_field, identifier_field, immutable_uuid_field


class LearningContext(models.Model):
    uuid = immutable_uuid_field()
    identifier = identifier_field()

    def __str__(self):
        return f"LearningContext {self.uuid}: {self.identifier}"

    class Meta:
        constraints = [
            # LearningContext identifiers must be globally unique. This is
            # something that might be relaxed in the future if this system were
            # to be extensible to something like multi-tenancy, in which case
            # we'd tie it to something like a Site or Org.
            models.UniqueConstraint(fields=["identifier"], name="learning_publishing_lc_uniq_identifier")
        ]

class LearningContextVersion(models.Model):
    """
    """
    uuid = immutable_uuid_field()
    learning_context = models.ForeignKey(LearningContext, on_delete=models.CASCADE)
    version_num = models.PositiveIntegerField()

    class Meta:
        constraints = [
            # LearningContextVersions are created in a linear history, because
            # every version is intended as either a published version or a draft
            # version that is a candidate for publishing. In the event of a race
            # condition of two processes that are trying to publish the "next"
            # version, we should only allow one to win, and fail the other one
            # so that it has to re-read and re-try (instead of silently
            # overwriting).
            models.UniqueConstraint(
                fields=["learning_context_id", "version_num"],
                name="learning_publishing_lcv_uniq_lc_vn",
            )
        ]


class ContentPackage(models.Model):
    """
    A ContentPackage is an unversioned collection of Content without Policy.

    ContentPackages exist as a mechanism for sharing content between different
    LearningContexts. A LearningContext may have one or more ContentPackages.
    For example, a Content Library might have one ContentPackage, while a Course
    will use the ContentPackages from several different libraries, as well as
    having one of its own.

    A ContentPackage belongs to one particular LearningContext, but may also be
    accessed from other LearningContexts. The owning LearningContext sets the
    default policy settings.

    ContentPackages aren't separately versioned. Or rather, the ContentPackage
    represents all the content that has ever existed for it at once, and the
    versioning happens at the LearningContextVersion layer.
    """
    uuid = immutable_uuid_field()

    # TODO: Should ContentPackages have identifiers or titles? Are those only
    #       given by the LearningContext in some third, joining model?

    # TODO: What is the behavior when the LearningContext is deleted, w.r.t.
    #       other LearningContexts that might use this ContentPackage?
    learning_context = models.ForeignKey(LearningContext, on_delete=models.CASCADE)


class BlockType(models.Model):
    """
    Data we want to track:

    * Abstract type, from the LMS's point of view (e.g. an atomic leaf thing vs.
      a whole sequence).
    * What is the subsystem that understands more about this (e.g. XBlock)?
    * Classification of this thing within the subsystem (e.g 'problem').

    Need to add another field?
    """
    major = models.CharField(
        max_length=50,
        blank=False,
        null=False,
        help_text="Major types include 'block', 'unit', and 'sequence'."
    )
    minor = models.CharField(
        max_length=50,
        blank=True,
        null=False,
    )

    def __str__(self):
        return f"{self.major}:{self.minor}"


class ContentAtom(models.Model):
    """
    This is the most basic piece of content data, with no metadata.

    It can encode text, json, or binary data. It has no identity beyond a hash
    of its payload data (text/json/binary). It is scoped to a ContentPackage,
    and not shared across ContentPackages. These are not versioned in any way.
    The concept of versioning exists at a higher level.

    TODO: Maybe this would be better as separate classes for BinaryAtom,
          TextAtom, and JSONAtom? Would make joins for mixed content awkward,
          wouldn't it?
    """
    # We'll scope this ContentAtom to a specific ContentPackage both for
    # security reasons (e.g. malicious hash collision), and also to make cleanup
    # simpler when a ContentPackage is deleted.
    content_package = models.ForeignKey(ContentPackage, on_delete=models.CASCADE)

    # Hash has to mime_type + text_data + json_data + bin_data. We'll need some
    # kind of prefixing to make sure we don't get hash collisions when something
    # tries to store binary data that happens to match text data for the same
    # type of ContentAtom.
    hash_digest = hash_field()

    # Per RFC 4288, MIME type and sub-type may each be 127 chars. Add one more
    # char for the '/' in the middle, and we're at 255.
    mime_type = models.CharField(max_length=255, blank=False, null=False)

    # Typicaly only one of these would be used at a given time. Maybe these
    # should just be made into separate models?
    text_data = models.TextField(null=True)
    json_data = models.JSONField(null=True)
    bin_data = models.BinaryField(null=True)


    size = models.PositiveBigIntegerField()

    class Meta:
        constraints = [
            # Make sure we don't store duplicates of this raw data within the
            # same ContentPackage.
            models.UniqueConstraint(
                fields=["content_package_id", "hash_digest"],
                name="learning_publishing_ca_uniq_cp_hd",
            )
        ]


class ContentSegment(models.Model):
    """
    A ContentSegment is an ordered list of contiguous ContentObjects.

    This represents a short list of ContentObjects that are so tightly bound to
    each other, that it does not make sense to display any of them separately.
    For example, we could have a Video and a Problem that asks specific
    questions about the video. They may use different rendering systems, but the
    content in them is strongly connected.
    """
    uuid = immutable_uuid_field()
    identifier = identifier_field()


class ContentObject(models.Model):
    """
    Represents the combined content for a single renderable piece.

    This does _not_ include things that we consider policy-related metadata.

    An example piece of content could be the entirety of content associated with
    one particular XBlock block, e.g. a ProblemBlock. This model has almost no
    data associated with it because that data is mostly encoded in
    ContentObjectParts.


    Does it make sense to get rid of the concept of ContentSegment and instead
    think of it as two ContentObjectParts with type application/x+xblock ? With
    ordering done via naming like 0/html_identifier, 1/problem_identifier?

    That would tie the versioned thing to the ContentObjectPart instead of the
    ContentObject.


    """
    uuid = immutable_uuid_field()
    content_segment = models.ForeignKey(ContentSegment, on_delete=models.CASCADE)
    segment_order_num = models.PositiveIntegerField()

    class Meta:
        constraints = [
            # Make sure we don't get ordering conflicts between ContentObjects
            # in the same ContentSegment.
            models.UniqueConstraint(
                fields=["content_segment_id", "segment_order_num"],
                name="learning_publishing_co_uniq_cs_son",
            )
        ]


class ContentObjectPart(models.Model):
    """
    A single piece of a ContentObject, with an identifier and MIME type.

    Many individual Blocks are logically several assets tied together. For
    example:

    * ProblemBlocks have an XML definition of the problem, as well as separate
      entries for an associated static assets. We could also potentially
      separate grading code into a separate part.
    * HTMLBlocks have an XML definition, but also an HTML file, and associated
      assets.
    * VideoBlocks have an XML definition with attributes, but they can also have
      text transcript files (.srt or .vtt).
    
    Each entry may be treated like a file, but does not have to be.
    """
    uuid = immutable_uuid_field()
    identifier = identifier_field()
    content_object = models.ForeignKey(ContentObject, on_delete=models.CASCADE)
    content_atom = models.ForeignKey(ContentAtom, on_delete=models.RESTRICT)

    class Meta:
        constraints = [
            # Within the same ContentObject, each ContentObjectPart should have
            # a unique identifier.
            models.UniqueConstraint(
                fields=["content_object_id", "identifier"],
                name="learning_publishing_cop_uniq_co_identifier",
            )
        ]


#class BlockVersion(models.Model):
#    uuid = immutable_uuid_field()
#    content = models.ForeignKey(ContentObject, on_delete=models.RESTRICT)
#    identifier = identifier_field(unique=False)
#
#    title = models.CharField(max_length=1000, blank=True, null=True)
#
#    def __str__(self):
#        return f"{self.uuid}: {self.title}"

