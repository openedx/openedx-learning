8. Tag tree data structure
==========================

Context
-------

A taxonomy groups a set of related tags under a namespace and a set of usage rules. Some taxonomies require tags to be selected from a list or nested tree of valid options.

Do we need a formal tree data structure to represent hierarchical tags?

Decision
--------

No, a simplistic tree structure is sufficient for the MVP and forseeable feature requests.

Existing tree data structures are designed to support very dynamic and deeply nested trees (e.g. forum threads) which are traversed frequently, and this feature set is overkill for taxonomy trees.

Taxonomy trees have a maximum depth of 3 levels, which limits the depth of node traversal, and simplifies the UI/UX required to tag or search filter content with nested tags.

Taxonomy trees only require simple operations, and infrequent traversals. Frequent operations (like viewing content tags) will only display the leaf tag value, not its full lineage, to minimize tree traversal. Full trees can be fetched quickly enough during content tag editing. Taxonomy tree changes themselves will also be infrequent.

Rejected Alternatives
---------------------

All taxonomies are trees
~~~~~~~~~~~~~~~~~~~~~~~~

We could use a tree structure for all taxonomies: flat taxonomies would have only 1 level of tags under the root, while nested taxonomies can be deeper.

To implement this, we'd link each taxonomy to a root tag, with the user-visible tags underneath.

It was simpler instead to link the tag to the taxonomy, which removes the need for the unseen root tag.

Closure tables
~~~~~~~~~~~~~~

https://coderwall.com/p/lixing/closure-tables-for-browsing-trees-in-sql

Implementing the taxonomy tree using closure tables allows for tree traversals in O(N) time or less, where N is the total number of tags in the taxonomy. So the tree depth isn't as much of a performance concern as the total number of tags.

Options include:

* `django-tree-queries <https://github.com/matthiask/django-tree-queries>`_

  Simple, performant, and well-maintained tree data structure.  However it uses RECURSIVE CTE queries, which aren't supported until MySQL 8.0.

* `django-mptt <https://github.com/django-mptt/django-mptt>`_

  Already an edx-platform dependency, but no longer maintained. It can be added retroactively to an existing tree-like model.

* `django-closuretree <https://github.com/ocadotechnology/django-closuretree>`_

  Another a good reference implementation for closure tables which can be added retroactively to an existing tree-like model. It is not actively maintained.
