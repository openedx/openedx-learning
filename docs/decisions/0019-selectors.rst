19. Selectors for Dynamically Selecting Content
===============================================

Context
-------

This ADR proposes a way to represent dynamic members of a container, where dynamic means selecting members from a specified pool. Some examples of dynamic selection are:

1. A/B Testing: testing two different groups of components to see which perform better.
2. Per Student: randomly selecting three problems from a set of 20 per student.

And any other custom use case to dynamically select members for a container. This proposal introduces the concepts of selectors and variants to implement this type of dynamic selection.

Decisions
---------

1. Core Structure
~~~~~~~~~~~~~~~~~

This section explains the concepts and behaviors used to build dynamic selection, selectors and variants.

- Selectors determine what the container should display based on the selector type. For example, based on the nature an A/B split test or a randomization selector members of the container would vary.
- Selectors are used to dynamically select 0-N publishable entities from a specified pool. E.g., take 5 components from this pool of 20.
- The logic for pushing members into variants depends on the selector selection method. For example, A/B split testing two different sets of components or select three problems from a set of twenty.
- Variants hold the members selected for a container based on what the selection method is. E.g., if the selector is "select 5 components out this pool of 20 components" then the variant would be the 5 components selected for the user.
- Variants are build on the parent-child relationship used for containers and their members, storing the dynamically selected content as an ordered list as containers do.

2. Selector Types and Selecting Content
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

This section describes how different types of selectors work and how they handle the selection of dynamic content.

- A selector can be of any type, which means it can implement any method to select members from a pool. Therefore, selectors will follow extensibility principles in `0003-content-extensibility.rst <0003-content-extensibility.rst>`_ for creating new selector types.
- Selection versions encode the rules and holds useful details for the selection process like: where to get members from, number of items to select, and other criteria. For instance, for the "select 5 components out of this pool of 20 components" its selector version would encode where to get the 20 components, how many to get for each user and any other detail needed to create the specific variants.
- Depending on the size of the pool of members, variants can be generated at publishing time or on-demand. This behavior should be determined by the selector version based on high vs low permutation scenarios.
- A compositor is responsible for populating the variants but will not be implemented as part of the selector application which belongs to the authoring app.

3. Versioning
~~~~~~~~~~~~~

A new version of a selector is created whenever the pool of concent changes by adding, removing or reordering existing members.

