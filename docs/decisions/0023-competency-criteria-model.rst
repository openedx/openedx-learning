23. How should CBE competency achievement criteria be modeled in the database?
==============================================================================

Context
-------
Competency Based Education (CBE) requires that the LMS have the ability to track learners' mastery of competencies through the means of competency achievement criteria. For example, in order to demonstrate that I have mastered the Multiplication competency, I need to have earned 75% or higher on Assignment 1 or Assignment 2. The association of the competency, the threshold, the assignments, and the logical OR operator together make up the competency achievement criteria. Course Authors and Platform Administrators need a way to set up these associations in Studio so that their outcomes can be calculated as learners complete their materials. This is an important prerequisite for being able to display competency progress dashboards to learners and staff to make Open edX the platform of choice for those using the CBE model.

In order to support these use cases, we need to be able to model these rules (competency achievement criteria) and their association to the tag/competency to be demonstrated and the object (course, subsection, unit, etc) or objects that are used as the means to assess competency mastery. We also need to leave flexibility for a variety of different types as well as groupings to be able to develop a variety of pathways of different combinations of objects that can be used by learners to demonstrate mastery of a competency.

Additionally, we need to be able to track each learner's progress towards competency demonstration as they begin receiving results for their work on objects associated with the competency via competency achievement criteria.

Terminology
-----------
To reduce ambiguity, this ADR uses the following CamelCase domain terms:

- ``CompetencyTaxonomy``: A taxonomy that is explicitly enabled for CBE competency features.
- ``CompetencyAchievementCriteria``: The full criteria expression used to evaluate each learner's status for one competency. Evaluation yields a competency outcome (at minimum demonstrated/not demonstrated, and potentially richer outcomes such as mastery level in future ADRs).
- ``CompetencyCriteriaGroup``: An internal node in the ``CompetencyAchievementCriteria`` expression tree that combines child nodes with ``AND`` or ``OR``.
- ``CompetencyCriterion``: A leaf node in the ``CompetencyAchievementCriteria`` expression tree. It points to one tag/object association plus the rule used to evaluate that object.
- ``CompetencyRuleProfile``: A reusable default evaluation rule that can be scoped by taxonomy, course, or organization.

In short: ``CompetencyAchievementCriteria`` is the full tree, while ``CompetencyCriterion`` is one leaf in that tree.

Decision
--------

1. ``CompetencyTaxonomy`` concept (database table)

   Represents the set of taxonomies that are competency-enabled rather than generic tag-only taxonomies.

   Maps to ``Taxonomy`` using Django multi-table inheritance (``CompetencyTaxonomy(Taxonomy)``), not a ``taxonomy_type`` column on ``oel_tagging_taxonomy``.

   Relationship to other concepts:

   - ``CompetencyRuleProfile`` can be scoped to a ``CompetencyTaxonomy``.
   - ``CompetencyCriteriaGroup`` and ``CompetencyCriterion`` are only valid for competencies from enabled taxonomies.

   A taxonomy listed in this table:

   - is able to be displayed in the UI with the competency criteria association view.
   - is able to be displayed in the UI with the competency progress tracking views.
   - is also able to be displayed in existing taxonomy views.
   - has constraints on associated content objects to only be those supported for progress tracking.
   - has constraints on associated content objects to only include ones that could logically be used to demonstrate mastery of the competency (for example, associating both a course and one assignment within that same course would be ambiguous).

   In contrast, a taxonomy that is not listed in this table:

   - is only displayed in existing taxonomy views.
   - is not displayed in competency criteria association views.
   - is not displayed in competency progress tracking views.
   - has no competency-specific constraints on associated content objects.

   This new database table will have the following columns:
   1. ``taxonomy_ptr_id``: Primary key and one-to-one foreign key to ``oel_tagging_taxonomy.id``.

   Lifecycle rules for this parent/child pair:

   - Creating a competency taxonomy creates both the parent ``oel_tagging_taxonomy`` row and the ``CompetencyTaxonomy`` row in one transaction.
   - Deleting either representation is treated as deleting the competency taxonomy and removes both rows, subject to Decision 7 delete protections.

