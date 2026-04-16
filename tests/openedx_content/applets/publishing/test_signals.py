"""
Tests related to the Catalog signal handlers
"""

from datetime import datetime, timezone
from typing import Any

import pytest

from openedx_content import api
from tests.utils import abort_transaction, capture_events

pytestmark = pytest.mark.django_db(transaction=True)
now_time = datetime.now(tz=timezone.utc)

# LEARNING_PACKAGE_ENTITIES_CHANGED


def test_single_entity_changed() -> None:
    """
    Test that LEARNING_PACKAGE_ENTITIES_CHANGED is emitted when we change a
    publishable entity.
    """
    learning_package = api.create_learning_package(key="lp1", title="Test LP 📦")

    # Note: creating an entity does not emit any events until we create a version of that entity.
    with capture_events(expected_count=0):
        entity = api.create_publishable_entity(learning_package.id, key="entity1", created=now_time, created_by=None)

    NEW_VERSION_NUM = 3  # Just for fun let's use a version number other than 1

    with capture_events(expected_count=1) as captured:
        v1 = api.create_publishable_entity_version(
            entity.id, version_num=NEW_VERSION_NUM, title="Entity 1 V3", created=now_time, created_by=None
        )

    entity.refresh_from_db()
    assert api.get_draft_version(entity.id) == v1

    # Because only one change (create_..._version) has affected this version, it's easy for us to get its DraftChangeLog
    expected_draft_change_log_id = v1.draftchangelogrecord_set.get().draft_change_log_id

    event = captured[0]  # capture_events(...) context manager already asserted there's only one event.
    assert event.signal is api.signals.LEARNING_PACKAGE_ENTITIES_CHANGED
    assert event.kwargs["learning_package"].id == learning_package.id
    assert event.kwargs["learning_package"].title == "Test LP 📦"
    assert event.kwargs["changed_by"].user_id is None
    assert event.kwargs["change_log"].draft_change_log_id == expected_draft_change_log_id
    assert event.kwargs["change_log"].changes == [
        api.signals.ChangeLogRecordData(entity_id=entity.id, old_version=None, new_version=NEW_VERSION_NUM),
    ]
    assert event.kwargs["metadata"].time == now_time


def test_single_entity_changed_abort() -> None:
    """
    Test that no events are emitted when we roll back a transaction that would have
    changed a publishable entity.
    """
    learning_package = api.create_learning_package(key="lp1", title="Test LP 📦")

    entity = api.create_publishable_entity(learning_package.id, key="entity1", created=now_time, created_by=None)

    with capture_events(expected_count=0):
        with abort_transaction():
            api.create_publishable_entity_version(
                entity.id, version_num=1, title="Entity 1 V1", created=now_time, created_by=None
            )


