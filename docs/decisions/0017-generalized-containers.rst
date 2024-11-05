17. Modeling Containers as a Generalized Capability for Holding Content
========================================================================

Context
-------

This ADR proposes a model for containers that can hold different types of content and can be used to model other content types with similar behavior, such as units, subsections, sections, or courses. The model defines containers' core structure and purpose, the types of containers, content constraints, container members, version control, publishing, and pruning.

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
- Containers can be nested within other containers, allowing for complex content structures.
- Containers might be of different types, with each type potentially having different restrictions on the type of content it can hold but that will not be enforced by containers.
- Content restrictions for containers are implemented at the app layer, allowing specific container types, like Unit, to limit their members to particular content types (e.g., only Components).
- The course hierarchy Course > Section > Subsection > Unit will be implemented as relationships between containers, with each level acting as a container that holds other content. The hierarchy will be enforced by the content restrictions of each particular container but allowed to be overridden to support `0002-content-flexibility.rst`_.
- Containers will follow extensibility principles in `0003-content-extensibility.rst`_ for creating new container types or subtypes.

3. Container Members and Relationships
=======================================

- The members of a container can be any type of publishable content.
- Members within a container are maintained in a specific order as an ordered list.
- Containers represent their content hierarchy through a structure that defines parent-child relationships between the container and its members.
- The structure defining these relationships is anonymous, so it can only be referenced through the container.
- Containers can hold both static and dynamically generated content, including user-specific variations.
- Each container holds different states of its members (user-defined, initial, and frozen final state) to support rollback operations.
- Members can be added or removed from a container, and the container will maintain the state of the content for the previous version (frozen final state).
- The initial state of a container is immutable.
- When a container's structure changes, e.g., when a new member is added, the user-defined state of the container is updated with the new members list.
- Containers support both fixed and version-agnostic references for members, allowing members to be pinned to a specific version or set to reference the latest draft or published state.
- The latest draft or published states can be referenced by setting the version to ``None``, avoiding the need for new instances on each update.
- A single member (publishable entity) can be referenced by multiple containers, allowing for reuse of content across different containers.

4. Version Control
==================================

- A new version is created if and only if the container itself changes (e.g., title, ordering of contents, adding or removing content) and not when its content changes (e.g., a component in a Unit is updated with new text).
- Changes to the order of members within a container require creating a new version of the container with the new ordering.
- Changes in pinned published or draft states require creating a new version of the container to maintain the state of the content for the previous version.
- Each time a new version is created because of metadata changed, its members are copied from the previous version to preserve the state of the content at that time.
- When using version-agnostic references, no new version is created when the content changes, and the reference is updated to the latest draft or published state.
- If a member is soft-deleted, the container will create a new version with the member removed.

5. Publishing
=============

- Containers can be published, allowing their content to be accessible from where the container is referenced.
- When a draft container is published, all its draft members are also published.
- Members of a container can be published independently of the container itself.
- If a member of a container is published independently, then it'd be published in the context of the container where it is referenced.

1. Pruning
==========

WIP


.. _0002-content-flexibility.rst: docs/decisions/0002-content-extensibility.rst
.. _0003-content-extensibility.rst: docs/decisions/0003-content-extensibility.rst
