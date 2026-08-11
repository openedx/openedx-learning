.. _openedx-learning-adr-0004:

4. How should learner competency mastery be recorded concurrently and at scale?
================================================================================

Status
------
Proposed.

Context
-------
A learner's mastery of one competency is stored at three levels of the competency criteria tree:
the leaf criterion that was graded, each criteria group above it, and the competency itself. There
is one row per learner and node, updated in place (:ref:`openedx-learning-adr-0002`,
:ref:`openedx-learning-adr-0003`). Each row holds one of three values, lowest to highest:
``AttemptedNotDemonstrated``, ``PartiallyAttempted``, ``Demonstrated``.
So one grade change updates the leaf and then every row above
it, for a very large number of learners, in bursts. This ADR decides how those writes stay correct
when two of them for the same learner overlap.

What triggers a change is a subsection grade, or any other learning instrument tied to a
competency by a competency criterion, such as a course grade or a rubric criterion. The rows above
the leaf are stored rather than recomputed on read because they also drive notifications, badges,
and certificate issuing, so the roll-up has to happen when the grade does either way.

Decision
--------

1. **The platform's grading task calls one openedx-core function, in the same atomic transaction as the
   grade write.** Subsection grading already happens in a celery task; that task writes the grade
   and then calls this function, which updates the leaf and walks up. Writing up the tree stops
   where :ref:`openedx-learning-adr-0002`, Decision 6 says it stops.

2. **Automatic updates only move a status up: each write stores the higher of the stored value and
   the newly computed one.** This makes the recorder safe
   against celery delivering the same work twice or out of order. Applying one grade event twice
   lands on the same value as applying it once.

3. **Before recomputing a group, lock that group's row.**
   If two children advance at the same moment, each recomputation could read the other child as not yet
   advanced. Both would then compute the same too-low value. Locking the group first makes the two writers take turns, so the
   second one reads the first's committed children. Handling deadlocks is needed: see Unresolved 1.

4. **A direct staff edit is the exception to all of the above.** An instructor or admin correcting
   a status by hand may set any value, including a lower one, and the rows above the edited one are
   recomputed and overwritten rather than merged, including any an earlier staff edit set by hand.
   So a staff edit or a Django admin change is the only thing that can lower
   a status, and a later grade change can raise what an edit lowered but can never re-lower what an
   edit raised.

Unresolved
----------

1. How to avoid deadlocks on competency group node locks that a) involve a grade change locking one group and
   b) involve a grade change locking multiple groups, which happens when one subsection manifests as multiple leafs
   in the same tree.
2. How notifications, badges, and certificates learn that a row moved.

Assumptions
-----------

1. Connections run at ``READ COMMITTED`` isolation. Decision 3 depends on it: the read taken after
   the lock has to see current data rather than a snapshot from earlier in the transaction. MySQL's
   own default is ``REPEATABLE READ``, but Django overrides it to ``READ COMMITTED`` on every
   connection and edx-platform leaves that alone. A deployment that changes the setting breaks
   decision 3 with no error and no failing test.

Rejected Alternatives
---------------------

1. Prevent concurrent writes with a coarser lock, either deployment-wide or per-learner.

    - Pros:
        - Correctness comes from a single lock rather than from the merge argument in Decision 2,
          so it is simpler to reason about.
        - A per-learner lock (for example a database advisory lock keyed on a hash of the user id)
          still lets different learners record in parallel, and gives the same per-learner
          serialization the chosen design relies on.
    - Cons:
        - A single deployment-wide lock serializes recording across every learner, giving up the
          throughput the design needs under bursty grading.
        - A per-learner lock still serializes a single learner's independent competencies against
          each other even when they never contend.
        - Either lock adds lock-lifecycle machinery (acquisition, release, and handling a holder
          that dies) across a very large key space.
        - The chosen design needs no lock beyond the row locks the database already takes for the
          statements it issues: the merge (Decision 2) makes each single-row write safe, and the
          parent row lock (Decision 3) serializes only writers that actually contend for the same
          parent row of the same learner, so different learners, and different competencies of one
          learner, still record in parallel.

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
        - Without a shared transaction, a failure or a lost event leaves the grade and its mastery
          rows permanently out of sync (data drift), with no way to roll them back together.
        - Writing the statuses in the same transaction as the grade (Decision 1) instead makes the
          grade and its mastery consequences commit or fail as a unit.

4. Commit the leaf, then re-read the leaves before rolling up, with no lock.

    - Pros:
        - Correct, and lock-free. Every writer commits its leaf before reading, so whichever writer
          reads last sees every leaf already committed and computes the true value; the merge in
          Decision 2 keeps it.
    - Cons:
        - The leaf has to commit before the roll-up reads, so the roll-up cannot share the grade's
          transaction, which reopens the partial-failure window Decision 1 exists to close.

5. Detect conflicts optimistically: a version column plus a unique constraint, and the losing write
   retries.

    - Pros:
        - Contention costs a retry rather than a wait, so no writer ever blocks.
    - Cons:
        - Every writer needs conflict handling and a retry loop, and repeated contention on one
          parent multiplies retries. The row lock in Decision 3 reaches the same result by waiting.
