"""
Test Django app config
"""

# pylint: disable=import-outside-toplevel
#
# Local imports in AppConfig.ready() are common and expected in Django, since
# Django needs to run initialization before before we can query for things like
# models, settings, and app config.

from django.apps import AppConfig


class TestAppConfig(AppConfig):
    """
    Configuration for the test Django application.
    """

    name = "tests.test_django_app"
    label = "test_django_app"

    def register_publishable_models(self):
        """
        Register all Publishable -> Version model pairings in our app.
        """
        from openedx_content.api import register_publishable_models

        from .models import (
            ContainerContainer,
            ContainerContainerVersion,
            TestContainer,
            TestContainerVersion,
            TestEntity,
            TestEntityVersion,
        )

        register_publishable_models(TestEntity, TestEntityVersion)
        register_publishable_models(TestContainer, TestContainerVersion)
        register_publishable_models(ContainerContainer, ContainerContainerVersion)

    def ready(self):
        """
        Currently used to register publishable models.

        May later be used to register signal handlers as well.
        """
        self.register_publishable_models()
