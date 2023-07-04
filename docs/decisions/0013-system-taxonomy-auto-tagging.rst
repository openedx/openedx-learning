13. System-defined automatic tagging
=====================================

Context
--------

One main characteristic of system-defined taxonomies is automatic content tagging.
It is necessary to implement this functionality when the associated content is created or edited.

Decision
---------

Events
~~~~~~~~

It is necessary to create `events`_ for each content for creation/edition: ``CourseCreation``, ``LibraryCreation``, etc.
This events will live in `openedx-events`_.

Receivers
~~~~~~~~~~

Auto-tagging receivers will live under ``openedx.features.tagging``,
registered as `a receiver`_ with the respective code.

Rejected Options
-----------------

Django Signals
~~~~~~~~~~~~~~

Implement a function to add the tag from the content metadata and register that function
as a Django signal. This works for Django database models, but some of the content lives in Mongo,
outside of the Django models. Also, using openedx-filters is better in the edx context, but if there is
other no-edX project that need to use ``openedx-tagging``, can use the Django Signals approach.


openedx-filters
~~~~~~~~~~~~~~~
Use `openedx-filters`_ to create a `filter`_ which calls `the auto tagging pipeline`_ after content
creation/editing. Although this approach works, there are more suitable options. Filters are
used to act on the input data and provide means to block the flow. This is not necessary in the
auto tagging context. The `hooks documentation`_ suggests the use of `events`_ hooks to expand functionality.


.. _openedx-events: https://github.com/openedx/openedx-events
.. _openedx-filters: https://github.com/openedx/openedx-filters
.. _filter: https://github.com/openedx/openedx-filters/blob/a4a192e1cac0b70bed31e0db8e4c4b058848c5c4/openedx_filters/learning/filters.py
.. _the auto tagging pipeline: https://github.com/openedx/edx-platform/blob/40613ae3f47eb470aff87359a952ed7e79ad8555/docs/guides/hooks/filters.rst#implement-pipeline-steps
.. _hooks documentation: https://github.com/openedx/edx-platform/blob/master/docs/guides/hooks/index.rst
.. _events: https://github.com/openedx/edx-platform/blob/master/docs/guides/hooks/events.rst
.. _a receiver: https://github.com/openedx/edx-platform/blob/master/docs/guides/hooks/events.rst#receiving-events
