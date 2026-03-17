"""
LearningPackage model
"""
from django.db import models

from openedx_django_lib.fields import (
    MultiCollationTextField,
    case_insensitive_char_field,
    immutable_uuid_field,
    label_field,
    manual_date_time_field,
)


class LearningPackage(models.Model):
    """
    Top level container for a grouping of authored content.

    Each PublishableEntity belongs to exactly one LearningPackage.
    """
    # Explictly declare a 4-byte ID instead of using the app-default 8-byte ID.
    # We do not expect to have more than 2 billion LearningPackages on a given
    # site. Furthermore, many, many things have foreign keys to this model and
    # uniqueness indexes on those foreign keys + their own fields, so the 4
    # bytes saved will add up over time.
    id = models.AutoField(primary_key=True)

    uuid = immutable_uuid_field()

    # Formerly called "key", represented in the DB as "_key".
    label = label_field(db_column="_key")

    title = case_insensitive_char_field(max_length=500, blank=False)

    # TODO: We should probably defer this field, since many things pull back
    # LearningPackage as select_related. Usually those relations only care about
    # the UUID and key, so maybe it makes sense to separate the model at some
    # point.
    description = MultiCollationTextField(
        blank=True,
        null=False,
        default="",
        max_length=10_000,
        # We don't really expect to ever sort by the text column, but we may
        # want to do case-insensitive searches, so it's useful to have a case
        # and accent insensitive collation.
        db_collations={
            "sqlite": "NOCASE",
            "mysql": "utf8mb4_unicode_ci",
        }
    )

    created = manual_date_time_field()
    updated = manual_date_time_field()

    def __str__(self):
        return f"{self.label}"

    class Meta:
        constraints = [
            # LearningPackage labels must be globally unique. This is something
            # that might be relaxed in the future if this system were to be
            # extensible to something like multi-tenancy, in which case we'd tie
            # it to something like a Site or Org.
            models.UniqueConstraint(
                fields=["label"],
                name="oel_publishing_lp_uniq_key",
            )
        ]
        verbose_name = "Learning Package"
        verbose_name_plural = "Learning Packages"
