"""
Basic tests for the publishing containers API.
"""
# pylint: disable=too-many-positional-arguments, unused-argument

from datetime import datetime, timezone
from typing import Any, assert_type

import pytest
from django.core.exceptions import ValidationError
from django.db.utils import IntegrityError

from openedx_content.applets.publishing import api as publishing_api
from openedx_content.applets.publishing.models import (
    Container,
    ContainerVersion,
    Draft,
    DraftChangeLog,
    DraftSideEffect,
    LearningPackage,
    PublishableEntity,
    PublishableEntityMixin,
    PublishableEntityVersionMixin,
)
from openedx_content.applets.publishing.models.container import ContainerTypeRecord
from tests.test_django_app.models import (
    ContainerContainer,
    TestContainer,
    TestContainerVersion,
    TestEntity,
    TestEntityVersion,
)

# Note: to test the Publishing applet in isolation, this test suite does not import "Component", "Unit", or other models
# from applets that build on this one. Since Containers require specific concrete container types, we use
# "TestContainer" and "ContainerContainer" from test_django_app, which are specifically for testing the publishing
# API.


pytestmark = pytest.mark.django_db
now = datetime(2026, 5, 8, tzinfo=timezone.utc)


@pytest.fixture(autouse=True)
def container_tear_down():
    """
    Reset Container's internal type cache after each test.
    Required because the test runner truncates tables after each test, and that
    invalidates the cached container types.
    """
    yield None  # run the test
    Container.reset_cache()


########################################################################################################################
# Fixtures:


# The fixtures available below and their hierarchy are:
#
# lp (LearningPackage)
# ├─ grandparent (ContainerContainer)
# │  ├─ parent_of_two (TestContainer)
# │  │  ├─ child_entity1 (PublishableEntity)
# │  │  └─ child_entity2 (PublishableEntity)
# │  └─ parent_of_three (TestContainer)
# │     ├─ child_entity3 (📌 pinned to v1, PublishableEntity)
# │     ├─ child_entity2 (📌 pinned to v1, PublishableEntity)
# │     └─ child_entity1 (PublishableEntity)
# │
# ├─ parent_of_six (TestContainer, has duplicate children)
# │  ├─ child_entity3 (📌 pinned to v1, PublishableEntity)
# │  ├─ child_entity2 (📌 pinned to v1, PublishableEntity)
# │  ├─ child_entity1 (PublishableEntity)
# │  ├─ child_entity1 (PublishableEntity)
# │  ├─ child_entity2 (📌 pinned to v1, PublishableEntity)
# │  └─ child_entity3 (PublishableEntity)
# │
# └─ container_of_uninstalled_type ("misc" Container - it's specific type plugin no longer available)
#    └─ child_entity1 (PublishableEntity)
#
# lp2 (LearningPackage)
# └─ other_lp_parent (TestContainer)
#    └─ other_lp_child (PublishableEntity)
#
# Note that the "child" entities are referenced in multiple containers
# Everything is initially in a draft state only, with no published version.


@pytest.fixture(name="other_user")
def _other_user(django_user_model):
    return django_user_model.objects.create_user(username="other", password="something")


@pytest.fixture(name="lp")
def _lp() -> LearningPackage:
    """Get a Learning Package."""
    return publishing_api.create_learning_package(key="containers-test-lp", title="Testing Containers Main LP")


@pytest.fixture(name="lp2")
def _lp2() -> LearningPackage:
    """Get a Second Learning Package."""
    return publishing_api.create_learning_package(key="containers-test-lp2", title="Testing Containers (📦 2)")


def create_test_entity(learning_package: LearningPackage, key: str, title: str) -> TestEntity:
    """Create a TestEntity with a draft version"""
    pe = publishing_api.create_publishable_entity(learning_package.id, key, created=now, created_by=None)
    new_entity = TestEntity.objects.create(publishable_entity=pe)
    pev = publishing_api.create_publishable_entity_version(
        new_entity.pk,
        version_num=1,
        title=title,
        created=now,
        created_by=None,
    )
    TestEntityVersion.objects.create(publishable_entity_version=pev)
    return new_entity


@pytest.fixture(name="child_entity1")
def _child_entity1(lp: LearningPackage) -> TestEntity:
    """An example entity, such as a component"""
    return create_test_entity(lp, key="child_entity1", title="Child 1 🌴")


@pytest.fixture(name="child_entity2")
def _child_entity2(lp: LearningPackage) -> TestEntity:
    """An example entity, such as a component"""
    return create_test_entity(lp, key="child_entity2", title="Child 2 🌈")


@pytest.fixture(name="child_entity3")
def _child_entity3(lp: LearningPackage) -> TestEntity:
    """An example entity, such as a component"""
    return create_test_entity(lp, key="child_entity3", title="Child 3 ⛵️")


@pytest.fixture(name="other_lp_child")
def _other_lp_child(lp2: LearningPackage) -> TestEntity:
    """An example entity, such as a component"""
    return create_test_entity(lp2, key="other_lp_child", title="Child in other Learning Package 📦")


def create_test_container(
    learning_package: LearningPackage, key: str, entities: publishing_api.EntityListInput, title: str = ""
) -> TestContainer:
    """Create a TestContainer with a draft version"""
    container, _version = publishing_api.create_container_and_version(
        learning_package.id,
        key=key,
        title=title or f"Container ({key})",
        entities=entities,
        container_type=TestContainer,
        created=now,
        created_by=None,
    )
    return container


@pytest.fixture(name="parent_of_two")
def _parent_of_two(lp: LearningPackage, child_entity1: TestEntity, child_entity2: TestEntity) -> TestContainer:
    """An TestContainer with two children"""
    return create_test_container(
        lp,
        key="parent_of_two",
        title="Generic Container with Two Unpinned Children",
        entities=[child_entity1, child_entity2],
    )


@pytest.fixture(name="parent_of_three")
def _parent_of_three(
    lp: LearningPackage,
    child_entity1: TestEntity,
    child_entity2: TestEntity,
    child_entity3: TestEntity,
) -> TestContainer:
    """An TestContainer with three children, two of which are pinned"""
    return create_test_container(
        lp,
        key="parent_of_three",
        title="Generic Container with Two 📌 Pinned Children and One Unpinned",
        entities=[child_entity3.versioning.draft, child_entity2.versioning.draft, child_entity1],
    )


@pytest.fixture(name="parent_of_six")
def _parent_of_six(
    lp: LearningPackage,
    child_entity1: TestEntity,
    child_entity2: TestEntity,
    child_entity3: TestEntity,
) -> TestContainer:
    """An TestContainer with six children, two of each entity, with different pinned combinations"""
    return create_test_container(
        lp,
        key="parent_of_six",
        title="Generic Container with Two 📌 Pinned Children and One Unpinned",
        entities=[
            # 1: both unpinned, 2: both pinned, and 3: pinned and unpinned
            child_entity3.versioning.draft,
            child_entity2.versioning.draft,
            child_entity1,
            child_entity1,
            child_entity2.versioning.draft,
            child_entity3,
        ],
    )


@pytest.fixture(name="grandparent")
def _grandparent(
    lp: LearningPackage,
    parent_of_two: TestContainer,
    parent_of_three: TestContainer,
) -> ContainerContainer:
    """An ContainerContainer with two unpinned children"""
    grandparent, _version = publishing_api.create_container_and_version(
        lp.id,
        key="grandparent",
        title="Generic Container with Two Unpinned TestContainer children",
        entities=[parent_of_two, parent_of_three],
        container_type=ContainerContainer,
        created=now,
        created_by=None,
    )
    return grandparent


@pytest.fixture(name="container_of_uninstalled_type")
def _container_of_uninstalled_type(lp: LearningPackage, child_entity1: TestEntity) -> Container:
    """
    A container whose ContainerType implementation is no longer available,
    e.g. leftover data from an uninstalled plugin.
    """
    # First create a TestContainer, then we'll modify it to simulate it being from an uninstalled plugin
    container, _ = publishing_api.create_container_and_version(
        lp.pk,
        key="abandoned-container",
        title="Abandoned Container 1",
        entities=[child_entity1],
        container_type=TestContainer,
        created=now,
    )
    # Now create the plugin type (no public API for this; only do this in a test)
    ctr = ContainerTypeRecord.objects.create(type_code="misc")
    Container.objects.filter(pk=container.pk).update(container_type_record=ctr)
    return Container.objects.get(pk=container.pk)  # Reload and just use the base Container type


@pytest.fixture(name="other_lp_parent")
def _other_lp_parent(lp2: LearningPackage, other_lp_child: PublishableEntity) -> TestContainer:
    """An TestContainer with one child"""
    other_lp_parent, _version = publishing_api.create_container_and_version(
        lp2.id,
        key="other_lp_parent",
        title="Generic Container with One Unpinned Child Entity",
        entities=[other_lp_child],
        container_type=TestContainer,
        created=now,
        created_by=None,
    )
    return other_lp_parent


def publish_entity(obj: PublishableEntityMixin):
    """Helper method to publish a single container or other entity."""
    lp_id = obj.publishable_entity.learning_package_id
    publishing_api.publish_from_drafts(
        lp_id,
        draft_qset=publishing_api.get_all_drafts(lp_id).filter(entity=obj.publishable_entity),
    )


