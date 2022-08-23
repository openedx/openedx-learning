from django.contrib import admin

from .models import (
    Item, ItemVersion, ItemVersionComponentVersion,
    Component, ComponentVersion, ComponentVersionContent,
)

@admin.register(Item)
class ItemAdmin(admin.ModelAdmin):
    list_display = ('identifier', 'uuid', 'created', 'modified')
    readonly_fields = ['uuid']

