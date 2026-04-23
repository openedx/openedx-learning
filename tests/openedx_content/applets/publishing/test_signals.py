"""
Tests related to the Catalog signal handlers
"""

from datetime import datetime, timezone
from typing import Any

import pytest

from openedx_content import api
from openedx_content.models_api import LearningPackage, PublishableEntity, PublishLog
from tests.utils import abort_transaction, capture_events

pytestmark = pytest.mark.django_db(transaction=True)
now_time = datetime.now(tz=timezone.utc)


def publish_entity(obj: PublishableEntity) -> PublishLog:
    """Helper method to publish a single entity."""
    lp_id = obj.learning_package_id
    return api.publish_from_drafts(lp_id, draft_qset=api.get_all_drafts(lp_id).filter(entity=obj))


def change_record(obj: PublishableEntity, old_version: int | None, new_version: int | None, direct: bool | None = None):
    """Helper function to construct ChangeLogRecordData() using only version numbers instead of numbers+IDs"""
    old_version_id = obj.versions.get(version_num=old_version).id if old_version is not None else None
    new_version_id = obj.versions.get(version_num=new_version).id if new_version is not None else None
    return api.signals.ChangeLogRecordData(
        entity_id=obj.id,
        old_version=old_version,
        old_version_id=old_version_id,
        new_version=new_version,
        new_version_id=new_version_id,
        direct=direct,
    )


# LEARNING_PACKAGE_CREATED


def test_learning_package_created() -> None:
    """
    Test that LEARNING_PACKAGE_CREATED is emitted when a new ``LearningPackage``
    is created.
    """
    with capture_events(signals=[api.signals.LEARNING_PACKAGE_CREATED], expected_count=1) as captured:
        learning_package = api.create_learning_package(package_ref="lp1", title="Test LP 📦")

    event = captured[0]
    assert event.signal is api.signals.LEARNING_PACKAGE_CREATED
    assert event.kwargs["learning_package"].id == learning_package.id
    assert event.kwargs["learning_package"].title == "Test LP 📦"


def test_learning_package_created_not_emitted_on_update() -> None:
    """
    Test that updating an existing ``LearningPackage`` does NOT emit
    LEARNING_PACKAGE_CREATED. The event is only for new rows.
    """
    learning_package = api.create_learning_package(package_ref="lp1", title="Test LP 📦")

    with capture_events(signals=[api.signals.LEARNING_PACKAGE_CREATED], expected_count=0):
        api.update_learning_package(learning_package.id, title="Updated Title")


def test_learning_package_created_aborted() -> None:
    """
    Test that LEARNING_PACKAGE_CREATED is NOT emitted when the transaction
    that created the ``LearningPackage`` is rolled back.
    """
    with capture_events(signals=[api.signals.LEARNING_PACKAGE_CREATED], expected_count=0):
        with abort_transaction():
            api.create_learning_package(package_ref="lp1", title="Test LP 📦")


# LEARNING_PACKAGE_UPDATED


def test_learning_package_updated() -> None:
    """
    Test that LEARNING_PACKAGE_UPDATED is emitted when
    ``update_learning_package`` actually changes a field, and that the payload
    reflects the post-update title.
    """
    learning_package = api.create_learning_package(package_ref="lp1", title="Original Title")

    with capture_events(signals=[api.signals.LEARNING_PACKAGE_UPDATED], expected_count=1) as captured:
        api.update_learning_package(learning_package.id, title="New Title 📦")

    event = captured[0]
    assert event.signal is api.signals.LEARNING_PACKAGE_UPDATED
    assert event.kwargs["learning_package"].id == learning_package.id
    assert event.kwargs["learning_package"].title == "New Title 📦"


def test_learning_package_updated_noop() -> None:
    """
    Test that LEARNING_PACKAGE_UPDATED is NOT emitted when
    ``update_learning_package`` is called with no field changes (the early
    return in the API means the row is never saved).
    """
    learning_package = api.create_learning_package(package_ref="lp1", title="Test LP 📦")

    with capture_events(signals=[api.signals.LEARNING_PACKAGE_UPDATED], expected_count=0):
        api.update_learning_package(learning_package.id)


def test_learning_package_updated_aborted() -> None:
    """
    Test that LEARNING_PACKAGE_UPDATED is NOT emitted when the transaction
    that would have updated the ``LearningPackage`` is rolled back.
    """
    learning_package = api.create_learning_package(package_ref="lp1", title="Original Title")

    with capture_events(signals=[api.signals.LEARNING_PACKAGE_UPDATED], expected_count=0):
        with abort_transaction():
            api.update_learning_package(learning_package.id, title="Not going to stick")

    # Confirm the title was not actually changed:
    learning_package.refresh_from_db()
    assert learning_package.title == "Original Title"


