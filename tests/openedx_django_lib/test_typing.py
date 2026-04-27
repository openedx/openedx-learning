"""
Tests for our django typing utils
"""
from typing import assert_type

from tests.test_django_app.models import MyTypedModel, RelatedTypedModel

from openedx_django_lib.typing import get_model_id


def test_get_model_id() -> None:
    """
    Test that get_model_id behaves as expected, both at runtime and during typechecking.
    """
    my_model = MyTypedModel()
    related_model = RelatedTypedModel(my_model=my_model)

    # Sanity checks
    assert_type(my_model, MyTypedModel)
    assert_type(my_model.id, MyTypedModel.ID)
    assert_type(related_model.my_model, MyTypedModel)
    assert_type(related_model.my_model.id, MyTypedModel.ID)
    assert_type(related_model.my_model_id, MyTypedModel.ID)

    # get_model_id on a model returns its id
    assert get_model_id(my_model) == my_model.id
    assert_type(get_model_id(my_model), MyTypedModel.ID)
    assert get_model_id(related_model.my_model) == my_model.id
    assert_type(get_model_id(related_model.my_model), MyTypedModel.ID)

    # get_model_id on an id returns itself
    assert get_model_id(my_model.id) == my_model.id
    assert_type(get_model_id(my_model.id), MyTypedModel.ID)
    assert get_model_id(related_model.my_model.id) == my_model.id
    assert_type(get_model_id(related_model.my_model.id), MyTypedModel.ID)
