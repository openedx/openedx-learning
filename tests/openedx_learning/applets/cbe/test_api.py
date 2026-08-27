"""
Tests for the CBE public API surface (openedx_learning.api).
"""
import pytest

from openedx_learning.api import is_competency_taxonomy, select_competency_taxonomies
from openedx_learning.models import CompetencyTaxonomy
from openedx_tagging.models import Taxonomy

pytestmark = pytest.mark.django_db


def test_is_competency_taxonomy() -> None:
    """
    is_competency_taxonomy() is True for a competency taxonomy, False for a plain one.
    """
    competency = CompetencyTaxonomy.objects.create(name="Nursing", export_id="nursing-v1")
    plain = Taxonomy.objects.create(name="Plain Tags", export_id="plain-v1")

    assert is_competency_taxonomy(Taxonomy.objects.get(pk=competency.pk)) is True
    assert is_competency_taxonomy(plain) is False


def test_is_competency_taxonomy_on_child_instance_directly() -> None:
    """
    is_competency_taxonomy() also returns True when handed a CompetencyTaxonomy
    instance directly, not just a parent Taxonomy fetched from the DB.
    """
    competency = CompetencyTaxonomy.objects.create(name="Nursing", export_id="nursing-v1")
    assert is_competency_taxonomy(competency) is True


def test_is_competency_taxonomy_on_unsaved_instance() -> None:
    """
    is_competency_taxonomy() returns False for an unsaved Taxonomy, rather than raising.
    """
    # pk is None, so the reverse one-to-one descriptor short-circuits and raises
    # RelatedObjectDoesNotExist, which Django defines as an AttributeError subclass
    # precisely so hasattr() catches it here instead of propagating.
    unsaved = Taxonomy(name="Unsaved", export_id="unsaved-v1")
    assert is_competency_taxonomy(unsaved) is False


def test_select_competency_taxonomies_avoids_n_plus_1(django_assert_num_queries) -> None:
    """
    select_competency_taxonomies() joins the CompetencyTaxonomy row in, so checking
    is_competency_taxonomy() on every row in the queryset costs one query, not N+1.
    """
    competency1 = CompetencyTaxonomy.objects.create(name="Nursing", export_id="nursing-v1")
    competency2 = CompetencyTaxonomy.objects.create(name="Welding", export_id="welding-v1")
    plain = Taxonomy.objects.create(name="Plain Tags", export_id="plain-v1")
    # Scoped to just these three: unfiltered Taxonomy.objects.all() would also pick up
    # any taxonomies seeded outside this test, which would make the True/False counts
    # below depend on incidental fixture data.
    taxonomies = Taxonomy.objects.filter(pk__in=[competency1.pk, competency2.pk, plain.pk])

    with django_assert_num_queries(1):
        results = [is_competency_taxonomy(t) for t in select_competency_taxonomies(taxonomies)]

    assert results.count(True) == 2
    assert results.count(False) == 1
