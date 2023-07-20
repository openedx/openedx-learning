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

We need to create an instance of each System-defined Taxonomy in a fixture. With their respective characteristics and subclasses.
The ``pk`` of these instances must be negative so as not to affect the auto-incremented ``pk`` of Taxonomies.

Later, we need to create content-side ObjectTags that live on ``openedx.features.content_tagging`` for each content and taxonomy to be used (eg. ``CourseLanguageObjectTag``, ``CourseOrganizationObjectTag``).
This new class is used to configure the automatic content tagging. You can read the `document number 0013`_ to see this configuration.

Tags creation
~~~~~~~~~~~~~~

We have two ways to handle Tags creation and validation for System-defined Taxonomies:

**Hardcoded by fixtures/migrations**

#. If the tags don't change over the time, you can create all on a fixture (e.g Languages).
   The ``pk`` of these instances must be negative.
#. If the tags change over the time, you can create all on a migration. If you edit, delete, or add new tags, you should also do it in a migration.

**Dynamic tags**

Closed Taxonomies that depends on a core data model. Ex. AuthorTaxonomy with Users as Tags

#. Tags are created on the fly when new ObjectTags are added.
#. Tag.external_id we store an identifier from the instance (eg. User.pk).
#. Tag.value we store a human readable representation of the instance (eg. User.username).
#. Resync the tags to re-fetch the value. 


Rejected Options
-----------------

Free-form tags
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

Open Taxonomy that depends on a core data model, but simplifies the creation of Tags by allowing free-form tags,

Rejected because it has been seen that using dynamic tags provides more functionality and more advantages.

.. _document number 0013: https://github.com/openedx/openedx-learning/blob/main/docs/decisions/0013-system-taxonomy-auto-tagging.rst
