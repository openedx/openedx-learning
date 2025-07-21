"""
Django admin for sections models
"""
from django.contrib import admin
from django.utils.safestring import SafeText

from openedx_learning.lib.admin_utils import ReadOnlyModelAdmin, model_detail_link

from ..publishing.models import ContainerVersion
from .models import Section, SectionVersion


class SectionVersionInline(admin.TabularInline):
    """
    Minimal table for subsecdtion versions in a subsection
    """
    model = SectionVersion
    fields = ["pk"]
    readonly_fields = ["pk"]
    ordering = ["-pk"]  # Newest first

    def pk(self, obj: ContainerVersion) -> SafeText:
        return obj.pk


@admin.register(Section)
class SectionAdmin(ReadOnlyModelAdmin):
    """
    Very minimal interface... just direct the admin user's attention towards the related Container model admin.
    """
    inlines = [SectionVersionInline]
    list_display = ["pk", "key"]
    fields = ["key"]
    readonly_fields = ["key"]

    def key(self, obj: Section) -> SafeText:
        return model_detail_link(obj.container, obj.key)

    def get_form(self, request, obj=None, change=False, **kwargs):
        help_texts = {'key': f'For more details of this {self.model.__name__}, click above to see its Container view'}
        kwargs.update({'help_texts': help_texts})
        return super().get_form(request, obj, **kwargs)
