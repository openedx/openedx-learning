"""
Basic tests of the Collections API.
"""
from datetime import datetime, timezone

from django.contrib.auth import get_user_model
from django.core.exceptions import ObjectDoesNotExist, ValidationError
from freezegun import freeze_time

# Ensure our APIs and models are all exported to the package API.
from openedx_learning.api import authoring as api
from openedx_learning.api.authoring_models import (
    Collection,
    CollectionPublishableEntity,
    LearningPackage,
    PublishableEntity,
    PublishableEntityVersion,
)
from openedx_learning.lib.test_utils import TestCase

User = get_user_model()


class CollectionTestCase(TestCase):
    """
    Base-class for setting up commonly used test data.
    """
    learning_package: LearningPackage
    learning_package_2: LearningPackage
    now: datetime

    @classmethod
    def setUpTestData(cls) -> None:
        cls.learning_package = api.create_learning_package(
            key="ComponentTestCase-test-key",
            title="Components Test Case Learning Package",
        )
        cls.learning_package_2 = api.create_learning_package(
            key="ComponentTestCase-test-key-2",
            title="Components Test Case another Learning Package",
        )
        cls.now = datetime(2024, 8, 5, tzinfo=timezone.utc)


class CollectionsTestCase(CollectionTestCase):
    """
    Base class with a bunch of collections pre-created.
    """
    collection1: Collection
    collection2: Collection
    collection3: Collection
    disabled_collection: Collection

    @classmethod
    def setUpTestData(cls) -> None:
        """
        Initialize our content data (all our tests are read only).
        """
        super().setUpTestData()
        cls.collection1 = api.create_collection(
            cls.learning_package.id,
            key="COL1",
            created_by=None,
            title="Collection 1",
            description="Description of Collection 1",
        )
        cls.collection2 = api.create_collection(
            cls.learning_package.id,
            key="COL2",
            created_by=None,
            title="Collection 2",
            description="Description of Collection 2",
        )
        cls.collection3 = api.create_collection(
            cls.learning_package_2.id,
            key="COL3",
            created_by=None,
            title="Collection 3",
            description="Description of Collection 3",
        )
        cls.disabled_collection = api.create_collection(
            cls.learning_package.id,
            key="COL4",
            created_by=None,
            title="Disabled Collection",
            description="Description of Disabled Collection",
            enabled=False,
        )


class GetCollectionTestCase(CollectionsTestCase):
    """
    Test grabbing a queryset of Collections.
    """
    def test_get_collection(self):
        """
        Test getting a single collection.
        """
        collection = api.get_collection(self.learning_package.pk, 'COL1')
        assert collection == self.collection1

    def test_get_collection_not_found(self):
        """
        Test getting a collection that doesn't exist.
        """
        with self.assertRaises(ObjectDoesNotExist):
            api.get_collection(self.learning_package.pk, '12345')

    def test_get_collection_wrong_learning_package(self):
        """
        Test getting a collection that doesn't exist in the requested learning package.
        """
        with self.assertRaises(ObjectDoesNotExist):
            api.get_collection(self.learning_package.pk, self.collection3.key)

    def test_get_collections(self):
        """
        Test getting all ENABLED collections for a learning package.
        """
        collections = api.get_collections(self.learning_package.id)
        assert list(collections) == [
            self.collection1,
            self.collection2,
        ]

    def test_get_invalid_collections(self):
        """
        Test getting collections for an invalid learning package should return an empty queryset.
        """
        collections = api.get_collections(12345)
        assert not list(collections)

    def test_get_all_collections(self):
        """
        Test getting all collections.
        """
        collections = api.get_collections(self.learning_package.id, enabled=None)
        self.assertQuerySetEqual(collections, [
            self.collection1,
            self.collection2,
            self.disabled_collection,
        ], ordered=True)

    def test_get_all_enabled_collections(self):
        """
        Test getting all ENABLED collections.
        """
        collections = api.get_collections(self.learning_package.id, enabled=True)
        self.assertQuerySetEqual(collections, [
            self.collection1,
            self.collection2,
        ], ordered=True)

    def test_get_all_disabled_collections(self):
        """
        Test getting all DISABLED collections.
        """
        collections = api.get_collections(self.learning_package.id, enabled=False)
        assert list(collections) == [self.disabled_collection]


