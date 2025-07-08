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
    Class to create a .toml file of a learning package (WIP)
    """

    def __init__(self, learning_package: LearningPackage):
        self.doc = document()
        self.learning_package = learning_package

    def _create_header(self) -> None:
        self.doc.add(comment(f"Datetime of the export: {datetime.now()}"))
        self.doc.add(nl())

    def _create_table(self, params: Dict[str, Any]) -> Table:
        section = table()
        for key, value in params.items():
            section.add(key, value)
        return section

    def create(self) -> None:
        """
        Process the toml file
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
        return dumps(self.doc)
