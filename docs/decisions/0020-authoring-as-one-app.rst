20. Authoring as an Umbrella App of Smaller Applets
===================================================

Context
-------

Up to this point, Learning Core has used many small apps with a narrow focus (e.g. ``components``, ``collections``, etc.) in order to make each individual app simpler to reason about. This has been useful overall, but it has made refactoring more cumbersome. For instance:

#. Moving models between apps is tricky, requiring the use of Django's ``SeparateDatabaseAndState`` functionality to fake a deletion in one app and a creation in another without actually altering the database.
#. Renaming an app is also cumbersome, because the process requires creating a new app and transitioning the models over. This came up when trying to rename the ``contents`` app to ``media``.

There have also been minor inconveniences, like having a long list of ``INSTALLED_APPS`` to maintain in edx-platform over time.

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

3. Restructuring Plan
~~~~~~~~~~~~~~~~~~~~~

In one pull request, we would:

#. Remove the ``apps.py`` files for all existing ``authoring`` apps: ``backup_restore``, ``collections``, ``components``, ``contents``, ``publishing``, ``sections``, ``subsections``, ``units``.
#. Move the above apps to a new ``openedx_learning.apps.authoring.applets`` package.
#. Convert the top level ``openedx_learning.apps.authoring`` package to be a Django app. The top level ``admin.py``, ``api.py``, and ``models.py`` modules will do wildcard imports from the corresponding modules across all applet packages.

4. Model Migration Plan
~~~~~~~~~~~~~~~~~~~~~~~

Migrating models across apps is tricky. This plan assumes that people will either have a new install or run migrations from Ulmo or the current "main" branch, both of which have the same models/schema at the time of this writing (v0.30.2).

The new ``authoring`` app's initial migration will detect whether it is a new install or an update to an existing one and either create the tables or simply repoint the models to the existing schema. The next migration will rename the tables to have a common ``oel_authoring`` prefix.


4. The Bigger Picture
~~~~~~~~~~~~~~~~~~~~~

This practice means that the ``authoring`` Django app corresponds to a Subdomain in Domain Driven Design terminology, with each applet being a Bounded Context. We call these "Applets" instead of "Bounded Contexts" because we don't want it to get confused for Django's notion of Contexts and Context Processors (or Python's notion of Context Managers).
