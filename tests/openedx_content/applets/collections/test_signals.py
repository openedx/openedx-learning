"""
Tests for the COLLECTION_CHANGED signal.
"""

from datetime import datetime, timezone

import pytest
from django.db import transaction

from openedx_content import api
from openedx_content.applets.collections.signals import COLLECTION_CHANGED, CollectionChangeData
from openedx_content.models_api import Collection, LearningPackage, PublishableEntity
from tests.utils import abort_transaction, capture_events

pytestmark = pytest.mark.django_db(transaction=True)
now_time = datetime.now(tz=timezone.utc)


@pytest.fixture(name="lp1")
def _lp1() -> LearningPackage:
    """A learning package for use across collection signal tests."""
    return api.create_learning_package(package_ref="lp1", title="Test LP 📦")


def _create_entity(learning_package_id: LearningPackage.ID, entity_ref: str) -> PublishableEntity:
    """Helper: create a bare PublishableEntity in the given learning package."""
    return api.create_publishable_entity(learning_package_id, entity_ref=entity_ref, created=now_time, created_by=None)


# COLLECTION_CHANGED — create_collection


def test_create_collection(lp1: LearningPackage, admin_user) -> None:
    """
    Test that COLLECTION_CHANGED is emitted with created=True
    when a new collection is created.
    """
    with capture_events(expected_count=1) as captured:
        collection = api.create_collection(
            lp1.id,
            collection_code="col1",
            title="Collection 1",
            created_by=admin_user.id,
        )

    event = captured[0]
    assert event.signal is COLLECTION_CHANGED
    assert event.kwargs["learning_package"].id == lp1.id
    assert event.kwargs["learning_package"].title == "Test LP 📦"
    assert event.kwargs["changed_by"].user_id == admin_user.id
    assert event.kwargs["change"] == CollectionChangeData(
        collection_id=collection.id,
        collection_code="col1",
        created=True,
    )
    collection.refresh_from_db()
    # Note: unfortunately collection.modified is slightly different than collection.created
    # (see https://code.djangoproject.com/ticket/16745). It would be nice if we made them exactly the same.
    assert event.kwargs["metadata"].time == collection.modified


def test_create_collection_disabled(lp1: LearningPackage) -> None:
    """
    Test that no event is emitted when a collection is created with enabled=False.

    A disabled collection is invisible to consumers, so there is nothing to notify about.
    """
    with capture_events(expected_count=0):
        api.create_collection(
            lp1.id,
            collection_code="col1",
            title="Collection 1",
            created_by=None,
            enabled=False,
        )

    # And if that disabled collection is deleted, no event is emitted. We don't want to emit a deleted event for a
    # collection that never had a created event.
    with capture_events(expected_count=0):
        api.delete_collection(lp1.id, collection_code="col1", hard_delete=True)


def test_create_collection_disabled_then_enabled(lp1: LearningPackage) -> None:
    """
    Test that no event is emitted when a collection is created already soft
    deleted (with enabled=False), but IS emitted when we enable/un-delete it.
    """
    with capture_events(expected_count=0):
        collection = api.create_collection(
            lp1.id,
            collection_code="col1",
            title="Collection 1",
            created_by=None,
            enabled=False,
        )

    # Enabling (un-deleting) that collection will result in a "created" event:
    with capture_events(expected_count=1) as captured:
        api.restore_collection(lp1.id, collection_code="col1")  # FIXME: we can't specify a user here.

    event = captured[0]
    assert event.signal is COLLECTION_CHANGED
    assert event.kwargs["learning_package"].id == lp1.id
    assert event.kwargs["changed_by"].user_id is None
    assert event.kwargs["change"] == CollectionChangeData(
        collection_id=collection.id,
        collection_code="col1",
        created=True,
    )


def test_create_collection_aborted(lp1: LearningPackage) -> None:
    """
    Test that no event is emitted when a collection creation is rolled back.
    """
    with capture_events(expected_count=0):
        with abort_transaction():
            api.create_collection(
                lp1.id,
                collection_code="col1",
                title="Collection 1",
                created_by=None,
            )


# COLLECTION_CHANGED — update_collection


def test_update_collection(lp1: LearningPackage) -> None:
    """
    Test that COLLECTION_CHANGED is emitted with metadata_modified=True
    when a collection's title or description is updated.
    """
    collection = api.create_collection(lp1.id, "col1", title="Collection 1", created_by=None)
    orig_modified = collection.modified

    with capture_events(expected_count=1) as captured:
        api.update_collection(lp1.id, "col1", title="Updated Title")

    event = captured[0]
    assert event.signal is COLLECTION_CHANGED
    assert event.kwargs["learning_package"].id == lp1.id
    assert event.kwargs["change"] == CollectionChangeData(
        collection_id=collection.id,
        collection_code="col1",
        metadata_modified=True,
    )
    collection.refresh_from_db()
    assert collection.modified > orig_modified
    assert event.kwargs["metadata"].time == collection.modified


