from datetime import datetime
from typing import Dict, List
import uuid

from attrs import define, field


@define
class LearningContextData:
    uuid: uuid.UUID
    identifier: str
    title: str

    created: datetime
    modified: datetime


@define
class ComponentData:
    uuid: uuid.UUID

    # The combination of (learning_context, namespace, type, identifier) is
    # unique, but the same namespace+type+identifier can exist in a different
    # Learning Context.
    learning_context: LearningContextData
    namespace: str
    type: str
    identifier: str

    created: datetime
    modified: datetime


@define
class ComponentVersionData:
    component: ComponentData
    created: datetime


@define
class SavedComponentVersionData(ComponentVersionData):
    """
    This is the data for a Component that has been saved to the database.
    """

    uuid: uuid.UUID


@define
class ItemData:
    identifier: str
    learning_context: LearningContextData


@define
class SavedItemData(ItemData):
    uuid: uuid.UUID


@define
class ItemVersionData:
    uuid: uuid.UUID
    item: ItemData
    title: str

    component_versions: List[ComponentVersionData]


@define
class ContentData:
    learning_context: LearningContextData
    hash_digest: str  # should this be bytes instead?
    type: str
    sub_type: str
    size: int
    created: datetime
