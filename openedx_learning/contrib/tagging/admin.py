""" Tagging app admin """
from django.contrib import admin
from .models import TagContent

admin.site.register(TagContent)
