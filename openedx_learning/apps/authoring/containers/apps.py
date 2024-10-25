"""
Containers Django application initialization.
"""

from django.apps import AppConfig


class ContainersConfig(AppConfig):
    """
    Configuration for the containers Django application.
    """

    name = "openedx_learning.apps.authoring.containers"
    verbose_name = "Learning Core > Authoring > Containers"
    default_auto_field = "django.db.models.BigAutoField"
    label = "oel_containers"


    def ready(self):
        """
        Register Component and ComponentVersion.
        """
        from ..publishing.api import register_content_models  # pylint: disable=import-outside-toplevel
        from .models import ContainerEntity, ContainerEntityVersion  # pylint: disable=import-outside-toplevel

        register_content_models(ContainerEntity, ContainerEntityVersion)
