18. Modeling Units as a Concrete Implementation of the Container Capability
===========================================================================

Context
-------

The container capability is a generalized capability to hold different types of content. This decision focuses on modeling units as a concrete implementation of the container capability.

Decisions
---------

All decisions from `0017-generalized-containers.rst`_ are still valid but are written here alongside unit-specific decisions for better illustration.

.. _`0017-generalized-containers.rst`: 0017-generalized-containers.rst

1. Units as Containers
=======================

- A unit is a concrete type of container that holds components.
- A unit is a container, making it also a publishable entity.
- A Django application, which builds on the container application definitions, will an API and enough definitions for other unit subtypes to use.

2. Unit Types and Content Constraints
======================================

- Units can only hold components as their members but will not enforce this restriction at the model level.
- Units are the first level of nested content types Unit > Components.
- Content restrictions for units are implemented at the app layer, allowing units to limit their members to only components.
- Unit subtypes can be created by following the extensibility principles in `0003-content-extensibility.rst`_.

3. Unit Members and Relationships
==================================

- The members of a unit can only be components.
- Components are referenced as an ordered list in a unit.
- Units can hold both static and dynamic content, such as user-specific variations.
- Units can reference pinned and unpinned versions of its components.
- The latest draft or publish version of a component can be set by using `None` in thr parent-child relationship between units-components.
- A single component can be reference by multiple units.

4. Unit Version History
============================

- Each unit version holds different list of components to support rollback operations and history tracking.
- The author-defined list is the list of components defined by the author for a specific unit version.
- The author-defined list of components won't change for a specific version.
- The initial list is a copy of the author-defined list that has all components pinned to the versions at the time of the unit version creation.
- The initial list is immutable for a unit version.
- The frozen list refers to the list of components at the time when the next version of the unit is created.
- When creating the author-defined list of a new version with pinned references, then the author-defined list is the same as the initial and frozen list. When creating a new version with unpinned references, then the frozen list starts as `None` and should be updated with the author-defined components pinned when a new version is created.
- The author-defined list is used to show the content of a unit version as the author specified it, the frozen list can be used for discard operations on a draft version and the initial-list is part of the history of evolution of the unit.
- These lists allow history tracking of a unit version and revert operations.

5. Next Unit Versions
======================

- A new version is created if and only if the unit itself changes (e.g., title, ordering of components, adding or removing components) and not when its components change (e.g., a component in a Unit is updated with new text).
- When a shared component is soft-deleted in a different unit, a new unit version should be created for all containers referencing it without the component.

6. Publishing
==============

- Units can be published, allowing their content to be accessible from where the unit is being used.
- When a draft unit is published, all its draft components are also published.
- Components within a unit can be published independently of the unit itself.
- When a new draft, created for a unit when a shared component is soft-deleted, is published then all units referencing the component will be force-published.
- Units are not affected by the publishing process of its components.

7. Pruning
===========

- A unit version can be pruned if:
  #. It's not being used by any subsections.
  #. It's not a published version.
  #. It's not the latest version of the unit.
- In a top-down approach, start with the unit and work your way down to its component versions.
- Component versions will not be deleted if they are shared by other units.
- Pruning a unit version will not affect the unit's history or the components of other unit versions.
