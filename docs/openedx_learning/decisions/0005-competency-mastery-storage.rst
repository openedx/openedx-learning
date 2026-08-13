.. _openedx-learning-adr-0005:

5. How should learner competency status be stored at scale?
===========================================================

Status
------
Proposed.

Context
-------
Competency achievement criteria form a boolean tree (:ref:`openedx-learning-adr-0002`). A
``CompetencyCriterion`` leaf points at one tag/object association and a rule; a
``CompetencyCriteriaGroup`` combines its children with an ``AND``/``OR`` operator, up to the
competency itself. A learner's mastery is tracked against that tree in three tables, one per level:
``StudentCompetencyCriteriaStatus`` (leaf), ``StudentCompetencyCriteriaGroupStatus`` (group), and
``StudentCompetencyStatus`` (competency). :ref:`openedx-learning-adr-0002`, Decision 6 defines their
columns and :ref:`openedx-learning-adr-0003`, Decision 5 says they are updated in place.

Row count concentrates at the leaf. A course may for example carry on the order of 200 leaf criteria, so the
leaf table holds roughly learners x attempted leaves, which reaches the low billions for an Open edX
instance with millions of learners. The two tables above it are smaller, by the tree's fan-out.

If we store history of status attempts, or if we use append-only tables, we add a multiplier:
learners x attempted leaves x problem attempts for this leaf and learner. That means that every time
a problem in a subsection is attempted by a student, a new row is written. That would increase the order
of magnitude well beyond the potential low billions to easily tens of billions.

That scale is not, on its own, what makes a relational database struggle. A point lookup against a
billion-row table backed by the right composite index is a logarithmic-time index seek regardless of
the table's size, and every read this ADR sizes for is such a lookup: the learner-facing dashboard
asks for one learner's status, and each index in :ref:`openedx-learning-adr-0002`, Decision 5 leads
with the learner. What billions of rows makes painful is schema migrations, backups, and any
non-indexed or aggregate query.

On the requirements side, no student competency status history is needed. This allows us to
define the tables without history or append-only restraints.

Decision
--------

1. **Do not store history for student competency statuses. Don't add a history table.**
   Because the history that is needed for Competencies is owned by ORAs, there is
   no need to store history of competency status changes.
   And storing history on a massive leaf table is difficult because:
   - The history table grows with each problem attempt without clear bounds.
   - Similar huge tables in openedx-platform pose a big maintenance burden.
   - Truncation and deletion poses challenges.
   - Storage is expensive.

2. **Update Rows instead of making them append-only.**
   Having append-only tables for competency statuses runs into the same problem. They will
   grow just as massive. Instead, since we don't need to track history,
   it is sufficient to just update a row when it changes. This scales much better.

3. **Build the student competency status tables for scale.**
   As some of these tables will become massive, we want to avoid making migrations and schema changes necessary later.
   Thus, we do our best to make sure that the fields and indexes are future-proof, not needing to add fields later on,
   and select the indexes so that even a table in the billions of rows can be sufficiently performant.

Rejected Alternatives
---------------------

0. Add separate history tables that track status attempts.

   This is not required any longer.

1. Compute leaves transiently, never store them.

    - Pros:
        - Eliminates the largest table, since leaf demonstration would be computed on demand from
          the leaf's rule and the learner's grade.
    - Cons:
        - A recomputed leaf reflects the rule as it stands now, not the rule that was in force when
          the learner was graded. That contradicts :ref:`openedx-learning-adr-0003`, Decision 4,
          which says criteria edits apply going forward and do not retroactively update existing
          learner statuses, and it can silently lower a status, which its Decision 5 forbids.

2. Keep the tables append-only: never update a row, and resolve current status as the latest row for
   a learner and node.

    - Pros:
        - Every write is an insert rather than a read-modify-write, so there is no current row to
          keep consistent.
    - Cons:
        - A read must resolve the latest row for a learner and node rather than reading one in-place
          row, which is more expensive and more complex.
        - There is no single current row for :ref:`openedx-learning-adr-0004`, Decision 3 to lock,
          and nothing for its Decision 2 merge to write into. Both would have to be redesigned.
        - This was the design before :ref:`openedx-learning-adr-0003`, Decision 5, and reopening it
          here would settle the deferred history question by accident and only partly, since a status
          row records neither who changed it nor why.

