"""
TOML serialization for learning packages and publishable entities.
"""

from datetime import datetime
from typing import Optional

import tomlkit

from openedx_learning.apps.authoring.collections.models import Collection
from openedx_learning.apps.authoring.publishing.models import PublishableEntity, PublishableEntityVersion
from openedx_learning.apps.authoring.publishing.models.learning_package import LearningPackage


def toml_learning_package(learning_package: LearningPackage) -> str:
    """
    Create a TOML representation of the learning package.

    The resulting content looks like:
        # Datetime of the export: 2025-09-03 12:50:59.573253

        [learning_package]
        title = "Components Test Case Learning Package"
        key = "ComponentTestCase-test-key"
        description = "This is a test learning package for components."
        created = 2025-09-03T17:50:59.536190Z
        updated = 2025-09-03T17:50:59.536190Z
    """
    doc = tomlkit.document()
    doc.add(tomlkit.comment(f"Datetime of the export: {datetime.now()}"))
    section = tomlkit.table()
    section.add("title", learning_package.title)
    section.add("key", learning_package.key)
    section.add("description", learning_package.description)
    section.add("created", learning_package.created)
    section.add("updated", learning_package.updated)
    doc.add("learning_package", section)
    return tomlkit.dumps(doc)


def _get_toml_publishable_entity_table(
        entity: PublishableEntity,
        draft_version: Optional[PublishableEntityVersion],
        published_version: Optional[PublishableEntityVersion],
        include_versions: bool = True) -> tomlkit.items.Table:
    """
    Create a TOML representation of a publishable entity.

    The resulting content looks like:
        [entity]
        uuid = "f8ea9bae-b4ed-4a84-ab4f-2b9850b59cd6"
        can_stand_alone = true
        key = "xblock.v1:problem:my_published_example"

        [entity.draft]
        version_num = 2

        [entity.published]
        version_num = 1

    Note: This function returns a tomlkit.items.Table, which represents
    a string-like TOML fragment rather than a complete TOML document.
    """
    entity_table = tomlkit.table()
    entity_table.add("uuid", str(entity.uuid))
    entity_table.add("can_stand_alone", entity.can_stand_alone)
    # Add key since the toml filename doesn't show the real key
    entity_table.add("key", entity.key)

    if not include_versions:
        return entity_table

    if draft_version:
        draft_table = tomlkit.table()
        draft_table.add("version_num", draft_version.version_num)
        entity_table.add("draft", draft_table)

    published_table = tomlkit.table()
    if published_version:
        published_table.add("version_num", published_version.version_num)
    else:
        published_table.add(tomlkit.comment("unpublished: no published_version_num"))
    entity_table.add("published", published_table)
    return entity_table


def toml_publishable_entity(
        entity: PublishableEntity,
        versions_to_write: list[PublishableEntityVersion],
        draft_version: Optional[PublishableEntityVersion],
        published_version: Optional[PublishableEntityVersion]) -> str:
    """
    Create a TOML representation of a publishable entity and its versions.

    The resulting content looks like:
        [entity]
        uuid = "f8ea9bae-b4ed-4a84-ab4f-2b9850b59cd6"
        can_stand_alone = true
        key = "xblock.v1:problem:my_published_example"

        [entity.draft]
        version_num = 2

        [entity.published]
        version_num = 1

        # ### Versions

        [[version]]
        title = "My published problem"
        uuid = "2e07511f-daa7-428a-9032-17fe12a77d06"
        version_num = 1

        [version.container]
        children = []

        [version.container.unit]
        graded = true
    """
    entity_table = _get_toml_publishable_entity_table(entity, draft_version, published_version)
    doc = tomlkit.document()
    doc.add("entity", entity_table)
    doc.add(tomlkit.nl())
    doc.add(tomlkit.comment("### Versions"))

    for entity_version in versions_to_write:
        version = tomlkit.aot()
        version_table = toml_publishable_entity_version(entity_version)
        version.append(version_table)
        doc.add("version", version)

    return tomlkit.dumps(doc)


def toml_publishable_entity_version(version: PublishableEntityVersion) -> tomlkit.items.Table:
    """
    Create a TOML representation of a publishable entity version.

    The resulting content looks like:
        [[version]]
        title = "My published problem"
        uuid = "2e07511f-daa7-428a-9032-17fe12a77d06"
        version_num = 1

        [version.container]
        children = []

        [version.container.unit]
        graded = true

     Note: This function returns a tomlkit.items.Table, which represents
    a string-like TOML fragment rather than a complete TOML document.
    """
    version_table = tomlkit.table()
    version_table.add("title", version.title)
    version_table.add("uuid", str(version.uuid))
    version_table.add("version_num", version.version_num)

    container_table = tomlkit.table()

    children = []
    if hasattr(version, 'containerversion'):
        children_qs = (
            version.containerversion.entity_list.entitylistrow_set
            .order_by("entity__key")
            .values_list("entity__key", flat=True)
            .distinct()
        )
        children = list(children_qs)
    container_table.add("children", children)

    unit_table = tomlkit.table()
    unit_table.add("graded", True)

    container_table.add("unit", unit_table)
    version_table.add("container", container_table)
    return version_table  # For use in AoT


def toml_collection(collection: Collection, entity_keys: list[str]) -> str:
    """
    Create a TOML representation of a collection.

    The resulting content looks like:
        [collection]
        title = "Collection 1"
        key = "COL1"
        description = "Description of Collection 1"
        created = 2025-09-03T22:28:53.839362Z
        entities = [
            "xblock.v1:problem:my_published_example",
            "xblock.v1:html:my_draft_example",
        ]
    """
    doc = tomlkit.document()

    entities_array = tomlkit.array()
    entities_array.extend(entity_keys)
    entities_array.multiline(True)

    collection_table = tomlkit.table()
    collection_table.add("title", collection.title)
    collection_table.add("key", collection.key)
    collection_table.add("description", collection.description)
    collection_table.add("created", collection.created)
    collection_table.add("entities", entities_array)

    doc.add("collection", collection_table)

    return tomlkit.dumps(doc)
