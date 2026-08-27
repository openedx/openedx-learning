"""
App Config for our umbrella openedx_learning app.
"""
from django.apps import AppConfig


class LearningConfig(AppConfig):
    """
    Initialization for all applets must happen in here.
    """

    name = "openedx_learning"
    verbose_name = "Open edX Core > Learning"
    default_auto_field = "django.db.models.BigAutoField"
    label = "openedx_learning"
