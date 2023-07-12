"""
Registry for object tag classes
"""
import logging
from typing import Iterator, Type

log = logging.getLogger(__name__)

# Global registry
_OBJECT_TAG_CLASS_REGISTRY = []


def register_object_tag_class(cls, index=0):
    """
    Register a given class as a candidate object tag class.

    By default, inserts the given class at the beginning of the list, so that it will be considered before all
    previously-registered classes. Adjust ``index`` to change where the class will be considered.
    """
    _OBJECT_TAG_CLASS_REGISTRY.insert(index, cls)


def cast_object_tag(object_tag: "ObjectTag") -> "ObjectTag":
    """
    Returns the most appropriate ObjectTag subclass for the given attributes.

    If no ObjectTag subclasses are found, then returns None.
    """
    # Some taxonomies have custom object tag classes applied.
    if object_tag.taxonomy_id:
        taxonomy = object_tag.taxonomy
        try:
            ObjectTagClass = taxonomy.object_tag_class
            if ObjectTagClass:
                return ObjectTagClass().copy(object_tag)
        except ImportError:
            # Log error and continue
            log.exception(f"Unable to import custom object_tag_class for {taxonomy}")

    # Return the first appropriate object tag class
    for ObjectTagClass in _OBJECT_TAG_CLASS_REGISTRY:
        cast_object_tag = ObjectTagClass().copy(object_tag)

        if cast_object_tag.is_valid():
            return cast_object_tag

    return None
