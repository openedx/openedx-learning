"""
Tests of the Django admin for the catalog half of Pathways.
"""
# mypy: disable-error-code="misc"
# (Ignore 'Unexpected attribute "org_code" for model "CatalogPathway"' until
#  https://github.com/typeddjango/django-stubs/issues/1034 is fixed.)

import pytest
from django.contrib import admin
from organizations.api import ensure_organization  # type: ignore[import]

from openedx_catalog.admin import CatalogPathwayAdmin, PathwayCategoryAdmin
from openedx_catalog.models import CatalogPathway, PathwayCategory, PathwayCategoryTranslation
from openedx_catalog.models.pathway_category import DEFAULT_PATHWAY_CATEGORY_CODE

pytestmark = pytest.mark.django_db


@pytest.fixture(name="default_category")
def _default_category() -> PathwayCategory:
    """The category shipped by the initial migration"""
    return PathwayCategory.objects.get(category_code=DEFAULT_PATHWAY_CATEGORY_CODE)


def test_pathway_count_is_not_inflated_by_searching_translations(default_category, rf, admin_user) -> None:
    """
    Searching joins in the translations, so a category with two pathways and two matching translations must still
    count two pathways, not four.
    """
    ensure_organization("Org1")
    CatalogPathway.objects.create(org_code="Org1", pathway_code="First", category=default_category)
    CatalogPathway.objects.create(org_code="Org1", pathway_code="Second", category=default_category)
    PathwayCategoryTranslation.objects.create(pathway_category=default_category, language_code="fr", title="Pathway FR")
    PathwayCategoryTranslation.objects.create(pathway_category=default_category, language_code="de", title="Pathway DE")

    model_admin = PathwayCategoryAdmin(PathwayCategory, admin.site)
    request = rf.get("/", {"q": "Pathway"})
    request.user = admin_user
    queryset = model_admin.get_queryset(request)
    results, _may_have_duplicates = model_admin.get_search_results(request, queryset, "Pathway")

    assert {category.pathway_count for category in results.distinct()} == {2}


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
