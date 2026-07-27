.. _openedx-learning-adr-0004:

4. How should learner competency mastery be recorded concurrently and at scale?
================================================================================

Status
------
Proposed.

Context
-------
When a learner is graded on a subsection (or any other learning instrument associated to a competency
with a competency criteria, like a course or rubric criterion), the platform must evaluate whether that grade
demonstrates any attached competencies and record the learner's mastery. Mastery is recorded at
three levels: the criterion (leaf), the criteria group, and the competency. Per
:ref:`openedx-learning-adr-0002` and :ref:`openedx-learning-adr-0005`, all three levels are
*materialized* (stored), not recomputed on read, so that dashboards and other read surfaces stay
fast. A single grade change therefore writes the changed leaf's status and then re-evaluates and
re-writes the derived rows from that leaf up to the competency root. The re-evaluation
is needed for multiple reasons, including notifications, and badge and certificate issuing. Per
:ref:`openedx-learning-adr-0005`, each level is stored as an ACTIVE row updated in place, holding
the current status for a learner and node, plus an append-only HISTORY row per genuine status
advance.

**Monotonicity: competency statuses only ever move forward.** Per
:ref:`openedx-learning-adr-0005`, every node, at every level, advances through a small status
lattice (``AttemptedNotDemonstrated`` to ``PartiallyAttempted`` to ``Demonstrated``) and is never
lowered later. This holds for leaf nodes, group nodes, and top-level competency masteries.

Two forces shape how recording should happen:

- **Same-learner correctness.** A grade change writes the changed leaf and then re-derives the
  group and competency rows above it. Leaf rows are always correct, since each leaf is a pure
  function of its own grade. The derived rows are the hazard: We want to avoid a case where two evaluations for the same learner
  that overlap can each read a stale snapshot of the sibling leaf statuses and each write a derived
  roll-up computed from an incomplete picture (a *write-skew*).

- **Throughput.** Grading is bursty and spans a very large number of learners, so the recording
  path must keep up under peak load.

Decision
--------

**1. Every write is a monotone merge, never a blind overwrite.** A node's status is written as
``status := max(stored status, newly computed status)`` (a single ``GREATEST``-style ``UPDATE``,
atomic at the row for the duration of that one statement, with no application-level lock). Because
the merge takes the higher of the two values, it is commutative, idempotent, and insensitive to
order. This is why out-of-order delivery and re-delivery are harmless without sequence tracking.

**2. When a child advances, its parent is recomputed in the same transaction, under a brief row lock on that parent.**
The merge in mechanism 1 makes a single-row write safe, but a *conjunctive*
parent (for example "demonstrated only when all children are demonstrated") is computed by reading
several child rows first, so two overlapping evaluations for one learner could each read a stale
sibling and compute a parent that is too low. To prevent that, recomputing a parent takes a
row-level lock on the parent row (a ``SELECT ... FOR UPDATE``) before reading its children: two
updates that touch the same parent for the same learner take turns, and the second reads the first's
committed children and computes from the complete picture. This correctness argument assumes
``READ COMMITTED`` isolation (the Open edX platform default on MySQL; higher isolation levels are not
supported on the platform): under it the lock's own read and the sibling reads that follow it always
return the latest committed rows, rather than a snapshot fixed at an earlier read in the same
transaction, which is what a higher level such as ``REPEATABLE READ`` would do. Locks are taken child-before-parent up
the path to the root, a consistent order, so concurrent updates cannot deadlock. This is an ordinary
single-row lock. Every read the recorder makes, here and in the mass-recompute path
(:ref:`openedx-learning-adr-0005`), runs against the primary database and never a read replica:
these reads feed the roll-up write and take the row locks above, so a replica's lag would compute a
roll-up from stale siblings. The read-replica offload in :ref:`openedx-learning-adr-0005` is
reserved for the read-only dashboard and reporting paths.

