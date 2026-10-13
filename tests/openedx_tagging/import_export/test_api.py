"""
Test for import/export API
"""
import csv
import itertools
import json
from collections.abc import Sequence
from contextlib import contextmanager
from io import BytesIO, StringIO

from django.db import transaction
from django.test.testcases import TestCase

import openedx_tagging.import_export.api as import_export_api
from openedx_tagging.import_export import ParserFormat
from openedx_tagging.models import ObjectTag, Tag, TagImportTask, TagImportTaskState, Taxonomy

from .mixins import TestImportExportMixin


class TestImportExportApi(TestImportExportMixin, TestCase):
    """
    Test import/export API functions
    """

    def setUp(self) -> None:
        self.tags = [
            {"id": "tag_31", "value": "Tag 31"},
            {"id": "tag_32", "value": "Tag 32"},
            {"id": "tag_33", "value": "Tag 33", "parent_id": "tag_31"},
            {"id": "tag_1", "value": "Tag 1 V2"},
            {"id": "tag_4", "value": "Tag 4", "parent_id": "tag_32"},
        ]
        json_data = {"tags": self.tags}
        self.file = BytesIO(json.dumps(json_data).encode())

        json_data = {"invalid": [
            {"id": "tag_1", "name": "Tag 1"},
        ]}
        self.invalid_parser_file = BytesIO(json.dumps(json_data).encode())
        json_data = {"tags": [
            {'id': 'tag_31', 'value': 'Tag 31'},
            {'id': 'tag_31', 'value': 'Tag 32'},
        ]}
        self.invalid_plan_file = BytesIO(json.dumps(json_data).encode())

        self.parser_format = ParserFormat.JSON

        self.open_taxonomy = Taxonomy(
            name="Open taxonomy",
            allow_free_text=True
        )
        self.read_only_taxonomy = Taxonomy(
            name="Read-only taxonomy",
            read_only=True,
        )
        return super().setUp()

    def _import_rows(self, rows: list[dict], replace: bool = False):
        """
        Import `rows` as a JSON file and return (result, log), checking the
        task log matches the last import log.
        """
        result, task, _plan = import_export_api.import_tags(
            self.taxonomy,
            BytesIO(json.dumps({"tags": rows}).encode()),
            self.parser_format,
            replace=replace,
        )
        log = import_export_api.get_last_import_log(self.taxonomy)
        assert log == task.log
        return result, log

    def _snapshot(self) -> set:
        """
        Return the (pk, external_id, parent pk) of every tag in the taxonomy.
        """
        return set(self.taxonomy.tag_set.values_list("pk", "external_id", "parent_id"))

    def test_check_status(self) -> None:
        TagImportTask.create(self.taxonomy)
        status = import_export_api.get_last_import_status(self.taxonomy)
        assert status == TagImportTaskState.LOADING_DATA

    def test_check_log(self) -> None:
        TagImportTask.create(self.taxonomy)
        log = import_export_api.get_last_import_log(self.taxonomy)
        assert "Import task created" in log

    def test_invalid_import_tags(self) -> None:
        TagImportTask.create(self.taxonomy)
        with self.assertRaises(ValueError):
            # Raise error if there is a current in progress task
            import_export_api.import_tags(
                self.taxonomy,
                self.file,
                self.parser_format,
            )

    def test_import_export_validations(self) -> None:
        # Check that import is invalid with open taxonomy
        with self.assertRaises(ValueError):
            import_export_api.import_tags(
                self.open_taxonomy,
                self.file,
                self.parser_format,
            )

        # Check that import is invalid with read-only taxonomy
        with self.assertRaises(ValueError):
            import_export_api.import_tags(
                self.read_only_taxonomy,
                self.file,
                self.parser_format,
            )

    def test_with_python_error(self) -> None:
        self.file.close()
        result, task, _plan = import_export_api.import_tags(
            self.taxonomy,
            self.file,
            self.parser_format,
        )
        assert not result
        status = import_export_api.get_last_import_status(self.taxonomy)
        log = import_export_api.get_last_import_log(self.taxonomy)
        assert status == TagImportTaskState(task.status)
        assert status == TagImportTaskState.ERROR
        assert log == task.log
        assert "ValueError('I/O operation on closed file.')" in log

    def test_with_parser_error(self) -> None:
        result, task, _plan = import_export_api.import_tags(
            self.taxonomy,
            self.invalid_parser_file,
            self.parser_format,
        )
        assert not result
        status = import_export_api.get_last_import_status(self.taxonomy)
        log = import_export_api.get_last_import_log(self.taxonomy)
        assert status == TagImportTaskState(task.status)
        assert status == TagImportTaskState.ERROR
        assert log == task.log
        assert "Starting to load data from file" in log
        assert "Invalid '.json' format" in log

    def test_with_plan_errors(self) -> None:
        result, task, _plan = import_export_api.import_tags(
            self.taxonomy,
            self.invalid_plan_file,
            self.parser_format,
        )
        assert not result
        status = import_export_api.get_last_import_status(self.taxonomy)
        log = import_export_api.get_last_import_log(self.taxonomy)
        assert status == TagImportTaskState(task.status)
        assert status == TagImportTaskState.ERROR
        assert log == task.log
        assert "Starting to load data from file" in log
        assert "Load data finished" in log
        assert "Starting plan actions" in log
        assert "Plan finished" in log
        assert "Conflict with 'create'" in log

    def test_valid(self) -> None:
        result, task, _plan = import_export_api.import_tags(
            self.taxonomy,
            self.file,
            self.parser_format,
            replace=True,
        )
        assert result
        status = import_export_api.get_last_import_status(self.taxonomy)
        log = import_export_api.get_last_import_log(self.taxonomy)
        assert status == TagImportTaskState(task.status)
        assert status == TagImportTaskState.SUCCESS
        assert log == task.log
        assert "Starting to load data from file" in log
        assert "Load data finished" in log
        assert "Starting plan actions" in log
        assert "Plan finished" in log
        assert "Starting execute actions" in log
        assert "Execution finished" in log

    def test_start_task_after_error(self) -> None:
        result, _task, _plan = import_export_api.import_tags(
            self.taxonomy,
            self.invalid_parser_file,
            self.parser_format,
        )
        assert not result
        result, _task, _plan = import_export_api.import_tags(
            self.taxonomy,
            self.file,
            self.parser_format,
        )
        assert result

    def test_start_task_after_success(self) -> None:
        result, _task, _plan = import_export_api.import_tags(
            self.taxonomy,
            self.file,
            self.parser_format,
        )
        assert result

        # Opening again the file
        json_data = {"tags": self.tags}
        self.file = BytesIO(json.dumps(json_data).encode())

        result, _task, _plan = import_export_api.import_tags(
            self.taxonomy,
            self.file,
            self.parser_format,
        )
        assert result

    def test_import_with_export_output(self) -> None:
        for parser_format in ParserFormat:
            output = import_export_api.export_tags(
                self.taxonomy,
                parser_format,
            )
            file = BytesIO(output.encode())
            new_taxonomy = Taxonomy(name="New taxonomy", export_id=f"new_taxonomy_{parser_format}")
            new_taxonomy.save()
            result, _task, _plan = import_export_api.import_tags(
                new_taxonomy,
                file,
                parser_format,
            )
            assert result
            old_tags = self.taxonomy.tag_set.all()
            assert len(old_tags) == new_taxonomy.tag_set.count()

            for tag in old_tags:
                new_tag = new_taxonomy.tag_set.get(external_id=tag.external_id)
                assert new_tag.value == tag.value
                if tag.parent:
                    assert new_tag.parent
                    assert tag.parent.external_id == new_tag.parent.external_id

    def test_reimport_after_generated_external_ids_is_a_no_op(self) -> None:
        """
        Export a taxonomy whose tags have auto-generated external_ids, then re-import
        the exact same file. The plan should report no changes at all.
        """
        self.taxonomy.add_tag("Generated Tag One")
        self.taxonomy.add_tag("Generated Tag Two", parent_tag_value="Generated Tag One")

        output = import_export_api.export_tags(self.taxonomy, self.parser_format)
        file = BytesIO(output.encode())

        result, _task, plan = import_export_api.import_tags(
            self.taxonomy,
            file,
            self.parser_format,
            replace=True,
            plan_only=True,
        )
        assert result
        assert plan is not None
        assert not plan.errors
        assert all(action.name == "without_changes" for action in plan.actions)

    def test_reimport_pre_upgrade_export_file_fails_safely(self) -> None:
        """
        A file exported before this ticket's upgrade has each tag's old integer database id
        in the `id` column instead of a real external_id. Re-importing it afterward (in ADD
        mode, not replace) must fail safely: validation errors identifying the rows it can't
        match, and no tag created, renamed, re-parented, or deleted.
        """
        tag = self.taxonomy.add_tag("Existing Tag")
        tag_count_before = self.taxonomy.tag_set.count()

        # Simulate a pre-upgrade export: `id` is an old integer PK, not `tag.external_id`.
        stale_pk = str(tag.pk)
        assert stale_pk != tag.external_id  # sanity check the simulation is realistic
        import_file = BytesIO(json.dumps({"tags": [{"id": stale_pk, "value": tag.value}]}).encode())

        result, _task, plan = import_export_api.import_tags(
            self.taxonomy,
            import_file,
            self.parser_format,
            replace=False,
            plan_only=True,
        )
        assert not result
        assert plan is not None
        assert plan.errors
        assert any("Duplicated tag value" in str(error) for error in plan.errors)
        assert self.taxonomy.tag_set.count() == tag_count_before
        # Confirm nothing was renamed either:
        tag.refresh_from_db()
        assert tag.value == "Existing Tag"

    def test_reimport_pre_upgrade_export_file_fails_safely_on_id_collision(self) -> None:
        """
        Same stale-database-id scenario as above, but the id also happens to equal a
        different tag's real, current external_id, so the row resolves to that other
        tag instead of failing to match anyone. The import still fails safely: that
        tag's value differs from the row's (Tag.value is unique per taxonomy, and the
        original tag still holds it), so a rename action also applies to it and its
        duplicate-value check rejects the whole plan.
        """
        tag = self.taxonomy.add_tag("Existing Tag")
        stale_pk = str(tag.pk)
        assert stale_pk != tag.external_id  # sanity check the simulation is realistic

        # A different, unrelated tag whose real external_id happens to equal that stale id.
        other_tag = self.taxonomy.add_tag("Unrelated Tag", external_id=stale_pk)
        tag_count_before = self.taxonomy.tag_set.count()

        import_file = BytesIO(json.dumps({"tags": [{"id": stale_pk, "value": tag.value}]}).encode())

        result, _task, plan = import_export_api.import_tags(
            self.taxonomy,
            import_file,
            self.parser_format,
            replace=False,
            plan_only=True,
        )
        assert not result
        assert plan is not None
        assert plan.errors
        assert any("Duplicated tag value" in str(error) for error in plan.errors)
        assert self.taxonomy.tag_set.count() == tag_count_before
        # Confirm the unrelated tag was not renamed or re-parented:
        other_tag.refresh_from_db()
        assert other_tag.value == "Unrelated Tag"
        assert other_tag.parent is None
        # And the original tag is also untouched:
        tag.refresh_from_db()
        assert tag.value == "Existing Tag"

    def test_import_removing_with_childs(self) -> None:
        """
        Test import need to remove childs with parents that will also be removed
        """
        new_taxonomy = Taxonomy(name="New taxonomy")
        new_taxonomy.save()
        level2 = Tag.objects.create(
            id=1000,
            external_id="tag_2",
            value="Tag 2",
            taxonomy=new_taxonomy,
        )
        level1 = Tag.objects.create(
            id=1001,
            external_id="tag_1",
            value="Tag 1",
            taxonomy=new_taxonomy,
        )
        level3 = Tag.objects.create(
            id=1002,
            external_id="tag_3",
            value="Tag 3",
            taxonomy=new_taxonomy,
        )
        level2.parent = level1
        level2.save()

        level3.parent = level3
        level3.save()

        # Import with empty tags, to remove all tags
        importFile = BytesIO(json.dumps({"tags": []}).encode())
        result, _tasks, _plan = import_export_api.import_tags(
            new_taxonomy,
            importFile,
            ParserFormat.JSON,
            replace=True,
        )
        assert result

    def test_import_removing_with_childs_no_external_id(self) -> None:
        """
        Test import need to remove childs with parents that will also be removed,
        using tags without external_id
        """
        new_taxonomy = Taxonomy(name="New taxonomy")
        new_taxonomy.save()
        level2 = Tag.objects.create(
            id=1000,
            value="Tag 2",
            taxonomy=new_taxonomy,
        )
        level1 = Tag.objects.create(
            id=1001,
            value="Tag 1",
            taxonomy=new_taxonomy,
        )
        level3 = Tag.objects.create(
            id=1002,
            value="Tag 3",
            taxonomy=new_taxonomy,
        )
        level2.parent = level1
        level2.save()

        level3.parent = level3
        level3.save()

        # Import with empty tags, to remove all tags
        importFile = BytesIO(json.dumps({"tags": []}).encode())

        result, _tasks, _plan = import_export_api.import_tags(
            new_taxonomy,
            importFile,
            ParserFormat.JSON,
            replace=True,
        )
        assert result

    def test_import_rename_external_id_preserves_pk(self) -> None:
        """
        Importing a row with a matching `previous_id` renames the tag's
        external_id in place, preserving its primary key (see ADR 0010).
        """
        old_pk = self.taxonomy.tag_set.get(external_id="tag_1").pk

        importFile = BytesIO(json.dumps({"tags": [
            {"id": "tag_50", "value": "Tag 1 Renamed", "previous_id": "tag_1"},
        ]}).encode())
        result, _task, _plan = import_export_api.import_tags(
            self.taxonomy,
            importFile,
            self.parser_format,
        )
        assert result

        renamed_tag = Tag.objects.get(pk=old_pk)
        assert renamed_tag.external_id == "tag_50"
        assert renamed_tag.value == "Tag 1 Renamed"
        assert not self.taxonomy.tag_set.filter(external_id="tag_1").exists()

    def test_import_rename_external_id_then_export(self) -> None:
        """
        A follow-up export after a rename contains the new id, and neither
        the old id nor a `previous_id` field, since `previous_id` is
        import-only and never persisted (see ADR 0010).
        """
        importFile = BytesIO(json.dumps({"tags": [
            {"id": "tag_50", "value": "Tag 1 Renamed", "previous_id": "tag_1"},
        ]}).encode())
        result, _task, _plan = import_export_api.import_tags(
            self.taxonomy,
            importFile,
            self.parser_format,
        )
        assert result

        output = import_export_api.export_tags(self.taxonomy, self.parser_format)
        exported_tags = json.loads(output).get("tags")
        exported_ids = [tag.get("id") for tag in exported_tags]
        assert "tag_50" in exported_ids
        assert "tag_1" not in exported_ids
        for tag in exported_tags:
            assert "previous_id" not in tag

    def test_import_rename_external_id_preserves_pk_csv(self) -> None:
        """
        Same as `test_import_rename_external_id_preserves_pk`, but through
        the .csv format (see ADR 0010).
        """
        old_pk = self.taxonomy.tag_set.get(external_id="tag_1").pk

        importFile = BytesIO("id,value,previous_id\ntag_50,Tag 1 Renamed,tag_1\n".encode())
        result, _task, _plan = import_export_api.import_tags(
            self.taxonomy,
            importFile,
            ParserFormat.CSV,
        )
        assert result

        renamed_tag = Tag.objects.get(pk=old_pk)
        assert renamed_tag.external_id == "tag_50"
        assert renamed_tag.value == "Tag 1 Renamed"
        assert not self.taxonomy.tag_set.filter(external_id="tag_1").exists()

    def test_import_rename_external_id_then_export_csv(self) -> None:
        """
        Same as `test_import_rename_external_id_then_export`, but via .csv:
        the export contains the new id, not the old one, and its header
        has no `previous_id` column, since it's import-only and never
        persisted (see ADR 0010).
        """
        importFile = BytesIO("id,value,previous_id\ntag_50,Tag 1 Renamed,tag_1\n".encode())
        result, _task, _plan = import_export_api.import_tags(
            self.taxonomy,
            importFile,
            ParserFormat.CSV,
        )
        assert result

        output = import_export_api.export_tags(self.taxonomy, ParserFormat.CSV)
        header = output.splitlines()[0].split(",")
        assert "previous_id" not in header

        exported_ids = [line.split(",")[0] for line in output.splitlines()[1:]]
        assert "tag_50" in exported_ids
        assert "tag_1" not in exported_ids

    def test_import_rename_external_id_survives_replace_mode(self) -> None:
        """
        Studio's taxonomy import wizard always runs with replace=True, so
        this must be verified end-to-end, not just at generate_actions()
        level (see
        test_import_plan.TestTagImportPlan.test_generate_actions_rename_external_id_replace_skips_delete
        for the plan-level check that the old id is excluded from the
        delete sweep).
        """
        old_pk = self.taxonomy.tag_set.get(external_id="tag_1").pk

        importFile = BytesIO(json.dumps({"tags": [
            {"id": "tag_50", "value": "Tag 1 Renamed", "previous_id": "tag_1"},
        ]}).encode())
        result, task, _plan = import_export_api.import_tags(
            self.taxonomy,
            importFile,
            self.parser_format,
            replace=True,
        )
        assert result
        log = import_export_api.get_last_import_log(self.taxonomy)
        assert log == task.log

        renamed_tag = Tag.objects.get(pk=old_pk)
        assert renamed_tag.external_id == "tag_50"
        assert renamed_tag.value == "Tag 1 Renamed"
        assert not self.taxonomy.tag_set.filter(external_id="tag_1").exists()

    def test_import_rename_external_id_survives_replace_mode_case_different_previous_id(self) -> None:
        """
        Regression: replace=True with a previous_id that differs from the
        stored external_id only in case ("TAG_1" vs "tag_1") must still
        protect the existing tag from the delete sweep end-to-end. Before
        the fix, the exact-case pop in generate_actions() missed this tag,
        the delete sweep queued and removed it, and the rename's own
        execute() then crashed with Tag.DoesNotExist since the pk it
        resolved at plan time no longer existed.
        """
        old_pk = self.taxonomy.tag_set.get(external_id="tag_1").pk

        importFile = BytesIO(json.dumps({"tags": [
            {"id": "tag_50", "value": "Tag 1 Renamed", "previous_id": "TAG_1"},
        ]}).encode())
        result, task, _plan = import_export_api.import_tags(
            self.taxonomy,
            importFile,
            self.parser_format,
            replace=True,
        )
        assert result
        log = import_export_api.get_last_import_log(self.taxonomy)
        assert log == task.log

        renamed_tag = Tag.objects.get(pk=old_pk)
        assert renamed_tag.external_id == "tag_50"
        assert renamed_tag.value == "Tag 1 Renamed"
        assert not self.taxonomy.tag_set.filter(external_id="tag_1").exists()

    def test_import_plain_row_replace_survives_case_different_id(self) -> None:
        """
        Regression: a plain row (no previous_id) with id="TAG_1" under
        replace=True must still protect the existing tag_1 tag from the
        delete sweep end-to-end, even though it differs from the stored
        external_id only in case. Before the fix, the exact-case
        `tag.id in tags_for_delete` check missed this tag, the delete
        sweep removed it, and tag_4's own update_parent action (an
        explicit re-parent onto "tag_1") then crashed looking up a tag
        that had already been deleted.
        """
        old_pk = self.taxonomy.tag_set.get(external_id="tag_1").pk

        importFile = BytesIO(json.dumps({"tags": [
            {"id": "TAG_1", "value": "Tag 1"},
            {"id": "tag_2", "value": "Tag 2", "parent_id": "tag_1"},
            {"id": "tag_3", "value": "Tag 3"},
            {"id": "tag_4", "value": "Tag 4", "parent_id": "tag_1"},
        ]}).encode())
        result, task, _plan = import_export_api.import_tags(
            self.taxonomy,
            importFile,
            self.parser_format,
            replace=True,
        )
        log = import_export_api.get_last_import_log(self.taxonomy)
        assert log == task.log
        assert "Traceback" not in log
        assert result

        surviving_tag = Tag.objects.get(pk=old_pk)
        assert surviving_tag.external_id == "tag_1"
        assert surviving_tag.value == "Tag 1"

        reparented_tag = self.taxonomy.tag_set.get(external_id="tag_4")
        assert reparented_tag.parent is not None
        assert reparented_tag.parent.pk == old_pk

    def test_import_rename_external_id_previous_id_equals_id_is_noop(self) -> None:
        """
        previous_id equal to id is a no-op: RenameTagExternalId.applies_for
        declines to fire (see test_actions.py), and normal update handling
        applies instead. End-to-end: re-importing a tag with previous_id
        set to its own external_id succeeds, and export still shows the
        same id.
        """
        importFile = BytesIO(json.dumps({"tags": [
            {"id": "tag_1", "value": "Tag 1", "previous_id": "tag_1"},
        ]}).encode())
        result, task, _plan = import_export_api.import_tags(
            self.taxonomy,
            importFile,
            self.parser_format,
        )
        assert result
        log = import_export_api.get_last_import_log(self.taxonomy)
        assert log == task.log
        assert "Traceback" not in log

        output = import_export_api.export_tags(self.taxonomy, self.parser_format)
        exported_tags = json.loads(output).get("tags")
        exported_ids = [tag.get("id") for tag in exported_tags]
        assert "tag_1" in exported_ids

    def test_import_rename_external_id_unmatched_previous_id_rejected(self) -> None:
        importFile = BytesIO(json.dumps({"tags": [
            {"id": "tag_50", "value": "Tag 50", "previous_id": "tag_999"},
        ]}).encode())
        result, task, _plan = import_export_api.import_tags(
            self.taxonomy,
            importFile,
            self.parser_format,
        )
        assert not result
        log = import_export_api.get_last_import_log(self.taxonomy)
        assert log == task.log
        assert "Unknown previous_id" in log
        assert not self.taxonomy.tag_set.filter(external_id="tag_50").exists()

    def test_import_rename_external_id_colliding_new_id_rejected(self) -> None:
        tag_before = self.taxonomy.tag_set.get(external_id="tag_1")
        importFile = BytesIO(json.dumps({"tags": [
            {"id": "tag_2", "value": "Tag 1", "previous_id": "tag_1"},
        ]}).encode())
        result, task, _plan = import_export_api.import_tags(
            self.taxonomy,
            importFile,
            self.parser_format,
        )
        assert not result
        log = import_export_api.get_last_import_log(self.taxonomy)
        assert log == task.log
        assert "already exists" in log

        tag_after = self.taxonomy.tag_set.get(external_id="tag_1")
        assert tag_after.pk == tag_before.pk
        assert tag_after.value == tag_before.value

    def test_import_rename_external_id_duplicate_previous_id_rejected(self) -> None:
        """
        Two rows sharing the same previous_id both target the same old tag.
        This must be rejected cleanly at the plan step, not crash at execute
        time once the first rename has already renamed the old tag away.
        """
        importFile = BytesIO(json.dumps({"tags": [
            {"id": "tag_50", "value": "Tag 50", "previous_id": "tag_1"},
            {"id": "tag_60", "value": "Tag 60", "previous_id": "tag_1"},
        ]}).encode())
        result, task, _plan = import_export_api.import_tags(
            self.taxonomy,
            importFile,
            self.parser_format,
        )
        assert not result
        log = import_export_api.get_last_import_log(self.taxonomy)
        assert log == task.log
        assert "Duplicated previous_id" in log
        assert "Traceback" not in log

        tag_after = self.taxonomy.tag_set.get(external_id="tag_1")
        assert tag_after.external_id == "tag_1"
        assert not self.taxonomy.tag_set.filter(external_id="tag_50").exists()
        assert not self.taxonomy.tag_set.filter(external_id="tag_60").exists()

    def test_import_rename_external_id_reuses_id_freed_by_replace_delete(self) -> None:
        """
        Replace-mode import that omits tag_1 (queuing it for deletion) and
        renames tag_2 onto id="tag_1" in the same file, reusing the id
        tag_1's deletion is about to free. Must succeed end-to-end: tag_1
        still being physically present (though queued for deletion) at
        validate time must not count as a collision.

        The new value and parent_id deliberately differ from tag_1's
        current ones: with matching values, RenameTag/UpdateParentTag's
        DB-only lookups would fire instead and pass even without this fix,
        proving nothing. tag_3 gets its own no-op row so it survives as a
        valid parent target, rather than being swept up by the same delete.
        """
        old_tag_1_pk = self.taxonomy.tag_set.get(external_id="tag_1").pk
        old_tag_2_pk = self.taxonomy.tag_set.get(external_id="tag_2").pk

        importFile = BytesIO(json.dumps({"tags": [
            {"id": "tag_1", "value": "Renamed From Tag 2", "previous_id": "tag_2", "parent_id": "tag_3"},
            {"id": "tag_3", "value": "Tag 3"},
        ]}).encode())
        result, task, _plan = import_export_api.import_tags(
            self.taxonomy,
            importFile,
            self.parser_format,
            replace=True,
        )
        log = import_export_api.get_last_import_log(self.taxonomy)
        assert log == task.log
        assert "Traceback" not in log
        assert "Duplicated tag value" not in log
        assert result

        # tag_1's old row was genuinely deleted, not merely renamed away.
        assert not Tag.objects.filter(pk=old_tag_1_pk).exists()

        # tag_2 is the same underlying row, now wearing tag_1's freed-up id,
        # with the row's OWN new value and parent, not tag_1's old ones:
        # proof that RenameTag/UpdateParentTag did not sneak in and mutate
        # the doomed tag_1 before it got deleted.
        renamed_tag = Tag.objects.get(pk=old_tag_2_pk)
        assert renamed_tag.external_id == "tag_1"
        assert renamed_tag.value == "Renamed From Tag 2"
        assert renamed_tag.parent is not None
        assert renamed_tag.parent.external_id == "tag_3"

    def test_import_rename_parent_and_child_both_renamed(self) -> None:
        """
        A parent tag and its child are both renamed in the same import,
        with the child's parent_id explicitly set to the parent's NEW id.
        Must apply cleanly end-to-end, with the child correctly re-parented
        under the renamed parent.
        """
        old_pk_1 = self.taxonomy.tag_set.get(external_id="tag_1").pk
        old_pk_2 = self.taxonomy.tag_set.get(external_id="tag_2").pk

        importFile = BytesIO(json.dumps({"tags": [
            {"id": "tag_10", "value": "Tag 1 Renamed", "previous_id": "tag_1"},
            {"id": "tag_20", "value": "Tag 2 Renamed", "previous_id": "tag_2", "parent_id": "tag_10"},
        ]}).encode())
        result, task, _plan = import_export_api.import_tags(
            self.taxonomy,
            importFile,
            self.parser_format,
        )
        log = import_export_api.get_last_import_log(self.taxonomy)
        assert log == task.log
        assert "Traceback" not in log
        assert result

        parent_tag = Tag.objects.get(pk=old_pk_1)
        child_tag = Tag.objects.get(pk=old_pk_2)
        assert parent_tag.external_id == "tag_10"
        assert child_tag.external_id == "tag_20"
        assert child_tag.parent is not None
        assert child_tag.parent.pk == parent_tag.pk

    def test_import_rename_parent_and_child_both_renamed_replace_mode(self) -> None:
        """
        Same scenario as test_import_rename_parent_and_child_both_renamed,
        but with replace=True: the delete sweep must not interfere with the
        parent/child rename, since both are protected by previous_id.
        """
        old_pk_1 = self.taxonomy.tag_set.get(external_id="tag_1").pk
        old_pk_2 = self.taxonomy.tag_set.get(external_id="tag_2").pk

        importFile = BytesIO(json.dumps({"tags": [
            {"id": "tag_10", "value": "Tag 1 Renamed", "previous_id": "tag_1"},
            {"id": "tag_20", "value": "Tag 2 Renamed", "previous_id": "tag_2", "parent_id": "tag_10"},
        ]}).encode())
        result, task, _plan = import_export_api.import_tags(
            self.taxonomy,
            importFile,
            self.parser_format,
            replace=True,
        )
        log = import_export_api.get_last_import_log(self.taxonomy)
        assert log == task.log
        assert "Traceback" not in log
        assert result

        parent_tag = Tag.objects.get(pk=old_pk_1)
        child_tag = Tag.objects.get(pk=old_pk_2)
        assert parent_tag.external_id == "tag_10"
        assert child_tag.external_id == "tag_20"
        assert child_tag.parent is not None
        assert child_tag.parent.pk == parent_tag.pk

    def test_import_swap_external_ids(self) -> None:
        """
        A 2-tag swap (tag_1 <-> tag_3, both root tags so parent handling
        doesn't complicate the assertions) has no valid plain execution
        order: either rename collides with the DB's per-statement unique
        constraint on (taxonomy, external_id). Each tag must be staged
        through a placeholder id first (see ADR 0010 amendment).
        """
        old_pk_1 = self.taxonomy.tag_set.get(external_id="tag_1").pk
        old_pk_3 = self.taxonomy.tag_set.get(external_id="tag_3").pk

        importFile = BytesIO(json.dumps({"tags": [
            {"id": "tag_3", "value": "Tag 1", "previous_id": "tag_1"},
            {"id": "tag_1", "value": "Tag 3", "previous_id": "tag_3"},
        ]}).encode())
        result, task, _plan = import_export_api.import_tags(
            self.taxonomy,
            importFile,
            self.parser_format,
        )
        log = import_export_api.get_last_import_log(self.taxonomy)
        assert log == task.log
        assert "Traceback" not in log
        assert result

        # Both tags keep their original pks: this was a rename, not a
        # delete-and-recreate.
        tag_1 = Tag.objects.get(pk=old_pk_1)
        tag_3 = Tag.objects.get(pk=old_pk_3)
        assert tag_1.external_id == "tag_3"
        assert tag_1.value == "Tag 1"
        assert tag_3.external_id == "tag_1"
        assert tag_3.value == "Tag 3"

        output = import_export_api.export_tags(self.taxonomy, self.parser_format)
        exported_tags = json.loads(output).get("tags")
        for tag in exported_tags:
            assert not tag.get("id", "").startswith("oel-import-staging:")
        exported_by_value = {tag["value"]: tag["id"] for tag in exported_tags}
        assert exported_by_value["Tag 1"] == "tag_3"
        assert exported_by_value["Tag 3"] == "tag_1"

    def test_import_three_cycle_external_ids(self) -> None:
        """
        End-to-end 3-cycle: tag_1 -> tag_2 -> tag_3 -> tag_1. Same staging
        mechanism as a 2-tag swap, generalized to any cycle length.
        """
        old_pk_1 = self.taxonomy.tag_set.get(external_id="tag_1").pk
        old_pk_2 = self.taxonomy.tag_set.get(external_id="tag_2").pk
        old_pk_3 = self.taxonomy.tag_set.get(external_id="tag_3").pk

        importFile = BytesIO(json.dumps({"tags": [
            {"id": "tag_2", "value": "Tag 1", "previous_id": "tag_1"},
            {"id": "tag_3", "value": "Tag 2", "previous_id": "tag_2"},
            {"id": "tag_1", "value": "Tag 3", "previous_id": "tag_3"},
        ]}).encode())
        result, task, _plan = import_export_api.import_tags(
            self.taxonomy,
            importFile,
            self.parser_format,
        )
        log = import_export_api.get_last_import_log(self.taxonomy)
        assert log == task.log
        assert "Traceback" not in log
        assert result

        assert Tag.objects.get(pk=old_pk_1).external_id == "tag_2"
        assert Tag.objects.get(pk=old_pk_2).external_id == "tag_3"
        assert Tag.objects.get(pk=old_pk_3).external_id == "tag_1"

        output = import_export_api.export_tags(self.taxonomy, self.parser_format)
        exported_tags = json.loads(output).get("tags")
        for tag in exported_tags:
            assert not tag.get("id", "").startswith("oel-import-staging:")

    def test_import_swap_external_ids_with_colliding_values_rejected(self) -> None:
        """
        A contended external_id swap where each row also takes the other
        tag's value: must cleanly reject, not raise an IntegrityError.
        Value swaps are an explicit, documented limitation (see ADR 0010
        amendment): (taxonomy, value) has the same unique-constraint shape
        as (taxonomy, external_id), but staging is only implemented for
        external_id.
        """
        old_pk_1 = self.taxonomy.tag_set.get(external_id="tag_1").pk
        old_pk_3 = self.taxonomy.tag_set.get(external_id="tag_3").pk

        importFile = BytesIO(json.dumps({"tags": [
            {"id": "tag_3", "value": "Tag 3", "previous_id": "tag_1"},
            {"id": "tag_1", "value": "Tag 1", "previous_id": "tag_3"},
        ]}).encode())
        result, task, _plan = import_export_api.import_tags(
            self.taxonomy,
            importFile,
            self.parser_format,
        )
        log = import_export_api.get_last_import_log(self.taxonomy)
        assert log == task.log
        assert "Traceback" not in log
        assert "Duplicated tag value" in log
        assert not result

        # Nothing changed: neither tag's external_id or value moved.
        tag_1 = Tag.objects.get(pk=old_pk_1)
        tag_3 = Tag.objects.get(pk=old_pk_3)
        assert tag_1.external_id == "tag_1"
        assert tag_1.value == "Tag 1"
        assert tag_3.external_id == "tag_3"
        assert tag_3.value == "Tag 3"

    def test_import_duplicate_final_id_rejected(self) -> None:
        """
        Two rows can't claim the same final id: a tag_1<->tag_3 swap plus
        an unrelated third row also targeting id=tag_1 is ambiguous. Must
        reject outright at the plan step, not resolve by row order
        (previously: a silent overwrite or an uncaught crash, depending on
        which row came first).
        """
        old_pk_1 = self.taxonomy.tag_set.get(external_id="tag_1").pk
        old_pk_3 = self.taxonomy.tag_set.get(external_id="tag_3").pk

        importFile = BytesIO(json.dumps({"tags": [
            {"id": "tag_3", "value": "Tag 1", "previous_id": "tag_1"},
            {"id": "tag_1", "value": "Tag 3", "previous_id": "tag_3"},
            {"id": "tag_1", "value": "Something Else Entirely"},
        ]}).encode())
        result, task, _plan = import_export_api.import_tags(
            self.taxonomy,
            importFile,
            self.parser_format,
        )
        log = import_export_api.get_last_import_log(self.taxonomy)
        assert log == task.log
        assert "Traceback" not in log
        assert "Duplicate id" in log
        assert not result

        # Nothing changed: neither tag's external_id or value moved.
        tag_1 = Tag.objects.get(pk=old_pk_1)
        tag_3 = Tag.objects.get(pk=old_pk_3)
        assert tag_1.external_id == "tag_1"
        assert tag_1.value == "Tag 1"
        assert tag_3.external_id == "tag_3"
        assert tag_3.value == "Tag 3"

    def test_import_duplicate_final_id_rejected_regardless_of_order(self) -> None:
        """
        Same collision as test_import_duplicate_final_id_rejected, with
        the unrelated row moved to the front: rejection must not depend on
        row order. Previously this ordering hit an uncaught
        Tag.DoesNotExist crash at execute time instead of a clean
        plan-time rejection.
        """
        old_pk_1 = self.taxonomy.tag_set.get(external_id="tag_1").pk
        old_pk_3 = self.taxonomy.tag_set.get(external_id="tag_3").pk

        importFile = BytesIO(json.dumps({"tags": [
            {"id": "tag_1", "value": "Something Else Entirely"},
            {"id": "tag_3", "value": "Tag 1", "previous_id": "tag_1"},
            {"id": "tag_1", "value": "Tag 3", "previous_id": "tag_3"},
        ]}).encode())
        result, task, _plan = import_export_api.import_tags(
            self.taxonomy,
            importFile,
            self.parser_format,
        )
        log = import_export_api.get_last_import_log(self.taxonomy)
        assert log == task.log
        assert "Traceback" not in log
        assert "Duplicate id" in log
        assert not result

        tag_1 = Tag.objects.get(pk=old_pk_1)
        tag_3 = Tag.objects.get(pk=old_pk_3)
        assert tag_1.external_id == "tag_1"
        assert tag_1.value == "Tag 1"
        assert tag_3.external_id == "tag_3"
        assert tag_3.value == "Tag 3"

    def test_import_duplicate_final_id_rejected_case_insensitive(self) -> None:
        """
        Two rows claiming the same final id in different case ("tag_50" and
        "TAG_50") must be rejected as a duplicate: external_id is
        case-insensitive at the DB layer (NOCASE / utf8mb4_unicode_ci), so
        these collide even though the Python-side strings differ.
        """
        importFile = BytesIO(json.dumps({"tags": [
            {"id": "tag_50", "value": "Tag 1 Renamed", "previous_id": "tag_1"},
            {"id": "TAG_50", "value": "Tag 3 Renamed", "previous_id": "tag_3"},
        ]}).encode())
        result, task, _plan = import_export_api.import_tags(
            self.taxonomy,
            importFile,
            self.parser_format,
        )
        log = import_export_api.get_last_import_log(self.taxonomy)
        assert log == task.log
        assert "Traceback" not in log
        assert "Duplicate id" in log
        assert not result

        # Nothing changed: neither tag was renamed.
        tag_1 = self.taxonomy.tag_set.get(external_id="tag_1")
        tag_3 = self.taxonomy.tag_set.get(external_id="tag_3")
        assert tag_1.value == "Tag 1"
        assert tag_3.value == "Tag 3"

    def test_import_plain_row_targets_vacated_id_rejected(self) -> None:
        """
        A plain row (no previous_id) with id="tag_1", alongside a different
        row renaming "tag_1" away (previous_id="tag_1", id="tag_50"), must be
        rejected at the plan step: the plain row's id would otherwise resolve
        to the very tag the other row is renaming away from, not to a
        distinct tag that happens to share that id.
        """
        importFile = BytesIO(json.dumps({"tags": [
            {"id": "tag_50", "value": "Tag 1", "previous_id": "tag_1"},
            {"id": "tag_1", "value": "Brand New"},
        ]}).encode())
        result, task, _plan = import_export_api.import_tags(
            self.taxonomy,
            importFile,
            self.parser_format,
        )
        log = import_export_api.get_last_import_log(self.taxonomy)
        assert log == task.log
        assert "Traceback" not in log
        assert "is renamed away by row" in log
        assert not result

        tag_1 = self.taxonomy.tag_set.get(external_id="tag_1")
        assert tag_1.value == "Tag 1"
        assert not self.taxonomy.tag_set.filter(external_id="tag_50").exists()

    def test_import_plain_row_targets_vacated_id_rejected_regardless_of_order(self) -> None:
        """
        Same collision as test_import_plain_row_targets_vacated_id_rejected,
        with the plain row moved to the front of the file: rejection must
        not depend on row order.
        """
        importFile = BytesIO(json.dumps({"tags": [
            {"id": "tag_1", "value": "Brand New"},
            {"id": "tag_50", "value": "Tag 1", "previous_id": "tag_1"},
        ]}).encode())
        result, task, _plan = import_export_api.import_tags(
            self.taxonomy,
            importFile,
            self.parser_format,
        )
        log = import_export_api.get_last_import_log(self.taxonomy)
        assert log == task.log
        assert "Traceback" not in log
        assert "is renamed away by row" in log
        assert not result

        tag_1 = self.taxonomy.tag_set.get(external_id="tag_1")
        assert tag_1.value == "Tag 1"
        assert not self.taxonomy.tag_set.filter(external_id="tag_50").exists()

    def test_import_rename_referencing_stale_old_id_rejected(self) -> None:
        """
        Regression: a plain rename of tag_1 to tag_50, with a different
        row's parent_id referencing tag_1's OLD id, must be rejected at
        the plan step, not crash at execute time. The rename comes first
        in the file, so an accepted stale reference would hit an uncaught
        Tag.DoesNotExist once no tag holds "tag_1" any more.
        """
        importFile = BytesIO(json.dumps({"tags": [
            {"id": "tag_50", "value": "Tag 1", "previous_id": "tag_1"},
            {"id": "tag_60", "value": "Tag 60", "parent_id": "tag_1"},
        ]}).encode())
        result, task, _plan = import_export_api.import_tags(
            self.taxonomy,
            importFile,
            self.parser_format,
        )
        assert not result
        log = import_export_api.get_last_import_log(self.taxonomy)
        assert log == task.log
        assert "Parent tag tag_1 is renamed to tag_50 in this file; use tag_50 as the parent_id." in log
        assert "Traceback" not in log

        assert self.taxonomy.tag_set.filter(external_id="tag_1").exists()
        assert not self.taxonomy.tag_set.filter(external_id="tag_50").exists()
        assert not self.taxonomy.tag_set.filter(external_id="tag_60").exists()

    def test_import_existing_child_names_renamed_away_parent_rejected(self) -> None:
        """
        An existing child (tag_2 under tag_1) that keeps parent_id="tag_1"
        while the file renames tag_1 to tag_50 is rejected in either row
        order, and neither the taxonomy nor its export changes.
        """
        rename = {"id": "tag_50", "value": "Tag 1", "previous_id": "tag_1"}
        child = {"id": "tag_2", "value": "Tag 2", "parent_id": "tag_1"}
        snapshot_before = self._snapshot()
        export_before = import_export_api.export_tags(self.taxonomy, self.parser_format)
        for rows in ([rename, child], [child, rename]):
            with self.subTest(first=rows[0]["id"]):
                result, log = self._import_rows(rows)
                assert not result
                assert f"Row {rows.index(child) + 1}'s parent_id (tag_1) names an id this file renames away." in log
                assert "Use 'tag_50' as the parent_id." in log
                assert "Traceback" not in log

                assert self._snapshot() == snapshot_before
                assert import_export_api.export_tags(self.taxonomy, self.parser_format) == export_before

    def test_import_child_and_renamed_parent_row_claiming_freed_id(self) -> None:
        """
        tag_3 is renamed to tag_1, an id the same replace=True import frees by
        omitting its holder. A child row naming tag_1 succeeds in either row
        order: the renamed tag keeps its pk, the old holder is gone, and the
        child is nested under the renamed tag.
        """
        pk_1 = self.taxonomy.tag_set.get(external_id="tag_1").pk
        pk_3 = self.taxonomy.tag_set.get(external_id="tag_3").pk
        child = {"id": "tag_4", "value": "Tag 4", "parent_id": "tag_1"}
        rename = {"id": "tag_1", "value": "Tag 3", "previous_id": "tag_3"}
        for rows in ([child, rename], [rename, child]):
            with self.subTest(first=rows[0]["id"]), transaction.atomic():
                result, log = self._import_rows(rows, replace=True)
                assert "Traceback" not in log
                assert result

                assert Tag.objects.get(pk=pk_3).external_id == "tag_1"
                assert not Tag.objects.filter(pk=pk_1).exists()
                assert self.taxonomy.tag_set.get(external_id="tag_4").parent_id == pk_3
                transaction.set_rollback(True)

    def test_import_swap_with_children_in_any_row_order(self) -> None:
        """
        The swap with children on end-state ids gives the same result in
        every one of the 24 row orders.
        """
        pk_1 = self.taxonomy.tag_set.get(external_id="tag_1").pk
        pk_2 = self.taxonomy.tag_set.get(external_id="tag_2").pk
        pk_3 = self.taxonomy.tag_set.get(external_id="tag_3").pk
        pk_4 = self.taxonomy.tag_set.get(external_id="tag_4").pk
        rows = [
            {"id": "tag_1", "value": "Tag 3", "previous_id": "tag_3"},
            {"id": "tag_3", "value": "Tag 1", "previous_id": "tag_1"},
            {"id": "tag_2", "value": "Tag 2", "parent_id": "tag_3"},
            {"id": "tag_4", "value": "Tag 4", "parent_id": "tag_1"},
        ]
        for order in itertools.permutations(range(4)):
            with self.subTest(order=order), transaction.atomic():
                result, log = self._import_rows([rows[i] for i in order], replace=True)
                assert "Traceback" not in log
                assert result

                assert Tag.objects.get(pk=pk_1).external_id == "tag_3"
                assert Tag.objects.get(pk=pk_3).external_id == "tag_1"
                assert Tag.objects.get(pk=pk_2).parent_id == pk_1
                assert Tag.objects.get(pk=pk_4).parent_id == pk_3

                output = import_export_api.export_tags(self.taxonomy, self.parser_format)
                exported_tags = json.loads(output).get("tags")
                for tag in exported_tags:
                    assert not tag.get("id", "").startswith("oel-import-staging:")
                exported_by_id = {tag["id"]: tag for tag in exported_tags}
                assert exported_by_id["tag_2"]["parent_id"] == "tag_3"
                assert exported_by_id["tag_4"]["parent_id"] == "tag_1"
                transaction.set_rollback(True)

    def test_import_swap_children_stale_ids_rejected_in_any_row_order(self) -> None:
        """
        Children naming the stale pre-import ids are rejected in every one of
        the 24 row orders, each error reports the row's file position, and
        the taxonomy is unchanged.
        """
        rows = [
            {"id": "tag_1", "value": "Tag 3", "previous_id": "tag_3"},
            {"id": "tag_3", "value": "Tag 1", "previous_id": "tag_1"},
            {"id": "tag_2", "value": "Tag 2", "parent_id": "tag_1"},
            {"id": "tag_4", "value": "Tag 4", "parent_id": "tag_3"},
        ]
        before = self._snapshot()
        new_ids = {"tag_2": ("tag_1", "tag_3"), "tag_4": ("tag_3", "tag_1")}
        for order in itertools.permutations(range(4)):
            with self.subTest(order=order):
                file_rows = [rows[i] for i in order]
                result, log = self._import_rows(file_rows, replace=True)
                assert not result
                assert "Traceback" not in log
                for position, row in enumerate(file_rows, start=1):
                    if row["id"] in new_ids:
                        stale_id, new_id = new_ids[row["id"]]
                        assert f"Row {position}'s parent_id ({stale_id}) names an id this file renames away." in log
                        assert f"Use '{new_id}' as the parent_id." in log
                assert self._snapshot() == before

    def test_import_child_of_invalid_definer_row_rejected_in_any_order(self) -> None:
        """
        A child whose parent_id names a rename row with an unmatched
        previous_id, or a new-tag row with a duplicate value, is rejected
        cleanly in either row order and leaves the taxonomy unchanged.
        """
        cases = {
            "unmatched previous_id": (
                {"id": "tag_90", "value": "Tag 90", "previous_id": "tag_99"},
                "Unknown previous_id (tag_99). No tag with that external_id exists in this taxonomy.",
            ),
            "duplicate value": ({"id": "tag_90", "value": "Tag 1"}, None),
        }
        child = {"id": "tag_91", "value": "Tag 91", "parent_id": "tag_90"}
        before = self._snapshot()
        for name, (definer, cause) in cases.items():
            for rows in ([definer, child], [child, definer]):
                with self.subTest(case=name, first=rows[0]["id"]):
                    result, log = self._import_rows(rows)
                    assert not result
                    assert "Traceback" not in log
                    assert "Output errors" in log
                    if cause:
                        assert cause in log
                    assert self._snapshot() == before

    def test_import_cyclic_parent_ids_rejected(self) -> None:
        """
        Two new tags naming each other as parent are rejected with an unknown
        parent error, with and without replace, and nothing is created.
        """
        rows = [
            {"id": "tag_90", "value": "Tag 90", "parent_id": "tag_91"},
            {"id": "tag_91", "value": "Tag 91", "parent_id": "tag_90"},
        ]
        before = self._snapshot()
        for replace in (False, True):
            with self.subTest(replace=replace):
                result, log = self._import_rows(rows, replace=replace)
                assert not result
                assert "Unknown parent tag" in log
                assert "Traceback" not in log
                assert self._snapshot() == before

    def test_import_child_of_new_row_with_value_freed_by_replace(self) -> None:
        """
        With replace=True, a new row reusing the value of an existing tag the
        file omits is accepted in every row order, because the replace-delete
        frees the value, and its child is nested under it. If the file keeps
        the existing tag, the same value is a real duplicate and is rejected.
        """
        definer = {"id": "tag_90", "value": "Tag 1"}
        child = {"id": "tag_91", "value": "Tag 91", "parent_id": "tag_90"}
        kept = {"id": "tag_1", "value": "Tag 1"}
        before = self._snapshot()
        for order in itertools.permutations(range(2)):
            with self.subTest(case="omitted", order=order), transaction.atomic():
                result, log = self._import_rows([[definer, child][i] for i in order], replace=True)
                assert "Traceback" not in log
                assert result
                parent = self.taxonomy.tag_set.get(external_id="tag_90")
                assert self.taxonomy.tag_set.get(external_id="tag_91").parent_id == parent.pk
                transaction.set_rollback(True)
        for order in itertools.permutations(range(3)):
            with self.subTest(case="kept", order=order):
                result, log = self._import_rows([[definer, child, kept][i] for i in order], replace=True)
                assert not result
                assert "Traceback" not in log
                assert "Output errors" in log
                assert self._snapshot() == before

    def test_import_longer_and_mixed_parent_cycles_rejected_in_any_row_order(self) -> None:
        """
        A three-tag cycle of new tags, and a cycle through a rename row (the
        rename row's parent_id names a new tag whose parent_id names the
        rename row's new id), are rejected cleanly in every row order and
        leave the taxonomy unchanged.
        """
        cases = {
            "three new tags": [
                {"id": "tag_90", "value": "Tag 90", "parent_id": "tag_91"},
                {"id": "tag_91", "value": "Tag 91", "parent_id": "tag_92"},
                {"id": "tag_92", "value": "Tag 92", "parent_id": "tag_90"},
            ],
            "rename row and new tag": [
                {"id": "tag_50", "value": "Tag 1", "previous_id": "tag_1", "parent_id": "tag_90"},
                {"id": "tag_90", "value": "Tag 90", "parent_id": "tag_50"},
            ],
        }
        before = self._snapshot()
        for name, rows in cases.items():
            for order in itertools.permutations(range(len(rows))):
                with self.subTest(case=name, order=order):
                    result, log = self._import_rows([rows[i] for i in order])
                    assert not result
                    assert "Traceback" not in log
                    assert "Output errors" in log
                    assert self._snapshot() == before

    def test_import_parent_cycles_through_existing_tags_rejected(self) -> None:
        """
        A cycle that includes an existing tag is rejected once, in either row
        order, and leaves the taxonomy unchanged: an existing and a new tag as
        each other's parent, a rename row and an existing tag, a self-parent, and a cycle through tag_2, which
        is a child of tag_1 and not in the file.
        """
        cases = {
            "existing and new tag": (
                [
                    {"id": "tag_2", "value": "Tag 2", "parent_id": "tag_90"},
                    {"id": "tag_90", "value": "Tag 90", "parent_id": "tag_2"},
                ],
                "creates a parent cycle.",
            ),
            "self parent": (
                [{"id": "tag_2", "value": "Tag 2", "parent_id": "tag_2"}],
                "Row 1's parent_id (tag_2) creates a parent cycle.",
            ),
            "rename row and existing tag": (
                [
                    {"id": "tag_50", "value": "Tag 1", "previous_id": "tag_1", "parent_id": "tag_2"},
                    {"id": "tag_2", "value": "Tag 2", "parent_id": "tag_50"},
                ],
                "creates a parent cycle.",
            ),
            "through a tag not in the file": (
                [{"id": "tag_1", "value": "Tag 1", "parent_id": "tag_2"}],
                "Row 1's parent_id (tag_2) creates a parent cycle.",
            ),
        }
        before = self._snapshot()
        for name, (rows, message) in cases.items():
            for order in itertools.permutations(range(len(rows))):
                with self.subTest(case=name, order=order):
                    result, log = self._import_rows([rows[i] for i in order])
                    assert not result
                    assert "Traceback" not in log
                    assert log.count(message) == 1
                    assert self._snapshot() == before

    def test_import_existing_tag_moved_under_later_new_parent(self) -> None:
        """
        An existing tag moved under a new parent defined later in the file is
        accepted, and the tag ends up under the new parent.
        """
        result, log = self._import_rows([
            {"id": "tag_2", "value": "Tag 2", "parent_id": "tag_90"},
            {"id": "tag_90", "value": "Tag 90"},
        ])
        assert result
        assert "Traceback" not in log
        parent = self.taxonomy.tag_set.get(external_id="tag_90")
        assert self.taxonomy.tag_set.get(external_id="tag_2").parent_id == parent.pk

    def test_import_swap_rename_child_stale_parent_id_rejected_once(self) -> None:
        """
        In a tag_1 <-> tag_3 swap, a rename row (tag_2 -> tag_20) naming the
        stale parent id tag_1 is rejected, and the error appears exactly once.
        """
        before = self._snapshot()
        result, log = self._import_rows([
            {"id": "tag_3", "value": "Tag 1", "previous_id": "tag_1"},
            {"id": "tag_1", "value": "Tag 3", "previous_id": "tag_3"},
            {"id": "tag_20", "value": "Tag 2", "previous_id": "tag_2", "parent_id": "tag_1"},
        ])
        assert not result
        assert "Traceback" not in log
        assert log.count("Row 3's parent_id (tag_1) names an id this file renames away.") == 1
        assert self._snapshot() == before

    def test_import_rename_child_stale_parent_id_without_swap_reported_once(self) -> None:
        """
        Without a swap, a rename row (tag_2 -> tag_20) naming the stale parent
        id tag_1 gets only the rename action's error, once.
        """
        before = self._snapshot()
        result, log = self._import_rows([
            {"id": "tag_50", "value": "Tag 1", "previous_id": "tag_1"},
            {"id": "tag_20", "value": "Tag 2", "previous_id": "tag_2", "parent_id": "tag_1"},
        ])
        assert not result
        assert "Traceback" not in log
        assert log.count("Parent tag tag_1 is renamed to tag_50 in this file; use tag_50 as the parent_id.") == 1
        assert "names an id this file renames away" not in log
        assert self._snapshot() == before

    def test_import_case_only_parent_rename_keeps_child_parent(self) -> None:
        """
        Renaming a parent only by case succeeds, and a child that keeps the
        old casing in parent_id stays under the same parent.
        """
        pk_1 = self.taxonomy.tag_set.get(external_id="tag_1").pk
        pk_2 = self.taxonomy.tag_set.get(external_id="tag_2").pk
        result, log = self._import_rows([
            {"id": "TAG_1", "value": "Tag 1", "previous_id": "tag_1"},
            {"id": "tag_2", "value": "Tag 2", "parent_id": "tag_1"},
        ])
        assert result
        assert "Traceback" not in log
        assert Tag.objects.get(pk=pk_1).external_id == "TAG_1"
        assert Tag.objects.get(pk=pk_2).parent_id == pk_1

    def test_import_new_child_before_new_parent_row(self) -> None:
        """
        A new child row listed before its new parent row succeeds, the child
        is nested under the new parent, and the export shows its parent_id.
        """
        result, log = self._import_rows([
            {"id": "tag_91", "value": "Tag 91", "parent_id": "tag_90"},
            {"id": "tag_90", "value": "Tag 90"},
        ])
        assert result
        assert "Traceback" not in log
        parent = self.taxonomy.tag_set.get(external_id="tag_90")
        assert self.taxonomy.tag_set.get(external_id="tag_91").parent_id == parent.pk

        output = import_export_api.export_tags(self.taxonomy, self.parser_format)
        exported_by_id = {tag["id"]: tag for tag in json.loads(output).get("tags")}
        assert exported_by_id["tag_91"]["parent_id"] == "tag_90"

    def test_import_child_first_references_plain_rename_new_id(self) -> None:
        """
        A new child row listed before the plain rename (tag_1 -> tag_50) of
        its parent, and naming the new id, succeeds and is nested under the
        renamed tag.
        """
        pk_1 = self.taxonomy.tag_set.get(external_id="tag_1").pk
        result, log = self._import_rows([
            {"id": "tag_60", "value": "Tag 60", "parent_id": "tag_50"},
            {"id": "tag_50", "value": "Tag 1", "previous_id": "tag_1"},
        ])
        assert result
        assert "Traceback" not in log
        assert Tag.objects.get(pk=pk_1).external_id == "tag_50"
        assert self.taxonomy.tag_set.get(external_id="tag_60").parent_id == pk_1

    def test_import_plain_and_rename_children_of_renamed_parent_in_reverse_order(self) -> None:
        """
        A plain child and a rename-row child both naming the renamed parent's
        new id, listed before the parent's rename row, succeed and end up
        under the renamed parent.
        """
        pk_1 = self.taxonomy.tag_set.get(external_id="tag_1").pk
        pk_2 = self.taxonomy.tag_set.get(external_id="tag_2").pk
        result, log = self._import_rows([
            {"id": "tag_20", "value": "Tag 2", "previous_id": "tag_2", "parent_id": "tag_50"},
            {"id": "tag_60", "value": "Tag 60", "parent_id": "tag_50"},
            {"id": "tag_50", "value": "Tag 1", "previous_id": "tag_1"},
        ])
        assert result
        assert "Traceback" not in log
        assert Tag.objects.get(pk=pk_1).external_id == "tag_50"
        assert Tag.objects.get(pk=pk_2).external_id == "tag_20"
        assert Tag.objects.get(pk=pk_2).parent_id == pk_1
        assert self.taxonomy.tag_set.get(external_id="tag_60").parent_id == pk_1

    def test_import_same_value_without_external_id(self) -> None:
        new_taxonomy = Taxonomy(name="New taxonomy")
        new_taxonomy.save()

        # Tag with no external_id
        Tag.objects.create(
            value="same_value",
            taxonomy=new_taxonomy,
        )

        # Import with one tag with the same value
        importFile = BytesIO(json.dumps({"tags": [{"id": "imported_tag", "value": "same_value"}]}).encode())

        result, _tasks, _plan = import_export_api.import_tags(
            new_taxonomy,
            importFile,
            ParserFormat.JSON,
            replace=True,
        )
        assert result


