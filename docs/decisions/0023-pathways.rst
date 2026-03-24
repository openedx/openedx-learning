23. Pathways
============

Context
-------

Open edX needs a way to group multiple courses (and, in the future, other learning contexts) into structured learning collections that learners can enroll in and progress through.

The pathways applet provides foundational models for defining pathways, managing enrollment, tracking learner progress, and evaluating completion criteria. It lives in ``openedx_content.applets.pathways`` as part of the Open edX Core.

Decisions
---------

1. Model Overview
~~~~~~~~~~~~~~~~~

The following diagram shows all pathway models and their relationships.

.. graphviz::

   digraph pathways {
     node [shape=record fontname="Helvetica" fontsize=10]
     edge [fontname="Helvetica" fontsize=9]

     subgraph cluster_publishing {
       label="Publishing Layer"
       style=dashed
       color=gray

       PE [label="{PublishableEntity|uuid\llearning_package (FK)\lkey\lcreated\lcreated_by (FK)\l}"]
       PEV [label="{PublishableEntityVersion|uuid\lentity (FK)\ltitle\lversion_num\lcreated\lcreated_by (FK)\l}"]
       PE -> PEV [label="1:N" style=dashed color=gray]
     }

     subgraph cluster_pathway {
       label="Pathway Definition"
       style=solid

       Pathway [label="{Pathway|publishable_entity (1:1 PK)\lkey (PathwayKeyField)\lorg (FK Organization)\l}"]
       PathwayVersion [label="{PathwayVersion|publishable_entity_version (1:1 PK)\lpathway (FK)\ldescription\lsequential\linvite_only\ldefault_step_criteria (CEL)\lcompletion_criteria (CEL)\lmetadata (JSON)\l}"]
       PathwayStep [label="{PathwayStep|publishable_entity (1:1 PK)\lpathway (FK)\l}"]
       PathwayStepVersion [label="{PathwayStepVersion|publishable_entity_version (1:1 PK)\lstep (FK)\lstep_type\lcontext_key (LearningContextKeyField)\lorder\lcriteria (CEL)\lgroup\l}"]

       Pathway -> PathwayVersion [label="1:N"]
       Pathway -> PathwayStep [label="1:N"]
       PathwayStep -> PathwayStepVersion [label="1:N"]
     }

     subgraph cluster_enrollment {
       label="Enrollment"
       style=solid

       User1 [label="{User}" style=dashed]
       PathwayEnrollment [label="{PathwayEnrollment|user (FK)\lpathway (FK)\lis_active\lcreated\lmodified\l}"]
       PathwayEnrollmentAllowed [label="{PathwayEnrollmentAllowed|email\lpathway (FK)\lcreated\l}"]
       PathwayEnrollmentAudit [label="{PathwayEnrollmentAudit|enrollment (FK)\laction\ltimestamp\l}"]

       User1 -> PathwayEnrollment [label="1:N"]
       User1 -> PathwayEnrollmentAllowed [label="1:N"]
       PathwayEnrollment -> PathwayEnrollmentAudit [label="1:N"]
       PathwayEnrollmentAllowed -> PathwayEnrollmentAudit [label="1:N"]
     }

     subgraph cluster_progress {
       label="Learner Progress"
       style=solid

       User2 [label="{User}" style=dashed]
       PathwayStepAttempt [label="{PathwayStepAttempt|user (FK)\lstep (FK PathwayStep)\lgrade\lcompletion_level\lcreated\lupdated\l}"]

       User2 -> PathwayStepAttempt [label="1:N"]
     }

     PE -> Pathway [label="1:1" style=dotted]
     PE -> PathwayStep [label="1:1" style=dotted]
     PEV -> PathwayVersion [label="1:1" style=dotted]
     PEV -> PathwayStepVersion [label="1:1" style=dotted]

     Pathway -> PathwayEnrollment [label="1:N"]
     Pathway -> PathwayEnrollmentAllowed [label="1:N"]

     PathwayStep -> PathwayStepAttempt [label="1:N"]
   }


2. Pathway Structure
~~~~~~~~~~~~~~~~~~~~

