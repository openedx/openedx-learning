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
from django.conf import settings

from openedx_learning.lib.fields import (
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
    prev_version = models.ForeignKey(LearningContext, on_delete=models.RESTRICT, null=True, related_name='+')
    created = manual_date_time_field()


# Placeholder:
"""
class PublishLog(models.Model):
    learning_context = models.ForeignKey(LearningContext, on_delete=models.CASCADE)
    version_num = models.PositiveIntegerField()

    # Note: The same LearningContextVersion can show up multiple times if it's
    # the case that something was reverted to an earlier version.
    learning_context_version = models.ForeignKey(LearningContextVersion, on_delete=models.RESTRICT)

    published_at = manual_date_time_field()
    published_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True)

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
"""
