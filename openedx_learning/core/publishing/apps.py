"""
publishing Django application initialization.
"""

from django.apps import AppConfig


class PublishingConfig(AppConfig):
    """
    Configuration for the publishing Django application.
    """

    name = "openedx_learning.core.publishing"
    verbose_name = "Learning Core: Publishing"
    default_auto_field = "django.db.models.BigAutoField"
    label = "oel_publishing"