def test_update_collection_no_op(lp1: LearningPackage) -> None:
    """
    Test that COLLECTION_CHANGED is NOT emitted when
    update_collection is called without any fields to update.
    """
    api.create_collection(lp1.id, "col1", title="Collection 1", created_by=None)

    with capture_events(expected_count=0):
        # No title or description provided — the API short-circuits with no DB write.
        api.update_collection(lp1.id, "col1")


# COLLECTION_CHANGED — delete_collection


def test_delete_collection_soft(lp1: LearningPackage) -> None:
    """
    Test that COLLECTION_CHANGED is emitted with deleted=True
    when a collection is soft-deleted (enabled=False).
    """
    collection = api.create_collection(lp1.id, "col1", title="Collection 1", created_by=None)
    entity1 = _create_entity(lp1.id, "entity1")
    entity2 = _create_entity(lp1.id, "entity2")
    api.add_to_collection(
        lp1.id,
        "col1",
        PublishableEntity.objects.filter(id__in=[entity1.id, entity2.id]),
    )

    with capture_events(expected_count=1) as captured:
        api.delete_collection(lp1.id, "col1")

    event = captured[0]
    assert event.signal is COLLECTION_CHANGED
    assert event.kwargs["learning_package"].id == lp1.id
    assert event.kwargs["change"] == CollectionChangeData(
        collection_id=collection.id,
        collection_code="col1",
        deleted=True,
        entities_removed=sorted([entity1.id, entity2.id]),
    )


def test_delete_collection_hard(lp1: LearningPackage) -> None:
    """
    Test that COLLECTION_CHANGED is emitted with deleted=True and
    entities_removed populated when a collection is hard-deleted.
    """
    collection = api.create_collection(lp1.id, "col1", title="Collection 1", created_by=None)
    entity1 = _create_entity(lp1.id, "entity1")
    entity2 = _create_entity(lp1.id, "entity2")
    api.add_to_collection(
        lp1.id,
        "col1",
        PublishableEntity.objects.filter(id__in=[entity1.id, entity2.id]),
    )

    collection_id = collection.id  # Capture before deletion

    with capture_events(expected_count=1) as captured:
        api.delete_collection(lp1.id, "col1", hard_delete=True)

    event = captured[0]
    assert event.signal is COLLECTION_CHANGED
    assert event.kwargs["learning_package"].id == lp1.id
    assert event.kwargs["change"] == CollectionChangeData(
        collection_id=collection_id,
        collection_code="col1",
        deleted=True,
        entities_removed=sorted([entity1.id, entity2.id]),
    )


# COLLECTION_CHANGED — restore_collection


def test_restore_collection(lp1: LearningPackage) -> None:
    """
    Test that COLLECTION_CHANGED is emitted with created=True
    when a soft-deleted collection is restored.
    """
    collection = api.create_collection(lp1.id, "col1", title="Collection 1", created_by=None)
    api.delete_collection(lp1.id, "col1")  # soft-delete first

    with capture_events(expected_count=1) as captured:
        api.restore_collection(lp1.id, "col1")

    event = captured[0]
    assert event.signal is COLLECTION_CHANGED
    assert event.kwargs["learning_package"].id == lp1.id
    assert event.kwargs["change"] == CollectionChangeData(
        collection_id=collection.id,
        collection_code="col1",
        created=True,
    )


# COLLECTION_CHANGED — add_to_collection


def test_add_to_collection(lp1: LearningPackage) -> None:
    """
    Test that COLLECTION_CHANGED is emitted with the correct
    entities_added list when entities are added to a collection.
    """
    collection = api.create_collection(lp1.id, "col1", title="Collection 1", created_by=None)
    entity1 = _create_entity(lp1.id, "entity1")
    entity2 = _create_entity(lp1.id, "entity2")

    with capture_events(expected_count=1) as captured:
        api.add_to_collection(
            lp1.id,
            "col1",
            PublishableEntity.objects.filter(id__in=[entity1.id, entity2.id]),
        )

    event = captured[0]
    assert event.signal is COLLECTION_CHANGED
    assert event.kwargs["learning_package"].id == lp1.id
    assert event.kwargs["change"] == CollectionChangeData(
        collection_id=collection.id,
        collection_code="col1",
        entities_added=sorted([entity1.id, entity2.id]),
    )


def test_add_to_collection_aborted(lp1: LearningPackage) -> None:
    """
    Test that no event is emitted when adding entities to a collection is rolled back.
    """
    api.create_collection(lp1.id, "col1", title="Collection 1", created_by=None)
    entity1 = _create_entity(lp1.id, "entity1")

    with capture_events(expected_count=0):
        with abort_transaction():
            api.add_to_collection(
                lp1.id,
                "col1",
                PublishableEntity.objects.filter(id=entity1.id),
            )


