17. Modeling Containers as a Generalized Capability for Holding Content
========================================================================

Context
-------

This ADR proposes a model for containers that can hold different types of content and can be used to model other content types with similar behavior, such as units, subsections, sections, or courses. The model defines containers' core structure and purpose, the types of containers, content constraints, container members, version control, publishing, and pruning.

Decisions
---------

1. Core Structure and Purpose of Containers
===========================================

This section defines the purpose and structure of containers, explaining how they are designed to hold various types of content through a parent-child setup.

- A container is designed as a generalized capability to hold different types of content.
- A container is a publishable content type that holds other content types through a parent-child relationship.
- A container application will offer shared definitions for use by other container types.

2. Container Types and Content Constraints
==========================================

This section defines container types, content constraints, hierarchy, and extensibility. It introduces the main types of containers and outlines how content limitations and configurations are handled at the application level to support flexible content structures.

- A container marks any PublishableEntity, such as sections, subsections, units, or any other custom content type, as a type that can hold other content.
- Containers can be nested within other containers, allowing for complex content structures.
- Containers might be of different types, with each type potentially having different restrictions on the type of content it can hold but that will not be enforced by containers.
- Content restrictions for containers are implemented at the app layer, allowing specific container types, like Unit, to limit their members to particular content types (e.g., only Components).
- The course hierarchy Course > Section > Subsection > Unit will be implemented as relationships between containers, with each level acting as a container that holds other content. The hierarchy will be enforced by the content restrictions of each particular container but allowed to be overridden to support `0002-content-flexibility.rst`_.
- Containers will follow extensibility principles in `0003-content-extensibility.rst`_ for creating new container types or subtypes.

3. Container Members and Relationships
=======================================

This section defines container members, their order, and relationships, covering flexible connections and support for draft and published states of their members.

- The members of a container can be any type of publishable content.
- Members within a container are maintained in a specific order as an ordered list.
- Containers represent their content hierarchy through a structure that defines parent-child relationships between the container and its members.
- The structure defining these relationships is anonymous, so it can only be referenced through the container.
- Containers can hold both static and dynamically generated content, such as user-specific variations.
- Containers support both fixed and version-agnostic references for members, allowing members to be pinned to a specific version or set to reference the latest draft or published state.
- The latest draft or published states can be referenced by setting the version to ``None``, avoiding the need for new instances on each update.
- A single member (publishable entity) can be referenced by multiple containers, allowing for reuse of content across different containers.

4. Container Lists and Rollback Operations
==========================================

This section defines the various lists of container's members (author-defined, initial, and frozen) and explains how these lists are preserved to support rollback operations.

- Each container holds different states of its members (author-defined, initial, and frozen final) to support rollback operations.
- The author-defined list of a container is the list of members that the author has defined for the version of the container.
- The author-defined list won't change for a container version even if its references get soft-deleted.
- The initial list of a container is the list of members the container when it was first created.
- The initial list of a container is immutable.
- All references in the initial list of a container are pinned to the version of the member at the time of the container's creation.
- The frozen list of a container is the list of members of the container at the time when a new version is created.

5. Version Control
==================================

This section defines the rules for version control in containers, explaining when new versions are created based on changes to container structure, metadata, or member states.

- A new version is created if and only if the container itself changes (e.g., title, ordering of contents, adding or removing content) and not when its content changes (e.g., a component in a Unit is updated with new text).
- Changes to the order of members within a container require creating a new version of the container with the new ordering.
- Each time a new version is created because of metadata changed, its members are copied from the previous version to preserve the state of the content at that time.
- Changes in pinned published or draft states require creating a new version of the container to maintain the state of the content for the previous version.
- When using version-agnostic references to members, no new version is created when members change since the latest draft or published state is always used.
- If a member is soft-deleted, the container will create a new version with the member removed.

6. Publishing
=============

This section explains the publishing process for containers, detailing how containers and their members become accessible, either together or independently, based on their publication state.

- Containers can be published, allowing their content to be accessible from where the container is referenced.
- When a draft container is published, all its draft members are also published.
- Members of a container can be published independently of the container itself.
- If a member of a container is published independently, then it'd be published in the context of the container where it is referenced.

7. Pruning
==========

WIP


.. _0002-content-flexibility.rst: docs/decisions/0002-content-extensibility.rst
.. _0003-content-extensibility.rst: docs/decisions/0003-content-extensibility.rst
