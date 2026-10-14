"""
Test for import_plan functions
"""
import itertools
from unittest import mock

import ddt  # type: ignore[import]
from django.db import connection
from django.test.testcases import TestCase
from django.test.utils import CaptureQueriesContext

from openedx_tagging.import_export.actions import CreateTag, DeleteTag, UpdateParentTag
from openedx_tagging.import_export.exceptions import TagImportError
from openedx_tagging.import_export.import_plan import ExistingTag, TagImportPlan, TagItem, _ParentForest
from openedx_tagging.models import Tag, Taxonomy

from .test_actions import TestImportActionMixin


@ddt.ddt
class TestTagImportPlan(TestImportActionMixin, TestCase):
    """
    Test for import plan functions
    """

    structure_taxonomy: Taxonomy

    @classmethod
    def setUpTestData(cls) -> None:
        super().setUpTestData()
        cls.structure_taxonomy = Taxonomy.objects.create(name="Structure taxonomy")

    def setUp(self) -> None:
        super().setUp()
        self.import_plan = TagImportPlan(self.taxonomy)

    def test_tag_import_error(self) -> None:
        message = "Error message"
        expected_repr = f"TagImportError({message})"
        error = TagImportError(message)
        assert str(error) == message
        assert repr(error) == expected_repr

    @ddt.data(
        ('tag_10', 1),  # Test invalid
        ('tag_30', 0),  # Test valid
    )
    @ddt.unpack
    def test_build_action(self, tag_id: str, errors_expected: int):
        self.import_plan.indexed_actions = self.indexed_actions
        self.import_plan._build_action(  # pylint: disable=protected-access
            CreateTag,
            TagItem(
                id=tag_id,
                value='_',
                index=100
            )
        )
        assert len(self.import_plan.errors) == errors_expected
        assert len(self.import_plan.actions) == 1
        assert self.import_plan.actions[0].name == 'create'
        assert self.import_plan.indexed_actions['create'][1].tag.id == tag_id

    def test_build_delete_actions(self) -> None:
        tags = {
            tag.external_id: tag
            for tag in self.taxonomy.tag_set.exclude(pk=25)
        }
        # Clear other actions to only have the delete ones
        self.import_plan.actions.clear()

        self.import_plan._build_delete_actions(tags)  # pylint: disable=protected-access
        assert len(self.import_plan.errors) == 0

        # Check actions in order
        # #1 Delete 'tag_1'
        assert self.import_plan.actions[0].name == 'delete'
        assert self.import_plan.actions[0].tag.id == 'tag_1'
        # #2 Delete 'tag_2'
        assert self.import_plan.actions[1].name == 'delete'
        assert self.import_plan.actions[1].tag.id == 'tag_2'
        # #3 Delete 'tag_3'
        assert self.import_plan.actions[2].name == 'delete'
        assert self.import_plan.actions[2].tag.id == 'tag_3'

    @ddt.data(
        # Test valid actions
        (
            [
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
            ]
        ),
        # Test with errors in actions
        (
            [
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
            4,
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
            ]
        ),
        # Test with deletes (replace=True)
        (
            [
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
                    'name': 'update_parent',
                    'id': 'tag_4',
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
                    'name': 'delete',
                    'id': 'tag_3',
                },
                {
                    'name': 'without_changes',
                    'id': 'tag_4',
                },
            ]
        )
    )
    @ddt.unpack
    def test_generate_actions(self, tags, replace, expected_errors, expected_actions):
        tags = [TagItem(**tag) for tag in tags]
        self.import_plan.generate_actions(tags=tags, replace=replace)
        assert len(self.import_plan.errors) == expected_errors
        assert len(self.import_plan.actions) == len(expected_actions)

        for index, action in enumerate(expected_actions):
            assert self.import_plan.actions[index].name == action['name']
            assert self.import_plan.actions[index].tag.id == action['id']
            assert self.import_plan.actions[index].index == index + 1

    @ddt.data(
        # Testing plan with errors
        (
            [
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
            "Import plan for Import Taxonomy Test\n"
            "--------------------------------\n"
            "#1: Create a new tag with values (external_id=tag_31, value=Tag 31, parent_id=None).\n"
            "#2: Create a new tag with values (external_id=tag_31, value=Tag 32, parent_id=None).\n"
            "#3: Rename tag value of <Tag> (tag_1 / Tag 1) to 'Tag 2'\n"
            "#4: Update the parent of <Tag> (tag_4 / Tag 4) from parent "
            "<Tag> (tag_3 / Tag 3) to tag_100\n"
            "#5: Create a new tag with values (external_id=tag_33, value=Tag 32, parent_id=None).\n"
            "#6: Update the parent of <Tag> (tag_2 / Tag 2) from parent "
            "<Tag> (tag_1 / Tag 1) to None\n"
            "#7: Rename tag value of <Tag> (tag_2 / Tag 2) to 'Tag 31'\n"
            "\nOutput errors\n"
            "--------------------------------\n"
            "Duplicate id (tag_31): file rows 1, 2 all claim it as their final id. "
            "Each row's id must be unique within a single import.\n"
            "Conflict with 'create' (#2) and action #1: Duplicated external_id tag.\n"
            "Action error in 'rename' (#3): Duplicated tag value with tag in database (external_id=tag_2).\n"
            "Action error in 'update_parent' (#4): Unknown parent tag (tag_100). "
            "Add a row for the parent to your file.\n"
            "Conflict with 'create' (#5) and action #2: Duplicated tag value.\n"
            "Conflict with 'rename' (#7) and action #1: Duplicated tag value.\n"
        ),
        # Testing valid plan
        (
            [
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
            "Import plan for Import Taxonomy Test\n"
            "--------------------------------\n"
            "#1: Create a new tag with values (external_id=tag_31, value=Tag 31, parent_id=None).\n"
            "#2: Create a new tag with values (external_id=tag_32, value=Tag 32, parent_id=tag_1).\n"
            "#3: Rename tag value of <Tag> (tag_2 / Tag 2) to 'Tag 2 v2'\n"
            "#4: Update the parent of <Tag> (tag_4 / Tag 4) from parent "
            "<Tag> (tag_3 / Tag 3) to tag_1\n"
            "#5: Rename tag value of <Tag> (tag_4 / Tag 4) to 'Tag 4 v2'\n"
            "#6: No changes needed for <TagItem> (tag_1 / Tag 1)\n"
        ),
        # Testing deletes (replace=True)
        (
            [
                {
                    'id': 'tag_4',
                    'value': 'Tag 4',
                    'parent_id': 'tag_3',
                },
            ],
            True,
            "Import plan for Import Taxonomy Test\n"
            "--------------------------------\n"
            "#1: Update the parent of <Tag> (tag_4 / Tag 4) from parent "
            "<Tag> (tag_3 / Tag 3) to None\n"
            "#2: Delete tag <TagItem> (tag_1 / Tag 1)\n"
            "#3: Delete tag <TagItem> (tag_2 / Tag 2)\n"
            "#4: Delete tag <TagItem> (tag_3 / Tag 3)\n"
            "#5: No changes needed for <TagItem> (tag_4 / Tag 4)\n"
        ),
    )
    @ddt.unpack
    def test_plan(self, tags, replace, expected):
        """
        Test the output of plan() function

        It has been decided to verify the output exactly to detect
        any error when printing this information that the user is going to read.
        """
        tags = [TagItem(**tag) for tag in tags]
        self.import_plan.generate_actions(tags=tags, replace=replace)
        plan = self.import_plan.plan()
        assert plan == expected

    @ddt.data(
        # Testing all actions
        (
            [
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
        ),
        # Testing deletes (replace=True)
        (
            [
                {
                    'id': 'tag_4',
                    'value': 'Tag 4',
                    'parent_id': 'tag_3',
                },
            ],
            True,
        ),
    )
    @ddt.unpack
    def test_execute(self, tags, replace):
        tags = [TagItem(**tag) for tag in tags]
        self.import_plan.generate_actions(tags=tags, replace=replace)
        self.import_plan.execute()
        tag_external_ids = []
        for tag_item in tags:
            # This checks any creation
            tag = self.taxonomy.tag_set.get(external_id=tag_item.id)

            # Checks any rename
            assert tag.value == tag_item.value

            # Checks any parent update
            if not replace:
                if not tag_item.parent_id:
                    assert tag.parent is None
                else:
                    assert tag.parent.external_id == tag_item.parent_id

            tag_external_ids.append(tag_item.id)

        if replace:
            # Checks deletions checking that exists the updated tags
            external_ids = list(self.taxonomy.tag_set.values_list("external_id", flat=True))
            assert tag_external_ids == external_ids

    def test_generate_actions_rename_external_id(self) -> None:
        tags = [
            TagItem(id='tag_50', value='Tag 1', previous_id='tag_1'),
        ]
        self.import_plan.generate_actions(tags=tags, replace=False)
        self.assertEqual(len(self.import_plan.errors), 0)
        self.assertEqual(len(self.import_plan.actions), 1)
        self.assertEqual(self.import_plan.actions[0].name, 'rename_external_id')
        self.assertEqual(self.import_plan.actions[0].tag.id, 'tag_50')

    def test_generate_actions_rename_external_id_case_only_skips_staging(self) -> None:
        """
        A case-only rename (id differs from previous_id only in case) must not
        stage itself via StageTagExternalIdForSwap: there is no other row
        contending for the id, so the swap is unnecessary and its plan message
        ("temporarily move tag off its external_id...") would be misleading.
        """
        tags = [
            TagItem(id='TAG_1', value='Tag 1', previous_id='tag_1'),
        ]
        self.import_plan.generate_actions(tags=tags, replace=False)
        self.assertEqual(len(self.import_plan.errors), 0)
        self.assertEqual(len(self.import_plan.indexed_actions['stage_external_id']), 0)
        self.assertEqual(len(self.import_plan.indexed_actions['rename_external_id']), 1)

    def test_generate_actions_rename_external_id_replace_skips_delete(self) -> None:
        # tag_1 is renamed to tag_50 (previous_id='tag_1'); under replace=True
        # its old id must not be swept up in the delete pass, since it is the
        # same underlying tag, not a removed one.
        tags = [
            TagItem(id='tag_50', value='Tag 1', previous_id='tag_1'),
            TagItem(id='tag_2', value='Tag 2'),
            TagItem(id='tag_3', value='Tag 3'),
            TagItem(id='tag_4', value='Tag 4', parent_id='tag_3'),
        ]
        self.import_plan.generate_actions(tags=tags, replace=True)
        self.assertEqual(len(self.import_plan.errors), 0)
        delete_targets = [
            action.tag.id for action in self.import_plan.actions if action.name == 'delete'
        ]
        self.assertNotIn('tag_1', delete_targets)

    def test_generate_actions_rename_external_id_replace_skips_delete_case_different_previous_id(self) -> None:
        """
        Regression: previous_id='TAG_1' must still protect the existing
        tag_1 tag from the replace-mode delete sweep even though it differs
        from the stored external_id only in case, since external_id is a
        case-insensitive DB field. Before the fix, the exact-case pop missed
        this tag, queuing it for deletion and then crashing the rename's own
        execute() with Tag.DoesNotExist.
        """
        tags = [
            TagItem(id='tag_50', value='Tag 1', previous_id='TAG_1'),
            TagItem(id='tag_2', value='Tag 2'),
            TagItem(id='tag_3', value='Tag 3'),
            TagItem(id='tag_4', value='Tag 4', parent_id='tag_3'),
        ]
        self.import_plan.generate_actions(tags=tags, replace=True)
        self.assertEqual(len(self.import_plan.errors), 0)
        delete_targets = [
            action.tag.id for action in self.import_plan.actions if action.name == 'delete'
        ]
        self.assertNotIn('tag_1', delete_targets)

    def test_generate_actions_plain_row_replace_skips_delete_case_different_id(self) -> None:
        """
        Regression: a plain row (no previous_id) with id='TAG_1' must still
        protect the existing tag_1 tag from the replace-mode delete sweep
        even though it differs from the stored external_id only in case.
        Before the fix, the exact-case `tag.id in tags_for_delete` check
        missed this tag, queuing it for deletion and then crashing
        tag_4's own update_parent action (an explicit re-parent onto
        "tag_1") once tag_1 no longer existed.
        """
        tags = [
            TagItem(id='TAG_1', value='Tag 1'),
            TagItem(id='tag_2', value='Tag 2', parent_id='tag_1'),
            TagItem(id='tag_3', value='Tag 3'),
            TagItem(id='tag_4', value='Tag 4', parent_id='tag_1'),
        ]
        self.import_plan.generate_actions(tags=tags, replace=True)
        self.assertEqual(len(self.import_plan.errors), 0)
        delete_targets = [
            action.tag.id for action in self.import_plan.actions if action.name == 'delete'
        ]
        self.assertNotIn('tag_1', delete_targets)

    def test_generate_actions_rename_external_id_value_collision_with_create(self) -> None:
        """
        Regression: a value collision between a `RenameTagExternalId` action
        and a later `CreateTag` action in the same import must be caught at
        validate time, not silently pass through to `execute()` and hit the
        database's `unique_together(taxonomy, value)` constraint.
        """
        tags = [
            TagItem(id='tag_50', value='Shared', previous_id='tag_1'),
            TagItem(id='tag_60', value='Shared'),
        ]
        self.import_plan.generate_actions(tags=tags, replace=False)
        self.assertEqual(len(self.import_plan.errors), 1)
        self.assertIn("Duplicated tag value", str(self.import_plan.errors[0]))

    def test_error_in_execute(self):
        created_tag = 'tag_31'
        tags = [
            TagItem(
                id=created_tag,
                value='Tag 31'
            ),  # Valid tag (creation)
            TagItem(
                id='tag_32',
                value='Tag 31'
            ),  # Invalid
        ]
        self.import_plan.generate_actions(tags=tags)
        assert not self.taxonomy.tag_set.filter(external_id=created_tag).exists()
        assert not self.import_plan.execute()
        assert not self.taxonomy.tag_set.filter(external_id=created_tag).exists()

    def test_generate_actions_swap_stages_and_renames(self) -> None:
        """
        A 2-tag swap (tag_1 <-> tag_3, both root tags) has no valid plain
        execution order, since (taxonomy, external_id) is unique and
        enforced per-statement: each tag must be staged through a
        placeholder id first.
        """
        tags = [
            TagItem(id='tag_3', value='Tag 1', previous_id='tag_1'),
            TagItem(id='tag_1', value='Tag 3', previous_id='tag_3'),
        ]
        self.import_plan.generate_actions(tags=tags, replace=False)
        self.assertEqual(self.import_plan.errors, [])
        self.assertEqual(len(self.import_plan.indexed_actions['stage_external_id']), 2)
        self.assertEqual(len(self.import_plan.indexed_actions['rename_external_id']), 2)
        self.assertEqual(self.import_plan.indexed_actions['rename'], [])
        self.assertEqual(self.import_plan.indexed_actions['update_parent'], [])

    def test_generate_actions_three_cycle_stages_all(self) -> None:
        """
        A 3-cycle (tag_1 -> tag_2 -> tag_3 -> tag_1) is staged the same way
        as a 2-tag swap: every tag in the cycle is contended by another row
        in the same import, so all three are staged first.
        """
        tags = [
            TagItem(id='tag_2', value='Tag 1', previous_id='tag_1'),
            TagItem(id='tag_3', value='Tag 2', previous_id='tag_2'),
            TagItem(id='tag_1', value='Tag 3', previous_id='tag_3'),
        ]
        self.import_plan.generate_actions(tags=tags, replace=False)
        self.assertEqual(self.import_plan.errors, [])
        self.assertEqual(len(self.import_plan.indexed_actions['stage_external_id']), 3)
        self.assertEqual(len(self.import_plan.indexed_actions['rename_external_id']), 3)

    def test_generate_actions_chain_stages_only_contended_tags(self) -> None:
        """
        A chain tag_2 -> tag_3 -> tag_4 -> tag_90 (fresh, uncontended).
        Only tag_3 and tag_4 are contended (their current id is another
        row's target); tag_2's current id is nobody's target, so it isn't
        staged.
        """
        tag_2_pk = self.taxonomy.tag_set.get(external_id='tag_2').pk
        tag_3_pk = self.taxonomy.tag_set.get(external_id='tag_3').pk
        tag_4_pk = self.taxonomy.tag_set.get(external_id='tag_4').pk

        tags = [
            TagItem(id='tag_3', value='Tag 2', previous_id='tag_2'),
            TagItem(id='tag_4', value='Tag 3', previous_id='tag_3'),
            TagItem(id='tag_90', value='Tag 4', previous_id='tag_4'),
        ]
        self.import_plan.generate_actions(tags=tags, replace=False)
        self.assertEqual(self.import_plan.errors, [])
        staged_pks = {
            action.target_pk for action in self.import_plan.indexed_actions['stage_external_id']
        }
        self.assertEqual(staged_pks, {tag_3_pk, tag_4_pk})
        self.assertNotIn(tag_2_pk, staged_pks)
        self.assertEqual(len(self.import_plan.indexed_actions['rename_external_id']), 3)

    def test_generate_actions_parent_id_stale_after_plain_rename_rejected(self) -> None:
        """
        Regression: tag_1 is renamed to tag_50 and nothing reuses "tag_1"
        (a plain, non-contended rename, never staged). A different row's
        parent_id references the now-stale "tag_1" -- must be rejected,
        since no tag will hold that external_id after the import.
        """
        tags = [
            TagItem(id='tag_50', value='Tag 1', previous_id='tag_1'),
            TagItem(id='tag_60', value='Tag 60', parent_id='tag_1'),
        ]
        self.import_plan.generate_actions(tags=tags, replace=False)
        self.assertEqual(len(self.import_plan.errors), 1)
        self.assertIn(
            "Parent tag tag_1 is renamed to tag_50 in this file; use tag_50 as the parent_id.",
            str(self.import_plan.errors[0]),
        )

    def test_generate_actions_parent_id_new_id_after_earlier_rename_accepted(self) -> None:
        """
        Same rename as above (tag_1 -> tag_50), but the other row's
        parent_id references the *new* id "tag_50" instead of the stale old
        one, and the rename row comes first in the file: this must be
        accepted, same convention as referencing a newly-created parent.
        """
        tags = [
            TagItem(id='tag_50', value='Tag 1', previous_id='tag_1'),
            TagItem(id='tag_60', value='Tag 60', parent_id='tag_50'),
        ]
        self.import_plan.generate_actions(tags=tags, replace=False)
        self.assertEqual(self.import_plan.errors, [])

    def test_generate_actions_existing_child_names_renamed_away_parent_rejected(self) -> None:
        """
        An existing child that keeps its parent's pre-import id is rejected when the file
        renames that parent, and the error names the row and the parent's new id.

        Before      File rows
        tag_1       tag_50 (previous_id tag_1)
            tag_2   tag_2 (parent_id tag_1)

        The tag_2 row is "no change" for UpdateParentTag, so only the plan-level check can
        reject it.
        """
        tags = [
            TagItem(id='tag_50', value='Tag 1', previous_id='tag_1'),
            TagItem(id='tag_2', value='Tag 2', parent_id='tag_1'),
        ]
        self.import_plan.generate_actions(tags=tags, replace=False)
        self.assertEqual(len(self.import_plan.errors), 1)
        self.assertIn("Row 2's parent_id (tag_1)", str(self.import_plan.errors[0]))
        self.assertIn("Use 'tag_50' as the parent_id.", str(self.import_plan.errors[0]))

    def test_generate_actions_swap_rename_child_stale_parent_id_rejected_once(self) -> None:
        """
        In a swap, a child that is itself renamed and names its parent's stale id is reported
        exactly once.

        Before      File rows
        tag_1       tag_3 (previous_id tag_1)
            tag_2   tag_1 (previous_id tag_3)
        tag_3       tag_20 (previous_id tag_2, parent_id tag_1)

        The rename action's own parent validation accepts "tag_1", because it is also another
        rename row's final id, so the plan-level check reports it.
        """
        tags = [
            TagItem(id='tag_3', value='Tag 1', previous_id='tag_1'),
            TagItem(id='tag_1', value='Tag 3', previous_id='tag_3'),
            TagItem(id='tag_20', value='Tag 2', previous_id='tag_2', parent_id='tag_1'),
        ]
        self.import_plan.generate_actions(tags=tags, replace=False)
        self.assertEqual(len(self.import_plan.errors), 1)
        self.assertIn("Row 3's parent_id (tag_1)", str(self.import_plan.errors[0]))

    def test_generate_actions_rename_child_stale_parent_id_without_swap_not_duplicated(self) -> None:
        """
        Without a swap, a renamed child that names its parent's stale id is reported only by
        the rename action's parent validation, not a second time by the plan-level check.

        Before      File rows
        tag_1       tag_50 (previous_id tag_1)
            tag_2   tag_20 (previous_id tag_2, parent_id tag_1)
        """
        tags = [
            TagItem(id='tag_50', value='Tag 1', previous_id='tag_1'),
            TagItem(id='tag_20', value='Tag 2', previous_id='tag_2', parent_id='tag_1'),
        ]
        self.import_plan.generate_actions(tags=tags, replace=False)
        self.assertEqual(len(self.import_plan.errors), 1)
        self.assertIn(
            "Parent tag tag_1 is renamed to tag_50 in this file; use tag_50 as the parent_id.",
            str(self.import_plan.errors[0]),
        )

    def test_generate_actions_case_only_parent_rename_not_flagged(self) -> None:
        """
        A rename that only changes the parent's capitalization keeps the id pointing at the
        same tag, so a child that keeps parent_id "tag_1" is accepted.

        Before      After
        tag_1       TAG_1
            tag_2       tag_2
        """
        tags = [
            TagItem(id='TAG_1', value='Tag 1', previous_id='tag_1'),
            TagItem(id='tag_2', value='Tag 2', parent_id='tag_1'),
        ]
        self.import_plan.generate_actions(tags=tags, replace=False)
        self.assertEqual(self.import_plan.errors, [])

    def test_generate_actions_swap_children_accepted_in_any_row_order(self) -> None:
        """
        Children that name the end-state ids of swapped parents are accepted in every row
        order. Each child stays on the same physical parent.

        Before      After
        tag_1       tag_3 (was tag_1)
            tag_2       tag_2
        tag_3       tag_1 (was tag_3)
            tag_4       tag_4
        """
        rows = [
            TagItem(id='tag_1', value='Tag 3', previous_id='tag_3'),
            TagItem(id='tag_3', value='Tag 1', previous_id='tag_1'),
            TagItem(id='tag_2', value='Tag 2', parent_id='tag_3'),
            TagItem(id='tag_4', value='Tag 4', parent_id='tag_1'),
        ]
        # Planning is fast, so every one of the 24 row orders is checked.
        for order in itertools.permutations(range(4)):
            with self.subTest(order=order):
                self.import_plan.generate_actions(tags=[rows[i] for i in order], replace=False)
                self.assertEqual(self.import_plan.errors, [])

    def test_generate_actions_swap_stale_ids_rejected_in_any_row_order(self) -> None:
        """
        Children that name the stale pre-import ids of swapped parents are rejected in every
        row order. Each error names the child's row number and its parent's new id.

        Before      File rows
        tag_1       tag_1 (previous_id tag_3)
            tag_2   tag_3 (previous_id tag_1)
        tag_3       tag_2 (parent_id tag_1)
            tag_4   tag_4 (parent_id tag_3)
        """
        rows = [
            TagItem(id='tag_1', value='Tag 3', previous_id='tag_3'),
            TagItem(id='tag_3', value='Tag 1', previous_id='tag_1'),
            TagItem(id='tag_2', value='Tag 2', parent_id='tag_1'),
            TagItem(id='tag_4', value='Tag 4', parent_id='tag_3'),
        ]
        # Planning is fast, so every one of the 24 row orders is checked.
        for order in itertools.permutations(range(4)):
            with self.subTest(order=order):
                file_rows = [rows[i] for i in order]
                self.import_plan.generate_actions(tags=file_rows, replace=False)
                messages = [str(error) for error in self.import_plan.errors]
                self.assertEqual(len(messages), 2)
                new_ids = {'tag_1': 'tag_3', 'tag_3': 'tag_1'}
                for position, row in enumerate(file_rows, start=1):
                    if row.parent_id:
                        prefix = f"Row {position}'s parent_id ({row.parent_id})"
                        matching = [m for m in messages if m.startswith(prefix)]
                        self.assertEqual(len(matching), 1)
                        self.assertIn(f"Use '{new_ids[row.parent_id]}' as the parent_id.", matching[0])

    def test_generate_actions_valid_row_order_keeps_action_order(self) -> None:
        """
        A file whose parents already come before their children keeps its row order in the
        plan.

        Before      After
        tag_1       new_parent
                        new_child
                    tag_50 (was tag_1)
                        renamed_tag_child
        """
        tags = [
            TagItem(id='new_parent', value='New parent'),
            TagItem(id='new_child', value='New child', parent_id='new_parent'),
            TagItem(id='tag_50', value='Tag 1', previous_id='tag_1'),
            TagItem(id='renamed_tag_child', value='Renamed tag child', parent_id='tag_50'),
        ]
        self.import_plan.generate_actions(tags=tags, replace=False)
        self.assertEqual(self.import_plan.errors, [])
        self.assertEqual(
            [action.tag.id for action in self.import_plan.actions],
            ['new_parent', 'new_child', 'tag_50', 'renamed_tag_child'],
        )

    def test_generate_actions_deep_reversed_chain_terminates(self) -> None:
        """
        A 1100-row chain of new tags listed child first is ordered without hitting the
        recursion limit, and every row is planned. The chain is far too deep to apply, so the
        plan reports it.

        File rows: n1099 (parent_id n1098), ..., n1 (parent_id n0), n0
        """
        tags = [
            TagItem(id=f'n{i}', value=f'N{i}', parent_id=f'n{i - 1}' if i else None)
            for i in reversed(range(1100))
        ]
        self.import_plan.generate_actions(tags=tags, replace=False)
        self.assertEqual(len(self.import_plan.actions), 1100)
        self.assertEqual(self.import_plan.actions[0].tag.id, 'n0')
        self.assertEqual(len(self.import_plan.errors), 1)
        self.assertIn('deeper than 6 levels', str(self.import_plan.errors[0]))

    def test_plan_validations_do_not_query_per_row(self) -> None:
        """
        The row ordering and the plan-level validations add no queries, however many rows
        have a parent_id: the plan costs the same with them replaced by no-ops.

        File rows: 200 new tags, every second one under tag_1 and the others under the new
        tag before them.
        """
        tags = [
            TagItem(id=f'n{i}', value=f'N{i}', parent_id='tag_1' if i % 2 == 0 else f'n{i - 1}')
            for i in range(200)
        ]
        with CaptureQueriesContext(connection) as real:
            self.import_plan.generate_actions(tags=tags, replace=False)
        with (
            mock.patch.object(TagImportPlan, '_validate_parent_id_not_stale'),
            mock.patch.object(TagImportPlan, '_validate_no_parent_cycles'),
            mock.patch.object(
                TagImportPlan, '_order_rows_by_parent_dependency', side_effect=lambda rows, existing: list(rows),
            ),
            CaptureQueriesContext(connection) as without_validations,
        ):
            self.import_plan.generate_actions(tags=tags, replace=False)
        self.assertEqual(len(real), len(without_validations))

    def test_generate_actions_three_level_chain_defined_later_accepted(self) -> None:
        """
        Three new tags listed child first are created parent first.

        File rows                                   After
        new_child (parent_id new_parent)            new_grandparent
        new_parent (parent_id new_grandparent)          new_parent
        new_grandparent                                     new_child
        """
        tags = [
            TagItem(id='new_child', value='New child', parent_id='new_parent'),
            TagItem(id='new_parent', value='New parent', parent_id='new_grandparent'),
            TagItem(id='new_grandparent', value='New grandparent'),
        ]
        self.import_plan.generate_actions(tags=tags, replace=False)
        self.assertEqual(self.import_plan.errors, [])
        self.assertEqual(
            [action.tag.id for action in self.import_plan.actions],
            ['new_grandparent', 'new_parent', 'new_child'],
        )

    def test_generate_actions_existing_tag_moved_under_later_new_parent_accepted(self) -> None:
        """
        An existing tag moved under a new parent whose row comes later in the file is
        accepted, and the parent is created first.

        Before      After
        tag_1       tag_1
            tag_2   new_parent
                        tag_2
        """
        tags = [
            TagItem(id='tag_2', value='Tag 2', parent_id='new_parent'),
            TagItem(id='new_parent', value='New parent'),
        ]
        self.import_plan.generate_actions(tags=tags, replace=False)
        self.assertEqual(self.import_plan.errors, [])
        self.assertEqual(self.import_plan.actions[0].name, 'create')
        self.assertEqual(self.import_plan.actions[0].tag.id, 'new_parent')

    def test_generate_actions_mixed_case_parent_id_defined_later_accepted(self) -> None:
        """
        A parent_id that differs only in case from the id of a later new row still makes the
        child wait for that row, because ids are case-insensitive.

        File rows                                   After
        new_child (parent_id NEW_PARENT)            New_Parent
        New_Parent                                      new_child
        """
        tags = [
            TagItem(id='new_child', value='New child', parent_id='NEW_PARENT'),
            TagItem(id='New_Parent', value='New parent'),
        ]
        self.import_plan.generate_actions(tags=tags, replace=False)
        self.assertEqual(self.import_plan.errors, [])
        self.assertEqual(self.import_plan.actions[0].tag.id, 'New_Parent')

    def test_generate_actions_self_parent_of_existing_tag_rejected(self) -> None:
        """
        An existing tag that names itself as its parent is a cycle of length one and is
        reported once.

        Before      File rows
        tag_1       tag_2 (parent_id tag_2)
            tag_2
        """
        self.import_plan.generate_actions(tags=[TagItem(id='tag_2', value='Tag 2', parent_id='tag_2')], replace=False)
        messages = [str(error) for error in self.import_plan.errors]
        self.assertEqual(messages, ["Row 1's parent_id (tag_2) creates a parent cycle."])

    def test_generate_actions_child_of_deleted_holder_follows_rename_onto_its_id(self) -> None:
        """
        With replace=True the file omits tag_1, so tag_1 is deleted, and renames tag_3 onto
        the id tag_1. The tag_2 row names tag_1, so tag_2 moves under the renamed tag after
        the rename runs, instead of being promoted to a root.

        Before      After
        tag_1       tag_1 (was tag_3)
            tag_2       tag_2
        tag_3
            tag_4
        """
        tags = [
            TagItem(id='tag_1', value='Tag 3', previous_id='tag_3'),
            TagItem(id='tag_2', value='Tag 2', parent_id='tag_1'),
        ]
        self.import_plan.generate_actions(tags=tags, replace=True)
        self.assertEqual(self.import_plan.errors, [])
        row_updates = [
            action for action in self.import_plan.indexed_actions['update_parent']
            if action.tag.id == 'tag_2' and action.tag.parent_id == 'tag_1'
        ]
        self.assertEqual(len(row_updates), 1)
        self.assertGreater(
            self.import_plan.actions.index(row_updates[0]),
            self.import_plan.actions.index(self.import_plan.indexed_actions['rename_external_id'][0]),
        )

    def _plan_for_new_taxonomy(self, tags: list[TagItem]) -> TagImportPlan:
        """
        Create ``tags`` (parents listed before their children) in an empty taxonomy shared by
        the class, and return a plan for that taxonomy. A test calls this once, and the tags
        are rolled back with the test.
        """
        created: dict[str, Tag] = {}
        for tag in tags:
            created[tag.id] = Tag.objects.create(
                taxonomy=self.structure_taxonomy,
                value=tag.value,
                external_id=tag.id,
                parent=created[tag.parent_id] if tag.parent_id else None,
            )
        return TagImportPlan(self.structure_taxonomy)

    def test_generate_actions_valid_move_order_keeps_action_order(self) -> None:
        """
        A file whose parent moves are already in a valid order keeps its row order in the
        plan.

        Before              After
        old_root            new_root
            old_child           new_middle
            new_root                old_root
                                    old_child
        """
        plan = self._plan_for_new_taxonomy([
            TagItem(id='old_root', value='Old root'),
            TagItem(id='old_child', value='Old child', parent_id='old_root'),
            TagItem(id='new_root', value='New root', parent_id='old_root'),
        ])
        rows = [
            TagItem(id='new_root', value='New root'),
            TagItem(id='new_middle', value='New middle', parent_id='new_root'),
            TagItem(id='old_root', value='Old root', parent_id='new_middle'),
            TagItem(id='old_child', value='Old child', parent_id='new_middle'),
        ]
        plan.generate_actions(tags=rows, replace=False)
        self.assertEqual(plan.errors, [])
        self.assertEqual(
            [action.tag.id for action in plan.actions], ['new_root', 'new_middle', 'old_root', 'old_child'],
        )

    def test_generate_actions_ordinary_import_has_no_detach_actions(self) -> None:
        """
        An import whose steps are all valid keeps its plan: no move to the root is added
        before the other actions.

        Before              After
        level_1             level_1
            level_2             level_2
                level_3             level_3
                                        new_leaf
        """
        chain = [
            TagItem(id='level_1', value='Level 1'),
            TagItem(id='level_2', value='Level 2', parent_id='level_1'),
            TagItem(id='level_3', value='Level 3', parent_id='level_2'),
        ]
        plan = self._plan_for_new_taxonomy(chain)
        plan.generate_actions(
            tags=chain + [TagItem(id='new_leaf', value='New leaf', parent_id='level_3')],
            replace=False,
        )
        self.assertEqual(plan.errors, [])
        self.assertEqual(
            [action.name for action in plan.actions], ['without_changes'] * 3 + ['create'],
        )

    def test_parent_dry_run_accepts_valid_and_rejects_invalid_sequences(self) -> None:
        """
        ``_ParentForest`` accepts a valid move, and rejects a cycle, a tree that gets too
        deep, and a reference to a tag that an earlier delete removed (a delete also removes
        the descendants).

        Before
        level_1
            level_2
                level_3
                    level_4
                        level_5
        other_root
            other_child
        """
        tags = {
            'level_1': ExistingTag(pk=1, parent_pk=None, parent_external_id=None),
            'level_2': ExistingTag(pk=2, parent_pk=1, parent_external_id='level_1'),
            'level_3': ExistingTag(pk=3, parent_pk=2, parent_external_id='level_2'),
            'level_4': ExistingTag(pk=4, parent_pk=3, parent_external_id='level_3'),
            'level_5': ExistingTag(pk=5, parent_pk=4, parent_external_id='level_4'),
            'other_root': ExistingTag(pk=6, parent_pk=None, parent_external_id=None),
            'other_child': ExistingTag(pk=7, parent_pk=6, parent_external_id='other_root'),
        }
        taxonomy = Taxonomy()

        def move(tag_id: str, parent_id: str | None) -> UpdateParentTag:
            return UpdateParentTag(taxonomy, TagItem(id=tag_id, value='x', parent_id=parent_id), 1)

        delete_level_2 = DeleteTag(taxonomy, TagItem(id='level_2', value='x'), 1)
        self.assertTrue(_ParentForest(tags).apply(move('other_child', 'level_1')))
        # level_1 under its own descendant is a cycle.
        self.assertFalse(_ParentForest(tags).apply(move('level_1', 'level_5')))
        # other_child would end up at a seventh level.
        self.assertFalse(_ParentForest(tags).apply(move('other_root', 'level_5')))
        forest = _ParentForest(tags)
        self.assertTrue(forest.apply(delete_level_2))
        self.assertFalse(forest.apply(move('other_root', 'level_3')))
        forest = _ParentForest(tags)
        self.assertTrue(forest.apply(delete_level_2))
        self.assertTrue(forest.apply(move('other_root', 'level_1')))

    def test_generate_actions_swap_case_variant_of_stale_parent_id_rejected(self) -> None:
        """
        In a swap, a child naming its parent's stale id in another case is rejected like the
        exact spelling, with its row number and the parent's new id.

        Before      File rows
        tag_1       tag_3 (previous_id tag_1)
            tag_2   tag_1 (previous_id tag_3)
        tag_3       tag_2 (parent_id TAG_1)
        """
        tags = [
            TagItem(id='tag_3', value='Tag 1', previous_id='tag_1'),
            TagItem(id='tag_1', value='Tag 3', previous_id='tag_3'),
            TagItem(id='tag_2', value='Tag 2', parent_id='TAG_1'),
        ]
        self.import_plan.generate_actions(tags=tags, replace=False)
        messages = [str(error) for error in self.import_plan.errors]
        self.assertEqual(len(messages), 1)
        self.assertIn("Row 3's parent_id (TAG_1)", messages[0])
        self.assertIn("Use 'tag_3' as the parent_id.", messages[0])

    def test_generate_actions_swap_case_variant_of_end_state_parent_id_accepted(self) -> None:
        """
        In a swap, children naming the end-state ids of their parents in another case are
        accepted.

        Before      After
        tag_1       tag_3 (was tag_1)
            tag_2       tag_2 (parent_id TAG_3)
        tag_3       tag_1 (was tag_3)
            tag_4       tag_4 (parent_id TAG_1)
        """
        tags = [
            TagItem(id='tag_3', value='Tag 1', previous_id='tag_1'),
            TagItem(id='tag_1', value='Tag 3', previous_id='tag_3'),
            TagItem(id='tag_2', value='Tag 2', parent_id='TAG_3'),
            TagItem(id='tag_4', value='Tag 4', parent_id='TAG_1'),
        ]
        self.import_plan.generate_actions(tags=tags, replace=False)
        self.assertEqual(self.import_plan.errors, [])

    def test_generate_actions_plain_rename_case_variant_of_parent_id_reported_once(self) -> None:
        """
        When the parent is renamed without a swap, a child naming the parent's old id in
        another case gets only the parent validation error, not a second one for the same row.

        Before      File rows
        tag_1       tag_50 (previous_id tag_1)
            tag_2   tag_2 (parent_id TAG_1)
        """
        tags = [
            TagItem(id='tag_50', value='Tag 1', previous_id='tag_1'),
            TagItem(id='tag_2', value='Tag 2', parent_id='TAG_1'),
        ]
        self.import_plan.generate_actions(tags=tags, replace=False)
        messages = [str(error) for error in self.import_plan.errors]
        self.assertEqual(len(messages), 1)
        self.assertIn('Parent tag TAG_1 is renamed to tag_50 in this file', messages[0])

    def test_generate_actions_genuine_collision_not_staged(self) -> None:
        """
        A rename targeting an id held by an unrelated tag that is not
        itself being renamed or deleted in this import is a real collision,
        not a staging candidate: the tag holding tag_2 is not a party to
        any rename row in this file.
        """
        tags = [
            TagItem(id='tag_2', value='Tag 1', previous_id='tag_1'),
        ]
        self.import_plan.generate_actions(tags=tags, replace=False)
        self.assertEqual(self.import_plan.indexed_actions['stage_external_id'], [])
        self.assertEqual(len(self.import_plan.errors), 1)
        self.assertIn("already exists", str(self.import_plan.errors[0]))

    def test_generate_actions_rejects_duplicate_final_id(self) -> None:
        """
        Two rows can't claim the same final id: a tag_1<->tag_3 swap plus
        an unrelated third row also targeting id=tag_1 is ambiguous.
        Reject the whole import outright, naming both offending rows by
        position, instead of letting swap-staging silently treat the
        collision as valid (see DuplicateFinalIdError).

        The unrelated third row (plain, id=tag_1) also independently
        matches _validate_no_plain_row_targets_a_vacated_id, since tag_1 is
        also the first row's previous_id: both checks catch a real,
        distinct problem with that same row, so two errors are expected.
        """
        tags = [
            TagItem(id='tag_3', value='Tag 1', previous_id='tag_1'),
            TagItem(id='tag_1', value='Tag 3', previous_id='tag_3'),
            TagItem(id='tag_1', value='Something Else Entirely'),
        ]
        self.import_plan.generate_actions(tags=tags, replace=False)
        self.assertEqual(len(self.import_plan.errors), 2)
        error = str(self.import_plan.errors[0])
        self.assertIn("tag_1", error)
        self.assertIn("file rows 2, 3", error)

    def test_generate_actions_rejects_duplicate_final_id_regardless_of_order(self) -> None:
        """
        Same collision as test_generate_actions_rejects_duplicate_final_id,
        but with the unrelated row moved to the front of the file: the
        rejection doesn't depend on row order.
        """
        tags = [
            TagItem(id='tag_1', value='Something Else Entirely'),
            TagItem(id='tag_3', value='Tag 1', previous_id='tag_1'),
            TagItem(id='tag_1', value='Tag 3', previous_id='tag_3'),
        ]
        self.import_plan.generate_actions(tags=tags, replace=False)
        self.assertEqual(len(self.import_plan.errors), 2)
        error = str(self.import_plan.errors[0])
        self.assertIn("tag_1", error)
        self.assertIn("file rows 1, 3", error)