def modify_entity(obj: TestEntity, title="Newly modified entity"):
    """Modify a TestEntity, creating a new version with a new title"""
    assert isinstance(obj, TestEntity)
    new_raw_version = publishing_api.create_publishable_entity_version(
        obj.pk, version_num=obj.versioning.latest.version_num + 1, title=title, created=now, created_by=None
    )
    return TestEntityVersion.objects.create(pk=new_raw_version.pk)


def Entry(
    component_version: PublishableEntityVersionMixin,
    pinned: bool = False,
) -> publishing_api.ContainerEntityListEntry:
    """Helper for quickly constructing ContainerEntityListEntry entries"""
    return publishing_api.ContainerEntityListEntry(component_version.publishable_entity_version, pinned=pinned)


########################################################################################################################

# `create_container`, and `create_container_version` are not tested directly here, but they are used indirectly by
# `create_container_and_version`. They are also used explicitly in `ContainerSideEffectsTestCase`, below.

# Basic tests of `create_container_and_version`


def test_create_generic_empty_container(lp: LearningPackage, admin_user) -> None:
    """
    Creating an empty TestContainer. It will have only a draft version.
    """
    container, container_v1 = publishing_api.create_container_and_version(
        lp.pk,
        key="new-container-1",
        title="Test Container 1",
        container_type=TestContainer,
        created=now,
        created_by=admin_user.pk,
        can_stand_alone=False,
    )

    assert_type(container, TestContainer)
    # assert_type(container_v1, TestContainerVersion)  # FIXME: seems not possible yet as of Python 3.12
    # Note the assert_type() calls must come before 'assert isinstance()' or they'll have no effect.
    assert isinstance(container, TestContainer)
    assert isinstance(container_v1, TestContainerVersion)
    assert container.versioning.draft == container_v1
    assert container.versioning.published is None
    assert container.key == "new-container-1"
    assert container.versioning.draft.title == "Test Container 1"
    assert container.created == now
    assert container.created_by == admin_user
    assert container.versioning.draft.created == now
    assert container.versioning.draft.created_by == admin_user
    assert not container.can_stand_alone

    assert publishing_api.get_container_children_count(container, published=False) == 0
    with pytest.raises(ContainerVersion.DoesNotExist):
        publishing_api.get_container_children_count(container, published=True)


def test_create_container_queries(lp: LearningPackage, child_entity1: TestEntity, django_assert_num_queries) -> None:
    """Test how many database queries are required to create a container."""
    base_args: dict[str, Any] = {
        "title": "Test Container",
        "created": now,
        "created_by": None,
        "container_type": TestContainer,
    }
    # The exact numbers here aren't too important - this is just to alert us if anything significant changes.
    with django_assert_num_queries(31):
        publishing_api.create_container_and_version(lp.pk, key="c1", **base_args)
    # And try with a a container that has children:
    with django_assert_num_queries(32):
        publishing_api.create_container_and_version(lp.pk, key="c2", **base_args, entities=[child_entity1])


# versioning helpers


def test_container_versioning_helpers(parent_of_two: TestContainer):
    """
    Test that the .versioning helper of a subclass like `TestContainer` returns a `TestContainerVersion`, and
    same for the base class `Container` equivalent.
    """
    assert isinstance(parent_of_two, TestContainer)
    base_container = parent_of_two.container
    assert base_container.__class__ is Container
    container_version = base_container.versioning.draft
    assert container_version.__class__ is ContainerVersion
    subclass_version = parent_of_two.versioning.draft
    assert isinstance(subclass_version, TestContainerVersion)
    assert subclass_version.container_version == container_version
    assert subclass_version.container_version.container == base_container
    assert subclass_version.container_version.container.testcontainer == parent_of_two


# create_next_container_version


def test_create_next_container_version_no_changes(parent_of_two: TestContainer, other_user):
    """
    Test creating a new version of the "parent of two" container, but without
    any actual changes.
    """
    original_version = parent_of_two.versioning.draft
    assert original_version.version_num == 1

    # Create a new version with no changes:
    v2_date = datetime.now(tz=timezone.utc)
    version_2 = publishing_api.create_next_container_version(
        parent_of_two,
        created=v2_date,
        created_by=other_user.pk,
        # Specify no changes at all
    )

    # assert_type(version_2, TestContainerVersion)
    # ^ Must come before 'assert isinstance(...)'. Unfortunately, getting the subclass return type in python 3.12 is not
    # possible unless we explicitly pass in the ContainerVersion subclass as a parameter (which makes the API less
    # generic) or convert `create_next_container_version()` to a classmethod on Container, which is inconsistent with
    # our convention of a function-based public API and semi-private model API.
    assert isinstance(version_2, TestContainerVersion)

    # Now it should have an incremented version number but be unchanged:
    assert version_2 == parent_of_two.versioning.draft
    assert version_2.version_num == 2
    assert version_2.title == original_version.title
    # Since we didn't change the entities, the same entity list should be re-used:
    assert version_2.entity_list_id == original_version.entity_list_id
    assert version_2.created == v2_date
    assert version_2.created_by == other_user
    assert publishing_api.get_container_children_entities_keys(
        original_version
    ) == publishing_api.get_container_children_entities_keys(version_2)


def test_create_next_container_version_with_changes(
    parent_of_two: TestContainer, child_entity1: TestEntity, child_entity2: TestEntity
):
    """
    Test creating a new version of the "parent of two" container, changing the
    title and swapping the order of the children
    """
    original_version = parent_of_two.versioning.draft
    assert original_version.version_num == 1

    # Create a new version, specifying version number 5 and changing the title and the order of the children:
    v5_date = datetime.now(tz=timezone.utc)
    publishing_api.create_next_container_version(
        parent_of_two,
        title="New Title - children reversed",
        entities=[child_entity2, child_entity1],  # Reversed from original [child_entity1, child_entity2] order
        force_version_num=5,
        created=v5_date,
        created_by=None,
    )

    # Now retrieve the new version:
    version_5 = parent_of_two.versioning.draft
    assert parent_of_two.versioning.published is None  # No change to published version
    assert version_5.version_num == 5
    assert version_5.created == v5_date
    assert version_5.created_by is None
    assert version_5.title == "New Title - children reversed"
    assert version_5.entity_list_id != original_version.entity_list_id
    assert publishing_api.get_container_children_entities_keys(version_5) == ["child_entity2", "child_entity1"]


def test_create_next_container_version_with_append(
    parent_of_two: TestContainer,
    child_entity1: TestEntity,
    child_entity2: TestEntity,
    child_entity3: TestEntity,
):
    """
    Test creating a new version of the "parent of two" container, using the APPEND action to append new children.
    """
    original_version = parent_of_two.versioning.draft
    assert original_version.version_num == 1
    child_entity1_v1 = child_entity1.versioning.draft
    assert child_entity1_v1.version_num == 1

    # Create a new version, APPENDing entity 3 and 📌 pinned entity1 (v1)
    version_2 = publishing_api.create_next_container_version(
        parent_of_two,
        entities=[child_entity3, child_entity1_v1],
        created=now,
        created_by=None,
        entities_action=publishing_api.ChildrenEntitiesAction.APPEND,
    )

    assert parent_of_two.versioning.draft == version_2
    assert publishing_api.get_entities_in_container(parent_of_two, published=False) == [
        Entry(child_entity1.versioning.draft, pinned=False),  # Unchanged, original first child
        Entry(child_entity2.versioning.draft, pinned=False),  # Unchanged, original second child
        Entry(child_entity3.versioning.draft, pinned=False),  # 🆕 entity 3, appended, unpinned
        Entry(child_entity1_v1, pinned=True),  # 🆕 entity 1, appended, 📌 pinned
    ]


def test_create_next_container_version_with_remove_1(
    parent_of_six: TestContainer,
    child_entity1: TestEntity,
    child_entity2: TestEntity,
    child_entity3: TestEntity,
):
    """
    Test creating a new version of the "parent of two" container, using the REMOVE action to remove children.
    """
    ####################################################################################################################
    # TODO: Note: this "REMOVE" API isn't really a great API. It needs all these tests cases to handle the case of
    # duplicate entries, and pinned vs. unpinned, and we don't even use "pinning" in Open edX yet. We should consider
    # dropping the APPEND/REMOVE APIs altogether and just having a simple "replace all children with this new list" API.
    ####################################################################################################################

    # Before looks like this:
    assert publishing_api.get_entities_in_container(parent_of_six, published=False) == [
        Entry(child_entity3.versioning.draft, pinned=True),  # entity 3, 📌 pinned
        Entry(child_entity2.versioning.draft, pinned=True),  # entity 2, 📌 pinned
        Entry(child_entity1.versioning.draft, pinned=False),  # entity 1, unpinned
        Entry(child_entity1.versioning.draft, pinned=False),  # entity 1, unpinned
        Entry(child_entity2.versioning.draft, pinned=True),  # entity 2, 📌 pinned
        Entry(child_entity3.versioning.draft, pinned=False),  # entity 3, unpinned
    ]
    # Remove "entity 1 unpinned" - should remove both:
    publishing_api.create_next_container_version(
        parent_of_six.pk,
        entities=[child_entity1],
        created=now,
        created_by=None,
        entities_action=publishing_api.ChildrenEntitiesAction.REMOVE,
    )
    # Now it looks like:

    assert publishing_api.get_entities_in_container(parent_of_six, published=False) == [
        Entry(child_entity3.versioning.draft, pinned=True),  # entity 3, 📌 pinned
        Entry(child_entity2.versioning.draft, pinned=True),  # entity 2, 📌 pinned
        # entity 1 unpinned x2 removed
        Entry(child_entity2.versioning.draft, pinned=True),  # entity 2, 📌 pinned
        Entry(child_entity3.versioning.draft, pinned=False),  # entity 3, unpinned
    ]


