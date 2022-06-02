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

Item
  An Item is a small piece of content, like a video, problem, or bit of HTML text. It has an identity, renderer, and potentially student state. It is not a container for other content, and has no child elements.
  
  Items are analogous to the "Module" portion of the traditional Open edX course.

Segment
  A Segment is an ordered list of Items that must be presented to the user together. The Items inside a Segment may be of different types, but it does not make sense to show one of these Items in isolation. An example could be one Item that explains a problem scenario, along with a problem Item that asks a question about it–a common scenario in content libraries. By default, each Item is its own Segment.

  Open edX currently models these as nested Verticals (a.k.a. Units), but this often causes problems for code that traverses the content without realizing that such a nesting is possible.

Unit
  This is a list of one or more Segments that is displayed to the user on one page. A Unit may be stitched together using content that comes from multiple sources, such as content libraries. Units do not have to be strictly instructional content, as things like upgrade offers and error messages may also be injected.

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
