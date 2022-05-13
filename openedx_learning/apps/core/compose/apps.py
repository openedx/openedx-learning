"""
publishing Django application initialization.
"""

from django.apps import AppConfig


class ComposeConfig(AppConfig):
    """
    Configuration for the publishing Django application.
    """
    name = "openedx_learning.apps.core.compose"
    verbose_name = "Learning Core: Compose"
    default_auto_field = 'django.db.models.BigAutoField'