def test_multiple_entites_changed(admin_user) -> None:
    """
    Test that LEARNING_PACKAGE_ENTITIES_CHANGED is emitted when we change
    several publishable entities in a single edit.
    """
    learning_package = api.create_learning_package(key="lp1", title="Test LP 📦")
    created_args = {"created": now_time, "created_by": admin_user.id}

    # Entity 1 will have no initial version:
    entity1 = api.create_publishable_entity(learning_package.id, key="entity1", **created_args)
    # Entity 2 will have an initial version:
    entity2 = api.create_publishable_entity(learning_package.id, key="entity2", **created_args)
    api.create_publishable_entity_version(entity2.id, version_num=1, title="Entity 2 V1", **created_args)
    # Entity 3 will have an initial version that later gets deleted:
    entity3 = api.create_publishable_entity(learning_package.id, key="entity3", **created_args)
    api.create_publishable_entity_version(entity3.id, version_num=1, title="Entity 3 V1", **created_args)

    with capture_events(expected_count=1) as captured:
        with api.bulk_draft_changes_for(
            learning_package.id,
            changed_by=admin_user.id,
            changed_at=now_time,
        ) as draft_change_log:
            # Note: the 'created_args' values below get ignored because of the bulk context.
            # Create two versions of entity1:
            api.create_publishable_entity_version(entity1.id, version_num=1, title="Entity 1 V1", **created_args)
            api.create_publishable_entity_version(entity1.id, version_num=2, title="Entity 1 V2", **created_args)
            # Create a version 2 of entity 2:
            api.create_publishable_entity_version(entity2.id, version_num=2, title="Entity 2 V2", **created_args)
            # Delete entity 3:
            api.set_draft_version(entity3.id, None, set_at=now_time, set_by=admin_user.id)

    event = captured[0]
    assert event.signal is api.signals.LEARNING_PACKAGE_ENTITIES_CHANGED
    assert event.kwargs["learning_package"].id == learning_package.id
    assert event.kwargs["learning_package"].title == "Test LP 📦"
    assert event.kwargs["changed_by"].user_id is admin_user.id
    assert event.kwargs["change_log"].draft_change_log_id == draft_change_log.id
    assert event.kwargs["change_log"].changes == [
        # Entity 1 jumps from no version to version 2:
        api.signals.ChangeLogRecordData(entity_id=entity1.id, old_version=None, new_version=2),
        # Entity 2 jumps v1 -> v2:
        api.signals.ChangeLogRecordData(entity_id=entity2.id, old_version=1, new_version=2),
        # Entity 3 gets deleted:
        api.signals.ChangeLogRecordData(entity_id=entity3.id, old_version=1, new_version=None),
    ]
    assert event.kwargs["metadata"].time == now_time


def test_multiple_entites_change_aborted() -> None:
    """
    Test that LEARNING_PACKAGE_ENTITIES_CHANGED is NOT emitted when we roll back
    a transaction that would have modified multiple entities in a bulk change.
    """
    learning_package = api.create_learning_package(key="lp1", title="Test LP 📦")
    created_args: dict[str, Any] = {"created": now_time, "created_by": None}

    # Entity 1 will have no initial version:
    entity1 = api.create_publishable_entity(learning_package.id, key="entity1", **created_args)
    # Entity 2 will have an initial version:
    entity2 = api.create_publishable_entity(learning_package.id, key="entity2", **created_args)
    api.create_publishable_entity_version(entity2.id, version_num=1, title="Entity 2 V1", **created_args)
    # Entity 3 will have an initial version that later gets deleted:
    entity3 = api.create_publishable_entity(learning_package.id, key="entity3", **created_args)
    api.create_publishable_entity_version(entity3.id, version_num=1, title="Entity 3 V1", **created_args)

    with capture_events(expected_count=0):
        with abort_transaction():
            with api.bulk_draft_changes_for(learning_package.id, changed_by=None, changed_at=now_time):
                # Note: the 'created_args' values below get ignored because of the bulk context.
                # Create two versions of entity1:
                api.create_publishable_entity_version(entity1.id, version_num=1, title="Entity 1 V1", **created_args)
                api.create_publishable_entity_version(entity1.id, version_num=2, title="Entity 1 V2", **created_args)
                # Create a version 2 of entity 2:
                api.create_publishable_entity_version(entity2.id, version_num=2, title="Entity 2 V2", **created_args)
                # Delete entity 3:
                api.set_draft_version(entity3.id, None, set_at=now_time, set_by=None)


# LEARNING_PACKAGE_ENTITIES_PUBLISHED


