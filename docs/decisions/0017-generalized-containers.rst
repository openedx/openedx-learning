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
- A container is a publishable content type that holds other content types through a parent-child relationship. For example, sections, subsections and units.
- The generalized container capability will have its own Django application as part of the authoring application where other types of containers and content types will build on top of. For instance:

  - Generalized containers (containers app is lowest level of these applications)
  - Selectors for dynamically selecting 0-N PublishableEntities, i.e. how we're going to do things like SplitTest and Randomized (selectors application, builds on containers).
  - Units (units app, builds on containers and selectors).

2. Container Types and Content Constraints
==========================================

This section defines container types, content constraints, hierarchy, and extensibility. It introduces the main types of containers and outlines how content limitations and configurations are handled at the application level to support flexible content structures.

- A container marks any PublishableEntity, such as sections, subsections, units, or any other custom content type, as a type that can hold other content.
- Containers can be nested within other containers, allowing for complex content structures. For example, subsections can contain units.
- Containers might be of different types, with each type potentially having different restrictions on the type of content it can hold but that will not be enforced by containers.
- Content restrictions for containers are implemented at the app layer, allowing specific container types, like units, to limit their members to particular content types, e.g., units are restricted to contain only components.
- The course hierarchy Course > Section > Subsection > Unit will be implemented as relationships between containers, with each level acting as a container that holds other content. The hierarchy will be enforced by the content restrictions of each particular container but allowed to be overridden to support `0002-content-flexibility.rst`_.
- Containers will follow extensibility principles in `0003-content-extensibility.rst`_ for creating new container types or subtypes.

3. Container Members and Relationships
=======================================

This section defines container members, their order, and relationships, covering flexible connections and support for draft and published states of their members.

- The members of a container can be any type of publishable content. E.g., sections, subsections, units, components, and any other publishable thing. For more details on publishable content, see `PublishableEntity`_.
- Members within a container are maintained in a specific order as an ordered list. E.g., components within a unit, or units within a subsection, are presented in a specific order.
- Containers represent their content hierarchy through a structure, like Course > Section > Subsection > Unit > Component, which defines parent-child relationships at each level.
- Containers support both pinned and unpinned references for its members, allowing members to be pinned to a specific version or set to reference its latest version. For instance, component V1 might be used in a unit instead of its latest version.
- The latest state of a member can be referenced by setting its version to ``None``, which consists of the standard for a floating version.
- A single member (publishable entity) can be shared by multiple containers, allowing for reuse of content across different containers. For instance, a component can be shared by multiple units.

4. Container Version History
============================

This section defines the various lists of container's versions (author-defined, initial, and frozen) used  to track the history of changes made to a container, allowing to view past versions and changes over time.

- Each container version holds different lists of members (author-defined, initial, and frozen) to support rollback operations and history tracking for the container.
- The author-defined list is the list of members that the author has defined for the version of the container.
- The author-defined list won't change for a specific container version even if its references get soft-deleted.
- The initial list is a copy of the author-defined list that has all versions pinned as they were at the time the container version was created.
- The initial list is immutable for a container version.
- The frozen list refers to the list of members at the time when the next version of the container is created.
- The author-defined list is used to show the content of a container version as the author specified it, the frozen list can be used for discard operations on a draft version and the initial-list is part of the history of evolution of the container.

Let's say a course author creates a unit with three components, all using floating versions. Each component's latest version is V1. The author-defined list would include these three components, ordered as the author decided. The initial list would have the components pinned to V1, while the frozen list would be empty until we create the next version for the container.

Now, when the author creates a new version of the unit, for example, V2, we need to store the latest state of the container in the frozen list. This means pinning the latest versions of the components at that time, let's say V1, V2, and V3, respectively.

Next, imagine the course author creates a new unit but uses pinned references for the components instead of floating versions, as they don't want to use the latest updates. In this case, the author-defined list, initial list, and frozen list would all be the same, as the component versions remain fixed. If we were to use different pinned versions, then a new unit version would be created instead.

5. Next Container Versions
==================================

This section defines the rules for version control in containers, explaining when new versions are created based on changes to container structure or metadata.

- A new version is created if and only if the container itself changes (e.g., title, ordering of members, adding or removing members) and not when its members change (e.g., a component in a Unit is updated with new text). For instance, a new version of a unit is created when a component is removed, not when a new version of a component is created.
- When a shared member is soft-deleted in a another container, all containers referencing it should create a new version without the member. This new version will be the new draft version of the container. For example, suppose a component is shared between two units, if the component is soft-deleted independently, then we'd need to create a new version for both units sharing the component.

6. Publishing
=============

This section explains the publishing process for containers, detailing how containers and their members become accessible, either together or independently, based on their publication state. The publishing process happens on container versions, but throughout this section we'd call them containers for simplicity.

- Containers can be published, allowing their content to be accessible from where the container is being used.
- When a draft container is published, all its draft members are also published. For instance, after publishing a draft version of subsection which contains a draft unit with an updated title, the latest published version of the unit will be the one with the updated title, reflecting the changes made previously.
- Members of a container can be published independently of the container itself. E.g., a shared component can be published independently of the unit if it also exists outside the unit.
- When a new draft is created for a container with a shared member that has been soft-deleted, publishing the draft will trigger the publishing of all containers referencing that soft-deleted member. For example, if a component was soft-deleted triggering the creation of two draft units, then publishing one of the units would result in the publish of the second unit. Both units will now be published without the soft-deleted component.
- Containers are not affected by the publishing process of its members. This means that publishing a component won't trigger new publishing processes for a container.

7. Pruning
==========

This section defines the rules for pruning container versions, explaining when a container version can be pruned and the effects of pruning on the container and its members.

- A container version can be pruned if:
  #. It's not being used by any other container.
  #. It's not a published version.
  #. It's not the latest version of the container.
- In a top-down approach, start the deletion process with the parent container and work your way down to its members. E.g., when pruning Section V2 > Subsection V1 > Unit V3, the deletion process starts in the greater container working its way down to the smaller.
- Pruning a container version will not affect the container's history or the members of other container versions, so containers will not be deleted if they are shared by other containers.

.. _0002-content-flexibility.rst: docs/decisions/0002-content-extensibility.rst
.. _0003-content-extensibility.rst: docs/decisions/0003-content-extensibility.rst
.. _PublishableEntity: https://github.com/openedx/openedx-learning/blob/main/openedx_learning/apps/authoring/publishing/models.py#L100-L184