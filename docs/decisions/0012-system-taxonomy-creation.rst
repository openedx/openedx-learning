12. System-defined Taxonomy & Tags creation
============================================

Context
--------

The System-defined are closed taxonomies created by the system. Some of this are totally static (e.g Language)
and some depends on a core data model (e.g. Organizations). It is necessary to define how to create and validate 
the System-defined taxonomies and their tags.


Decision
---------

Create a ``Content-side`` class that lives on ``openedx.features.tagging``.
You must create a content-side model for each content and taxonomy to be used.
You can use ``ContentSystemTaxonomyMixin`` and the mixin of the Taxonomy (e.g. ``LanguageSystemTaxonomy``) to create the new class.
Then, all system-defined taxonomies must be created initially in a fixture.

Each Taxonomy mixin has ``get_tags``; to configure the valid tags, and ``validate_tags``; to check if a list of tags are valid.

We have two ways to handle tags in this type of taxonomies:

Hardcoded by fixtures/migrations
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

#. If the tags don't change over the time, you can create all on a fixture (e.g Languages). 
#. If the tags change over the time, you can create all on a migration. If you edit, delete, or add new tags, you should also do it in a migration.

Free-form tags
~~~~~~~~~~~~~~

This taxonomy depends on a core data model, but simplifies the creation of Tags by allowing free-form tags,
but we can validate the tags using the ``validate_tags`` method. For example we can put the Author taxonomy associated with
the ``User`` model and use the ``ID`` field as tags. Also we can validate if an User still exists or has been deleted over time.


Rejected Options
-----------------

Auto-generated from the codebase
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

Taxonomies that depend on a core data model and it is necessary to create a Tag for each object created.