def test_publish_events(admin_user) -> None:
    """
    Test that LEARNING_PACKAGE_ENTITIES_PUBLISHED is emitted when we publish
    changes to entities in a learning package.
    """
    learning_package = api.create_learning_package(key="lp1", title="Test LP 📦")
    created_args = {"created": now_time, "created_by": admin_user.id}

    # Entity 1 will have no initial version:
    entity1 = api.create_publishable_entity(learning_package.id, key="entity1", **created_args)
    # Entity 2 will have an initial version with some changes:
    entity2 = api.create_publishable_entity(learning_package.id, key="entity2", **created_args)
    api.create_publishable_entity_version(entity2.id, version_num=1, title="Entity 2 V1", **created_args)
    api.create_publishable_entity_version(entity2.id, version_num=2, title="Entity 2 V2", **created_args)
    # Entity 3 will have an initial version that later gets deleted:
    entity3 = api.create_publishable_entity(learning_package.id, key="entity3", **created_args)
    api.create_publishable_entity_version(entity3.id, version_num=1, title="Entity 3 V1", **created_args)

    # Publish these initial changes:
    first_publish_time = datetime.now(tz=timezone.utc)
    with capture_events(expected_count=1) as captured:
        first_log = api.publish_all_drafts(
            learning_package.id, published_at=first_publish_time, published_by=admin_user.id
        )

    event = captured[0]
    assert event.signal is api.signals.LEARNING_PACKAGE_ENTITIES_PUBLISHED
    assert event.kwargs["learning_package"].id == learning_package.id
    assert event.kwargs["learning_package"].title == "Test LP 📦"
    assert event.kwargs["changed_by"].user_id is admin_user.id
    assert event.kwargs["change_log"].publish_log_id == first_log.id
    assert event.kwargs["change_log"].changes == [
        # Entity 1 is not yet published, since it has no draft version.
        # Entity 2 is newly published, and now at v2:
        api.signals.ChangeLogRecordData(entity_id=entity2.id, old_version=None, new_version=2),
        # Entity 3 is newly published, and now at v1:
        api.signals.ChangeLogRecordData(entity_id=entity3.id, old_version=None, new_version=1),
    ]
    assert event.kwargs["metadata"].time == first_publish_time

    # Now modify the entities again:
    # Create a version of entity1:
    api.create_publishable_entity_version(entity1.id, version_num=1, title="Entity 1 V1", **created_args)
    # Create a version 3 of entity2:
    api.create_publishable_entity_version(entity2.id, version_num=3, title="Entity 2 V3", **created_args)
    # Delete entity 3:
    api.set_draft_version(entity3.id, None, set_at=now_time, set_by=admin_user.id)

    # Publish these new changes:
    second_publish_time = datetime.now(tz=timezone.utc)
    with capture_events(expected_count=1) as captured:
        second_log = api.publish_all_drafts(
            learning_package.id, published_at=second_publish_time, published_by=admin_user.id
        )

    event = captured[0]
    assert event.signal is api.signals.LEARNING_PACKAGE_ENTITIES_PUBLISHED
    assert event.kwargs["learning_package"].id == learning_package.id
    assert event.kwargs["learning_package"].title == "Test LP 📦"
    assert event.kwargs["changed_by"].user_id is admin_user.id
    assert event.kwargs["change_log"].publish_log_id == second_log.id
    assert event.kwargs["change_log"].changes == [
        # Entity 1 is newly published at v1:
        api.signals.ChangeLogRecordData(entity_id=entity1.id, old_version=None, new_version=1),
        # Entity 2 jumps v2 -> v3:
        api.signals.ChangeLogRecordData(entity_id=entity2.id, old_version=2, new_version=3),
        # Entity 3 gets deleted:
        api.signals.ChangeLogRecordData(entity_id=entity3.id, old_version=1, new_version=None),
    ]
    assert event.kwargs["metadata"].time == second_publish_time


def test_publish_events_aborted(admin_user) -> None:
    """
    Test that LEARNING_PACKAGE_ENTITIES_PUBLISHED is NOT emitted when we roll
    back a transaction that would have published some entities.
    """
    learning_package = api.create_learning_package(key="lp1", title="Test LP 📦")
    created_args = {"created": now_time, "created_by": admin_user.id}

    # Create an entity with some initial version:
    entity1 = api.create_publishable_entity(learning_package.id, key="entity1", **created_args)
    api.create_publishable_entity_version(entity1.id, version_num=1, title="Entity 1 V1", **created_args)

    def do_publish():
        draft_qset = api.get_all_drafts(learning_package.id).filter(entity=entity1)
        api.publish_from_drafts(
            learning_package.id, draft_qset=draft_qset, published_at=now_time, published_by=admin_user.id
        )

    with capture_events(expected_count=0):
        with abort_transaction():
            do_publish()

    with capture_events(expected_count=1):
        do_publish()
