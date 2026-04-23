"""
Signals that are part of the public API of openedx_content.

Import these as e.g. `from openedx_content.api import signals` or as
`from openedx_content import api as content_api` -> `content_api.signals._____`

These signals may be moved into openedx_events at some point.
"""

# This intermediate file is necessary so we can (1) filter the applet .signals
# module exports using `__all__` (we don't want to import models like
# `LearningPackage` that happen to be used in our `signals.py` files), and (2)
# so we can still namespace these under `api.signals.____` (see `api.py` for
# details on why).

# These wildcard imports are okay because these api modules declare __all__
# to define which symbols are public.
# pylint: disable=wildcard-import
from .applets.collections.signals import *
from .applets.publishing.signals import *
