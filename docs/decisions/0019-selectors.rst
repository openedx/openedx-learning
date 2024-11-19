Selectors for Dynamically Selecting Content
===========================================

Context
-------

This ADR proposes a way to represent dynamic members of a container, where dynamic means selecting members from a specified pool. Some examples of dynamic selection are:

1. A/B Testing: testing two different groups of components to see which perform better.
2. Per Student: randomly selecting three problems from a set of 20 per student.

And any other custom use case to dynamically select members for a container. This proposal introduces the concepts of selectors and variants to implement this type of dynamic selection.

1. Core Structure
=================

This section explains the concepts and behaviors used to build dynamic selection, selectors and variants.

- Selectors determine what the container should display based on the selector type. For example, based on the nature an A/B split test or a randomization selector members of the container would vary.
- Selectors are designed to dynamically select 0-N publishable entities (e.g., components).
- Each version represents a set of members at a particular time.
- The logic for pushing members into variants depends on the selection version's selection method.
- Variants hold the members selected for a container based on what the selection method is.
- Variants are build on the parent-child relationship between containers and their members, storing the dynamically selected content as an ordered list.

2. Selector Types and Selecting Content
=======================================

This section describes how different types of selectors work and how they handle the selection of dynamic content.

- A selector can be of any type, which means it can implement any method to select members from a pool.
- Selection versions encode the rules and holds useful details for the selection process like: where to get members from, number of items to select, and other criteria.
- Depending on the size of the pool of members, variants can be generated at publishing time or on-demand. This behavior should be determined by the selector version based on high vs low permutation scenarios.
- A compositor is responsible for populating the variants but will not be implemented as part of the authoring application.

3. Versioning
=============

A new version of a selector is created whenever the pool of concent changes by adding, removing or reordering existing members.