20. Authoring as an Umbrella App of Smaller Applets
===================================================

Context
-------

Up to this point, Learning Core has used many small apps with a narrow focus (e.g. ``components``, ``collections``, etc.) in order to make each individual app simpler to reason about. This has been useful overall, but it has made refactoring more cumbersome. For instance:

#. Moving models between apps is tricky, requiring the use of Django's ``SeparateDatabaseAndState`` functionality to fake a deletion in one app and a creation in another without actually altering the database. It also requires doctoring the migration files for models in other repos that might have foreign key relations to the model being moved, so that they're pointing to the new ``app_label``.  This will be an issue when we try to extract container-related models and logic out of publishing and into a new ``containers`` app.
#. Renaming an app is also cumbersome, because the process requires creating a new app and transitioning the models over. This came up when trying to rename the ``contents`` app to ``media``.

There have also been minor inconveniences, like having a long list of ``INSTALLED_APPS`` to maintain in edx-platform over time, or not having these tables easily grouped together in the Django admin interface.

Decisions
---------

1. Single Authoring App
~~~~~~~~~~~~~~~~~~~~~~~

All existing authoring apps will be merged into one Django app (``openedx_learning.app.authoring``). Some consequences of this decision:

- The tables will be renamed to have the ``oel_authoring`` label prefix.
- All management commands will be moved to the ``authoring`` app.

2. Logical Separation via Applets
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

We will continue to keep internal API boundaries between individual applets, and use the ``api.py`` modules. This is both to insulate applets from implementation changes in other applets, as well as to provide a set of APIs that third-party plugins can utilize. As before, we will use Import Linter to enforce dependency ordering.

3. Restructuring Specifics
~~~~~~~~~~~~~~~~~~~~~~~~~~

In one pull request, we are going to:

#. Create bare shells of the existing ``authoring`` apps (``backup_restore``, ``collections``, ``components``, ``contents``, ``publishing``, ``sections``, ``subsections``, ``units``), and move them to the ``openedx_learning.apps.authoring.backcompat`` package. These shells will have an ``apps.py`` file and the ``migrations`` package for each existing app. This will allow for a smooth schema migration to transition the models from these individual apps to ``authoring``.
#. Move the actual models files and API logic for our existing authoring apps to the ``openedx_learning.apps.authoring.applets`` package.
#. Convert the top level ``openedx_learning.apps.authoring`` package to be a Django app. The top level ``admin.py``, ``api.py``, and ``models.py`` modules will do wildcard imports from the corresponding modules across all applet packages.

In terms of model migrations, all existing apps will have a final migration that uses ``SeparateDatabaseAndState`` to remove all model state, but make no actual database changes. After that, the initial ``authoring`` app migration will list all these "deletion" migrations as dependencies, and then also use ``SeparateDatabaseAndState`` to create the model state without doing any actual database operations. The next ``authoring`` app migration will rename all existing
database tables to use the ``oel_authoring`` prefix, for uniformity.

There are a few edx-platform apps that already have foreign keys and migrations that reference these models. It will be necessary to alter those historical migrations to pretend that these models have always come from the ``authoring`` app (with the label ``oel_authoring``).

In a future release (no earlier than Willow), we would remove the old apps entirely, and alter the intial ``authoring`` app migration so that it looks like a simple schema creation without state separation. We would also remove all references to the original set of small apps. This shouldn't affect existing installs because the ``authoring`` migration would have already run on those sites. This may require edx-platform apps to alter their migration dependencies to repoint to the initial ``authoring`` migration.

4. The Bigger Picture
~~~~~~~~~~~~~~~~~~~~~

This practice means that the ``authoring`` Django app corresponds to a Subdomain in Domain Driven Design terminology, with each applet being a Bounded Context. We call these "Applets" instead of "Bounded Contexts" because we don't want it to get confused for Django's notion of Contexts and Context Processors (or Python's notion of Context Managers).
