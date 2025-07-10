"""
Utilities for backup and restore app
"""

from datetime import datetime
from typing import Any, Dict

from tomlkit import comment, document, dumps, nl, table
from tomlkit.items import Table

from openedx_learning.apps.authoring.publishing.models.learning_package import LearningPackage


class TOMLLearningPackageFile():
    """
    Class to create a .toml representation of a LearningPackage instance.

    This class builds a structured TOML document using `tomlkit` with metadata and fields
    extracted from a `LearningPackage` object. The output can later be saved to a file or used elsewhere.
    """

    def __init__(self, learning_package: LearningPackage):
        self.doc = document()
        self.learning_package = learning_package

    def _create_header(self) -> None:
        """
        Adds a comment with the current datetime to indicate when the export occurred.
        This helps with traceability and file versioning.
        """
        self.doc.add(comment(f"Datetime of the export: {datetime.now()}"))
        self.doc.add(nl())

    def _create_table(self, params: Dict[str, Any]) -> Table:
        """
        Builds a TOML table section from a dictionary of key-value pairs.

        Args:
            params (Dict[str, Any]): A dictionary containing keys and values to include in the TOML table.

        Returns:
            Table: A TOML table populated with the provided keys and values.
        """
        section = table()
        for key, value in params.items():
            section.add(key, value)
        return section

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

    def get(self) -> str:
        """
        Returns:
            str: The string representation of the generated TOML document.
            Ensure `create()` has been called beforehand to get meaningful output.
        """
        return dumps(self.doc)
