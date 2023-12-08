"""
Django metadata for the Collections Django application.
"""
from django.apps import AppConfig


class CollectionsConfig(AppConfig):
    """
    Configuration for the Collections Django application.
    """

    name = "openedx_learning.core.collections"
    verbose_name = "Learning Core: Collections"
    default_auto_field = "django.db.models.BigAutoField"
    label = "oel_collections"

    def ready(self):
        """
        Register the ComponentCollection, ComponentCollectionVersion relation.
        """
        #from ..publishing.api import register_content_models  # pylint: disable=import-outside-toplevel
        #from .models import ComponentCollection, ComponentCollectionVersion  # pylint: disable=import-outside-toplevel

        #register_content_models(ComponentCollection, ComponentCollectionVersion)
