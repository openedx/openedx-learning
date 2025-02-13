"""
Django admin for linking models
"""

from django.contrib import admin

from openedx_learning.lib.admin_utils import ReadOnlyModelAdmin

from .models import LearningContextLinksStatus, PublishableEntityLink


@admin.register(PublishableEntityLink)
class PublishableEntityLinkAdmin(ReadOnlyModelAdmin):
    """
    PublishableEntityLink admin.
    """
    fields = (
        "uuid",
        "upstream_block",
        "upstream_usage_key",
        "upstream_context_key",
        "downstream_usage_key",
        "downstream_context_key",
        "downstream_context_title",
        "version_synced",
        "version_declined",
        "created",
        "updated",
    )
    readonly_fields = fields
    list_display = [
        "upstream_block",
        "upstream_usage_key",
        "downstream_usage_key",
        "downstream_context_title",
        "version_synced",
        "updated",
    ]
    search_fields = [
        "upstream_usage_key",
        "upstream_context_key",
        "downstream_usage_key",
        "downstream_context_key",
        "downstream_context_title",
    ]


@admin.register(LearningContextLinksStatus)
class LearningContextLinksStatusAdmin(admin.ModelAdmin):
    """
    LearningContextLinksStatus admin.
    """
    fields = (
        "context_key",
        "status",
        "created",
        "updated",
    )
    readonly_fields = ("created", "updated")
    list_display = (
        "context_key",
        "status",
        "created",
        "updated",
    )
