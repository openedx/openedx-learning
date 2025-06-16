"""
Django admin for sections models
"""
from django.contrib import admin
from django.utils.safestring import SafeText

from openedx_learning.lib.admin_utils import ReadOnlyModelAdmin, model_detail_link

from .models import Section


@admin.register(Section)
class SectionAdmin(ReadOnlyModelAdmin):
    """
    Very minimal interface... just direct the admin user's attention towards the related Container model admin.
    """
    list_display = ["section_id", "key"]
    fields = ["see"]
    readonly_fields = ["see"]

    def section_id(self, obj: Section) -> int:
        return obj.pk

    def key(self, obj: Section) -> SafeText:
        return model_detail_link(obj.container, obj.container.key)

    def see(self, obj: Section) -> SafeText:
        return self.key(obj)