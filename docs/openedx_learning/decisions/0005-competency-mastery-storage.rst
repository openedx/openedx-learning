.. _openedx-learning-adr-0005:

5. How should learner competency status be stored at scale?
===========================================================

Status
------
Proposed.

Context
-------
Per :ref:`openedx-learning-adr-0002`, competency achievement criteria form a boolean tree. An
internal ``CompetencyCriteriaGroup`` node combines child nodes with an ``AND``/``OR``
``logic_operator``, can be scoped to a course run, and can nest under a parent group. A
``CompetencyCriterion`` leaf is the tree's terminal node: it points at one tag/object association
and a rule.

The student mastery statuses tied to these tree nodes are stored in:
- `StudentCompetencyCriteriaStatus` (leaf nodes)
- `StudentCompetencyCriteriaGroupStatus` (middle nodes)
- `StudentCompetencyStatus` (top-level)

For each of these, we also need to persist history, because we need an audit trail to understand
why a learner did or didn't achieve mastery of a particular competency or any of the associated "measurement instruments"
(gradeable subsections).

Storing every leaf multiplies out at scale. A course can carry on the order of 200 leaf criteria,
so the leaf level is where the row count concentrates: the leaf table (learners x attempted
leaves) potentially reaches the low billions for an Open edX instance with millions of learners. The dominant
multiplier is this per-leaf breadth (roughly 200x per course), not time. Mastery is monotonic (see
"Advance-only banking" below): a node can only advance through the small status lattice, at most a handful of
forward steps ever.

That scale is not, on its own, what makes a relational database struggle. A point lookup against a
billion-row table backed by the right composite index is a logarithmic-time index seek regardless
of the table's size; the dashboard reads this feature performs are exactly such point lookups. What
billions of rows makes painful is schema migrations, backups, and any non-indexed or aggregate
query.

Decision
--------

**Store statuses / mastery at every level, each split into ACTIVE and HISTORY.** The leaf, group, and
competency levels each keep one ACTIVE row per learner and node, updated in place, so reading a
learner's current status is a direct indexed lookup rather than a scan for the most recent of many
rows. Each level also has a parallel append-only HISTORY table that records one row per genuine
status advance, for audit and point-in-time reconstruction. Because status only advances, the status
at any past time is the latest recorded advance at or before that time, so point-in-time is fully
reconstructable from HISTORY. Because status is monotonic, the number of advances per node is bounded
by the status lattice (a small constant), so HISTORY grows with learners and nodes, not with time,
and stays about the same order of size as ACTIVE. Keeping ACTIVE and HISTORY separate still pays:
ACTIVE is a single in-place current row optimized for the dashboard point lookup and is the row
per-learner concurrency is anchored on (:ref:`openedx-learning-adr-0004`), while HISTORY is
append-only.

