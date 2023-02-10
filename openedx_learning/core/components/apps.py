from django.apps import AppConfig


class ComponentsConfig(AppConfig):
    """
    Configuration for the Components Django application.
    """

    name = "openedx_learning.core.components"
    verbose_name = "Learning Core: Components"
    default_auto_field = "django.db.models.BigAutoField"
