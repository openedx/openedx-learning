"""
Utilities for backup and restore app
"""

from datetime import datetime
from typing import Any, Dict

from tomlkit import aot, comment, document, dumps, nl, table
from tomlkit.items import Table

from openedx_learning.apps.authoring.publishing.models.learning_package import LearningPackage
from openedx_learning.apps.authoring.publishing.models.publishable_entity import (
    PublishableEntityMixin,
    PublishableEntityVersionMixin,
)


class TOMLMixin:
    """
    Mixin class to provide common functionality for TOML file generation.
    This class can be extended by other classes that need to generate TOML files.
    """

    def __init__(self, existing_doc: document = None):
        self.doc = document() if existing_doc is None else existing_doc

    def add_nl(self) -> None:
        """
        Adds a newline to the TOML document.
        This is useful for formatting the output.
        """
        self.doc.add(nl())

    def add_comment(self, text: str) -> None:
        """
        Adds a comment to the TOML document.
        Args:
            text (str): The comment text to add.
        """
        self.doc.add(comment(text))
        self.add_nl()

    def _create_table(self, params: Dict[str, Any], comment_text: str = None) -> Table:
        """
        Builds a TOML table section from a dictionary of key-value pairs.
        """
        section = table()
        if comment_text:
            section.add(comment(comment_text))
        for key, value in params.items():
            section.add(key, value)
        return section

    def get(self) -> str:
        """
        Returns:
            str: The string representation of the generated TOML document.
            Ensure `create()` has been called beforehand to get meaningful output.
        """
        return dumps(self.doc)

    def get_document(self) -> document:
        """
        Returns:
            document: The TOML document object.
            Ensure `create()` has been called beforehand to get meaningful output.
        """
        return self.doc


class TOMLPublishableEntityVersionFile(TOMLMixin):
    """
    Class to create a .toml representation of a PublishableEntityVersion instance.

    This class builds a structured TOML document using `tomlkit` with metadata and fields
    extracted from a `PublishableEntityVersion` object. The output can later be saved to a file or used elsewhere.
    """

    def __init__(
            self,
            publishable_entity_version: PublishableEntityVersionMixin,
            versions: aot,
            existing_doc: document = None
    ):
        super().__init__(existing_doc)
        self.publishable_entity_version = publishable_entity_version
        self.versions = versions  # Array Of Tables

    def create(self) -> None:
        """
        Populates the TOML document with a header and a table containing
        metadata from the PublishableEntityVersion instance.

        This method must be called before calling `get()`, otherwise the document will be empty.
        """
        version_table = self._create_table({
            "title": self.publishable_entity_version.title,
            "uuid": str(self.publishable_entity_version.uuid),
            "version_num": self.publishable_entity_version.version_num,
        })

        container_table = self._create_table({
            "children": [],
        })
        version_table.add("container", container_table)

        unit_table = self._create_table({
            "graded": True,
        })
        container_table.add("unit", unit_table)

        # Add version information to array of tables
        self.versions.append(version_table)


class TOMLPublishableEntityFile(TOMLMixin):
    """
    Class to create a .toml representation of a PublishableEntity instance.

    This class builds a structured TOML document using `tomlkit` with metadata and fields
    extracted from a `PublishableEntity` object. The output can later be saved to a file or used elsewhere.
    """

    def __init__(self, publishable_entity: PublishableEntityMixin):
        super().__init__()
        self.aot = aot()  # Array Of Tables
        self.publishable_entity = publishable_entity
        self.draft_version = publishable_entity.versioning.draft
        self.published_version = publishable_entity.versioning.published

    def create(self) -> None:
        """
        Populates the TOML document with a header and a table containing
        metadata from the PublishableEntity instance.

        This method must be called before calling `get()`, otherwise the document will be empty.
        """
        # PublishableEntity metadata
        entity = self._create_table({
            "uuid": str(self.publishable_entity.uuid),
            "can_stand_alone": self.publishable_entity.can_stand_alone,
        })

        # PublishableEntity draft metadata
        entity_draft = self._create_table({
            "version_num": self.publishable_entity.versioning.draft.version_num,
        })
        entity.add("draft", entity_draft)

        # PublishableEntity published metadata
        if self.published_version is None:
            draft_table = self._create_table({})
            draft_table.add(comment("unpublished: no published_version_num"))
            entity.add("published", draft_table)
        else:
            entity_published = self._create_table({
                "version_num": self.publishable_entity.versioning.published.version_num,
            })
            entity.add("published", entity_published)
        self.doc.add("entity", entity)
        self.add_nl()
        self.add_comment("### Versions")

    def add_versions_to_document(self) -> None:
        """
        Adds the version information to the document.
        This method should be called after `create()` to ensure the document is populated.
        """
        self.doc.add("version", self.aot)


class TOMLLearningPackageFile(TOMLMixin):
    """
    Class to create a .toml representation of a LearningPackage instance.

    This class builds a structured TOML document using `tomlkit` with metadata and fields
    extracted from a `LearningPackage` object. The output can later be saved to a file or used elsewhere.
    """

    def __init__(self, learning_package: LearningPackage):
        super().__init__()
        self.learning_package = learning_package

    def _create_header(self) -> None:
        """
        Adds a comment with the current datetime to indicate when the export occurred.
        This helps with traceability and file versioning.
        """
        self.add_comment(f"Datetime of the export: {datetime.now()}")

    def create(self) -> None:
        """
        Populates the TOML document with a header and a table containing
        metadata from the LearningPackage instance.

        This method must be called before calling `get()`, otherwise the document will be empty.
        """
        self._create_header()
        section = self._create_table({
            "title": self.learning_package.title,
            "key": self.learning_package.key,
            "description": self.learning_package.description,
            "created": self.learning_package.created,
            "updated": self.learning_package.updated
        })
        self.doc.add("learning_package", section)
