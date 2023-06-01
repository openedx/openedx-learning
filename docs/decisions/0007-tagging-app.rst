7. Tagging App structure
========================

Context
-------

We want the openedx_tagging app to be useful in different Django projects outside of just openedx-learning and edx-platform.


Decisions
---------

The openedx_tagging data structures and code will stand alone with no dependencies on other Open edX projects.

Classes which require dependencies on other Open edX projects should be defined within a ``tagging`` module inside those projects.

For example, here we define ``openedx_tagging.core.models.Taxonomy``, whose data and functionality are self-contained to the openedx_tagging app. However in Studio, we need to be able to limit access to some Taxonomy by organization, using the same "course creator" access which  limits course creation for an organization to a defined set of users.

So in edx-platform, we create the ``cms.djangoapps.tagging`` app, and it contains ``models.OrgTaxonomy``, which has a 1:1 relationship with an ``openedx_tagging.core.models.Taxonomy``, so that ``openedx_tagging.core.models.Tag`` entries can be created which link to that Taxonomy.

To support the org restrictions, `OrgTaxonomy` adds the ``org_owner`` field, a foreign key to the Organization model, which is provided by the edx-organization app.