class CollectionCreateTestCase(CollectionTestCase):
    """
    Test creating a collection.
    """

    def test_create_collection(self):
        """
        Test creating a collection.
        """
        user = User.objects.create(
            username="user",
            email="user@example.com",
        )
        created_time = datetime(2024, 8, 8, tzinfo=timezone.utc)
        with freeze_time(created_time):
            collection = api.create_collection(
                self.learning_package.id,
                key='MYCOL',
                title="My Collection",
                created_by=user.id,
                description="This is my collection",
            )

        assert collection.title == "My Collection"
        assert collection.key == "MYCOL"
        assert collection.description == "This is my collection"
        assert collection.enabled
        assert collection.created == created_time
        assert collection.modified == created_time
        assert collection.created_by == user

    def test_create_collection_without_description(self):
        """
        Test creating a collection without a description.
        """
        collection = api.create_collection(
            self.learning_package.id,
            key='MYCOL',
            created_by=None,
            title="My Collection",
        )
        assert collection.title == "My Collection"
        assert collection.key == "MYCOL"
        assert collection.description == ""
        assert collection.enabled


class CollectionEntitiesTestCase(CollectionsTestCase):
    """
    Test collections that contain publishable entitites.
    """
    published_entity: PublishableEntity
    pe_version: PublishableEntityVersion
    draft_entity: PublishableEntity
    de_version: PublishableEntityVersion
    user: User  # type: ignore [valid-type]

    @classmethod
    def setUpTestData(cls) -> None:
        """
        Initialize our content data
        """
        super().setUpTestData()

        cls.user = User.objects.create(
            username="user",
            email="user@example.com",
        )

        # Make and Publish one PublishableEntity
        cls.published_entity = api.create_publishable_entity(
            cls.learning_package.id,
            key="my_entity_published_example",
            created=cls.now,
            created_by=cls.user.id,
        )
        cls.pe_version = api.create_publishable_entity_version(
            cls.published_entity.id,
            version_num=1,
            title="An Entity that we'll Publish 🌴",
            created=cls.now,
            created_by=cls.user.id,
        )
        api.publish_all_drafts(
            cls.learning_package.id,
            message="Publish from CollectionTestCase.setUpTestData",
            published_at=cls.now,
        )

        # Create two Draft PublishableEntities, one in each learning package
        cls.draft_entity = api.create_publishable_entity(
            cls.learning_package.id,
            key="my_entity_draft_example",
            created=cls.now,
            created_by=cls.user.id,
        )
        cls.de_version = api.create_publishable_entity_version(
            cls.draft_entity.id,
            version_num=1,
            title="An Entity that we'll keep in Draft 🌴",
            created=cls.now,
            created_by=cls.user.id,
        )

        # Add some shared entities to the collections
        cls.collection1 = api.add_to_collection(
            cls.learning_package.id,
            key=cls.collection1.key,
            entities_qset=PublishableEntity.objects.filter(id__in=[
                cls.published_entity.id,
            ]),
            created_by=cls.user.id,
        )
        cls.collection2 = api.add_to_collection(
            cls.learning_package.id,
            key=cls.collection2.key,
            entities_qset=PublishableEntity.objects.filter(id__in=[
                cls.published_entity.id,
                cls.draft_entity.id,
            ]),
        )
        cls.disabled_collection = api.add_to_collection(
            cls.learning_package.id,
            key=cls.disabled_collection.key,
            entities_qset=PublishableEntity.objects.filter(id__in=[
                cls.published_entity.id,
            ]),
        )

    def test_create_collection_entities(self):
        """
        Ensure the collections were pre-populated with the expected publishable entities.
        """
        assert list(self.collection1.entities.all()) == [
            self.published_entity,
        ]
        assert list(self.collection2.entities.all()) == [
            self.published_entity,
            self.draft_entity,
        ]
        assert not list(self.collection3.entities.all())

    def test_add_to_collection(self):
        """
        Test adding entities to collections.
        """
        modified_time = datetime(2024, 8, 8, tzinfo=timezone.utc)
        with freeze_time(modified_time):
            self.collection1 = api.add_to_collection(
                self.learning_package.id,
                self.collection1.key,
                PublishableEntity.objects.filter(id__in=[
                    self.draft_entity.id,
                ]),
                created_by=self.user.id,
            )

        assert list(self.collection1.entities.all()) == [
            self.published_entity,
            self.draft_entity,
        ]
        for collection_entity in CollectionPublishableEntity.objects.filter(collection=self.collection1):
            assert collection_entity.created_by == self.user
        assert self.collection1.modified == modified_time

    def test_add_to_collection_again(self):
        """
        Test that re-adding entities to a collection doesn't throw an error.
        """
        modified_time = datetime(2024, 8, 8, tzinfo=timezone.utc)
        with freeze_time(modified_time):
            self.collection2 = api.add_to_collection(
                self.learning_package.id,
                self.collection2.key,
                PublishableEntity.objects.filter(id__in=[
                    self.published_entity.id,
                ]),
            )

        assert list(self.collection2.entities.all()) == [
            self.published_entity,
            self.draft_entity,
        ]
        assert self.collection2.modified == modified_time

    def test_add_to_collection_wrong_learning_package(self):
        """
        We cannot add entities to a collection from a different learning package.
        """
        with self.assertRaises(ValidationError):
            api.add_to_collection(
                self.learning_package_2.id,
                self.collection3.key,
                PublishableEntity.objects.filter(id__in=[
                    self.published_entity.id,
                ]),
            )

        assert not list(self.collection3.entities.all())

    def test_remove_from_collection(self):
        """
        Test removing entities from a collection.
        """
        modified_time = datetime(2024, 8, 8, tzinfo=timezone.utc)
        with freeze_time(modified_time):
            self.collection2 = api.remove_from_collection(
                self.learning_package.id,
                self.collection2.key,
                PublishableEntity.objects.filter(id__in=[
                    self.published_entity.id,
                ]),
            )

        assert list(self.collection2.entities.all()) == [
            self.draft_entity,
        ]
        assert self.collection2.modified == modified_time

    def test_get_entity_collections(self):
        """
        Tests fetching the enabled collections which contain a given entity.
        """
        collections = api.get_entity_collections(
            self.learning_package.id,
            self.published_entity.key,
        )
        assert list(collections) == [
            self.collection1,
            self.collection2,
        ]


