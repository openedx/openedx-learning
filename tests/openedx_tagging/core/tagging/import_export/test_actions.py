"""
Tests for actions
"""
import ddt

from django.test.testcases import TestCase

from openedx_tagging.core.tagging.models import Taxonomy
from openedx_tagging.core.tagging.import_export.dsl import TagDSL
from openedx_tagging.core.tagging.import_export.actions import (
    ImportAction,
    CreateTag,
    UpdateParentTag,
    RenameTag,
    DeleteTag,
    WithoutChanges,
)


class TestImportActionMixin:
    """
    Mixin for import action tests
    """

    fixtures = ["tests/openedx_tagging/core/fixtures/tagging.yaml"]

    def setUp(self):
        self.taxonomy = Taxonomy.objects.get(name="Import Taxonomy Test")
        self.indexed_actions = {
            'create': [
                CreateTag(
                    taxonomy=self.taxonomy,
                    tag=TagDSL(
                        id='tag_10',
                        value='Tag 10',
                        index=0
                    ),
                    index=0,
                )
            ],
            'rename': [
                RenameTag(
                    taxonomy=self.taxonomy,
                    tag=TagDSL(
                        id='tag_11',
                        value='Tag 11',
                        index=1
                    ),
                    index=1,
                )
            ]
        }


@ddt.ddt
class TestImportAction(TestImportActionMixin, TestCase):
    """
    Test for general function of the ImportAction class
    """

    def test_not_implemented_functions(self):
        with self.assertRaises(NotImplementedError):
            ImportAction.valid_for(None, None)
        action = ImportAction(None, None, None)
        with self.assertRaises(NotImplementedError):
            action.validate(None)
        with self.assertRaises(NotImplementedError):
            action.execute()

    @ddt.data(
        ('create', 'id', 'tag_10', True),
        ('rename', 'value', 'Tag 11', True),
        ('rename', 'id', 'tag_10', False),
        ('create', 'value', 'Tag 11', False),
    )
    @ddt.unpack
    def test_search_action(self, action_name, attr, search_value, expected):
        import_action = ImportAction(self.taxonomy, None, None)
        action = import_action._search_action(  # pylint: disable=protected-access
            self.indexed_actions,
            action_name,
            attr,
            search_value,
        )
        if expected:
            self.assertEqual(getattr(action.tag, attr), search_value)
        else:
            self.assertIsNone(action)

    @ddt.data(
        ('tag_1', True),
        ('tag_10', True),
        ('tag_100', False),
    )
    @ddt.unpack
    def test_validate_parent(self, parent_id, expected):
        action = ImportAction(
            self.taxonomy,
            TagDSL(
                id='tag_110',
                value='_',
                parent_id=parent_id,
                index=100
            ),
            index=100,
        )
        error = action._validate_parent(self.indexed_actions)  # pylint: disable=protected-access
        if expected:
            self.assertIsNone(error)
        else:
            self.assertEqual(
                str(error),
                (
                    "Action error in 'import_action' (#100) in tag (tag_110): "
                    "Unknown parent tag (tag_100). "
                    "You need to add parent before the child in your file."
                )
            )

    @ddt.data(
        (
            'Tag 1',
            (
                "Action error in 'import_action' (#100) in tag (tag_110): "
                "Duplicated tag value with tag (pk=22)."
            )
        ),
        (
            'Tag 10',
            (
                "Conflict with 'import_action' (#100) in tag (tag_110) "
                "and action #0: Duplicated tag value."
            )
        ),
        (
            'Tag 11',
            (
                "Conflict with 'import_action' (#100) in tag (tag_110) "
                "and action #1: Duplicated tag value."
            )
        ),
        ('Tag 20', None)
    )
    @ddt.unpack
    def test_validate_value(self, value, expected):
        action = ImportAction(
            self.taxonomy,
            TagDSL(
                id='tag_110',
                value=value,
                index=100
            ),
            index=100,
        )
        error = action._validate_value(self.indexed_actions)  # pylint: disable=protected-access
        if not expected:
            self.assertIsNone(error)
        else:
            self.assertEqual(str(error), expected)


@ddt.ddt
class TestCreateTag(TestImportActionMixin, TestCase):
    """
    Test for 'create' action
    """

    @ddt.data(
        ('tag_1', False),
        ('tag_100', True),
    )
    @ddt.unpack
    def test_valid_for(self, tag_id, expected):
        result = CreateTag.valid_for(
            self.taxonomy,
            TagDSL(
                id=tag_id,
                value='_',
                index=100,
            )
        )
        self.assertEqual(result, expected)

    @ddt.data(
        ('tag_10', False),
        ('tag_100', True),
    )
    @ddt.unpack
    def test_validate_id(self, tag_id, expected):
        action = CreateTag(
            taxonomy=self.taxonomy,
            tag=TagDSL(
                id=tag_id,
                value='_',
                index=100,
            ),
            index=100
        )
        error = action._validate_id(self.indexed_actions)  # pylint: disable=protected-access
        if expected:
            self.assertIsNone(error)
        else:
            self.assertEqual(
                str(error),
                (
                    f"Conflict with 'create' (#100) in tag ({tag_id}) "
                    "and action #0: Duplicated id tag."
                )
            )

    @ddt.data(
        ('tag_10', "Tag 20", None, 1),  # Invalid tag id
        ('tag_20', "Tag 10", None, 1),  # Invalid value,
        ('tag_20', "Tag 20", 'tag_100', 1),  # Invalid parent id,
        ('tag_10', "Tag 10", None, 2),  # Invalid tag id and value,
        ('tag_10', "Tag 10", 'tag_100', 3),  # Invalid tag id, value and parent,
        ('tag_20', "Tag 20", 'tag_1', 0),  # Valid
    )
    @ddt.unpack
    def test_validate(self, tag_id, tag_value, parent_id, expected):
        action = CreateTag(
            taxonomy=self.taxonomy,
            tag=TagDSL(
                id=tag_id,
                value=tag_value,
                index=100,
                parent_id=parent_id
            ),
            index=100
        )
        errors = action.validate(self.indexed_actions)
        self.assertEqual(len(errors), expected)