def test_create_next_container_version_with_remove_2(
    parent_of_six: TestContainer,
    child_entity1: TestEntity,
    child_entity2: TestEntity,
    child_entity3: TestEntity,
):
    """
    Test creating a new version of the "parent of two" container, using the REMOVE action to remove children.
    """
    # Before looks like this:
    assert publishing_api.get_entities_in_container(parent_of_six, published=False) == [
        Entry(child_entity3.versioning.draft, pinned=True),  # entity 3, 📌 pinned
        Entry(child_entity2.versioning.draft, pinned=True),  # entity 2, 📌 pinned
        Entry(child_entity1.versioning.draft, pinned=False),  # entity 1, unpinned
        Entry(child_entity1.versioning.draft, pinned=False),  # entity 1, unpinned
        Entry(child_entity2.versioning.draft, pinned=True),  # entity 2, 📌 pinned
        Entry(child_entity3.versioning.draft, pinned=False),  # entity 3, unpinned
    ]
    # Remove "entity 2 pinned" - should remove both:
    publishing_api.create_next_container_version(
        parent_of_six.pk,
        entities=[child_entity2.versioning.draft],  # specify the version for "pinned"
        created=now,
        created_by=None,
        entities_action=publishing_api.ChildrenEntitiesAction.REMOVE,
    )
    # Now it looks like:

    assert publishing_api.get_entities_in_container(parent_of_six, published=False) == [
        Entry(child_entity3.versioning.draft, pinned=True),  # entity 3, 📌 pinned
        # removed
        Entry(child_entity1.versioning.draft, pinned=False),  # entity 1, unpinned
        Entry(child_entity1.versioning.draft, pinned=False),  # entity 1, unpinned
        # removed
        Entry(child_entity3.versioning.draft, pinned=False),  # entity 3, unpinned
    ]


def test_create_next_container_version_with_remove_3(
    parent_of_six: TestContainer,
    child_entity1: TestEntity,
    child_entity2: TestEntity,
    child_entity3: TestEntity,
):
    """
    Test creating a new version of the "parent of two" container, using the REMOVE action to remove children.
    """
    # Before looks like this:
    assert publishing_api.get_entities_in_container(parent_of_six, published=False) == [
        Entry(child_entity3.versioning.draft, pinned=True),  # entity 3, 📌 pinned
        Entry(child_entity2.versioning.draft, pinned=True),  # entity 2, 📌 pinned
        Entry(child_entity1.versioning.draft, pinned=False),  # entity 1, unpinned
        Entry(child_entity1.versioning.draft, pinned=False),  # entity 1, unpinned
        Entry(child_entity2.versioning.draft, pinned=True),  # entity 2, 📌 pinned
        Entry(child_entity3.versioning.draft, pinned=False),  # entity 3, unpinned
    ]
    # Remove "entity 3 pinned" - should remove only one:
    publishing_api.create_next_container_version(
        parent_of_six.pk,
        entities=[child_entity3.versioning.draft],  # specify the version for "pinned"
        created=now,
        created_by=None,
        entities_action=publishing_api.ChildrenEntitiesAction.REMOVE,
    )
    # Now it looks like:

    assert publishing_api.get_entities_in_container(parent_of_six, published=False) == [
        # entity 3 pinned removed
        Entry(child_entity2.versioning.draft, pinned=True),  # entity 2, 📌 pinned
        Entry(child_entity1.versioning.draft, pinned=False),  # entity 1, unpinned
        Entry(child_entity1.versioning.draft, pinned=False),  # entity 1, unpinned
        Entry(child_entity2.versioning.draft, pinned=True),  # entity 2, 📌 pinned
        Entry(child_entity3.versioning.draft, pinned=False),  # entity 3, unpinned so should not be removed
    ]


def test_create_next_container_version_with_remove_4(
    parent_of_six: TestContainer,
    child_entity1: TestEntity,
    child_entity2: TestEntity,
    child_entity3: TestEntity,
):
    """
    Test creating a new version of the "parent of two" container, using the REMOVE action to remove children.
    """
    # Before looks like this:
    assert publishing_api.get_entities_in_container(parent_of_six, published=False) == [
        Entry(child_entity3.versioning.draft, pinned=True),  # entity 3, 📌 pinned
        Entry(child_entity2.versioning.draft, pinned=True),  # entity 2, 📌 pinned
        Entry(child_entity1.versioning.draft, pinned=False),  # entity 1, unpinned
        Entry(child_entity1.versioning.draft, pinned=False),  # entity 1, unpinned
        Entry(child_entity2.versioning.draft, pinned=True),  # entity 2, 📌 pinned
        Entry(child_entity3.versioning.draft, pinned=False),  # entity 3, unpinned
    ]
    # Remove "entity 3 unpinned" - should remove only one:
    publishing_api.create_next_container_version(
        parent_of_six.pk,
        entities=[child_entity3],
        created=now,
        created_by=None,
        entities_action=publishing_api.ChildrenEntitiesAction.REMOVE,
    )
    # Now it looks like:

    assert publishing_api.get_entities_in_container(parent_of_six, published=False) == [
        Entry(child_entity3.versioning.draft, pinned=True),  # entity 3, 📌 pinned so should not be removed
        Entry(child_entity2.versioning.draft, pinned=True),  # entity 2, 📌 pinned
        Entry(child_entity1.versioning.draft, pinned=False),  # entity 1, unpinned
        Entry(child_entity1.versioning.draft, pinned=False),  # entity 1, unpinned
        Entry(child_entity2.versioning.draft, pinned=True),  # entity 2, 📌 pinned
        # entity 3 unpinned removed
    ]


def test_create_next_container_version_with_conflicting_version(parent_of_two: TestContainer):
    """
    Test that an appropriate error is raised when calling `create_next_container_version` and specifying a version
    number that already exists.
    """

    def create_v5():
        """Create a new version, specifying version number 5 and changing the title and the order of the children."""
        publishing_api.create_next_container_version(
            parent_of_two.pk,
            title="New version - forced as v5",
            force_version_num=5,
            created=now,
            created_by=None,
        )

    # First it should work:
    create_v5()
    # Then it should fail:
    with pytest.raises(IntegrityError):
        create_v5()


def test_create_next_container_version_uninstalled_plugin(container_of_uninstalled_type: Container):
    """
    Test that an appropriate error is raised when calling `create_next_container_version` for a container whose type
    implementation is no longer installed. Such containers should still be readable but not writable.
    """
    with pytest.raises(publishing_api.ContainerImplementationMissingError):
        publishing_api.create_next_container_version(
            container_of_uninstalled_type.pk,
            title="New version of the container",
            created=now,
            created_by=None,
        )


def test_create_next_container_version_other_lp(parent_of_two: TestContainer, other_lp_child: PublishableEntity):
    """
    Test that an appropriate error is raised when trying to add a child from another learning package to a container.
    """
    with pytest.raises(ValidationError, match="Container entities must be from the same learning package."):
        publishing_api.create_next_container_version(
            parent_of_two.pk,
            title="Bad Version with entities from another learning package",
            created=now,
            created_by=None,
            entities=[other_lp_child],  # <-- from "lp2" Learning Package
        )


# get_container


def test_get_container(parent_of_two: TestContainer, django_assert_num_queries) -> None:
    """
    Test `get_container()`
    """
    with django_assert_num_queries(1):
        result = publishing_api.get_container(parent_of_two.pk)
    assert result == parent_of_two.container
    # Versioning data should be pre-loaded via select_related()
    with django_assert_num_queries(0):
        assert result.versioning.has_unpublished_changes


def test_get_container_nonexistent() -> None:
    """
    Test `get_container()` with an invalid ID.
    """
    with pytest.raises(Container.DoesNotExist):
        publishing_api.get_container(-5000)


def test_get_container_soft_deleted(parent_of_two: TestContainer) -> None:
    """
    Test `get_container()` with a soft deleted container
    """
    publishing_api.soft_delete_draft(parent_of_two.pk, deleted_by=None)
    parent_of_two.refresh_from_db()
    assert parent_of_two.versioning.draft is None
    assert parent_of_two.versioning.published is None
    # Get the container
    result = publishing_api.get_container(parent_of_two.pk)
    assert result == parent_of_two.container  # It works fine! get_container() ignores publish/delete status.


