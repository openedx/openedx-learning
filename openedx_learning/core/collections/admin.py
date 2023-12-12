"""
Django admin for Collections.

This is extremely bare-bones at the moment, and basically gives you just enough
information to let you know whether it's working or not.
"""
from django.contrib import admin

from openedx_learning.lib.admin_utils import ReadOnlyModelAdmin

from ..publishing.models import PublishableEntity
from .models import (
    AddToCollection,
    Collection,
    CollectionChangeSet,
    CollectionPublishableEntity,
    PublishEntity,
    RemoveFromCollection
)


class CollectionChangeSetTabularInline(admin.TabularInline):
    model = CollectionChangeSet
    fields = ["version_num", "created"]
    readonly_fields = ["version_num", "created"]


class PublishableEntityInline(admin.TabularInline):
    model = Collection.publishable_entities.through


@admin.register(Collection)
class CollectionAdmin(ReadOnlyModelAdmin):
    """
    Read-only admin for LearningPackage model
    """
    fields = ["learning_package", "key", "title", "uuid", "created", "created_by"]
    readonly_fields = ["learning_package", "key", "title", "uuid", "created", "created_by"]
    list_display = ["learning_package", "key", "title", "uuid", "created", "created_by"]
    search_fields = ["key", "title", "uuid"]
    list_filter = ["learning_package"]

    inlines = [
        CollectionChangeSetTabularInline,
        PublishableEntityInline,
    ]


class AddToCollectionTabularInline(admin.TabularInline):
    model = AddToCollection


class RemoveFromCollectionTabularInline(admin.TabularInline):
    model = RemoveFromCollection


class PublishEntityTabularInline(admin.TabularInline):
    model = PublishEntity


@admin.register(CollectionChangeSet)
class CollectionChangeSetAdmin(ReadOnlyModelAdmin):
    inlines = [
        AddToCollectionTabularInline,
        RemoveFromCollectionTabularInline,
        PublishEntityTabularInline,
    ]
