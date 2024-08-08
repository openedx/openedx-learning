"""
Collections API (warning: UNSTABLE, in progress API)
"""
from __future__ import annotations

from django.db.models import QuerySet

from .models import Collection


def create_collection(
    learning_package_id: int,
    name: str,
    description: str = "",
) -> Collection:
    """
    Create a new Collection
    """
    collection = Collection.objects.create(
        learning_package_id=learning_package_id,
        name=name,
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
    name: str | None = None,
    description: str | None = None,
) -> Collection:
    """
    Update a Collection
    """
    lp = Collection.objects.get(id=collection_id)

    # If no changes were requested, there's nothing to update, so just return
    # the Collection as-is
    if all(field is None for field in [name, description]):
        return lp

    if name is not None:
        lp.name = name
    if description is not None:
        lp.description = description

    lp.save()
    return lp


def get_learning_package_collections(learning_package_id: int) -> QuerySet[Collection]:
    """
    Get all collections for a given learning package

    Only enabled collections are returned
    """
    return (
        Collection.objects
        .filter(learning_package_id=learning_package_id, enabled=True)
        .select_related("learning_package")
    )
