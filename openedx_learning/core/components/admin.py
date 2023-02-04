from django.contrib import admin

from .models import (
    Unit,
    UnitVersion,
    ItemVersionComponentVersion,
    Component,
    ComponentVersion,
    ComponentVersionContent,
)


@admin.register(Unit)
class ItemAdmin(admin.ModelAdmin):
    list_display = ("identifier", "uuid", "created", "modified")
    readonly_fields = ["uuid"]
