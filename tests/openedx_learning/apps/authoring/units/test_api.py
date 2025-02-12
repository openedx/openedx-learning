"""
Basic tests for the units API.
"""
from ..components.test_api import ComponentTestCase
from openedx_learning.api import authoring as authoring_api


class UnitTestCase(ComponentTestCase):

    def setUp(self) -> None:
        self.component_1, self.component_version_1 = authoring_api.create_component_and_version(
            self.learning_package.id,
            component_type=self.problem_type,
            local_key="Query Counting",
            title="Querying Counting Problem",
            created=self.now,
            created_by=None,
        )
        self.component_2, self.component_version_2 = authoring_api.create_component_and_version(
            self.learning_package.id,
            component_type=self.problem_type,
            local_key="Query Counting (2)",
            title="Querying Counting Problem (2)",
            created=self.now,
            created_by=None,
        )

    def test_create_unit_with_content_instead_of_components(self):
        """Test creating a unit with content instead of components.

        Expected results:
        1. An error is raised indicating the content restriction for units.
        2. The unit is not created.
        """

    def test_create_empty_first_unit_and_version(self):
        """Test creating a unit with no components.

        Expected results:
        1. A unit and unit version are created.
        2. The unit version number is 1.
        3. The unit version is in the unit's versions.
        """
        unit, unit_version = authoring_api.create_unit_and_version(
            learning_package_id=self.learning_package.id,
            key=f"unit:key",
            title="Unit",
            created=self.now,
            created_by=None,
        )
        assert unit, unit_version
        assert unit_version.version_num == 1
        assert unit_version in unit.versioning.versions.all()

    def test_create_next_unit_version_with_two_components(self):
        """Test creating a unit version with two components.

        Expected results:
        1. A new unit version is created.
        2. The unit version number is 2.
        3. The unit version is in the unit's versions.
        4. The components are in the unit version's user defined list.
        5. Initial list contains the pinned versions of the defined list.
        6. Frozen list is empty.
        """
        unit, unit_version = authoring_api.create_unit_and_version(
            learning_package_id=self.learning_package.id,
            key=f"unit:key",
            title="Unit",
            created=self.now,
            created_by=None,
        )
        unit_version_v2 = authoring_api.create_next_unit_version(
            unit=unit,
            title="Unit",
            publishable_entities_pks=[
                self.component_1.publishable_entity.id,
                self.component_2.publishable_entity.id,
            ],
            draft_version_pks=[None, None],
            published_version_pks=[None, None],
            created=self.now,
            created_by=None,
        )
        assert unit_version_v2.version_num == 2
        assert unit_version_v2 in unit.versioning.versions.all()
        publishable_entities_in_list = [
            row.entity for row in authoring_api.get_user_defined_list_in_unit_version(unit_version_v2.pk)
        ]
        assert self.component_1.publishable_entity in publishable_entities_in_list
        assert self.component_2.publishable_entity in publishable_entities_in_list


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

    def test_create_two_units_with_same_components(self):
        """Test creating two units with the same components.

        Expected results:
        1. Two different units are created.
        2. The units have the same components.
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
