"""
Idea: This app has _only_ things related to Publishing any kind of content
associated with a LearningPackage.
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
        return f"{self.identifier}: {self.title}"

    class Meta:
        constraints = [
            # LearningPackage identifiers must be globally unique. This is
            # something that might be relaxed in the future if this system were
            # to be extensible to something like multi-tenancy, in which case
            # we'd tie it to something like a Site or Org.
            models.UniqueConstraint(fields=["identifier"], name="lp_uniq_identifier")
        ]
        verbose_name = "Learning Package"
        verbose_name_plural = "Learning Packages"


class PublishLogEntry(models.Model):
    """
    This model tracks Publishing activity.

    It is expected that other apps make foreign keys to this table to mark when
    their content gets published. This is to allow us to tie together many
    different entities (e.g. Components, Units, etc.) that are all published at
    the same time.
    """

    uuid = immutable_uuid_field()
    learning_package = models.ForeignKey(LearningPackage, on_delete=models.CASCADE)
    message = models.CharField(max_length=1000, null=False, blank=True, default="")
    published_at = manual_date_time_field()
    published_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
    )

    class Meta:
        verbose_name = "Publish Log Entry"
        verbose_name_plural = "Publish Log Entries"
