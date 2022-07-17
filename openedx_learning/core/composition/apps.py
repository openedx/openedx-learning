"""
Composition App Configuration
"""

from django.apps import AppConfig


class CompositionConfig(AppConfig):
    """
    Configuration for the publishing Django application.
    """
    name = "openedx_learning.core.composition"
    verbose_name = "Learning Core: Composition"
    default_auto_field = 'django.db.models.BigAutoField'
