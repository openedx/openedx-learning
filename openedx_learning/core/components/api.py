"""
Public APIs for manipulating Items in the ItemStore
"""
from typing import Optional, List
from datetime import datetime, timezone
import textwrap
import uuid

from openedx_learning.lib.fields import create_hash_digest

from .data import (
    ContentData,
    ComponentData,
    ComponentVersionData,
    ItemData,
    ItemVersionData,
    LearningContextData,
    SavedItemData,
)


def create_component(
    learning_context_uuid: uuid.UUID,
    namespace: str,
    type: str,
    identifier: str,
    uuid: Optional[uuid.UUID],
    created: Optional[datetime.datetime],
) -> ComponentData:
    pass


def create_item(ItemData) -> SavedItemData:
    pass


def create_item(
    learning_context_uuid,
    identifier,
) -> SavedItemData:
    pass


def create_item_version(
    item: ItemData,
    title: str,
    uuid: Optional[uuid.UUID],
    component_versions: List[ComponentVersionData],
) -> ItemVersionData:
    return None


def create_component_version() -> ComponentVersionData:
    return None


def get_item(item_uuid):
    pass


def get_item_version(item_version_uuid):
    pass


def fake_item_version(item_version_uuid):
    now = datetime.now(timezone.utc)

    lcd = LearningContextData(
        uuid=uuid.uuid4(),
        identifier="intro_courselet",
        title="Open edX LMS Basics",
        created=now,
        modified=now,
    )

    item = ItemData(
        uuid=uuid.uuid4(),
        identifier="what_is_modulestore",
        learning_context=lcd,
    )

    olx_bytes = textwrap.dedent(
        """
            <problem>
              <multiplechoiceresponse>
                <p>Pretend this is a longer intro.</p>
              <label>The ModuleStore is:</label>
              <choicegroup type="MultipleChoice">
                  <choice correct="true">a storage mechanism for XBlocks and XModules</choice>
                  <choice correct="true">a runtime for XBlocks and XModules</choice>
                  <choice correct="true">a giant headache</choice>
                  <choice correct="false">a wee, harmless little bunny</choice>
                </choicegroup>
              </multiplechoiceresponse>
            </problem>"""
    ).encode("utf-8")
    mkd_cont = ContentData(
        learning_context=lcd, hash_digest=create_hash_digest(olx_bytes), type="text"
    )
    mkd_comp = ComponentData(
        uuid=uuid.uuid4(),
        learning_context=lcd,
        namespace="xblock.v1",
        type="markdown",
        identifier="what_is_modulestore",
        created=now,
        modified=now,
    )
    mkd_comp_v = ComponentVersionData(
        uuid=uuid.uuid4(),
        component=mkd_comp,
    )

    return ItemVersionData(
        uuid=item_version_uuid,
        item=item,
        title="What is Modulestore?",
        component_versions=[
            ComponentVersionData(
                uuid=uuid.uuid4(),
                component=None,
                created=now,
            )
        ],
    )


def get_items():
    """
    Make a layer that iterates over the Queryset and does the casting into data
    structures, eg.

    items = data_from_qset(Item.objects.all(), ItemData)

    """
    pass