def test_get_container_uninstalled_type(container_of_uninstalled_type: Container) -> None:
    """
    Test `get_container()` with a container from an uninstalled plugin
    """
    # Nothing special happens. It should work fine.
    result = publishing_api.get_container(container_of_uninstalled_type.pk)
    assert result == container_of_uninstalled_type


# get_container_version


def test_get_container_version(parent_of_two: TestContainer) -> None:
    """
    Test getting a specific container version
    """
    # Note: This is not a super useful API, and we're not using it anywhere.
    cv = publishing_api.get_container_version(parent_of_two.versioning.draft.pk)
    assert cv == parent_of_two.versioning.draft.container_version


def test_get_container_version_nonexistent() -> None:
    """
    Test getting a specific container version that doesn't exist
    """
    with pytest.raises(ContainerVersion.DoesNotExist):
        publishing_api.get_container_version(-500)


# get_container_by_key


def test_get_container_by_key(lp: LearningPackage, parent_of_two: TestContainer) -> None:
    """
    Test getting a specific container by key
    """
    result = publishing_api.get_container_by_key(lp.pk, parent_of_two.key)
    assert result == parent_of_two.container
    # The API always returns "Container", not specific subclasses like TestContainer:
    assert result.__class__ is Container


def test_get_container_by_key_nonexistent(lp: LearningPackage) -> None:
    """
    Test getting a specific container by key, where the key and/or learning package is invalid
    """
    with pytest.raises(LearningPackage.DoesNotExist):
        publishing_api.get_container_by_key(32874, "invalid-key")

    with pytest.raises(Container.DoesNotExist):
        publishing_api.get_container_by_key(lp.pk, "invalid-key")


# get_container_type_code and get_container_type


def test_get_container_type(grandparent: ContainerContainer, parent_of_two: TestContainer, child_entity1: TestEntity):
    """
    Test get_container_type_code() and get_container_type()
    """
    # Grandparent is a "ContainerContainer":
    assert isinstance(grandparent, ContainerContainer)
    assert publishing_api.get_container_type_code(grandparent) == "test_container_container"
    assert publishing_api.get_container_type(grandparent) is ContainerContainer
    # The functions work even if we pass a generic "Container" object:
    assert isinstance(grandparent.base_container, Container)
    assert publishing_api.get_container_type_code(grandparent.base_container) == "test_container_container"
    assert publishing_api.get_container_type(grandparent.base_container) is ContainerContainer

    # "Parent of Two" is a "TestContainer":
    assert isinstance(parent_of_two, TestContainer)
    assert publishing_api.get_container_type_code(parent_of_two) == "test_generic"
    assert publishing_api.get_container_type(parent_of_two) is TestContainer
    assert isinstance(parent_of_two.container, Container)
    assert publishing_api.get_container_type_code(parent_of_two.container) == "test_generic"
    assert publishing_api.get_container_type(parent_of_two.container) is TestContainer

    # Passing in a non-container will trigger an assert failure:
    with pytest.raises(AssertionError):
        publishing_api.get_container_type(child_entity1)  # type: ignore


def test_get_container_type_deleted(container_of_uninstalled_type: Container):
    """
    Get ContainerType will raise ValueError if the container type implementation
    is no longer available
    """
    with pytest.raises(
        publishing_api.ContainerImplementationMissingError,
        match='An implementation for "misc" containers is not currently installed.',
    ):
        publishing_api.get_container_type(container_of_uninstalled_type)

    # But get_container_type_code() should still work:
    assert publishing_api.get_container_type_code(container_of_uninstalled_type) == "misc"


# get_containers


def test_get_containers(
    lp: LearningPackage,
    grandparent: ContainerContainer,
    parent_of_two: TestContainer,
    parent_of_three: TestContainer,
    lp2: LearningPackage,
    other_lp_parent: TestContainer,
):
    """
    Test that we can get all containers in a Learning Package
    """
    result = list(publishing_api.get_containers(lp.id))
    # The API always returns Container base class instances, never specific types:
    assert [c.__class__ is Container for c in result]
    # (we _could_ implement a get_typed_containers() API, but there's probably no need?)
    assert result == [
        # Default ordering is in the order they were created:
        parent_of_two.container,
        parent_of_three.container,
        grandparent.base_container,
    ]
    # Now repeat with the other Learning Package, to make sure they're isolated:
    assert list(publishing_api.get_containers(lp2.id)) == [
        other_lp_parent.container,
    ]


def test_get_containers_soft_deleted(
    lp: LearningPackage,
    grandparent: ContainerContainer,
    parent_of_two: TestContainer,
    parent_of_three: TestContainer,
):
    """
    Test that soft deleted containers are excluded from `get_containers()` by
    default, but can be included.
    """
    # Soft delete `parent_of_two`:
    publishing_api.soft_delete_draft(parent_of_two.pk)
    # Now it should not be included in the result:
    assert list(publishing_api.get_containers(lp.id)) == [
        # parent_of_two is not returned.
        parent_of_three.container,
        grandparent.base_container,
    ]
    # Unless we specify include_deleted=True:
    assert list(publishing_api.get_containers(lp.id, include_deleted=True)) == [
        parent_of_two.container,
        parent_of_three.container,
        grandparent.base_container,
    ]


# General publishing tests.


def test_contains_unpublished_changes_queries(
    grandparent: ContainerContainer, child_entity1: TestEntity, django_assert_num_queries
) -> None:
    """Test that `contains_unpublished_changes()` works, and check how many queries it uses"""
    # Setup: grandparent and all its decsendants are unpublished drafts only.
    assert grandparent.versioning.published is None

    # Tests:
    with django_assert_num_queries(1):
        assert publishing_api.contains_unpublished_changes(grandparent)
    with django_assert_num_queries(1):
        assert publishing_api.contains_unpublished_changes(grandparent.pk)

    # Publish grandparent and all its descendants:
    with django_assert_num_queries(143):  # TODO: investigate as this seems high!
        publish_entity(grandparent)

    # Tests:
    with django_assert_num_queries(1):
        assert not publishing_api.contains_unpublished_changes(grandparent)

    # Now make a tiny change to a grandchild component (not a direct child of "grandparent"), and make sure it's
    # detected:
    publishing_api.create_publishable_entity_version(
        child_entity1.pk,
        version_num=2,
        title="Modified grandchild",
        created=now,
        created_by=None,
    )
    child_entity1.refresh_from_db()
    assert child_entity1.versioning.has_unpublished_changes

    with django_assert_num_queries(1):
        assert publishing_api.contains_unpublished_changes(grandparent)


def test_auto_publish_children(
    parent_of_two: TestContainer,
    child_entity1: TestEntity,
    child_entity2: TestEntity,
    child_entity3: TestEntity,
):
    """
    Test that publishing a container publishes its child components automatically.
    """
    # At first, nothing is published:
    assert publishing_api.contains_unpublished_changes(parent_of_two.pk)
    assert child_entity1.versioning.published is None
    assert child_entity2.versioning.published is None
    assert child_entity3.versioning.published is None
    child_entity1_v1 = child_entity1.versioning.draft

    # Publish ONLY the "parent_of_two" container.
    # This should however also auto-publish components 1 & 2 since they're children
    publish_entity(parent_of_two)
    # Now all changes to the container and its two children are published:
    for entity in [parent_of_two, child_entity1, child_entity2, child_entity3]:
        entity.refresh_from_db()
    assert parent_of_two.versioning.has_unpublished_changes is False  # Shallow check
    assert child_entity1.versioning.has_unpublished_changes is False
    assert child_entity2.versioning.has_unpublished_changes is False
    assert publishing_api.contains_unpublished_changes(parent_of_two.pk) is False  # Deep check
    assert child_entity1.versioning.published == child_entity1_v1  # v1 is now the published version.

    # But our other component that's outside the container is not affected:
    child_entity3.refresh_from_db()
    assert child_entity3.versioning.has_unpublished_changes
    assert child_entity3.versioning.published is None


def test_no_publish_parent(parent_of_two: TestContainer, child_entity1: TestEntity):
    """
    Test that publishing an entity does NOT publish changes to its parent containers
    """
    # "child_entity1" is a child of "parent_of_two"
    assert child_entity1.key in publishing_api.get_container_children_entities_keys(parent_of_two.versioning.draft)
    # Neither are published:
    assert child_entity1.versioning.published is None
    assert parent_of_two.versioning.published is None

    # Publish ONLY one of its child components
    publish_entity(child_entity1)
    child_entity1.refresh_from_db()  # Clear cache on '.versioning'
    assert child_entity1.versioning.has_unpublished_changes is False

    # The container that contains that component should still be unpublished:
    parent_of_two.refresh_from_db()  # Clear cache on '.versioning'
    assert parent_of_two.versioning.has_unpublished_changes
    assert parent_of_two.versioning.published is None
    with pytest.raises(ContainerVersion.DoesNotExist):
        # There is no published version of "parent_of_two":
        publishing_api.get_entities_in_container(parent_of_two, published=True)


