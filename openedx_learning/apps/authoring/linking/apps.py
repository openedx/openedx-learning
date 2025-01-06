"""
linking Django application initialization.
"""

from django.apps import AppConfig


class LinkingConfig(AppConfig):
    """
    Configuration for the linking Django application.
    """

    name = "openedx_learning.apps.authoring.linking"
    verbose_name = "Learning Core > Authoring > Linking"
    default_auto_field = "django.db.models.BigAutoField"
    label = "oel_linking"
