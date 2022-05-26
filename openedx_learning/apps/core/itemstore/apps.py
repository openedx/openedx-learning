from django.apps import AppConfig


class ItemStoreConfig(AppConfig):
    """
    Configuration for the publishing Django application.
    """
    name = "openedx_learning.apps.core.itemstore"
    verbose_name = "Learning Core: Item Store"
    default_auto_field = 'django.db.models.BigAutoField'
