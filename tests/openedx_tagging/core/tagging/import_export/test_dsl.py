"""
Test for DSL functions
"""
import ddt

from django.test.testcases import TestCase

from openedx_tagging.core.tagging.import_export.import_plan import TagDSL, TagImportDSL
from openedx_tagging.core.tagging.import_export.actions import CreateTag
from openedx_tagging.core.tagging.import_export.exceptions import TagImportError
from .test_actions import TestImportActionMixin

@ddt.ddt
class TestTagImportDSL(TestImportActionMixin, TestCase):
    """
    Test for DSL functions
    """

    def setUp(self):
        super().setUp()
        self.dsl = TagImportDSL(self.taxonomy)

    def test_tag_import_error(self):
        message = "Error message"
        expected_repr = f"TagImportError({message})"
        error = TagImportError(message)
        assert str(error) == message
        assert repr(error) == expected_repr


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
        assert len(self.dsl.errors) == errors_expected
        assert len(self.dsl.actions) == 1
        assert self.dsl.actions[0].name == 'create'
        assert self.dsl.indexed_actions['create'][1].tag.id == tag_id

    def test_build_delete_actions(self):
        tags = {
            tag.external_id: tag
            for tag in self.taxonomy.tag_set.exclude(pk=25)
        }
        # Clear other actions to only have the delete ones
        self.dsl.actions.clear()

        self.dsl._build_delete_actions(tags)  # pylint: disable=protected-access
        assert len(self.dsl.errors) == 0

        # Check actions in order
        # #1 Update parent of 'tag_2'
        assert self.dsl.actions[0].name == 'update_parent'
        assert self.dsl.actions[0].tag.id == 'tag_2'
        assert self.dsl.actions[0].tag.parent_id is None
        # #2 Delete 'tag_1'
        assert self.dsl.actions[1].name == 'delete'
        assert self.dsl.actions[1].tag.id == 'tag_1'
        # #3 Delete 'tag_2'
        assert self.dsl.actions[2].name == 'delete'
        assert self.dsl.actions[2].tag.id == 'tag_2'
        # #4 Update parent of 'tag_4'
        assert self.dsl.actions[3].name == 'update_parent'
        assert self.dsl.actions[3].tag.id == 'tag_4'
        assert self.dsl.actions[3].tag.parent_id is None
        # #5 Delete 'tag_3'
        assert self.dsl.actions[4].name == 'delete'
        assert self.dsl.actions[4].tag.id == 'tag_3'

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
                'name': 'update_parent',
                'id': 'tag_2',
            },
            {
                'name': 'delete',
                'id': 'tag_1',
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
        assert len(self.dsl.errors) == expected_errors
        assert len(self.dsl.actions) == len(expected_actions)

        for index, action in enumerate(expected_actions):
            assert self.dsl.actions[index].name == action['name']
            assert self.dsl.actions[index].tag.id == action['id']
            assert self.dsl.actions[index].index == index + 1

    @ddt.data(
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
            {
                'id': 'tag_33',
                'value': 'Tag 32',
            },
            {
                'id': 'tag_2',
                'value': 'Tag 31',
            },
        ],
        False,
        "Plan\n"
        "--------------------------------\n"
        "#1: Create a new tag with values (external_id=tag_31, value=Tag 31, parent_id=None).\n"
        "#2: Create a new tag with values (external_id=tag_31, value=Tag 32, parent_id=None).\n"
        "#3: Rename tag value of tag (id=26) from 'Tag 1' to 'Tag 2'\n"
        "#4: Update the parent of tag (id=29) from parent (external_id=tag_3) to parent (external_id=tag_100).\n"
        "#5: Create a new tag with values (external_id=tag_33, value=Tag 32, parent_id=None).\n"
        "#6: Update the parent of tag (id=27) from parent (external_id=tag_1) to parent (external_id=None).\n"
        "#7: Rename tag value of tag (id=27) from 'Tag 2' to 'Tag 31'\n"
        "Output errors\n"
        "--------------------------------\n"
        "Conflict with 'create' (#2) and action #1: Duplicated external_id tag.\n"
        "Action error in 'rename' (#3): Duplicated tag value with tag (id=27).\n"
        "Action error in 'update_parent' (#4): Unknown parent tag (tag_100). "
        "You need to add parent before the child in your file.\n"
        "Conflict with 'create' (#5) and action #2: Duplicated tag value.\n"
        "Conflict with 'rename' (#7) and action #1: Duplicated tag value.\n"
        ),
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
        "Plan\n"
        "--------------------------------\n"
        "#1: Create a new tag with values (external_id=tag_31, value=Tag 31, parent_id=None).\n"
        "#2: Create a new tag with values (external_id=tag_32, value=Tag 32, parent_id=tag_1).\n"
        "#3: Rename tag value of tag (id=27) from 'Tag 2' to 'Tag 2 v2'\n"
        "#4: Update the parent of tag (id=29) from parent (external_id=tag_3) to parent (external_id=tag_1).\n"
        "#5: Rename tag value of tag (id=29) from 'Tag 4' to 'Tag 4 v2'\n"
        "#6: No changes needed for tag (external_id=tag_1)\n"
        ),
        ([
            {
                'id': 'tag_4',
                'value': 'Tag 4',
                'parent_id': 'tag_3',
            },
        ],
        True,
        "Plan\n"
        "--------------------------------\n"
        "#1: No changes needed for tag (external_id=tag_4)\n"
        "#2: Update the parent of tag (id=27) from parent (external_id=tag_1) to parent (external_id=None).\n"
        "#3: Delete tag (id=26)\n"
        "#4: Delete tag (id=27)\n"
        "#5: Update the parent of tag (id=29) from parent (external_id=tag_3) to parent (external_id=None).\n"
        "#6: Delete tag (id=28)\n"
        )
    )
    @ddt.unpack
    def test_plan(self, tags, replace, expected):
        tags = [TagDSL(**tag) for tag in tags]
        self.dsl.generate_actions(tags=tags, replace=replace)
        plan = self.dsl.plan()
        assert plan == expected

    @ddt.data(
        ([
            {
                'id': 'tag_31',
                'value': 'Tag 31',
            },
            {
                'id': 'tag_32',
                'value': 'Tag 32',
            },
            {
                'id': 'tag_1',
                'value': 'Tag 1 V2',
            },
            {
                'id': 'tag_4',
                'value': 'Tag 4',
                'parent_id': 'tag_32',
            },
            {
                'id': 'tag_33',
                'value': 'Tag 33',
            },
            {
                'id': 'tag_2',
                'value': 'Tag 2 V2',
            },
        ], False),
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
        ], False),
        ([
            {
                'id': 'tag_4',
                'value': 'Tag 4',
                'parent_id': 'tag_3',
            },
        ], True),
    )
    @ddt.unpack
    def test_execute(self, tags, replace):
        tags = [TagDSL(**tag) for tag in tags]
        self.dsl.generate_actions(tags=tags, replace=replace)
        assert self.dsl.execute()
        tag_external_ids = []
        for tag_dsl in tags:
            # This checks any creation
            tag = self.taxonomy.tag_set.get(external_id=tag_dsl.id)

            # Checks any rename
            assert tag.value == tag_dsl.value

            # Checks any parent update
            if not replace:
                if not tag_dsl.parent_id:
                    assert tag.parent is None
                else:
                    assert tag.parent.external_id == tag_dsl.parent_id

            tag_external_ids.append(tag_dsl.id)

        if replace:
            # Checks deletions checking that exists the updated tags
            external_ids = list(self.taxonomy.tag_set.values_list("external_id", flat=True))
            assert tag_external_ids == external_ids

    def test_error_in_execute(self):
        created_tag = 'tag_31'
        tags = [
            TagDSL(
                id=created_tag,
                value='Tag 31'
            ),  # Valid tag (creation)
            TagDSL(
                id='tag_32',
                value='Tag 31'
            ),  # Invalid
        ]
        self.dsl.generate_actions(tags=tags)
        assert not self.taxonomy.tag_set.filter(external_id=created_tag).exists()
        assert not self.dsl.execute()
        assert not self.taxonomy.tag_set.filter(external_id=created_tag).exists()
        