2. ``CompetencyCriteriaGroup`` concept (database table)

   Represents an internal boolean-expression node for ``CompetencyAchievementCriteria``.

   A single ``CompetencyAchievementCriteria`` is represented by one root ``CompetencyCriteriaGroup`` plus all descendant groups and leaf ``CompetencyCriterion`` rows.

   Relationship to other concepts:

   - A group belongs to one competency (``oel_tagging_tag_id``) and optional course scope (``course_id``).
   - A group can have child groups.
   - ``logic_operator`` (``AND``/``OR``) defines how children are combined.
   - ``ordering`` defines deterministic sibling evaluation sequence during group recomputation and enables short-circuit evaluation.

   This new database table will have the following columns:

   1. ``id``: unique primary key
   2. ``parent_id``: The ``CompetencyCriteriaGroup.id`` of the parent group. Null means this is a root group.
   3. ``oel_tagging_tag_id``: The ``oel_tagging_tag.id`` for the competency represented by this criteria tree.
   4. ``course_id``: Nullable foreign key to ``openedx_catalog_courserun.id`` for the course that scopes this criteria tree.
   5. ``name``: string
   6. ``ordering``: Indicates evaluation sequence number for this criteria group. This defines deterministic evaluation order for siblings during read-time evaluation and event-driven recomputation, and enables short-circuit evaluation.
   7. ``logic_operator``: Either “AND” or “OR” or null. This determines how children are combined at a group node ("AND" or "OR").

   Example: A root group uses "OR" with two child groups.

   - Child group A (``ordering=1``) requires "AND" across Assignment 1 and Assignment 2.
   - Child group B (``ordering=2``) requires "AND" across Final Exam and Lab Assignment 3.
   - If group A evaluates to true, group B is not evaluated.
   - ``ordering`` complements learner-status materialization: progress is still persisted at leaf/group/root levels, and ``ordering`` only defines child scan order when a parent recomputes after a leaf status change.

   Concrete event example (materialization + ordered recompute):

   - Root group uses ``AND`` with Group A (``ordering=1``) and Group B (``ordering=2``).
   - Group A status is currently ``AttemptedNotDemonstrated``; Group B status is currently ``PartiallyAttempted``; root is ``AttemptedNotDemonstrated``.
   - New event: learner completes one remaining leaf criterion under Group B, so that leaf row changes to ``Demonstrated``.
   - Bottom-up materialization updates Group B first. Group B now becomes ``Demonstrated``.
   - Recompute the root ``AND`` group in ``ordering`` sequence: Group A is evaluated first and is still ``AttemptedNotDemonstrated``, so root is determined immediately and Group B does not need to be checked for root recomputation.
   - Persist changed rows only: the updated leaf row and Group B row. Root remains ``AttemptedNotDemonstrated`` and is not rewritten.

   Boundaries and intended behavior:

   - Empty groups: Persisted criteria definitions should not contain empty groups. Authoring flows may temporarily create empty groups while editing, but backend validation must reject them.
   - Mixed tree depths: Backend supports deeply nested groups. Current frontend authoring constraint is a maximum depth of 3 layers total, using zero-indexed depth (``0=root``, ``1=course-scope group``, ``2=leaf criteria/group``).
   - Retrieval scope: Evaluation/read paths should be windowed by course run dates, not full-history by default. For a requested date window ``[window_start, window_end]``, include (a) all nodes where ``course_id is null``, and (b) complete subtrees for course-scoped groups whose course run overlaps the window (``course_start <= window_end`` and ``course_end >= window_start``, with null ``course_end`` treated as ongoing). Do not return partial subtrees.
   - Practical size and growth: Total rows in ``CompetencyCriteriaGroup`` are expected to grow over time as course runs are added; this ADR sets no global DB row cap. No max total node-count cap is required per root group. For ``course_id is null`` branches, expected size is small (realistically <=500 nodes). Pagination is supported for authoring/list APIs.


