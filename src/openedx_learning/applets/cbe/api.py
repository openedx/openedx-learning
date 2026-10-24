"""
Public API for Competency-Based Education (CBE).
"""
from __future__ import annotations

import logging
from datetime import datetime, timezone
from decimal import Decimal
from typing import Any, Sequence

from django.core.exceptions import ValidationError
from django.db import connection, transaction
from django.db.models import QuerySet
from django.db.transaction import TransactionManagementError
from django.utils.translation import gettext_lazy as _
from opaque_keys import InvalidKeyError
from opaque_keys.edx.keys import UsageKey

from openedx_catalog.api import get_course_run
from openedx_catalog.models_api import CourseRun
from openedx_tagging.api import create_taxonomy, get_object_tags, tag_object
from openedx_tagging.models import ObjectTag, Tag, Taxonomy

from .data import GradedObjectScore
from .models import (
    CompetencyCriteriaGroup,
    CompetencyCriterion,
    CompetencyRuleProfile,
    CompetencyTaxonomy,
    LogicOperator,
    MasteryStatus,
    StudentCompetencyCriterionStatus,
)
from .rule_payloads import evaluate_rule

__all__ = [
    "GradedObjectScore",
    "associate_competency_criterion",
    "create_competency_criterion",
    "create_competency_taxonomy",
    "get_competency_rule_profiles",
    "is_competency_taxonomy",
    "record_graded_object_statuses",
    "resolve_competency_tag",
    "resolve_supplied_leaf_group",
    "select_competency_taxonomies",
]

log = logging.getLogger(__name__)


def create_competency_taxonomy(  # pylint: disable=too-many-positional-arguments
    name: str,
    description: str | None = None,
    enabled=True,
    allow_multiple=True,
    allow_free_text=False,
    read_only=False,
    export_id: str | None = None,
) -> CompetencyTaxonomy:
    """
    Create, save, and return a new CompetencyTaxonomy with the given attributes.
    """
    taxonomy = create_taxonomy(
        name=name,
        description=description,
        enabled=enabled,
        allow_multiple=allow_multiple,
        allow_free_text=allow_free_text,
        read_only=read_only,
        export_id=export_id,
        taxonomy_cls=CompetencyTaxonomy,
    )
    assert isinstance(taxonomy, CompetencyTaxonomy)
    return taxonomy


def get_competency_rule_profiles() -> QuerySet[CompetencyRuleProfile]:
    """
    Return every live CompetencyRuleProfile, in ascending ``id`` order.

    UNSTABLE: the rule profile family is incomplete, so the create, update, and archive entry
    points still to come may change this function's shape without a deprecation cycle.

    Archived profiles are left out: retirement is archive-only.

    The ordering is part of the contract rather than a cosmetic detail: an unordered queryset
    gives a paginating caller overlapping and skipped pages.
    """
    return CompetencyRuleProfile.objects.filter(archived=False).order_by("id")


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


def resolve_competency_tag(tag_id: int) -> Tag:
    """
    Return the competency Tag identified by ``tag_id``.

    UNSTABLE: the criteria-authoring family is incomplete, so its validation and group update
    and archive behavior may change this function's shape without a deprecation cycle.

    Raises Tag.DoesNotExist if no such Tag exists, or if it isn't on a CompetencyTaxonomy.
    Shared by the view and :func:`associate_competency_criterion` so both agree on what counts
    as valid.
    """
    tag = Tag.objects.get(pk=tag_id)
    # Explicit None check narrows the type for mypy.
    if tag.taxonomy is None or not is_competency_taxonomy(tag.taxonomy):
        raise Tag.DoesNotExist("Tag is not on a CompetencyTaxonomy.")
    return tag


def _create_leaf_group(
    tag: Tag,
    course_run: CourseRun,
    logic_operator: str | None = None,
) -> CompetencyCriteriaGroup:
    """
    Return a fresh leaf CompetencyCriteriaGroup under ``tag``'s root/course-level groups.

    Gets or creates the root and course-level groups, then always creates a new leaf: a
    tag/course pair can hold more than one leaf, one per criterion. The root and course-level
    group names are truncated to fit the name column; they are never shown in the UI.

    The root and course-level lookups need no lock: the database holds one root per tag and one
    course-level group per tag and course, and ``get_or_create()`` recovers from a concurrent insert.
    """
    name_max_length = CompetencyCriteriaGroup._meta.get_field("name").max_length
    # Both get_or_create() lookups match archived rows deliberately, so an archived container is
    # never replaced; rejecting or reactivating it is the archived-group checks' decision.
    root, _ = CompetencyCriteriaGroup.objects.get_or_create(
        tag=tag,
        parent=None,
        defaults={"name": f"{tag.value} (root)"[:name_max_length]},
    )
    course_level_group, _ = CompetencyCriteriaGroup.objects.get_or_create(
        tag=tag,
        course=course_run,
        parent=root,
        defaults={"name": f"{tag.value} — {course_run.title}"[:name_max_length]},
    )
    return CompetencyCriteriaGroup.objects.create(
        tag=tag,
        course=None,
        parent=course_level_group,
        logic_operator=logic_operator or LogicOperator.OR,
    )


