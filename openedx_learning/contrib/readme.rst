Contrib Package
===============

The ``contrib`` package holds Django apps that *could* be implemented in separate repos, but are bundled here because it's more convenient to do so.

Guidelines
----------

Nothing from ``lib`` or ``core`` should *ever* import from ``contrib``.
