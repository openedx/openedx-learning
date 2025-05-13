"""
Django admin for subsection models
"""
from django.contrib import admin
from django.utils.safestring import SafeText

from openedx_learning.lib.admin_utils import ReadOnlyModelAdmin, model_detail_link

from .models import Subsection, SubsectionVersion


class SubsectionVersionInline(admin.TabularInline):
    """
    Minimal table for subsecdtion versions in a subsection
    """
    model = SubsectionVersion


@admin.register(Subsection)
class SubsectionAdmin(ReadOnlyModelAdmin):
    """
    Very minimal interface... just direct the admin user's attention towards the related Container model admin.
    """
    list_display = ["subsection_id", "key"]
    fields = ["see"]
    readonly_fields = ["see"]
    inlines = [SubsectionVersionInline]

    def subsection_id(self, obj: Subsection) -> int:
        return obj.pk

    def key(self, obj: Subsection) -> SafeText:
        return model_detail_link(obj.container, obj.container.key)

    def see(self, obj: Subsection) -> SafeText:
        return self.key(obj)
