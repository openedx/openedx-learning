"""
Idea: This app has _only_ things related to Publishing any kind of content
associated with a LearningPackage. So in that sense:

* LearningPackage (might even go elsewhere)
* something to mark that an app has created a version for an LP
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


class LearningPackage(models.Model):
    uuid = immutable_uuid_field()
    identifier = identifier_field()
    title = models.CharField(max_length=1000, null=False, blank=False)

    created = manual_date_time_field()
    updated = manual_date_time_field()

    def __str__(self):
        return f"{self.identifier} ({self.uuid})"

    class Meta:
        constraints = [
            # LearningPackage identifiers must be globally unique. This is
            # something that might be relaxed in the future if this system were
            # to be extensible to something like multi-tenancy, in which case
            # we'd tie it to something like a Site or Org.
            models.UniqueConstraint(fields=["identifier"], name="lp_uniq_identifier")
        ]


class PublishLogEntry(models.Model):
    """
    This model tracks Publishing activity.

    It is expected that other apps make foreign keys to this table to mark when
    their content gets published.
    """
    uuid = immutable_uuid_field()
    learning_package = models.ForeignKey(LearningPackage, on_delete=models.CASCADE)
    published_at = manual_date_time_field()
    published_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
    )