# LEARNING_PACKAGE_DELETED


def test_learning_package_deleted() -> None:
    """
    Test that LEARNING_PACKAGE_DELETED is emitted when a ``LearningPackage``
    is deleted.
    """
    learning_package = api.create_learning_package(package_ref="lp1", title="Test LP 📦")
    lp_id = learning_package.id

    with capture_events(signals=[api.signals.LEARNING_PACKAGE_DELETED], expected_count=1) as captured:
        learning_package.delete()

    event = captured[0]
    assert event.signal is api.signals.LEARNING_PACKAGE_DELETED
    assert event.kwargs["learning_package"].id == lp_id
    assert event.kwargs["learning_package"].title == "Test LP 📦"


def test_learning_package_deleted_via_queryset() -> None:
    """
    Test that LEARNING_PACKAGE_DELETED fires once per row when multiple
    ``LearningPackage`` instances are deleted via a ``QuerySet.delete()``.
    """
    lp1 = api.create_learning_package(package_ref="lp1", title="LP 1")
    lp2 = api.create_learning_package(package_ref="lp2", title="LP 2")

    with capture_events(signals=[api.signals.LEARNING_PACKAGE_DELETED], expected_count=2) as captured:
        LearningPackage.objects.filter(id__in=[lp1.id, lp2.id]).delete()

    deleted_ids = {event.kwargs["learning_package"].id for event in captured}
    assert deleted_ids == {lp1.id, lp2.id}


def test_learning_package_deleted_aborted() -> None:
    """
    Test that LEARNING_PACKAGE_DELETED is NOT emitted when the transaction
    that would have deleted the ``LearningPackage`` is rolled back.
    """
    learning_package = api.create_learning_package(package_ref="lp1", title="Test LP 📦")
    lp_id = learning_package.id

    with capture_events(signals=[api.signals.LEARNING_PACKAGE_DELETED], expected_count=0):
        with abort_transaction():
            learning_package.delete()

    # Confirm it's still in the database (the row survived the rollback).
    # Note: we can't use ``learning_package.id`` here because Django sets
    # ``instance.id = None`` after ``.delete()``, even if the transaction
    # ultimately rolls back; that's why we captured it beforehand.
    assert LearningPackage.objects.filter(id=lp_id).exists()


# ENTITIES_DRAFT_CHANGED


def test_single_entity_changed() -> None:
    """
    Test that ENTITIES_DRAFT_CHANGED is emitted when we change a publishable entity.
    """
    learning_package = api.create_learning_package(package_ref="lp1", title="Test LP 📦")

    # Note: creating an entity does not emit any events until we create a version of that entity.
    with capture_events(expected_count=0):
        entity = api.create_publishable_entity(
            learning_package.id, entity_ref="entity1", created=now_time, created_by=None
        )

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
    assert event.signal is api.signals.ENTITIES_DRAFT_CHANGED
    assert event.kwargs["learning_package"].id == learning_package.id
    assert event.kwargs["learning_package"].title == "Test LP 📦"
    assert event.kwargs["changed_by"].user_id is None
    assert event.kwargs["change_log"].draft_change_log_id == expected_draft_change_log_id
    assert event.kwargs["change_log"].changes == [
        change_record(entity, old_version=None, new_version=NEW_VERSION_NUM),
    ]
    assert event.kwargs["metadata"].time == now_time


def test_single_entity_changed_abort() -> None:
    """
    Test that no events are emitted when we roll back a transaction that would have
    changed a publishable entity.
    """
    learning_package = api.create_learning_package(package_ref="lp1", title="Test LP 📦")

    entity = api.create_publishable_entity(learning_package.id, entity_ref="entity1", created=now_time, created_by=None)

    with capture_events(expected_count=0):
        with abort_transaction():
            api.create_publishable_entity_version(
                entity.id, version_num=1, title="Entity 1 V1", created=now_time, created_by=None
            )


