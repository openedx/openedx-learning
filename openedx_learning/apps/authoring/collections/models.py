"""
Core models for Collections
"""
from __future__ import annotations

from django.db import models
from django.utils.translation import gettext_lazy as _

from ....lib.fields import case_insensitive_char_field
from ..publishing.models import LearningPackage


class Collection(models.Model):
    """
    Represents a collection of library components
    """

    id = models.AutoField(primary_key=True)
    learning_package = models.ForeignKey(LearningPackage, on_delete=models.CASCADE)
    name = case_insensitive_char_field(
        null=False,
        max_length=255,
        db_index=True,
        help_text=_(
            "The name of the collection."
        ),
    )
    description = case_insensitive_char_field(
        null=False,
        blank=True,
        max_length=10_000,
        help_text=_(
            "Provides extra information for the user about this collection."
        ),
    )
    # We don't have api functions to handle the enabled field. This is a placeholder for future use and
    # a way to "soft delete" collections.
    enabled = models.BooleanField(
        default=True,
        help_text=_(
            "Whether the collection is enabled or not."
        ),
    )
    created = models.DateTimeField(auto_now_add=True)
    modified = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name_plural = "Collections"

    def __repr__(self):
        """
        Developer-facing representation of a Collection.
        """
        return str(self)

    def __str__(self):
        """
        User-facing string representation of a Collection.
        """
        return f"<{self.__class__.__name__}> ({self.id}:{self.name})"