# COLLECTION_CHANGED — remove_from_collection


def test_remove_from_collection(lp1: LearningPackage) -> None:
    """
    Test that COLLECTION_CHANGED is emitted with the correct
    entities_removed list when entities are removed from a collection.
    """
    collection = api.create_collection(lp1.id, "col1", title="Collection 1", created_by=None)
    entity1 = _create_entity(lp1.id, "entity1")
    entity2 = _create_entity(lp1.id, "entity2")
    api.add_to_collection(
        lp1.id,
        "col1",
        PublishableEntity.objects.filter(id__in=[entity1.id, entity2.id]),
    )

    with capture_events(expected_count=1) as captured:
        api.remove_from_collection(
            lp1.id,
            "col1",
            PublishableEntity.objects.filter(id=entity1.id),
        )

    event = captured[0]
    assert event.signal is COLLECTION_CHANGED
    assert event.kwargs["learning_package"].id == lp1.id
    assert event.kwargs["change"] == CollectionChangeData(
        collection_id=collection.id,
        collection_code="col1",
        entities_removed=[entity1.id],
    )


# COLLECTION_CHANGED — set_collections


def test_set_collections(lp1: LearningPackage, admin_user) -> None:
    """
    Test that COLLECTION_CHANGED is emitted once per affected
    collection when set_collections reassigns an entity's collections.

    In this scenario entity starts in col1+col2, then is moved to col2+col3.
    We expect two events: one for col1 (entity removed) and one for col3 (entity added).
    col2 is unchanged so it should not emit an event.
    """
    col1 = api.create_collection(lp1.id, "col1", title="Collection 1", created_by=None)
    col2 = api.create_collection(lp1.id, "col2", title="Collection 2", created_by=None)
    col3 = api.create_collection(lp1.id, "col3", title="Collection 3", created_by=None)
    entity = _create_entity(lp1.id, "entity1")

    # Put entity in col1 + col2 to start with
    api.set_collections(entity, Collection.objects.filter(id__in=[col1.id, col2.id]))

    # Reassign: entity goes into col2 + col3 (col1 removed, col3 added)
    with capture_events(expected_count=2) as captured:
        api.set_collections(entity, Collection.objects.filter(id__in=[col2.id, col3.id]), created_by=admin_user.id)

    events_by_collection = {e.kwargs["change"].collection_id: e for e in captured}
    assert set(events_by_collection.keys()) == {col1.id, col3.id}

    # col1: entity was removed
    col1_removed_event = events_by_collection[col1.id].kwargs
    assert col1_removed_event["changed_by"].user_id == admin_user.id
    assert col1_removed_event["change"] == CollectionChangeData(
        collection_id=col1.id,
        collection_code="col1",
        entities_removed=[entity.id],
    )

    # col3: entity was added
    col3_added_event = events_by_collection[col3.id].kwargs
    assert col1_removed_event["changed_by"].user_id == admin_user.id
    assert col3_added_event["change"] == CollectionChangeData(
        collection_id=col3.id,
        collection_code="col3",
        entities_added=[entity.id],
    )
    # The collections were modified simultaneously:
    assert col1_removed_event["metadata"].time == col3_added_event["metadata"].time


def test_set_collections_aborted(lp1: LearningPackage) -> None:
    """
    Test that no events are emitted when set_collections is rolled back.
    """
    col1 = api.create_collection(lp1.id, "col1", title="Collection 1", created_by=None)
    entity = _create_entity(lp1.id, "entity1")

    with capture_events(expected_count=0):
        with abort_transaction():
            api.set_collections(entity, Collection.objects.filter(id=col1.id))


# COLLECTION_CHANGED — entity draft state changes do NOT emit


def _create_entity_with_version(learning_package_id: LearningPackage.ID, entity_ref: str) -> PublishableEntity:
    """Helper: create a PublishableEntity with an initial draft version (so its draft can be deleted)."""
    entity = api.create_publishable_entity(
        learning_package_id, entity_ref=entity_ref, created=now_time, created_by=None
    )
    api.create_publishable_entity_version(entity.id, version_num=1, title=entity_ref, created=now_time, created_by=None)
    return entity


