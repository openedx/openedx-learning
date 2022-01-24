"""
publishing Django application initialization.
"""

from django.apps import AppConfig


class PublishingConfig(AppConfig):
    """
    Configuration for the publishing Django application.
    """
    name = 'openedx_learning.apps.learning_publishing'
    verbose_name = 'Learning Core: Content Publishing'