"""
Django admin for units models
"""
from django.contrib import admin
from django.utils.safestring import SafeText

from openedx_learning.lib.admin_utils import ReadOnlyModelAdmin, model_detail_link

from .models import Unit, UnitVersion


class UnitVersionInline(admin.TabularInline):
    """
    Minimal table for unit versions in a unit

    @@TODO add inlines to the other container version types (subsections, sections, etc)
    """
    model = UnitVersion


@admin.register(Unit)
class UnitAdmin(ReadOnlyModelAdmin):
    """
    Very minimal interface... just direct the admin user's attention towards the related Container model admin.
    """
    list_display = ["unit_id", "container_key"]
    fields = ["see"]
    readonly_fields = ["see"]
    inlines = [UnitVersionInline]

    def unit_id(self, obj: Unit) -> int:
        return obj.pk

    def container_key(self, obj: Unit) -> SafeText:
        return model_detail_link(obj.container, obj.container.key)

    def see(self, obj: Unit) -> SafeText:
        return self.container_key(obj)