def _row(tag_id: str, value: str, parent_id: str | None = None, previous_id: str | None = None) -> dict:
    """
    Build an import row, leaving out the optional fields that are not set.
    """
    row = {"id": tag_id, "value": value}
    if parent_id:
        row["parent_id"] = parent_id
    if previous_id:
        row["previous_id"] = previous_id
    return row


class TestImportAcceptanceScenarios(TestCase):
    """
    The acceptance scenarios of the external_id rename import (#673, #858), run the way the
    Studio import wizard does: a full replace import of a CSV or JSON file, checked through
    the import log and the exported file.
    """

    formats = (ParserFormat.JSON, ParserFormat.CSV)
    taxonomy: Taxonomy

    @classmethod
    def setUpTestData(cls) -> None:
        super().setUpTestData()
        cls.taxonomy = Taxonomy.objects.create(name="Competencies")

    def _render(self, rows: list[dict], parser_format: ParserFormat) -> BytesIO:
        """
        Render `rows` as an import file of the given format.
        """
        if parser_format == ParserFormat.JSON:
            return BytesIO(json.dumps({"tags": rows}).encode())
        buffer = StringIO()
        writer = csv.DictWriter(buffer, fieldnames=["id", "value", "parent_id", "previous_id"])
        writer.writeheader()
        writer.writerows(rows)
        return BytesIO(buffer.getvalue().encode())

    def _import(self, rows: list[dict], parser_format: ParserFormat, plan_only: bool = False):
        """
        Run a full replace import and return (result, log, plan).
        """
        result, task, plan = import_export_api.import_tags(
            self.taxonomy,
            self._render(rows, parser_format),
            parser_format,
            replace=True,
            plan_only=plan_only,
        )
        log = import_export_api.get_last_import_log(self.taxonomy)
        assert log == task.log
        assert "Traceback" not in log
        return result, log, plan

    def _seed(self, rows: list[dict]) -> dict[str, int]:
        """
        Create the starting tags and return their pks by external_id.
        """
        result, _log, _plan = self._import(rows, ParserFormat.JSON)
        assert result
        return {tag.external_id: tag.pk for tag in self.taxonomy.tag_set.all()}

    def _associate(self, pks: dict[str, int], *external_ids: str) -> dict[int, int]:
        """
        Tag a content object with each tag and return the ObjectTag pks by tag pk.
        """
        object_tags = {}
        for external_id in external_ids:
            tag = Tag.objects.get(pk=pks[external_id])
            object_tag = ObjectTag.objects.create(
                object_id=f"object-{tag.pk}", taxonomy=self.taxonomy, tag=tag, _value=tag.value,
            )
            object_tags[tag.pk] = object_tag.pk
        return object_tags

    def _assert_associations_kept(self, object_tags: dict[int, int]) -> None:
        """
        Check each ObjectTag still points to the same tag, not a recreated one.
        """
        for tag_pk, object_tag_pk in object_tags.items():
            assert ObjectTag.objects.get(pk=object_tag_pk).tag_id == tag_pk

    def _export(self, parser_format: ParserFormat) -> str:
        """
        Export the taxonomy in the given format.
        """
        return import_export_api.export_tags(self.taxonomy, parser_format)

    def _exported_rows(self, parser_format: ParserFormat) -> list[dict]:
        """
        Parse the export and check it only carries the id, value and parent_id fields.
        """
        output = self._export(parser_format)
        if parser_format == ParserFormat.JSON:
            rows = json.loads(output)["tags"]
            fields = {key for row in rows for key in row}
        else:
            reader = csv.DictReader(StringIO(output))
            assert reader.fieldnames == ["id", "value", "parent_id"]
            rows = list(reader)
            fields = set(reader.fieldnames)
        assert fields <= {"id", "value", "parent_id"}
        return [{"id": row["id"], "value": row["value"], "parent_id": row.get("parent_id") or None} for row in rows]

    def _exported_ids(self, parser_format: ParserFormat) -> dict[str, str]:
        """
        Return the exported id of each tag, by tag value.
        """
        return {row["value"]: row["id"] for row in self._exported_rows(parser_format)}

    def _exported_parents(self, parser_format: ParserFormat) -> dict[str, str | None]:
        """
        Return the exported parent_id of each tag, by tag value.
        """
        return {row["value"]: row["parent_id"] for row in self._exported_rows(parser_format)}

    @contextmanager
    def _rolled_back(self):
        """
        Run a block in a savepoint that is rolled back, so a scenario can be repeated.
        """
        with transaction.atomic():
            yield
            transaction.set_rollback(True)

    def _assert_rejected(self, rows: list[dict], parser_format: ParserFormat, *messages: str) -> str:
        """
        Check the import is rejected, its log has each message, and nothing changed.
        """
        snapshot = set(self.taxonomy.tag_set.values_list("pk", "external_id", "value", "parent_id"))
        before = self._export(parser_format)
        result, log, _plan = self._import(rows, parser_format)
        assert not result
        for message in messages:
            assert message in log
        assert set(self.taxonomy.tag_set.values_list("pk", "external_id", "value", "parent_id")) == snapshot
        assert self._export(parser_format) == before
        return log

    def test_rename_shows_in_export_without_duplicate_or_previous_id(self) -> None:
        """
        S1, S2, S15: a rename shows in the export once, as the new id, with no row for the old
        id and no previous_id field, and the tag keeps its pk and its content associations.
        """
        pks = self._seed([_row("COMP-A", "Alpha")])
        object_tags = self._associate(pks, "COMP-A")
        for parser_format in self.formats:
            with self.subTest(parser_format=parser_format), self._rolled_back():
                count = len(self._exported_rows(parser_format))
                result, _log, _plan = self._import([_row("COMP-B", "Alpha", previous_id="COMP-A")], parser_format)
                assert result
                assert [row["id"] for row in self._exported_rows(parser_format)] == ["COMP-B"]
                assert len(self._exported_rows(parser_format)) == count
                assert self.taxonomy.tag_set.count() == 1
                assert Tag.objects.get(pk=pks["COMP-A"]).external_id == "COMP-B"
                self._assert_associations_kept(object_tags)

    def test_reimport_with_previous_id_equal_to_id_is_idempotent(self) -> None:
        """
        S3: a row whose previous_id equals its id succeeds and the export does not change.
        """
        self._seed([_row("COMP-B", "Beta")])
        for parser_format in self.formats:
            with self.subTest(parser_format=parser_format), self._rolled_back():
                before = self._export(parser_format)
                result, _log, _plan = self._import([_row("COMP-B", "Beta", previous_id="COMP-B")], parser_format)
                assert result
                assert self._export(parser_format) == before

    def test_new_id_without_previous_id_is_created(self) -> None:
        """
        S4: a row with a new id and no previous_id creates a tag that shows in the export.
        """
        self._seed([_row("COMP-A", "Alpha")])
        for parser_format in self.formats:
            with self.subTest(parser_format=parser_format), self._rolled_back():
                result, _log, _plan = self._import(
                    [_row("COMP-A", "Alpha"), _row("COMP-Z", "Zulu")], parser_format,
                )
                assert result
                assert self._exported_ids(parser_format) == {"Alpha": "COMP-A", "Zulu": "COMP-Z"}

    def test_unmatched_previous_id_rejected(self) -> None:
        """
        S5: an unmatched previous_id is rejected with the id in the log, nothing is introduced,
        and when several rows have one, every id is in the same log.
        """
        self._seed([_row("COMP-A", "Alpha"), _row("COMP-C", "Gamma")])
        for parser_format in self.formats:
            with self.subTest(parser_format=parser_format):
                self._assert_rejected(
                    [_row("COMP-B", "Alpha", previous_id="COMP-GHOST"), _row("COMP-C", "Gamma")],
                    parser_format,
                    "COMP-GHOST",
                )
                self._assert_rejected(
                    [
                        _row("COMP-B", "Alpha", previous_id="COMP-GHOST-1"),
                        _row("COMP-D", "Gamma", previous_id="COMP-GHOST-2"),
                    ],
                    parser_format,
                    "COMP-GHOST-1",
                    "COMP-GHOST-2",
                )

    def test_rename_onto_id_of_kept_tag_rejected(self) -> None:
        """
        S6, S8: a rename onto an id whose holder the same file keeps is rejected, in either row
        order, whether the holder is kept as a plain row or as a row with previous_id equal to id.
        """
        self._seed([_row("COMP-Z", "Xray"), _row("COMP-A", "Yank")])
        rename = _row("COMP-Z", "Yank", previous_id="COMP-A")
        keeps = {
            "plain": _row("COMP-Z", "Xray"),
            "previous_id equal to id": _row("COMP-Z", "Xray", previous_id="COMP-Z"),
        }
        for parser_format in self.formats:
            for name, keep in keeps.items():
                for rows in ([rename, keep], [keep, rename]):
                    with self.subTest(parser_format=parser_format, keep=name, first=rows[0]["value"]):
                        self._assert_rejected(rows, parser_format, "COMP-Z")

    def test_rename_onto_id_freed_by_omitting_holder(self) -> None:
        """
        S7: a rename onto an id the same file frees by omitting its holder succeeds in every row
        order: the holder is gone, the renamed tag keeps its pk and associations, and the export
        shows it.
        """
        pks = self._seed([
            _row("COMP-Z", "Xray"), _row("COMP-A", "Yank"), _row("COMP-W", "Whisky"), _row("COMP-V", "Victor"),
        ])
        object_tags = self._associate(pks, "COMP-A")
        rows = [
            _row("COMP-Z", "Yank", previous_id="COMP-A"), _row("COMP-W", "Whisky"), _row("COMP-V", "Victor"),
        ]
        for parser_format in self.formats:
            for order in itertools.permutations(range(3)):
                with self.subTest(parser_format=parser_format, order=order), self._rolled_back():
                    result, _log, _plan = self._import([rows[i] for i in order], parser_format)
                    assert result
                    assert not Tag.objects.filter(pk=pks["COMP-Z"]).exists()
                    assert Tag.objects.get(pk=pks["COMP-A"]).external_id == "COMP-Z"
                    self._assert_associations_kept(object_tags)
                    assert self._exported_ids(parser_format) == {
                        "Yank": "COMP-Z", "Whisky": "COMP-W", "Victor": "COMP-V",
                    }

    def test_swap_keeps_tags_and_associations(self) -> None:
        """
        S9: a swap succeeds in either row order, creates and deletes nothing, keeps both tags'
        pks and associations, and the export shows the swapped ids.
        """
        pks = self._seed([_row("COMP-A", "Alpha"), _row("COMP-B", "Beta")])
        object_tags = self._associate(pks, "COMP-A", "COMP-B")
        rows = [_row("COMP-B", "Alpha", previous_id="COMP-A"), _row("COMP-A", "Beta", previous_id="COMP-B")]
        for parser_format in self.formats:
            for order in itertools.permutations(range(2)):
                with self.subTest(parser_format=parser_format, order=order), self._rolled_back():
                    result, _log, _plan = self._import([rows[i] for i in order], parser_format)
                    assert result
                    assert self.taxonomy.tag_set.count() == 2
                    assert Tag.objects.get(pk=pks["COMP-A"]).external_id == "COMP-B"
                    assert Tag.objects.get(pk=pks["COMP-B"]).external_id == "COMP-A"
                    self._assert_associations_kept(object_tags)
                    assert self._exported_ids(parser_format) == {"Alpha": "COMP-B", "Beta": "COMP-A"}

    def test_three_way_rotation_in_any_row_order(self) -> None:
        """
        S10: a three-way rotation succeeds in all six row orders, and each tag holds the id its
        own row specified.
        """
        pks = self._seed([_row("COMP-A", "Alpha"), _row("COMP-B", "Beta"), _row("COMP-C", "Gamma")])
        rows = [
            _row("COMP-B", "Alpha", previous_id="COMP-A"),
            _row("COMP-C", "Beta", previous_id="COMP-B"),
            _row("COMP-A", "Gamma", previous_id="COMP-C"),
        ]
        for parser_format in self.formats:
            for order in itertools.permutations(range(3)):
                with self.subTest(parser_format=parser_format, order=order), self._rolled_back():
                    result, _log, _plan = self._import([rows[i] for i in order], parser_format)
                    assert result
                    assert Tag.objects.get(pk=pks["COMP-A"]).external_id == "COMP-B"
                    assert Tag.objects.get(pk=pks["COMP-B"]).external_id == "COMP-C"
                    assert Tag.objects.get(pk=pks["COMP-C"]).external_id == "COMP-A"
                    assert self._exported_ids(parser_format) == {
                        "Alpha": "COMP-B", "Beta": "COMP-C", "Gamma": "COMP-A",
                    }

    def test_rename_chain_colliding_with_kept_tag_rejected_whole(self) -> None:
        """
        S11: a rename chain that ends on an id the file keeps is rejected whole in all six row
        orders, with the id in the log and all three tags unchanged.
        """
        self._seed([_row("COMP-A", "Alpha"), _row("COMP-B", "Beta"), _row("COMP-C", "Gamma")])
        rows = [
            _row("COMP-B", "Alpha", previous_id="COMP-A"),
            _row("COMP-C", "Beta", previous_id="COMP-B"),
            _row("COMP-C", "Gamma"),
        ]
        for parser_format in self.formats:
            for order in itertools.permutations(range(3)):
                with self.subTest(parser_format=parser_format, order=order):
                    self._assert_rejected([rows[i] for i in order], parser_format, "COMP-C")

    def test_child_names_new_id_of_renamed_parent(self) -> None:
        """
        S12: a child row naming its renamed parent's new id succeeds in either row order, the
        child stays under the same parent tag, and the export shows it nested under the new id.
        """
        pks = self._seed([_row("COMP-P", "Parent"), _row("COMP-K", "Kid", parent_id="COMP-P")])
        rows = [_row("COMP-P2", "Parent", previous_id="COMP-P"), _row("COMP-K", "Kid", parent_id="COMP-P2")]
        for parser_format in self.formats:
            for order in itertools.permutations(range(2)):
                with self.subTest(parser_format=parser_format, order=order), self._rolled_back():
                    result, _log, _plan = self._import([rows[i] for i in order], parser_format)
                    assert result
                    assert Tag.objects.get(pk=pks["COMP-K"]).parent_id == pks["COMP-P"]
                    assert self._exported_ids(parser_format)["Parent"] == "COMP-P2"
                    assert self._exported_parents(parser_format)["Kid"] == "COMP-P2"

    def test_child_names_pre_import_id_of_renamed_parent_rejected(self) -> None:
        """
        S13, A: an existing child naming its parent's pre-import id is rejected in either row
        order, with its row position and the new id in the log, and nothing changes.
        """
        self._seed([_row("COMP-P", "Parent"), _row("COMP-K", "Kid", parent_id="COMP-P")])
        rows = [_row("COMP-P2", "Parent", previous_id="COMP-P"), _row("COMP-K", "Kid", parent_id="COMP-P")]
        for parser_format in self.formats:
            for order in itertools.permutations(range(2)):
                with self.subTest(parser_format=parser_format, order=order):
                    file_rows = [rows[i] for i in order]
                    child_row = file_rows.index(rows[1]) + 1
                    self._assert_rejected(
                        file_rows,
                        parser_format,
                        f"Row {child_row}'s parent_id (COMP-P) names an id this file renames away.",
                        "Use 'COMP-P2' as the parent_id.",
                    )

    def test_parent_and_child_both_renamed(self) -> None:
        """
        S14: renaming a parent and its child together succeeds in either row order, and the
        export shows both new ids with the child nested under the parent.
        """
        pks = self._seed([_row("COMP-P", "Parent"), _row("COMP-K", "Kid", parent_id="COMP-P")])
        rows = [
            _row("COMP-P2", "Parent", previous_id="COMP-P"),
            _row("COMP-K2", "Kid", parent_id="COMP-P2", previous_id="COMP-K"),
        ]
        for parser_format in self.formats:
            for order in itertools.permutations(range(2)):
                with self.subTest(parser_format=parser_format, order=order), self._rolled_back():
                    result, _log, _plan = self._import([rows[i] for i in order], parser_format)
                    assert result
                    assert Tag.objects.get(pk=pks["COMP-K"]).parent_id == pks["COMP-P"]
                    assert self._exported_ids(parser_format) == {"Parent": "COMP-P2", "Kid": "COMP-K2"}
                    assert self._exported_parents(parser_format) == {"Parent": None, "Kid": "COMP-P2"}

    def test_export_has_no_previous_id_and_round_trips_without_changes(self) -> None:
        """
        S16: the export only has id, value and parent_id, and importing it back unchanged plans
        no change.
        """
        self._seed([_row("COMP-P", "Parent"), _row("COMP-K", "Kid", parent_id="COMP-P"), _row("COMP-A", "Alpha")])
        for parser_format in self.formats:
            with self.subTest(parser_format=parser_format):
                exported = self._exported_rows(parser_format)
                assert len(exported) == 3
                result, _log, plan = self._import(
                    [{key: value for key, value in row.items() if value} for row in exported],
                    parser_format,
                    plan_only=True,
                )
                assert result
                assert plan is not None
                assert {action.name for action in plan.actions} == {"without_changes"}

    def test_swap_with_children_in_representative_orders(self) -> None:
        """
        B, C: in a swap where each parent has a child, children naming the end-state ids succeed
        and stay on their physical parents, and children naming the stale ids are rejected with
        their row positions, in several row orders and both formats.
        """
        pks = self._seed([
            _row("COMP-A", "Alpha"), _row("COMP-AK", "Alpha kid", parent_id="COMP-A"),
            _row("COMP-B", "Beta"), _row("COMP-BK", "Beta kid", parent_id="COMP-B"),
        ])
        swap = [_row("COMP-B", "Alpha", previous_id="COMP-A"), _row("COMP-A", "Beta", previous_id="COMP-B")]
        accepted = swap + [
            _row("COMP-AK", "Alpha kid", parent_id="COMP-B"), _row("COMP-BK", "Beta kid", parent_id="COMP-A"),
        ]
        stale = swap + [
            _row("COMP-AK", "Alpha kid", parent_id="COMP-A"), _row("COMP-BK", "Beta kid", parent_id="COMP-B"),
        ]
        orders = [(0, 1, 2, 3), (2, 3, 0, 1), (2, 0, 3, 1), (3, 2, 1, 0)]
        for parser_format in self.formats:
            for order in orders:
                with self.subTest(parser_format=parser_format, order=order), self._rolled_back():
                    result, _log, _plan = self._import([accepted[i] for i in order], parser_format)
                    assert result
                    assert Tag.objects.get(pk=pks["COMP-AK"]).parent_id == pks["COMP-A"]
                    assert Tag.objects.get(pk=pks["COMP-BK"]).parent_id == pks["COMP-B"]
                    assert self._exported_parents(parser_format) == {
                        "Alpha": None, "Beta": None, "Alpha kid": "COMP-B", "Beta kid": "COMP-A",
                    }
                with self.subTest(parser_format=parser_format, order=order, stale=True):
                    file_rows = [stale[i] for i in order]
                    self._assert_rejected(
                        file_rows,
                        parser_format,
                        f"Row {file_rows.index(stale[2]) + 1}'s parent_id (COMP-A) names an id this file renames away.",
                        f"Row {file_rows.index(stale[3]) + 1}'s parent_id (COMP-B) names an id this file renames away.",
                    )

    def test_every_rejected_row_is_in_the_one_log(self) -> None:
        """
        Several rejected rows of different kinds each have their message in the same log, since
        the wizard shows the log as one block.
        """
        self._seed([
            _row("COMP-P", "Parent"),
            _row("COMP-K1", "Kid 1", parent_id="COMP-P"),
            _row("COMP-K2", "Kid 2", parent_id="COMP-P"),
            _row("COMP-A", "Alpha"),
        ])
        rows = [
            _row("COMP-P2", "Parent", previous_id="COMP-P"),
            _row("COMP-K1", "Kid 1", parent_id="COMP-P"),
            _row("COMP-K2", "Kid 2", parent_id="COMP-P"),
            _row("COMP-B", "Alpha", previous_id="COMP-GHOST"),
        ]
        for parser_format in self.formats:
            with self.subTest(parser_format=parser_format):
                self._assert_rejected(
                    rows,
                    parser_format,
                    "Row 2's parent_id (COMP-P) names an id this file renames away.",
                    "Row 3's parent_id (COMP-P) names an id this file renames away.",
                    "COMP-GHOST",
                )

    def test_rename_onto_freed_id_forming_parent_cycle_rejected(self) -> None:
        """
        A rename onto an id the same import frees can close a parent cycle through the
        renamed tag: a self-parent, and two renames naming each other as parent. Both are
        rejected at the plan step with exactly one cycle error, in either row order.
        """
        self._seed([_row(tag_id, f"Value {tag_id}") for tag_id in ("COMP-X", "COMP-Y")])
        self_parent = [_row("COMP-X", "Value COMP-Y", parent_id="COMP-X", previous_id="COMP-Y")]
        for parser_format in self.formats:
            with self.subTest(parser_format=parser_format, case="self parent"):
                log = self._assert_rejected(self_parent, parser_format, "creates a parent cycle.")
                assert log.count("creates a parent cycle.") == 1
        self._seed([_row(tag_id, f"Value {tag_id}") for tag_id in ("COMP-A", "COMP-B", "COMP-C", "COMP-D")])
        rows = [
            _row("COMP-A", "Value COMP-C", parent_id="COMP-B", previous_id="COMP-C"),
            _row("COMP-B", "Value COMP-D", parent_id="COMP-A", previous_id="COMP-D"),
        ]
        for parser_format in self.formats:
            for order in itertools.permutations(range(2)):
                with self.subTest(parser_format=parser_format, order=order, case="two renames"):
                    log = self._assert_rejected([rows[i] for i in order], parser_format, "creates a parent cycle.")
                    assert log.count("creates a parent cycle.") == 1

    def test_child_of_deleted_holder_moves_under_tag_renamed_onto_its_id(self) -> None:
        """
        A child of a tag that the import deletes, while another tag is renamed onto the
        deleted tag's id, ends up under the renamed tag, not as a root, in either row order.
        """
        pks = self._seed([_row("COMP-X", "Xray"), _row("COMP-Y", "Yank"), _row("COMP-C", "Child", parent_id="COMP-X")])
        object_tags = self._associate(pks, "COMP-C")
        rows = [_row("COMP-X", "Yank", previous_id="COMP-Y"), _row("COMP-C", "Child", parent_id="COMP-X")]
        for parser_format in self.formats:
            for order in itertools.permutations(range(2)):
                with self.subTest(parser_format=parser_format, order=order), self._rolled_back():
                    result, _log, _plan = self._import([rows[i] for i in order], parser_format)
                    assert result
                    assert not Tag.objects.filter(pk=pks["COMP-X"]).exists()
                    assert Tag.objects.get(pk=pks["COMP-C"]).parent_id == pks["COMP-Y"]
                    assert Tag.objects.get(pk=pks["COMP-Y"]).external_id == "COMP-X"
                    self._assert_associations_kept(object_tags)
                    assert self._exported_parents(parser_format) == {"Yank": None, "Child": "COMP-X"}

    def test_kept_tags_under_deleted_ancestors_become_roots(self) -> None:
        """
        A kept tag whose parent is deleted by the import becomes a root, also when that
        parent sits under a deleted ancestor, which would otherwise cascade to the kept tag.
        """
        cases = {
            "grandchild of a deleted chain": (
                [("t0", None), ("t1", "t0"), ("t5", "t1")], ["t5"],
            ),
            "kept tags at two depths": (
                [("t0", None), ("t1", "t0"), ("t2", "t1"), ("t3", "t2"), ("t4", "t3")], ["t2", "t4"],
            ),
            "child of a deleted root": ([("t0", None), ("t1", "t0")], ["t1"]),
        }
        for name, (structure, kept) in cases.items():
            for parser_format in self.formats:
                with self.subTest(case=name, parser_format=parser_format), self._rolled_back():
                    pks = self._seed([_row(tag_id, f"Value {tag_id}", parent) for tag_id, parent in structure])
                    result, _log, _plan = self._import(
                        [_row(tag_id, f"Value {tag_id}") for tag_id in kept], parser_format,
                    )
                    assert result
                    assert set(self.taxonomy.tag_set.values_list("pk", flat=True)) == {pks[t] for t in kept}
                    assert all(tag.parent_id is None for tag in self.taxonomy.tag_set.all())
                    assert self._exported_parents(parser_format) == {f"Value {t}": None for t in kept}

    def _assert_tree_after_import(
        self,
        rows: list[dict],
        expected_parents: dict[str, str | None],
        pks: dict[str, int],
        orders: Sequence[tuple[int, ...]],
        parser_formats: tuple[ParserFormat, ...],
        *,
        static_rows: tuple[dict, ...] = (),
    ) -> None:
        """
        Import `rows` in each row order and format, followed by `static_rows` (the other tags
        the replace import has to keep), and check that every tag in
        `expected_parents` (external_id to parent external_id) ends up under that parent in the
        database and the export, and that the tags in `pks` keep their pk. Each import is
        rolled back.
        """
        for parser_format in parser_formats:
            for order in orders:
                with self.subTest(parser_format=parser_format, order=order), self._rolled_back():
                    result, _log, _plan = self._import([rows[i] for i in order] + list(static_rows), parser_format)
                    assert result
                    for tag_id, pk in pks.items():
                        assert Tag.objects.get(pk=pk).external_id == tag_id
                    db_parents = {
                        tag.external_id: tag.parent.external_id if tag.parent else None
                        for tag in self.taxonomy.tag_set.select_related("parent")
                    }
                    assert db_parents == expected_parents
                    exported = {row["id"]: row["parent_id"] for row in self._exported_rows(parser_format)}
                    assert exported == expected_parents

    def test_ancestry_inversion_in_any_row_order(self) -> None:
        """
        A child of t0 becomes t0's ancestor (a new tag g0 is put between them), which only
        works if it moves out of t0's subtree first. It succeeds in all 24 row orders in JSON and
        in four of them in CSV, and ends with the expected tree.
        """
        pks = self._seed([_row("t0", "Zero"), _row("t1", "One", "t0"), _row("t2", "Two", "t0")])
        rows = [_row("t0", "Zero", "g0"), _row("t1", "One", "g0"), _row("t2", "Two"), _row("g0", "New", "t2")]
        expected = {"t0": "g0", "t1": "g0", "t2": None, "g0": "t2"}
        orders = list(itertools.permutations(range(4)))
        self._assert_tree_after_import(rows, expected, pks, orders, (ParserFormat.JSON,))
        self._assert_tree_after_import(rows, expected, pks, orders[::6], (ParserFormat.CSV,))

    def test_parent_and_child_swap_places(self) -> None:
        """
        A parent and its child swap places in either row order.
        """
        pks = self._seed([_row("t0", "Zero"), _row("t1", "One", "t0")])
        rows = [_row("t0", "Zero", "t1"), _row("t1", "One")]
        orders = list(itertools.permutations(range(2)))
        self._assert_tree_after_import(rows, {"t0": "t1", "t1": None}, pks, orders, self.formats)

    def test_three_level_chain_reversed(self) -> None:
        """
        A chain t0 > t1 > t2 is reversed to t2 > t1 > t0 in all six row orders.
        """
        pks = self._seed([_row("t0", "Zero"), _row("t1", "One", "t0"), _row("t2", "Two", "t1")])
        rows = [_row("t2", "Two"), _row("t1", "One", "t2"), _row("t0", "Zero", "t1")]
        expected = {"t2": None, "t1": "t2", "t0": "t1"}
        orders = list(itertools.permutations(range(3)))
        self._assert_tree_after_import(rows, expected, pks, orders, self.formats)

    def test_tag_moved_under_its_former_grandchild(self) -> None:
        """
        A root t0 is moved under t2, its former grandchild, which is left a child of t1
        (now a root), in all six row orders.
        """
        pks = self._seed([_row("t0", "Zero"), _row("t1", "One", "t0"), _row("t2", "Two", "t1")])
        rows = [_row("t0", "Zero", "t2"), _row("t1", "One"), _row("t2", "Two", "t1")]
        expected = {"t0": "t2", "t1": None, "t2": "t1"}
        orders = list(itertools.permutations(range(3)))
        self._assert_tree_after_import(rows, expected, pks, orders, self.formats)

    def _seed_deep_chain(self) -> dict[str, int]:
        """
        Create the chain t0 > t1 > t2 > t3 > t5 and return the pks by external_id.
        """
        return self._seed([
            _row("t0", "Zero"), _row("t1", "One", "t0"), _row("t2", "Two", "t1"),
            _row("t3", "Three", "t2"), _row("t5", "Five", "t3"),
        ])

    def test_deep_tag_moved_to_root_with_new_children_in_any_row_order(self) -> None:
        """
        t5 is the deepest tag of a chain and moves to the root while new tags g0 and g1 are put
        under it. Creating them first would exceed the maximum depth, so the import detaches t5
        first. It succeeds in all six row orders in JSON and in three of them in CSV.
        """
        pks = self._seed_deep_chain()
        rows = [_row("g1", "New 1", "g0"), _row("g0", "New 0", "t5"), _row("t5", "Five")]
        chain = (_row("t0", "Zero"), _row("t1", "One", "t0"), _row("t2", "Two", "t1"), _row("t3", "Three", "t2"))
        expected = {"t0": None, "t1": "t0", "t2": "t1", "t3": "t2", "t5": None, "g0": "t5", "g1": "g0"}
        orders = list(itertools.permutations(range(3)))
        self._assert_tree_after_import(rows, expected, pks, orders, (ParserFormat.JSON,), static_rows=chain)
        self._assert_tree_after_import(rows, expected, pks, orders[::2], (ParserFormat.CSV,), static_rows=chain)

    def test_deep_tag_under_renamed_parent_moved_to_root_in_any_row_order(self) -> None:
        """
        The same move when t5's old parent t3 is renamed in the same import: all 24 row orders
        in JSON succeed and t5 keeps its pk.
        """
        pks = self._seed_deep_chain()
        rows = [
            _row("g1", "New 1", "g0"), _row("g0", "New 0", "t5"), _row("t5", "Five"),
            _row("r3", "Three", "t2", "t3"),
        ]
        expected = {"t0": None, "t1": "t0", "t2": "t1", "r3": "t2", "t5": None, "g0": "t5", "g1": "g0"}
        orders = list(itertools.permutations(range(4)))
        kept_pks = {tag_id: pk for tag_id, pk in pks.items() if tag_id != "t3"} | {"r3": pks["t3"]}
        static = (_row("t0", "Zero"), _row("t1", "One", "t0"), _row("t2", "Two", "t1"))
        self._assert_tree_after_import(rows, expected, kept_pks, orders, (ParserFormat.JSON,), static_rows=static)

    def test_subtree_moved_under_deep_tag_before_it_is_shallowed(self) -> None:
        """
        A three-level subtree s0 > s1 > s2 moves under c3, which itself moves to the root, in
        every row order and both formats.
        """
        pks = self._seed([
            _row("c0", "C0"), _row("c1", "C1", "c0"), _row("c2", "C2", "c1"), _row("c3", "C3", "c2"),
            _row("s0", "S0"), _row("s1", "S1", "s0"), _row("s2", "S2", "s1"),
        ])
        rows = [_row("s0", "S0", "c3"), _row("c3", "C3"), _row("s1", "S1", "s0"), _row("s2", "S2", "s1")]
        expected = {"c0": None, "c1": "c0", "c2": "c1", "c3": None, "s0": "c3", "s1": "s0", "s2": "s1"}
        orders = list(itertools.permutations(range(4)))
        static = (_row("c0", "C0"), _row("c1", "C1", "c0"), _row("c2", "C2", "c1"))
        self._assert_tree_after_import(rows, expected, pks, orders, (ParserFormat.JSON,), static_rows=static)
        self._assert_tree_after_import(rows, expected, pks, orders[::6], (ParserFormat.CSV,), static_rows=static)

    def test_three_new_levels_under_moved_deep_tag(self) -> None:
        """
        Three new tags chained under t5, which moves to the root, succeed in all 24 row orders.
        """
        pks = self._seed_deep_chain()
        rows = [
            _row("t5", "Five"), _row("g0", "New 0", "t5"), _row("g1", "New 1", "g0"), _row("g2", "New 2", "g1"),
        ]
        expected = {
            "t0": None, "t1": "t0", "t2": "t1", "t3": "t2", "t5": None, "g0": "t5", "g1": "g0", "g2": "g1",
        }
        orders = list(itertools.permutations(range(4)))
        chain = (_row("t0", "Zero"), _row("t1", "One", "t0"), _row("t2", "Two", "t1"), _row("t3", "Three", "t2"))
        self._assert_tree_after_import(rows, expected, pks, orders, (ParserFormat.JSON,), static_rows=chain)

    def test_import_that_leaves_tags_too_deep_is_rejected(self) -> None:
        """
        An import that would put a tag at the seventh level, by adding a child to the deepest
        tag of a six-level chain or by moving a chain under another, cannot be applied in any
        order, so it is rejected at the plan step and nothing changes.
        """
        chain = [("a", None), ("b", "a"), ("c", "b"), ("d", "c"), ("e", "d"), ("f", "e")]
        two_chains = [("a", None), ("b", "a"), ("c", "b"), ("d", "c"), ("w", None), ("x", "w"), ("y", "x"), ("z", "y")]
        cases = {
            "child of the deepest tag": (
                chain, [_row(tag_id, f"Value {tag_id}", parent) for tag_id, parent in chain]
                + [_row("g", "Value g", "f")],
            ),
            "chain moved under another": (
                two_chains,
                [_row(t, f"Value {t}", "d" if t == "w" else parent) for t, parent in two_chains],
            ),
        }
        message = "This import would leave tags deeper than 6 levels"
        for name, (structure, rows) in cases.items():
            self._seed([_row(tag_id, f"Value {tag_id}", parent) for tag_id, parent in structure])
            for parser_format in self.formats:
                with self.subTest(case=name, parser_format=parser_format):
                    log = self._assert_rejected(rows, parser_format, message)
                    assert log.count(message) == 1
            self.taxonomy.tag_set.all().delete()

    def test_swap_child_naming_parent_id_in_another_case(self) -> None:
        """
        In a swap, ids are case-insensitive: a child naming its parent's stale id in another case
        is rejected once, with its row position and the new id, like the exact spelling. A child
        naming the end-state ids in another case is accepted and stays under its parent.
        """
        pks = self._seed([
            _row("COMP-A", "Alpha"), _row("COMP-AK", "Alpha kid", "COMP-A"),
            _row("COMP-B", "Beta"), _row("COMP-BK", "Beta kid", "COMP-B"),
        ])
        swap = [_row("COMP-B", "Alpha", previous_id="COMP-A"), _row("COMP-A", "Beta", previous_id="COMP-B")]
        stale = swap + [_row("COMP-AK", "Alpha kid", "comp-a"), _row("COMP-BK", "Beta kid", "comp-a")]
        accepted = swap + [_row("COMP-AK", "Alpha kid", "comp-b"), _row("COMP-BK", "Beta kid", "comp-a")]
        expected = {"COMP-B": None, "COMP-A": None, "COMP-AK": "COMP-B", "COMP-BK": "COMP-A"}
        moved_pks = {
            "COMP-B": pks["COMP-A"], "COMP-A": pks["COMP-B"], "COMP-AK": pks["COMP-AK"], "COMP-BK": pks["COMP-BK"],
        }
        orders = [(0, 1, 2, 3), (2, 3, 0, 1), (3, 2, 1, 0), (2, 0, 3, 1)]
        self._assert_tree_after_import(accepted, expected, moved_pks, orders, self.formats)
        for parser_format in self.formats:
            for order in orders:
                with self.subTest(parser_format=parser_format, order=order, stale=True):
                    file_rows = [stale[i] for i in order]
                    position = file_rows.index(stale[2]) + 1
                    log = self._assert_rejected(
                        file_rows,
                        parser_format,
                        f"Row {position}'s parent_id (comp-a) names an id this file renames away.",
                        "Use 'COMP-B' as the parent_id.",
                    )
                    assert log.count("names an id this file renames away") == 1

    def test_plain_rename_child_naming_parent_id_in_another_case_reported_once(self) -> None:
        """
        When a parent is plainly renamed, a child naming its old id in another case gets only
        the parent validation error, in either row order and format.
        """
        self._seed([_row("COMP-P", "Parent"), _row("COMP-K", "Kid", "COMP-P")])
        rows = [_row("COMP-P2", "Parent", previous_id="COMP-P"), _row("COMP-K", "Kid", "comp-p")]
        for parser_format in self.formats:
            for order in itertools.permutations(range(2)):
                with self.subTest(parser_format=parser_format, order=order):
                    log = self._assert_rejected(
                        [rows[i] for i in order],
                        parser_format,
                        "Parent tag comp-p is renamed to COMP-P2 in this file; use COMP-P2 as the parent_id.",
                    )
                    assert "names an id this file renames away" not in log

    def test_case_only_parent_rename_with_case_variant_child(self) -> None:
        """
        Renaming a parent only by case, a child naming it in another case stays under it.
        """
        pks = self._seed([_row("COMP-P", "Parent"), _row("COMP-K", "Kid", "COMP-P")])
        for child_parent in ("comp-p", "Comp-P"):
            rows = [_row("Comp-P", "Parent", previous_id="COMP-P"), _row("COMP-K", "Kid", child_parent)]
            expected = {"Comp-P": None, "COMP-K": "Comp-P"}
            kept_pks = {"Comp-P": pks["COMP-P"], "COMP-K": pks["COMP-K"]}
            with self.subTest(child_parent=child_parent):
                self._assert_tree_after_import(
                    rows, expected, kept_pks, list(itertools.permutations(range(2))), self.formats,
                )
