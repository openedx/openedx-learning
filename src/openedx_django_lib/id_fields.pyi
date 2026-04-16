"""
Expanded type definitions to support fully-typed integer primary key fields
"""

from typing import TypeVar

from django.db import models

_IDType = TypeVar("_IDType", bound=int)

class TypedBigAutoField(models.BigAutoField[_IDType, _IDType]):
    _pyi_private_set_type: _IDType | int
    _pyi_private_get_type: _IDType

class TypedAutoField(models.AutoField[_IDType, _IDType]):
    _pyi_private_set_type: _IDType | int
    _pyi_private_get_type: _IDType
