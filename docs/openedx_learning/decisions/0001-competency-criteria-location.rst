.. _openedx-learning-adr-0001:

1. Where in the codebase should CBE competency criteria go?
============================================================

Context
-------
Competency Based Education (CBE) requires that the LMS have the ability to track learners' mastery of competencies through the means of competency criteria. For example, in order to demonstrate that I have mastered the Multiplication competency, I need to have earned 75% or higher on Assignment 1 or Assignment 2\. The association of the competency, the threshold, the assignments, and the logical OR operator together make up the competency criteria for the competency. Course Authors and Platform Administrators need a way to set up these associations in Studio so that their outcomes can be calculated as learners complete their materials. This is an important prerequisite for being able to display competency progress dashboards to learners and staff to make Open edX the platform of choice for those using the CBE model.

Decisions
---------
CBE Competency Criteria, Student Competency Criteria Status, and Student Competency Status values should go in the openedx-core repository as there are broader architectural goals to refactor as much code as possible out of the openedx-platform repository into the openedx-core repository such that it can be designed in a way that is easy for plugin developers to utilize. Additionally, we intend to treat CBE features as core features of Open edX rather than optional plugins, and as a result, CBE competency criteria and learner status should live in the learning core rather than in a separate new repo.

Given the current refactor of openedx-core (see :ref:`openedx-content-adr-0010`), we will place CBE code inside a new top-level ``openedx_learning`` app as an applet, alongside Learning Pathways. The intended layout is:

::

    src/
         openedx_catalog/
         openedx_content/
         openedx_learning/
             applets/
                 cbe/
                 learning_pathways/
         openedx_tagging/

The umbrella ``src/openedx_learning`` app will aggregate its applets into a single Django app and Python API, similar to the internal structure of ``src/openedx_content`` today.

This placement will keep CBE close to shared learning-domain concepts like ``learning_pathways``.

Rejected Alternatives
---------------------
1. Put all CBE competency criteria and learner status in a single ``openedx-core`` app under ``src/openedx_competency_criteria``
    - Pros:
        - Keeps a single cohesive Django app for authoring criteria and storing learner status, reducing cross-app dependencies and simplifying migrations and APIs.
    - Cons:
        - Does not align with the applet-based top-level structure (``src/openedx_learning/applets/...``).
2. openedx-platform repository
    - Pros: This is where all data currently associated with students is stored, so it would match the existing pattern and reduce integration work for the LMS.
    - Cons: The intention is to move core learning concepts out of openedx-platform (see :ref:`openedx-core-adr-0001`), and keeping it there makes reuse and pluggability harder.
3. All code related to adding Competency Criteria to Open edX goes in ``src/openedx_content/applets/competency_criteria``
    - Pros:
        - Tagging and competency criteria are part of content authoring workflows as is all of the other code in this directory.
        - All other elements using the Publishable Framework are in this directory.
    - Cons:
        - We want each package of code to be independent, and this would separate competency criteria from the tags that they are dependent on.
        - Competency criteria also includes learner status and runtime evaluation, which do not fit cleanly in the authoring app.
        - The learner status models in this feature would have a ForeignKey to settings.AUTH_USER_MODEL, which is a runtime/learner concern. If those models lived under the authoring app, then the authoring app would have to import and depend on the user model, forcing an authoring-only package to carry learner/runtime dependencies. This may create unwanted coupling.
4. New Competency Criteria Content tables will go in ``src/openedx_tagging/competency_criteria``. New Student Status tables will go in ``src/openedx_student_status``.
    - Pros:
        - Keeps competency criteria in the same package as the tags that they are dependent on.
    - Cons:
        - ``src/openedx_tagging`` is intended to be a standalone library without Open edX-specific dependencies (see :ref:`openedx-tagging-adr-0002`) competency criteria would violate that boundary.
        - Splitting Competency Criteria and Student Statuses into two apps would require cross-app foreign keys (e.g., status rows pointing at criteria/tag rows in another app), migration ordering and dependency declarations to ensure tables exist in the right order, and shared business logic or APIs for computing/updating status that now must live in one app but reference models in the other.
5. Split competency criteria and learner statuses into two apps inside ``src`` (e.g., ``src/openedx_competency_criteria`` and ``src/openedx_learner_status``)
    - Pros:
        - Clear separation between authoring configuration and computed learner state.
        - Could allow different storage or scaling strategies for status data.
    - Cons:
        - Still introduces cross-app dependency and coordination for a single feature set.
        - May be premature for the POC; adds overhead without proven need.
6. Store learner status in a separate service
    - Pros:
        - Scales independently and avoids write-heavy tables in the core app database.
        - Could potentially reuse existing infrastructure for grades.
    - Cons:
        - Introduces eventual consistency and more integration complexity for LMS/Studio views.
        - Requires additional infrastructure and operational ownership.
7. Split authoring and runtime into separate repos/packages
    - Pros:
        - Clear ownership boundaries and independent release cycles.
    - Cons:
        - Adds packaging and versioning overhead for a tightly coupled domain.
        - Increases coordination cost for migrations and API changes.
8. Migrate grading signals to openedx-events now and have openedx-core consume events directly
    - Pros:
        - Aligns with the long-term direction of moving events out of edx-platform.
        - Avoids a shim app in edx-platform and reduces tech debt.
    - Cons:
        - Requires cross-repo coordination and work beyond the current scope.
        - Depends on changes to openedx-events that are not yet scheduled or ready.
