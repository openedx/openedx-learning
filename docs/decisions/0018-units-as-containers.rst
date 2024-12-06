18. Modeling Units as a Concrete Implementation of the Container Capability
===========================================================================

Context
-------

The container capability is a generalized capability to hold different types of content. This decision focuses on modeling units as a concrete implementation of the container capability.

Decisions
---------

All decisions from `0017-generalized-containers.rst <0017-generalized-containers.rst>`_ are still valid but are written here alongside unit-specific decisions for better illustration.

1. Units as Containers
=======================

- A unit is a concrete type of container that holds components.
- A unit is a container, making it also a publishable entity.
- Units build on the generalized container capability to hold components and selectors for dynamically selecting 0-N PublishableEntities.
- Units have their own Django application that builds on containers and selectors.

2. Unit Types and Content Constraints
======================================

- Units can only hold components as their children but will not enforce this restriction at the model level.
- Units are the first level of nested content types Unit > Components.
- Content restrictions for units are implemented at the application layer, allowing units to limit their children to only components. None of this is enforced at the model level.
- Unit subtypes can be created by following the extensibility principles in `Content Extensibility Through Model Relations <0003-content-extensibility.rst>`_.

3. Unit Children and Relationships
==================================

- The children of a unit can only be components.
- Components in a unit are referenced as an ordered list. For example, a unit can have a list of components that are ordered by the author.
- Units can hold both static and dynamic content (using selectors), such as user-specific variations. For example, a unit can have components that won't change for all users and components that are dynamically selected based on particular criteria, like A/B tests or Random selection.
- Units can reference pinned and unpinned versions of its components. The latest version of a component can be set by using ``None`` as the version. For example, a unit can have a component that is always the latest version so it always shows the latest content or a component that is pinned to a specific version so it always shows the same content regardless of the latest version.
- A single component can be reference by multiple units.

4. Next Unit Versions
======================

Only changes to the unit itself (e.g., title, ordering of components, adding or removing a component, or changes to the unit's metadata) will create a new version of the unit. Changes to the components of a unit will not create a new version of the unit.

5. Publishing
==============

- Units can be published, allowing their content to be accessible from where the unit is being used. Only after a unit is published it can be reused as content for other containers.
- When a draft unit is published, all its draft components are also published.
- Components within a unit can be published independently of the unit itself. This could happen for components that are shared by multiple units.
- Units are not affected by the publishing process of its components.

6. Pruning
==========

- A unit version can be pruned if it's not being used by any subsections, it's not a published version, and it's not the latest version of the unit.
- In a top-down approach, start with the unit and work your way down to its component versions.
- Component versions will not be deleted if they are shared by other units.
- Pruning a unit version will not affect the unit's history or the components of other unit versions that are still in use.