**64-bit primary keys from the start.** The leaf ACTIVE and HISTORY tables use a 64-bit
``BigAutoField`` primary key, chosen up front, mirroring edx-platform's
``UnsignedBigIntAutoField`` on ``PersistentSubsectionGrade`` ("primary key will need to be
large for this table"). Changing a primary-key type on a billion-row table later is
prohibitively expensive.

**No database-level foreign keys to `user_id` on ACTIVE or HISTORY table.**
Foreign keys to ``user_id`` must have ``db_constraint=False`` set, mirroring edx-platform's own
``StudentModule``. This follows the app-boundary decision in :ref:`openedx-learning-adr-0001`, which keeps
learner-status models decoupled from the concrete user model. Furthermore,
a real constraint has an ongoing cost at this table's write volume:
a hot user row would see extra lock contention under concurrent writes. This
follows the app-boundary decision in :ref:`openedx-learning-adr-0001`, which keeps
learner-status models decoupled from the concrete user model.

This is independent of the delete-protection boundary in :ref:`openedx-learning-adr-0002`
(Decision 7): that boundary keys off ``competency_criteria_id`` and its ancestor tables, not
``user_id``, so dropping the database-level constraint here does not weaken it.

**Advance-only banking, monotonic.** Once a node reaches ``Demonstrated`` its ACTIVE row is retained
("banked"): the recorder never automatically regresses it, not on a later downward grade correction
and not on a criteria change. This applies at every level, including the leaf. A genuine downward
grade correction does not advance the status, so it writes no HISTORY row and leaves the banked
ACTIVE status unchanged; because HISTORY records only advances, it never carries suppressed
regressions. Reversing a banked status is a separate administrative action, out of scope here.
This monotonicity is what makes out-of-order and duplicate delivery safe, since a late or replayed
event can never lower a status, and :ref:`openedx-learning-adr-0004` relies on it.

**Retroactive criteria changes are monotonic for the learner.** A retroactive edit can newly grant
or preserve mastery, but it never silently revokes it, and it never rewrites a learner's recorded
leaf mastery downward.

Rejected Alternatives
---------------------

1. Compute leaves transiently, never store them.

    - Pros:
        - Eliminates the largest tables (leaf ACTIVE and HISTORY), since leaf demonstration would be
          computed on demand from the leaf's rule plus group-node status.
    - Cons:
        - Does not account for competency tree edits: a later restructuring of the criteria tree would
          make previously-computed leaf statuses incorrect, because there is no stored, frozen leaf
          mastery to rely on.

2. Keep everything append-only (no ACTIVE table); current status is the latest row.

    - Pros:
        - One model per level instead of paired ACTIVE and HISTORY tables.
    - Cons:
        - A dashboard read must resolve the latest advance out of a node's history rather than reading
          one in-place row, which is more expensive and more complex, even with HISTORY bounded by
          monotonicity.
        - There is no single current row for the per-learner concurrency in
          :ref:`openedx-learning-adr-0004` to anchor on.

3. Put the leaf HISTORY table behind its own Django database alias and router, or make a separate
   physical database mandatory, or partition/shard the leaf tables, up front.

    - Pros:
        - Physically isolates or splits the largest tables from the start. In the router variant the
          alias would default to the main database, letting a deployment opt into a separate physical
          database later without a schema change.
        - Mirrors edx-platform's courseware-history router
          (``StudentModuleHistoryExtended``), which is likewise a history table.
    - Cons:
        - A second alias gives up atomicity. Django runs a write to another alias on its own
          connection, so a learner's ACTIVE and HISTORY rows can no longer commit in one transaction,
          and the HISTORY append needs its own retrying, self-reconciling write path
          (:ref:`openedx-learning-adr-0004`) to avoid losing audit rows. That cost is paid by every
          deployment, including the overwhelming majority that never split the database.
        - The prior art does not actually support the pattern: edx-platform's courseware-history
          router was retrofitted to work around a 32-bit primary key running out, not adopted as a
          scaling design.
        - Mandating a separate physical database or a partitioning scheme imposes real operational
          cost on every deployment, with nothing measured to justify it.
        - Premature, and reversible: an alias, a separate database, partitioning, and sharding all
          remain available to revisit if a specific need is proven.

4. Store child evaluations on the parent group row instead of a leaf ACTIVE table (an enriched
   attained-set).

    - Pros:
        - Reduces the hot-store footprint by avoiding a separate leaf ACTIVE table.
    - Cons:
        - The reduction does not address the largest table (leaf HISTORY), so the main scaling concern
          remains.
        - Re-incurs the denormalized-array correctness burden that storing first-class leaf rows
          removed.
        - Couples a leaf's frozen mastery to the current shape of the criteria tree, so restructuring
          the tree can corrupt already-recorded mastery. Structural robustness is valued over the
          hot-store saving.
        - The single-row group read it optimizes is already served acceptably by an indexed range read
          of a learner's leaf rows.

5. Serve heavy reads of the leaf tables from a read replica
   (``edx_django_utils``'s ``read_replica_or_default()``).

    - Pros:
        - Keeps dashboard and reporting reads of the two largest tables off the primary, where row
          count and read volume concentrate.
    - Cons:
        - Premature: no measurement shows the primary struggling with these reads. The dashboard reads
          are point lookups on a composite index, not the large, expensive, widely-called reads that
          drive ``StudentModule`` load in edx-platform, so CBE read load should be much lower.
        - Replica lag is a correctness hazard next to the recorder, which must read from the primary
          (:ref:`openedx-learning-adr-0004`); introducing replica reads means maintaining that
          distinction in every new read path.
        - Adding it later is cheap, since it is a per-query choice rather than a schema decision.