def test_add_entity_after_publish(lp: LearningPackage, parent_of_two: TestContainer, child_entity3: TestEntity):
    """
    Adding an entity to a published container will create a new version and show that the container has unpublished
    changes.
    """
    parent_of_two_v1 = parent_of_two.versioning.draft
    assert parent_of_two_v1.version_num == 1
    assert parent_of_two.versioning.published is None
    # Publish everything in the learning package:
    publishing_api.publish_all_drafts(lp.pk)
    parent_of_two.refresh_from_db()  # Reloading is necessary
    assert not parent_of_two.versioning.has_unpublished_changes  # Shallow check
    assert not publishing_api.contains_unpublished_changes(parent_of_two)  # Deeper check

    # Add a published entity (child_entity3, unpinned):
    parent_of_two_v2 = publishing_api.create_next_container_version(
        parent_of_two.pk,
        entities=[child_entity3],
        created=now,
        created_by=None,
        entities_action=publishing_api.ChildrenEntitiesAction.APPEND,
    )
    # Now the container should have unpublished changes:
    parent_of_two.refresh_from_db()  # Reloading the container is necessary
    assert parent_of_two.versioning.has_unpublished_changes  # Shallow check - adding a child changes the container
    assert publishing_api.contains_unpublished_changes(parent_of_two)  # Deeper check
    assert parent_of_two.versioning.draft == parent_of_two_v2
    assert parent_of_two.versioning.published == parent_of_two_v1


def test_modify_unpinned_entity_after_publish(
    parent_of_two: TestContainer, child_entity1: TestEntity, child_entity2: TestEntity
):
    """
    Modifying an unpinned entity in a published container will NOT create a new version nor show that the container has
    unpublished changes (but it will "contain" unpublished changes). The modifications will appear in the published
    version of the container only after the child entity is published.
    """
    # Use "parent_of_two" which has two unpinned child entities.
    # Publish it and its two children:
    publish_entity(parent_of_two)
    parent_of_two.refresh_from_db()  # Technically reloading is only needed if we accessed 'versioning' before publish
    child_entity1_v1 = child_entity1.versioning.draft
    child_entity2_v1 = child_entity2.versioning.draft

    assert parent_of_two.versioning.has_unpublished_changes is False  # Shallow check
    assert publishing_api.contains_unpublished_changes(parent_of_two.pk) is False  # Deeper check
    assert child_entity1.versioning.has_unpublished_changes is False

    # Now modify the child entity (it remains a draft):
    child_entity1_v2 = modify_entity(child_entity1)

    # The component now has unpublished changes; the container doesn't directly but does contain
    parent_of_two.refresh_from_db()  # Reloading the container is necessary, or '.versioning' will be outdated
    child_entity1.refresh_from_db()
    assert (
        parent_of_two.versioning.has_unpublished_changes is False
    )  # Shallow check should be false - container is unchanged
    assert publishing_api.contains_unpublished_changes(parent_of_two.pk)  # But the container DOES "contain" changes
    assert child_entity1.versioning.has_unpublished_changes

    # Since the child's changes haven't been published, they should only appear in the draft container
    assert publishing_api.get_entities_in_container(parent_of_two, published=False) == [
        Entry(child_entity1_v2),  # new version
        Entry(child_entity2_v1),  # unchanged second child
    ]
    assert publishing_api.get_entities_in_container(parent_of_two, published=True) == [
        Entry(child_entity1_v1),  # old version
        Entry(child_entity2_v1),  # unchanged second child
    ]

    # But if we publish the child, the changes will appear in the published version of the container.
    publish_entity(child_entity1)
    assert publishing_api.get_entities_in_container(parent_of_two, published=False) == [
        Entry(child_entity1_v2),  # new version
        Entry(child_entity2_v1),  # unchanged second child
    ]
    assert publishing_api.get_entities_in_container(parent_of_two, published=True) == [
        Entry(child_entity1_v2),  # new version
        Entry(child_entity2_v1),  # unchanged second child
    ]
    assert publishing_api.contains_unpublished_changes(parent_of_two) is False  # No longer contains unpublished changes


def test_modify_pinned_entity(
    lp: LearningPackage,
    parent_of_three: TestContainer,
    child_entity1: TestEntity,
    child_entity2: TestEntity,
    child_entity3: TestEntity,
):
    """
    When a pinned 📌 entity in a container is modified and/or published, it will have no effect on either the draft nor
    published version of the container, which will continue to use the pinned version.
    """
    # Note: "parent_of_three" has two pinned children and one unpinned
    expected_contents = [
        Entry(child_entity3.versioning.draft, pinned=True),  # pinned 📌 to v1
        Entry(child_entity2.versioning.draft, pinned=True),  # pinned 📌 to v1
        Entry(child_entity1.versioning.draft, pinned=False),
    ]
    assert publishing_api.get_entities_in_container(parent_of_three, published=False) == expected_contents

    # Publish everything
    publishing_api.publish_all_drafts(lp.id)

    # Now modify the first 📌 pinned child entity (#3) by changing its title (it remains a draft):
    modify_entity(child_entity3)

    # The component now has unpublished changes; the container is entirely unaffected
    parent_of_three.refresh_from_db()  # Reloading the container is necessary, or '.versioning' will be outdated
    child_entity3.refresh_from_db()
    assert parent_of_three.versioning.has_unpublished_changes is False  # Shallow check
    assert publishing_api.contains_unpublished_changes(parent_of_three) is False  # Deep check
    assert child_entity3.versioning.has_unpublished_changes is True

    # Neither the draft nor the published version of the container is affected
    assert publishing_api.get_entities_in_container(parent_of_three, published=False) == expected_contents
    assert publishing_api.get_entities_in_container(parent_of_three, published=True) == expected_contents
    # Even if we publish the component, the container stays pinned to the specified version:
    publish_entity(child_entity3)
    assert publishing_api.get_entities_in_container(parent_of_three, published=False) == expected_contents
    assert publishing_api.get_entities_in_container(parent_of_three, published=True) == expected_contents


def test_publishing_shared_component(lp: LearningPackage):
    """
    A complex test case involving two units with a shared component and other non-shared components.

    Note these are not actual "Unit"s nor "Components" but instead `TestContainer` and `TestEntity` standing
    in for them.

    Unit 1: components C1, C2, C3
    Unit 2: components C2, C4, C5
    Everything is "unpinned".
    """
    # 1️⃣ Create the units and publish them:
    c1, c2, c3, c4, c5 = [create_test_entity(lp, key=f"C{i}", title=f"Component {i}") for i in range(1, 6)]
    c1_v1 = c1.versioning.draft
    c3_v1 = c3.versioning.draft
    c4_v1 = c4.versioning.draft
    c5_v1 = c5.versioning.draft
    unit1, _ = publishing_api.create_container_and_version(
        lp.pk,
        entities=[c1, c2, c3],
        title="Unit 1",
        key="unit:1",
        created=now,
        created_by=None,
        container_type=TestContainer,
    )
    unit2, _ = publishing_api.create_container_and_version(
        lp.pk,
        entities=[c2, c4, c5],
        title="Unit 2",
        key="unit:2",
        created=now,
        created_by=None,
        container_type=TestContainer,
    )
    publishing_api.publish_all_drafts(lp.pk)
    assert publishing_api.contains_unpublished_changes(unit1.pk) is False
    assert publishing_api.contains_unpublished_changes(unit2.pk) is False

    # 2️⃣ Then the author edits C2 inside of Unit 1 making C2v2.
    c2_v2 = modify_entity(c2)
    # This makes U1 and U2 both show up as Units that CONTAIN unpublished changes, because they share the component.
    assert publishing_api.contains_unpublished_changes(unit1.pk)
    assert publishing_api.contains_unpublished_changes(unit2.pk)
    # (But the units themselves are unchanged:)
    unit1.refresh_from_db()
    unit2.refresh_from_db()
    assert unit1.versioning.has_unpublished_changes is False
    assert unit2.versioning.has_unpublished_changes is False

    # 3️⃣ In addition to this, the author also modifies another component in Unit 2 (C5)
    c5_v2 = modify_entity(c5)

    # 4️⃣ The author then publishes Unit 1, and therefore everything in it.
    publish_entity(unit1)

    # Result: Unit 1 will show the newly published version of C2:
    assert publishing_api.get_entities_in_container(unit1, published=True) == [
        Entry(c1_v1),
        Entry(c2_v2),  # new published version of C2
        Entry(c3_v1),
    ]

    # Result: someone looking at Unit 2 should see the newly published component 2, because publishing it anywhere
    # publishes it everywhere. But publishing C2 and Unit 1 does not affect the other components in Unit 2.
    # (Publish propagates downward, not upward)
    assert publishing_api.get_entities_in_container(unit2, published=True) == [
        Entry(c2_v2),  # new published version of C2
        Entry(c4_v1),  # still original version of C4 (it was never modified)
        Entry(c5_v1),  # still original version of C5 (it hasn't been published)
    ]

    # Result: Unit 2 CONTAINS unpublished changes because of the modified C5. Unit 1 doesn't contain unpub changes.
    assert publishing_api.contains_unpublished_changes(unit1.pk) is False
    assert publishing_api.contains_unpublished_changes(unit2.pk)

    # 5️⃣ Publish component C5, which should be the only thing unpublished in the learning package
    publish_entity(c5)
    # Result: Unit 2 shows the new version of C5 and no longer contains unpublished changes:
    assert publishing_api.get_entities_in_container(unit2, published=True) == [
        Entry(c2_v2),  # new published version of C2
        Entry(c4_v1),  # still original version of C4 (it was never modified)
        Entry(c5_v2),  # new published version of C5
    ]
    assert publishing_api.contains_unpublished_changes(unit2.pk) is False