3. ``CompetencyRuleProfile`` concept (database table)

   Represents a reusable default rule configuration that can be applied to many ``CompetencyCriterion`` rows.

   Relationship to other concepts:

   - Can be scoped by taxonomy, course, and/or organization.
   - Is referenced by ``CompetencyCriterion``, which may override its type/payload.

   This new database table will have the following columns:

   1. ``id``: unique primary key
   2. ``organization_id``: The ``organization_id`` of the organization that this competency rule profile is scoped to. Null if it is not scoped to a specific organization.
   3. ``course_id``: The ``course_id`` of the course that this competency rule profile is scoped to. Null if it is not scoped to a specific course.
   4. ``competency_taxonomy_id``: The ``CompetencyTaxonomy.taxonomy_ptr_id`` of the competency taxonomy that this competency rule profile is scoped to.
   5. ``rule_type``: “View”, “Grade”, “MasteryLevel” (Only “Grade” will be supported for now)
   6. ``rule_payload``: JSON payload keyed by ``rule_type`` to avoid freeform strings. It is structured JSON (not arbitrary freeform data): each ``rule_type`` defines the allowed payload shape and required keys, and validation enforces this contract. JSON is used instead of fixed columns like ``op``, ``value``, and ``scale`` so that future rule types (for example, ``MasteryLevel`` thresholds or plugin-defined evaluators such as CEL-based rules) can add their own fields without repeated schema migrations or many nullable columns. Examples:

      1. ``Grade``: ``{"op": "gte", "value": 75, "scale": "percent"}``

4. ``CompetencyCriterion`` concept (``CompetencyCriteria`` database table)

   Represents one leaf condition in a ``CompetencyAchievementCriteria`` tree.

   Relationship to other concepts:

   - Belongs to one ``CompetencyCriteriaGroup``.
   - Points to one ``oel_tagging_objecttag`` association.
   - Uses one ``CompetencyRuleProfile`` by default, with optional per-criterion overrides.

   This new database table will have the following columns:

   1. ``id``: unique primary key
   2. ``competency_criteria_group_id``: Foreign key to ``CompetencyCriteriaGroup.id``.
   3. ``oel_tagging_objecttag_id``: Tag/Object Association id
   4. ``competency_rule_profile_id``: Nullable FK to the ``CompetencyRuleProfile`` applied to this criterion. If null, evaluate using fallback lookup order: taxonomy-scoped profile, then course-scoped profile, then organization-scoped profile, then system default.
   5. ``rule_type_override``: Nullable enumerated rule type: “View”, “Grade”, “MasteryLevel” (Only “Grade” will be supported for now). When set, this overrides the ``rule_type`` in the associated ``CompetencyRuleProfile`` for this criterion.
   6. ``rule_payload_override``: Nullable JSON payload keyed by ``rule_type`` to avoid freeform strings. When set, this overrides the ``rule_payload`` in the associated ``CompetencyRuleProfile`` for this criterion. The same typed/validated payload contract as ``rule_payload`` applies. Examples:

      1. ``Grade``: ``{"op": "gte", "value": 75, "scale": "percent"}``

5. Indexes for common lookups

   1. ``CompetencyCriteriaGroup(oel_tagging_tag_id, course_id)``
   2. ``CompetencyCriteriaGroup(parent_id)``
   3. ``oel_tagging_objecttag(object_id)``
   4. ``CompetencyCriteria(oel_tagging_objecttag_id)``
   5. ``CompetencyCriteria(competency_criteria_group_id)``
   6. ``StudentCompetencyCriteriaStatus(user_id, competency_criteria_id)``
   7. ``StudentCompetencyCriteriaGroupStatus(user_id, competency_criteria_group_id)``
   8. ``StudentCompetencyStatus(user_id, oel_tagging_tag_id)``
   9. ``CompetencyRuleProfile(competency_taxonomy_id, course_id, organization_id)``
   10. ``CompetencyMasteryStatuses(status)`` (unique)

