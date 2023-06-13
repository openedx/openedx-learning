13. System-defined automatic tagging
=====================================

Context
--------

One main characteristic of the System-defined is the automatic content tagging. 
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

After create the ``Content-side`` class for each content and taxonomy,
create a function inside each class with the logic of the auto tagging.
Then you need to register each class as `a pipeline`_ with the respective filter.

This pipelines will live on ``openedx.features.tagging``

Rejected Options
-----------------

Django Signals
~~~~~~~~~~~~~~

Implement a function to add the tag from the content metadata and register that function
as a Django signal. This works for Django database models, but some of the content lives in Mongo, 
outside of the Django models. Also, using openedx-filters is better in the edx context, but if there is
other no-edX project that need to use ``openedx-tagging``, can use the Django Signals approach.

.. _openedx-filters: https://github.com/openedx/openedx-filters/tree/a4a192e1cac0b70bed31e0db8e4c4b058848c5c4
.. _filters: https://github.com/openedx/openedx-filters/blob/a4a192e1cac0b70bed31e0db8e4c4b058848c5c4/openedx_filters/learning/filters.py
.. _a pipeline: https://github.com/openedx/edx-platform/blob/40613ae3f47eb470aff87359a952ed7e79ad8555/docs/guides/hooks/filters.rst#implement-pipeline-steps