# get_entities_in_container


def test_get_entities_in_container(
    parent_of_three: TestContainer,
    child_entity1: TestEntity,
    child_entity2: TestEntity,
    child_entity3: TestEntity,
) -> None:
    """
    Test `get_entities_in_container()`
    """
    expected = [
        # This particular container has three children (3, 2, 1), two of them 📌 pinned:
        publishing_api.ContainerEntityListEntry(child_entity3.versioning.draft.publishable_entity_version, pinned=True),
        publishing_api.ContainerEntityListEntry(child_entity2.versioning.draft.publishable_entity_version, pinned=True),
        publishing_api.ContainerEntityListEntry(
            child_entity1.versioning.draft.publishable_entity_version, pinned=False
        ),
    ]
    assert publishing_api.get_entities_in_container(parent_of_three, published=False) == expected
    # Asking about the published version will throw an exception, since no published version exists yet:
    with pytest.raises(ContainerVersion.DoesNotExist):
        publishing_api.get_entities_in_container(parent_of_three, published=True)

    publish_entity(parent_of_three)
    assert publishing_api.get_entities_in_container(parent_of_three, published=True) == expected


def test_get_entities_in_container_soft_deletion_unpinned(
    parent_of_three: TestContainer,
    child_entity1: TestEntity,
    child_entity2: TestEntity,
    child_entity3: TestEntity,
) -> None:
    """Test that `get_entities_in_container()` correctly handles soft deletion of child entities."""
    before = [  # This particular container has three children (3, 2, 1), two of them 📌 pinned:
        Entry(child_entity3.versioning.draft, pinned=True),
        Entry(child_entity2.versioning.draft, pinned=True),
        Entry(child_entity1.versioning.draft, pinned=False),
    ]
    assert publishing_api.get_entities_in_container(parent_of_three, published=False) == before

    # First, publish everything:
    publish_entity(parent_of_three)
    # Soft delete the third, unpinned child (child_entity1):
    publishing_api.soft_delete_draft(child_entity1.pk)

    # That deletion should NOT count as a change to the container itself:
    parent_of_three.refresh_from_db()
    assert not parent_of_three.versioning.has_unpublished_changes
    # But it "contains" a change (a deletion)
    assert publishing_api.contains_unpublished_changes(parent_of_three)

    after = [
        before[0],  # first two children are unchanged
        before[1],
        # the third child (#1) has been soft deleted and doesn't appear in the draft
    ]
    assert publishing_api.get_entities_in_container(parent_of_three, published=False) == after


def test_get_entities_in_container_soft_deletion_pinned(
    parent_of_three: TestContainer,
    child_entity1: TestEntity,
    child_entity2: TestEntity,
    child_entity3: TestEntity,
) -> None:
    """Test that `get_entities_in_container()` correctly handles soft deletion of 📌 pinned child entities."""
    before = [  # This particular container has three children (3, 2, 1), two of them 📌 pinned:
        Entry(child_entity3.versioning.draft, pinned=True),
        Entry(child_entity2.versioning.draft, pinned=True),
        Entry(child_entity1.versioning.draft, pinned=False),
    ]
    assert publishing_api.get_entities_in_container(parent_of_three, published=False) == before

    # First, publish everything:
    publish_entity(parent_of_three)
    # Soft delete child 2:
    publishing_api.soft_delete_draft(child_entity2.pk)

    # The above deletions should NOT count as a change to the container itself, in any way:
    parent_of_three.refresh_from_db()
    assert not parent_of_three.versioning.has_unpublished_changes
    assert not publishing_api.contains_unpublished_changes(parent_of_three)

    # Since the second child was pinned to an exact version, soft deleting it doesn't affect the contents of the
    # container at all:
    assert publishing_api.get_entities_in_container(parent_of_three, published=False) == before


# get_entities_in_container_as_of


def test_snapshots_of_published_unit(lp: LearningPackage, child_entity1: TestEntity, child_entity2: TestEntity):
    """Test that we can access snapshots of the historic published version of containers and their contents."""
    child_entity1_v1 = child_entity1.versioning.draft

    # At first the container has one child (unpinned):
    container = create_test_container(lp, key="c", entities=[child_entity1])
    modify_entity(child_entity1, title="Component 1 as of checkpoint 1")
    _, before_publish = publishing_api.get_entities_in_container_as_of(container, 0)
    assert not before_publish  # Empty list

    # Publish everything, creating Checkpoint 1
    checkpoint_1 = publishing_api.publish_all_drafts(lp.id, message="checkpoint 1")

    ########################################################################

    # Now we update the title of the component.
    modify_entity(child_entity1, title="Component 1 as of checkpoint 2")
    # Publish everything, creating Checkpoint 2
    checkpoint_2 = publishing_api.publish_all_drafts(lp.id, message="checkpoint 2")
    ########################################################################

    # Now add a second component to the unit:
    modify_entity(child_entity1, title="Component 1 as of checkpoint 3")
    modify_entity(child_entity2, title="Component 2 as of checkpoint 3")
    publishing_api.create_next_container_version(
        container.pk,
        title="Unit title in checkpoint 3",
        entities=[child_entity1, child_entity2],
        created=now,
        created_by=None,
    )
    # Publish everything, creating Checkpoint 3
    checkpoint_3 = publishing_api.publish_all_drafts(lp.id, message="checkpoint 3")
    ########################################################################

    # Now add a third component to the unit, a pinned 📌 version of component 1.
    # This will test pinned versions and also test adding at the beginning rather than the end of the unit.
    publishing_api.create_next_container_version(
        container.pk,
        title="Unit title in checkpoint 4",
        entities=[child_entity1_v1, child_entity1, child_entity2],
        created=now,
        created_by=None,
    )
    # Publish everything, creating Checkpoint 4
    checkpoint_4 = publishing_api.publish_all_drafts(lp.id, message="checkpoint 4")
    ########################################################################

    # Modify the drafts, but don't publish:
    modify_entity(child_entity1, title="Component 1 draft")
    modify_entity(child_entity2, title="Component 2 draft")

    # Now fetch the snapshots:
    _, as_of_checkpoint_1 = publishing_api.get_entities_in_container_as_of(container, checkpoint_1.pk)
    assert [ev.entity_version.title for ev in as_of_checkpoint_1] == [
        "Component 1 as of checkpoint 1",
    ]
    _, as_of_checkpoint_2 = publishing_api.get_entities_in_container_as_of(container, checkpoint_2.pk)
    assert [ev.entity_version.title for ev in as_of_checkpoint_2] == [
        "Component 1 as of checkpoint 2",
    ]
    _, as_of_checkpoint_3 = publishing_api.get_entities_in_container_as_of(container, checkpoint_3.pk)
    assert [ev.entity_version.title for ev in as_of_checkpoint_3] == [
        "Component 1 as of checkpoint 3",
        "Component 2 as of checkpoint 3",
    ]
    _, as_of_checkpoint_4 = publishing_api.get_entities_in_container_as_of(container, checkpoint_4.pk)
    assert [ev.entity_version.title for ev in as_of_checkpoint_4] == [
        "Child 1 🌴",  # Pinned. This title is self.component_1_v1.title (original v1 title)
        "Component 1 as of checkpoint 3",  # we didn't modify these components so they're same as in snapshot 3
        "Component 2 as of checkpoint 3",  # we didn't modify these components so they're same as in snapshot 3
    ]


# get_containers_with_entity


def test_get_containers_with_entity_draft(
    lp: LearningPackage,
    grandparent: ContainerContainer,
    parent_of_two: TestContainer,
    parent_of_three: TestContainer,
    parent_of_six: TestContainer,
    child_entity1: TestEntity,
    child_entity2: TestEntity,
    child_entity3: TestEntity,
    lp2: LearningPackage,
    other_lp_parent: TestContainer,
    other_lp_child: TestEntity,
    django_assert_num_queries,
):
    """Test that we can efficiently get a list of all the draft containers containing a given entity."""

    # Note this test uses a lot of pre-loaded fixtures. Refer to the diagram in the comments near the top of this file.
    # The idea is to have enough variety to ensure we're testing comprehensively:
    # - duplicate entities in the same container
    # - pinned and unpinned entities
    # - different learning packages

    # "child_entity1" is found in three different containers:
    with django_assert_num_queries(1):
        result = list(publishing_api.get_containers_with_entity(child_entity1.publishable_entity.pk))
    assert result == [  # Note: ordering is in order of container creation
        parent_of_two.container,
        parent_of_three.container,
        parent_of_six.container,  # This should only appear once, not several times.
    ]

    # "child_entity3" is found in two different containers:
    with django_assert_num_queries(1):
        result = list(publishing_api.get_containers_with_entity(child_entity3.publishable_entity.pk))
    assert result == [  # Note: ordering is in order of container creation
        parent_of_three.container,  # pinned in this container
        parent_of_six.container,  # pinned and unpinned in this container
    ]

    # Test retrieving only "unpinned", for cases like potential deletion of a component, where we wouldn't care
    # about pinned uses anyways (they would be unaffected by a delete).

    with django_assert_num_queries(1):
        result = list(
            publishing_api.get_containers_with_entity(child_entity3.publishable_entity.pk, ignore_pinned=True)
        )
    assert result == [  # Note: ordering is in order of container creation
        parent_of_six.container,  # it's pinned and unpinned in this container
    ]

    # Some basic tests of the other learning package:
    assert list(publishing_api.get_containers_with_entity(other_lp_child.publishable_entity.pk)) == [
        other_lp_parent.container
    ]
    assert not list(publishing_api.get_containers_with_entity(other_lp_parent.publishable_entity.pk))


