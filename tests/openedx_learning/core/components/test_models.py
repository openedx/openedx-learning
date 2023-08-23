"""
Tests related to the Component models
"""
from datetime import datetime, timezone

from django.test.testcases import TestCase

from openedx_learning.core.components.api import create_component_and_version
from openedx_learning.core.publishing.api import LearningPackage, create_learning_package, publish_all_drafts


class TestModelVersioningQueries(TestCase):
    """
    Test that Component/ComponentVersion are registered with the publishing app.
    """
    learning_package: LearningPackage
    now: datetime

    @classmethod
    def setUpTestData(cls) -> None:  # Note: we must specify '-> None' to opt in to type checking
        cls.learning_package = create_learning_package(
            "components.TestVersioning",
            "Learning Package for Testing Component Versioning",
        )
        cls.now = datetime(2023, 5, 8, tzinfo=timezone.utc)

    def test_latest_version(self) -> None:
        component, component_version = create_component_and_version(
            learning_package_id=self.learning_package.id,
            namespace="xblock.v1",
            type="problem",
            local_key="monty_hall",
            title="Monty Hall Problem",
            created=self.now,
            created_by=None,
        )
        assert component.versioning.draft == component_version
        assert component.versioning.published is None
        publish_all_drafts(self.learning_package.pk, published_at=self.now)

        # Force the re-fetch from the database
        assert component.versioning.published == component_version

        # Grabbing the list of versions for this component
        assert list(component.versioning.versions) == [component_version]
