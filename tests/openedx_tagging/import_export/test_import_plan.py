"""
Test for import_plan functions
"""
import itertools
from unittest import mock

import ddt  # type: ignore[import]
from django.db import connection
from django.test.testcases import TestCase
from django.test.utils import CaptureQueriesContext

from openedx_tagging.import_export.actions import CreateTag, DeleteTag, RenameTagExternalId, UpdateParentTag
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
        tag_2 is an existing child of tag_1. tag_1 is renamed to tag_50 and
        tag_2's row keeps parent_id="tag_1", the pre-import id. The row is
        "no change" for UpdateParentTag, so only the plan-level check can
        reject it, and the error names the row and the new id.
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
        In a tag_1 <-> tag_3 swap, a rename row (tag_2 -> tag_20) that names
        the stale parent id "tag_1" is reported exactly once. The rename
        action's own parent validation lets it through because "tag_1" is
        also a rename row's final id, so the plan-level check reports it.
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
        Without a swap, a rename row (tag_2 -> tag_20) that names the stale
        parent id "tag_1" is reported only by the rename action's parent
        validation, not a second time by the plan-level check.
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
        A case-only rename of the parent (tag_1 -> TAG_1) keeps the id
        resolving to the same tag, so a child that keeps parent_id="tag_1"
        is not stale.
        """
        tags = [
            TagItem(id='TAG_1', value='Tag 1', previous_id='tag_1'),
            TagItem(id='tag_2', value='Tag 2', parent_id='tag_1'),
        ]
        self.import_plan.generate_actions(tags=tags, replace=False)
        self.assertEqual(self.import_plan.errors, [])

    def test_generate_actions_swap_children_accepted_in_any_row_order(self) -> None:
        """
        The tag_1 <-> tag_3 swap with children on end-state ids is accepted
        in every one of the 24 row orders.
        """
        rows = [
            TagItem(id='tag_1', value='Tag 3', previous_id='tag_3'),
            TagItem(id='tag_3', value='Tag 1', previous_id='tag_1'),
            TagItem(id='tag_2', value='Tag 2', parent_id='tag_3'),
            TagItem(id='tag_4', value='Tag 4', parent_id='tag_1'),
        ]
        for order in itertools.permutations(range(4)):
            with self.subTest(order=order):
                self.import_plan.generate_actions(tags=[rows[i] for i in order], replace=False)
                self.assertEqual(self.import_plan.errors, [])

    def test_generate_actions_swap_stale_ids_rejected_in_any_row_order(self) -> None:
        """
        Children that name the stale pre-import ids are rejected in every one
        of the 24 row orders, and each error reports the row's file position.
        """
        rows = [
            TagItem(id='tag_1', value='Tag 3', previous_id='tag_3'),
            TagItem(id='tag_3', value='Tag 1', previous_id='tag_1'),
            TagItem(id='tag_2', value='Tag 2', parent_id='tag_1'),
            TagItem(id='tag_4', value='Tag 4', parent_id='tag_3'),
        ]
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

    def test_generate_actions_new_child_before_new_parent_accepted(self) -> None:
        """
        A new child row listed before its new parent row is accepted, and the
        plan creates the parent first.
        """
        tags = [
            TagItem(id='tag_90', value='Tag 90', parent_id='tag_91'),
            TagItem(id='tag_91', value='Tag 91'),
        ]
        self.import_plan.generate_actions(tags=tags, replace=False)
        self.assertEqual(self.import_plan.errors, [])
        self.assertEqual([action.tag.id for action in self.import_plan.actions], ['tag_91', 'tag_90'])

    def test_generate_actions_valid_row_order_keeps_action_order(self) -> None:
        """
        A file whose parents already come before their children keeps its
        row order in the plan.
        """
        tags = [
            TagItem(id='tag_91', value='Tag 91'),
            TagItem(id='tag_92', value='Tag 92', parent_id='tag_91'),
            TagItem(id='tag_50', value='Tag 1', previous_id='tag_1'),
            TagItem(id='tag_60', value='Tag 60', parent_id='tag_50'),
        ]
        self.import_plan.generate_actions(tags=tags, replace=False)
        self.assertEqual(self.import_plan.errors, [])
        self.assertEqual(
            [action.tag.id for action in self.import_plan.actions],
            ['tag_91', 'tag_92', 'tag_50', 'tag_60'],
        )

    def test_generate_actions_cyclic_parent_ids_rejected(self) -> None:
        """
        Two new rows that name each other as parent terminate with an error.
        """
        tags = [
            TagItem(id='tag_90', value='Tag 90', parent_id='tag_91'),
            TagItem(id='tag_91', value='Tag 91', parent_id='tag_90'),
        ]
        self.import_plan.generate_actions(tags=tags, replace=False)
        self.assertEqual(len(self.import_plan.errors), 1)
        self.assertIn("Unknown parent tag", str(self.import_plan.errors[0]))

    def test_generate_actions_deep_reversed_chain_terminates(self) -> None:
        """
        A 1100-row chain of new tags listed child first is ordered without hitting the recursion
        limit and every row is planned. The chain is far too deep to apply, so the plan reports it.
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
        The ordering and the plan-level validations add no queries, however many rows have a
        parent_id: the plan costs the same with them replaced by no-ops.
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

    def test_rows_ordered_as_definers_match_create_and_rename_applies_for(self) -> None:
        """
        A row is planned before a child that names its id exactly when it is a rename row or
        CreateTag.applies_for holds: existing tags (also with a different case) are not
        definers, new tags (also with a different case) and rename rows are, including a
        rename onto the id of an existing tag.
        """
        rows = [
            TagItem(id='tag_1', value='Tag 1'),
            TagItem(id='TAG_2', value='Tag 2'),
            TagItem(id='tag_90', value='Tag 90'),
            TagItem(id='Tag_91', value='Tag 91'),
            TagItem(id='tag_50', value='Tag 3', previous_id='tag_3'),
            TagItem(id='tag_4', value='Tag 1', previous_id='tag_1'),
        ]
        planned_first = set()
        for row in rows:
            child = TagItem(id='tag_95', value='Tag 95', parent_id=row.id)
            self.import_plan.generate_actions(tags=[child, row], replace=False)
            ids = [
                action.tag.id for action in self.import_plan.actions if action.name != 'stage_external_id'
            ]
            if ids.index(row.id) < ids.index('tag_95'):
                planned_first.add(row.id)
        expected = {
            row.id for row in rows
            if RenameTagExternalId.applies_for(self.taxonomy, row) or CreateTag.applies_for(self.taxonomy, row)
        }
        self.assertEqual(expected, {'tag_90', 'Tag_91', 'tag_50', 'tag_4'})
        self.assertEqual(planned_first, expected)

    def test_generate_actions_three_level_chain_defined_later_accepted(self) -> None:
        """
        A definer whose own parent is defined later in the file is still
        planned after that parent: a child, its parent and its grandparent
        listed in reverse are created grandparent first.
        """
        tags = [
            TagItem(id='tag_92', value='Tag 92', parent_id='tag_91'),
            TagItem(id='tag_91', value='Tag 91', parent_id='tag_90'),
            TagItem(id='tag_90', value='Tag 90'),
        ]
        self.import_plan.generate_actions(tags=tags, replace=False)
        self.assertEqual(self.import_plan.errors, [])
        self.assertEqual(
            [action.tag.id for action in self.import_plan.actions],
            ['tag_90', 'tag_91', 'tag_92'],
        )

    def test_generate_actions_existing_tag_moved_under_later_new_parent_accepted(self) -> None:
        """
        An existing tag moved under a new parent that is defined later in
        the file is accepted, and the parent is created first.
        """
        tags = [
            TagItem(id='tag_2', value='Tag 2', parent_id='tag_90'),
            TagItem(id='tag_90', value='Tag 90'),
        ]
        self.import_plan.generate_actions(tags=tags, replace=False)
        self.assertEqual(self.import_plan.errors, [])
        self.assertEqual(self.import_plan.actions[0].name, 'create')
        self.assertEqual(self.import_plan.actions[0].tag.id, 'tag_90')

    def test_generate_actions_mixed_case_parent_id_defined_later_accepted(self) -> None:
        """
        A parent_id that differs only in case from the id of a later new row
        still finds that row as its definer.
        """
        tags = [
            TagItem(id='tag_91', value='Tag 91', parent_id='TAG_90'),
            TagItem(id='Tag_90', value='Tag 90'),
        ]
        self.import_plan.generate_actions(tags=tags, replace=False)
        self.assertEqual(self.import_plan.errors, [])
        self.assertEqual(self.import_plan.actions[0].tag.id, 'Tag_90')

    def _cycle_messages(self, tags: list[TagItem]) -> list[str]:
        """
        Generate the actions for `tags` and return the error messages.
        """
        self.import_plan.generate_actions(tags=tags, replace=False)
        return [str(error) for error in self.import_plan.errors]

    def test_generate_actions_self_parent_of_existing_tag_rejected(self) -> None:
        """
        An existing tag that names itself as its parent is a cycle of length
        one and is reported once.
        """
        messages = self._cycle_messages([TagItem(id='tag_2', value='Tag 2', parent_id='tag_2')])
        self.assertEqual(messages, ["Row 1's parent_id (tag_2) creates a parent cycle."])

    def test_generate_actions_existing_and_new_tag_cycle_rejected_once(self) -> None:
        """
        An existing tag and a new tag naming each other as parent are rejected
        with exactly one cycle error, in either row order.
        """
        rows = [
            TagItem(id='tag_2', value='Tag 2', parent_id='tag_90'),
            TagItem(id='tag_90', value='Tag 90', parent_id='tag_2'),
        ]
        for order in itertools.permutations(range(2)):
            with self.subTest(order=order):
                messages = self._cycle_messages([rows[i] for i in order])
                self.assertEqual(len(messages), 1)
                self.assertIn("Row 1's parent_id", messages[0])
                self.assertIn("creates a parent cycle.", messages[0])

    def test_generate_actions_cycle_through_db_only_tag_rejected(self) -> None:
        """
        tag_2 is a child of tag_1 and is not in the file. A row moving tag_1
        under tag_2 closes a cycle through that DB-only tag.
        """
        messages = self._cycle_messages([TagItem(id='tag_1', value='Tag 1', parent_id='tag_2')])
        self.assertEqual(messages, ["Row 1's parent_id (tag_2) creates a parent cycle."])

    def test_generate_actions_cycle_of_definer_rows_reports_only_unknown_parent(self) -> None:
        """
        A cycle made only of new-tag rows, or of a rename row and a new-tag
        row, is reported by the parent validation as an unknown parent and not
        a second time as a cycle.
        """
        cases = {
            'new tags': [
                TagItem(id='tag_90', value='Tag 90', parent_id='tag_91'),
                TagItem(id='tag_91', value='Tag 91', parent_id='tag_90'),
            ],
            'rename and new tag': [
                TagItem(id='tag_50', value='Tag 1', previous_id='tag_1', parent_id='tag_90'),
                TagItem(id='tag_90', value='Tag 90', parent_id='tag_50'),
            ],
        }
        for name, rows in cases.items():
            for order in itertools.permutations(range(2)):
                with self.subTest(case=name, order=order):
                    messages = self._cycle_messages([rows[i] for i in order])
                    self.assertEqual(len(messages), 1)
                    self.assertIn("Unknown parent tag", messages[0])

    def test_generate_actions_self_parent_after_rename_onto_freed_id_rejected(self) -> None:
        """
        tag_3 is renamed onto tag_1, which the same replace import frees, and names
        itself as parent. The cycle is reported at the plan step.
        """
        tags = [TagItem(id='tag_1', value='Tag 3', previous_id='tag_3', parent_id='tag_1')]
        self.import_plan.generate_actions(tags=tags, replace=True)
        messages = [str(error) for error in self.import_plan.errors]
        self.assertEqual(messages, ["Row 1's parent_id (tag_1) creates a parent cycle."])

    def test_generate_actions_child_of_deleted_holder_follows_rename_onto_its_id(self) -> None:
        """
        tag_2 is a child of tag_1, which the replace import deletes while tag_3 is
        renamed onto the id tag_1. Its row plans an update_parent action to tag_1,
        which runs after the rename, instead of leaving it promoted to a root.
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

    def test_defines_id_is_shared_by_ordering_and_cycle_check(self) -> None:
        """
        Both the ordering and the cycle check use one rule for which rows define their id: with
        it patched to never define, a child stays before its late parent row and a cycle of new
        tags is reported as a parent cycle instead of an unknown parent.
        """
        late_parent = [
            TagItem(id='tag_91', value='Tag 91', parent_id='tag_90'),
            TagItem(id='tag_90', value='Tag 90'),
        ]
        new_cycle = [
            TagItem(id='tag_90', value='Tag 90', parent_id='tag_91'),
            TagItem(id='tag_91', value='Tag 91', parent_id='tag_90'),
        ]
        with mock.patch.object(TagImportPlan, '_defines_id', return_value=False):
            self.import_plan.generate_actions(tags=late_parent, replace=False)
            self.assertEqual(self.import_plan.actions[0].tag.id, 'tag_91')
            self.import_plan.generate_actions(tags=new_cycle, replace=False)
            self.assertTrue(any('creates a parent cycle.' in str(e) for e in self.import_plan.errors))

    def _plan_for_new_taxonomy(self, structure: list[tuple[str, str | None]]) -> TagImportPlan:
        """
        Create the given (external_id, parent external_id) tags, in parent-first order, in an
        empty taxonomy shared by the class, and return a plan for it. Each tag's value is
        "Tag <id>". A test calls this once, and its tags are rolled back with the test.
        """
        tags: dict[str, Tag] = {}
        for external_id, parent_id in structure:
            tags[external_id] = Tag.objects.create(
                taxonomy=self.structure_taxonomy,
                value=f'Tag {external_id}',
                external_id=external_id,
                parent=tags[parent_id] if parent_id else None,
            )
        return TagImportPlan(self.structure_taxonomy)

    def _row(self, tag_id: str, parent_id: str | None = None) -> TagItem:
        """
        Build the import row for the tag created by `_plan_for_new_taxonomy`.
        """
        return TagItem(id=tag_id, value=f'Tag {tag_id}', parent_id=parent_id)

    def _assert_promotions_precede_deletes(self, plan: TagImportPlan) -> None:
        """
        Check every delete action comes after every promotion of a kept child to a root.
        """
        names = [action.name for action in plan.actions]
        deletes = [index for index, name in enumerate(names) if name == 'delete']
        self.assertTrue(deletes)
        self.assertEqual(deletes, list(range(deletes[0], deletes[-1] + 1)))
        self.assertNotIn('create', names[:deletes[0]])
        self.assertEqual(set(names[:deletes[0]]), {'update_parent'})

    def test_generate_actions_kept_grandchild_of_deleted_chain_promoted_before_deletes(self) -> None:
        """
        t5 is kept under t1, which is deleted along with its parent t0. Deleting t0
        would cascade to t1 and t5, so t5 is promoted to a root before any delete.
        """
        plan = self._plan_for_new_taxonomy([('t0', None), ('t1', 't0'), ('t5', 't1')])
        plan.generate_actions(tags=[self._row('t5')], replace=True)
        self.assertEqual(plan.errors, [])
        self._assert_promotions_precede_deletes(plan)

    def test_generate_actions_kept_tags_at_two_depths_under_deleted_ancestors(self) -> None:
        """
        In a five-level chain with t0, t1 and t3 deleted, the kept t2 and t4 are both
        promoted before any delete.
        """
        structure = [('t0', None), ('t1', 't0'), ('t2', 't1'), ('t3', 't2'), ('t4', 't3')]
        plan = self._plan_for_new_taxonomy(structure)
        plan.generate_actions(tags=[self._row('t2'), self._row('t4')], replace=True)
        self.assertEqual(plan.errors, [])
        self._assert_promotions_precede_deletes(plan)
        promoted = {
            action.tag.id for action in plan.actions[:2] if action.name == 'update_parent'
        }
        self.assertEqual(promoted, {'t2', 't4'})

    def test_generate_actions_kept_child_of_deleted_root_promoted(self) -> None:
        """
        A kept child of a deleted root is promoted to a root before the delete.
        """
        plan = self._plan_for_new_taxonomy([('t0', None), ('t1', 't0')])
        plan.generate_actions(tags=[self._row('t1')], replace=True)
        self.assertEqual(plan.errors, [])
        self.assertEqual([action.name for action in plan.actions[:2]], ['update_parent', 'delete'])

    def _update_parent_index(self, plan: TagImportPlan, tag_id: str, parent_id: str | None) -> int:
        """
        Return the index of the update_parent action that sets `tag_id` under `parent_id`.
        """
        return next(
            index for index, action in enumerate(plan.actions)
            if action.name == 'update_parent' and action.tag.id == tag_id and action.tag.parent_id == parent_id
        )

    def test_generate_actions_ancestry_inversion_accepted_in_any_row_order(self) -> None:
        """
        t2 is a child of t0 and becomes t0's ancestor (g0 is new, under t2). In all 24 row
        orders the plan is clean and t2 moves out of t0's subtree before t0 moves under g0.
        """
        rows = [
            self._row('t0', 'g0'), self._row('t1', 'g0'), self._row('t2'), self._row('g0', 't2'),
        ]
        plan = self._plan_for_new_taxonomy([('t0', None), ('t1', 't0'), ('t2', 't0')])
        for order in itertools.permutations(range(4)):
            with self.subTest(order=order):
                plan.generate_actions(tags=[rows[i] for i in order], replace=False)
                self.assertEqual(plan.errors, [])
                self.assertLess(
                    self._update_parent_index(plan, 't2', None), self._update_parent_index(plan, 't0', 'g0'),
                )

    def test_generate_actions_parent_and_child_swap_places_in_any_row_order(self) -> None:
        """
        A parent and its child swap places: the child moves to the root before the parent
        moves under it, in either row order.
        """
        rows = [self._row('t0', 't1'), self._row('t1')]
        plan = self._plan_for_new_taxonomy([('t0', None), ('t1', 't0')])
        for order in itertools.permutations(range(2)):
            with self.subTest(order=order):
                plan.generate_actions(tags=[rows[i] for i in order], replace=False)
                self.assertEqual(plan.errors, [])
                self.assertLess(
                    self._update_parent_index(plan, 't1', None), self._update_parent_index(plan, 't0', 't1'),
                )

    def test_generate_actions_three_level_inversion_accepted_in_any_row_order(self) -> None:
        """
        A three-level chain t0 > t1 > t2 is reversed: each move runs only after the tag it
        moves under has left its subtree, in all six row orders.
        """
        rows = [self._row('t2'), self._row('t1', 't2'), self._row('t0', 't1')]
        plan = self._plan_for_new_taxonomy([('t0', None), ('t1', 't0'), ('t2', 't1')])
        for order in itertools.permutations(range(3)):
            with self.subTest(order=order):
                plan.generate_actions(tags=[rows[i] for i in order], replace=False)
                self.assertEqual(plan.errors, [])
                moves = [
                    self._update_parent_index(plan, 't2', None),
                    self._update_parent_index(plan, 't1', 't2'),
                    self._update_parent_index(plan, 't0', 't1'),
                ]
                self.assertEqual(moves, sorted(moves))

    def test_generate_actions_valid_move_order_keeps_action_order(self) -> None:
        """
        A file whose parent moves are already in a valid order keeps its row order in the plan.
        """
        plan = self._plan_for_new_taxonomy([('t0', None), ('t1', 't0'), ('t2', 't0')])
        rows = [self._row('t2'), self._row('g0', 't2'), self._row('t0', 'g0'), self._row('t1', 'g0')]
        plan.generate_actions(tags=rows, replace=False)
        self.assertEqual(plan.errors, [])
        self.assertEqual([action.tag.id for action in plan.actions], ['t2', 'g0', 't0', 't1'])

    def _deep_chain_structure(self) -> list[tuple[str, str | None]]:
        """
        Return a chain t0 > t1 > t2 > t3 > t5 of five levels, the deepest the taxonomy allows
        before a child of t5 would be a sixth level (parent depth 4, so the tag below it is 5).
        """
        return [('t0', None), ('t1', 't0'), ('t2', 't1'), ('t3', 't2'), ('t5', 't3')]

    def _passes_dry_run(self, plan: TagImportPlan) -> bool:
        """
        Return whether the plan's actions pass the parent dry run, on the taxonomy as it is now.
        """
        forest = _ParentForest({
            tag.external_id.casefold(): ExistingTag(
                tag.pk, tag.parent_id, tag.parent.external_id if tag.parent else None,
            )
            for tag in plan.taxonomy.tag_set.select_related('parent')
        })
        return all(forest.apply(action) for action in plan.actions)

    def _assert_detached_first(self, plan: TagImportPlan, tag_id: str) -> None:
        """
        Check the plan starts with the update-to-root of `tag_id`, before any other action
        of its rows, and that the plan passes the dry run.
        """
        first = plan.actions[0]
        self.assertEqual((first.name, first.tag.id, first.tag.parent_id), ('update_parent', tag_id, None))
        self.assertTrue(self._passes_dry_run(plan))

    def test_generate_actions_deep_parent_move_detaches_before_attaching(self) -> None:
        """
        t5 is moved to the root while new tags g0 and g1 are put under it. Creating them
        under t5 before it moves would make g1 a seventh level. All six row orders plan clean,
        and the hazardous one (new tags first) detaches t5 before any create.
        """
        rows = [self._row('g1', 'g0'), self._row('g0', 't5'), self._row('t5')]
        plan = self._plan_for_new_taxonomy(self._deep_chain_structure())
        for order in itertools.permutations(range(3)):
            with self.subTest(order=order):
                plan.generate_actions(tags=[rows[i] for i in order], replace=False)
                self.assertEqual(plan.errors, [])
                self.assertTrue(self._passes_dry_run(plan))
        plan.generate_actions(tags=rows, replace=False)
        self._assert_detached_first(plan, 't5')

    def test_generate_actions_ordinary_import_has_no_detach_actions(self) -> None:
        """
        An import whose steps are all valid keeps its plan: no update-to-root is added.
        """
        plan = self._plan_for_new_taxonomy(self._deep_chain_structure()[:3])
        plan.generate_actions(
            tags=[self._row('t0'), self._row('t1', 't0'), self._row('t2', 't1'), self._row('n0', 't2')],
            replace=False,
        )
        self.assertEqual(plan.errors, [])
        self.assertEqual(
            [action.name for action in plan.actions], ['without_changes'] * 3 + ['create'],
        )

    def test_generate_actions_deep_tag_under_renamed_parent_moved_to_root(self) -> None:
        """
        t5's parent t3 is renamed to r3 while t5 moves to the root and new tags go under it:
        all 24 row orders plan clean, and the hazardous one detaches t5 first.
        """
        rows = [
            self._row('g1', 'g0'), self._row('g0', 't5'), self._row('t5'),
            TagItem(id='r3', value='Tag t3', previous_id='t3', parent_id='t2'),
        ]
        plan = self._plan_for_new_taxonomy(self._deep_chain_structure())
        for order in itertools.permutations(range(4)):
            with self.subTest(order=order):
                plan.generate_actions(tags=[rows[i] for i in order], replace=False)
                self.assertEqual(plan.errors, [])
                self.assertTrue(self._passes_dry_run(plan))
        plan.generate_actions(tags=rows, replace=False)
        self._assert_detached_first(plan, 't5')

    def test_generate_actions_subtree_moved_under_deep_tag_before_it_is_shallowed(self) -> None:
        """
        A three-level subtree s0 > s1 > s2 is moved under c3, which is itself moved to the root.
        Attaching s0 under c3 while c3 is still at depth 3 would make s2 a seventh level.
        """
        structure = [('c0', None), ('c1', 'c0'), ('c2', 'c1'), ('c3', 'c2'), ('s0', None), ('s1', 's0'), ('s2', 's1')]
        rows = [self._row('s0', 'c3'), self._row('c3'), self._row('s1', 's0'), self._row('s2', 's1')]
        plan = self._plan_for_new_taxonomy(structure)
        for order in itertools.permutations(range(len(rows))):
            with self.subTest(order=order):
                plan.generate_actions(tags=[rows[i] for i in order], replace=False)
                self.assertEqual(plan.errors, [])
                self.assertTrue(self._passes_dry_run(plan))

    def test_generate_actions_three_level_new_chain_under_moved_deep_tag(self) -> None:
        """
        Three new tags are chained under t5, which moves to the root: all 24 row orders plan clean.
        """
        rows = [self._row('t5'), self._row('g0', 't5'), self._row('g1', 'g0'), self._row('g2', 'g1')]
        plan = self._plan_for_new_taxonomy(self._deep_chain_structure())
        for order in itertools.permutations(range(4)):
            with self.subTest(order=order):
                plan.generate_actions(tags=[rows[i] for i in order], replace=False)
                self.assertEqual(plan.errors, [])
                self.assertTrue(self._passes_dry_run(plan))

    def test_parent_dry_run_accepts_valid_and_rejects_invalid_sequences(self) -> None:
        """
        The dry run accepts a valid move, and rejects a cycle, a tree that gets too deep, and a
        reference to a tag removed by an earlier delete (a delete also removes descendants).
        """
        # A chain c0 > ... > c4 of five levels, and a root s0 with a child s1.
        tags = {
            'c0': ExistingTag(1, None, None), 'c1': ExistingTag(2, 1, 'c0'), 'c2': ExistingTag(3, 2, 'c1'),
            'c3': ExistingTag(4, 3, 'c2'), 'c4': ExistingTag(5, 4, 'c3'),
            's0': ExistingTag(6, None, None), 's1': ExistingTag(7, 6, 's0'),
        }
        taxonomy = Taxonomy()

        def update(tag_id: str, parent_id: str | None) -> UpdateParentTag:
            return UpdateParentTag(taxonomy, TagItem(id=tag_id, value='x', parent_id=parent_id), 1)

        delete = DeleteTag(taxonomy, TagItem(id='c1', value='x'), 1)
        self.assertTrue(_ParentForest(tags).apply(update('s1', 'c0')))
        self.assertFalse(_ParentForest(tags).apply(update('c0', 'c4')))
        self.assertFalse(_ParentForest(tags).apply(update('s0', 'c4')))
        forest = _ParentForest(tags)
        self.assertTrue(forest.apply(delete))
        self.assertFalse(forest.apply(update('s0', 'c2')))
        forest = _ParentForest(tags)
        self.assertTrue(forest.apply(delete))
        self.assertTrue(forest.apply(update('s0', 'c0')))

    def test_generate_actions_rebuilds_a_hazardous_plan_only_once(self) -> None:
        """
        When the dry run keeps failing, the plan is rebuilt detach-first once, checked once more,
        and reported as invalid instead of being rebuilt again.
        """
        plan = self._plan_for_new_taxonomy(self._deep_chain_structure())
        rows = [self._row('g0', 't5'), self._row('t5')]
        with mock.patch.object(TagImportPlan, '_parent_changes_are_valid', return_value=False) as dry_run:
            plan.generate_actions(tags=rows, replace=False)
        self.assertEqual(dry_run.call_count, 2)
        self.assertEqual(len(plan.errors), 1)
        first = plan.actions[0]
        self.assertEqual((first.name, first.tag.id, first.tag.parent_id), ('update_parent', 't5', None))

    def test_generate_actions_rejects_a_new_tag_below_the_maximum_depth(self) -> None:
        """
        A tag added under a tag that is already at the deepest level cannot be applied in any
        order, so the plan has the invalid hierarchy error instead of an applicable plan.
        """
        structure = [('a', None), ('b', 'a'), ('c', 'b'), ('d', 'c'), ('e', 'd'), ('f', 'e')]
        plan = self._plan_for_new_taxonomy(structure)
        rows = [self._row(tag_id, parent) for tag_id, parent in structure] + [self._row('g', 'f')]
        plan.generate_actions(tags=rows, replace=True)
        self.assertEqual(len(plan.errors), 1)
        self.assertIn('deeper than 6 levels', str(plan.errors[0]))

    def test_generate_actions_rejects_a_subtree_moved_too_deep(self) -> None:
        """
        Moving the chain w > x > y > z under d (a > b > c > d) would put z at the seventh level,
        so the plan has the invalid hierarchy error.
        """
        structure = [('a', None), ('b', 'a'), ('c', 'b'), ('d', 'c'), ('w', None), ('x', 'w'), ('y', 'x'), ('z', 'y')]
        plan = self._plan_for_new_taxonomy(structure)
        rows = [self._row(tag_id, 'd' if tag_id == 'w' else parent) for tag_id, parent in structure]
        plan.generate_actions(tags=rows, replace=True)
        self.assertEqual(len(plan.errors), 1)
        self.assertIn('deeper than 6 levels', str(plan.errors[0]))

    def test_generate_actions_swap_case_variant_of_stale_parent_id_rejected(self) -> None:
        """
        In a tag_1 <-> tag_3 swap, a child naming the stale id "tag_1" with another case is
        rejected like the exact spelling, with its row position and the new id.
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
        In the same swap, children naming the end-state ids with another case are accepted.
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
        When tag_1 is plainly renamed to tag_50, a child naming "TAG_1" gets only the parent
        validation error, not a second one for the same row.
        """
        tags = [
            TagItem(id='tag_50', value='Tag 1', previous_id='tag_1'),
            TagItem(id='tag_2', value='Tag 2', parent_id='TAG_1'),
        ]
        self.import_plan.generate_actions(tags=tags, replace=False)
        messages = [str(error) for error in self.import_plan.errors]
        self.assertEqual(len(messages), 1)
        self.assertIn('Parent tag TAG_1 is renamed to tag_50 in this file', messages[0])

    def test_generate_actions_case_only_parent_rename_with_case_variant_child_accepted(self) -> None:
        """
        Renaming tag_1 only by case keeps the id, so a child naming it in either case is accepted.
        """
        for parent_id in ('tag_1', 'Tag_1', 'TAG_1'):
            with self.subTest(parent_id=parent_id):
                tags = [
                    TagItem(id='TAG_1', value='Tag 1', previous_id='tag_1'),
                    TagItem(id='tag_2', value='Tag 2', parent_id=parent_id),
                ]
                self.import_plan.generate_actions(tags=tags, replace=False)
                self.assertEqual(self.import_plan.errors, [])

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
