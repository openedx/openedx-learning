"""
Subsection Django application initialization.
"""

from django.apps import AppConfig


class SectionsConfig(AppConfig):
    """
    Configuration for the subsections Django application.
    """

    name = "openedx_learning.apps.authoring.sections"
    verbose_name = "Learning Core > Authoring > Sections"
    default_auto_field = "django.db.models.BigAutoField"
    label = "oel_sections"

    def ready(self):
        """
        Register Subsection and SubsectionVersion.
        """
        from ..publishing.api import register_content_models  # pylint: disable=import-outside-toplevel
        from .models import Section, SectionVersion  # pylint: disable=import-outside-toplevel

        register_content_models(Section, SectionVersion)