6. Learner progress status concepts (``StudentCompetency*Status`` database tables)

   When a completion event (graded, completed, mastered, etc.) occurs for an object, determine and track the learner's status in earning the competency. To reduce recalculation frequency, store results at each level.

   Relationship to other concepts:

   - ``StudentCompetencyCriteriaStatus`` tracks status at ``CompetencyCriterion`` leaf level.
   - ``StudentCompetencyCriteriaGroupStatus`` tracks status at ``CompetencyCriteriaGroup`` node level.
   - ``StudentCompetencyStatus`` tracks top-level competency demonstration state.
   - All learner status rows use a shared lookup table (``CompetencyMasteryStatuses``) so status semantics live in one place and student status tables stay structurally consistent.

   Intended update flow (bottom-up materialization):

   - A learner event updates one ``StudentCompetencyCriteriaStatus`` row.
   - Recompute ancestor ``CompetencyCriteriaGroup`` statuses upward to the root.
   - At each group, evaluate children in ``ordering`` sequence and short-circuit when the group's result is already determined by its ``logic_operator``.
   - Persist only rows whose status changed.

   1. Add new database table for ``CompetencyMasteryStatuses`` with these columns:

      1. ``id``: unique primary key
      2. ``status``: unique status value (seeded values: “Demonstrated”, “AttemptedNotDemonstrated”, and “PartiallyAttempted”)

      Notes:

      - This table is system-owned lookup data and should be treated as immutable configuration, not user-authored rows.

   2. Add new database table for ``StudentCompetencyCriteriaStatus`` with these columns:

      1. ``id``: unique primary key
      2. ``competency_criteria_id``: Foreign key to ``CompetencyCriterion.id``
      3. ``user_id``: Foreign key pointing to user_id (presumably the learner's id, although it appears that it is possible for staff to get grades as well) in ``auth_user`` table
      4. ``status_id``: Foreign key to ``CompetencyMasteryStatuses.id``
      5. ``created``: The timestamp at which the student's criterion status was set.

   3. Add a new database table for ``StudentCompetencyCriteriaGroupStatus`` with these columns:

      1. ``id``: unique primary key
      2. ``competency_criteria_group_id``: Foreign key to ``CompetencyCriteriaGroup.id``
      3. ``user_id``: Foreign key pointing to user_id (presumably the learner's id, although it appears that it is possible for staff to get grades as well) in ``auth_user`` table
      4. ``status_id``: Foreign key to ``CompetencyMasteryStatuses.id``
      5. ``created``: The timestamp at which the student's criteria-group status was set.

   4. Add a new database table for ``StudentCompetencyStatus`` with these columns:

      1. ``id``: unique primary key
      2. ``oel_tagging_tag_id``: Foreign key pointing to Tag id
      3. ``user_id``: Foreign key pointing to user_id (presumably the learner's id, although it appears that it is possible for staff to get grades as well) in ``auth_user`` table
      4. ``status_id``: Foreign key to ``CompetencyMasteryStatuses.id``. This table should have a constraint to only allow status values of “Demonstrated” and “PartiallyAttempted” since it represents overall competency demonstration state, not in-progress states.
      5. ``created``: The timestamp at which the student's competency status was set.

7. Delete protection boundaries

   - If no learner status rows exist for a competency definition, hard delete is allowed and cascades through competency metadata tables.
   - Once any related learner status exists in ``StudentCompetencyStatus``, ``StudentCompetencyCriteriaGroupStatus``, or ``StudentCompetencyCriteriaStatus``, deletion of associated competency definition rows is blocked.
   - This delete protection applies to ``oel_tagging_taxonomy``, ``CompetencyTaxonomy``, ``oel_tagging_tag``, ``oel_tagging_objecttag``, ``CompetencyCriteriaGroup``, ``CompetencyCriteria``, and ``CompetencyRuleProfile``.
   - Once any related learner status exists, retiring definitions may be archive-only (hidden from authoring and new associations), not hard delete.

.. image:: images/CompetencyCriteriaModel.png
   :alt: Competency Criteria Model
   :width: 80%
   :align: center


Example
-------
The following example illustrates how the decision model supports both defaults and overrides without requiring authors to specify every rule by hand.

Competency: "Writing Poetry" (a competency taxonomy tag)

Course: "Course X"

Content objects:

- Assignment 7: "Submit a Poem"
- Assignment 9: "Remix a Poem"

1. ``oel_tagging_objecttag``:

   - Assignment 7 tagged with "Writing Poetry"
   - Assignment 9 tagged with "Writing Poetry"

2. ``CompetencyRuleProfile``:

   - Course-scoped default: ``Grade >= 75%`` for this competency taxonomy

3. ``CompetencyCriteriaGroup``:

   - Root group uses ``OR``
   - Group A (``ordering=1``) uses ``AND``
   - Group B (``ordering=2``) uses ``AND``

4. ``CompetencyCriteria``:

   - Group A + Assignment 7 (uses default rule profile)
   - Group A + Assignment 9 (override to ``Grade >= 85%``)
   - Group B + Assignment 7 (uses default rule profile)
   - Group B + Assignment 9 (uses default rule profile)

This allows authors to set a single default rule for most tagged content, and only override where needed. It also lets the same tag/object association participate in multiple criteria groups without duplicating tagging rows.


Rejected Alternatives
---------------------
1. Update ``oel_tagging_taxonomy`` to have a new column for ``taxonomy_type`` where the value could be “Competency” or “Tag”.

   1. Pros
   
      1. Simpler model with fewer tables
      2. Reuses existing taxonomy table and keeps reads straightforward when checking taxonomy usage
      3. Avoids introducing an additional join for queries that only need to know whether a taxonomy is competency-enabled
   2. Cons
   
      1. Couples CBE concerns directly into the generic tagging domain model, reducing separation of concerns
      2. Makes ``oel_tagging_taxonomy`` less generic and encourages enum/flag growth as new specialized usages are added
      3. Prevents strong foreign key guarantees for CBE tables, since they can only point to ``oel_tagging_taxonomy`` and not specifically to competency-enabled taxonomies
      4. Makes it harder to keep competency features optional for deployments that only want generic tagging
      5. Increases risk of future refactor/migration work if the competency domain later needs to be split from tagging

2. Same as above except combine the ``CompetencyCriteria`` and ``oel_tagging_objecttag`` tables by adding the rule information as columns on the ``oel_tagging_objecttag`` table. This would be a more denormalized approach that would reduce the number of joins needed to retrieve competency achievement criteria information but would add complexity to the ``oel_tagging_objecttag`` table and make it less flexible for other uses.

   1. Pros

      1. Reduces number of joins needed to retrieve competency achievement criteria information
      2. Single-row lookup per object tag when the competency criteria is a 1:1 mapping to a tag/object association
      3. Potentially simpler UI/API if all consumers already pivot around ``objecttag`` and do not need criteria grouping
   2. Cons

      1. Dilutes semantics as ``objecttag`` stops being a pure generic tagging junction.
      2. Many nullable columns. Most tags won't be criteria; you'll add mostly-null fields unless they're scoped with a type discriminator and partial indexes.
      3. It becomes easy to create criteria rows missing required fields (rule profile, overrides) unless enforced with a discriminator and additional constraints.
      4. It breaks or complicates criteria grouping because a single ``objecttag`` may need to participate in multiple criteria groups. You would need to duplicate ``objecttag`` rows or add another join table, which defeats the intended simplification.
      5. Down the road, permissioning differences in who can create/edit criteria vs who can create/edit generic tags would be harder to implement and audit.
      6. Performance risk if the objecttag table becomes very large and is queried for both generic tagging and competency criteria use cases with mostly-null criteria fields.
      7. Future rule types may require different fields, further bloating ``objecttag`` and reducing performance for non-competency use cases.

3. Add a generic oel\_tagging\_objecttag\_metadata table to attempt to assist with pluggable metadata concept. This table would have foreign keys to each metadata table, currently only competency\_criteria\_group and competency\_criteria as well as a type field to indicate what metadata table is being pointed to.  

   1. Pros

      1. Centrally organizes metadata associations in one place
   2. Cons

      1. Adds additional overhead to retrieve specific metadata

4. Split rule storage into per-type tables (for example, ``competency_criteria_grade_rule`` and ``competency_criteria_mastery_rule``) instead of a single JSON payload.  

   1. Pros

      1. Provides stricter schemas and validation per rule type
   2. Cons

      1. Increases table count and join complexity as new rule types are added
