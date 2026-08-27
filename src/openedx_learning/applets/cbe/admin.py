"""
Django Admin pages for CBE models.
"""
from django.contrib import admin

from .models import CompetencyTaxonomy

__all__ = [
    "CompetencyTaxonomyAdmin",
]


class CompetencyTaxonomyAdmin(admin.ModelAdmin):
    """
    The CompetencyTaxonomy model admin.
    """
    list_display = ["name", "export_id", "enabled"]
    list_filter = ["enabled"]


admin.site.register(CompetencyTaxonomy, CompetencyTaxonomyAdmin)