def test_multiple_entites_changed(admin_user) -> None:
    """
    Test that ENTITIES_DRAFT_CHANGED is emitted when we change several publishable entities in a single edit.
    """
    learning_package = api.create_learning_package(package_ref="lp1", title="Test LP 📦")
    created_args = {"created": now_time, "created_by": admin_user.id}

    # Entity 1 will have no initial version:
    entity1 = api.create_publishable_entity(learning_package.id, entity_ref="entity1", **created_args)
    # Entity 2 will have an initial version:
    entity2 = api.create_publishable_entity(learning_package.id, entity_ref="entity2", **created_args)
    api.create_publishable_entity_version(entity2.id, version_num=1, title="Entity 2 V1", **created_args)
    # Entity 3 will have an initial version that later gets deleted:
    entity3 = api.create_publishable_entity(learning_package.id, entity_ref="entity3", **created_args)
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
    assert event.signal is api.signals.ENTITIES_DRAFT_CHANGED
    assert event.kwargs["learning_package"].id == learning_package.id
    assert event.kwargs["learning_package"].title == "Test LP 📦"
    assert event.kwargs["changed_by"].user_id is admin_user.id
    assert event.kwargs["change_log"].draft_change_log_id == draft_change_log.id
    assert event.kwargs["change_log"].changes == [
        # Entity 1 jumps from no version to version 2:
        change_record(entity1, old_version=None, new_version=2),
        # Entity 2 jumps v1 -> v2:
        change_record(entity2, old_version=1, new_version=2),
        # Entity 3 gets deleted:
        change_record(entity3, old_version=1, new_version=None),
    ]
    assert event.kwargs["metadata"].time == now_time


def test_multiple_entites_change_aborted() -> None:
    """
    Test that ENTITIES_DRAFT_CHANGED is NOT emitted when we roll back
    a transaction that would have modified multiple entities in a bulk change.
    """
    learning_package = api.create_learning_package(package_ref="lp1", title="Test LP 📦")
    created_args: dict[str, Any] = {"created": now_time, "created_by": None}

    # Entity 1 will have no initial version:
    entity1 = api.create_publishable_entity(learning_package.id, entity_ref="entity1", **created_args)
    # Entity 2 will have an initial version:
    entity2 = api.create_publishable_entity(learning_package.id, entity_ref="entity2", **created_args)
    api.create_publishable_entity_version(entity2.id, version_num=1, title="Entity 2 V1", **created_args)
    # Entity 3 will have an initial version that later gets deleted:
    entity3 = api.create_publishable_entity(learning_package.id, entity_ref="entity3", **created_args)
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


def test_changes_with_side_effects() -> None:
    """
    Test that the ENTITIES_DRAFT_CHANGED event handles dependencies
    and side effects.
    """
    learning_package = api.create_learning_package(package_ref="lp1", title="Test LP 📦")
    created_args: dict[str, Any] = {"created": now_time, "created_by": None}

    # Create entities with dependencies

    def create_entity(name: str, dependencies: list[PublishableEntity.ID] | None = None) -> PublishableEntity:
        e = api.create_publishable_entity(learning_package.id, entity_ref=name, **created_args)
        api.create_publishable_entity_version(
            e.id, version_num=1, title=f"{name} V1", dependencies=dependencies, **created_args
        )
        return e

    child1 = create_entity("child1")
    parent1 = create_entity("parent1", dependencies=[child1.id])

    # now, modifying child1 will affect parent1:
    with capture_events(expected_count=1) as captured:
        api.create_publishable_entity_version(child1.id, version_num=2, title="child1 V2", **created_args)

    event = captured[0]
    assert event.signal is api.signals.ENTITIES_DRAFT_CHANGED
    assert event.kwargs["change_log"].changes == [
        change_record(child1, old_version=1, new_version=2),  # directly modified
        change_record(parent1, old_version=1, new_version=1),  # side effect
    ]


# ENTITIES_PUBLISHED


