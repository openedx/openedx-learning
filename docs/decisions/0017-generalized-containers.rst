Modeling Containers as a Generalized Capability for Holding Content
=======================================================================

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
- Containers might be of different types, with each type potentially having different restrictions on the type of content it can hold but are not enforced by containers.
- Content restrictions for containers are implemented at the app layer, allowing specific container types, like Unit, to limit their children to particular content types (e.g., only Components).
- The course hierarchy Course > Section > Subsection > Unit will be implemented as relationships between containers, with each level acting as a container that holds other content. The hierarchy will be enforced by the content restrictions of each particular container.
- This hierarchy will not rely on the XBlock mechanism but will still be capable of supporting XBlock content types (e.g., by holding Components).
- Containers will follow extensibility principles in `0003-content-extensibility.rst` for creating new container types or subtypes, static or dynamic.

3. Container Members and Relationships
======================================

- Members of a container can be any type of publishable content.
- A generic model will define the parent-child relationships between containers and PublishableEntities to support both static and dynamic content using the same structure.
- Each container version maintains a structured reference to different states of its members (e.g., user-defined state, initial state, last state), enabling efficient access to historical states and supporting reverts and draft states.
- Containers maintain a defined order for their members. When ordering needs to change, a new copy of the member should be created.
- Members can be fixed to a particular version or set to point to the latest version for draft and published states.
	- If the published version changes from V0 to V1 and there is an EntityListRow pointing to that version, a new instance will need to be created to reference the new version. To avoid creating new instances when always referencing the latest version, pointers to the draft/published states can be set to `None`, which reduces redundant data storage.
	- If the version is pinned, then each time versions are updated, a new member with the new reference must be created.

4. Versioning Management
========================

- A new version of the container is created if and only if the container itself changes (e.g., title, ordering of contents, adding or removing content) and not when its content changes (e.g., a component in a Unit is updated with new text).

5. Publishing
=============

WIP

6. Pruning
==========

WIP
