"""
Django admin for publishing models
"""
from __future__ import annotations

from django.contrib import admin
from django.db.models import Count

from openedx_learning.lib.admin_utils import ReadOnlyModelAdmin, one_to_one_related_model_html

from .models import (
    DraftChangeLog,
    DraftChangeLogRecord,
    LearningPackage,
    PublishableEntity,
    PublishLog,
    PublishLogRecord,
)
from .models.publish_log import Published


@admin.register(LearningPackage)
class LearningPackageAdmin(ReadOnlyModelAdmin):
    """
    Read-only admin for LearningPackage model
    """
    fields = ["key", "title", "uuid", "created", "updated"]
    readonly_fields = ["key", "title", "uuid", "created", "updated"]
    list_display = ["key", "title", "uuid", "created", "updated"]
    search_fields = ["key", "title", "uuid"]


class PublishLogRecordTabularInline(admin.TabularInline):
    """
    Inline read-only tabular view for PublishLogRecords
    """
    model = PublishLogRecord
    fields = (
        "entity",
        "title",
        "old_version_num",
        "new_version_num",
    )
    readonly_fields = fields

    def get_queryset(self, request):
        queryset = super().get_queryset(request)
        return queryset.select_related("entity", "old_version", "new_version")

    def old_version_num(self, pl_record: PublishLogRecord):
        if pl_record.old_version is None:
            return "-"
        return pl_record.old_version.version_num

    def new_version_num(self, pl_record: PublishLogRecord):
        if pl_record.new_version is None:
            return "-"
        return pl_record.new_version.version_num

    def title(self, pl_record: PublishLogRecord):
        """
        Get the title to display for the PublishLogRecord
        """
        if pl_record.new_version:
            return pl_record.new_version.title
        if pl_record.old_version:
            return pl_record.old_version.title
        return ""


@admin.register(PublishLog)
class PublishLogAdmin(ReadOnlyModelAdmin):
    """
    Read-only admin view for PublishLog
    """
    inlines = [PublishLogRecordTabularInline]

    fields = ("uuid", "learning_package", "published_at", "published_by", "message")
    readonly_fields = fields
    list_display = fields
    list_filter = ["learning_package"]


@admin.register(PublishableEntity)
class PublishableEntityAdmin(ReadOnlyModelAdmin):
    """
    Read-only admin view for Publishable Entities
    """
    list_display = [
        "key",
        "draft_version",
        "published_version",
        "uuid",
        "learning_package",
        "created",
        "created_by",
        "can_stand_alone",
    ]
    list_filter = ["learning_package"]
    search_fields = ["key", "uuid"]

    fields = [
        "key",
        "draft_version",
        "published_version",
        "uuid",
        "learning_package",
        "created",
        "created_by",
        "see_also",
        "can_stand_alone",
    ]
    readonly_fields = [
        "key",
        "draft_version",
        "published_version",
        "uuid",
        "learning_package",
        "created",
        "created_by",
        "see_also",
        "can_stand_alone",
    ]

    def get_queryset(self, request):
        queryset = super().get_queryset(request)
        return queryset.select_related(
            "learning_package", "published__version",
        )

    def see_also(self, entity):
        return one_to_one_related_model_html(entity)

    def draft_version(self, entity):
        if entity.draft.version:
            return entity.draft.version.version_num
        return None

    def published_version(self, entity):
        if entity.published.version:
            return entity.published.version.version_num
        return None


@admin.register(Published)
class PublishedAdmin(ReadOnlyModelAdmin):
    """
    Read-only admin view for Published model
    """
    fields = ("entity", "version_num", "previous", "published_at", "message")
    list_display = fields

    def get_queryset(self, request):
        queryset = super().get_queryset(request)
        return queryset.select_related(
            "entity",
            "version",
            "publish_log_record",
            "publish_log_record__old_version",
            "publish_log_record__publish_log",
        )

    def version_num(self, published_obj):
        if published_obj.version:
            return published_obj.version.version_num
        return None

    def previous(self, published_obj):
        """
        Determine what to show in the "Previous" field
        """
        old_version = published_obj.publish_log_record.old_version
        # if there was no previous old version, old version is None
        if not old_version:
            return old_version
        return old_version.version_num

    def published_at(self, published_obj):
        return published_obj.publish_log_record.publish_log.published_at

    def message(self, published_obj):
        return published_obj.publish_log_record.publish_log.message


class DraftChangeLogRecordTabularInline(admin.TabularInline):
    """
    Tabular inline for a single Draft change.
    """
    model = DraftChangeLogRecord

    fields = (
        "entity",
        "title",
        "old_version_num",
        "new_version_num",
    )
    readonly_fields = fields

    def get_queryset(self, request):
        queryset = super().get_queryset(request)
        return queryset.select_related("entity", "old_version", "new_version") \
                       .order_by("entity__key")

    def old_version_num(self, draft_change: DraftChangeLogRecord):
        if draft_change.old_version is None:
            return "-"
        return draft_change.old_version.version_num

    def new_version_num(self, draft_change: DraftChangeLogRecord):
        if draft_change.new_version is None:
            return "-"
        return draft_change.new_version.version_num

    def title(self, draft_change: DraftChangeLogRecord):
        """
        Get the title to display for the DraftChange
        """
        if draft_change.new_version:
            return draft_change.new_version.title
        if draft_change.old_version:
            return draft_change.old_version.title
        return ""


@admin.register(DraftChangeLog)
class DraftChangeSetAdmin(ReadOnlyModelAdmin):
    """
    Read-only admin to view Draft changes (via inline tables)
    """
    inlines = [DraftChangeLogRecordTabularInline]
    fields = (
        "uuid",
        "learning_package",
        "num_changes",
        "changed_at",
        "changed_by",
    )
    readonly_fields = fields
    list_display = fields
    list_filter = ["learning_package"]

    def num_changes(self, draft_change_set):
        return draft_change_set.num_changes

    def get_queryset(self, request):
        queryset = super().get_queryset(request)
        return queryset.select_related("learning_package", "changed_by") \
                       .annotate(num_changes=Count("records"))
