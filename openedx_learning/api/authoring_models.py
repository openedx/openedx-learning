"""
This is where we expose a small handful of models and model mixins that we want
callers to extend or make foreign keys to. Callers importing this module should
never instantiate any of the models themselves–there are API functions in
authoring.py to create and modify data models in a way that keeps those models
consistent.
"""
# These wildcard imports are okay because these modules declare __all__.
# pylint: disable=wildcard-import
from ..apps.authoring.collections.models import *
from ..apps.authoring.components.models import *
from ..apps.authoring.contents.models import *
from ..apps.authoring.publishing.model_mixins import *
from ..apps.authoring.publishing.models import *
