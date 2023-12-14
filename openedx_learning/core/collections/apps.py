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
        from ..publishing.signals import PUBLISHED_PRE_COMMIT
        from . import handlers

        PUBLISHED_PRE_COMMIT.connect(
            handlers.update_collections_from_publish,
            dispatch_uid="oel__collections__update_collections_from_publish",
        )
