"""
Convenience utilities for the Django Admin.
"""
from django.contrib import admin


class ReadOnlyModelAdmin(admin.ModelAdmin):
    """
    ModelAdmin subclass that removes any editing ability.

    The Django Admin is really useful for quickly examining model data. At the
    same time, model creation and updates follow specific rules that are meant
    to be enforced above the model layer (in api.py files), so making edits in
    the Django Admin is potentially dangerous.

    In general, if you're providing Django Admin interfaces for your
    openedx-learning related app data models, you should subclass this class
    instead of subclassing admin.ModelAdmin directly.
    """

    def has_add_permission(self, request):
        return False

    def has_change_permission(self, request, obj=None):
        return False

    def has_delete_permission(self, request, obj=None):
        return False
