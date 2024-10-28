17. Modeling Containers as a Generalized Capability for Holding Content
========================================================================

Context
-------

WIP

Decisions
---------

1. Core Structure and Purpose of Containers
===========================================

- A container is designed as a generalized capability to hold different types of content.
- A container is a publishable content type that holds other content types through a parent-child relationship.
- A container application will offer shared definitions for use by other container types.

2. Container Types and Content Constraints
==========================================

- A container marks any PublishableEntity, such as sections, subsections, units, or any other custom content type, as a type that can hold other content.
- Containers might be of different types, with each type potentially having different restrictions on the type of content it can hold but that will not be enforced by containers.
- Content restrictions for containers are implemented at the app layer, allowing specific container types, like Unit, to limit their members to particular content types (e.g., only Components).
- The course hierarchy Course > Section > Subsection > Unit will be implemented as relationships between containers, with each level acting as a container that holds other content. The hierarchy will be enforced by the content restrictions of each particular container.
- Containers will follow extensibility principles in `0003-content-extensibility.rst` for creating new container types or subtypes, static or dynamic.

1. Container Members and Relationships
=======================================

- The members of a container can be any type of publishable content.
- A container holds references to generic data structures for defining parent-child relationships between a container and its members. These structures point to either static or dynamically generated content to allow associations for different types of content within the container.
- Members are stored as a list of references to the content they hold to maintain ordering.
- Each container holds different states of its members (e.g., user-defined state, initial state, last state) to support rollback operations.
- Containers maintain a defined order for their members. When ordering needs to change, a new copy of the child should be created.
- Each child can be fixed to a particular version or set to point to the latest version for draft and published states. Draft or published states can be referenced without creating new instances for each version update by using the convention of setting the reference to `None`.
- If the child's draft or published version is pinned, then each time versions are updated, a new child with the new reference must be created.

1. Container Versioning Management
==================================

- The container itself is versioned, and a new version is created if and only if the container itself changes (e.g., title, ordering of contents, adding or removing content) and not when its content changes (e.g., a component in a Unit is updated with new text).

1. Publishing
=============

WIP

1. Pruning
==========

WIP

Consequences
------------

WIP
