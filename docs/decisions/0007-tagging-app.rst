7. Tagging App structure
========================

Context
-------

We want the openedx_tagging app to be useful in different Django projects outside of just openedx-learning and edx-platform.


Decisions
---------

The openedx_tagging data structures and code will stand alone with no dependencies on other Open edX projects.

Classes which require dependencies on other Open edX projects should be defined within a ``tagging`` module inside those projects.

Taxonomy
~~~~~~~~

The ``openedx_tagging`` module defines ``openedx_tagging.core.models.Taxonomy``, whose data and functionality are self-contained to the ``openedx_tagging`` app. However in Studio, we need to be able to limit access to some Taxonomy by organization, using the same "course creator" access which limits course creation for an organization to a defined set of users.

So in edx-platform, we will create the ``openedx.features.content_tagging`` app, to contain the models and logic for linking Organization owners to Taxonomies. There's no need to subclass Taxonomy here; we can enforce access using the ``content_tagging.api``.

ObjectTag
~~~~~~~~~

Similarly, the ``openedx_tagging`` module defined ``openedx_tagging.core.models.ObjectTag``, also self-contained to the
``openedx_tagging`` app.

But to tag content in the LMS/Studio, we need to enforce ``object_id`` as a CourseKey or UsageKey type. So to do this, we subclass ``ObjectTag``, and use the ``openedx.features.tagging.registry`` to register the subclass, so that it will be picked up when this tagging API creates or resyncs object tags.

Rejected Alternatives
---------------------

Embed in edx-platform
~~~~~~~~~~~~~~~~~~~~~

Embedding the logic in edx-platform would provide the content tagging logic specifically required for the MVP.

However, we plan to extend tagging to other object types (e.g. People) and contexts (e.g. Marketing), and so a generic, standalone library is preferable in the log run.


Subclass Taxonomy
~~~~~~~~~~~~~~~~~

Another approach considered was to encapsulate the complexity of ObjectTag validation in the Taxonomy class, and so use subclasses of Taxonomy to validate different types of ObjectTags, and use `multi-table inheritance`_ and django polymorphism when pulling the taxonomies from the database.

However, because we will have a number of different types of Taxonomies, this proved non-performant.


-.. _multi-table inheritance: https://docs.djangoproject.com/en/3.2/topics/db/models/#multi-table-inheritance
