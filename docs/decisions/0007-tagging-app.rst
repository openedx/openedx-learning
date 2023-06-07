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

The ``openedx_tagging`` module defines ``openedx_tagging.core.models.Taxonomy``, whose data and functionality are self-contained to the ``openedx_tagging`` app. However in Studio, we need to be able to limit access to some Taxonomy by organization, using the same "course creator" access which  limits course creation for an organization to a defined set of users.

So in edx-platform, we will create the ``openedx.features.tagging`` app, to contain ``models.OrgTaxonomy``. OrgTaxonomy subclasses ``openedx_tagging.core.models.Taxonomy``, employing Django's `multi-table inheritance`_ feature, which allows the base Tag class to keep foreign keys to the Taxonomy, while allowing OrgTaxonomy to store foreign keys into Studio's Organization table.

ObjectTag
~~~~~~~~~

Similarly, the ``openedx_tagging`` module defined ``openedx_tagging.core.models.ObjectTag``, also self-contained to the
``openedx_tagging`` app.

But to tag content in the LMS/Studio, we create ``openedx.features.tagging.models.ContentTag``, which subclasses ``ObjectTag``, and can then reference functionality available in the platform code.

Rejected Alternatives
---------------------

Embed in edx-platform
~~~~~~~~~~~~~~~~~~~~~

Embedding the logic in edx-platform would provide the content tagging logic specifically required for the MVP.

However, we plan to extend tagging to other object types (e.g. People) and contexts (e.g. Marketing), and so a generic, standalone library is preferable in the log run.


.. _multi-table inheritance: https://docs.djangoproject.com/en/3.2/topics/db/models/#multi-table-inheritance
