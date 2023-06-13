"""
tagging Django application initialization.
"""

from django.apps import AppConfig


class TaggingConfig(AppConfig):
    """
    Configuration for the tagging Django application.
    """

    name = "openedx_tagging.core.tagging"
    verbose_name = "Tagging"
    default_auto_field = "django.db.models.BigAutoField"
    label = "oel_tagging"