def resolve_supplied_leaf_group(group_id: int, tag: Tag, course_run: CourseRun) -> CompetencyCriteriaGroup:
    """
    Return the CompetencyCriteriaGroup identified by ``group_id``, validated as a usable leaf.

    UNSTABLE: the criteria-authoring family is incomplete, so its validation and group update
    and archive behavior may change this function's shape without a deprecation cycle.

    Raises CompetencyCriteriaGroup.DoesNotExist if it doesn't exist, or ValidationError (keyed
    "group_id") if it isn't a leaf, doesn't belong to ``tag``, or its course doesn't match
    ``course_run``.
    """
    group = CompetencyCriteriaGroup.objects.get(pk=group_id)
    if group.parent_id is None or group.course_id is not None:
        raise ValidationError({"group_id": _("group_id must reference a leaf CompetencyCriteriaGroup.")})
    if group.tag_id != tag.id:
        raise ValidationError({"group_id": _("group_id must belong to the given competency tag.")})
    if group.parent.course_id != course_run.id:
        raise ValidationError({"group_id": _("group_id must belong to the given course.")})
    return group


def create_competency_criterion(
    group: CompetencyCriteriaGroup,
    object_id: str,
    rule_profile_id: int | None = None,
    rule_type_override: str | None = None,
    rule_payload_override: dict | None = None,
) -> CompetencyCriterion:
    """
    Create and return a CompetencyCriterion under ``group``, tagging ``object_id`` along the way.

    UNSTABLE: the criteria-authoring family is incomplete, so its validation and group update
    and archive behavior may change this function's shape without a deprecation cycle.

    ``tag_object()`` replaces an object's full tag list for a taxonomy rather than appending, so
    this reads the object's existing tags first and unions in the new one, rather than silently
    dropping a sibling competency's tag under the same taxonomy. Raises ValidationError (keyed
    "object_id") when the taxonomy refuses the tag, e.g. it allows only one tag per object.

    When no rule fields are supplied, resolves to the live profile scoped to the tag's taxonomy,
    else the live system default, rather than persisting null: ADR-0002 Decision 4 always
    resolves to a concrete profile, and the model's own xor-override constraint forbids leaving
    all three fields null. Course- and organization-scoped profiles are not resolved here, since
    a criterion is authored at taxonomy scope.
    """
    tag = group.tag
    # tag.taxonomy_id is nullable at the model level; already guaranteed set by the caller.
    assert tag.taxonomy_id is not None
    existing_values = [existing_tag.value for existing_tag in get_object_tags(object_id, taxonomy_id=tag.taxonomy_id)]
    if tag.value not in existing_values:
        existing_values.append(tag.value)
    try:
        tag_object(object_id, tag.taxonomy, existing_values)
    except ValueError as exc:
        raise ValidationError({"object_id": str(exc)}) from exc
    object_tag = ObjectTag.objects.get(object_id=object_id, taxonomy_id=tag.taxonomy_id, tag_id=tag.id)

    if rule_profile_id is None and rule_type_override is None and rule_payload_override is None:
        live = CompetencyRuleProfile.objects.filter(archived=False, organization__isnull=True, course__isnull=True)
        # CompetencyTaxonomy shares its pk with its parent Taxonomy row.
        profile = live.filter(competency_taxonomy_id=tag.taxonomy_id).first() or live.get(
            competency_taxonomy__isnull=True
        )
        rule_profile_id = profile.id

    # Parent-competency dominance/containment validation belongs here, before creation.

    return CompetencyCriterion.objects.create(
        group=group,
        object_tag=object_tag,
        rule_profile_id=rule_profile_id,
        rule_type_override=rule_type_override,
        rule_payload_override=rule_payload_override,
    )


