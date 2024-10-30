18. Modeling Units as a Concrete Implementation of the Container Capability
=======================================================================

Context
-------

The container capability is a generalized capability to hold different types of content. This decision focuses on modeling units as a concrete implementation of the container capability.

Decisions
---------

All decisions from `0017-generalized-containers.rst`_ are still valid so that this decisions will build on top of them.

.. _`0017-generalized-containers.rst`: 0017-generalized-containers.rst

1. Units as Containers
=======================

- A unit is a concrete type of container that holds components.
- A unit is a container, making it also a publishable entity.
- A unit application will offer shared definitions for use by other unit subtypes.

1. Unit Types and Content Constraints
======================================

- Units can only hold components as their members but will not enforce this restriction at the model level.
- Content restrictions for units are implemented at the app layer, allowing units to limit their members to components.

1. Unit Members and Relationships
==================================

- The members of a unit can only be components.

4. Unit Versioning Management
==============================

- A unit is versioned, and a new version is created if and only if the unit itself changes (e.g., title, ordering of contents, adding or removing content) and not when its content changes (e.g., a component in a unit is updated with new text).
