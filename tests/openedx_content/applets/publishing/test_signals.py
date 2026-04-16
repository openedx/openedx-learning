"""
Tests related to the Catalog signal handlers
"""

from datetime import datetime, timezone

import pytest
from django.db import transaction

from openedx_content import api
from tests.utils import capture_events

pytestmark = pytest.mark.django_db(transaction=True)
now_time = datetime.now(tz=timezone.utc)


class DeliberateRollbackException(Exception):
    """Exception used to deliberately cancel and roll back a DB transaction"""


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
        try:
            with transaction.atomic():
                api.create_publishable_entity_version(
                    entity.id, version_num=1, title="Entity 1 V1", created=now_time, created_by=None
                )
                raise DeliberateRollbackException()
        except DeliberateRollbackException:
            pass


def test_multiple_entites_changed() -> None:
    """
    Test that LEARNING_PACKAGE_ENTITIES_CHANGED is emitted when we change
    several publishable entities in a single edit.
    """
    learning_package = api.create_learning_package(key="lp1", title="Test LP 📦")

    # Entity 1 will have no initial version:
    entity1 = api.create_publishable_entity(learning_package.id, key="entity1", created=now_time, created_by=None)
    # Entity 2 will have an initial version:
    entity2 = api.create_publishable_entity(learning_package.id, key="entity2", created=now_time, created_by=None)
    api.create_publishable_entity_version(
        entity2.id, version_num=1, title="Entity 2 V1", created=now_time, created_by=None
    )
    # Entity 3 will have an initial version that later gets deleted:
    entity3 = api.create_publishable_entity(learning_package.id, key="entity3", created=now_time, created_by=None)
    api.create_publishable_entity_version(
        entity3.id, version_num=1, title="Entity 3 V1", created=now_time, created_by=None
    )

    with capture_events(expected_count=1) as captured:
        with api.bulk_draft_changes_for(learning_package.id, changed_by=None, changed_at=now_time) as draft_change_log:
            # Create two versions of entity1:
            api.create_publishable_entity_version(
                entity1.id, version_num=1, title="Entity 1 V1", created=now_time, created_by=None
            )
            api.create_publishable_entity_version(
                entity1.id, version_num=2, title="Entity 1 V2", created=now_time, created_by=None
            )
            # Create a version 2 of entity 2:
            api.create_publishable_entity_version(
                entity2.id, version_num=2, title="Entity 2 V2", created=now_time, created_by=None
            )
            # Delete entity 3:
            api.set_draft_version(entity3.id, None, set_at=now_time, set_by=None)

    event = captured[0]
    assert event.signal is api.signals.LEARNING_PACKAGE_ENTITIES_CHANGED
    assert event.kwargs["learning_package"].id == learning_package.id
    assert event.kwargs["learning_package"].title == "Test LP 📦"
    assert event.kwargs["changed_by"].user_id is None
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
