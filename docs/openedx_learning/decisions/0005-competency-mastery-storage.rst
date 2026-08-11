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

Row count concentrates at the leaf. A course can carry on the order of 200 leaf criteria, so the
leaf table holds roughly learners x attempted leaves, which reaches the low billions for an Open edX
instance with millions of learners. The two tables above it are smaller, by the tree's fan-out.

That scale is not, on its own, what makes a relational database struggle. A point lookup against a
billion-row table backed by the right composite index is a logarithmic-time index seek regardless of
the table's size, and every read this ADR sizes for is such a lookup: the learner-facing dashboard
asks for one learner's status, and each index in :ref:`openedx-learning-adr-0002`, Decision 5 leads
with the learner. What billions of rows makes painful is schema migrations, backups, and any
non-indexed or aggregate query.

So the question here is narrow: given that row count, does the leaf level need storage treatment of
its own, or does it use the same database and the same conventions as everything else in this repo?

Decision
--------

1. **Materialize a status row at all three levels, including the leaf.** Each table holds at most one
   row per learner and node, updated in place, and that row is the learner's current status. A row
   exists only once the learner has attempted that node, so absence means not yet attempted rather
   than a status of its own. Nothing is recomputed on read, so a read is a direct indexed lookup on
   the unique ``(learner, node)`` index (:ref:`openedx-learning-adr-0002`, Decision 5) rather than an
   evaluation of the tree. Storing the leaf in particular freezes what a learner demonstrated against
   the criteria as they stood at the time, so later restructuring of the tree cannot change it.

2. **A status write is an upsert against that unique index**, not a read-then-insert. Two workers
   handling a redelivered grade event can both find no row for a learner and node and both try to
   insert one; the unique index has to resolve that race rather than fail it, since surviving
   duplicate delivery is what :ref:`openedx-learning-adr-0004`, Decision 2 is for, and its Decision 3
   lock is on the group row, which does not protect a leaf row that does not exist yet.

3. **All three tables live in the deployment's default database, unpartitioned and unsharded, and
   are both read and written on the primary.** One recording therefore runs on one connection. That
   is what lets :ref:`openedx-learning-adr-0004`, Decision 1 commit the leaf write, every ancestor
   write, and the platform's grade write as a single transaction, and what makes the group row lock
   in :ref:`openedx-learning-adr-0004`, Decision 3 actually serialize the writers it is aimed at.

4. **These tables get no schema conventions of their own.** They take this repo's defaults: a
   ``BigAutoField`` primary key (:ref:`openedx-content-adr-0003`, and OEP-68 for Open edX models
   generally) and a real foreign key to ``settings.AUTH_USER_MODEL``. Their size is not by itself a
   reason to deviate.

Assumptions
-----------

1. The consuming deployment routes these tables and the platform's grade write to the same database
   alias. ``transaction.atomic()`` is per-alias, so a router that splits them silently voids
   :ref:`openedx-learning-adr-0004`, Decision 1 with no error and no failing test. This holds in
   edx-platform today, but it is a property of a repo this one cannot see or enforce.

2. No caller redirects the recorder's reads to a read replica. edx-platform installs
   ``edx_django_utils``'s ``ReadReplicaRouter``, which defaults reads to the writer but exposes a
   thread-local ``read_queries_only()`` that redirects reads for every model inside the block. The
   recorder reads the value it is about to overwrite and takes ``SELECT ... FOR UPDATE`` on a group
   row; neither survives being routed to a replica.

Out of Scope
------------

**Learner status history is left to a future ADR.** An audit trail is a real requirement: an
instance needs to be able to explain why a learner did or did not achieve mastery of a competency,
or of any of the associated measurement instruments such as a gradeable subsection. The three tables
decided here do not provide it, because an in-place update overwrites the status it replaces.

What this decision alone can answer:

- A learner's current status at any level, as a point lookup.
- Which criterion, and through it which tag/object association, currently backs a leaf status. The
  criterion foreign key survives, and those associations cannot be hard-deleted once learner status
  exists (:ref:`openedx-learning-adr-0003`, Decision 3).
- What rule a criterion carried at some past time, from the ``django-simple-history`` records on the
  definition models (:ref:`openedx-learning-adr-0003`, Decision 1).
- When a status last changed, from ``modified`` (:ref:`openedx-learning-adr-0002`, Decision 6).

What it cannot answer: a learner's status as of an arbitrary past date, the path a node took through
the status lattice, why a status was kept rather than lowered after a downward grade correction, or
what a tag/object association looked like when it produced a status, since ``oel_tagging_objecttag``
carries no history of its own and edits to it remain permitted
(:ref:`openedx-learning-adr-0003`, Decision 4).

One constraint carries forward to whatever decides history: it may add tables, but it may not make
these three append-only. The unique ``(learner, node)`` indexes in
:ref:`openedx-learning-adr-0002`, Decision 5 already forbid it, and
:ref:`openedx-learning-adr-0004`, Decisions 2 and 3 need exactly one row per learner and node to
merge into and to lock.

A signal-based history mechanism such as ``django-simple-history`` records nothing written through
``queryset.update()`` or ``bulk_update()``. That is a constraint on the recorder now, not on the
future ADR: it is built first, and if it writes in bulk it forecloses that option before anyone
reads this.

Deferring history is cheap rather than free: adding a table later is an additive migration that
touches none of the columns or indexes decided here, and automatic updates advance a status a
bounded number of times per learner and node, since the lattice is small and
:ref:`openedx-learning-adr-0004`, Decision 2 never lowers one. Staff edits
(:ref:`openedx-learning-adr-0004`, Decision 4) can lower a status and so allow it to advance again,
but they are human-initiated and rare enough not to change the order of magnitude. What cannot be
recovered is the record of what happened before that table exists.

Two further questions are not settled here: what happens to these rows when a user is deleted or
retired, and how staff-facing reads that span learners rather than a single learner are served.
Every index decided so far leads with the learner, so a cross-learner or aggregate read is exactly
the non-indexed query this ADR's Context calls painful at this row count.

Rejected Alternatives
---------------------

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
