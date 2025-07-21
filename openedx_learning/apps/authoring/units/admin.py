"""
Django admin for units models
"""
from django.contrib import admin
from django.utils.safestring import SafeText

from openedx_learning.lib.admin_utils import ReadOnlyModelAdmin, model_detail_link

from ..publishing.models import ContainerVersion
from .models import Unit, UnitVersion


class UnitVersionInline(admin.TabularInline):
    """
    Minimal table for unit versions in a unit
    """
    model = UnitVersion
    fields = ["pk"]
    readonly_fields = ["pk"]
    ordering = ["-pk"]  # Newest first

    def pk(self, obj: ContainerVersion) -> SafeText:
        return obj.pk


@admin.register(Unit)
class UnitAdmin(ReadOnlyModelAdmin):
    """
    Very minimal interface... just direct the admin user's attention towards the related Container model admin.
    """
    inlines = [UnitVersionInline]
    list_display = ["pk", "key"]
    fields = ["key"]
    readonly_fields = ["key"]

    def key(self, obj: Unit) -> SafeText:
        return model_detail_link(obj.container, obj.key)

    def get_form(self, request, obj=None, change=False, **kwargs):
        help_texts = {'key': f'For more details of this {self.model.__name__}, click above to see its Container view'}
        kwargs.update({'help_texts': help_texts})
        return super().get_form(request, obj, **kwargs)