def test_entity_draft_state_changes_do_not_emit_collection_event(lp1: LearningPackage) -> None:
    """
    COLLECTION_CHANGED reflects explicit mutations of a Collection (its metadata
    or its membership rows), not changes to the draft state of entities that
    happen to be members. Soft-deleting, restoring, or creating an entity does
    NOT emit COLLECTION_CHANGED — even if that entity is in one or more
    collections — because the ``CollectionPublishableEntity`` rows themselves
    are unchanged.

    Consumers that need to react to draft-state changes of entities-in-collections
    should subscribe to ``ENTITIES_DRAFT_CHANGED`` directly.
    """
    api.create_collection(lp1.id, "col1", title="Collection 1", created_by=None)
    api.create_collection(lp1.id, "col2", title="Collection 2", created_by=None)
    entity = _create_entity_with_version(lp1.id, "entity1")
    v1 = api.get_draft_version(entity)
    api.add_to_collection(lp1.id, "col1", PublishableEntity.objects.filter(id=entity.id))
    api.add_to_collection(lp1.id, "col2", PublishableEntity.objects.filter(id=entity.id))

    with capture_events(signals=[COLLECTION_CHANGED], expected_count=0):
        # Soft-delete: no event, even though `entity` is in two collections.
        api.soft_delete_draft(entity.id)
        # Restore via reverting to the previous version: no event.
        assert v1 is not None
        api.set_draft_version(entity.id, v1.id)
        # Soft-delete and restore via a new version: no event.
        api.soft_delete_draft(entity.id)
        api.create_publishable_entity_version(
            entity.id, version_num=2, title="entity1 v2", created=now_time, created_by=None
        )
        # Creating a brand-new entity is unrelated to any collection: no event.
        _create_entity_with_version(lp1.id, "entity2")


# COLLECTION_CHANGED — combined events


def test_entity_created_and_assigned_in_bulk_context(lp1: LearningPackage) -> None:
    """
    Test that the expected events fire when an entity is created and assigned
    to a collection inside a bulk draft change context: one ``created=True``
    from ``create_collection`` and one ``entities_added=[entity]`` from
    ``add_to_collection``. The entity-creation itself does not emit an extra
    COLLECTION_CHANGED.
    """
    with capture_events(signals=[COLLECTION_CHANGED], expected_count=2) as captured:
        with api.bulk_draft_changes_for(lp1.id, changed_by=None, changed_at=now_time):
            col1 = api.create_collection(lp1.id, "col1", title="Collection 1", created_by=None)
            entity = _create_entity_with_version(lp1.id, "entity1")
            api.add_to_collection(lp1.id, "col1", PublishableEntity.objects.filter(id=entity.id))

    assert captured[0].kwargs["change"] == CollectionChangeData(
        collection_id=col1.id,
        collection_code="col1",
        created=True,
    )
    assert captured[1].kwargs["change"] == CollectionChangeData(
        collection_id=col1.id,
        collection_code="col1",
        entities_added=[entity.id],
    )


def test_entity_created_and_assigned_in_transaction(lp1: LearningPackage) -> None:
    """
    Same as above, but in a plain ``transaction.atomic()`` context rather than
    a ``bulk_draft_changes_for`` context.
    """
    with capture_events(signals=[COLLECTION_CHANGED], expected_count=2) as captured:
        with transaction.atomic():
            col1 = api.create_collection(lp1.id, "col1", title="Collection 1", created_by=None)
            entity = _create_entity_with_version(lp1.id, "entity1")
            api.add_to_collection(lp1.id, "col1", PublishableEntity.objects.filter(id=entity.id))

    assert captured[0].kwargs["change"] == CollectionChangeData(
        collection_id=col1.id,
        collection_code="col1",
        created=True,
    )
    assert captured[1].kwargs["change"] == CollectionChangeData(
        collection_id=col1.id,
        collection_code="col1",
        entities_added=[entity.id],
    )


def test_entity_restored_and_assigned_in_bulk_context(lp1: LearningPackage) -> None:
    """
    Test that an entity being restored and added to a new collection inside a
    bulk draft change context produces exactly the expected explicit-mutation
    events: ``created=True`` for the new collection and
    ``entities_added=[entity]`` for the add. The restoration itself does not
    emit a COLLECTION_CHANGED.
    """
    entity = _create_entity_with_version(lp1.id, "entity1")
    v1 = api.get_draft_version(entity)
    assert v1 is not None
    api.soft_delete_draft(entity.id, deleted_by=None)

    with capture_events(signals=[COLLECTION_CHANGED], expected_count=2) as captured:
        with api.bulk_draft_changes_for(lp1.id, changed_by=None, changed_at=now_time):
            api.set_draft_version(entity.id, v1.id)
            col1 = api.create_collection(lp1.id, "col1", title="Collection 1", created_by=None)
            api.add_to_collection(lp1.id, "col1", PublishableEntity.objects.filter(id=entity.id))

    assert captured[0].kwargs["change"] == CollectionChangeData(
        collection_id=col1.id,
        collection_code="col1",
        created=True,
    )
    assert captured[1].kwargs["change"] == CollectionChangeData(
        collection_id=col1.id,
        collection_code="col1",
        entities_added=[entity.id],
    )
