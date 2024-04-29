16. Python Public API Conventions
=================================

Context
--------

OEP-49 lays out conventions for having `per-app API modules <https://docs.openedx.org/projects/openedx-proposals/en/latest/best-practices/oep-0049-django-app-patterns.html#api-py>`_, and we follow this module naming convention for apps in ``openedx_learning``. Unfortunately, this has a couple of drawbacks for Learning Core:

#. **Casual API consumers will have difficulty finding functions they need.** Learning Core apps tend to be smaller than what OEP-49 envisioned, meaning that we have more of them. This makes them easier to reason about individually during development, but cumbersome to casually scan through for the things you need. This will get worse over time, as we continue to add new apps.
#. **We will have less flexibility to refactor apps over time if API consumers import directly from each app.** We want to provide a more stable interface, but this repo will be undergoing heavy development in the coming years.

For these reasons, we should supplement OEP-49 recommendations with a more consumer-friendly API layer.

Decision
--------

In addition to OEP-49, we will adopt the following practices:

Learning Core Django apps will be grouped into packages.
  Apps in ``openedx_learning`` will be grouped into broadly related packages under ``openedx_learning.apps``. The first of these groups will be "authoring" (``openedx_learning.apps.authoring``). Future packages may include "learner", "personalization", "activity", "grading", etc.

Learning Core Django apps will continue to have their own ``api`` modules.
  So for example, ``openedx_learning.apps.authoring.components.api`` will continue to exist.

Learning Core will have a top level package for its public API.
  All public APIs intended for use by consumers of Learning Core will be represented as modules in the ``openedx_learning.api`` package that corresponds to the app groupings (e.g. ``openedx_learning.api.authoring``).

App ``api`` modules will define their public functions using ``__all__``.
  The public API modules will do a wildcard import from the various apps in their package group. So ``openedx_learning/api/authoring.py`` might look like::

    from ..apps.authoring.components.api import *
    from ..apps.authoring.contents.api import *
    from ..apps.authoring.publishing.api import *

  This relies on the individual apps to properly set ``__all__`` to the list of functions that they are willing to publicly support.

App ``api`` modules within a package of apps still import from each other.
  So for example, ``openedx_learning.apps.authoring.components.api`` will continue to import APIs that it needs from ``..publishing.api``, instead of using the public API at ``openedx_learning.api.authoring``. These imports should not use wildcards.

  Functions and constants that are not listed as part of a module's ``__all__`` may still be imported by other app APIs in the same package grouping. This should allow a package more flexibility to create provisional APIs that we may not want to support publicly.

  If a function or attribute is intended to be completely private to an app's ``api`` module (i.e. not used even by other apps in its package), it should be prefixed with an underscore.

App ``api`` modules should not import directly from apps outside their package.
  For example, ``openedx_learning.apps.personalization.api`` should import authoring API functions from ``openedx_learning.api.authoring``, **not** directly from something like ``openedx_learning.apps.authoring.components.api``. This will help to limit the impact of refactoring app package internal changes, as well as exposing shortcomings in the existing public APIs.

Public API modules may implement their own functions.
  In addition to aggregating app ``api`` modules via wildcard imports, public API modules like ``openedx_learning.api.authoring`` may implement their own functionality. This will be useful for convenience functions that invoke multiple app APIs, and for backwards compatibility shims. When possible, the bulk of the logic for these should continue to live in app-defined APIs, with the public API module acting more as a glue layer.

Importlinter will be used to enforce these restrictions.

Rejected Alternatives
---------------------

Public APIs in each app package

  We could have added these aggregations as ``api`` modules in each app group package, e.g. ``openedx_learning.apps.authoring.api``. Some reasons this was rejected:

  * It's more convenient for browsing and documentation generation to have the public API modules in the same package.
  * It's more idiomatic for Python libraries to expose their APIs in appropriately named modules (like ``authoring``), rather than all imported modules being named ``api``.
