import uuid

from django.db import models
from django.conf import settings
from model_utils.models import TimeStampedModel
from simple_history.models import HistoricalRecords

from openedx_learning.lib.fields import hash_field, identifier_field, immutable_uuid_field

from ..learning_publishing.models import ContentObject


class LearningContextType(models.Model):
    # Identifier
    identifier = models.CharField(max_length=100, blank=False, null=False)


class LearningContext(TimeStampedModel):
    """
    A LearningContext represents a set of content that is versioned together.

    Courses and Content Libraries are examples.

    .. no_pii:
    """
    uuid = immutable_uuid_field()
    identifier = identifier_field(unique=True)

    # Don't allow deletion of LearningContextTypes.
    type = models.ForeignKey(LearningContextType, on_delete=models.RESTRICT)
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, null=True, on_delete=models.SET_NULL
    )

    class Meta:
        verbose_name = "Learning Context"


    def __str__(self):
        """
        Get a string representation of this model instance.
        """
        # TODO: return a string appropriate for the data fields
        return "<PublishedLearningContext, ID: {}>".format(self.id)


class LearningContextVersion(TimeStampedModel):
    """
    What's a Context Version?

    .. no_pii:
    """
    uuid = immutable_uuid_field()
    identifier = identifier_field(unique=False)

    # TODO: Replace this with something that doesn't require opaque-keys
    learning_context = models.ForeignKey(LearningContext, on_delete=models.CASCADE)
    title = models.CharField(max_length=255, db_index=True)


class Block(models.model):
    uuid = immutable_uuid_field()


class BlockVersion(models.Model):
    """
    Blocks represent a single addressible piece of learning content.

    * It is tied to a single LearningContextVersion.
    * It is deleted when its LearningContextVersion is deleted.
    * It's the model other apps should make a ForeignKey into when associating
      data for this particular LearningContextVersion, e.g. content partition
      groups.
    * Multiple BlockVersions can exist pointing to the same ContentObject for
      the same LearningContext. Example: Using the same problem from a content
      library in multiple places in the same course.

    This gives us a table that gets thrashed a lot (each version must make all
    the rows again). But it gives us some predictability (initial publish and
    incremental publish are largely the same in terms of cost), and makes it
    easier to clean up (all Blocks for a LearningContextVersion can be deleted
    when that LearningContextVersion is deleted).

    If you have data that should be deleted whenever a LearingContextVersion is
    deleted, make it a foreign key against this model.
    """
    uuid = immutable_uuid_field(unique=True)
    learning_context_version = models.ForeignKey(LearningContextVersion, on_delete=models.CASCADE)
    identifier = identifier_field(unique=False)
    content_object = models.ForeignKey(ContentObject, on_delete=models.RESTRICT)

    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=["learning_context_version_id", "identifier"],
                name="one_block_identifier_per_learning_context_version",
            )
        ]






class LearningContextBranch(TimeStampedModel):
    """
    What's a Branch?

    .. no_pii:
    """
    learning_context = models.ForeignKey(LearningContext, on_delete=models.CASCADE)
    branch_name = models.CharField(max_length=100)

    # The intent of having on_delete=RESTRICT for version and on_delete=CASCADE
    # for learning_context is to say, "You can't delete the version that is
    # being pointed to by a branch (because it might be the live version that
    # students are using), but if you're deleting _the entire Learning Context_,
    # then it's fine to delete the branch pointer info as well."
    version = models.ForeignKey(LearningContextVersion, on_delete=models.RESTRICT)

    history = HistoricalRecords()

    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=["learning_context_id", "branch_name"],
                name="one_branch_per_learning_context",
            )
        ]
