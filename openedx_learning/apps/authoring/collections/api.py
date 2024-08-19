"""
Collections API (warning: UNSTABLE, in progress API)
"""
from __future__ import annotations

from django.db.models import QuerySet

from .models import Collection

# The public API that will be re-exported by openedx_learning.apps.authoring.api
# is listed in the __all__ entries below. Internal helper functions that are
# private to this module should start with an underscore. If a function does not
# start with an underscore AND it is not in __all__, that function is considered
# to be callable only by other apps in the authoring package.
__all__ = [
    "create_collection",
    "get_collection",
    "get_learning_package_collections",
    "update_collection",
]


def create_collection(
    learning_package_id: int,
    title: str,
    created_by: int | None,
    description: str = "",
) -> Collection:
    """
    Create a new Collection
    """
    collection = Collection.objects.create(
        learning_package_id=learning_package_id,
        title=title,
        created_by=created_by,
        description=description,
    )
    return collection


def get_collection(collection_id: int) -> Collection:
    """
    Get a Collection by ID
    """
    return Collection.objects.get(id=collection_id)


def update_collection(
    collection_id: int,
    title: str | None = None,
    description: str | None = None,
) -> Collection:
    """
    Update a Collection
    """
    collection = Collection.objects.get(id=collection_id)

    # If no changes were requested, there's nothing to update, so just return
    # the Collection as-is
    if all(field is None for field in [title, description]):
        return collection

    if title is not None:
        collection.title = title
    if description is not None:
        collection.description = description

    collection.save()
    return collection


def get_learning_package_collections(learning_package_id: int) -> QuerySet[Collection]:
    """
    Get all collections for a given learning package

    Only enabled collections are returned
    """
    return Collection.objects \
                     .filter(learning_package_id=learning_package_id, enabled=True) \
                     .select_related("learning_package")
