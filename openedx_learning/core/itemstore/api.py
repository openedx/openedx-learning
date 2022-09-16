# type: ignore
"""
Public APIs for manipulating Items in the ItemStore
"""
from typing import Optional
import datetime
import uuid


from .data import ComponentData, ItemData


def create_component(
    learning_context_uuid: uuid.UUID,
    namespace: str,
    type: str,
    identifier: str,

    uuid: Optional[uuid.UUID],
    created: Optional[datetime.datetime],
) -> ComponentData:
    pass


def create_item(
    learning_context_uuid: uuid.UUID,
    identifier: str,
    uuid: Optional[uuid.UUID],
) -> ItemData:
    pass


def sample_code():
    new_item = create_item(identifier)


def get_items():
    """
    Make a layer that iterates over the Queryset and does the casting into data
    structures, eg.

    items = data_from_qset(Item.objects.all(), ItemData)

    """
    pass


