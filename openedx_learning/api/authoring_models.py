"""
This is where we expose a small handful of models and model mixins that we want
callers to extend or make foreign keys to. Callers importing this module should
never instantiate any of the models themselves–there are API functions in
authoring.py to create and modify data models in a way that keeps those models
consistent.
"""
# These wildcard imports are okay because these modules declare __all__.
# pylint: disable=wildcard-import
from ..apps.authoring.applets.collections.models import *
from ..apps.authoring.applets.components.models import *
from ..apps.authoring.applets.contents.models import *
from ..apps.authoring.applets.publishing.models import *
from ..apps.authoring.applets.sections.models import *
from ..apps.authoring.applets.subsections.models import *
from ..apps.authoring.applets.units.models import *
