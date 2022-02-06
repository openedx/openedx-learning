"""
publishing Django application initialization.
"""

from django.apps import AppConfig


class PartitioningConfig(AppConfig):
    """
    Configuration for the publishing Django application.
    """
    name = "openedx_learning.apps.core.learning_partitioning"
    verbose_name = "Learning Core: Partitioning"
    default_auto_field = 'django.db.models.BigAutoField'
