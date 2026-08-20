.. _openedx-learning-adr-0006:

6. Pathways: Mapping Pathway Items to the Things That Fulfill Them
==================================================================

Status
------

Draft

Context
-------

:ref:`openedx-learning-adr-0005` establishes that a Pathway Item is a stable requirement whose fulfillment can change
over time. This ADR describes how we intend to map Items to the things that fulfill them, starting with the only
fulfillment type in the first release: passing a course.

The exact data model here will likely need adjustment; we expect to modify it in an actual code PR.
Development does not gate on this ADR - it captures intent and boundaries, not field-level models.

Decisions
---------

1. In the MVP, a Pathway Item is fulfilled by passing a course run:

   - Each Item holds an **author-defined list of course runs** that fulfill it. Passing *any one* of them fulfills
     the Item. The runs may belong to different catalog courses.
   - The list is explicit rather than "any run of this catalog course", because we don't necessarily want to give
     credit for every possible older version of a course.
   - "Passing" is determined by each course's own grading policy. The grade and passed/failed state are read directly
     from the course; Pathways define no grading of their own.
   - Each Item designates a **default course run** - the one a learner is enrolled in when they begin the Item - and,
     if that course uses multiple enrollment tracks, the track to enroll them in. The default can change over time.

2. Fulfillment types attach at this layer only. Potential future types - section completion, competency attainment,
   admin override - plug in as alternative ways to fulfill an Item, without touching Item identity, Pathway structure,
   or Pathway completion criteria.

3. Edge cases are resolved at this layer and never leak upward. For example: multiple passed runs fulfilling the same
   Item (the Item is simply fulfilled), or one passed run fulfilling several Items simultaneously (each Item is
   fulfilled independently).

4. Prior work counts. If a learner passed a course before enrolling in a Pathway that contains it, that pass fulfills
   the corresponding Item - fulfillment is evaluated against the learner's record, not against activity that happened
   "inside" the Pathway.

.. Run `dot -Tsvg images/pathway-item-fulfillment.dot > images/pathway-item-fulfillment.svg` to regenerate the
   diagram after making changes to `images/pathway-item-fulfillment.dot`.

.. image:: images/pathway-item-fulfillment.svg
   :alt: Pathway Item fulfillment mapping
   :width: 100%

Consequences
------------

- Authors control exactly which runs count, at the cost of manually updating the list when new runs are created.
- Because passing state comes directly from course grading, there is no Pathway-side duplication of grades to keep in
  sync.
- The fulfillment mapping is the natural extension point for everything post-MVP, and the part of the model we
  expect to iterate on in code.
