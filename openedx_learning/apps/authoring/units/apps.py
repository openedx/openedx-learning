"""
Unit Django application initialization.
"""

from django.apps import AppConfig


class UnitsConfig(AppConfig):
    """
    Configuration for the units Django application.
    """

    name = "openedx_learning.apps.authoring.units"
    verbose_name = "Learning Core > Authoring > Units"
    default_auto_field = "django.db.models.BigAutoField"
    label = "oel_units"

    def ready(self):
        """
        Register Unit and UnitVersion.
        """
        from ..publishing.api import register_content_models  # pylint: disable=import-outside-toplevel
        from .models import Unit, UnitVersion  # pylint: disable=import-outside-toplevel

        register_content_models(Unit, UnitVersion)
