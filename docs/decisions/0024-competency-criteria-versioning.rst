24. How should versioning be handled for CBE competency achievement criteria?
=============================================================================

Context
-------
Course Authors and/or Platform Administrators will be entering the competency achievement criteria rules in Studio that learners are required to meet in order to demonstrate competencies. Depending on the institution, these Course Authors or Platform Administrators may have a variety of job titles, including Instructional Designer, Curriculum Designer, Instructor, LMS Administrator, Faculty, or other Staff. 

Typically, only one person would be responsible for entering competency achievement criteria rules in Studio for each course, though this person may change over time. However, entire programs could have many different Course Authors or Platform Administrators with this responsibility. 

Typically, institutions and instructional designers do not change the mastery requirements (competency achievement criteria) for their competencies frequently over time. However, the ability to do historical audit logging of changes within Studio can be a valuable feature to those who have mistakenly made changes and want to revert or those who want to experiment with new approaches.

Currently, Open edX always displays the latest edited version of content in the Studio UI and always shows the latest published version of content in the LMS UI, despite having more robust version tracking on the backend (Publishable Entities).

Authoring data (criteria definitions) and runtime learner data (status) have different governance needs. The former is long-lived and typically non-PII, while the latter is user-specific, can be large (learners x criteria/competencies x time), and may require stricter retention and access controls. These differing lifecycles can make deep coupling of authoring and runtime data harder to manage at scale. Performance is also a consideration as computing or resolving versioned criteria for large courses could add overhead in Studio authoring screens or LMS views.

Decision
--------
For the initial implementation, versioning and traceability of competency achievement criteria will be handled with a combination of model history and lifecycle guardrails:

1. Apply ``django-simple-history`` to competency criteria definition moodels/tables:

   - ``CompetencyCriteriaGroup``
   - ``CompetencyCriteria``
   - ``CompetencyRuleProfile``

   This provides historical row snapshots and audit metadata for authored criteria definitions, without adopting the full publishable framework for this phase.

2. Do not apply ``django-simple-history`` to ``oel_tagging_tag``, ``oel_tagging_taxonomy``, or ``CompetencyTaxonomy`` in this phase.

   These models are treated as non-evaluative display/metadata for competency criteria purposes; edits to names or metadata in these tables are not intended to change evaluation outcomes.

3. ``oel_tagging_objecttag`` associations used by competency criteria follow post-use archive rules:

   - Before any related learner status exists, edits and deletes are allowed.
   - After any related learner status exists, disassociation/deletion is archive-only (soft delete), not hard delete.
   - Archived rows remain queryable so learner status records can continue to be traced back to their source association.

4. Authoring guardrails must warn on potentially impactful edits:

   - If a user edits competency criteria definitions or competency object/tag associations after related learner status exists, Studio must display an explicit warning that student statuses have already been set, and these changes will be applied going forward, so existing learner statuses will not be retroactively updated.
   - Applying these changes requires explicit user confirmation.

5. Learner status models/tables are append-only history and do not use ``django-simple-history``:

   - For ``StudentCompetencyCriteriaStatus``, ``StudentCompetencyCriteriaGroupStatus``, and ``StudentCompetencyStatus``, each status change is stored as a new row with ``created`` as the write timestamp.
   - Existing learner status rows are not updated in place.
   - Current status is determined by the most recent row for a given learner + target entity (ordered by ``created``, with ``id`` as a tie-breaker).
   - Older rows represent the learner status history and remain available for audit/tracing.


Rejected Alternatives
---------------------

1. Defer competency achievement criteria versioning for the initial implementation. Store only the latest authored criteria and expose the latest published state in the LMS, consistent with current Studio/LMS behavior. 
    - Pros: 
        - Keeps the initial implementation lightweight
    - Cons:
        - There is no built-in rollback or audit history
        - Adding versioning later will require data migration and careful choices about draft vs published defaults
2. Each model indicates version, status, and audit fields
    - Pros:   
        - Simple and familiar pattern (version + status + created/updated metadata)  
        - Straightforward queries for the current published state  
        - Can support rollback by marking an earlier version as published  
        - Stable identifiers (original_ids) can anchor versions and ease potential future migrations  
    - Cons:  
        - Requires custom conventions for versioning across related tables and nested groups  
        - Lacks shared draft/publish APIs and immutable version objects that other authoring apps can reuse  
        - Not necessarily consistent with existing patterns in the codebase (though these are already not overly consistent).   
3. Publishable framework in openedx-learning  
    - Pros:  
        - First-class draft/published semantics with immutable historical versions  
        - Consistent APIs and patterns shared across other authoring apps  
    - Cons:  
        - Requires modeling criteria/groups as publishable entities and wiring Studio/LMS workflows to versioning APIs
        - Adds schema and migration complexity for a feature that does not yet require full versioning
4. Append-only audit log table (event history)  
    - Pros:  
        - Lightweight way to capture who changed what and when  
        - Enables basic rollback by replaying or reversing events  
    - Cons:  
        - Requires custom tooling to reconstruct past versions  
        - Does not align with existing publishable versioning patterns
