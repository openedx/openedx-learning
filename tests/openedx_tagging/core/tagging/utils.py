"""
Useful utilities for testing tagging and taxonomy code.
"""
from __future__ import annotations


def pretty_format_tags(result, parent=True, external_id=False, usage_count=True) -> list[str]:
    """
    Format the result of get_filtered_tags() to be more human readable.

    Also works with other wrappers around get_filtered_tags, like api.get_tags()
    Also works with serialized TagData from the REST API.
    """
    pretty_results = []
    for t in result:
        line = f"{t['depth'] * '  '}{t['value']} "
        if external_id:
            line += f"({t['external_id']}) "
        if parent:
            line += f"({t['parent_value']}) "
        line += "("
        if usage_count:
            line += f"used: {t.get('usage_count', '?')}, "
        line += f"children: {t['child_count']})"
        pretty_results.append(line)
    return pretty_results
