.. _openedx-tagging-adr-0011:

11. Cross-instance identity for taxonomies copied with course content
========================================================================

Status
------

Proposed

Context
-------

Competency Based Education (CBE) will bring about the use case where, when course content is
copied by any of the three supported mechanisms, a new course run, course export/import, or
course/library copy, any competency criteria attached to that content should be copied along with
it. Competency criteria (``CompetencyCriteria``, ``CompetencyCriteriaGroup``) are versioned via
``django-simple-history`` per :ref:`openedx-learning-adr-0003`, but the taxonomies and tags they
reference are deliberately non-evaluative, unversioned display metadata. Copying a criterion
therefore also means resolving the taxonomy and tags it points to on the target.

No stable, cross-instance identity exists for a ``Taxonomy`` or ``Tag`` today. ``Taxonomy.export_id``
and ``Tag.external_id`` are both editable, instance-scoped identifiers designed for import-file
bookkeeping (see :ref:`openedx-tagging-adr-0006`), not for answering "does the target already have
this taxonomy."

The three copy mechanisms differ significantly in current maturity:

- **Course export/import** (legacy XBlock/modulestore course): already works, via a ``tags.csv``
  sibling file resolved by ``export_id`` at import time.
- **New course run**: always same-instance/same-database. ``copy_tags()`` exists in
  ``openedx_tagging.api`` but is not wired into the course-rerun flow.
- **Library copy**: always same-instance today; no cross-instance transport exists in
  ``content_libraries``, and none is planned.

Excluded from this decision:

- Cross-instance library copy. Not a near-term platform capability; out of scope.
- The newer ``openedx_content`` Component/Container content model. It has no tag-copy wiring at
  all today; this decision targets the legacy course model that currently carries course content,
  and a future extension should reuse the identity contract defined here rather than re-deriving it.
- Versioning ``Taxonomy``/``Tag`` themselves (see Deferred, below).

Decision
--------

Stable identity
~~~~~~~~~~~~~~~~

Add an immutable ``uuid`` field to ``Taxonomy``, generated at creation and preserved through
export/import. ``export_id`` cannot serve this purpose on its own: it is free text, chosen and
editable by whoever administers a taxonomy, so nothing guarantees that the same ``export_id`` on
two different instances refers to the same taxonomy, or that two different taxonomies on two
instances never happen to share one. A ``uuid`` is generated once, never touched by a person, and
so cannot collide or drift the way a human-chosen identifier can. ``export_id`` keeps its existing
role as the human-meaningful identifier; ``uuid`` adds the machine identity it was never designed
to provide. This follows the existing convention in this codebase of using ``uuid`` for a stable
external reference (see ``PublishableEntity.uuid``, :ref:`openedx-content-adr-0003`), applied here
to a model that currently lacks it.

``Tag`` does not need a new identifier: ``Tag.external_id`` (already used by the tag import/export
plan-building logic, see :ref:`openedx-tagging-adr-0006`) is sufficient for within-taxonomy
matching. Free-text taxonomies have no ``Tag`` rows and travel as literal strings unconditionally;
no reconciliation applies to them.

Copy semantics
~~~~~~~~~~~~~~

Competency criteria are copied **by reference**: the target's criteria are bound to a taxonomy
sharing the source's ``uuid``, not to an independent duplicate. This is a larger commitment than a
by-value copy, but a by-value copy would leave the target's competency evaluation permanently
disconnected from the taxonomy it depends on, undermining the goal of this use case.

Resolution on import
~~~~~~~~~~~~~~~~~~~~~

On import, whether the source and target are the same deployment or two different organizations'
instances, the behavior is uniform:

- If no taxonomy with a matching ``uuid`` exists on the target, auto-create one, seeded from the
  tags that traveled with the export.
- If a taxonomy with a matching ``uuid`` already exists, reconcile it (see below) rather than
  creating a duplicate.

A single uniform rule was chosen over branching by deployment relationship because the
reconciliation policy below already guards against silent corruption in both cases; adding a
second behavior for the cross-organization case would add complexity without removing risk.

Reconciliation on repeat import
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

