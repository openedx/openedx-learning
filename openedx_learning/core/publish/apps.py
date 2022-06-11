"""
publishing Django application initialization.
"""

from django.apps import AppConfig


class PublishConfig(AppConfig):
    """
    Configuration for the publishing Django application.
    """
    name = "openedx_learning.core.publish"
    verbose_name = "Learning Core: Publish"
    default_auto_field = 'django.db.models.BigAutoField'
