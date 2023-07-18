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

So in edx-platform, we will create the ``openedx.features.content_tagging`` app, to contain the models and logic for linking Organization owners to Taxonomies. Here, we can subclass ``Taxonomy`` as needed, preferably using proxy models. The APIs are responsible for ensuring that any ``Taxonomy`` instances are cast to the appropriate subclass.

ObjectTag
~~~~~~~~~

Similarly, the ``openedx_tagging`` module defined ``openedx_tagging.core.models.ObjectTag``, also self-contained to the
``openedx_tagging`` app.

But to tag content in the LMS/Studio, we need to enforce ``object_id`` as a CourseKey or UsageKey type. So to do this, we subclass ``ObjectTag``, and use this class when creating object tags for the content taxonomies. Once the ``object_id`` is set, it is not editable, and so this key validation need not happen again.

Rejected Alternatives
---------------------

Embed in edx-platform
~~~~~~~~~~~~~~~~~~~~~

Embedding the logic in edx-platform would provide the content tagging logic specifically required for the MVP.

However, we plan to extend tagging to other object types (e.g. People) and contexts (e.g. Marketing), and so a generic, standalone library is preferable in the log run.
