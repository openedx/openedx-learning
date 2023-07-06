"""
Registry for object tag classes
"""
import logging
from typing import Type

log = logging.getLogger(__name__)

# Global registry
_OBJECT_TAG_CLASS_REGISTRY = []


def register_object_tag_class(cls):
    """
    Register a given class as a candidate object tag class.

    The class must have a `valid_for` class method.
    """
    assert hasattr(cls, "valid_for")
    _OBJECT_TAG_CLASS_REGISTRY.append(cls)


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

    # Return the most recently-registered, appropriate object tag class
    for ObjectTagClass in reversed(_OBJECT_TAG_CLASS_REGISTRY):
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
