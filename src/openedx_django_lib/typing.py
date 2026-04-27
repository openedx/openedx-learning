"""
Utilities and types for working with strongly-typed Django code.
"""
import typing as t

from django.db.models import Model

_Model_T = t.TypeVar("_Model_T", bound=Model)
_ModelID_T = t.TypeVar("_ModelID_T", bound=int)


def get_model_id(model_or_id: _Model_T | _ModelID_T, /) -> _ModelID_T:
    """
    Given a variable that could be a model instance or its ID, return the ID.

    Raises a TypeError if called on a model without an `.id` attribute.
    Most of our models have `.id` integer PK fields, or `.id` @properties which proxy to a 1-1 model,
    but some models (e.g. ManyToManys) do not.
    """
    if isinstance(model_or_id, Model):
        try:
            return t.cast(_ModelID_T, model_or_id.id)  # type: ignore[attr-defined]
        except AttributeError as exc:
            raise TypeError("get_model_id is only valid on models with an `id` field.") from exc
    return t.cast(_ModelID_T, model_or_id)
