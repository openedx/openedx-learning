"""
Data models used by openedx-tagging
"""
from __future__ import annotations

from typing import TypedDict


class TagData(TypedDict):
    """
    Data about a single tag. Many of the tagging API methods return Django
    QuerySets that resolve to these dictionaries.

    Even though the data will be in this same format, it will not necessarily
    be an instance of this class but rather a plain dictionary. This is more a
    type than a class.
    """
    value: str
    external_id: str | None
    child_count: int
    depth: int
    parent_value: str | None
    # Note: usage_count may not actually be present but there's no way to indicate that w/ python types at the moment
    usage_count: int
    # Internal database ID, if any. Generally should not be used; prefer 'value' which is unique within each taxonomy.
    _id: int | None
