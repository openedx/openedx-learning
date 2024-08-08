"""
Basic tests of the Collections API.
"""
from datetime import datetime, timezone

from django.core.exceptions import ObjectDoesNotExist
from freezegun import freeze_time

from openedx_learning.apps.authoring.collections import api as collection_api
from openedx_learning.apps.authoring.collections.models import Collection
from openedx_learning.apps.authoring.publishing import api as publishing_api
from openedx_learning.apps.authoring.publishing.models import LearningPackage
from openedx_learning.lib.test_utils import TestCase


class CollectionTestCase(TestCase):
    """
    Base-class for setting up commonly used test data.
    """
    learning_package: LearningPackage
    now: datetime

    @classmethod
    def setUpTestData(cls) -> None:
        cls.learning_package = publishing_api.create_learning_package(
            key="ComponentTestCase-test-key",
            title="Components Test Case Learning Package",
        )
        cls.now = datetime(2024, 8, 5, tzinfo=timezone.utc)


class GetCollectionTestCase(CollectionTestCase):
    """
    Test grabbing a queryset of Collections.
    """
    collection1: Collection
    collection2: Collection
    disabled_collection: Collection

    @classmethod
    def setUpTestData(cls) -> None:
        """
        Initialize our content data (all our tests are read only).
        """
        super().setUpTestData()
        cls.collection1 = collection_api.create_collection(
            cls.learning_package.id,
            name="Collection 1",
            description="Description of Collection 1",
        )
        cls.collection2 = collection_api.create_collection(
            cls.learning_package.id,
            name="Collection 2",
            description="Description of Collection 2",
        )
        cls.disabled_collection = collection_api.create_collection(
            cls.learning_package.id,
            name="Disabled Collection",
            description="Description of Disabled Collection",
        )
        cls.disabled_collection.enabled = False
        cls.disabled_collection.save()

    def test_get_collection(self):
        """
        Test getting a single collection.
        """
        collection = collection_api.get_collection(self.collection1.pk)
        assert collection == self.collection1

    def test_get_collection_not_found(self):
        """
        Test getting a collection that doesn't exist.
        """
        with self.assertRaises(ObjectDoesNotExist):
            collection_api.get_collection(12345)

    def test_get_learning_package_collections(self):
        """
        Test getting all ENABLED collections for a learning package.
        """
        collections = collection_api.get_learning_package_collections(self.learning_package.id)
        assert list(collections) == [
            self.collection1,
            self.collection2,
        ]

    def test_get_invalid_learning_package_collections(self):
        """
        Test getting collections for an invalid learning package should return an empty queryset.
        """
        collections = collection_api.get_learning_package_collections(12345)
        assert not list(collections)


class CollectionCreateTestCase(CollectionTestCase):
    """
    Test creating a collection.
    """

    def test_create_collection(self):
        """
        Test creating a collection.
        """
        created_time = datetime(2024, 8, 8, tzinfo=timezone.utc)
        with freeze_time(created_time):
            collection = collection_api.create_collection(
                self.learning_package.id,
                name="My Collection",
                description="This is my collection",
            )

        assert collection.name == "My Collection"
        assert collection.description == "This is my collection"
        assert collection.enabled
        assert collection.created == created_time
        assert collection.modified == created_time

    def test_create_collection_without_description(self):
        """
        Test creating a collection without a description.
        """
        collection = collection_api.create_collection(
            self.learning_package.id,
            name="My Collection",
        )
        assert collection.name == "My Collection"
        assert collection.description == ""
        assert collection.enabled


class UpdateCollectionTestCase(CollectionTestCase):
    """
    Test updating a collection.
    """
    collection: Collection

    def setUp(self) -> None:
        """
        Initialize our content data
        """
        super().setUp()
        self.collection = collection_api.create_collection(
            self.learning_package.id,
            name="Collection",
            description="Description of Collection",
        )

    def test_update_collection(self):
        """
        Test updating a collection's name and description.
        """
        modified_time = datetime(2024, 8, 8, tzinfo=timezone.utc)
        with freeze_time(modified_time):
            collection = collection_api.update_collection(
                self.collection.pk,
                name="New Name",
                description="",
            )

        assert collection.name == "New Name"
        assert collection.description == ""
        assert collection.modified == modified_time
        assert collection.created == self.collection.created  # unchanged

    def test_update_collection_partial(self):
        """
        Test updating a collection's name.
        """
        collection = collection_api.update_collection(
            self.collection.pk,
            name="New Name",
        )

        assert collection.name == "New Name"
        assert collection.description == self.collection.description  # unchanged

    def test_update_collection_empty(self):
        """
        Test empty update.
        """
        modified_time = datetime(2024, 8, 8, tzinfo=timezone.utc)
        with freeze_time(modified_time):
            collection = collection_api.update_collection(
                self.collection.pk,
            )

        assert collection.name == self.collection.name  # unchanged
        assert collection.description == self.collection.description  # unchanged
        assert collection.modified == self.collection.modified  # unchanged

    def test_update_collection_not_found(self):
        """
        Test updating a collection that doesn't exist.
        """
        with self.assertRaises(ObjectDoesNotExist):
            collection_api.update_collection(12345, name="New Name")