3. Put the leaf table behind its own Django database alias and router, or make a separate physical
   database mandatory, or partition or shard it, up front.

    - Pros:
        - Physically isolates or splits the largest table from the start. In the router variant the
          alias would default to the main database, letting a deployment opt into a separate
          physical database later without a schema change.
        - There is prior art in edx-platform, the courseware-history router
          (``StudentModuleHistoryExtended``).
    - Cons:
        - A second alias gives up atomicity, and here that is disqualifying rather than merely
          costly. Django runs a write to another alias on its own connection, so the leaf write and
          the ancestor writes could no longer share one transaction with the grade write, which is
          what :ref:`openedx-learning-adr-0004`, Decision 1 requires.
        - The prior art does not actually support the pattern: edx-platform's courseware-history
          router was retrofitted to work around a 32-bit primary key running out, not adopted as a
          scaling design.
        - Mandating a separate physical database or a partitioning scheme imposes real operational
          cost on every deployment, with nothing measured to justify it.
        - Premature, and mostly reversible: an alias, a separate physical database, and
          application-level sharding all remain available if a specific need is proven. Native MySQL
          partitioning does not, and that is accepted here: MySQL requires every column of the
          partitioning expression to appear in every unique key, and Decision 4's surrogate ``id``
          primary key and Decision 1's unique ``(learner, node)`` key share no column, so partitioning
          would first mean changing the primary key of the largest table in the schema.

4. Store child evaluations on the parent group row instead of a leaf table (an enriched
   attained-set).

    - Pros:
        - Avoids the largest table entirely.
    - Cons:
        - A leaf write stops being an independent single-row merge and becomes a read-modify-write
          of a column shared with every sibling, so it has to hold the group lock across the whole
          write rather than only across the recompute
          (:ref:`openedx-learning-adr-0004`, Decisions 2 and 3).
        - Reaches past this ADR: it would also mean amending :ref:`openedx-learning-adr-0002`,
          Decisions 5 and 7 and :ref:`openedx-learning-adr-0003`, Decision 4, all of which key on a
          per-leaf status row existing.
        - A status packed into a per-group array has no unique index and no foreign key behind it,
          so nothing but application code keeps it consistent with the criteria it describes.
        - Couples a leaf's frozen mastery to the current shape of the criteria tree, so restructuring
          the tree can corrupt already-recorded mastery (Decision 1).
        - The single-row group read it optimizes is already served acceptably by an indexed range
          read of a learner's leaf rows.

5. Serve heavy reads of the leaf table from a read replica
   (``edx_django_utils``'s ``read_replica_or_default()``).

    - Pros:
        - Keeps dashboard and reporting reads of the largest table off the primary, where row count
          and read volume concentrate.
    - Cons:
        - Premature: no measurement shows the primary struggling with these reads. The dashboard
          reads are point lookups on a composite index, not the large, expensive, widely-called
          reads that drive ``StudentModule`` load in edx-platform, so CBE read load should be much
          lower.
        - Replica lag is a correctness hazard next to the recorder, which must read the primary. A
          replica cannot serve the ``SELECT ... FOR UPDATE`` in :ref:`openedx-learning-adr-0004`,
          Decision 3 at all. Introducing replica reads means maintaining that distinction in every
          new read path.
        - Adding it later is cheap, since it is a per-query choice rather than a schema decision.

6. Give the leaf table a custom unsigned 64-bit primary key (``UnsignedBigIntAutoField``), as
   edx-platform does on ``PersistentSubsectionGrade``.

    This doubles the positive range of a plain ``BigAutoField``, but that range is already far out of
    reach for this table, and an instance approaching it would hit other limits first. A custom field
    type carries ongoing maintenance cost, and unsigned integers do not exist in PostgreSQL.
    ``BigAutoField`` is the default for Open edX models, so these tables need no primary-key decision
    of their own.

7. Drop the database-level constraint on the learner foreign key (``db_constraint=False``), mirroring
   edx-platform's ``StudentModule``.

    The argument for it was that a real constraint costs write throughput at this volume, because a
    hot user row would see extra lock contention. Reports of user-row contention in edx-platform do
    exist (which is why ``completion`` and ``bookmarks`` dropped their constraints), but they are not
    understood well enough to design around here. This repo's convention is a real foreign key to
    ``settings.AUTH_USER_MODEL``, which already keeps the models independent of any concrete user
    model, so these tables follow it and need no decision of their own.
