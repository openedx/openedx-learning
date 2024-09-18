"""
Django Admin pages for Collection models.
"""
from django.contrib import admin

from .models import Collection


class CollectionAdmin(admin.ModelAdmin):
    """
    The Collection model admin.

    Allows users to easily disable/enable (aka soft delete and restore) or bulk delete Collections.
    """
    readonly_fields = ["key", "learning_package"]
    list_filter = ["enabled"]
    list_display = ["key", "title", "enabled", "modified"]
    list_editable = ["enabled"]

    def has_add_permission(self, request, *args, **kwargs):
        """
        Disallow adding new collections via Django Admin.
        """
        return False  # pragma: no cover


admin.site.register(Collection, CollectionAdmin)
