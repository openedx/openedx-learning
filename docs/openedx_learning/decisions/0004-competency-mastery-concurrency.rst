.. _openedx-learning-adr-0004:

4. How should learner competency mastery be recorded concurrently and at scale?
================================================================================

Status
------
Proposed.

Context
-------
A learner's mastery of one competency is stored at three levels of the criteria tree: the graded
leaf criterion, each criteria group above it, and the competency itself. There is one row per
learner and node, updated in place (:ref:`openedx-learning-adr-0002`,
:ref:`openedx-learning-adr-0003`). Each row holds one of three values, lowest to highest:
``AttemptedNotDemonstrated``, ``PartiallyAttempted``, ``Demonstrated``.

One grade change updates the leaf and then every row above it, for many learners at once. This ADR
decides how those updates stay correct when two of them for the same learner overlap.

The problem: a group requires both Assignment A and Assignment B, and celery tasks recomputing
grades and competency statuses for this worker run at the same time. That is likely to happen
when instructor actions trigger multiple subsection grading events.
Each of the two writers sees its own assignment done and the other still outstanding,
so both write "not demonstrated" for the group. Both are wrong, both have finished, and nothing is
left to correct it.

Two constraints shape the answer. First, **the grading task cannot be one transaction**: it reads
MongoDB and memcached, writes to file storage, queues further celery tasks, publishes events, and
triggers database writes owned by four other Django apps. Wrapping all of that would roll back other
apps' data and publish events for a grade that never commits. Second, **everything above the leaf is
derived**: a group's value can always be recalculated from the leaves beneath it, so the leaf is the
only row that is a direct consequence of the grade.

Decision
--------

1. **Write the leaf status in the same transaction as the grade. Nothing above it.**
   The grading task calls one openedx-core function, which writes the leaf, so the grade and its
   leaf commit or fail together. Every row above the leaf is written after that transaction commits.

2. **Roll up one level at a time, committing each level before reading the next. Take no locks.**
   A writer sees only committed data, so whichever writer reads a parent last sees all its children
   at their final values and computes the correct result. Some writer always reads last, so the tree
   ends up correct and no writer waits for another.

3. **Automatic updates may only raise a status, never lower it.** Each write stores whichever is
   higher, the stored or the newly computed value, in a single statement so concurrent writers cannot
   overwrite each other. A writer reading stale data can then only compute a value that is too low,
   and too low is discarded. That is also what makes celery's repeated and out-of-order delivery
   harmless.

4. **Re-run a failed roll-up rather than undoing the grade.** By Decision 3 a failure leaves rows too
   low, never too high, so nothing incorrect needs undoing and re-running is always safe.

5. **Add a "dirty" marker, set with the value change and cleared once the parent has been
   recalculated.** It is set by the same statement that changes the value, so nothing can fail in
   between, and cleared whether or not the parent's value changed. Clearing is conditional on the
   value passed up still being current, otherwise one writer can clear another's marker and lose its work.

6. **A scheduled job looks for "dirty" markers and finishes roll-ups that stopped partway.**
   The job is scheduled rather than triggered, because a killed worker raises no exception to react
   to. openedx-core cannot own a scheduler, so it exposes the entry point and the deployment sets the
   interval. In a healthy system no markers are set, so a marker older
   than the interval is also the alert.

7. **Only a direct staff edit may lower a status.** A staff correction may set any value, and the
   rows above it are recalculated and overwritten rather than merged. A later grade change can raise
   what an edit lowered, but never lower what an edit raised. It is also the only path that takes a
   lock, on the learner's root group row.

Rejected Alternatives
---------------------

1. Lock each criteria group row before recalculating it. This was the previous decision here.

    - Pros:
        - Correctness comes from making contending writers take turns, which is easier to prove than
          an argument about the order of commits and reads.
    - Cons:
        - One grade change can affect several leaves of the same tree, so a writer can need several
          locks at once, which introduces deadlocks that need their own detection and retry code.
        - It puts a lock wait on every grade change. MySQL waits 50 seconds by default, inside a task
          allowed 300 seconds in total.
        - Correctness would depend on the isolation level, silently, and SQLite has no row locks, so
          the test suite could not exercise it.

2. Share one transaction between the grade and the whole roll-up, not just the leaf. This ADR
   originally assumed this was available.

    - Pros:
        - The grade and every mastery row it touches would commit or fail together, so no roll-up
          could ever be left unfinished and Decisions 5 and 6 would be unnecessary.
    - Cons:
        - The grading task cannot be wrapped in a transaction at all, for the reasons in the Context.
        - Wrapping only the roll-up is worse than doing nothing: it hides each writer's changes from
          the other until both have finished, which is the problem in the Context again, one level up
          the tree and harder to diagnose.

3. Take one lock on the learner's root group row, then recalculate the whole subtree beneath it.

    - Pros:
        - Easy to reason about: one lock, always the same row, so no deadlock and no ordering
          argument.
    - Cons:
        - It puts a lock, and its timeout handling, on every grade change rather than only on the
          rare path that lowers a value.
        - It makes a learner's unrelated competencies wait for each other, and needs row locks,
          which SQLite does not support.

    This is the right shape for the paths that lower a value, and Decision 7 uses it there.

4. Use a coarser lock, either one per deployment or one per learner.

    - Pros:
        - A single lock replaces the ordering argument in Decision 2.
    - Cons:
        - A deployment-wide lock serializes every learner behind every other, giving up the
          throughput bursty grading needs.
        - Either kind adds machinery for acquiring and releasing locks, and for recovering from a
          dead lock holder, across a very large key space.

5. Recalculate the derived levels on every read instead of storing them.

    - Pros:
        - No roll-up writes at all, so there is nothing to keep consistent.
    - Cons:
        - It moves a full bottom-up tree evaluation onto every read, the opposite of what dashboards
          need.
        - Already settled against in :ref:`openedx-learning-adr-0002`. Unresolved item 1 is the
          narrower version still open.

6. Send an event to openedx-core and do all the work in a separate celery task.

    - Pros:
        - Recording a grade would not depend on the competency code being installed or fast.
    - Cons:
        - openedx-core is a library and cannot own a celery queue, so every caller would supply one.
        - The leaf would no longer commit with the grade, giving up the one guarantee Decision 1 is
          cheap enough to keep.

7. Detect conflicts optimistically, with a version column and a retry loop for the losing write.

    - Pros:
        - Contention costs a retry rather than a wait.
    - Cons:
        - Decision 3 is already optimistic, without the retry loop. A write that loses has computed
          a value that is too low, and discarding those is exactly what Decision 3 does.
