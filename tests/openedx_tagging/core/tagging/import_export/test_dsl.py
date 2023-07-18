"""
Test for DSL functions
"""
import ddt

from django.test.testcases import TestCase

from openedx_tagging.core.tagging.import_export.dsl import TagDSL, TagImportDSL
from openedx_tagging.core.tagging.import_export.actions import CreateTag
from .test_actions import TestImportActionMixin

@ddt.ddt
class TestTagImportDSL(TestImportActionMixin, TestCase):
    """
    Test for DSL functions
    """

    def setUp(self):
        super().setUp()
        self.dsl = TagImportDSL(self.taxonomy)

    @ddt.data(
        ('tag_10', 1),
        ('tag_30', 0),
    )
    @ddt.unpack
    def test_build_action(self, tag_id, errors_expected):
        self.dsl.indexed_actions = self.indexed_actions
        self.dsl._build_action(  # pylint: disable=protected-access
            CreateTag,
            TagDSL(
                id=tag_id,
                value='_',
                index=100
            )
        )
        self.assertEqual(len(self.dsl.errors), errors_expected)
        self.assertEqual(len(self.dsl.actions), 1)
        self.assertEqual(self.dsl.actions[0].name, 'create')
        self.assertEqual(self.dsl.indexed_actions['create'][1].tag.id, tag_id)

    def test_build_delete_actions(self):
        tags = {
            tag.external_id: tag
            for tag in self.taxonomy.tag_set.exclude(pk=25)
        }
        # Clear other actions to only have the delete ones
        self.dsl.actions.clear()

        self.dsl._build_delete_actions(tags)  # pylint: disable=protected-access
        self.assertEqual(len(self.dsl.errors), 0)

        # Check actions in order
        # #1 Delete 'tag_1'
        self.assertEqual(self.dsl.actions[0].name, 'delete')
        self.assertEqual(self.dsl.actions[0].tag.id, 'tag_1')
        # #2 Delete 'tag_2'
        self.assertEqual(self.dsl.actions[1].name, 'delete')
        self.assertEqual(self.dsl.actions[1].tag.id, 'tag_2')
        # #3 Update parent of 'tag_4'
        self.assertEqual(self.dsl.actions[2].name, 'update_parent')
        self.assertEqual(self.dsl.actions[2].tag.id, 'tag_4')
        self.assertIsNone(self.dsl.actions[2].tag.parent_id)
        # #4 Delete 'tag_3'
        self.assertEqual(self.dsl.actions[3].name, 'delete')
        self.assertEqual(self.dsl.actions[3].tag.id, 'tag_3')

    @ddt.data(
        ([
          {
              'id': 'tag_31',
              'value': 'Tag 31',
          },
          {
              'id': 'tag_32',
              'value': 'Tag 32',
              'parent_id': 'tag_1',
          },
          {
              'id': 'tag_2',
              'value': 'Tag 2 v2',
              'parent_id': 'tag_1'
          },
          {
              'id': 'tag_4',
              'value': 'Tag 4 v2',
              'parent_id': 'tag_1',
          },
          {
              'id': 'tag_1',
              'value': 'Tag 1',
          },
        ],
        False,
        0,
        [
            {
                'name': 'create',
                'id': 'tag_31'
            },
            {
                'name': 'create',
                'id': 'tag_32'
            },
            {
                'name': 'rename',
                'id': 'tag_2'
            },
            {
                'name': 'update_parent',
                'id': 'tag_4'
            },
            {
                'name': 'rename',
                'id': 'tag_4'
            },
            {
                'name': 'without_changes',
                'id': 'tag_1'
            },
        ]),
        ([
            {
                'id': 'tag_31',
                'value': 'Tag 31',
            },
            {
                'id': 'tag_31',
                'value': 'Tag 32',
            },
            {
                'id': 'tag_1',
                'value': 'Tag 2',
            },
            {
                'id': 'tag_4',
                'value': 'Tag 4',
                'parent_id': 'tag_100',
            },
        ],
        False,
        3,
        [
            {
                'name': 'create',
                'id': 'tag_31',
            },
            {
                'name': 'create',
                'id': 'tag_31',
            },
            {
                'name': 'rename',
                'id': 'tag_1',
            },
            {
                'name': 'update_parent',
                'id': 'tag_4',
            }
        ]),
        ([
            {
                'id': 'tag_4',
                'value': 'Tag 4',
                'parent_id': 'tag_3',
            },
        ],
        True,
        0,
        [
            {
                'name': 'without_changes',
                'id': 'tag_4',
            },
            {
                'name': 'delete',
                'id': 'tag_1'
            },
            {
                'name': 'delete',
                'id': 'tag_2',
            },
            {
                'name': 'update_parent',
                'id': 'tag_4',
            },
            {
                'name': 'delete',
                'id': 'tag_3',
            },
        ])
    )
    @ddt.unpack
    def test_generate_actions(self, tags, replace, expected_errors, expected_actions):
        tags = [TagDSL(**tag) for tag in tags]
        self.dsl.generate_actions(tags=tags, replace=replace)
        self.assertEqual(len(self.dsl.errors), expected_errors)
        self.assertEqual(len(self.dsl.actions), len(expected_actions))

        for index, action in enumerate(expected_actions):
            self.assertEqual(self.dsl.actions[index].name, action['name'])
            self.assertEqual(self.dsl.actions[index].tag.id, action['id'])
            self.assertEqual(self.dsl.actions[index].index, index)
