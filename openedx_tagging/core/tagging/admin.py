""" Tagging app admin """
from django import forms
from django.contrib import admin

from .models import ObjectTag, Tag, Taxonomy


def check_taxonomy(taxonomy: Taxonomy):
    """
    Checks if the taxonomy is valid to edit or delete
    """
    taxonomy = taxonomy.cast()
    return not taxonomy.system_defined


class TaxonomyAdmin(admin.ModelAdmin):
    """
    Admin for Taxonomy Model
    """
    
    def has_change_permission(self, request, obj=None):
        """
        Avoid edit system-defined taxonomies
        """
        if obj is not None:
            return check_taxonomy(taxonomy=obj)
        return super().has_change_permission(request, obj)
    
    def has_delete_permission(self, request, obj=None):
        """
        Avoid delete system-defined taxonomies
        """
        if obj is not None:
            return check_taxonomy(taxonomy=obj)
        return super().has_change_permission(request, obj)


class TagForm(forms.ModelForm):
    """
    Form for create a Tag
    """
    class Meta:
        model = Tag
        fields = '__all__'

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        print(self.fields)
        if 'taxonomy' in self.fields:
            self.fields['taxonomy'].queryset = self._filter_taxonomies()
        
    def _filter_taxonomies(self):
        """
        Returns taxonomies that allows Tag creation

        - Not allow free text
        - Not system defined
        """
        taxonomy_queryset = Taxonomy.objects.filter(
            allow_free_text=False
        )
        valid_taxonomy_ids = [
            taxonomy.id for taxonomy 
            in taxonomy_queryset if check_taxonomy(taxonomy)
        ]

        return taxonomy_queryset.filter(id__in=valid_taxonomy_ids)


class TagAdmin(admin.ModelAdmin):
    """
    Admin for Tag Model
    """
    form = TagForm

    def has_change_permission(self, request, obj=None):
        """
        Avoid edit system-defined taxonomies
        """
        if obj is not None:
            taxonomy = obj.taxonomy
            if taxonomy:
                return check_taxonomy(taxonomy)
        return super().has_change_permission(request, obj)
    
    def has_delete_permission(self, request, obj=None):
        """
        Avoid delete system-defined taxonomies
        """
        if obj is not None:
            taxonomy = obj.taxonomy
            if taxonomy:
                return check_taxonomy(taxonomy)
        return super().has_change_permission(request, obj)


admin.site.register(Taxonomy, TaxonomyAdmin)
admin.site.register(Tag, TagAdmin)
admin.site.register(ObjectTag)
