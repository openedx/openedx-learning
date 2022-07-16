"""
The item model hiearachy is: Item -> ItemVersion -> Content

Item is the versionless thing that is guaranteed to exist for the lifetime of
the LearningContext. An ItemVersion is a different version of that item for a
given LearningContext, and may include policy changes (like grading). Content
represents the raw byte data.
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

    An Item will have many ItemVersions over time, and most metadata is
    associated with the ItemVersion model. Make a foreign key to this model when
    you need a stable reference that will exist for as long as the
    LearningContext itself exists. It is possible for an Item to have no active
    ItemVersion in the current LearningContextVersion (i.e. this content was at
    some point removed from the "published" version).

    An Item belongs to one and only one LearningContext.

    The UUID should be treated as immutable. The identifier field *is* mutable,
    but changing it will affect all ItemVersions.
    """
    uuid = immutable_uuid_field()
    learning_context = models.ForeignKey(LearningContext, on_delete=models.CASCADE)
    identifier = identifier_field()

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

    A new ItemVersion should be created anytime there is either a change to the
    content or a change to the policy around a piece of content (e.g. schedule
    change).
    
    Each ItemVersion belongs to one and only one Item.
    """
    uuid = immutable_uuid_field()

    item = models.ForeignKey(Item, on_delete=models.CASCADE)

    # Question: Title is the only thing here that actually has human-readable
    # text. Does it make sense to lift it out into a separate metadata model,
    # possibly even one with language awareness?
    title = models.CharField(max_length=1000, blank=True, null=True)

    created = manual_date_time_field()

    def __str__(self):
        return f"{self.uuid}: {self.title}"


class LearningContextVersionItemVersion(models.Model):
    """
    Mapping of all ItemVersion in a given LearningContextVersion.

    TODO: Should the publish app have a model to subclass for this?
    """
    learning_context_version = models.ForeignKey(LearningContextVersion, on_delete=models.CASCADE)
    item_version = models.ForeignKey(ItemVersion, on_delete=models.RESTRICT)


class Content(models.Model):
    """
    This is the most basic piece of raw content data, with no version metadata.

    Content stores data in a Binary BLOB `data` field. This data is not
    normalized in any way, meaning that pieces of content that are semantically
    equivalent (e.g. differently spaced/sorted JSON) will result in new entries.
    This model is intentionally ignorant of what these things mean, because it
    expects supplemental data models to build on top of it.

    The other fields on Content are for data that is intrinsic to the file data
    itself (e.g. the size). Any smart parsing of the contents into more
    structured metadata should happen in other models that hang off of ItemInfo.
 
    Content models are not versioned in any way. The concept of versioning
    exists at a higher level.

    
    """
    # Cap item size at 10 MB for now.
    MAX_SIZE = 10_000_000

    learning_context = models.ForeignKey(LearningContext, on_delete=models.CASCADE)
    hash_digest = hash_field()

    # Per RFC 4288, MIME type and sub-type may each be 127 chars. Add one more
    # char for the '/' in the middle, and we're at 255.
    mime_type = models.CharField(max_length=255, blank=False, null=False)
    size = models.PositiveBigIntegerField(max=MAX_SIZE)

    # This should be manually set so that multiple Content rows being set in the
    # same transaction are created with the same timestamp. The timestamp should
    # be UTC.
    created = manual_date_time_field()

    data = models.BinaryField(null=False, max_length=MAX_SIZE)

    class Meta:
        constraints = [
            # Make sure we don't store duplicates of this raw data within the
            # same LearningContext, unless they're of different mime types.
            models.UniqueConstraint(
                fields=["learning_context_id", "mime_type", "hash_digest"],
                name="learning_publishing_content_uniq_lc_hd",
            )
        ]

class ItemVersionContent(models.Model):
    item_version = models.ForeignKey(ItemVersion, on_delete=models.CASCADE)
    content = models.ForeignKey(ItemVersion, on_delete=models.RESTRICT)
    identifier = identifier_field()

    class Meta:
        constraints = [
            # 
            models.UniqueConstraint(
                fields=["item_version_id", "identifier"],
                name="learning_publishing_item_version_content_iv_id",
            )
        ]



