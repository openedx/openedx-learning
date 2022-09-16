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
class ItemData:
    uuid: uuid.UUID
    identifier: str

    learning_context: LearningContextData


@define
class ItemVersionData:
    uuid: uuid.UUID
    item: ItemData
    title: str

    component_versions: List[ComponentVersionData]