# get_container_children_count


def test_get_container_children_count(
    lp: LearningPackage,
    parent_of_two: TestContainer,
    parent_of_three: TestContainer,
    parent_of_six: TestContainer,
    grandparent: ContainerContainer,
):
    """Test `get_container_children_count()`"""
    publishing_api.publish_all_drafts(lp.pk)
    assert publishing_api.get_container_children_count(parent_of_two, published=False) == 2
    assert publishing_api.get_container_children_count(parent_of_two, published=True) == 2

    assert publishing_api.get_container_children_count(parent_of_three, published=False) == 3
    assert publishing_api.get_container_children_count(parent_of_three, published=True) == 3

    assert publishing_api.get_container_children_count(parent_of_six, published=False) == 6
    assert publishing_api.get_container_children_count(parent_of_six, published=True) == 6
    # grandparent has two direct children - deeper descendants are not counted.
    assert publishing_api.get_container_children_count(grandparent, published=False) == 2
    assert publishing_api.get_container_children_count(grandparent, published=True) == 2

    # Add another container to "grandparent":
    publishing_api.create_next_container_version(
        grandparent,
        entities=[parent_of_two, parent_of_three, parent_of_six],
        created=now,
        created_by=None,
    )
    # Warning: this is required if 'grandparent' is passed by ID to `create_next_container_version()`:
    # grandparent.refresh_from_db()
    assert publishing_api.get_container_children_count(grandparent, published=False) == 3
    assert publishing_api.get_container_children_count(grandparent, published=True) == 2  # published is unchanged


def test_get_container_children_count_soft_deletion(
    lp: LearningPackage,
    parent_of_two: TestContainer,
    parent_of_six: TestContainer,
    child_entity2: TestEntity,
):
    """Test `get_container_children_count()` when an entity is soft deleted"""
    publishing_api.publish_all_drafts(lp.pk)
    publishing_api.soft_delete_draft(child_entity2.pk)
    # "parent_of_two" contains the soft deleted child, so its draft child count is decreased by one:
    assert publishing_api.get_container_children_count(parent_of_two, published=False) == 1
    assert publishing_api.get_container_children_count(parent_of_two, published=True) == 2
    # "parent_of_six" also contains two unpinned entries for the soft deleted child, so its draft child count is
    # decreased by two:
    assert publishing_api.get_container_children_count(parent_of_six, published=False) == 4
    assert publishing_api.get_container_children_count(parent_of_six, published=True) == 6


def test_get_container_children_count_queries(
    lp: LearningPackage,
    parent_of_two: TestContainer,
    parent_of_six: TestContainer,
    django_assert_num_queries,
):
    """Test how many database queries `get_container_children_count()` needs"""
    publishing_api.publish_all_drafts(lp.pk)
    with django_assert_num_queries(6):
        assert publishing_api.get_container_children_count(parent_of_two, published=False) == 2
    with django_assert_num_queries(6):
        assert publishing_api.get_container_children_count(parent_of_two, published=True) == 2
    with django_assert_num_queries(6):
        assert publishing_api.get_container_children_count(parent_of_six, published=False) == 6
    with django_assert_num_queries(6):
        assert publishing_api.get_container_children_count(parent_of_six, published=True) == 6


# get_container_children_entities_keys


def test_get_container_children_entities_keys(grandparent: ContainerContainer, parent_of_six: TestContainer) -> None:
    """Test `get_container_children_entities_keys()`"""

    # TODO: is get_container_children_entities_keys() a useful API method? It's not used in edx-platform.

    assert publishing_api.get_container_children_entities_keys(grandparent.versioning.draft) == [
        # These are the two children of "grandparent" - see diagram near the top of this file.
        "parent_of_two",
        "parent_of_three",
    ]

    assert publishing_api.get_container_children_entities_keys(parent_of_six.versioning.draft) == [
        "child_entity3",
        "child_entity2",
        "child_entity1",
        "child_entity1",
        "child_entity2",
        "child_entity3",
    ]


# Container deletion


def test_soft_delete_container(lp: LearningPackage, parent_of_two: TestContainer, child_entity1: TestEntity):
    """
    I can delete a container without deleting the entities it contains.

    See https://github.com/openedx/frontend-app-authoring/issues/1693
    """
    # Publish everything:
    publish_entity(parent_of_two)
    # Delete the container:
    publishing_api.soft_delete_draft(parent_of_two.publishable_entity_id)
    parent_of_two.refresh_from_db()
    # Now the draft container is [soft] deleted, but the children, published container, and other container are
    # unaffected:
    assert parent_of_two.versioning.draft is None  # container is soft deleted.
    assert parent_of_two.versioning.published is not None
    child_entity1.refresh_from_db()
    assert child_entity1.versioning.draft is not None

    # Publish the changes:
    publishing_api.publish_all_drafts(lp.id)
    # Now the container's published version is also deleted, but nothing else is affected.
    parent_of_two.refresh_from_db()
    assert parent_of_two.versioning.draft is None
    assert parent_of_two.versioning.published is None  # Now this is also None
    child_entity1.refresh_from_db()
    assert child_entity1.versioning.draft == child_entity1.versioning.published
    assert child_entity1.versioning.draft is not None


# Container side effects and dependencies


