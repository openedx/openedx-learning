openedx-learning
=============================

|pypi-badge| |ci-badge| |codecov-badge| |doc-badge| |pyversions-badge|
|license-badge|

This is experimentation/prototyping and not in any way production ready!
------------------------------------------------------------------------

Overview
--------

The Open edX Learning repository holds Django apps that represent core learning concepts and data models that have been extracted from edx-platform.

Motivation
----------

The short term goal of this project is to create a small, extensible core that is easier to reason about and write extensions for than edx-platform. The longer term goal is to create a more nimble core learning platform, enabling rapid experimentation and drastic changes to the learner experience that are difficult to implement with Open edX today.

Replacing edx-platform is explicitly *not* a goal of this project, as only a small fraction of the concepts in edx-platform make sense to carry over here. When these core concepts are extracted and the data migrated, edx-platform will import apps from this repo and make use of their public in-process APIs.

Architecture
------------

Parts
~~~~~

* ``openedx_learning.lib`` is for shared utilities, and may include things like custom field types, plugin registration code, etc.
* ``openedx_learning.core`` contains our Core Django apps, where foundational data structures and APIs will live.
* ``openedx_tagging.core`` contains the core Tagging app, which provides data structures and apis for tagging Open edX objects.

App Dependencies
~~~~~~~~~~~~~~~~

Anything can import from ``openedx_learning.lib``.

Core apps can import from each other, but cannot import from other apps outside of core. For those apps:

* ``learning_publishing`` has no dependencies. All the other apps depend on it.
* ``learning_composition`` and ``learning_navigation`` both depend on ``learning_partitioning``

Model Conventions
~~~~~~~~~~~~~~~~~

We have a few different identifier types in the schema, and we try to avoid ``_id`` for this because Django uses that convention to reference IDs in other models/tables. So instead we have:

* ``id`` is the auto-generated, internal row ID and primary key. This never changes. Data models should make foreign keys to this field, as per Django convention.
* ``uuid`` is a randomly generated UUID4. This is the stable way to refer to a row/resource from an external service. This never changes. This is separate from ``id`` mostly because there are performance penalties when using UUIDs as primary keys with MySQL.
* ``key`` is intended to be a case-sensitive, alphanumeric key, which holds some meaning to library clients. This is usually stable, but can be changed, depending on the business logic of the client. The apps in this repo should make no assumptions about it being stable. It can be used as a suffix.
* ``num`` is like ``key``, but for use when it's strictly numeric. It can also be used as a suffix.


See Also
~~~~~~~~

The structure of this repo follows [OEP-0049](https://open-edx-proposals.readthedocs.io/en/latest/architectural-decisions/oep-0049-django-app-patterns.html) where possible, and also borrows inspiration from:

* [Scaling Django to 500 apps](https://2021.djangocon.us/talks/scaling-django-to-500-apps/) (Dan Palmer, DjangoCon US 2021)
* [Django structure for scale and longevity](https://www.youtube.com/watch?v=yG3ZdxBb1oo) (Radoslav Georgiev, EuroPython 2018)

Code Overview
-------------

The ``openedx_learning.apps`` package contains all our Django applications. All apps are named with a ``learning_`` prefix to better avoid name conflicts, because Django's app namespace is flat. Apps will adhere to `OEP-0049: Django App Patterns <https://open-edx-proposals.readthedocs.io/en/latest/architectural-decisions/oep-0049-django-app-patterns.html>`_.

Development Workflow
--------------------

One Time Setup
~~~~~~~~~~~~~~
.. code-block::

  # Clone the repository
  git clone git@github.com:ormsbee/openedx-learning.git
  cd openedx-learning

  # Set up a virtualenv using virtualenvwrapper with the same name as the repo and activate it
  mkvirtualenv -p python3.8 openedx-learning


Every time you develop something in this repo
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
.. code-block::

  # Activate the virtualenv
  workon openedx-learning

  # Grab the latest code
  git checkout master
  git pull

  # Install/update the dev requirements
  make requirements

  # Run the tests and quality checks (to verify the status before you make any changes)
  make validate

  # Make a new branch for your changes
  git checkout -b <your_github_username>/<short_description>

  # Using your favorite editor, edit the code to make your change.
  vim …

  # Run your new tests
  pytest ./path/to/new/tests

  # Run all the tests and quality checks
  make validate

  # Commit all your changes
  git commit …
  git push

  # Open a PR and ask for review.

License
-------

The code in this repository is licensed under the AGPL 3.0 unless otherwise noted.

Please see `LICENSE.txt <LICENSE.txt>`_ for details.

How To Contribute
-----------------

This repo is in a very experimental state. Discussion using GitHub Issues is welcome, but you probably don't want to make contributions as everything can shift around drastically with little notice.

Reporting Security Issues
-------------------------

Please do not report security issues in public. Please email security@openedx.org.

Help
----

If you're having trouble, we have discussion forums at https://discuss.openedx.org where you can connect with others in the community.

Our real-time conversations are on Slack. You can request a `Slack invitation`_, then join our `community Slack workspace`_.

For more information about these options, see the `Getting Help`_ page.

.. _Slack invitation: https://openedx.org/slack
.. _community Slack workspace: https://openedx.slack.com/
.. _Getting Help: https://openedx.org/getting-help

.. |pypi-badge| image:: https://img.shields.io/pypi/v/openedx-learning.svg
    :target: https://pypi.python.org/pypi/openedx-learning/
    :alt: PyPI

.. |ci-badge| image:: https://github.com/openedx/openedx-learning/workflows/Python%20CI/badge.svg?branch=master
    :target: https://github.com/openedx/openedx-learning/actions
    :alt: CI

.. |codecov-badge| image:: https://codecov.io/github/edx/openedx-learning/coverage.svg?branch=master
    :target: https://codecov.io/github/edx/openedx-learning?branch=master
    :alt: Codecov

.. |doc-badge| image:: https://readthedocs.org/projects/openedx-learning/badge/?version=latest
    :target: https://openedx-learning.readthedocs.io/en/latest/
    :alt: Documentation

.. |pyversions-badge| image:: https://img.shields.io/pypi/pyversions/openedx-learning.svg
    :target: https://pypi.python.org/pypi/openedx-learning/
    :alt: Supported Python versions

.. |license-badge| image:: https://img.shields.io/github/license/edx/openedx-learning.svg
    :target: https://github.com/openedx/openedx-learning/blob/master/LICENSE.txt
    :alt: License
