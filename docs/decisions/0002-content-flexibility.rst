2. Approach to Content Flexibility
==================================

Context
-------

Open edX courses follow a strict Course > Section > Subsection > Unit > Module hierarchy. There are a number of use cases that do not fit this pattern:

* A problem bank shared via LTI, with individual problems for use in other LMS systems.
* Short courses that do not require the "Section" middle layer of hierarchy.
* Standalone assessments given after an informational session.
* LabXchange-style pathways and clusters.

The Learning Core should have a set of composable primitives that could be configured to construct these sorts of experiences, while still maintaining the ability to support the traditional Open edX course format.

Decision
--------

The following are foundational, extensible concepts in the Learning Core, which can be combined in different ways:

Component
  A Component is a small piece of content, like a video, problem, or bit of HTML text. It has an identity, renderer, and potentially student state. It is not a container for other content, and has no child elements.

Unit
  A Unit is an ordered list of one or more Components that is typically displayed together. A common use case might be to display some introductory Text, a Video, and some followup Problem (all separate Components). An individual Component in a Unit may or may not make sense when taken outside of that Unit–e.g. a Video may be reusable elsewhere, but the Problem referencing the video might not be.

Sequence
  A Sequence is a collection of Units that are presented one after the other, either to assess student understanding or to achieve some learning objective. 

  A Sequence is analogous to a Subsection in a traditional Open edX course.

Navigation
  Navigation is the higher-level organization of a course or other learning context. For a traditional course, this would be what determines the Sections and what Sequences are in each. A more advanced Navigation type might dynamically select Sequences that are appropriate for you based on your understanding of the material.

There are two goals:

#. Each of these concepts should be *extensible*, so that new types of Items, Units, etc. are created (the specifics of this would be in a follow-on ADR).
#. We should be able to use these in different combinations. For instance, a short course may have a different Navigation type than traditional courses (e.g. by removing a level of hierarchy), but that Navigation would then still point to Sequences, which point to Units, etc. The base types described in this document provide a lowest-common denominator interface to decouple the layers from each other, so that an extended Navigation type doesn't have to be aware of the various extended Sequence types, but can just know that is pointing to some sort of Sequence.

Consequences
------------

This is aligned with the ADR on the `Role of XBlock <https://github.com/openedx/edx-platform/blob/master/docs/decisions/0006-role-of-xblock.rst>`_, which envisions XBlocks as leaf nodes of instructional content like Videos and Problems, and not as container structures like Units or Sequences.

To realize the benefits of this system would require significant changes to Studio and especially the LMS. In particular, this would involve gradually removing the XBlock runtime from much of the courseware logic. This would allow for substantial simplifications of the LMS XBlock runtime itself, such as removing field inheritance.

Changelog
---------

2023-02-06:

* Renamed "Item" to "Component" to be consistent with user-facing Studio terminology.
* Collapsed the role of Segment into Unit simplify the data model.
