"""
Tests for our django typing utils
"""
from typing import NewType, assert_type

from django.db import models

from openedx_django_lib.fields import TypedBigAutoField
from openedx_django_lib.typing import get_model_id


class Foo(models.Model):
    """
    A model with a typed ID field
    """
    FooID = NewType("FooID", int)
    type ID = FooID

    class IDField(TypedBigAutoField[ID]):
        pass

    id = IDField(primary_key=True)


def test_get_model_id() -> None:
    """
    Test that get_model_id behaves as expected, both at runtime and during typechecking.
    """
    foo = Foo()

    # Sanity checks
    assert_type(foo, Foo)
    assert_type(foo.id, Foo.ID)

    # get_model_id on a model returns its id
    assert get_model_id(foo) == foo.id
    assert_type(get_model_id(foo), Foo.ID)

    # get_model_id on an id returns itself
    assert get_model_id(foo.id) == foo.id
    assert_type(get_model_id(foo.id), Foo.ID)
    