A **Pathway** is an ordered collection of steps that a learner progresses through. Each **PathwayStep** represents a single step within the pathway, which references a learning context (e.g., a course) that the learner must complete to fulfill that step.

**Publishing and Versioning**

Both ``Pathway`` and ``PathwayStep`` use ``PublishableEntityMixin`` / ``PublishableEntityVersionMixin``, linking to ``PublishableEntity`` and ``PublishableEntityVersion`` via OneToOneField (as established by the publishing applet). This provides:

- Draft/publish workflows — operators can prepare pathway changes without exposing incomplete versions to learners.
- Version history — every published change is tracked, enabling rollback and audit.
- Consistent tooling — the same publish/draft infrastructure used by other content types (Components, Units, etc.).

``PublishableEntity`` already provides ``uuid``, ``key``, ``learning_package``, ``created``, and ``created_by``. ``PublishableEntityVersion`` provides ``uuid``, ``title``, ``version_num``, ``created``, and ``created_by``. The pathway models extend these with domain-specific fields.

**Pathway** (uses ``PublishableEntityMixin``):

- ``key`` — ``PathwayKeyField`` with format ``path-v1:{org}+{path_id}`` (extends ``LearningContextKeyField``). Note It provides pathway key validation and parsing.
- ``org`` — FK to ``Organization``. Ties the pathway to a specific organization.

**PathwayVersion** (uses ``PublishableEntityVersionMixin``):

- ``pathway`` — FK back to ``Pathway``.
- ``description`` — detailed description (``title`` is inherited from ``PublishableEntityVersion``).
- ``sequential`` — whether steps must be completed in order.
- ``invite_only`` — whether enrollment is restricted to the allowlist.
- ``default_step_criteria`` — CEL expression applied to steps that don't override it.
- ``completion_criteria`` — CEL expression for pathway-level completion.
- ``metadata`` — JSONField for operator-specific extensibility (duration, difficulty, learning outcomes, etc.).

**PathwayStep** (uses ``PublishableEntityMixin``):

- ``pathway`` — FK to ``Pathway``.

**PathwayStepVersion** (uses ``PublishableEntityVersionMixin``):

- ``step`` — FK back to ``PathwayStep``.
- ``context_key`` — ``LearningContextKeyField`` referencing the learning context (e.g., ``course-v1:OpenedX+DemoX+DemoCourse``). TODO: replace it with proper foreign keys (e.g., to ``CourseRun``) before finalizing the data model.
- ``step_type`` — explicit type label (e.g., ``course``, ``pathway``) stored for query efficiency and validation rather than derived from the key at query time.
- ``order`` — position within the pathway (0-indexed).
- ``criteria`` — optional CEL expression overriding the pathway's ``default_step_criteria``.
- ``group`` — optional label for grouping steps in pathway-level expressions (e.g., "core", "elective").

Step display name and description are derived from the referenced learning context (course, subsection, etc.) and are not stored on the step itself.

Pathways can be **sequential** (steps must be completed in order) or **non-sequential** (any order). Pathways can be **invite-only**, restricting enrollment to allowlisted users.

Open Questions:
***************

#. Do we need a ``PathwayType``? If yes, what use cases would it serve that couldn't be handled within metadata?
#. Do we need ``step_type``, after all? Could we derive it from the key prefix (e.g., "course-v1" vs "path-v1")? Storing it explicitly allows for easier querying and validation, but introduces redundancy.

3. Enrollment
~~~~~~~~~~~~~

Enrollment is modeled after the existing Open edX course enrollment patterns:

- **PathwayEnrollment** tracks user-pathway enrollment state with an ``is_active`` flag for soft unenrollment.
- **PathwayEnrollmentAllowed** provides a pre-registration allowlist for invite-only pathways, enabling invitations before users register accounts.
- **PathwayEnrollmentAudit** records all enrollment state transitions for compliance and debugging.
- A **signal receiver** listens for ``User`` ``post_save`` and converts pending ``PathwayEnrollmentAllowed`` records into real enrollments when a new user registers.

4. Completion Criteria via CEL
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

