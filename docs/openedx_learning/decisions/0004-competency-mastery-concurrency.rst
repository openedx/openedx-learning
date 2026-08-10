.. _openedx-learning-adr-0004:

4. How should learner competency mastery be recorded concurrently and at scale?
================================================================================

Status
------
Proposed.

Context
-------
When a learner is graded on a subsection, the platform must work out whether that grade demonstrates
any attached competencies, and record it. The same goes for any other learning instrument tied to a
competency by a competency criterion, such as a course or a rubric criterion.

Mastery is recorded at three levels: the criterion (leaf), the criteria group, and the competency.
Per :ref:`openedx-learning-adr-0002`, all three are stored rather than recomputed on read, so that
dashboards and other read surfaces stay fast. Per :ref:`openedx-learning-adr-0003`, each level keeps
one row per learner and node, updated in place.

So a single grade change writes the changed leaf's status, then re-evaluates and re-writes every
derived row from that leaf up to the competency root. The roll-up is not only for reads: it also
drives notifications, badges, and certificate issuing.

**Monotonicity: the recorder only ever moves a status forward.** Every node advances through a small
status lattice (``AttemptedNotDemonstrated`` to ``PartiallyAttempted`` to ``Demonstrated``), and the
recorder never lowers it (:ref:`openedx-learning-adr-0003`). That holds at all three levels, and for
both of the recorder's triggers: neither a downward grade correction nor a change to the competency
criteria rules lowers a recorded status.

Monotonicity is a property of that automatic path, not of the stored data. Staff can set a learner's
status directly, through Django admin or as a deliberate instructor correction, and a direct edit
may lower it. A direct edit also cascades: the ancestors above the edited node are recomputed up to
the root, so an instructor correcting a leaf from ``Demonstrated`` to ``AttemptedNotDemonstrated``
lowers the group and competency rows above it too. That cascade cannot use the monotone merge of
mechanism 1, which never lowers anything, so it overwrites each ancestor with the freshly computed
value. It does take the same parent locks as mechanism 2, so it stays ordered against concurrent
recorder writes.

One consequence: a direct edit is the only thing that can lower a status. A later grade change
merges against whatever the edit left behind, so it can raise a status an edit lowered, but it can
never re-lower one an edit raised.

Two forces shape how recording should happen:

- **Same-learner correctness.** Leaf rows are never in doubt, since each leaf is a pure function of
  its own grade. The derived rows are the hazard. Two evaluations for the same learner that overlap
  can each read a stale snapshot of the sibling leaf statuses, and each write a roll-up computed
  from an incomplete picture.

- **Throughput.** Grading is bursty and spans a very large number of learners, so the recording
  path must keep up under peak load.

Decision
--------

**1. A recorder write only ever advances the stored value.** Every write is
``status := max(stored status, newly computed status)``, a single ``GREATEST``-style ``UPDATE`` with
no application-level lock. Taking the higher of the two values makes the write idempotent and
insensitive to order, so out-of-order delivery and re-delivery are harmless without sequence
tracking. The database holds that row's exclusive lock until the transaction commits, which is what
mechanism 2's lock ordering relies on.

**2. When a child advances, its parent is recomputed in the same transaction, under a row lock on
the parent.** A parent's rule can be conjunctive, for example "demonstrated only when all children
are demonstrated", so recomputing it means reading all of its children first. If two children of one
parent advance at the same time, each recomputation could read the other child's old value and write
a parent status that is too low.

To prevent that, a recomputation locks the parent row (``SELECT ... FOR UPDATE``) before reading the
children. The two writers take turns, and the second reads the first's committed children.

This relies on ``READ COMMITTED`` isolation, Django's default for MySQL, which the platform does not
override. Under it, the child reads that follow the lock return the latest committed rows. Under
``REPEATABLE READ`` they would instead return a snapshot fixed at an earlier read in the same
transaction, and the second writer would still see the stale child.

Locks are taken child-before-parent, up the path to the root. The criteria tree gives every node
exactly one parent (:ref:`openedx-learning-adr-0002`), so that path is unique, and two transactions
touching the same ancestor always reach it in the same order. They cannot deadlock. Where one grade
change advances several leaves at once, because a subsection carries several criteria, those leaves
are locked in primary-key order for the same reason.

**3. Entry point: a subsection grade change in edx-platform.** edx-platform computes subsection
grades in an async celery task (``recalculate_subsection_grade_v3``) triggered by a score-change
signal, not on the request thread. After that task writes the subsection grade, it calls a public
openedx-core function in the same transaction, which does the merge and the roll-up. As other kinds
of competency criteria are defined, completion for example, further entry points will call that same
function.

**4. The status writes and the roll-ups commit atomically with the subsection grade.** The leaf,
group, and competency writes from mechanisms 1 and 2 run inside the transaction that mechanism 3
opened for the subsection-grade write, so they commit as one unit with it. If any step fails, the
transaction rolls back and the task retries, leaving no partial roll-up behind.


Open Questions
--------------

1. **Confirm that a direct staff edit cascades to ancestors.** The Context above decides that it
   does: correcting a learner's leaf status by hand recomputes the group and competency rows above
   it, downward if that is what the rules produce. The alternative is to leave the ancestors
   untouched and require a separate reconciliation step. Cascading is what an instructor issuing a
   correction would expect, but it costs something: the recorder is no longer the only writer that
   can lower a status, and a stored ancestor status is no longer a pure function of the recorder's
   own history. This decision should be confirmed before implementation.

2. **Decide whether a cascade may overwrite a hand-set ancestor.** If a staff user has set a group
   or competency status directly, and a later direct edit below it cascades upward, the recomputed
   value overwrites the hand-set one. Whether a hand-set ancestor should instead survive the
   cascade is undecided.


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
          write safe, and the per-parent row lock (mechanism 2) serializes only writers that
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
        - Recording the status writes in the same transaction as the grade (mechanism 3) instead makes
          the grade and its mastery consequences commit or fail as a unit.
