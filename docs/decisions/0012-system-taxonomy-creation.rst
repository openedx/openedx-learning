12. System-defined Taxonomy & Tags creation
============================================

Context
--------

System-defined taxonomies are taxonomies created by the system. Some of these are totally static (e.g Language)
and some depends on a core data model (e.g. Organizations). It is necessary to define how to create and validate 
the System-defined taxonomies and their tags.


Decision
---------

System Tag lists and validation
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

Each System-defined Taxonomy will have its own ``ObjectTag`` subclass which is used for tag validation (e.g. ``LanguageObjectTag``, ``OrganizationObjectTag``).
Each subclass can overwrite ``get_tags``; to configure the valid tags, and ``is_valid``; to check if a list of tags are valid.  Both functions are implemented on the ``ObjectTag`` base class, but can be overwritten to handle special cases.

We need to create an instance of each System-defined Taxonomy's ObjectTag in a fixture. This instances will be used on different APIs.

Later, we need to create content-side ObjectTags that live on ``openedx.features.content_tagging`` for each content and taxonomy to be used (eg. ``CourseLanguageObjectTag``, ``CourseOrganizationObjectTag``).
This new class is used to configure the automatic content tagging. You can read the `document number 0013`_ to see this configuration.

Tags creation
~~~~~~~~~~~~~~

We have two ways to handle Tags creation and validation for System-defined Taxonomies:

**Hardcoded by fixtures/migrations**

#. If the tags don't change over the time, you can create all on a fixture (e.g Languages). 
#. If the tags change over the time, you can create all on a migration. If you edit, delete, or add new tags, you should also do it in a migration.

**Free-form tags**

This taxonomy depends on a core data model, but simplifies the creation of Tags by allowing free-form tags,
but we can validate the tags using the ``validate_object_tag`` method. For example we can put the ``AuthorSystemTaxonomy`` associated with
the ``User`` model and use the ``ID`` field as tags. Also we can validate if an ``User`` still exists or has been deleted over time.


Rejected Options
-----------------

Tags created by Auto-generated from the codebase
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

Taxonomies that depend on a core data model could create a Tag for each eligible object. 
Maintaining this dynamic list of available Tags is cumbersome: we'd need triggers for creation, editing, and deletion.
And if it's a large list of objects (e.g. Users), then copying that list into the Tag table is overkill.
It is better to dynamically generate the list of available Tags, and/or dynamically validate a submitted object tag than
to store the options in the database.

.. _document number 0013: https://github.com/openedx/openedx-learning/blob/main/docs/decisions/0013-system-taxonomy-auto-tagging.rst
