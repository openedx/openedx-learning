"""
Tests of the Publishing app's python API
"""
from __future__ import annotations

from datetime import datetime, timezone, tzinfo
from uuid import UUID

import pytest
from django.core.exceptions import ValidationError

from openedx_learning.core.publishing import api as publishing_api
from openedx_learning.core.publishing.models import LearningPackage, PublishableEntity
from openedx_learning.lib.test_utils import TestCase


class LearningPackageTestCase(TestCase):
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
        assert package.description == "A fun Description!"
        assert package.created == created
        assert package.updated == created

        # Should be auto-generated
        assert isinstance(package.uuid, UUID)

        # Having an actual value here means we were persisted to the database.
        assert isinstance(package.id, int)

        # Now test editing the fields.
        updated_package = publishing_api.update_learning_package(
            package.id,
            key="new_key",
            title="new title",
            description="new description",
        )
        assert updated_package.key == "new_key"
        assert updated_package.title == "new title"
        assert updated_package.description == "new description"
        assert updated_package.created == created
        assert updated_package.updated != created  # new time would be auto-generated

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

    def test_draft_lifecycle(self) -> None:
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
            entity.id,
            version_num=1,
            title="An Entity 🌴",
            created=self.now,
            created_by=None,
        )
        assert entity_version == publishing_api.get_draft_version(entity.id)

        # We never really remove rows from the table holding Drafts. We just
        # mark the version as None.
        publishing_api.soft_delete_draft(entity.id)
        deleted_entity_version = publishing_api.get_draft_version(entity.id)
        assert deleted_entity_version is None

    def test_reset_drafts_to_published(self) -> None:
        """
        Test throwing out Draft data and resetting to the Published versions.

        One place this might turn up is if we've imported an older version of
        the library and it causes a bunch of new versions to be created.

        Note that these tests don't associate any content with the versions
        being created. They don't have to, because making those content
        associations is the job of the ``components`` package, and potentially
        other higher-level things. We're never deleting ``PublishableEntity``
        or ``PublishableEntityVersion`` instances, so we don't have to worry
        about potentially breaking the associated models of those higher level
        apps. These tests just need to ensure that the Published and Draft
        models are updated properly to point to the correct versions.

        This could be broken up into separate tests for each scenario, but I
        wanted to make sure nothing went wrong when multiple types of reset were
        happening at the same time.
        """
        # This is the Entity that's going to get a couple of new versions
        # between Draft and Published.
        entity_with_changes = publishing_api.create_publishable_entity(
            self.learning_package.id,
            "entity_with_changes",
            created=self.now,
            created_by=None,
        )
        publishing_api.create_publishable_entity_version(
            entity_with_changes.id,
            version_num=1,
            title="I'm entity_with_changes v1",
            created=self.now,
            created_by=None,
        )

        # This Entity is going to remain unchanged between Draft and Published.
        entity_with_no_changes = publishing_api.create_publishable_entity(
            self.learning_package.id,
            "entity_with_no_changes",
            created=self.now,
            created_by=None,
        )
        publishing_api.create_publishable_entity_version(
            entity_with_no_changes.id,
            version_num=1,
            title="I'm entity_with_no_changes v1",
            created=self.now,
            created_by=None,
        )

        # This Entity will be Published, but will then be soft-deleted.
        entity_with_pending_delete = publishing_api.create_publishable_entity(
            self.learning_package.id,
            "entity_with_pending_delete",
            created=self.now,
            created_by=None,
        )
        publishing_api.create_publishable_entity_version(
            entity_with_pending_delete.id,
            version_num=1,
            title="I'm entity_with_pending_delete v1",
            created=self.now,
            created_by=None,
        )

        # Publish!
        publishing_api.publish_all_drafts(self.learning_package.id)

        # Create versions 2, 3, 4 of entity_with_changes. After this, the
        # Published version is 1 and the Draft version is 4.
        for version_num in range(2, 5):
            publishing_api.create_publishable_entity_version(
                entity_with_changes.id,
                version_num=version_num,
                title=f"I'm entity_with_changes v{version_num}",
                created=self.now,
                created_by=None,
            )

        # Soft-delete entity_with_pending_delete. After this, the Published
        # version is 1 and the Draft version is None.
        publishing_api.soft_delete_draft(entity_with_pending_delete.id)

        # Create a new entity that only exists in Draft form (no Published
        # version).
        new_entity = publishing_api.create_publishable_entity(
            self.learning_package.id,
            "new_entity",
            created=self.now,
            created_by=None,
        )
        publishing_api.create_publishable_entity_version(
            new_entity.id,
            version_num=1,
            title="I'm new_entity v1",
            created=self.now,
            created_by=None,
        )

        # The versions we expect in (entity, published version_num, draft
        # version_num) tuples.
        expected_pre_reset_state = [
            (entity_with_changes, 1, 4),
            (entity_with_no_changes, 1, 1),
            (entity_with_pending_delete, 1, None),
            (new_entity, None, 1),
        ]
        for entity, pub_version_num, draft_version_num in expected_pre_reset_state:
            # Make sure we grab a new copy from the database so we're not
            # getting stale cached values:
            assert pub_version_num == self._get_published_version_num(entity)
            assert draft_version_num == self._get_draft_version_num(entity)

        # Now reset to draft here!
        publishing_api.reset_drafts_to_published(self.learning_package.id)

        # Versions we expect after reset in (entity, published version num)
        # tuples. The only entity that is not version 1 is the new one.
        expected_post_reset_state = [
            (entity_with_changes, 1),
            (entity_with_no_changes, 1),
            (entity_with_pending_delete, 1),
            (new_entity, None),
        ]
        for entity, pub_version_num in expected_post_reset_state:
            assert (
                self._get_published_version_num(entity) ==
                self._get_draft_version_num(entity) ==
                pub_version_num
            )

    def _get_published_version_num(self, entity: PublishableEntity) -> int | None:
        published_version = publishing_api.get_published_version(entity.id)
        if published_version is not None:
            return published_version.version_num
        return None

    def _get_draft_version_num(self, entity: PublishableEntity) -> int | None:
        draft_version = publishing_api.get_draft_version(entity.id)
        if draft_version is not None:
            return draft_version.version_num
        return None
