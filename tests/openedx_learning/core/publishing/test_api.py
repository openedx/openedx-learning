from datetime import datetime, timezone
from uuid import UUID

from django.core.exceptions import ValidationError
from django.test import TestCase
import pytest

from openedx_learning.core.publishing.api import create_learning_package


class CreateLearningPackageTestCase(TestCase):
    def test_normal(self):
        """Normal flow with no errors."""
        key = "my_key"
        title = "My Excellent Title with Emoji 🔥"
        created = datetime(2023, 4, 2, 15, 9, 0, tzinfo=timezone.utc)
        package = create_learning_package(key, title, created)

        assert package.key == "my_key"
        assert package.title == "My Excellent Title with Emoji 🔥"
        assert package.created == created
        assert package.updated == created

        # Should be auto-generated
        assert isinstance(package.uuid, UUID)

        # Having an actual value here means we were persisted to the database.
        assert isinstance(package.id, int)

    def test_auto_datetime(self):
        """Auto-generated created datetime works as expected."""
        key = "my_key"
        title = "My Excellent Title with Emoji 🔥"
        package = create_learning_package(key, title)

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

    def test_non_utc_time(self):
        """Require UTC timezone for created."""
        with pytest.raises(ValidationError) as excinfo:
            create_learning_package("my_key", "A Title", datetime(2023, 4, 2))
        message_dict = excinfo.value.message_dict

        # Both datetime fields should be marked as invalid
        assert "created" in message_dict
        assert "updated" in message_dict

    def test_already_exists(self):
        """Raises ValidationError for duplicate keys."""
        create_learning_package("my_key", "Original")
        with pytest.raises(ValidationError) as excinfo:
            create_learning_package("my_key", "Duplicate")
        message_dict = excinfo.value.message_dict
        assert "key" in message_dict