def test_publish_events(admin_user) -> None:
    """
    Test that ENTITIES_PUBLISHED is emitted when we publish
    changes to entities in a learning package.
    """
    learning_package = api.create_learning_package(package_ref="lp1", title="Test LP 📦")
    created_args = {"created": now_time, "created_by": admin_user.id}

    # Entity 1 will have no initial version:
    entity1 = api.create_publishable_entity(learning_package.id, entity_ref="entity1", **created_args)
    # Entity 2 will have an initial version with some changes:
    entity2 = api.create_publishable_entity(learning_package.id, entity_ref="entity2", **created_args)
    api.create_publishable_entity_version(entity2.id, version_num=1, title="Entity 2 V1", **created_args)
    api.create_publishable_entity_version(entity2.id, version_num=2, title="Entity 2 V2", **created_args)
    # Entity 3 will have an initial version that later gets deleted:
    entity3 = api.create_publishable_entity(learning_package.id, entity_ref="entity3", **created_args)
    api.create_publishable_entity_version(entity3.id, version_num=1, title="Entity 3 V1", **created_args)

    # Publish these initial changes:
    first_publish_time = datetime.now(tz=timezone.utc)
    with capture_events(expected_count=1) as captured:
        first_log = api.publish_all_drafts(
            learning_package.id, published_at=first_publish_time, published_by=admin_user.id
        )

    event = captured[0]
    assert event.signal is api.signals.ENTITIES_PUBLISHED
    assert event.kwargs["learning_package"].id == learning_package.id
    assert event.kwargs["learning_package"].title == "Test LP 📦"
    assert event.kwargs["changed_by"].user_id is admin_user.id
    assert event.kwargs["change_log"].publish_log_id == first_log.id
    assert event.kwargs["change_log"].changes == [
        # Entity 1 is not yet published, since it has no draft version.
        # Entity 2 is newly published, and now at v2:
        change_record(entity2, old_version=None, new_version=2, direct=True),
        # Entity 3 is newly published, and now at v1:
        change_record(entity3, old_version=None, new_version=1, direct=True),
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
    assert event.signal is api.signals.ENTITIES_PUBLISHED
    assert event.kwargs["learning_package"].id == learning_package.id
    assert event.kwargs["learning_package"].title == "Test LP 📦"
    assert event.kwargs["changed_by"].user_id is admin_user.id
    assert event.kwargs["change_log"].publish_log_id == second_log.id
    assert event.kwargs["change_log"].changes == [
        # Entity 1 is newly published at v1:
        change_record(entity1, old_version=None, new_version=1, direct=True),
        # Entity 2 jumps v2 -> v3:
        change_record(entity2, old_version=2, new_version=3, direct=True),
        # Entity 3 gets deleted:
        change_record(entity3, old_version=1, new_version=None, direct=True),
    ]
    assert event.kwargs["metadata"].time == second_publish_time


def test_publish_events_aborted(admin_user) -> None:
    """
    Test that ENTITIES_PUBLISHED is NOT emitted when we roll
    back a transaction that would have published some entities.
    """
    learning_package = api.create_learning_package(package_ref="lp1", title="Test LP 📦")
    created_args = {"created": now_time, "created_by": admin_user.id}

    # Create an entity with some initial version:
    entity1 = api.create_publishable_entity(learning_package.id, entity_ref="entity1", **created_args)
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


def test_publish_with_dependencies() -> None:
    """
    Test that the ENTITIES_PUBLISHED event handles dependencies
    and side effects.
    """
    learning_package = api.create_learning_package(package_ref="lp1", title="Test LP 📦")
    created_args: dict[str, Any] = {"created": now_time, "created_by": None}

    # Create entities with dependencies

    def create_entity(name: str, dependencies: list[PublishableEntity.ID] | None = None) -> PublishableEntity:
        e = api.create_publishable_entity(learning_package.id, entity_ref=name, **created_args)
        api.create_publishable_entity_version(
            e.id, version_num=1, title=f"{name} V1", dependencies=dependencies, **created_args
        )
        return e

    # 👧👦 children
    child1 = create_entity("child1")
    child2 = create_entity("child2")
    child3 = create_entity("child3")
    # 🧓👩 parents
    parent1 = create_entity("parent1", dependencies=[child1.id, child2.id])
    parent2 = create_entity("parent2", dependencies=[child2.id, child3.id])
    # 👴👵 grandparents
    grandparent1 = create_entity("grandparent1", dependencies=[parent1.id])
    grandparent2 = create_entity("grandparent2", dependencies=[parent2.id])

    # publish grandparent1 directly and all its dependencies indirectly:
    with capture_events(expected_count=1) as captured:
        publish_entity(grandparent1)

    event = captured[0]
    assert event.signal is api.signals.ENTITIES_PUBLISHED
    assert event.kwargs["change_log"].changes == [
        change_record(grandparent1, old_version=None, new_version=1, direct=True),
        change_record(parent1, old_version=None, new_version=1, direct=False),
        change_record(child1, old_version=None, new_version=1, direct=False),
        change_record(child2, old_version=None, new_version=1, direct=False),
    ]

    # publish the rest:
    with capture_events(expected_count=1):
        api.publish_all_drafts(learning_package.id)

    # ✨ Now modify 'child3', causing side effects for parent2 and grandparent2
    api.create_publishable_entity_version(child3.id, version_num=2, title="child3 V2", **created_args)

    with capture_events(expected_count=1) as captured:
        publish_entity(child3)

    event = captured[0]
    assert event.signal is api.signals.ENTITIES_PUBLISHED
    assert event.kwargs["change_log"].changes == [
        change_record(child3, old_version=1, new_version=2, direct=True),
        change_record(parent2, old_version=1, new_version=1, direct=False),
        change_record(grandparent2, old_version=1, new_version=1, direct=False),
    ]
