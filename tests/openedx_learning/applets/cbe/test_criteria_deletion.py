"""
Delete-behavior tests for CompetencyCriteriaGroup, CompetencyRuleProfile, and CompetencyCriterion.

Every foreign key these three models declare is currently `on_delete=models.PROTECT`; see the
module docstring in `openedx_learning.applets.cbe.models.criteria` for why that is the current
fail-closed value rather than a settled one, and what is still open about it on #655.
"""
import pytest
from django.db.models import ProtectedError
from organizations.api import ensure_organization
from organizations.models import Organization

from openedx_catalog.models import CatalogCourse, CourseRun
from openedx_learning.models import (
    CompetencyCriteriaGroup,
    CompetencyCriterion,
    CompetencyRuleProfile,
    CompetencyTaxonomy,
    RuleType,
)
from openedx_tagging.models import ObjectTag, Tag

pytestmark = pytest.mark.django_db

_GRADE_PAYLOAD = {"op": "gte", "value": 0.8, "scale": "percent"}


@pytest.fixture(name="organization")
def _organization() -> Organization:
    """An Organization for use as a scope in these tests."""
    ensure_organization("Org1")
    return Organization.objects.get(short_name="Org1")


@pytest.fixture(name="organization2")
def _organization2() -> Organization:
    """A second Organization, distinct from `organization`, for use as a scope in these tests."""
    ensure_organization("Org2")
    return Organization.objects.get(short_name="Org2")


@pytest.fixture(name="course_run")
def _course_run(organization: Organization) -> CourseRun:
    """A CourseRun for use as a scope in these tests."""
    catalog_course = CatalogCourse.objects.create(org=organization, course_code="Python100")
    return CourseRun.objects.create(catalog_course=catalog_course, run_code="Fall2026")


@pytest.fixture(name="competency_taxonomy")
def _competency_taxonomy() -> CompetencyTaxonomy:
    """A CompetencyTaxonomy for use as a scope, and as the home taxonomy for `tag`."""
    return CompetencyTaxonomy.objects.create(name="Nursing", export_id="nursing-v1")


@pytest.fixture(name="tag")
def _tag(competency_taxonomy: CompetencyTaxonomy) -> Tag:
    """A Tag, from `competency_taxonomy`, for use as the competency a criteria tree evaluates."""
    return Tag.objects.create(taxonomy=competency_taxonomy, value="Writing Poetry")


@pytest.fixture(name="object_tag")
def _object_tag(competency_taxonomy: CompetencyTaxonomy, tag: Tag) -> ObjectTag:
    """An ObjectTag associating `tag` with a made-up content object, for use as a criterion's target."""
    return ObjectTag.objects.create(
        object_id="block-v1:Org1+Python100+Fall2026+problem+p1",
        taxonomy=competency_taxonomy,
        tag=tag,
    )


@pytest.fixture(name="group")
def _group(tag: Tag) -> CompetencyCriteriaGroup:
    """A root CompetencyCriteriaGroup for `tag`, for use as a criterion's parent group."""
    return CompetencyCriteriaGroup.objects.create(tag=tag)


@pytest.fixture(name="default_rule_profile")
def _default_rule_profile() -> CompetencyRuleProfile:
    """The system-default CompetencyRuleProfile seeded by migration 0003."""
    return CompetencyRuleProfile.objects.get(
        organization__isnull=True,
        course__isnull=True,
        competency_taxonomy__isnull=True,
    )


# ==============================================================================================
# One test per foreign key, all nine currently PROTECT. Each asserts on the raised
# ProtectedError's `protected_objects`, not just its type: several protected relationships can
# fire on one delete (see test_rule_profile_organization_protect and
# test_rule_profile_competency_taxonomy_protect below for two real traps of that kind), so a bare
# `pytest.raises(ProtectedError)` would not actually prove which foreign key did the protecting.
# ==============================================================================================


def test_group_parent_protect(tag: Tag) -> None:
    """
    Deleting a CompetencyCriteriaGroup that another group's `parent` points at raises
    ProtectedError. Django's PROTECT raises even though the referencing child group is not part
    of this delete call; nothing about `parent` being a self-referential, tree-shaped
    relationship exempts it from that.
    """
    root = CompetencyCriteriaGroup.objects.create(tag=tag)
    child = CompetencyCriteriaGroup.objects.create(tag=tag, parent=root)

    with pytest.raises(ProtectedError) as exc_info:
        root.delete()

    protected = exc_info.value.protected_objects
    assert any(isinstance(obj, CompetencyCriteriaGroup) and obj.pk == child.pk for obj in protected)


def test_group_tag_protect(tag: Tag, group: CompetencyCriteriaGroup) -> None:
    """Deleting a Tag that a CompetencyCriteriaGroup references via `tag` raises ProtectedError."""
    with pytest.raises(ProtectedError) as exc_info:
        tag.delete()

    protected = exc_info.value.protected_objects
    assert any(isinstance(obj, CompetencyCriteriaGroup) and obj.pk == group.pk for obj in protected)


def test_group_course_protect(tag: Tag, course_run: CourseRun) -> None:
    """Deleting a CourseRun that a CompetencyCriteriaGroup references via `course` raises ProtectedError."""
    group = CompetencyCriteriaGroup.objects.create(tag=tag, course=course_run)

    with pytest.raises(ProtectedError) as exc_info:
        course_run.delete()

    protected = exc_info.value.protected_objects
    assert any(isinstance(obj, CompetencyCriteriaGroup) and obj.pk == group.pk for obj in protected)