def _reject_duplicate_criterion(tag: Tag, object_id: str, group_id: int | None) -> None:
    """
    Raise ValidationError if ``object_id`` is already associated with ``tag`` (in ``group_id``, when supplied).

    Must run inside a transaction holding the tag row lock.
    """
    assert tag.taxonomy_id is not None  # narrowing for mypy; callers resolve competency tags only
    existing_object_tag = ObjectTag.objects.filter(
        object_id=object_id, taxonomy_id=tag.taxonomy_id, tag_id=tag.id,
    ).first()
    if existing_object_tag is None:
        return
    duplicate_criteria = CompetencyCriterion.objects.filter(object_tag=existing_object_tag)
    if group_id is None:
        # Can't know which group slot is intended, so any existing criterion is a duplicate.
        if duplicate_criteria.exists():
            raise ValidationError(
                {"object_id": _("A CompetencyCriterion already associates this tag with this object_id.")}
            )
    elif duplicate_criteria.filter(group_id=group_id).exists():
        # A different explicit group is a deliberate second association (ADR-0002), not a duplicate.
        raise ValidationError(
            {"group_id": _("A CompetencyCriterion already associates this tag with this object_id in this group.")}
        )


def _validate_rule_fields(
    rule_profile_id: int | None,
    rule_type_override: str | None,
    rule_payload_override: dict | None,
) -> None:
    """
    Raise ValidationError, keyed by the offending field, unless the rule fields form a valid combination.

    Valid: a live ``rule_profile_id`` alone, both overrides without a profile, or none of the three.
    """
    if rule_profile_id is not None and (rule_type_override is not None or rule_payload_override is not None):
        raise ValidationError({"rule_profile_id": _(
            "rule_profile_id cannot be combined with rule_type_override or rule_payload_override."
        )})
    if (rule_type_override is None) != (rule_payload_override is None):
        supplied_field = "rule_type_override" if rule_type_override is not None else "rule_payload_override"
        raise ValidationError({supplied_field: _(
            "rule_type_override and rule_payload_override must be supplied together."
        )})
    if rule_profile_id is None:
        return
    archived = CompetencyRuleProfile.objects.filter(pk=rule_profile_id).values_list("archived", flat=True).first()
    if archived is None:
        raise ValidationError({"rule_profile_id": _("No CompetencyRuleProfile matches rule_profile_id.")})
    if archived:
        # Archived profiles stay resolvable for existing criteria but are hidden from new associations.
        raise ValidationError({"rule_profile_id": _("rule_profile_id references an archived CompetencyRuleProfile.")})


def associate_competency_criterion(
    tag_id: int,
    object_id: str,
    *,
    group_id: int | None = None,
    logic_operator: str | None = None,
    rule_profile_id: int | None = None,
    rule_type_override: str | None = None,
    rule_payload_override: dict | None = None,
) -> CompetencyCriterion:
    """
    Associate ``object_id`` with the competency ``tag_id`` names, creating a criterion for it.

    UNSTABLE: the criteria-authoring family is incomplete, so its validation and group update
    and archive behavior may change this function's shape without a deprecation cycle.

    The public entry point for the create-criterion endpoint; the caller is expected to have
    already checked ``oel_tagging.can_tag_object``. Rejects re-targeting the same group a
    (tag_id, object_id) pair already uses, and rejects a duplicate via the derive-or-create
    path; a *different* explicit group is a deliberate second association per ADR-0002, not a
    duplicate. Branches on ``group_id`` to resolve or derive/create a leaf, then creates the
    criterion, all inside one transaction so a downstream failure rolls back any group just
    created.

    Raises ValidationError (never DRF's) on rejected input, including an invalid combination of
    rule fields or a missing or archived ``rule_profile_id``; Tag.DoesNotExist if ``tag_id``
    doesn't resolve to a competency tag; CompetencyCriteriaGroup.DoesNotExist if ``group_id``
    doesn't resolve.
    """
    tag = resolve_competency_tag(tag_id)
    # tag.taxonomy is already confirmed set; re-asserted since that doesn't cross function boundaries for mypy.
    assert tag.taxonomy_id is not None

    try:
        usage_key = UsageKey.from_string(object_id)
    except InvalidKeyError as exc:
        raise ValidationError({"object_id": _("object_id is not a valid usage key.")}) from exc

    try:
        course_run = get_course_run(usage_key.course_key)
    except CourseRun.DoesNotExist as exc:
        raise ValidationError({"object_id": _("No course run matches object_id's course.")}) from exc

    if group_id is not None and logic_operator is not None:
        raise ValidationError({"logic_operator": _("group_id and logic_operator cannot both be supplied.")})
    _validate_rule_fields(rule_profile_id, rule_type_override, rule_payload_override)

    with transaction.atomic():
        # The database enforces one root per tag; this lock only serializes _reject_duplicate_criterion(). That check
        # is check-then-act on both paths: without group_id a request always creates a fresh leaf, and with group_id
        # CompetencyCriterion has no unique constraint on (object_tag, group), so no index catches a concurrent copy.
        Tag.objects.select_for_update().get(pk=tag.pk)
        _reject_duplicate_criterion(tag, object_id, group_id)
        if group_id is not None:
            group = resolve_supplied_leaf_group(group_id, tag, course_run)
        else:
            group = _create_leaf_group(tag, course_run, logic_operator)
        return create_competency_criterion(
            group=group,
            object_id=object_id,
            rule_profile_id=rule_profile_id,
            rule_type_override=rule_type_override,
            rule_payload_override=rule_payload_override,
        )