**3. Entry point: edx-platform subsection grade change.** edx-platform
computes subsection grades in an async celery task (`recalculate_subsection_grade_v3`) triggered by a score-change signal, not on the
request thread. After that task writes the subsection grade, it calls a public openedx-core function
within the same transaction; this function does the monotone merge and the upward roll-up. This should be generalized as needed to other places that trigger a competency status update.

**4. The ACTIVE writes and roll-ups commit atomically with the subsection grade.** The leaf, group,
and competency ACTIVE writes from mechanisms 1 and 2 run inside the same transaction that mechanism 3
opened for the subsection-grade write, so they commit as a single unit with it. If any step fails,
that transaction rolls back and the task retries, leaving no partial roll-up behind.

**5. The leaf HISTORY append runs as a separate, idempotent, retrying write dispatched on commit.**
Because the leaf HISTORY table (``StudentCompetencyCriteriaStatusHistory``) may be routed to a
separate physical database (:ref:`openedx-learning-adr-0005`), its append cannot share the grade
transaction: a write to another database alias runs on its own connection and cannot be atomic with
the primary transaction, so it is a separate write even in the default single-database configuration.
Because HISTORY is the audit trail (:ref:`openedx-learning-adr-0005`), a silently dropped append is a
permanent audit gap, so the append is made durable rather than best-effort. Whether an advance
occurred, and the timestamp of that advance, are determined inside the committing transaction
(mechanisms 1 and 2) and carried to the append, so a retry records the real advance time and not the
retry time. The append is dispatched with ``transaction.on_commit`` so it fires only if the grade
transaction commits, and it runs as its own retrying task, mirroring edx-platform's established
``on_commit``-to-retrying-task pattern. A unique constraint on the advance (learner, node, and status;
:ref:`openedx-learning-adr-0002`) makes the insert idempotent, so a retry or a duplicate delivery
collapses to a no-op rather than a duplicate row. A residual gap remains if the process dies between
commit and dispatch; a reconciliation pass can detect an ACTIVE row whose latest status has no
matching HISTORY row and backfill it, though it cannot recover the original advance timestamp.


Rejected Alternatives
---------------------

1. Prevent concurrent writes with a coarser lock, either deployment-wide or per-learner.

    - Pros:
        - Correctness comes from a single lock rather than from the monotone-merge argument, so it is
          simpler to reason about.
        - A per-learner lock (for example a database advisory lock keyed on a hash of the user id)
          still lets different learners record in parallel, and gives the same per-learner
          serialization the chosen design relies on.
    - Cons:
        - A single deployment-wide lock serializes recording across every learner, giving up the
          throughput the design needs under bursty grading.
        - A per-learner lock still serializes a single learner's independent competencies against each
          other even when they never contend.
        - Either lock adds lock-lifecycle machinery (acquisition, release, and handling a holder that
          dies) across a very large key space.
        - The chosen design needs no such lock: the monotone merge (mechanism 1) makes each single-row
          write safe, and the brief per-parent row lock (mechanism 2) serializes only writers that
          actually contend for the same parent row of the same learner, so different learners, and
          different competencies of one learner, still record in parallel.

2. Recompute derived levels on read instead of materializing them.

    - Pros:
        - Eliminates the derived group and competency status rows and the roll-up writes entirely,
          leaving nothing to keep consistent on write.
    - Cons:
        - Moves the full bottom-up tree evaluation onto the hot read path, the opposite of what
          dashboards and other read surfaces need (a direct indexed lookup).
        - Settled against in :ref:`openedx-learning-adr-0002`.

3. Send an event to openedx-core and update competency statuses in a separate celery task.

    - Pros:
        - Decouples the mastery update from the grade write, so grade recording does not depend on
          competency code being installed or fast.
    - Cons:
        - Without a shared transaction, a failure or a lost event leaves the grade and its mastery rows
          permanently out of sync (data drift), with no way to roll them back together.
        - Recording the ACTIVE writes in the same transaction as the grade (mechanism 3) instead makes
          the grade and its mastery consequences commit or fail as a unit.
        - The one step that genuinely cannot share the transaction, the leaf HISTORY append, is handled
          explicitly in mechanism 5.