Completion criteria use the `Common Expression Language <https://cel.dev/>`_ (CEL), a safe, sandboxed expression language with no side effects and guaranteed termination.

Criteria operate at two levels:

**Step-level criteria** define when an individual step is considered "passed":

- Evaluated per-step against two variables: ``grade`` (0.0–1.0) and ``completion`` (0.0–1.0).
- ``PathwayVersion.default_step_criteria`` sets the default for all steps in the pathway.
- ``PathwayStepVersion.criteria`` can override the default for a specific step.
- An empty expression means the step always passes (no requirement).
- Example: ``grade >= 0.7 && completion >= 0.8``

**Pathway-level criteria** define when the overall pathway is considered "complete":

- Evaluated once against a ``steps`` list, where each entry is a map containing ``grade``, ``completion``, ``passed`` (computed from step-level criteria), ``group``, and ``order``.
- ``PathwayVersion.completion_criteria`` defines the expression. An empty expression means all steps must pass.
- ``PathwayStepVersion.group`` provides an optional label for grouping steps in pathway-level expressions.
- Examples:

  - ``steps.filter(s, s.passed).size() >= 4`` — pass any 4 steps
  - ``steps.filter(s, s.group == "core" && s.passed).size() >= 3 && steps.filter(s, s.group == "elective" && s.passed).size() >= 2`` — pass 3 core and 2 elective steps
  - ``steps.all(s, s.grade >= 0.8)`` — all steps must have grade at least 80%. TODO: This overrides the step-level criteria, so it could lead to a step being considered "not passed" at the step level but still contributing to pathway completion if its grade is high enough.
  - ``steps.filter(s, s.completion >= 1.0).size() == steps.size()`` — all steps must be fully completed
  - ``steps.filter(s, s.order <= 2 && s.passed).size() == 3 && steps.filter(s, s.order > 2 && s.grade >= 0.9).size() >= 1`` — first 3 steps must pass, plus at least 1 later step requires a grade of at least 90%
  - ``steps.map(s, s.grade).reduce(acc, val, acc + val) / steps.size() >= 0.75`` — average grade across all steps must be at least 75%

5. Learner Progress Tracking
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

**PathwayStepAttempt** — records a student's progress on a given attempt to fulfill a pathway step. This data is stored for efficiency in evaluating criteria and supporting progress displays without having to query the underlying learning context (e.g., course) for each step on the fly.

- ``user`` — FK to the user.
- ``step`` — FK to ``PathwayStep``.
- ``grade`` — current grade (0.0–1.0).
- ``completion_level`` — current completion (0.0–1.0).
- ``created``, ``updated`` — timestamps.

This stores one row per student per attempt (e.g., per course run), not per grade change. Detailed progress history is handled by eventing/analytics.

Whether a student has completed a step or the overall pathway is computed on-the-fly by evaluating the CEL criteria against the attempt data — there are no separate status models.

Open Questions:
***************

#. **Completion tracking performance**: For grades, we can rely on persistent grades. However, calculating completion currently requires building the course tree for each user, which is slow (and updating this entity may happen thousands of times for each learner within a course). Tracking earned/possible completions in ``PathwayStepAttempt`` could be an option, but introduces invalidation complexity: completions would need to be recalculated on course publish and when gated content becomes available (e.g., due to release dates set in the future).
#. **Multiple course runs**: The initial assumption was that a Pathway can reference only a single course run. However, one of the described use cases is changing a course run while keeping the same pathway. How do we want to support this?

6. Retrieving data from openedx-platform
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

TODO.

Consequences
------------

- The pathways applet provides a stable foundation for pathway management within Open edX Core, following the applet pattern established in ADR 0020.
- Using ``PublishableEntityMixin`` / ``PublishableEntityVersionMixin`` gives pathways proper draft/publish workflows and version history, consistent with other content types in the system.
- CEL-based criteria provide a flexible, safe way to express arbitrarily complex completion requirements without custom code.
- The two-level criteria design (step-level + pathway-level) supports both simple per-step thresholds and complex aggregate requirements like "pass N of M steps" or grouped criteria.
- External consumers (``openedx-platform``, plugins) can interact through either the public Python API or the REST API (both TBD).
