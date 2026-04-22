"""
LearningPackage model
"""

from typing import NewType

from django.db import models
from typing_extensions import deprecated

from openedx_django_lib.fields import (
    MultiCollationTextField,
    TypedAutoField,
    case_insensitive_char_field,
    immutable_uuid_field,
    manual_date_time_field,
    ref_field,
)


class LearningPackage(models.Model):
    """
    Top level container for a grouping of authored content.

    Each PublishableEntity belongs to exactly one LearningPackage.
    """

    LearningPackageID = NewType("LearningPackageID", int)
    type ID = LearningPackageID

    # Explictly declare a 4-byte ID instead of using the app-default 8-byte ID.
    # We do not expect to have more than 2 billion LearningPackages on a given
    # site. Furthermore, many, many things have foreign keys to this model and
    # uniqueness indexes on those foreign keys + their own fields, so the 4
    # bytes saved will add up over time.

    class IDField(TypedAutoField[ID]):  # Note: this is ...AutoField not ...BigAutoField
        pass

    id = IDField(primary_key=True)

    @property  # type: ignore[no-redef]
    @deprecated("Use .id instead")
    def pk(self) -> ID:
        return self.id

    uuid = immutable_uuid_field()

    # package_ref is an opaque reference string for the LearningPackage.
    package_ref = ref_field()

    title = case_insensitive_char_field(max_length=500, blank=False)

    # TODO: We should probably defer this field, since many things pull back
    # LearningPackage as select_related. Usually those relations only care about
    # the UUID and package_ref, so maybe it makes sense to separate the model at
    # some point.
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
        return f"{self.package_ref}"

    class Meta:
        constraints = [
            # package_refs must be globally unique.
            models.UniqueConstraint(
                fields=["package_ref"],
                name="oel_publishing_lp_uniq_key",
            )
        ]
        verbose_name = "Learning Package"
        verbose_name_plural = "Learning Packages"
