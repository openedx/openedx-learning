"""
Django app metadata for the Media Server application.
"""
from django.apps import AppConfig
from django.core.exceptions import ImproperlyConfigured
from django.conf import settings


class MediaServerConfig(AppConfig):
    """
    Configuration for the Media Server application.
    """

    name = "openedx_learning.contrib.media_server"
    verbose_name = "Learning Core: Media Server"
    default_auto_field = "django.db.models.BigAutoField"

    def ready(self):
        if not settings.DEBUG:
            # Until we get proper security and support for running this app
            # under a separate domain, just don't allow it to be run in
            # production environments.
            raise ImproperlyConfigured(
                "The media_server app should only be run in DEBUG mode!"
            )