def _effective_rule(criterion: CompetencyCriterion) -> tuple[str, Any]:
    """Return (rule_type, payload) for whichever of criterion's profile or override is set."""
    if criterion.rule_profile_id is not None:
        # The oel_cbe_criterion_profile_xor_override_check constraint guarantees rule_profile is
        # set whenever rule_profile_id is; this assertion only narrows that fact for mypy.
        assert criterion.rule_profile is not None
        return criterion.rule_profile.rule_type, criterion.rule_profile.rule_payload
    # Same constraint, the other way around: rule_type_override is set whenever rule_profile_id
    # is not.
    assert criterion.rule_type_override is not None
    return criterion.rule_type_override, criterion.rule_payload_override


def _raise_leaf_status(user_id: int, criterion_id: int, status: MasteryStatus, now: datetime) -> int:
    """
    Create or raise a learner's leaf status row for one criterion; never lowers a stored status.

    Returns the count of rows created or raised (0 or 1), matching the semantics of
    ``QuerySet.update()``'s own return value.
    """
    row, created = StudentCompetencyCriterionStatus.objects.get_or_create(
        user_id=user_id, criterion_id=criterion_id,
        defaults={"status_id": status, "created": now, "modified": now},
    )
    if created:
        return 1
    return StudentCompetencyCriterionStatus.objects.filter(
        pk=row.pk, status_id__lt=status,
    ).update(status_id=status, modified=now)


def record_graded_object_statuses(*, user_id: int, scores: Sequence[GradedObjectScore]) -> int:
    """
    Record a learner's leaf-level competency status for each graded object in ``scores``.

    UNSTABLE: the rollup and learner-status read entry points still to come may change what this
    function returns without a deprecation cycle.

    Call this only from inside the same transaction that also writes the grade: this function opens
    no transaction of its own and lets any storage error propagate rather than swallowing it, so the
    grade and its leaf statuses always commit or roll back together. Pass each ``object_id`` at most
    once, using the exact string already stored in ``ObjectTag.object_id``; the match performed
    against that value is case-sensitive. Leave out of ``scores`` any object worth zero possible
    points and any object the learner has not attempted. Only criteria whose tag belongs to a
    competency taxonomy are evaluated, and archived criteria are skipped. An evaluated criterion's
    status is only ever raised, never lowered. The return value is the count of leaf rows created or
    raised, where ``0`` means nothing changed. This function performs no authorization check of its
    own; as with ``openedx_tagging.api``, the caller is responsible for enforcing permissions.

    :raises TransactionManagementError: if called outside an atomic block.
    """
    # In autocommit mode get_or_create() would commit a leaf row on its own, apart from the grade.
    if not connection.in_atomic_block:
        raise TransactionManagementError("record_graded_object_statuses() must run inside the grade's transaction.")
    if not scores:
        return 0

    fraction_by_object_id: dict[str, Decimal] = {}
    for score in scores:
        if score.object_id in fraction_by_object_id:
            raise ValueError(f"duplicate object_id in scores: {score.object_id!r}")
        fraction_by_object_id[score.object_id] = score.fraction

    criteria = (
        CompetencyCriterion.objects.filter(
            object_tag__object_id__in=list(fraction_by_object_id),
            object_tag__taxonomy__competencytaxonomy__isnull=False,
            archived=False,
        )
        .select_related("object_tag", "rule_profile")
        .order_by("pk")
    )

    now = datetime.now(tz=timezone.utc)
    changed = 0
    for criterion in criteria:
        fraction = fraction_by_object_id[criterion.object_tag.object_id]
        rule_type, payload = _effective_rule(criterion)
        try:
            demonstrated = evaluate_rule(rule_type, payload, fraction)
        except ValidationError as exc:
            log.warning(
                "Skipping CompetencyCriterion %s for user %s on object %s: its rule cannot be applied: %s",
                criterion.pk, user_id, criterion.object_tag.object_id, exc.messages,
            )
            continue
        status = MasteryStatus.DEMONSTRATED if demonstrated else MasteryStatus.ATTEMPTED_NOT_DEMONSTRATED
        changed += _raise_leaf_status(user_id, criterion.pk, status, now)

    return changed
