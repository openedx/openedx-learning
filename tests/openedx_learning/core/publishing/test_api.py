"""
Tests of the Publishing app's python API
"""
from datetime import datetime, timezone
from uuid import UUID

import pytest
from django.core.exceptions import ValidationError

from openedx_learning.core.publishing import api as publishing_api
from openedx_learning.core.publishing.models import LearningPackage
from openedx_learning.lib.test_utils import TestCase


class CreateLearningPackageTestCase(TestCase):
    """
    Test creating a LearningPackage
    """
    def test_normal(self) -> None:  # Note: we must specify '-> None' to opt in to type checking
        """
        Normal flow with no errors.
        """
        key = "my_key"
        title = "My Excellent Title with Emoji 🔥"
        created = datetime(2023, 4, 2, 15, 9, 0, tzinfo=timezone.utc)
        description = "A fun Description!"
        package = publishing_api.create_learning_package(
            key=key,
            title=title,
            description=description,
            created=created
        )

        assert package.key == "my_key"
        assert package.title == "My Excellent Title with Emoji 🔥"
        assert package.created == created
        assert package.updated == created

        # Should be auto-generated
        assert isinstance(package.uuid, UUID)

        # Having an actual value here means we were persisted to the database.
        assert isinstance(package.id, int)

    def test_auto_datetime(self) -> None:
        """
        Auto-generated created datetime works as expected.
        """
        key = "my_key"
        title = "My Excellent Title with Emoji 🔥"
        package = publishing_api.create_learning_package(key, title)

        assert package.key == "my_key"
        assert package.title == "My Excellent Title with Emoji 🔥"

        # Auto-generated datetime checking...
        assert isinstance(package.created, datetime)
        assert package.created == package.updated
        assert package.created.tzinfo == timezone.utc

        # Should be auto-generated
        assert isinstance(package.uuid, UUID)

        # Having an actual value here means we were persisted to the database.
        assert isinstance(package.id, int)

    def test_non_utc_time(self) -> None:
        """
        Require UTC timezone for created.
        """
        with pytest.raises(ValidationError) as excinfo:
            publishing_api.create_learning_package(
                key="my_key",
                title="A Title",
                created=datetime(2023, 4, 2)
            )
        message_dict = excinfo.value.message_dict

        # Both datetime fields should be marked as invalid
        assert "created" in message_dict
        assert "updated" in message_dict

    def test_already_exists(self) -> None:
        """
        Raises ValidationError for duplicate keys.
        """
        publishing_api.create_learning_package("my_key", "Original")
        with pytest.raises(ValidationError) as excinfo:
            publishing_api.create_learning_package("my_key", "Duplicate")
        message_dict = excinfo.value.message_dict
        assert "key" in message_dict


class DraftTestCase(TestCase):
    """
    Test basic operations with Drafts.
    """
    now: datetime
    learning_package: LearningPackage

    @classmethod
    def setUpTestData(cls) -> None:
        cls.now = datetime(2024, 1, 28, 16, 45, 30, tzinfo=timezone.utc)
        cls.learning_package = publishing_api.create_learning_package(
            "my_package_key",
            "Draft Testing LearningPackage 🔥",
            created=cls.now,
        )

    def test_draft_lifecycle(self):
        """
        Test basic lifecycle of a Draft.
        """
        entity = publishing_api.create_publishable_entity(
            self.learning_package.id,
            "my_entity",
            created=self.now,
            created_by=None,
        )
        # Drafts are NOT created when a PublishableEntity is created, only when
        # its first PublisahbleEntityVersion is.
        assert publishing_api.get_draft_version(entity.id) is None

        entity_version = publishing_api.create_publishable_entity_version(
            entity_id=entity.id,
            version_num=1,
            title="An Entity 🌴",
            created=self.now,
            created_by=None,
        )
        assert entity_version == publishing_api.get_draft_version(entity.id)

        # We never really remove rows from the table holding Drafts. We just
        # mark the version as None.
        publishing_api.set_draft_version(entity.id, None)
        entity_version = publishing_api.get_draft_version(entity.id)
        assert entity_version is None

    def test_reset_drafts_to_published(self):
        """
        Test throwing out Draft data and resetting to the Published versions.

        One place this might turn up is if we've imported an older version of
        the library and it causes a bunch of new versions to be created.
        """

