"""
Sections Django application initialization.
"""

from django.apps import AppConfig


class SectionsConfig(AppConfig):
    """
    Configuration for the Sections Django application.
    """

    name = "openedx_learning.apps.authoring.sections"
    verbose_name = "Learning Core > Authoring > Sections"
    default_auto_field = "django.db.models.BigAutoField"
    label = "oel_sections"

    def ready(self):
        """
        Register Section and SectionVersion.
        """
        from ..publishing.api import register_publishable_models  # pylint: disable=import-outside-toplevel
        from .models import Section, SectionVersion  # pylint: disable=import-outside-toplevel

        register_publishable_models(Section, SectionVersion)