When a matching taxonomy already exists on the target, build a plan comparing the incoming tag
snapshot against the target's current tags, reusing the existing tag import/export plan-building
logic (``TagImportPlan``, keyed on ``Tag.external_id``) that already classifies differences into
create/rename/reparent/delete actions.

- If every action in the plan is a tag creation, apply it: the target gains the new tags, nothing
  existing is touched.
- If the plan contains any rename, reparent, or delete action, refuse the import of criteria bound
  to that taxonomy.

The actor triggering a course copy has no standing to mutate a taxonomy shared with other,
unrelated content on the target instance. In a manual tag re-import (the existing use of this
plan-building logic), the file represents the deliberate intent of whoever owns that taxonomy. A
copied course's snapshot only reflects what the source looked like at export time: a tag missing
from it doesn't mean the source deleted it, it may be something the target added independently.
Auto-applying deletes or renames on that basis risks silently corrupting taxonomy state that
unrelated courses on the target depend on. Additions carry no such risk: they only ever add new
identities, never touch existing ones.

Failure surfacing
~~~~~~~~~~~~~~~~~~

A refusal is modeled as an ordinary import task failure, using the existing
``UserTaskStatus.fail(message)`` / ``Error`` artifact / ``import_status_handler`` mechanism in
``contentstore``. The Studio Authoring MFE's import flow already reads this same ``Message`` field
(``CourseImportContext.tsx``), so this requires no new frontend or backend surface, and no
distinction needs to be drawn between a Platform Administrator and a Course Author watching the
same import: whoever is watching sees the existing failure message.

Alternatives Considered
------------------------

Copy by value (independent duplicate)
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

Give the target its own disconnected copy of the taxonomy and tags, with no ongoing identity link
to the source.

**Pros:** cheapest option; no cross-instance identity needed at all.

**Cons:** breaks the moment the source taxonomy changes; the target's criteria would reference a
frozen, immediately stale copy. Not chosen because it does not meet the intent of this use case as
well as by-reference does.

Branch no-match behavior by deployment relationship
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

Auto-create a stub taxonomy only for same-deployment imports; require manual administrator
reconciliation for a different organization's instance.

**Pros:** more conservative for the genuinely untrusted case.

**Cons:** two behaviors to build, test, and document instead of one; the additions-only
reconciliation policy already protects against silent corruption regardless of relationship,
making the extra branch unnecessary complexity.

Deferred
--------

These are known gaps in the design above, intentionally left unaddressed for now. None of them are
precluded by this decision; each could be added later without revisiting the identity model above.

Fancier reconciliation for non-additive diffs
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

The design above refuses any import whose diff includes a rename, reparent, or delete, rather than
attempting to apply or merge it. A more capable system could instead present the conflicting
changes for guided reconciliation rather than a flat refusal. Not built now because a flat refusal
is enough to satisfy this use case safely; worth revisiting if refusals turn out to be common in
practice.

Real versioning for taxonomies and tags
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

``Taxonomy``/``Tag`` could gain version history (e.g. via ``django-simple-history``, matching
``CompetencyCriteria``), which would let drift between source and target be tracked precisely
rather than detected only as additive or not. Likely needed eventually, but not required for this
use case, since the additions-only reconciliation policy already satisfies it without history.

Manual merge of independently-created taxonomies
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

Two institutions may independently author what they each consider the same taxonomy on their own
instances, without ever having copied content between each other. Since a ``uuid`` establishes
identity only once two taxonomies have actually shared a copy operation, importing between them
today would create a second, unrelated taxonomy on the receiving side, not recognize them as the
same one. Automatic matching cannot safely resolve this: falling back to matching by name or
content similarity would reintroduce the false-positive risk ``uuid`` was introduced to avoid, two
instances with genuinely different taxonomies that happen to look similar would be silently
merged. The eventual resolution is a deliberate, human-initiated action: an administrator manually
reassigns one instance's taxonomy to adopt the other's ``uuid``, retroactively establishing shared
identity going forward. Not designed here, since it is a distinct, rare operation, orthogonal to
the copy-time behavior this decision covers.

Changelog
---------

2026-07-09:

* Initial draft.
