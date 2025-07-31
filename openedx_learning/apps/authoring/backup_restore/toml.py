"""
TOML serialization for learning packages and publishable entities.
"""

from datetime import datetime

import tomlkit

from openedx_learning.apps.authoring.publishing.models import (
    Draft,
    PublishableEntity,
    PublishableEntityVersion,
    Published,
)
from openedx_learning.apps.authoring.publishing.models.learning_package import LearningPackage


def toml_learning_package(learning_package: LearningPackage) -> str:
    """Create a TOML representation of the learning package."""
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


def toml_publishable_entity(entity: PublishableEntity) -> str:
    """Create a TOML representation of a publishable entity."""

    current_draft_version = getattr(entity, "draft", None)
    current_published_version = getattr(entity, "published", None)

    doc = tomlkit.document()
    entity_table = tomlkit.table()
    entity_table.add("uuid", str(entity.uuid))
    entity_table.add("can_stand_alone", entity.can_stand_alone)

    if current_draft_version:
        draft = tomlkit.table()
        draft.add("version_num", current_draft_version.version.version_num)
        entity_table.add("draft", draft)

    published = tomlkit.table()
    if current_published_version:
        published.add("version_num", current_published_version.version.version_num)
    else:
        published.add(tomlkit.comment("unpublished: no published_version_num"))
    entity_table.add("published", published)

    doc.add("entity", entity_table)
    doc.add(tomlkit.nl())
    doc.add(tomlkit.comment("### Versions"))

    for entity_version in entity.versions.all():
        version = tomlkit.aot()
        version_table = toml_publishable_entity_version(entity_version)
        version.append(version_table)
        doc.add("version", version)

    return tomlkit.dumps(doc)


def toml_publishable_entity_version(version: PublishableEntityVersion) -> tomlkit.items.Table:
    """Create a TOML representation of a publishable entity version."""
    version_table = tomlkit.table()
    version_table.add("title", version.title)
    version_table.add("uuid", str(version.uuid))
    version_table.add("version_num", version.version_num)
    container_table = tomlkit.table()
    container_table.add("children", [])
    unit_table = tomlkit.table()
    unit_table.add("graded", True)
    container_table.add("unit", unit_table)
    version_table.add("container", container_table)
    return version_table  # For use in AoT