class UpdateCollectionTestCase(CollectionTestCase):
    """
    Test updating a collection.
    """
    collection: Collection

    @classmethod
    def setUpTestData(cls) -> None:
        """
        Initialize our content data
        """
        super().setUpTestData()
        cls.collection = api.create_collection(
            cls.learning_package.id,
            key="MYCOL",
            title="Collection",
            created_by=None,
            description="Description of Collection",
        )

    def test_update_collection(self):
        """
        Test updating a collection's title and description.
        """
        modified_time = datetime(2024, 8, 8, tzinfo=timezone.utc)
        with freeze_time(modified_time):
            collection = api.update_collection(
                self.learning_package.id,
                key=self.collection.key,
                title="New Title",
                description="",
            )

        assert collection.title == "New Title"
        assert collection.description == ""
        assert collection.modified == modified_time
        assert collection.created == self.collection.created  # unchanged

    def test_update_collection_partial(self):
        """
        Test updating a collection's title.
        """
        collection = api.update_collection(
            self.learning_package.id,
            key=self.collection.key,
            title="New Title",
        )

        assert collection.title == "New Title"
        assert collection.description == self.collection.description  # unchanged
        assert f"{collection}" == f"<Collection> (lp:{self.learning_package.id} {self.collection.key}:New Title)"

        collection = api.update_collection(
            self.learning_package.id,
            key=self.collection.key,
            description="New description",
        )

        assert collection.title == "New Title"  # unchanged
        assert collection.description == "New description"

    def test_update_collection_empty(self):
        """
        Test empty update.
        """
        modified_time = datetime(2024, 8, 8, tzinfo=timezone.utc)
        with freeze_time(modified_time):
            collection = api.update_collection(
                self.learning_package.id,
                key=self.collection.key,
            )

        assert collection.title == self.collection.title  # unchanged
        assert collection.description == self.collection.description  # unchanged
        assert collection.modified == self.collection.modified  # unchanged

    def test_update_collection_not_found(self):
        """
        Test updating a collection that doesn't exist.
        """
        with self.assertRaises(ObjectDoesNotExist):
            api.update_collection(
                self.learning_package.id,
                key="12345",
                title="New Title",
            )
