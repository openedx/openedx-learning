from django.apps import AppConfig


class ComponentsConfig(AppConfig):
    """
    Configuration for the Components Django application.
    """

    name = "openedx_learning.core.components"
    verbose_name = "Learning Core: Components"
    default_auto_field = "django.db.models.BigAutoField"
    label = "oel_components"

    def ready(self):
        """
        Register Component and ComponentVersion.
        """
        from ..publishing.api import register_content_models
        from .models import Component, ComponentVersion

        register_content_models(Component, ComponentVersion)
