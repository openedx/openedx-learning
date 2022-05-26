"""
Idea: This app has _only_ things related to Publishing any kind of content
associated with a LearningContext. So in that sense:

* LearningContext (might even go elsewhere)
* LearningContextVersion 
* something to mark that an app has created a version for an LC
* something to handle errors
* a mixin for doing efficient version tracking

"""
from django.db import models

from openedx_learning.lib.fields import (
    hash_field,
    identifier_field,
    immutable_uuid_field,
    manual_date_time_field,
)


class LearningContext(models.Model):
    uuid = immutable_uuid_field()
    identifier = identifier_field()
    created = manual_date_time_field()

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
    created = manual_date_time_field()


class PublishLog(models.Model):
    """
    
    """
    learning_context = models.ForeignKey(LearningContext, on_delete=models.CASCADE)
    version_num = models.PositiveIntegerField()

    # Note: The same LearningContextVersion can show up multiple times if it's
    # the case that something was reverted to an earlier version.
    learning_context_version = models.ForeignKey(LearningContextVersion, on_delete=models.RESTRICT)

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
                name="learning_publish_pl_uniq_lc_vn",
            )
        ]


class ItemRaw(models.Model):
    """
    This is the most basic piece of raw Item content data, with no metadata.

    ItemRaw stores data in a Binary BLOB `data` field. This data is not
    normalized in any way, meaning that pieces of content that are semantically
    equivalent (e.g. differently spaced/sorted JSON) will result in new entries.
    This model is intentionally ignorant of what these things mean, because it
    expects supplemental data models to build on top of it.

    The other fields on ItemRaw are for data that is intrinsic to the file data
    itself (e.g. the size). Any smart parsing of the contents into more
    structured metadata should happen in other models that hang off of ItemInfo.
 
    ItemRaw models are not versioned in any way. The concept of versioning
    exists at a higher level.

    TODO: Size limit thoughts–configurable? Start at 10 MB?
    """
    learning_context = models.ForeignKey(LearningContext, on_delete=models.CASCADE)
    hash_digest = hash_field()

    # Per RFC 4288, MIME type and sub-type may each be 127 chars. Add one more
    # char for the '/' in the middle, and we're at 255.
    mime_type = models.CharField(max_length=255, blank=False, null=False)
    size = models.PositiveBigIntegerField()

    # This should be manually set so that multiple ItemRaw rows being set in the
    # same transaction are created with the same timestamp. The timestamp should
    # be UTC.
    created = manual_date_time_field()

    data = models.BinaryField(null=False)

    class Meta:
        constraints = [
            # Make sure we don't store duplicates of this raw data within the
            # same LearningContext, unless they're of different mime types.
            models.UniqueConstraint(
                fields=["learning_context_id", "mime_type", "hash_digest"],
                name="learning_publishing_item_raw_uniq_lc_hd",
            )
        ]


class ItemInfo(models.Model):
    """

    """
    uuid = immutable_uuid_field()
    learning_context = models.ForeignKey(LearningContext, on_delete=models.CASCADE)
    type = models.CharField(max_length=100)
    item_raw = models.ForeignKey(ItemRaw, on_delete=models.RESTRICT)

    created = manual_date_time_field()


class Item(models.Model):
    """
    This represents any content that has ever existed in a LearningContext.
    """
    uuid = immutable_uuid_field()
    learning_context = models.ForeignKey(LearningContext, on_delete=models.CASCADE)
    identifier = identifier_field()

    published_version = models.ForeignKey('ItemVersion', on_delete=models.RESTRICT, null=True, related_name="+")
    first_published_at = models.DateTimeField(null=True)  # can be null if never published 
    last_published_at = models.DateTimeField(null=True)   # can be null if never published

    created = manual_date_time_field()
    modified = manual_date_time_field()

    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=["learning_context_id", "identifier"],
                name="learning_publishing_lcb_one_identifier_per_lc",
            )
        ]

    def __str__(self):
        return f"{self.identifier}"


class ItemVersion(models.Model):
    """
    """
    uuid = immutable_uuid_field()
    item_info = models.ForeignKey(ItemInfo, on_delete=models.RESTRICT)
    item = models.ForeignKey(Item, on_delete=models.CASCADE)
    title = models.CharField(max_length=1000, blank=True, null=True)

    def __str__(self):
        return f"{self.uuid}: {self.title}"


class LearningContextVersionItemVersion(models.Model):
    learning_context_version = models.ForeignKey(LearningContextVersion, on_delete=models.CASCADE)
    item_version = models.ForeignKey(ItemVersion, on_delete=models.PROTECT)
