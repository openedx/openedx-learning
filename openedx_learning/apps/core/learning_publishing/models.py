"""
High level principles:

1. Easy add and later remove apps without breaking the data model.
2. 
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


class ContentAtom(models.Model):
    """
    This is the most basic piece of content data, with no metadata.

    ContentAtom stores data in a Binary BLOB `data` field. This data is not
    normalized in any way, meaning that pieces of content that are semantically
    equivalent (e.g. differently spaced/sorted JSON) will result in new entries.
    This model is intentionally ignorant of what these things mean, because it
    expects supplemental data models to build on top of it (e.g. put foreign
    keys and 1:1 models against it).

    This model is scoped to a ContentPackage, and not shared across
    ContentPackages. This is both for security reasons (e.g. malicious hash
    collision in some future where BLAKE2 is compromised), and also to make
    cleanup simpler when a ContentPackage is deleted.
    
    ContentAtoms are not versioned in any way. The concept of versioning exists
    at a higher level.

    TODO: Size limit thoughts–configurable? Start at 10 MB?
    """
    # We'll scope this ContentAtom to a specific ContentPackage 
    content_package = models.ForeignKey(ContentPackage, on_delete=models.CASCADE)
    hash_digest = hash_field()

    # Per RFC 4288, MIME type and sub-type may each be 127 chars. Add one more
    # char for the '/' in the middle, and we're at 255.
    mime_type = models.CharField(max_length=255, blank=False, null=False)
    size = models.PositiveBigIntegerField()

    # This should be manually set so that multiple ContentAtoms being set in the
    # same transaction are created with the same timestamp. The timestamp should
    # be UTC.
    created = models.DateTimeField(null=False)

    data = models.BinaryField(null=False)

    class Meta:
        constraints = [
            # Make sure we don't store duplicates of this raw data within the
            # same ContentPackage, unless they're of different mime types.
            models.UniqueConstraint(
                fields=["content_package_id", "mime_type", "hash_digest"],
                name="learning_publishing_ca_uniq_cp_mt_hd",
            )
        ]


class ContentObject(models.Model):
    """
    """
    uuid = immutable_uuid_field()
    type = models.CharField(max_length=100)


class SimpleContentObject(models.Model):
    """
    """
    content_object = models.OneToOneField(ContentObject, on_delete=models.CASCADE, primary_key=True)
    content_atom = models.ForeignKey(ContentAtom, on_delete=models.RESTRICT)


class LearningItem(models.Model):
    """
    This represents any content that has ever existed in a LearningContext.
    """
    uuid = immutable_uuid_field()
    learning_context = models.ForeignKey(LearningContext, on_delete=models.CASCADE)
    identifier = identifier_field()

    currently_published = models.BooleanField()
    last_published = models.DateTimeField(null=True)  # can be null if never published

    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=["learning_context_id", "identifier"],
                name="learning_publishing_lcb_one_identifier_per_lc",
            )
        ]

    def __str__(self):
        return f"{self.identifier}"


class LearningItemVersion(models.Model):
    """
    """
    uuid = immutable_uuid_field()
    content = models.ForeignKey(ContentObject, on_delete=models.RESTRICT)
    learning_block = models.ForeignKey(LearningItem, on_delete=models.CASCADE)
    title = models.CharField(max_length=1000, blank=True, null=True)

    def __str__(self):
        return f"{self.uuid}: {self.title}"


class LearningContextVersionItems(models.Model):
    learning_context_version = models.ForeignKey(LearningContextVersion, on_delete=models.CASCADE)
    learning_block = models.ForeignKey(LearningItemVersion, on_delete=models.PROTECT)


#########

# These would go into separate apps.

class BlockContentObject(models.Model):
    simple_content_object = models.OneToOneField(SimpleContentObject, on_delete=models.CASCADE, primary_key=True)
    type = models.CharField(max_length=100)
    sub_type = models.CharField(max_length=100)


class StaticAssetContentObject(models.Model):
    simple_content_object = models.OneToOneField(SimpleContentObject, on_delete=models.CASCADE, primary_key=True)