def test_rule_profile_organization_protect(organization2: Organization) -> None:
    """
    Deleting an Organization that a CompetencyRuleProfile references via `organization` raises
    ProtectedError naming the profile.

    Uses `organization2`, which this test never attaches a CatalogCourse to, instead of
    `organization` (the one `course_run` uses elsewhere in this module): CatalogCourse.org is
    itself PROTECT, so deleting an organization with a CatalogCourse attached raises
    ProtectedError regardless of whether a CompetencyRuleProfile references it too, and this
    test would pass for the wrong reason.
    """
    profile = CompetencyRuleProfile.objects.create(
        organization=organization2, rule_type=RuleType.GRADE, rule_payload=_GRADE_PAYLOAD
    )

    with pytest.raises(ProtectedError) as exc_info:
        organization2.delete()

    protected = exc_info.value.protected_objects
    assert any(isinstance(obj, CompetencyRuleProfile) and obj.pk == profile.pk for obj in protected)


def test_rule_profile_course_protect(course_run: CourseRun) -> None:
    """Deleting a CourseRun that a CompetencyRuleProfile references via `course` raises ProtectedError."""
    profile = CompetencyRuleProfile.objects.create(
        course=course_run, rule_type=RuleType.GRADE, rule_payload=_GRADE_PAYLOAD
    )

    with pytest.raises(ProtectedError) as exc_info:
        course_run.delete()

    protected = exc_info.value.protected_objects
    assert any(isinstance(obj, CompetencyRuleProfile) and obj.pk == profile.pk for obj in protected)


def test_rule_profile_competency_taxonomy_protect(competency_taxonomy: CompetencyTaxonomy) -> None:
    """
    Deleting a CompetencyTaxonomy that a CompetencyRuleProfile references via
    `competency_taxonomy` raises ProtectedError naming the profile.

    Deliberately does not use the `tag` or `group` fixtures: a Tag under this taxonomy would be
    collected by Tag.taxonomy's CASCADE, and a CompetencyCriteriaGroup referencing that tag would
    then hit its own `tag` PROTECT (see test_taxonomy_delete_blocked_by_group_tag_protection
    below), which would raise ProtectedError without this test having exercised
    CompetencyRuleProfile.competency_taxonomy at all.
    """
    profile = CompetencyRuleProfile.objects.create(
        competency_taxonomy=competency_taxonomy, rule_type=RuleType.GRADE, rule_payload=_GRADE_PAYLOAD
    )

    with pytest.raises(ProtectedError) as exc_info:
        competency_taxonomy.delete()

    protected = exc_info.value.protected_objects
    assert any(isinstance(obj, CompetencyRuleProfile) and obj.pk == profile.pk for obj in protected)


def test_criterion_group_protect(
    group: CompetencyCriteriaGroup, object_tag: ObjectTag, default_rule_profile: CompetencyRuleProfile
) -> None:
    """
    Deleting a CompetencyCriteriaGroup that a CompetencyCriterion references via `group` raises
    ProtectedError, even though the criterion is not itself part of this delete call.
    """
    criterion = CompetencyCriterion.objects.create(
        group=group, object_tag=object_tag, rule_profile=default_rule_profile
    )

    with pytest.raises(ProtectedError) as exc_info:
        group.delete()

    protected = exc_info.value.protected_objects
    assert any(isinstance(obj, CompetencyCriterion) and obj.pk == criterion.pk for obj in protected)


def test_criterion_object_tag_protect(
    group: CompetencyCriteriaGroup, object_tag: ObjectTag, default_rule_profile: CompetencyRuleProfile
) -> None:
    """Deleting an ObjectTag that a CompetencyCriterion references via `object_tag` raises ProtectedError."""
    criterion = CompetencyCriterion.objects.create(
        group=group, object_tag=object_tag, rule_profile=default_rule_profile
    )

    with pytest.raises(ProtectedError) as exc_info:
        object_tag.delete()

    protected = exc_info.value.protected_objects
    assert any(isinstance(obj, CompetencyCriterion) and obj.pk == criterion.pk for obj in protected)


def test_criterion_rule_profile_protect(
    group: CompetencyCriteriaGroup, object_tag: ObjectTag, default_rule_profile: CompetencyRuleProfile
) -> None:
    """
    Deleting a CompetencyRuleProfile that a CompetencyCriterion references via `rule_profile`
    raises ProtectedError.
    """
    criterion = CompetencyCriterion.objects.create(
        group=group, object_tag=object_tag, rule_profile=default_rule_profile
    )

    with pytest.raises(ProtectedError) as exc_info:
        default_rule_profile.delete()

    protected = exc_info.value.protected_objects
    assert any(isinstance(obj, CompetencyCriterion) and obj.pk == criterion.pk for obj in protected)


def test_taxonomy_delete_blocked_by_group_tag_protection(
    competency_taxonomy: CompetencyTaxonomy, group: CompetencyCriteriaGroup
) -> None:
    """
    #655's approved design promises that deleting a CompetencyTaxonomy whose tag no learner holds
    mastery against succeeds as a plain hard delete: Tag.taxonomy is CASCADE, so the tag is
    collected along with the taxonomy. `PROTECT` on CompetencyCriteriaGroup.tag currently breaks
    that promise instead: the delete collects `tag` via CASCADE, then `group`'s reference to that
    tag hits PROTECT and the whole delete is refused, even though no learner has been graded
    against it (there is no learner-status table yet at all).

    This conflict is open on #655 (see the module docstring in
    openedx_learning.applets.cbe.models.criteria) and unresolved as of this writing. Whichever
    way it resolves, this test is the one that has to change: if CompetencyCriteriaGroup.tag
    moves to CASCADE, this becomes an assertion that the delete succeeds instead of raising.
    """
    with pytest.raises(ProtectedError) as exc_info:
        competency_taxonomy.delete()

    protected = exc_info.value.protected_objects
    assert any(isinstance(obj, CompetencyCriteriaGroup) and obj.pk == group.pk for obj in protected)
