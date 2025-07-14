"""
Utilities for backup and restore app
"""

from datetime import datetime
from typing import Any, Dict

from tomlkit import comment, document, dumps, nl, table
from tomlkit.items import Table

from openedx_learning.apps.authoring.publishing.models.learning_package import LearningPackage
from openedx_learning.apps.authoring.publishing.models.publishable_entity import PublishableEntityMixin


class TOMLMixin:
    """
    Mixin class to provide common functionality for TOML file generation.
    This class can be extended by other classes that need to generate TOML files.
    """

    def __init__(self):
        self.doc = document()

    def _create_table(self, params: Dict[str, Any]) -> Table:
        """
        Builds a TOML table section from a dictionary of key-value pairs.
        """
        section = table()
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


class TOMLPublishableEntityFile(TOMLMixin):
    """
    Class to create a .toml representation of a PublishableEntity instance.

    This class builds a structured TOML document using `tomlkit` with metadata and fields
    extracted from a `PublishableEntity` object. The output can later be saved to a file or used elsewhere.
    """

    def __init__(self, publishable_entity: PublishableEntityMixin):
        super().__init__()
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
            "created": self.publishable_entity.created,
        })
        self.doc.add("entity", entity)

        # PublishableEntity draft metadata
        entity_draft = self._create_table({
            "version_num": self.publishable_entity.versioning.draft.version_num,
        })
        self.doc.add("entity_draft", entity_draft)

        # PublishableEntity published metadata
        if self.published_version is None:
            self.doc.add("entity_published", self._create_table({}))
            self.doc.add(comment("unpublished: no published_version_num"))
            self.doc.add(nl())
        else:
            entity_published = self._create_table({
                "version_num": self.publishable_entity.versioning.published.version_num,
            })
            self.doc.add("entity_published", entity_published)


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
        self.doc.add(comment(f"Datetime of the export: {datetime.now()}"))
        self.doc.add(nl())

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