@ddt.ddt
class TestUpdateParentTag(TestImportActionMixin, TestCase):
    """
    Test for 'update_parent' action
    """

    @ddt.data(
        ('tag_100', None, False),  # Tag doesn't exist on database
        ('tag_2', 'tag_1', False),  # Parent don't change
        ('tag_2', 'tag_3', True),  # Valid
        ('tag_1', None, False),  # Both parent id are None
        ('tag_1', 'tag_3', True), # Valid
    )
    @ddt.unpack
    def test_valid_for(self, tag_id, parent_id, expected):
        result = UpdateParentTag.valid_for(
            taxonomy=self.taxonomy,
            tag=TagDSL(
                id=tag_id,
                value='_',
                parent_id=parent_id,
                index=100
            )
        )
        self.assertEqual(result, expected)

    @ddt.data(
        ('tag_2', 'tag_30', 1),  # Invalid parent
        ('tag_2', None, 0),  # Without parent
        ('tag_2', 'tag_10', 0),  # Valid
    )
    @ddt.unpack
    def test_validate(self, tag_id, parent_id, expected):
        action = UpdateParentTag(
            taxonomy=self.taxonomy,
            tag=TagDSL(
                id=tag_id,
                value='_',
                parent_id=parent_id,
                index=100,
            ),
            index=100
        )
        errors = action.validate(self.indexed_actions)
        self.assertEqual(len(errors), expected)

@ddt.ddt
class TestRenameTag(TestImportActionMixin, TestCase):
    """
    Test for 'rename' action
    """

    @ddt.data(
        ('tag_10', 'value', False),  # Tag doesn't exist on database
        ('tag_1', 'Tag 1', False),  # Same value
        ('tag_1', 'Tag 1 v2', True),  # Valid
    )
    @ddt.unpack
    def test_valid_for(self, tag_id, value, expected):
        result = RenameTag.valid_for(
            taxonomy=self.taxonomy,
            tag=TagDSL(
                id=tag_id,
                value=value,
                index=100,
            )
        )
        self.assertEqual(result, expected)

    @ddt.data(
        ('Tag 2', 1),  # There is a tag with the same value on database
        ('Tag 10', 1),  # There is a tag with the same value on create action
        ('Tag 11', 1),  # There is a tag with the same value on rename action
        ('Tag 12', 0),  # Valid
    )
    @ddt.unpack
    def test_validate(self, value, expected):
        action = RenameTag(
            taxonomy=self.taxonomy,
            tag=TagDSL(
                id='tag_1',
                value=value,
                index=100,
            ),
            index=100,
        )
        errors = action.validate(self.indexed_actions)
        self.assertEqual(len(errors), expected)


@ddt.ddt
class TestDeleteTag(TestImportActionMixin, TestCase):
    """
    Test for 'delete' action
    """

    @ddt.data(
        ('tag_10', None, False),  # Tag doesn't exist on database
        ('tag_1', 'rename', False),  # Invalid action
        ('tag_1', 'delete', True),  # Valid
    )
    @ddt.unpack
    def test_valid_for(self, tag_id, action, expected):
        result = DeleteTag.valid_for(
            taxonomy=self.taxonomy,
            tag=TagDSL(
                id=tag_id,
                value='_',
                action=action,
                index=100,
            ),
        )
        self.assertEqual(result, expected)

    def test_validate(self):
        action = DeleteTag(
            taxonomy=self.taxonomy,
            tag=TagDSL(
                id='_',
                value='_',
                index=100,
            ),
            index=100,
        )
        result = action.validate(self.indexed_actions)
        self.assertEqual(result, [])


class TestWithoutChanges(TestImportActionMixin, TestCase):
    """
    Test for 'without_changes' action
    """
    def test_valid_for(self):
        result = WithoutChanges.valid_for(
            self.taxonomy,
            tag=TagDSL(
                id='_',
                value='_',
                index=100,
            ),
        )
        self.assertFalse(result)

    def test_validate(self):
        action = WithoutChanges(
            taxonomy=self.taxonomy,
            tag=TagDSL(
                id='_',
                value='_',
                index=100,
            ),
            index=100,
        )
        result = action.validate(self.indexed_actions)
        self.assertEqual(result, [])
