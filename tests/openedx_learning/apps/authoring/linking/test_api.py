"""
Tests of the Linking app's python API
"""
from __future__ import annotations

from datetime import datetime, timezone

from openedx_learning.apps.authoring.components import api as components_api
from openedx_learning.apps.authoring.components.models import Component, ComponentType
from openedx_learning.apps.authoring.linking import api as linking_api
from openedx_learning.apps.authoring.linking.models import LearningContextLinksStatus, PublishableEntityLink
from openedx_learning.apps.authoring.publishing import api as publishing_api
from openedx_learning.apps.authoring.publishing.models import LearningPackage
from openedx_learning.lib.test_utils import TestCase


class EntityLinkingTestCase(TestCase):
    """
    Entity linking tests.
    """
    learning_package: LearningPackage
    now: datetime
    html_type: ComponentType
    html_component: Component

    @classmethod
    def setUpTestData(cls) -> None:
        cls.learning_package = publishing_api.create_learning_package(
            key="EntityLinkingTestCase-test-key",
            title="EntityLinking Test Case Learning Package",
        )
        cls.now = datetime(2023, 5, 8, tzinfo=timezone.utc)
        cls.html_type = components_api.get_or_create_component_type("xblock.v1", "html")
        cls.html_component, _ = components_api.create_component_and_version(
            cls.learning_package.id,
            component_type=cls.html_type,
            local_key="html_component",
            title="HTML 1",
            created=cls.now,
            created_by=None,
        )

    def test_get_or_create_learning_context_link_status(self) -> None:
        """
        Test get_or_create_learning_context_link_status api.
        """
        context_key = "test_context_key"
        assert not LearningContextLinksStatus.objects.filter(context_key=context_key).exists()
        linking_api.get_or_create_learning_context_link_status(context_key)
        assert LearningContextLinksStatus.objects.filter(context_key=context_key).exists()
        assert LearningContextLinksStatus.objects.filter(context_key=context_key).count() == 1
        # Should not create a new object
        linking_api.get_or_create_learning_context_link_status(context_key)
        assert LearningContextLinksStatus.objects.filter(context_key=context_key).count() == 1

    def test_update_or_create_entity_link(self) -> None:
        """
        Test update_or_create_entity_link.
        """
        downstream_usage_key = "test_downstream_usage_key"
        assert not PublishableEntityLink.objects.filter(downstream_usage_key=downstream_usage_key).exists()
        entity_args = {
            "upstream_usage_key": "test_upstream_usage_key",
            "upstream_context_key": "test_upstream_context_key",
            "downstream_usage_key": downstream_usage_key,
            "downstream_context_key": "test_downstream_context_key",
            "downstream_context_title": "test_downstream_context_key",
            "version_synced": 1,
        }
        # Should create new link
        link = linking_api.update_or_create_entity_link(self.html_component, **entity_args)  # type: ignore[arg-type]
        assert PublishableEntityLink.objects.filter(downstream_usage_key=downstream_usage_key).exists()
        prev_updated_time = link.updated
        # Using the api with same arguments should not make any changes
        link = linking_api.update_or_create_entity_link(self.html_component, **entity_args)  # type: ignore[arg-type]
        assert link.updated == prev_updated_time
        # update version_synced field
        link = linking_api.update_or_create_entity_link(
            self.html_component,
            **{**entity_args, "version_synced": 2}  # type: ignore[arg-type]
        )
        assert link.updated != prev_updated_time
        assert link.version_synced == 2

    def test_delete_entity_link(self) -> None:
        """
        Test delete entity link by downstream_usage_key
        """
        downstream_usage_key = "test_downstream_usage_key"
        entity_args = {
            "upstream_usage_key": "test_upstream_usage_key",
            "upstream_context_key": "test_upstream_context_key",
            "downstream_usage_key": downstream_usage_key,
            "downstream_context_key": "test_downstream_context_key",
            "downstream_context_title": "test_downstream_context_key",
            "version_synced": 1,
        }
        # Should create new link
        linking_api.update_or_create_entity_link(self.html_component, **entity_args)  # type: ignore[arg-type]
        assert PublishableEntityLink.objects.filter(downstream_usage_key=downstream_usage_key).exists()
        linking_api.delete_entity_link(downstream_usage_key)
        assert not PublishableEntityLink.objects.filter(downstream_usage_key=downstream_usage_key).exists()
