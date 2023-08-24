"""
Django metadata for the Learning Core REST API app
"""
from django.apps import AppConfig


class RESTAPIConfig(AppConfig):
    """
    Configuration for the Learning Core REST API Django app.
    """

    name = "openedx_learning.rest_api"
    verbose_name = "Learning Core: REST API"
    default_auto_field = "django.db.models.BigAutoField"
