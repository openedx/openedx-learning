"""

"""
from django.db import models
from model_utils.models import TimeStampedModel

from openedx_learning.lib.fields import hash_field, identifier_field, immutable_uuid_field


class LearningContext(models.Model):
    uuid = immutable_uuid_field()
    identifier = identifier_field(unique=True)

    def __str__(self):
        return f"{self.uuid}: {self.identifier}"

class LearningContextVersion(models.Model):
    """
    We actually rely on 
    """
    uuid = immutable_uuid_field()
    identifier = identifier_field(unique=False)
    version_num = models.PositiveIntegerField()


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


class LearningContextBlock(models.Model):
    """
    This represents any Block that has ever existed in a LearningContext.

    Notes:
    * I think it's feasible 
    """
    learning_context = models.ForeignKey(LearningContext, on_delete=models.CASCADE)
    uuid = immutable_uuid_field()
    identifier = identifier_field(unique=False)
    block_type = models.ForeignKey(BlockType, on_delete=models.RESTRICT)

    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=["learning_context_id", "identifier"],
                name="learning_publishing_lcb_one_identifier_per_lc",
            )
        ]

    def __str__(self):
        return f"{self.identifier}"


class BlockContent(models.Model):
    """
    Holds the basic content data.

    A few notes:
    
    This shouldn't be connected to LearningContexts directly, but to a
    ContentPackage. A LearningContext can use multiple ContentPackages, and
    multiple LearningContexts can use the same ContentPackage.
    
    We don't want this data in BlockVersion because:

      1. If something is deleted and recreated across versions (e.g. accidental
         deletion followed by re-upload), we don't want to have to re-upload
         everything.
      2. There are minor savings to be had by redundant content (e.g. some HTML
         templates that are repeated).
      3. We want to allow BlockVersion queries without fetching a bunch of extra
         content data by accident.
      4. We need to be able to reuse the same BlockContent in multiple
         LearningContexts, e.g. the Content Library use case.
    """
    learning_context = models.ForeignKey(LearningContext, on_delete=models.CASCADE)
    hash_digest = hash_field(unique=False)
    data = models.TextField()

    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=["learning_context_id", "hash_digest"],
                name="learning_publishing_bc_unique_content_hash",
            )
        ]


class BlockVersion(models.Model):
    """
    Maybe this is also associated with the Content
    """
    LAST_VERSION_NUM = 2147483647
    block = models.ForeignKey(LearningContextBlock, on_delete=models.RESTRICT)
    content = models.ForeignKey(BlockContent, on_delete=models.RESTRICT)

    uuid = immutable_uuid_field()
    start_version_num = models.PositiveIntegerField()
    end_version_num = models.PositiveIntegerField(default=LAST_VERSION_NUM)

    title = models.CharField(max_length=1000, blank=True, null=True)

    def __str__(self):
        return f"{self.uuid}: {self.title}"


class ContentPackage(models.Model):
    uuid = immutable_uuid_field()
    identifier = identifier_field(unique=True)
