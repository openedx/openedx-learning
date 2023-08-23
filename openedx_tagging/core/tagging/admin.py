"""
Tagging app admin
"""
from django.contrib import admin

from .models import ObjectTag, Tag, Taxonomy

admin.site.register(Taxonomy)
admin.site.register(Tag)
admin.site.register(ObjectTag)
