"""
Public API for Competency-Based Education (CBE).
"""
from __future__ import annotations

from django.db.models import QuerySet

from openedx_tagging.models import Taxonomy

__all__ = [
    "is_competency_taxonomy",
    "select_competency_taxonomies",
]


def is_competency_taxonomy(taxonomy: Taxonomy) -> bool:
    """
    Return True if ``taxonomy`` is competency-enabled, i.e. has a CompetencyTaxonomy row.

    Costs one query per call unless ``taxonomy`` came from a queryset passed through
    :func:`select_competency_taxonomies`. Returns False for an unsaved ``taxonomy``.
    """
    # "competencytaxonomy" is the accessor Django generates for the multi-table-inheritance
    # link from Taxonomy to CompetencyTaxonomy.
    return hasattr(taxonomy, "competencytaxonomy")


def select_competency_taxonomies(taxonomies: QuerySet[Taxonomy]) -> QuerySet[Taxonomy]:
    """
    Return ``taxonomies`` with each CompetencyTaxonomy row joined in.

    Pair this with :func:`is_competency_taxonomy` when checking more than one taxonomy,
    so the check costs no additional query per row.
    """
    return taxonomies.select_related("competencytaxonomy")
