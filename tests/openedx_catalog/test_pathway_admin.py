"""
Tests of the Django admin for the catalog half of Pathways.
"""
# mypy: disable-error-code="misc"
# (Ignore 'Unexpected attribute "org_code" for model "CatalogPathway"' until
#  https://github.com/typeddjango/django-stubs/issues/1034 is fixed.)

import pytest
from django.contrib import admin

from openedx_catalog.admin import CatalogPathwayAdmin, PathwayCategoryAdmin
from openedx_catalog.models import CatalogPathway, PathwayCategory
from openedx_catalog.models.pathway_category import DEFAULT_PATHWAY_CATEGORY_CODE

pytestmark = pytest.mark.django_db


@pytest.fixture(name="default_category")
def _default_category() -> PathwayCategory:
    """The category shipped by the initial migration"""
    return PathwayCategory.objects.get(category_code=DEFAULT_PATHWAY_CATEGORY_CODE)


def test_category_list_shows_the_plural_learners_see(default_category) -> None:
    """The derived plural when none is set, so operators can spot titles that need an explicit one."""
    model_admin = PathwayCategoryAdmin(PathwayCategory, admin.site)
    assert model_admin.title_plural_display(default_category) == "Pathways"

    default_category.title_plural = "Pathways of Study"
    assert model_admin.title_plural_display(default_category) == "Pathways of Study"


def test_add_form_preselects_the_default_category(default_category, rf, admin_user) -> None:
    model_admin = CatalogPathwayAdmin(CatalogPathway, admin.site)
    request = rf.get("/")
    request.user = admin_user
    assert model_admin.get_changeform_initial_data(request)["category"] == str(default_category.pk)


def test_add_form_preselects_nothing_once_the_default_is_deleted(default_category, rf, admin_user) -> None:
    default_category.delete()
    model_admin = CatalogPathwayAdmin(CatalogPathway, admin.site)
    request = rf.get("/")
    request.user = admin_user
    assert "category" not in model_admin.get_changeform_initial_data(request)
