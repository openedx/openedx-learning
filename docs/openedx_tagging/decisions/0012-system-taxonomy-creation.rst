12. System-defined Taxonomy & Tags creation
============================================

Context
--------

System-defined taxonomies are taxonomies created by the system. Some of these
depend on Django settings (e.g. Languages) and others depends on a core data
model (e.g. Organizations or Users). It is necessary to define how to create and
validate the System-defined taxonomies and their tags.


Decision
---------

System Tag lists and validation
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

Each Taxonomy has two methods for validating tags:
#. ``validate_value``
#. ``validate_external_id``

These functions will return ``True`` if a given tag is valid, based on its
external ID or value.  Subclasses should override these as needed, to implement
different types of taxonomy behavior (e.g. based on a model or baed on Django
settings).

For example ``validate_value("English")`` will return ``True`` for the language
taxonomy if the English language is enabled in the Django settings. Likewise,
``validate_external_id("en")`` would return true, but
``validate_external_id("zz")`` would be ``False`` because there is no such
language. Or, for a User taxonomy, ``validate_value("username")`` would return
``True`` if a user with that username exists, or ``validate_external_id(...)``
could validate if a user with that ID exists (note that the ID must be converted
to a string).

In all of these cases, a ``Tag`` instance may or may not exist in the database.
Before saving an ``ObjectTag`` which references a tag in these taxonomies, the
tagging API will use either ``Taxonomy.tag_for_value`` or
``Taxonomy.tag_for_external_id``. These methods are responsible for both
validating the tag (like ``validate_...``) but also auto-creating the ``Tag``
instance in case it doesn't already exist. Subclasses should override these as
needed.

In this way, the system-defined taxonomies are fully dynamic and can represent
tags based on Languages, Users, or Organizations that may exist in large numbers
or be constantly created.

At present, there isn't a good way to *list* all of the potential tags that
exist in a system-defined Taxonomy. We may add an API for that in the future,
for example to list all of the available languages. However for other cases like
users it doesn't make sense to even try to list all of the available tags. So
for now, the assumption is that the UI will not even try to display a list of
available tags for system-defined taxonomies. After all, system-defined tags are
usually applied automatically, rather than a user manually selecting from a
list. If there is a need to show a list of tags to the user, use the API that
lists the actually applied tags - i.e. the values of the ``ObjectTags``
currently applied to objects using the taxonomy.

Tags hard-coded by fixtures/migrations
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

In the future there may be system-defined taxonomies that are not dynamics at
all, where the list of tags are defined by ``Tag`` instances created by a
fixture or migration. However, as of now we don't have a use case for that.
