13. System-defined automatic tagging
=====================================

Context
--------

One main characteristic of the System-defined is the automatic content tagging. 
It is necessary to implement this functionality when the associated content is created or edited.

Decision
---------

Use `openedx-filters`_ to call the auto tagging function after content creation/edition.
After create the ``Content-side`` class, `register a pipeline`_ with the respective filter.
Some filters must to be created, like ``CourseCreation``, ``LibraryCreation``, etc.

All this logic will be live on ``openedx.features.tagging``.

Rejected Options
-----------------

Django Signals
~~~~~~~~~~~~~~

Implement a function to add the tag from the content metadata and register that function
as a Django signal. Use openedx-filters is better in the edx context, but if there is
other no-edX project that need to use ``openedx-tagging``, can use the Django Signals approach.

.. _openedx-filters: https://github.com/openedx/openedx-filters/tree/a4a192e1cac0b70bed31e0db8e4c4b058848c5c4
.. _register a pipeline: https://github.com/openedx/edx-platform/blob/40613ae3f47eb470aff87359a952ed7e79ad8555/docs/guides/hooks/filters.rst#implement-pipeline-steps
