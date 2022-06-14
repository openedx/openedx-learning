"""
The item model hiearachy is: Item -> ItemVersion -> ItemInfo -> ItemRaw

Item is the versionless thing that is guaranteed to exist for the lifetime of
the LearningContext. An ItemVersion is a different version of that item for a
given LearningContext, and may include policy changes (like grading). ItemInfo
covers basic metadata that is intrinsic to the item itself, and now how it's
used in a LearningContext. ItemRaw represents the raw byte data.

TODO: Add link to ADR after it merges.
"""
from django.db import models

from openedx_learning.lib.fields import (
    hash_field,
    identifier_field,
    immutable_uuid_field,
    manual_date_time_field,
)
from ..publish.models import LearningContext, LearningContextVersion


class Item(models.Model):
    """
    This represents any content that has ever existed in a LearningContext.
    """
    uuid = immutable_uuid_field()
    learning_context = models.ForeignKey(LearningContext, on_delete=models.CASCADE)
    identifier = identifier_field()

    # TODO: These pointers to the latest published version are convenient, but
    # we don't currently have the data integrity guarantees to make sure that 
    # multiple versions aren't active at the same time. Maybe add a ref to the
    # Item model in LearningContextVersionItemVersion, so we can force that
    # constraint?
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
    A particular version of an Item.

    A new ItemVersion is created anytime there is either a change to the content
    or a change to the policy around a piece of content (e.g. schedule change).
    """
    uuid = immutable_uuid_field()
    item_raw = models.ForeignKey('ItemRaw', on_delete=models.RESTRICT)
    item = models.ForeignKey(Item, on_delete=models.CASCADE)
    title = models.CharField(max_length=1000, blank=True, null=True)

    created = manual_date_time_field()

    def __str__(self):
        return f"{self.uuid}: {self.title}"


class LearningContextVersionItemVersion(models.Model):
    learning_context_version = models.ForeignKey(LearningContextVersion, on_delete=models.CASCADE)
    item_version = models.ForeignKey(ItemVersion, on_delete=models.RESTRICT)


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
