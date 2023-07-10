"""
Registry for object tag classes
"""
import logging
from typing import Type

log = logging.getLogger(__name__)

# Global registry
_OBJECT_TAG_CLASS_REGISTRY = []


def register_object_tag_class(cls, index=0):
    """
    Register a given class as a candidate object tag class.

    By default, inserts the given class at the beginning of the list, so that it will be considered before all
    previously-registered classes. Adjust ``index`` to change where the class will be considered.

    The class must have a `valid_for` class method.
    """
    assert hasattr(cls, "valid_for")
    _OBJECT_TAG_CLASS_REGISTRY.insert(index, cls)


def get_object_tag_class(
    taxonomy: "Taxonomy" = None,
    object_id: str = None,
    object_type: str = None,
    tag: "Tag" = None,
    value: str = None,
    name: str = None,
) -> Type:
    """
    Returns the most appropriate ObjectTag subclass for the given attributes.
    """
    # Some taxonomies have custom object tag classes applied.
    if taxonomy:
        try:
            ObjectTagClass = taxonomy.object_tag_class
            if ObjectTagClass:
                # Should we also verify ObjectTagClass.valid_for ?
                return ObjectTagClass
        except ImportError:
            # Log error and continue
            log.exception(f"Unable to import custom object_tag_class for {taxonomy}")

    # Return the first appropriate object tag class
    for ObjectTagClass in _OBJECT_TAG_CLASS_REGISTRY:
        if ObjectTagClass.valid_for(
            taxonomy=taxonomy,
            object_type=object_type,
            object_id=object_id,
            tag=tag,
            name=name,
            value=value,
        ):
            return ObjectTagClass

    # We should never reach here -- ObjectTag is always valid, and the last class checked.
    return None  # pragma: no cover
