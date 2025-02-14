"""
Basic tests for the units API.
"""
import ddt  # type: ignore[import]
import pytest
from django.core.exceptions import ValidationError

from openedx_learning.api import authoring as authoring_api
from openedx_learning.api import authoring_models

from ..components.test_api import ComponentTestCase

Entry = authoring_api.UnitListEntry


@ddt.ddt
class UnitTestCase(ComponentTestCase):
    """ Test cases for Units (containers of components) """

    def setUp(self) -> None:
        super().setUp()
        self.component_1, self.component_1_v1 = self.create_component(
            key="Query Counting",
            title="Querying Counting Problem",
        )
        self.component_2, self.component_2_v1 = self.create_component(
            key="Query Counting (2)",
            title="Querying Counting Problem (2)",
        )

    def create_component(self, *, title: str = "Test Component", key: str = "component:1") -> tuple[
        authoring_models.Component, authoring_models.ComponentVersion
    ]:
        """ Helper method to quickly create a component """
        return authoring_api.create_component_and_version(
            self.learning_package.id,
            component_type=self.problem_type,
            local_key=key,
            title=title,
            created=self.now,
            created_by=None,
        )

    def create_unit_with_components(
        self,
        components: list[authoring_models.Component | authoring_models.ComponentVersion],
        *,
        title="Unit",
        key="unit:key",
    ) -> authoring_models.Unit:
        """ Helper method to quickly create a unit with some components """
        unit, _unit_v1 = authoring_api.create_unit_and_version(
            learning_package_id=self.learning_package.id,
            key=key,
            title=title,
            created=self.now,
            created_by=None,
        )
        _unit_v2 = authoring_api.create_next_unit_version(
            unit=unit,
            title=title,
            components=components,
            created=self.now,
            created_by=None,
        )
        unit.refresh_from_db()
        return unit

    def modify_component(
        self,
        component: authoring_models.Component,
        *,
        title="Modified Component",
        timestamp=None,
    ) -> authoring_models.ComponentVersion:
        """
        Helper method to modify a component for the purposes of testing units/drafts/pinning/publishing/etc.
        """
        return authoring_api.create_next_component_version(
            component.pk,
            content_to_replace={},
            title=title,
            created=timestamp or self.now,
            created_by=None,
        )

    def test_create_unit_with_invalid_children(self):
        """
        Verify that only components can be added to units, and a specific
        exception is raised.
        """
        # Create two units:
        unit, unit_version = authoring_api.create_unit_and_version(
            learning_package_id=self.learning_package.id,
            key="unit:key",
            title="Unit",
            created=self.now,
            created_by=None,
        )
        unit2, _u2v1 = authoring_api.create_unit_and_version(
            learning_package_id=self.learning_package.id,
            key="unit:key2",
            title="Unit 2",
            created=self.now,
            created_by=None,
        )
        # Try adding a Unit to a Unit
        with pytest.raises(TypeError, match="Unit components must be either Component or ComponentVersion."):
            authoring_api.create_next_unit_version(
                unit=unit,
                title="Unit Containing a Unit",
                components=[unit2],
                created=self.now,
                created_by=None,
            )
        # Check that a new version was not created:
        assert unit.versioning.draft == unit_version

    def test_adding_external_components(self):
        """
        Test that components from another learning package cannot be added to a
        unit.
        """
        learning_package2 = authoring_api.create_learning_package(key="other-package", title="Other Package")
        unit, _unit_version = authoring_api.create_unit_and_version(
            learning_package_id=learning_package2.pk,
            key="unit:key",
            title="Unit",
            created=self.now,
            created_by=None,
        )
        assert self.component_1.learning_package != learning_package2
        # Try adding a a component from LP 1 (self.learning_package) to a unit from LP 2
        with pytest.raises(ValidationError, match="Container entities must be from the same learning package."):
            authoring_api.create_next_unit_version(
                unit=unit,
                title="Unit Containing an External Component",
                components=[self.component_1],
                created=self.now,
                created_by=None,
            )

    def test_create_empty_unit_and_version(self):
        """Test creating a unit with no components.

        Expected results:
        1. A unit and unit version are created.
        2. The unit version number is 1.
        3. The unit is a draft with unpublished changes.
        4. There is no published version of the unit.
        """
        unit, unit_version = authoring_api.create_unit_and_version(
            learning_package_id=self.learning_package.id,
            key="unit:key",
            title="Unit",
            created=self.now,
            created_by=None,
        )
        assert unit, unit_version
        assert unit_version.version_num == 1
        assert unit_version in unit.versioning.versions.all()
        assert unit.versioning.has_unpublished_changes
        assert unit.versioning.draft == unit_version
        assert unit.versioning.published is None

    def test_create_next_unit_version_with_two_unpinned_components(self):
        """Test creating a unit version with two unpinned components.

        Expected results:
        1. A new unit version is created.
        2. The unit version number is 2.
        3. The unit version is in the unit's versions.
        4. The components are in the draft unit version's component list and are unpinned.
        """
        unit, _unit_version = authoring_api.create_unit_and_version(
            learning_package_id=self.learning_package.id,
            key="unit:key",
            title="Unit",
            created=self.now,
            created_by=None,
        )
        unit_version_v2 = authoring_api.create_next_unit_version(
            unit=unit,
            title="Unit",
            components=[self.component_1, self.component_2],
            created=self.now,
            created_by=None,
        )
        assert unit_version_v2.version_num == 2
        assert unit_version_v2 in unit.versioning.versions.all()
        assert authoring_api.get_components_in_draft_unit(unit) == [
            Entry(self.component_1.versioning.draft),
            Entry(self.component_2.versioning.draft),
        ]
        assert authoring_api.get_components_in_published_unit(unit) is None

    def test_create_next_unit_version_with_unpinned_and_pinned_components(self):
        """
        Test creating a unit version with one unpinned and one pinned 📌 component.
        """
        unit, _unit_version = authoring_api.create_unit_and_version(
            learning_package_id=self.learning_package.id,
            key="unit:key",
            title="Unit",
            created=self.now,
            created_by=None,
        )
        unit_version_v2 = authoring_api.create_next_unit_version(
            unit=unit,
            title="Unit",
            components=[self.component_1, self.component_2_v1],  # Note the "v1" pinning 📌 the second one to version 1
            created=self.now,
            created_by=None,
        )
        assert unit_version_v2.version_num == 2
        assert unit_version_v2 in unit.versioning.versions.all()
        assert authoring_api.get_components_in_draft_unit(unit) == [
            Entry(self.component_1_v1),
            Entry(self.component_2_v1, pinned=True),  # Pinned 📌 to v1
        ]
        assert authoring_api.get_components_in_published_unit(unit) is None

    def test_add_component_after_publish(self):
        """
        Adding a component to a published unit will create a new version and
        show that the unit has unpublished changes.
        """
        unit, unit_version = authoring_api.create_unit_and_version(
            learning_package_id=self.learning_package.id,
            key="unit:key",
            title="Unit",
            created=self.now,
            created_by=None,
        )
        assert unit.versioning.draft == unit_version
        assert unit.versioning.published is None
        assert unit.versioning.has_unpublished_changes
        # Publish the empty unit:
        authoring_api.publish_all_drafts(self.learning_package.id)
        unit.refresh_from_db()  # Reloading the unit is necessary
        assert unit.versioning.has_unpublished_changes is False  # Shallow check for just the unit itself, not children
        assert authoring_api.contains_unpublished_changes(unit) is False  # Deeper check

        # Add a published component (unpinned):
        assert self.component_1.versioning.has_unpublished_changes is False
        unit_version_v2 = authoring_api.create_next_unit_version(
            unit=unit,
            title=unit_version.title,
            components=[self.component_1],
            created=self.now,
            created_by=None,
        )
        # Now the unit should have unpublished changes:
        unit.refresh_from_db()  # Reloading the unit is necessary
        assert unit.versioning.has_unpublished_changes  # Shallow check - adding a child is a change to the unit
        assert authoring_api.contains_unpublished_changes(unit)  # Deeper check
        assert unit.versioning.draft == unit_version_v2
        assert unit.versioning.published == unit_version

    def test_modify_unpinned_component_after_publish(self):
        """
        Modifying an unpinned component in a published unit will NOT create a
        new version nor show that the unit has unpublished changes (but it will
        "contain" unpublished changes). The modifications will appear in the
        published version of the unit only after the component is published.
        """
        # Create a unit with one unpinned draft component:
        assert self.component_1.versioning.has_unpublished_changes
        unit = self.create_unit_with_components([self.component_1])
        assert unit.versioning.has_unpublished_changes

        # Publish the unit and the component:
        authoring_api.publish_all_drafts(self.learning_package.id)
        unit.refresh_from_db()  # Reloading the unit is necessary if we accessed 'versioning' before publish
        self.component_1.refresh_from_db()
        assert unit.versioning.has_unpublished_changes is False  # Shallow check
        assert authoring_api.contains_unpublished_changes(unit) is False  # Deeper check
        assert self.component_1.versioning.has_unpublished_changes is False

        # Now modify the component by changing its title (it remains a draft):
        component_1_v2 = self.modify_component(self.component_1, title="Modified Counting Problem with new title")

        # The component now has unpublished changes; the unit doesn't directly but does contain
        unit.refresh_from_db()  # Reloading the unit is necessary, or 'unit.versioning' will be outdated
        self.component_1.refresh_from_db()
        assert unit.versioning.has_unpublished_changes is False  # Shallow check should be false - unit is unchanged
        assert authoring_api.contains_unpublished_changes(unit)  # But unit DOES contain changes
        assert self.component_1.versioning.has_unpublished_changes

        # Since the component changes haven't been published, they should only appear in the draft unit
        assert authoring_api.get_components_in_draft_unit(unit) == [
            Entry(component_1_v2),  # new version
        ]
        assert authoring_api.get_components_in_published_unit(unit) == [
            Entry(self.component_1_v1),  # old version
        ]

        # But if we publish the component, the changes will appear in the published version of the unit.
        self.publish_component(self.component_1)
        assert authoring_api.get_components_in_draft_unit(unit) == [
            Entry(component_1_v2),  # new version
        ]
        assert authoring_api.get_components_in_published_unit(unit) == [
            Entry(component_1_v2),  # new version
        ]
        assert authoring_api.contains_unpublished_changes(unit) is False  # No longer contains unpublished changes

    def test_modify_pinned_component(self):
        """
        When a pinned 📌 component in unit is modified and/or published, it will
        have no effect on either the draft nor published version of the unit,
        which will continue to use the pinned version.
        """
        # Create a unit with one component (pinned 📌 to v1):
        unit = self.create_unit_with_components([self.component_1_v1])

        # Publish the unit and the component:
        authoring_api.publish_all_drafts(self.learning_package.id)
        expected_unit_contents = [
            Entry(self.component_1_v1, pinned=True),  # pinned 📌 to v1
        ]
        assert authoring_api.get_components_in_published_unit(unit) == expected_unit_contents

        # Now modify the component by changing its title (it remains a draft):
        self.modify_component(self.component_1, title="Modified Counting Problem with new title")

        # The component now has unpublished changes; the unit is entirely unaffected
        unit.refresh_from_db()  # Reloading the unit is necessary, or 'unit.versioning' will be outdated
        self.component_1.refresh_from_db()
        assert unit.versioning.has_unpublished_changes is False  # Shallow check
        assert authoring_api.contains_unpublished_changes(unit) is False  # Deep check
        assert self.component_1.versioning.has_unpublished_changes is True

        # Neither the draft nor the published version of the unit is affected
        assert authoring_api.get_components_in_draft_unit(unit) == expected_unit_contents
        assert authoring_api.get_components_in_published_unit(unit) == expected_unit_contents
        # Even if we publish the component, the unit stays pinned to the specified version:
        self.publish_component(self.component_1)
        assert authoring_api.get_components_in_draft_unit(unit) == expected_unit_contents
        assert authoring_api.get_components_in_published_unit(unit) == expected_unit_contents

    def test_create_two_units_with_same_components(self):
        """Test creating two units with the same components.

        Expected results:
        1. Two different units are created.
        2. The units have the same components.
        """
        # Create a unit with component 2 unpinned, component 2 pinned 📌, and component 1:
        unit1 = self.create_unit_with_components([self.component_2, self.component_2_v1, self.component_1], key="u1")
        # Create a second unit with component 1 pinned 📌, component 2, and component 1 unpinned:
        unit2 = self.create_unit_with_components([self.component_1_v1, self.component_2, self.component_1], key="u2")

        # Check that the contents are as expected:
        assert [row.component_version for row in authoring_api.get_components_in_draft_unit(unit1)] == [
            self.component_2_v1, self.component_2_v1, self.component_1_v1,
        ]
        assert [row.component_version for row in authoring_api.get_components_in_draft_unit(unit2)] == [
            self.component_1_v1, self.component_2_v1, self.component_1_v1,
        ]

        # Modify component 1
        component_1_v2 = self.modify_component(self.component_1, title="component 1 v2")
        # Publish changes
        authoring_api.publish_all_drafts(self.learning_package.id)
        # Modify component 2 - only in the draft
        component_2_v2 = self.modify_component(self.component_2, title="component 2 DRAFT")

        # Check that the draft contents are as expected:
        assert authoring_api.get_components_in_draft_unit(unit1) == [
            Entry(component_2_v2),  # v2 in the draft version
            Entry(self.component_2_v1, pinned=True),  # pinned 📌 to v1
            Entry(component_1_v2),  # v2
        ]
        assert authoring_api.get_components_in_draft_unit(unit2) == [
            Entry(self.component_1_v1, pinned=True),  # pinned 📌 to v1
            Entry(component_2_v2),  # v2 in the draft version
            Entry(component_1_v2),  # v2
        ]

        # Check that the published contents are as expected:
        assert authoring_api.get_components_in_published_unit(unit1) == [
            Entry(self.component_2_v1),  # v1 in the published version
            Entry(self.component_2_v1, pinned=True),  # pinned 📌 to v1
            Entry(component_1_v2),  # v2
        ]
        assert authoring_api.get_components_in_published_unit(unit2) == [
            Entry(self.component_1_v1, pinned=True),  # pinned 📌 to v1
            Entry(self.component_2_v1),  # v1 in the published version
            Entry(component_1_v2),  # v2
        ]

    def test_publishing_shared_component(self):
        """
        A complex test case involving two units with a shared component and
        other non-shared components.

        Unit 1: components C1, C2, C3
        Unit 2: components C2, C4, C5
        Everything is "unpinned".
        """
        # 1️⃣ Create the units and publish them:
        (c1, c1_v1), (c2, _c2_v1), (c3, c3_v1), (c4, c4_v1), (c5, c5_v1) = [
            self.create_component(key=f"C{i}", title=f"Component {i}") for i in range(1, 6)
        ]
        unit1 = self.create_unit_with_components([c1, c2, c3], title="Unit 1", key="unit:1")
        unit2 = self.create_unit_with_components([c2, c4, c5], title="Unit 2", key="unit:2")
        authoring_api.publish_all_drafts(self.learning_package.id)
        assert authoring_api.contains_unpublished_changes(unit1) is False
        assert authoring_api.contains_unpublished_changes(unit2) is False

        # 2️⃣ Then the author edits C2 inside of Unit 1 making C2v2.
        c2_v2 = self.modify_component(c2, title="C2 version 2")
        # This makes U1 and U2 both show up as Units that CONTAIN unpublished changes, because they share the component.
        assert authoring_api.contains_unpublished_changes(unit1)
        assert authoring_api.contains_unpublished_changes(unit2)
        # (But the units themselves are unchanged:)
        unit1.refresh_from_db()
        unit2.refresh_from_db()
        assert unit1.versioning.has_unpublished_changes is False
        assert unit2.versioning.has_unpublished_changes is False

        # 3️⃣ In addition to this, the author also modifies another component in Unit 2 (C5)
        c5_v2 = self.modify_component(c5, title="C5 version 2")

        # 4️⃣ The author then publishes Unit 1, and therefore everything in it.
        # FIXME: this should only require publishing the unit itself, but we don't yet do auto-publishing children
        authoring_api.publish_from_drafts(
            self.learning_package.pk,
            draft_qset=authoring_api.get_all_drafts(self.learning_package.pk).filter(
                entity_id__in=[
                    unit1.publishable_entity.id,
                    c1.publishable_entity.id,
                    c2.publishable_entity.id,
                    c3.publishable_entity.id,
                ],
            ),
        )

        # Result: Unit 1 will show the newly published version of C2:
        assert authoring_api.get_components_in_published_unit(unit1) == [
            Entry(c1_v1),
            Entry(c2_v2),  # new published version of C2
            Entry(c3_v1),
        ]

        # Result: someone looking at Unit 2 should see the newly published component 2, because publishing it anywhere
        # publishes it everywhere. But publishing C2 and Unit 1 does not affect the other components in Unit 2.
        # (Publish propagates downward, not upward)
        assert authoring_api.get_components_in_published_unit(unit2) == [
            Entry(c2_v2),  # new published version of C2
            Entry(c4_v1),  # still original version of C4 (it was never modified)
            Entry(c5_v1),  # still original version of C5 (it hasn't been published)
        ]

        # Result: Unit 2 CONTAINS unpublished changes because of the modified C5. Unit 1 doesn't contain unpub changes.
        assert authoring_api.contains_unpublished_changes(unit1) is False
        assert authoring_api.contains_unpublished_changes(unit2)

        # 5️⃣ Publish component C5, which should be the only thing unpublished in the learning package
        self.publish_component(c5)
        # Result: Unit 2 shows the new version of C5 and no longer contains unpublished changes:
        assert authoring_api.get_components_in_published_unit(unit2) == [
            Entry(c2_v2),  # new published version of C2
            Entry(c4_v1),  # still original version of C4 (it was never modified)
            Entry(c5_v2),  # new published version of C5
        ]
        assert authoring_api.contains_unpublished_changes(unit2) is False

    def test_query_count_of_contains_unpublished_changes(self):
        """
        Checking for unpublished changes in a unit should require a fixed number
        of queries, not get more expensive as the unit gets larger.
        """
        # Add 100 components (unpinned)
        component_count = 100
        components = []
        for i in range(component_count):
            component, _version = self.create_component(
                key=f"Query Counting {i}",
                title=f"Querying Counting Problem {i}",
            )
            components.append(component)
        unit = self.create_unit_with_components(components)
        authoring_api.publish_all_drafts(self.learning_package.id)
        unit.refresh_from_db()
        with self.assertNumQueries(2):
            assert authoring_api.contains_unpublished_changes(unit) is False

        # Modify the most recently created component:
        self.modify_component(component, title="Modified Component")
        with self.assertNumQueries(2):
            assert authoring_api.contains_unpublished_changes(unit) is True

    @ddt.data(True, False)
    @pytest.mark.skip(reason="FIXME: we don't yet prevent adding soft-deleted components to units")
    def test_cannot_add_soft_deleted_component(self, publish_first):
        """
        Test that a soft-deleted component cannot be added to a unit.

        Although it's valid for units to contain soft-deleted components (by
        deleting the component after adding it), it is likely a mistake if
        you're trying to add one to the unit.
        """
        component, _cv = self.create_component(title="Deleted component")
        if publish_first:
            # Publish the component:
            authoring_api.publish_all_drafts(self.learning_package.id)
        # Now delete it. The draft version is now deleted:
        authoring_api.soft_delete_draft(component.pk)
        # Now try adding that component to a unit:
        with pytest.raises(ValidationError, match="component is deleted"):
            self.create_unit_with_components([component])

    def test_removing_component(self):
        """ Test removing a component from a unit (but not deleting it) """
        unit = self.create_unit_with_components([self.component_1, self.component_2])
        authoring_api.publish_all_drafts(self.learning_package.id)

        # Now remove component 2
        authoring_api.create_next_unit_version(
            unit=unit,
            title="Revised with component 2 deleted",
            components=[self.component_1],  # component 2 is gone
            created=self.now,
        )

        # Now it should not be listed in the unit:
        assert authoring_api.get_components_in_draft_unit(unit) == [
            Entry(self.component_1_v1),
        ]
        unit.refresh_from_db()
        assert unit.versioning.has_unpublished_changes  # The unit itself and its component list have change
        assert authoring_api.contains_unpublished_changes(unit)
        # The published version of the unit is not yet affected:
        assert authoring_api.get_components_in_published_unit(unit) == [
            Entry(self.component_1_v1),
            Entry(self.component_2_v1),
        ]

        # But when we publish the new unit version with the removal, the published version is affected:
        authoring_api.publish_all_drafts(self.learning_package.id)
        # FIXME: Refreshing the unit is necessary here because get_entities_in_published_container() accesses
        # container_entity.versioning.published, and .versioning is cached with the old version. But this seems like
        # a footgun?
        unit.refresh_from_db()
        assert authoring_api.contains_unpublished_changes(unit) is False
        assert authoring_api.get_components_in_published_unit(unit) == [
            Entry(self.component_1_v1),
        ]

    def test_soft_deleting_component(self):
        """ Test soft deleting a component that's in a unit (but not removing it) """
        unit = self.create_unit_with_components([self.component_1, self.component_2])
        authoring_api.publish_all_drafts(self.learning_package.id)

        # Now soft delete component 2
        authoring_api.soft_delete_draft(self.component_2.pk)

        # Now it should not be listed in the unit:
        assert authoring_api.get_components_in_draft_unit(unit) == [
            Entry(self.component_1_v1),
            # component 2 is soft deleted from the draft.
            # TODO: should we return some kind of placeholder here, to indicate that a component is still listed in the
            # unit's component list but has been soft deleted, and will be fully deleted when published, or restored if
            # reverted?
        ]
        assert unit.versioning.has_unpublished_changes is False  # The unit itself and its component list is not changed
        assert authoring_api.contains_unpublished_changes(unit)  # But it CONTAINS an unpublished change (a deletion)
        # The published version of the unit is not yet affected:
        assert authoring_api.get_components_in_published_unit(unit) == [
            Entry(self.component_1_v1),
            Entry(self.component_2_v1),
        ]

        # But when we publish the deletion, the published version is affected:
        authoring_api.publish_all_drafts(self.learning_package.id)
        assert authoring_api.contains_unpublished_changes(unit) is False
        assert authoring_api.get_components_in_published_unit(unit) == [
            Entry(self.component_1_v1),
        ]

    def test_soft_deleting_and_removing_component(self):
        """ Test soft deleting a component that's in a unit AND removing it """
        unit = self.create_unit_with_components([self.component_1, self.component_2])
        authoring_api.publish_all_drafts(self.learning_package.id)

        # Now soft delete component 2
        authoring_api.soft_delete_draft(self.component_2.pk)
        # And remove it from the unit:
        authoring_api.create_next_unit_version(
            unit=unit,
            title="Revised with component 2 deleted",
            components=[self.component_1],
            created=self.now,
        )

        # Now it should not be listed in the unit:
        assert authoring_api.get_components_in_draft_unit(unit) == [
            Entry(self.component_1_v1),
        ]
        assert unit.versioning.has_unpublished_changes is True
        assert authoring_api.contains_unpublished_changes(unit)
        # The published version of the unit is not yet affected:
        assert authoring_api.get_components_in_published_unit(unit) == [
            Entry(self.component_1_v1),
            Entry(self.component_2_v1),
        ]

        # But when we publish the deletion, the published version is affected:
        authoring_api.publish_all_drafts(self.learning_package.id)
        assert authoring_api.contains_unpublished_changes(unit) is False
        assert authoring_api.get_components_in_published_unit(unit) == [
            Entry(self.component_1_v1),
        ]

    # Test the query counts of various operations
    # Test that only components can be added to units
    # Test that components must be in the same learning package
    # Test that invalid component PKs cannot be added to a unit
    # Test that _version_pks=[] arguments must be related to publishable_entities_pks
    # Test that publishing a unit publishes its child components automatically
    # Test that publishing a component does NOT publish changes to its parent unit
    # Test that I can get a history of a given unit and all its children, including children that aren't currently in
    #     the unit and excluding children that are only in other units.
    # Test that I can get a history of a given unit and its children, that includes changes made to the child components
    #     while they were part of the unit but excludes changes made to those children while they were not part of
    #     the unit. 🫣

    def test_snapshots_of_published_unit(self):
        """
        Test that we can access snapshots of the historic published version of
        units and their contents.
        """
        # At first the unit has one component (unpinned):
        unit = self.create_unit_with_components([self.component_1])
        self.modify_component(self.component_1, title="Component 1 as of checkpoint 1")

        # Publish everything, creating Checkpoint 1
        checkpoint_1 = authoring_api.publish_all_drafts(self.learning_package.id, message="checkpoint 1")

        ########################################################################

        # Now we update the title of the component.
        self.modify_component(self.component_1, title="Component 1 as of checkpoint 2")
        # Publish everything, creating Checkpoint 2
        checkpoint_2 = authoring_api.publish_all_drafts(self.learning_package.id, message="checkpoint 2")
        ########################################################################

        # Now add a second component to the unit:
        self.modify_component(self.component_1, title="Component 1 as of checkpoint 3")
        self.modify_component(self.component_2, title="Component 2 as of checkpoint 3")
        authoring_api.create_next_unit_version(
            unit=unit,
            title="Unit title in checkpoint 3",
            components=[self.component_1, self.component_2],
            created=self.now,
        )
        # Publish everything, creating Checkpoint 3
        checkpoint_3 = authoring_api.publish_all_drafts(self.learning_package.id, message="checkpoint 3")
        ########################################################################

        # Now add a third component to the unit, a pinned 📌 version of component 1.
        # This will test pinned versions and also test adding at the beginning rather than the end of the unit.
        authoring_api.create_next_unit_version(
            unit=unit,
            title="Unit title in checkpoint 4",
            components=[self.component_1_v1, self.component_1, self.component_2],
            created=self.now,
        )
        # Publish everything, creating Checkpoint 4
        checkpoint_4 = authoring_api.publish_all_drafts(self.learning_package.id, message="checkpoint 4")
        ########################################################################

        # Modify the drafts, but don't publish:
        self.modify_component(self.component_1, title="Component 1 draft")
        self.modify_component(self.component_2, title="Component 2 draft")

        # Now fetch the snapshots:
        as_of_checkpoint_1 = authoring_api.get_components_in_published_unit_as_of(unit, checkpoint_1.pk)
        assert [cv.component_version.title for cv in as_of_checkpoint_1] == [
            "Component 1 as of checkpoint 1",
        ]
        as_of_checkpoint_2 = authoring_api.get_components_in_published_unit_as_of(unit, checkpoint_2.pk)
        assert [cv.component_version.title for cv in as_of_checkpoint_2] == [
            "Component 1 as of checkpoint 2",
        ]
        as_of_checkpoint_3 = authoring_api.get_components_in_published_unit_as_of(unit, checkpoint_3.pk)
        assert [cv.component_version.title for cv in as_of_checkpoint_3] == [
            "Component 1 as of checkpoint 3",
            "Component 2 as of checkpoint 3",
        ]
        as_of_checkpoint_4 = authoring_api.get_components_in_published_unit_as_of(unit, checkpoint_4.pk)
        assert [cv.component_version.title for cv in as_of_checkpoint_4] == [
            "Querying Counting Problem",  # Pinned. This title is self.component_1_v1.title (original v1 title)
            "Component 1 as of checkpoint 3",  # we didn't modify these components so they're same as in snapshot 3
            "Component 2 as of checkpoint 3",  # we didn't modify these components so they're same as in snapshot 3
        ]

    def test_next_version_with_different_different_title(self):
        """Test creating a unit version with a different title.

        Expected results:
        1. A new unit version is created.
        2. The unit version number is 2.
        3. The unit version is in the unit's versions.
        4. The unit version's title is different from the previous version.
        5. The user defined is the same as the previous version.
        6. The frozen list is empty.
        """

    def test_check_author_defined_list_matches_components(self):
        """Test checking the author defined list matches the components.

        Expected results:
        1. The author defined list matches the components used to create the unit version.
        """

    def test_check_initial_list_matches_components(self):
        """Test checking the initial list matches the components.

        Expected results:
        1. The initial list matches the components (pinned) used to create the unit version.
        """

    def test_check_frozen_list_is_none_floating_versions(self):
        """Test checking the frozen list is None when floating versions are used in the author defined list.

        Expected results:
        1. The frozen list is None.
        """

    def test_check_frozen_list_when_next_version_is_created(self):
        """Test checking the frozen list when a new version is created.

        Expected results:
        1. The frozen list has pinned versions of the user defined list from the previous version.
        """

    def test_check_lists_equal_when_pinned_versions(self):
        """Test checking the lists are equal when pinned versions are used.

        Expected results:
        1. The author defined list == initial list == frozen list.
        """

    def test_publish_unit_version(self):
        """Test publish unpublished unit version.

        Expected results:
        1. The newly created unit version has unpublished changes.
        2. The published version matches the unit version.
        3. The draft version matches the unit version.
        """

    def test_publish_unit_with_unpublished_component(self):
        """Test publishing a unit with an unpublished component.

        Expected results:
        1. The unit version is published.
        2. The component is published.
        """

    def test_next_version_with_different_order(self):
        """Test creating a unit version with different order of components.

        Expected results:
        1. A new unit version is created.
        2. The unit version number is 2.
        3. The unit version is in the unit's versions.
        4. The user defined list is different from the previous version.
        5. The initial list contains the pinned versions of the defined list.
        6. The frozen list is empty.
        """

    def test_soft_delete_component_from_units(self):
        """Soft-delete a component from a unit.

        Expected result:
        After soft-deleting the component (draft), a new unit version (draft) is created for the unit.
        """

    def test_soft_delete_component_from_units_and_publish(self):
        """Soft-delete a component from a unit and publish the unit.

        Expected result:
        After soft-deleting the component (draft), a new unit version (draft) is created for the unit.
        Then, if the unit is published all units referencing the component are published as well.
        """

    def test_unit_version_becomes_draft_again(self):
        """Test a unit version becomes a draft again.

        Expected results:
        1. The frozen list is None after the unit version becomes a draft again.
        """
