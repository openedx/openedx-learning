from django.contrib import admin

from .models import LearningPackage, PublishLogEntry


@admin.register(LearningPackage)
class LearningPackageAdmin(admin.ModelAdmin):
    fields = ("identifier", "title", "uuid", "created", "updated")
    readonly_fields = ("identifier", "title", "uuid", "created", "updated")
    list_display = ("identifier", "title", "uuid", "created", "updated")


@admin.register(PublishLogEntry)
class PublishLogEntryAdmin(admin.ModelAdmin):
    fields = ("uuid", "learning_package", "published_at", "published_by", "message")
    readonly_fields = (
        "uuid",
        "learning_package",
        "published_at",
        "published_by",
        "message",
    )
    list_display = (
        "uuid",
        "learning_package",
        "published_at",
        "published_by",
        "message",
    )
