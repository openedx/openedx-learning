"""
Core models for Collections
"""
from __future__ import annotations

from django.conf import settings
from django.db import models
from django.utils.translation import gettext_lazy as _

from ....lib.fields import MultiCollationTextField, case_insensitive_char_field
from ....lib.validators import validate_utc_datetime
from ..publishing.models import LearningPackage

__all__ = [
    "Collection",
]


class Collection(models.Model):
    """
    Represents a collection of library components
    """

    id = models.AutoField(primary_key=True)

    # Each collection belongs to a learning package
    learning_package = models.ForeignKey(LearningPackage, on_delete=models.CASCADE)

    title = case_insensitive_char_field(
        null=False,
        blank=False,
        max_length=500,
        help_text=_(
            "The title of the collection."
        ),
    )

    description = MultiCollationTextField(
        blank=True,
        null=False,
        default="",
        max_length=10_000,
        help_text=_(
            "Provides extra information for the user about this collection."
        ),
        db_collations={
            "sqlite": "NOCASE",
            "mysql": "utf8mb4_unicode_ci",
        }
    )

    # We don't have api functions to handle the enabled field. This is a placeholder for future use and
    # a way to "soft delete" collections.
    enabled = models.BooleanField(
        default=True,
        help_text=_(
            "Whether the collection is enabled or not."
        ),
    )

    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
    )

    created = models.DateTimeField(
        auto_now_add=True,
        validators=[
            validate_utc_datetime,
        ],
    )

    modified = models.DateTimeField(
        auto_now=True,
        validators=[
            validate_utc_datetime,
        ],
    )

    class Meta:
        verbose_name_plural = "Collections"
        indexes = [
            models.Index(fields=["learning_package_id", "title"]),
        ]

    def __repr__(self) -> str:
        """
        Developer-facing representation of a Collection.
        """
        return str(self)

    def __str__(self) -> str:
        """
        User-facing string representation of a Collection.
        """
        return f"<{self.__class__.__name__}> ({self.id}:{self.title})"
