"""
Utilities for backup and restore app
"""

from datetime import datetime
from typing import Any, Dict

from tomlkit import comment, document, dumps, nl, table
from tomlkit.items import Table


class LpTomlFile():
    """
    Class to create a .toml file of a learning package (WIP)
    """

    def __init__(self):
        self.doc = document()

    def _create_header(self) -> None:
        self.doc.add(comment(f"Datetime of the export: {datetime.now()}"))
        self.doc.add(nl())
        self.doc.add("title", "Learning package example")

    def _create_table(self, params: Dict[str, Any]) -> Table:
        section = table()
        for key, value in params.items():
            section.add(key, value)
        return section

    def create(self, lp_key: str) -> None:
        """
        Process the toml file
        """
        self._create_header()
        section = self._create_table({
            "title": "",
            "key": lp_key,
            "description": "",
            "created": "",
            "updated": ""
        })
        self.doc.add("Learning package", section)

    def get(self) -> str:
        return dumps(self.doc)