class TestContainerSideEffects:
    """
    Tests related to Container side effects and dependencies
    """

    def test_parent_child_side_effects(self, lp: LearningPackage) -> None:
        """Test that modifying a child has side-effects on its parent."""
        child_1 = publishing_api.create_publishable_entity(
            lp.id,
            "child_1",
            created=now,
            created_by=None,
        )
        child_1_v1 = publishing_api.create_publishable_entity_version(
            child_1.id,
            version_num=1,
            title="Child 1 🌴",
            created=now,
            created_by=None,
        )
        child_2 = publishing_api.create_publishable_entity(
            lp.id,
            "child_2",
            created=now,
            created_by=None,
        )
        publishing_api.create_publishable_entity_version(
            child_2.id,
            version_num=1,
            title="Child 2 🌴",
            created=now,
            created_by=None,
        )
        container: Container = publishing_api.create_container(
            lp.id,
            "my_container",
            created=now,
            created_by=None,
            container_type=TestContainer,
        )
        container_v1: ContainerVersion = publishing_api.create_container_version(
            container.pk,
            1,
            title="My Container",
            entities=[
                child_1,
                child_2,
            ],
            created=now,
            created_by=None,
        )

        # All this was just set up. Now that we have our container-child
        # relationships, altering a child should add the parent container to
        # the DraftChangeLog.
        child_1_v2 = publishing_api.create_publishable_entity_version(
            child_1.id,
            version_num=2,
            title="Child 1 v2",
            created=now,
            created_by=None,
        )
        last_change_log = DraftChangeLog.objects.order_by("-id").first()
        assert last_change_log is not None
        assert last_change_log.records.count() == 2
        child_1_change = last_change_log.records.get(entity=child_1)
        assert child_1_change.old_version == child_1_v1
        assert child_1_change.new_version == child_1_v2

        # The container should be here, but the versions should be the same for
        # before and after:
        container_change = last_change_log.records.get(entity=container.publishable_entity)
        assert container_change.old_version == container_v1.publishable_entity_version
        assert container_change.new_version == container_v1.publishable_entity_version

        # Exactly one side-effect should have been created because we changed
        # child_1 after it was part of a container.
        side_effects = DraftSideEffect.objects.all()
        assert side_effects.count() == 1
        side_effect = side_effects.first()
        assert side_effect is not None
        assert side_effect.cause == child_1_change
        assert side_effect.effect == container_change

    def test_bulk_parent_child_side_effects(self, lp: LearningPackage) -> None:
        """Test that modifying a child has side-effects on its parent. (bulk version)"""
        with publishing_api.bulk_draft_changes_for(lp.id):
            child_1 = publishing_api.create_publishable_entity(
                lp.id,
                "child_1",
                created=now,
                created_by=None,
            )
            publishing_api.create_publishable_entity_version(
                child_1.id,
                version_num=1,
                title="Child 1 🌴",
                created=now,
                created_by=None,
            )
            child_2 = publishing_api.create_publishable_entity(
                lp.id,
                "child_2",
                created=now,
                created_by=None,
            )
            child_2_v1 = publishing_api.create_publishable_entity_version(
                child_2.id,
                version_num=1,
                title="Child 2 🌴",
                created=now,
                created_by=None,
            )
            container: Container = publishing_api.create_container(
                lp.id,
                "my_container",
                created=now,
                created_by=None,
                container_type=TestContainer,
            )
            container_v1: ContainerVersion = publishing_api.create_container_version(
                container.pk,
                1,
                title="My Container",
                entities=[child_1, child_2],
                created=now,
                created_by=None,
            )

            # All this was just set up. Now that we have our container-child
            # relationships, altering a child should add the parent container to
            # the DraftChangeLog.
            child_1_v2 = publishing_api.create_publishable_entity_version(
                child_1.id,
                version_num=2,
                title="Child 1 v2",
                created=now,
                created_by=None,
            )

        # Because we're doing it in bulk, there's only one DraftChangeLog entry.
        assert DraftChangeLog.objects.count() == 1
        last_change_log = DraftChangeLog.objects.first()
        assert last_change_log is not None
        # There's only ever one change entry per publishable entity
        assert last_change_log.records.count() == 3

        child_1_change = last_change_log.records.get(entity=child_1)
        assert child_1_change.old_version is None
        assert child_1_change.new_version == child_1_v2

        child_2_change = last_change_log.records.get(entity=child_2)
        assert child_2_change.old_version is None
        assert child_2_change.new_version == child_2_v1

        container_change = last_change_log.records.get(entity=container.publishable_entity)
        assert container_change.old_version is None
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

    def test_draft_dependency_multiple_parents(self, lp: LearningPackage) -> None:
        """
        Test that a change in a draft component affects multiple parents.

        This is the scenario where one Component is contained by multiple Units.
        """
        # Set up a Component that lives in two Units
        component = publishing_api.create_publishable_entity(
            lp.id,
            "component_1",
            created=now,
            created_by=None,
        )
        publishing_api.create_publishable_entity_version(
            component.id,
            version_num=1,
            title="Component 1 🌴",
            created=now,
            created_by=None,
        )
        unit_1 = publishing_api.create_container(
            lp.id,
            "unit_1",
            created=now,
            created_by=None,
            container_type=TestContainer,
        )
        unit_2 = publishing_api.create_container(
            lp.id,
            "unit_2",
            created=now,
            created_by=None,
            container_type=TestContainer,
        )
        for unit in [unit_1, unit_2]:
            publishing_api.create_container_version(
                unit.pk,
                1,
                title="My Unit",
                entities=[component],
                created=now,
                created_by=None,
            )

        # At this point there should be no side effects because we created
        # everything from the bottom-up.
        assert not DraftSideEffect.objects.all().exists()

        # Now let's change the Component and make sure it created side-effects
        # for both Units.
        publishing_api.create_publishable_entity_version(
            component.id,
            version_num=2,
            title="Component 1.2 🌴",
            created=now,
            created_by=None,
        )
        side_effects = DraftSideEffect.objects.all()
        assert side_effects.count() == 2
        assert side_effects.filter(cause__entity=component).count() == 2
        assert side_effects.filter(effect__entity=unit_1.publishable_entity).count() == 1
        assert side_effects.filter(effect__entity=unit_2.publishable_entity).count() == 1

    def test_multiple_layers_of_containers(self, lp: LearningPackage) -> None:
        """Test stacking containers three layers deep."""
        # Note that these aren't real "components" and "units". Everything being
        # tested is confined to the publishing app, so those concepts shouldn't
        # be imported here. They're just named this way to make it more obvious
        # what the intended hierarchy is for testing container nesting.
        component = publishing_api.create_publishable_entity(
            lp.id,
            "component_1",
            created=now,
            created_by=None,
        )
        publishing_api.create_publishable_entity_version(
            component.id,
            version_num=1,
            title="Component 1 🌴",
            created=now,
            created_by=None,
        )
        unit = publishing_api.create_container(
            lp.id,
            "unit_1",
            created=now,
            created_by=None,
            container_type=TestContainer,
        )
        publishing_api.create_container_version(
            unit.pk,
            1,
            title="My Unit",
            entities=[component],
            created=now,
            created_by=None,
        )
        subsection = publishing_api.create_container(
            lp.id,
            "subsection_1",
            created=now,
            created_by=None,
            container_type=TestContainer,
        )
        publishing_api.create_container_version(
            subsection.pk,
            1,
            title="My Subsection",
            entities=[unit],
            created=now,
            created_by=None,
        )

        # At this point, no side-effects exist yet because we built it from the
        # bottom-up using different DraftChangeLogs
        assert not DraftSideEffect.objects.all().exists()

        with publishing_api.bulk_draft_changes_for(lp.id) as change_log:
            publishing_api.create_publishable_entity_version(
                component.id,
                version_num=2,
                title="Component 1v2🌴",
                created=now,
                created_by=None,
            )

        assert DraftSideEffect.objects.count() == 2
        component_change = change_log.records.get(entity=component)
        unit_change = change_log.records.get(entity=unit.publishable_entity)
        subsection_change = change_log.records.get(entity=subsection.publishable_entity)

        assert not component_change.affected_by.exists()
        assert unit_change.affected_by.count() == 1
        assert unit_change.affected_by.first().cause == component_change
        assert subsection_change.affected_by.count() == 1
        assert subsection_change.affected_by.first().cause == unit_change

        publish_log = publishing_api.publish_all_drafts(lp.id)
        assert publish_log.records.count() == 3

        publishing_api.create_publishable_entity_version(
            component.pk,
            version_num=3,
            title="Component v2",
            created=now,
            created_by=None,
        )
        publish_log = publishing_api.publish_from_drafts(
            lp.id,
            Draft.objects.filter(entity_id=component.pk),
        )
        assert publish_log.records.count() == 3
        component_publish = publish_log.records.get(entity=component)
        unit_publish = publish_log.records.get(entity=unit.publishable_entity)
        subsection_publish = publish_log.records.get(entity=subsection.publishable_entity)

        assert not component_publish.affected_by.exists()
        assert unit_publish.affected_by.count() == 1
        assert unit_publish.affected_by.first().cause == component_publish  # type: ignore[union-attr]
        assert subsection_publish.affected_by.count() == 1
        assert subsection_publish.affected_by.first().cause == unit_publish  # type: ignore[union-attr]

    def test_publish_all_layers(self, lp: LearningPackage) -> None:
        """Test that we can publish multiple layers from one root."""
        # Note that these aren't real "components" and "units". Everything being
        # tested is confined to the publishing app, so those concepts shouldn't
        # be imported here. They're just named this way to make it more obvious
        # what the intended hierarchy is for testing container nesting.
        component = publishing_api.create_publishable_entity(
            lp.id,
            "component_1",
            created=now,
            created_by=None,
        )
        publishing_api.create_publishable_entity_version(
            component.id,
            version_num=1,
            title="Component 1 🌴",
            created=now,
            created_by=None,
        )
        unit = publishing_api.create_container(
            lp.id,
            "unit_1",
            created=now,
            created_by=None,
            container_type=TestContainer,
        )
        publishing_api.create_container_version(
            unit.pk,
            1,
            title="My Unit",
            entities=[component],
            created=now,
            created_by=None,
        )
        subsection = publishing_api.create_container(
            lp.id,
            "subsection_1",
            created=now,
            created_by=None,
            container_type=TestContainer,
        )
        publishing_api.create_container_version(
            subsection.pk,
            1,
            title="My Subsection",
            entities=[unit],
            created=now,
            created_by=None,
        )
        publish_log = publishing_api.publish_from_drafts(
            lp.id,
            Draft.objects.filter(pk=subsection.pk),
        )

        # The component, unit, and subsection should all be accounted for in
        # the publish log records.
        assert publish_log.records.count() == 3

    def test_container_next_version(self, lp: LearningPackage) -> None:
        """Test that next_version works for containers."""
        child_1 = publishing_api.create_publishable_entity(
            lp.id,
            "child_1",
            created=now,
            created_by=None,
        )
        container = publishing_api.create_container(
            lp.id,
            "my_container",
            created=now,
            created_by=None,
            container_type=TestContainer,
        )
        assert container.versioning.latest is None
        v1 = publishing_api.create_next_container_version(
            container.pk,
            title="My Container v1",
            entities=None,
            created=now,
            created_by=None,
        )
        assert v1.version_num == 1
        assert container.versioning.latest == v1
        v2 = publishing_api.create_next_container_version(
            container.pk,
            title="My Container v2",
            entities=[child_1],
            created=now,
            created_by=None,
        )
        assert v2.version_num == 2
        assert container.versioning.latest == v2
        assert v2.entity_list.entitylistrow_set.count() == 1
        v3 = publishing_api.create_next_container_version(
            container.pk,
            title="My Container v3",
            entities=None,
            created=now,
            created_by=None,
        )
        assert v3.version_num == 3
        assert container.versioning.latest == v3
        # Even though we didn't pass any rows, it should copy the previous version's rows
        assert v2.entity_list.entitylistrow_set.count() == 1


# Tests TODO:
# Test that I can get a [PublishLog] history of a given container and all its children, including children that aren't
#     currently in the container and excluding children that are only in other containers.
# Test that I can get a [PublishLog] history of a given container and its children, that includes changes made to the
#     child components while they were part of the container but excludes changes made to those children while they were
#     not part of the container. 🫣
