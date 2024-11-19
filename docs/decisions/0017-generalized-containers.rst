17. Modeling Containers as a Generalized Capability for Holding Content
========================================================================

Context
-------

This ADR proposes a model for containers that can hold different types of content and can be used to model other content types with similar behavior, such as units, subsections, sections, or courses. The model defines containers' core structure and purpose, the types of containers, content constraints, container members, version control, publishing, and pruning.

Decisions
---------

#. Core Structure and Purpose of Containers
===========================================

This section defines the purpose and structure of containers, explaining how they are designed to hold various types of content through a parent-child setup.

- A container is designed as a generalized capability to hold different types of content.
- A container is a publishable content type that holds other content types through a parent-child relationship.
- The generalized container capability will have its own Django application where other types of containers and content types will build on top of. For instance:

  - Generalized containers (containers app is lowest level of these applications)
  - Selectors for dynamically selecting 0-N PublishableEntities, i.e. how we're going to do things like SplitTest and Randomized (selectors application, builds on containers).
  - Units (units app, builds on containers and selectors).

#. Container Types and Content Constraints
==========================================

This section defines container types, content constraints, hierarchy, and extensibility. It introduces the main types of containers and outlines how content limitations and configurations are handled at the application level to support flexible content structures.

- A container marks any PublishableEntity, such as sections, subsections, units, or any other custom content type, as a type that can hold other content.
- Containers can be nested within other containers, allowing for complex content structures.
- Containers might be of different types, with each type potentially having different restrictions on the type of content it can hold but that will not be enforced by containers.
- Content restrictions for containers are implemented at the app layer, allowing specific container types, like Unit, to limit their members to particular content types (e.g., only Components).
- The course hierarchy Course > Section > Subsection > Unit will be implemented as relationships between containers, with each level acting as a container that holds other content. The hierarchy will be enforced by the content restrictions of each particular container but allowed to be overridden to support `0002-content-flexibility.rst`_.
- Containers will follow extensibility principles in `0003-content-extensibility.rst`_ for creating new container types or subtypes.

#. Container Members and Relationships
=======================================

This section defines container members, their order, and relationships, covering flexible connections and support for draft and published states of their members.

- The members of a container can be any type of publishable content.
- Members within a container are maintained in a specific order as an ordered list.
- Containers represent their content hierarchy through a structure that defines parent-child relationships between the container and its members.
- Containers support both pinned and unpinned references for its members, allowing members to be pinned to a specific version or set to reference a particular version.
- The latest draft or published state of a member can be referenced by setting the version to ``None``.
- A single member (publishable entity) can be shared by multiple containers, allowing for reuse of content across different containers.

#. Container Version History
============================

This section defines the various lists of container's versions (author-defined, initial, and frozen) used  to track the history of changes made to a container, allowing to view past versions and changes over time.

- Each container version holds different lists of members (author-defined, initial, and frozen) to support rollback operations and history tracking for the container.
- The author-defined list is the list of members that the author has defined for the version of the container.
- The author-defined list won't change for a specific container version even if its references get soft-deleted.
- The initial list is a copy of the author-defined list that has all versions pinned as they were at the time the container version was created.
- The initial list is immutable for a container version.
- The frozen list refers to the list of members at the time when the next version of the container is created.
- The author-defined list is used to show the content of a container version as the author specified it, the frozen list can be used for discard operations on a draft version and the initial-list is part of the history of evolution of the container.

#. Next Container Versions
==================================

This section defines the rules for version control in containers, explaining when new versions are created based on changes to container structure or metadata.

- A new version is created if and only if the container itself changes (e.g., title, ordering of members, adding or removing members) and not when its members change (e.g., a component in a Unit is updated with new text).
- When a shared member is soft-deleted in a different container, a new container version should be created for all containers referencing it without the member. That new version will be the new draft version of the container.

#. Publishing
=============

This section explains the publishing process for containers, detailing how containers and their members become accessible, either together or independently, based on their publication state.

- Containers can be published, allowing their content to be accessible from where the container is being used.
- When a draft container is published, all its draft members are also published.
- Members of a container can be published independently of the container itself.
- When a new draft is created for a container with a shared member that has been soft-deleted, publishing the draft will trigger the publishing of all containers referencing that member.
- Containers are not affected by the publishing process of its members.

#. Pruning
==========

This section defines the rules for pruning container versions, explaining when a container version can be pruned and the effects of pruning on the container and its members.

- A container version can be pruned if:
  #. It's not being used by any other container.
  #. It's not a published version.
  #. It's not the latest version of the container.
- In a top-down approach, start with the parent container and work your way down to its members.
- Members will not be deleted if they are shared by other containers.
- Pruning a container version will not affect the container's history or the members of other container versions.

.. _0002-content-flexibility.rst: docs/decisions/0002-content-extensibility.rst
.. _0003-content-extensibility.rst: docs/decisions/0003-content-extensibility.rst
