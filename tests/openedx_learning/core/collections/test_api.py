"""
Tests of the Collection app's python API
"""
from datetime import datetime, timezone
from uuid import UUID

from django.core.exceptions import ValidationError

from openedx_learning.core.collections import api as collections_api
from openedx_learning.core.publishing import api as publishing_api
from openedx_learning.core.publishing.models import PublishableEntity

from openedx_learning.lib.test_utils import TestCase


class CollectionsTestCase(TestCase):
    """
    Test creating Collections
    """
    @classmethod
    def setUpTestData(cls) -> None:
        super().setUpTestData()
        cls.created = datetime(2023, 12, 7, 18, 23, 50, tzinfo=timezone.utc)
        cls.package = publishing_api.create_learning_package(
            "collections_test_learning_pkg_key",
            "Collections Testing LearningPackage 🔥",
            created=cls.created,
        )

        # Make and Publish one PublishableEntity
        cls.published_entity = publishing_api.create_publishable_entity(
            cls.package.id,
            "my_entity_published_example",
            cls.created,
            created_by=None,
        )
        cls.pe_version = publishing_api.create_publishable_entity_version(
            entity_id=cls.published_entity.id,
            version_num=1,
            title="An Entity that we'll Publish 🌴",
            created=cls.created,
            created_by=None,
        )
        publishing_api.publish_all_drafts(
            cls.package.id,
            message="Publish from CollectionsTestCase.setUpTestData",
            published_at=cls.created,
        )

        # Leave another PublishableEntity in Draft.
        cls.draft_entity = publishing_api.create_publishable_entity(
            cls.package.id,
            "my_entity_draft_example",
            cls.created,
            created_by=None,
        )
        cls.de_version = publishing_api.create_publishable_entity_version(
            entity_id=cls.draft_entity.id,
            version_num=1,
            title="An Entity that we'll keep in Draft 🌴",
            created=cls.created,
            created_by=None,
        )

    def test_bootstrap_only_published(self) -> None:
        """
        Normal flow with no errors.
        """
        collection = collections_api.create_collection(
            self.package.id,
            key="test_bootstrap_only_published_collection",
            title="Test Bootstrap 🦃 Only Published Collection",
            pub_entities_qset=PublishableEntity.objects.filter(
                id=self.published_entity.id
            ),
            created=self.created,
        )
        entities = list(collection.publishable_entities.all())
        assert len(entities) == 1
