.. _openedx-tagging-adr-0011:

11. Cross-instance identity for taxonomies copied with course content
========================================================================

Status
------

Proposed

Context
-------

Competency Based Education (CBE) introduces ``CompetencyCriteria``: see
:ref:`openedx-learning-adr-0002` for the full model, but in brief, a competency criterion asserts
that a piece of course content demonstrates a specific competency, which it identifies by pointing
at a Tag in a Taxonomy. Criteria are grouped into a ``CompetencyCriteriaGroup`` tree, also defined
in ADR 0002, that combines them with AND/OR logic and may be scoped to a specific course run
(``CourseRun`` in ``openedx_catalog``, identified by the same ``course_key`` that identifies the
corresponding legacy modulestore course; "course" throughout this decision means that same
course-run identity, the one ADR 0002's ``course_id`` references).

When course content is copied by any of the three supported mechanisms, a new course run, course
export/import, or course/library copy, any competency criteria attached to that content should be
copied along with it. Criteria themselves are versioned via ``django-simple-history`` per
:ref:`openedx-learning-adr-0003`, but the taxonomy and tags they reference are deliberately not:
they're non-evaluative display metadata that can change independently without creating a new
version of the criteria pointing at them. Copying a criterion therefore also means resolving the
taxonomy and tags it points to on the target, since the copy has to have a corresponding tag for it
to reference.

No stable, cross-instance identity exists for a ``Tag`` today: ``Tag.external_id`` is an editable,
instance-scoped identifier designed for import-file bookkeeping (see :ref:`openedx-tagging-adr-0006`).
``Taxonomy.export_id`` is different: per `modular-learning#183
<https://github.com/openedx/modular-learning/issues/183>`_, it was always intended to answer "does
the target already have this taxonomy," which is exactly what this decision needs; it just hasn't
been documented as such, or exercised for identity-matching purposes, until now.

The three copy mechanisms differ significantly in current maturity:

- **Course export/import** (legacy XBlock/modulestore course): already works, via a ``tags.csv``
  sibling file resolved by ``export_id`` at import time.
- **New course run**: always same-instance/same-database, so no taxonomy/tag resolution is ever
  needed; what's missing is recreating the ``ObjectTag``, ``CompetencyCriteria``, and
  ``CompetencyCriteriaGroup`` rows for the new run (see Copy semantics, below). ``copy_tags()``
  exists in ``openedx_tagging.api`` but is not wired into the course-rerun flow yet.
- **Library copy**: always same-instance today; no cross-instance transport exists in
  ``content_libraries``, and none is planned.

Excluded from this decision:

- Cross-instance library copy. Not a near-term platform capability; out of scope.
- The newer ``openedx_content`` Component/Container content model. It has no tag-copy wiring at
  all today; this decision targets the legacy course model that currently carries course content,
  and a future extension should reuse the identity contract defined here rather than re-deriving it.
- Versioning ``Taxonomy``/``Tag`` themselves (see Deferred, below).
- Org-level namespacing for taxonomies. Unlike courses/libraries, taxonomies aren't scoped to an
  org today; if multiple orgs ever need to independently evolve what they consider "the same"
  taxonomy, some namespacing convention may be needed. Not addressed here since no such conflict
  exists yet.

Decision
--------

Stable identity
~~~~~~~~~~~~~~~~

Use the existing ``Taxonomy.export_id`` field as the cross-instance identity, rather than adding a
new field. Two institutions that each set up the same third-party taxonomy (for example,
Lightcast Open Skills) can establish that they're the same taxonomy simply by using the same
``export_id`` (for example ``io.lightcast.open-skills``).

``export_id`` remains mutable and supports the manual-merge case below by editing one instance's
``export_id`` to match the other's.

The existing ``Tag.external_id`` (already used by the tag import/export plan-building logic, see
:ref:`openedx-tagging-adr-0006`) is sufficient for within-taxonomy matching.

Copy semantics
~~~~~~~~~~~~~~

Competency criteria are recreated on the target, not moved. For any of the three mechanisms, the
``ObjectTag``, ``CompetencyCriteria``, and ``CompetencyCriteriaGroup`` rows attached to the copied
content are duplicated and re-keyed to the new object and course ids, using an old-id-to-new-id
mapping built during the copy. A recreated ``CompetencyCriteriaGroup`` shares a parent group with
the original, so the two are combined by ``OR`` by default.

The ``Taxonomy``/``Tag`` rows a recreated ``ObjectTag`` points to are handled differently: they are
never duplicated, only referenced, and it's this taxonomy/tag relationship the rest of this
decision means by **by reference**. For a same-instance mechanism (new course run, library copy),
source and target already share the identical taxonomy row, so no resolution is needed at all.

Resolution on course import/export
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

Course import/export is the only mechanism where a matching taxonomy might not already exist on the
target.

On course import, whether the source and target are the same deployment or two different organizations'
instances, the behavior is uniform:

- If no taxonomy with a matching ``export_id`` exists on the target, auto-create one, seeded from the
  tags that traveled with the export.
- If a taxonomy with a matching ``export_id`` already exists, reconcile it (see below) rather than
  creating a duplicate.

Reconciliation on repeat import
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

When a matching taxonomy already exists on the target, build a plan comparing the incoming tag
snapshot against the target's current tags, reusing the existing tag import/export plan-building
logic (``TagImportPlan``, keyed on ``Tag.external_id``) that already classifies differences into
create/rename/reparent/delete actions.

- If every action in the plan is a tag creation, apply it: the target gains the new tags, nothing
  existing is touched.
- If the plan contains any rename, reparent, or delete action, refuse the import of criteria bound
  to that taxonomy because the actor triggering the course import may have no standing to mutate
  a taxonomy shared with other, unrelated content on the target instance.

Failure surfacing
~~~~~~~~~~~~~~~~~~

A refusal is modeled as an ordinary import task failure.

Alternatives Considered
------------------------

Add a new immutable ``uuid`` field
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

Add a new, randomly-generated ``uuid`` field on ``Taxonomy``, instead of reusing ``export_id``.

**Pros:** guaranteed collision-free by construction; no reliance on a human choosing a consistent
value.

**Cons:** a randomly-generated identifier can never let two independently-created taxonomies on
two different instances establish that they're the same one, exactly the "manual merge" case
deferred below, since two independent imports always produce two different random values with no
way to reconcile them. ``export_id`` already exists for this purpose (`modular-learning#183
<https://github.com/openedx/modular-learning/issues/183>`_), is already required, unique, and
format-validated, and its editability is what makes the deferred manual-merge case possible at
all. Not chosen, since it would have duplicated ``export_id``'s role while being strictly less
capable for the independently-created-taxonomies case.

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
use case, since the additions-only reconciliation policy already satisfies it without history. See
`openedx-core#455 <https://github.com/openedx/openedx-core/issues/455>`_ for the tentative plan for
taxonomy versioning.

Manual merge of independently-created taxonomies
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

Two institutions may independently author what they each consider the same taxonomy on their own
instances, without ever having copied content between each other. If they haven't both deliberately
set the same ``export_id``, importing between them today would create a second, unrelated taxonomy
on the receiving side, not recognize them as the same one. Automatic matching cannot safely resolve
this: falling back to matching by name or content similarity would reintroduce the false-positive
risk a deliberate, unique identifier was introduced to avoid, two instances with genuinely different
taxonomies that happen to look similar would be silently merged. The eventual resolution is a
deliberate, human-initiated action: an administrator manually edits one instance's taxonomy to
adopt the other's ``export_id``, retroactively establishing shared identity going forward. Not
designed here, since it is a distinct, rare operation, orthogonal to the copy-time behavior this
decision covers. Today this requires a direct API call: Studio's Taxonomy Editing UI has no field
to set or edit ``export_id``.

Changelog
---------

2026-07-09:

* Initial draft.
