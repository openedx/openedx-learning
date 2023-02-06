from django.contrib import admin

from .models import (
    Component,
    ComponentVersion,
    ComponentVersionContent,
)


@admin.register(Component)
class ComponentAdmin(admin.ModelAdmin):
    list_display = ("identifier", "uuid", "created", "modified")
    readonly_fields = ["uuid"]
