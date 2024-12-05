17. Modeling Containers as a Generalized Capability for Holding Content
========================================================================

Context
-------

This ADR proposes a model for containers that can hold different types of content and can be used to model other content types with similar behavior, such as units, subsections, sections, or courses. The model defines containers' core structure and purpose, the types of containers, content constraints, container children, version control, publishing, and pruning.

Decisions
---------

1. Core Structure and Purpose of Containers
===========================================

This section defines the purpose and structure of containers, explaining how they are designed to hold various types of content through a parent-child setup.

- A container is designed as a generalized capability to hold different types of content.
- A container is a publishable content type that holds other content types through a parent-child relationship. For example, sections, subsections and units.
- The generalized container capability will have its own Django application as part of the authoring application allowing other types of containers and content types will build on top of. For instance:

  - Generalized containers (containers app is lowest level of these applications)
  - Selectors for dynamically selecting 0-N PublishableEntities, i.e., how we're going to do things like SplitTest and Randomized (a selectors Django application that builds on containers).
  - Units (units Django application, builds on containers and selectors).

2. Container Types and Content Constraints
==========================================

This section defines container types, content constraints, hierarchy, and extensibility. It introduces the main types of containers and outlines how content limitations and configurations are handled at the application level to support flexible content structures.

- A container marks any PublishableEntity, such as sections, subsections, units, or any other custom content type, as a type that can hold other content.
- Containers can be nested within other containers, allowing for complex content structures. For example, subsections can contain units.
- Containers might be of different types, with each type potentially having different restrictions on the type of content it can hold but that will not be enforced by containers.
- Content restrictions for containers are implemented at the app layer, allowing specific container types, like units, to limit their children to particular content types, e.g., units are restricted to contain only components.
- The course hierarchy Course > Section > Subsection > Unit will be implemented as relationships between containers, with each level acting as a container that holds other content. The hierarchy will be enforced by the content restrictions of each particular container but allowed to be overridden to support `Approach to Content Flexibility <0002-content-flexibility.rst>`_.
- Containers will follow extensibility principles in `Content Extensibility Through Model Relations <0003-content-extensibility.rst>`_ for creating new container types or subtypes.

3. Container Children and Relationships
=======================================

This section defines container children, their order, and relationships, covering flexible connections and support for draft and published states of their children.

- Each container version holds a list of children that the author has defined for that version.
- The author-defined list is used to show the content of a container version as the author specified it
- The author-defined list won't change for a specific container version even if its members change. E.g., a unit version UV1 with three components (CV1, CV2, CV3) will always have those three components in the author-defined list, even if one of the components is soft-deleted or a new version for the component is created.
- The children of a container can be any type of publishable content. E.g., sections, subsections, units, components, and any other publishable thing. For more details on publishable content, see `PublishableEntity`_.
- Children within a container are maintained in a specific order as an ordered list. E.g., components within a unit, or units within a subsection, are presented in a specific order.
- Containers represent their content hierarchy through a structure, like Course > Section > Subsection > Unit > Component, which defines parent-child relationships at each level.
- Containers can reference a specific version of their children or be set to point to their latest versions. For instance, component V1 might be used in a unit instead of its latest version. The latest version of a child can be referenced by setting its version to ``None`` which consists of the chosen standard for this representation.
- A single child (publishable entity) can be shared by multiple containers, allowing for reuse of content across different containers. For instance, a component can be shared by multiple units.

4. Next Container Versions
==========================

This section defines the rules for version control in containers, explaining when new versions are created based on changes to container structure or metadata.

- A new version is created if and only if the container itself changes (e.g., title, ordering of children, adding or removing children) and not when its children change (e.g., a component in a Unit is updated with new text). For instance, a new version of a unit is created when a component is removed, not when a new version of a component is created.
- No external change to a child will trigger the creation of a new version for the container. For example, updating or soft-deleting a component will not trigger the creation of a new version for the unit.
- Containers with invalid references (e.g., references to soft-deleted children) will be filtered out as needed to ensure consistency.

5. Publishing
=============

This section explains the publishing process for containers, detailing how containers and their children become accessible, either together or independently, based on their publication state. The publishing process happens on container versions, but throughout this section we'd call them containers for simplicity.

- Containers can be published, allowing their content to be accessible from where the container is being used.
- When a draft container is published, all its draft children are also published. For instance, after publishing a draft version of subsection which contains a draft unit with an updated title, the latest published version of the unit will be the one with the updated title, reflecting the changes made previously.
- Children of a container can be published independently of the container itself. E.g., a shared component can be published independently of the unit if it also exists outside the unit.
- Containers are not affected by the publishing process of its children. This means that publishing a component won't trigger new publishing processes for a container.

6. Pruning
==========

This section defines the rules for pruning container versions, explaining when a container version can be pruned and the effects of pruning on the container and its children.

- A container version can be pruned if it's not being used by any other container, it's not a published version and it's not the latest version of the container.
- In a top-down approach, start the deletion process with the parent container and work your way down to its children. E.g., when pruning Section V2 > Subsection V1 > Unit V3, the deletion process starts in the greater container working its way down to the smaller.
- Pruning a container version will not affect the container's history or the children of other container versions, so containers will not be deleted if they are shared by other containers.

.. _PublishableEntity: https://github.com/openedx/openedx-learning/blob/main/openedx_learning/apps/authoring/publishing/models.py#L100-L184
