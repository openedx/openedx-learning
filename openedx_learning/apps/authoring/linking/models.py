"""
Contains models to store upstream-downstream links between publishable entities.
"""
from django.db import models
from django.utils.translation import gettext_lazy as _

from openedx_learning.lib.fields import (
    case_insensitive_char_field,
    immutable_uuid_field,
    key_field,
    manual_date_time_field,
)

from ..publishing.models import PublishableEntity

__all__ = [
    "PublishableEntityLink",
    "CourseLinksStatus",
    "CourseLinksStatusChoices"
]


class PublishableEntityLink(models.Model):
    """
    This represents link between any two publishable entities or link between publishable entity and a course
    xblock. It helps in tracking relationship between xblocks imported from libraries and used in different courses.
    """
    uuid = immutable_uuid_field()
    upstream_block = models.ForeignKey(
        PublishableEntity,
        on_delete=models.SET_NULL,
        related_name="links",
        null=True,
        blank=True,
    )
    upstream_usage_key = key_field(
        help_text=_(
            "Upstream block usage key, this value cannot be null"
            " and useful to track upstream library blocks that do not exist yet"
        )
    )
    upstream_context_key = key_field(
        help_text=_(
            "Upstream context key i.e., learning_package/library key"
        )
    )
    downstream_usage_key = key_field()
    downstream_context_key = key_field()
    downstream_context_title = case_insensitive_char_field(
        null=False,
        blank=False,
        max_length=1000,
        help_text=_(
            "The title of downstream context, for example, course display name."
        ),
    )
    version_synced = models.IntegerField()
    version_declined = models.IntegerField(null=True, blank=True)
    created = manual_date_time_field()
    updated = manual_date_time_field()

    def __str__(self):
        return f"{self.upstream_usage_key}->{self.downstream_usage_key}"

    class Meta:
        constraints = [
            # A downstream entity can only link to single upstream entity
            # whereas an entity can be upstream for multiple downstream entities.
            models.UniqueConstraint(
                fields=["downstream_usage_key"],
                name="oel_link_ent_downstream_key",
            )
        ]
        indexes = [
            # Search by course/downstream key
            models.Index(
                fields=["downstream_context_key"],
                name="oel_link_ent_idx_down_ctx_key",
            ),
            # Search by library/upstream key
            models.Index(
                fields=["upstream_context_key"],
                name="oel_link_ent_idx_up_ctx_key"
            ),
        ]
        verbose_name = "Publishable Entity Link"
        verbose_name_plural = "Publishable Entity Links"


class CourseLinksStatusChoices(models.TextChoices):
    """
    Enumerates the states that a CourseLinksStatus can be in.
    """
    PENDING = "pending", _("Pending")
    PROCESSING = "processing", _("Processing")
    FAILED = "failed", _("Failed")
    COMPLETED = "completed", _("Completed")


class CourseLinksStatus(models.Model):
    """
    This table stores current processing status of upstream-downstream links in PublishableEntityLink table for a
    course.
    """
    context_key = key_field(
        help_text=_("Linking status for downstream/course context key"),
    )
    status = models.CharField(
        max_length=20,
        choices=CourseLinksStatusChoices.choices,
        help_text=_("Status of links in given course."),
    )
    created = manual_date_time_field()
    updated = manual_date_time_field()

    class Meta:
        constraints = [
            # Single entry for a course
            models.UniqueConstraint(
                fields=["context_key"],
                name="oel_link_ent_status_ctx_key",
            )
        ]
        verbose_name = "Course Links status"
        verbose_name_plural = "Course Links status"

    def __str__(self):
        return f"{self.status}|{self.context_key}"
