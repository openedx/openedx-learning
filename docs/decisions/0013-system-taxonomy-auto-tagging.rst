13. System-defined automatic tagging
=====================================

Context
--------

One main characteristic of system-defined taxonomies is automatic content tagging. 
It is necessary to implement this functionality when the associated content is created or edited.

Decision
---------

Use `openedx-filters`_ to call the auto tagging function after content creation/edition.

Filters
~~~~~~~~

It is necessary to create `filters`_ for each content for creation/edition: ``CourseCreation``, ``LibraryCreation``, etc.
This filters will live on ``openedx-filters``.

Pipelines
~~~~~~~~~~

Auto-tagging pipelines will live under ``openedx.features.tagging``, 
registered as `a pipeline`_ with the respective filter.

Rejected Options
-----------------

Django Signals
~~~~~~~~~~~~~~

Implement a function to add the tag from the content metadata and register that function
as a Django signal. This works for Django database models, but some of the content lives in Mongo, 
outside of the Django models. Also, using openedx-filters is better in the edx context, but if there is
other no-edX project that need to use ``openedx-tagging``, can use the Django Signals approach.

.. _openedx-filters: https://github.com/openedx/openedx-filters
.. _filters: https://github.com/openedx/openedx-filters/blob/a4a192e1cac0b70bed31e0db8e4c4b058848c5c4/openedx_filters/learning/filters.py
.. _a pipeline: https://github.com/openedx/edx-platform/blob/40613ae3f47eb470aff87359a952ed7e79ad8555/docs/guides/hooks/filters.rst#implement-pipeline-steps
