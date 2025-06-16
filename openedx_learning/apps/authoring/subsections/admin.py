"""
Django admin for subsection models
"""
from django.contrib import admin
from django.utils.safestring import SafeText

from openedx_learning.lib.admin_utils import ReadOnlyModelAdmin, model_detail_link

from .models import Subsection


@admin.register(Subsection)
class SubsectionAdmin(ReadOnlyModelAdmin):
    """
    Django admin for Subsection model
    """
    list_display = ["subsection_id", "key"]
    fields = ["see"]
    readonly_fields = ["see"]

    def subsection_id(self, obj: Subsection) -> int:
        return obj.pk

    def key(self, obj: Subsection) -> SafeText:
        return model_detail_link(obj.container, obj.container.key)

    def see(self, obj: Subsection) -> SafeText:
        return self.key(obj)
