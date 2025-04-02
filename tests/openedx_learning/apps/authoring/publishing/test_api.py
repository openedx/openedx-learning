"""
Tests of the Publishing app's python API
"""
from __future__ import annotations

from datetime import datetime, timezone
from uuid import UUID

import pytest
from django.core.exceptions import ValidationError

from openedx_learning.apps.authoring.publishing import api as publishing_api
from openedx_learning.apps.authoring.publishing.models import (
    DraftChangeLog,
    DraftSideEffect,
    LearningPackage,
    PublishableEntity, 
)
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
        assert package.created.tzinfo == timezone.utc  # pylint: disable=no-member,useless-suppression

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
    learning_package_1: LearningPackage

    @classmethod
    def setUpTestData(cls) -> None:
        cls.now = datetime(2024, 1, 28, 16, 45, 30, tzinfo=timezone.utc)
        cls.learning_package_1 = publishing_api.create_learning_package(
            "my_package_key_1",
            "Draft Testing LearningPackage 🔥 1",
            created=cls.now,
        )
        cls.learning_package_2 = publishing_api.create_learning_package(
            "my_package_key_2",
            "Draft Testing LearningPackage 🔥 2",
            created=cls.now,
        )

    def test_simple_draft_changeset(self) -> None:
        with publishing_api.bulk_draft_changes_for(self.learning_package_1.id):
            entity = publishing_api.create_publishable_entity(
                self.learning_package_1.id,
                "my_entity",
                created=self.now,
                created_by=None,
            )
            publishing_api.create_publishable_entity_version(
                entity.id,
                version_num=1,
                title="An Entity 🌴",
                created=self.now,
                created_by=None,
            )
            entity2 = publishing_api.create_publishable_entity(
                self.learning_package_1.id,
                "my_entity2",
                created=self.now,
                created_by=None,
            )
            publishing_api.create_publishable_entity_version(
                entity2.id,
                version_num=1,
                title="An Entity 🌴 2",
                created=self.now,
                created_by=None,
            )
        draft_sets = list(DraftChangeLog.objects.all())
        assert len(draft_sets) == 1
        assert len(draft_sets[0].records.all()) == 2

        # Now that we're outside of the context manager, check that we're making
        # a new DraftChangeSet...
        entity3 = publishing_api.create_publishable_entity(
            self.learning_package_1.id,
            "my_entity3",
            created=self.now,
            created_by=None,
        )
        publishing_api.create_publishable_entity_version(
            entity3.id,
            version_num=1,
            title="An Entity 🌴 3",
            created=self.now,
            created_by=None,
        )
        draft_sets = list(DraftChangeLog.objects.all().order_by('id'))
        assert len(draft_sets) == 2
        assert len(draft_sets[1].records.all()) == 1

    def test_nested_draft_changesets(self) -> None:
        pass

    def test_multiple_draft_changes(self) -> None:
        """
        Test that multiple changes to the same entity are collapsed.
        """
        with publishing_api.bulk_draft_changes_for(self.learning_package_1.id):
            entity = publishing_api.create_publishable_entity(
                self.learning_package_1.id,
                "my_entity",
                created=self.now,
                created_by=None,
            )
            publishing_api.create_publishable_entity_version(
                entity.id,
                version_num=1,
                title="An Entity 🌴 v1",
                created=self.now,
                created_by=None,
            )
            publishing_api.create_publishable_entity_version(
                entity.id,
                version_num=2,
                title="An Entity 🌴 v2",
                created=self.now,
                created_by=None,
            )
        draft_sets = list(DraftChangeLog.objects.all().order_by('id'))
        assert len(draft_sets) == 1
        changes = list(draft_sets[0].records.all())
        assert len(changes) == 1
        assert changes[0].old_version is None
        assert changes[0].new_version.version_num == 2

    def test_draft_lifecycle(self) -> None:
        """
        Test basic lifecycle of a Draft.
        """
        entity = publishing_api.create_publishable_entity(
            self.learning_package_1.id,
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

    def test_soft_deletes(self) -> None:
        """Test the publishing behavior of soft deletes."""
        entity = publishing_api.create_publishable_entity(
            self.learning_package_1.id,
            "my_entity",
            created=self.now,
            created_by=None,
        )
        entity_version = publishing_api.create_publishable_entity_version(
            entity.id,
            version_num=1,
            title="An Entity 🌴",
            created=self.now,
            created_by=None,
        )

        # Initial publish
        publish_log = publishing_api.publish_all_drafts(self.learning_package_1.id)
        log_records = list(publish_log.records.all())
        assert len(log_records) == 1
        record = log_records[0]
        assert record.entity_id == entity.id
        assert record.old_version is None
        assert record.new_version_id == entity_version.id

        # Publishing the soft-delete
        publishing_api.soft_delete_draft(entity.id)
        publish_log = publishing_api.publish_all_drafts(self.learning_package_1.id)
        log_records = list(publish_log.records.all())
        assert len(log_records) == 1
        record = log_records[0]
        assert record.entity_id == entity.id
        assert record.old_version_id == entity_version.id
        assert record.new_version is None

        # Verify that we do not re-publish soft-deleted records. We initially
        # had a bug here because NULL != NULL in SQL, so the check to "publish
        # all the Drafts that have different versions than their Published
        # counterparts" would mistakenly pull in records that were NULL in both
        # places.
        publish_log = publishing_api.publish_all_drafts(self.learning_package_1.id)
        assert publish_log.records.count() == 0

    def test_soft_delete_and_reset(self) -> None:
        """
        Test edge case where we create, soft-delete, and then reset.

        This is an edge case because creating and then soft-deleting an item
        sequence of actions will make both the Draft and Published version NULL.
        In this situation reset_drafts_to_published should NOT create a
        DraftChangeLog (because they already match, so there's nothing to do).
        But we had a bug that redundantly set the Draft version to NULL again
        because NULL != NULL in SQL and we were doing the Draft vs. Published
        comparison naively without taking that into account.
        """
        entity = publishing_api.create_publishable_entity(
            self.learning_package_1.id,
            "my_entity",
            created=self.now,
            created_by=None,
        )
        # Draft Change #1: create the new version
        publishing_api.create_publishable_entity_version(
            entity.id,
            version_num=1,
            title="An Entity 🌴",
            created=self.now,
            created_by=None,
        )
        assert DraftChangeLog.objects.count() == 1

        # Change #1: delete the draft (set the draft version to None)
        publishing_api.soft_delete_draft(entity.id)
        assert DraftChangeLog.objects.count() == 2

        # This should NOT create a change:
        publishing_api.reset_drafts_to_published(self.learning_package_1.id)
        assert DraftChangeLog.objects.count() == 2

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
            self.learning_package_1.id,
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
            self.learning_package_1.id,
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
            self.learning_package_1.id,
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
        publishing_api.publish_all_drafts(self.learning_package_1.id)

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
            self.learning_package_1.id,
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
        publishing_api.reset_drafts_to_published(self.learning_package_1.id)

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

    def test_reset_drafts_to_published_bulk(self) -> None:
        """bulk_draft_changes_for creates only one DraftChangeLog."""
        with publishing_api.bulk_draft_changes_for(self.learning_package_1.id):
            self.test_reset_drafts_to_published()
        assert DraftChangeLog.objects.count() == 1

    def test_get_entities_with_unpublished_changes(self) -> None:
        """Test fetching entities with unpublished changes after soft deletes."""
        entity = publishing_api.create_publishable_entity(
            self.learning_package_1.id,
            "my_entity",
            created=self.now,
            created_by=None,
        )
        publishing_api.create_publishable_entity_version(
            entity.id,
            version_num=1,
            title="An Entity 🌴",
            created=self.now,
            created_by=None,
        )

        # Fetch unpublished entities
        entities = publishing_api.get_entities_with_unpublished_changes(self.learning_package_1.id)
        records = list(entities.all())
        assert len(records) == 1
        record = records[0]
        assert record.id == entity.id

        # Initial publish
        publishing_api.publish_all_drafts(self.learning_package_1.id)

        # soft-delete entity
        publishing_api.soft_delete_draft(entity.id)
        entities = publishing_api.get_entities_with_unpublished_changes(self.learning_package_1.id)
        assert len(entities) == 0
        entities = publishing_api.get_entities_with_unpublished_changes(self.learning_package_1.id,
                                                                        include_deleted_drafts=True)
        assert len(entities) == 1

        # publish soft-delete
        publishing_api.publish_all_drafts(self.learning_package_1.id)
        entities = publishing_api.get_entities_with_unpublished_changes(self.learning_package_1.id,
                                                                        include_deleted_drafts=True)
        # should not return published soft-deleted entities.
        assert len(entities) == 0

    def test_filter_publishable_entities(self) -> None:
        count_published = 7
        count_drafts = 6
        count_no_drafts = 3

        for index in range(count_published):
            # Create entities to publish
            entity = publishing_api.create_publishable_entity(
                self.learning_package_1.id,
                f"entity_published_{index}",
                created=self.now,
                created_by=None,
            )

            publishing_api.create_publishable_entity_version(
                entity.id,
                version_num=1,
                title=f"Entity_published_{index}",
                created=self.now,
                created_by=None,
            )

        publishing_api.publish_all_drafts(self.learning_package_1.id)

        for index in range(count_drafts):
            # Create entities with drafts
            entity = publishing_api.create_publishable_entity(
                self.learning_package_1.id,
                f"entity_draft_{index}",
                created=self.now,
                created_by=None,
            )

            publishing_api.create_publishable_entity_version(
                entity.id,
                version_num=1,
                title=f"Entity_draft_{index}",
                created=self.now,
                created_by=None,
            )

        for index in range(count_no_drafts):
            # Create entities without drafts
            entity = publishing_api.create_publishable_entity(
                self.learning_package_1.id,
                f"entity_no_draft_{index}",
                created=self.now,
                created_by=None,
            )

        drafts = publishing_api.filter_publishable_entities(
            PublishableEntity.objects.all(),
            has_draft=True,
        )
        assert drafts.count() == (count_published + count_drafts)

        no_drafts = publishing_api.filter_publishable_entities(
            PublishableEntity.objects.all(),
            has_draft=False,
        )
        assert no_drafts.count() == count_no_drafts

        published = publishing_api.filter_publishable_entities(
            PublishableEntity.objects.all(),
            has_published=True,
        )
        assert published.count() == count_published

        no_published = publishing_api.filter_publishable_entities(
            PublishableEntity.objects.all(),
            has_published=False,
        )
        assert no_published.count() == (count_drafts + count_no_drafts)

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


class ContainerTestCase(TestCase):
    """
    Test basic operations with Drafts.
    """
    now: datetime
    learning_package: LearningPackage

    @classmethod
    def setUpTestData(cls) -> None:
        cls.now = datetime(2024, 1, 28, 16, 45, 30, tzinfo=timezone.utc)
        cls.learning_package = publishing_api.create_learning_package(
            "containers_package_key",
            "Container Testing LearningPackage 🔥 1",
            created=cls.now,
        )

    def test_parent_child_side_effects(self) -> None:
        """Test that modifying a child has side-effects on its parent."""
        child_1 = publishing_api.create_publishable_entity(
            self.learning_package.id,
            "child_1",
            created=self.now,
            created_by=None, 
        )
        child_1_v1 = publishing_api.create_publishable_entity_version(
            child_1.id,
            version_num=1,
            title="Child 1 🌴",
            created=self.now,
            created_by=None,
        )
        child_2 = publishing_api.create_publishable_entity(
            self.learning_package.id,
            "child_2",
            created=self.now,
            created_by=None,
        )
        publishing_api.create_publishable_entity_version(
            child_2.id,
            version_num=1,
            title="Child 2 🌴",
            created=self.now,
            created_by=None,
        )
        container = publishing_api.create_container(
            self.learning_package.id,
            "my_container",
            created=self.now,
            created_by=None,
        )
        container_v1 = publishing_api.create_container_version(
            container.pk,
            1,
            title="My Container",
            publishable_entities_pks=[child_1.id, child_2.id],
            entity_version_pks=None,
            created=self.now,
            created_by=None,
        )

        # All this was just set up. Now that we have our container-child
        # relationships, altering a child should add the parent container to
        # the DraftChangeLog.
        child_1_v2 = publishing_api.create_publishable_entity_version(
            child_1.id,
            version_num=2,
            title="Child 1 v2",
            created=self.now,
            created_by=None,
        )
        last_change_log = DraftChangeLog.objects.order_by('-id').first()
        assert last_change_log.records.count() == 2
        child_1_change = last_change_log.records.get(entity=child_1)
        assert child_1_change.old_version == child_1_v1
        assert child_1_change.new_version == child_1_v2
        
        # The container should be here, but the versions should be the same for
        # before and after:
        container_change = last_change_log.records.get(
            entity=container.publishable_entity
        )
        assert container_change.old_version == container_v1.publishable_entity_version
        assert container_change.new_version == container_v1.publishable_entity_version

        # Exactly one side-effect should have been created because we changed
        # child_1 after it was part of a container.
        side_effects = DraftSideEffect.objects.all()
        assert side_effects.count() == 1
        side_effect = side_effects.first()
        assert side_effect.cause == child_1_change
        assert side_effect.effect == container_change


    def test_bulk_parent_child_side_effects(self) -> None:
        """Test that modifying a child has side-effects on its parent. (bulk version)"""
        with publishing_api.bulk_draft_changes_for(self.learning_package.id):
            child_1 = publishing_api.create_publishable_entity(
                self.learning_package.id,
                "child_1",
                created=self.now,
                created_by=None, 
            )
            child_1_v1 = publishing_api.create_publishable_entity_version(
                child_1.id,
                version_num=1,
                title="Child 1 🌴",
                created=self.now,
                created_by=None,
            )
            child_2 = publishing_api.create_publishable_entity(
                self.learning_package.id,
                "child_2",
                created=self.now,
                created_by=None,
            )
            child_2_v1 = publishing_api.create_publishable_entity_version(
                child_2.id,
                version_num=1,
                title="Child 2 🌴",
                created=self.now,
                created_by=None,
            )
            container = publishing_api.create_container(
                self.learning_package.id,
                "my_container",
                created=self.now,
                created_by=None,
            )
            container_v1 = publishing_api.create_container_version(
                container.pk,
                1,
                title="My Container",
                publishable_entities_pks=[child_1.id, child_2.id],
                entity_version_pks=None,
                created=self.now,
                created_by=None,
            )

            # All this was just set up. Now that we have our container-child
            # relationships, altering a child should add the parent container to
            # the DraftChangeLog.
            child_1_v2 = publishing_api.create_publishable_entity_version(
                child_1.id,
                version_num=2,
                title="Child 1 v2",
                created=self.now,
                created_by=None,
            )

        # Because we're doing it in bulk, there's only one DraftChangeLog entry.
        assert DraftChangeLog.objects.count() == 1
        last_change_log = DraftChangeLog.objects.first()
        # There's only ever one change entry per publishable entity
        assert last_change_log.records.count() == 3

        child_1_change = last_change_log.records.get(entity=child_1)
        assert child_1_change.old_version == None
        assert child_1_change.new_version == child_1_v2

        child_2_change = last_change_log.records.get(entity=child_2)
        assert child_2_change.old_version == None
        assert child_2_change.new_version == child_2_v1

        container_change = last_change_log.records.get(
            entity=container.publishable_entity
        )
        assert container_change.old_version == None
        assert container_change.new_version == container_v1.publishable_entity_version

        # There are two side effects here, because we grouped our draft edits
        # together using bulk_draft_changes_for, so changes to both children
        # count towards side-effects on the container.
        side_effects = DraftSideEffect.objects.all()
        assert side_effects.count() == 2
        caused_by_child_1 = side_effects.get(cause=child_1_change)
        caused_by_child_2 = side_effects.get(cause=child_2_change)
        assert caused_by_child_1.effect == container_change
        assert caused_by_child_2.effect == container_change

    def test_multiple_layers_of_containers(self):
        """Test stacking containers three layers deep."""
        pass
