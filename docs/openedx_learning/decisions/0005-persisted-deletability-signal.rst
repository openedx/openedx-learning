.. _openedx-learning-adr-0005:

5. How should delete-eligibility be signaled for competency guardrail records?
================================================================================

Status
------

Proposed

Context
-------

:ref:`openedx-learning-adr-0002` Decision 7 already decides *which* records are delete-protected:
once any related learner status exists in ``StudentCompetencyStatus``,
``StudentCompetencyCriteriaGroupStatus``, or ``StudentCompetencyCriteriaStatus``, hard delete is
blocked for ``Taxonomy``/``CompetencyTaxonomy``, ``Tag``, ``ObjectTag``, ``CompetencyCriteriaGroup``,
and ``CompetencyCriteria``. ``CompetencyRuleProfile`` has no delete path at all, with or without
learner status; archive is its only removal path.

What that decision doesn't cover is how a caller finds out a record is currently protected *before*
attempting to delete it, so Studio can disable or warn on the delete action instead of only
discovering the block from a failed request.

Decision
--------

Persist the signal instead of computing it at read time
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

Add a boolean ``deletable`` field, defaulting to ``True``, to each of the five delete-protected
models: ``Taxonomy``/``CompetencyTaxonomy``, ``Tag``, ``ObjectTag``, ``CompetencyCriteriaGroup``,
and ``CompetencyCriteria``. GET endpoints for these models expose the column directly; no
annotation or subquery runs on the read path at all.

``CompetencyRuleProfile`` does not get this field: it has no DELETE endpoint to gate, per ADR-0002
Decision 7.

No backfill computation is needed. All five models' rows only ever become non-deletable by way of
a ``StudentCompetencyCriteriaStatus``/``StudentCompetencyCriteriaGroupStatus``/
``StudentCompetencyStatus`` row referencing them, and those three tables are created by this same
body of work; no such row can exist yet at migration time, for a pre-existing ``Tag``/``Taxonomy``
row or otherwise. The field's plain ``True`` default is therefore already correct for every
existing row; the migration adding the column needs no accompanying data migration.

The flip is monotonic and can be set synchronously
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

``deletable`` only ever transitions ``True`` to ``False``, never back. Learner status rows are
append-only and never deleted (:ref:`openedx-learning-adr-0003` Decision 5), so once a record is
referenced by a learner status row, it can never become deletable again. This is what makes a
persisted column safe here without a general cache-invalidation scheme: there is no code path that
would ever need to flip it back to ``True``.

Because the transition is one-directional, it can be set synchronously, in the same transaction as
the write that creates the referencing status row: whichever ``Taxonomy``/``CompetencyTaxonomy``,
``Tag``, ``ObjectTag``, ``CompetencyCriteriaGroup``, or ``CompetencyCriteria`` row that status row
references gets ``deletable`` set to ``False`` as part of the same write. There is no
eventual-consistency gap where a GET could show ``deletable=True`` after the guardrail already
applies.

Enforcement stays on the write path
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

The persisted field is a UX convenience, not the enforcement mechanism. DELETE endpoints re-check
``deletable`` server-side before deleting; a client is never trusted to have an up-to-date copy.
If a delete is blocked, the handler may run one additional query at that point to identify the
specific blocking learner-status row(s) for the error message (``409 Conflict``, naming what
blocks it). Deletes are rare, so this extra query is acceptable exactly where a per-request
existence check on every read would not be.

Rejected Alternatives
----------------------

Compute ``deletable`` at read time via ``Exists()``/``OuterRef()``
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

Annotate the queryset for each GET endpoint with a correlated ``Exists()`` subquery per row,
computing the signal fresh on every request instead of persisting it.

**Pros:** always correct by construction, no write-path bookkeeping needed, no migration
considerations.

**Cons:** adds a JOIN to every list/detail read of these models to answer a question that's only
relevant on the rare delete attempt. Not chosen, since reads vastly outnumber deletes for this
data.

Cache the computed value with a generous TTL
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

Keep the ``Exists()`` computation, but cache its result instead of persisting it as a column.

**Pros:** no schema change, no write-path coupling to learner-status writes.

**Cons:** still requires the same per-row ``Exists()`` check to populate the cache on a miss, and
introduces a staleness window and invalidation question a persisted, monotonic field avoids by
construction: since the value only ever moves ``True`` to ``False`` and never back, there is no
"is my cache stale" question to answer at all. Not chosen, since it solves a narrower version of
the same problem the persisted field solves outright.

Changelog
---------

2026-07-15:

* Initial draft.
