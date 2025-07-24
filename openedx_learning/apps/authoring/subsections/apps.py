"""
Subsection Django application initialization.
"""

from django.apps import AppConfig


class SubsectionsConfig(AppConfig):
    """
    Configuration for the subsections Django application.
    """

    name = "openedx_learning.apps.authoring.subsections"
    verbose_name = "Learning Core > Authoring > Subsections"
    default_auto_field = "django.db.models.BigAutoField"
    label = "oel_subsections"

    def ready(self):
        """
        Register Subsection and SubsectionVersion.
        """
        from ..publishing.api import register_publishable_models  # pylint: disable=import-outside-toplevel
        from .models import Subsection, SubsectionVersion  # pylint: disable=import-outside-toplevel

        register_publishable_models(Subsection, SubsectionVersion)
