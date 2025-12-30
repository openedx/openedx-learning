"""
Django metadata for the Contents Django application.
"""
from django.apps import AppConfig


class ContentsConfig(AppConfig):
    """
    Configuration for the Contents Django application.
    """

    name = "openedx_learning.apps.authoring.media"
    verbose_name = "Learning Core > Authoring > Media"
    default_auto_field = "django.db.models.BigAutoField"
    label = "oel_contents"
