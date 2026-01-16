"""
App Config for our umbrella authoring app.
"""
from django.apps import AppConfig


class AuthoringConfig(AppConfig):
    """
    Initialization for all applets must happen in here.
    """

    name = "openedx_learning.apps.authoring"
    verbose_name = "Learning Core > Authoring"
    default_auto_field = "django.db.models.BigAutoField"
    label = "oel_authoring"

    def ready(self):
        """
        Currently used to register nitialize publishable models.

        May later be used to register signal handlers as well.
        """
        # Local imports in AppConfig.ready() are common and expected in Django,
        # since you can't import models at the top level without an error.
        #
        # pylint: disable=import-outside-toplevel
        from .api import register_publishable_models
        from .models import (
            Component, ComponentVersion,
            Container, ContainerVersion,
            Section, SectionVersion,
            Subsection, SubsectionVersion,
            Unit, UnitVersion,
        )
        register_publishable_models(Component, ComponentVersion)
        register_publishable_models(Container, ContainerVersion)
        register_publishable_models(Section, SectionVersion)
        register_publishable_models(Subsection, SubsectionVersion)
        register_publishable_models(Unit, UnitVersion)
