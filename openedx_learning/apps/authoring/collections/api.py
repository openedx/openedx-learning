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


def get_learning_package_collections(learning_package_id: int) -> QuerySet[Collection]:
    """
    Get all collections for a given learning package
    """
    return (
        Collection.objects
        .filter(learning_package_id=learning_package_id, enabled=True)
        .select_related("learning_package")
    )
