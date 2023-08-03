"""
Test for import/export API
"""
import json
from io import BytesIO

from django.test.testcases import TestCase

from openedx_tagging.core.tagging.models import TagImportTask, TagImportTaskState
from openedx_tagging.core.tagging.import_export import ParserFormat
import openedx_tagging.core.tagging.import_export.api as import_export_api

from .test_actions import TestImportActionMixin


class TestImportApi(TestImportActionMixin, TestCase):
    """
    Test import API functions
    """

    def setUp(self):
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
            {'id': 'tag_31', 'value': 'Tag 31',},
            {'id': 'tag_31', 'value': 'Tag 32',},
        ]}
        self.invalid_plan_file = BytesIO(json.dumps(json_data).encode())

        self.parser_format = ParserFormat.JSON
        return super().setUp()

    def test_check_status(self):
        TagImportTask.create(self.taxonomy)
        status = import_export_api.get_last_import_status(self.taxonomy)
        assert status == TagImportTaskState.LOADING_DATA.value

    def test_check_log(self):
        TagImportTask.create(self.taxonomy)
        log = import_export_api.get_last_import_log(self.taxonomy)
        assert "Import task created" in log

    def test_invalid_import_tags(self):
        TagImportTask.create(self.taxonomy)
        with self.assertRaises(ValueError):
            # Raise error if there is a current in progress task
            import_export_api.import_tags(
                self.taxonomy,
                self.file,
                self.parser_format,
            )

    def test_with_python_error(self):
        self.file.close()
        assert not import_export_api.import_tags(
            self.taxonomy,
            self.file,
            self.parser_format,
        )
        status = import_export_api.get_last_import_status(self.taxonomy)
        log = import_export_api.get_last_import_log(self.taxonomy)
        assert status == TagImportTaskState.ERROR.value
        assert "ValueError('I/O operation on closed file.')" in log

    def test_with_parser_error(self):
        assert not import_export_api.import_tags(
            self.taxonomy,
            self.invalid_parser_file,
            self.parser_format,
        )
        status = import_export_api.get_last_import_status(self.taxonomy)
        log = import_export_api.get_last_import_log(self.taxonomy)
        assert status == TagImportTaskState.ERROR.value
        assert "Starting to load data from file" in log
        assert "Invalid '.json' format" in log

    def test_with_plan_errors(self):
        assert not import_export_api.import_tags(
            self.taxonomy,
            self.invalid_plan_file,
            self.parser_format,
        )
        status = import_export_api.get_last_import_status(self.taxonomy)
        log = import_export_api.get_last_import_log(self.taxonomy)
        assert status == TagImportTaskState.ERROR.value
        assert "Starting to load data from file" in log
        assert "Load data finished" in log
        assert "Starting plan actions" in log
        assert "Plan finished" in log
        assert "Conflict with 'create'" in log

    def test_valid(self):
        assert import_export_api.import_tags(
            self.taxonomy,
            self.file,
            self.parser_format,
            replace=True,
        )
        status = import_export_api.get_last_import_status(self.taxonomy)
        log = import_export_api.get_last_import_log(self.taxonomy)
        assert status == TagImportTaskState.SUCCESS.value
        assert "Starting to load data from file" in log
        assert "Load data finished" in log
        assert "Starting plan actions" in log
        assert "Plan finished" in log
        assert "Starting execute actions" in log
        assert "Execution finished" in log

    def test_start_task_after_error(self):
        assert not import_export_api.import_tags(
            self.taxonomy,
            self.invalid_parser_file,
            self.parser_format,
        )
        assert import_export_api.import_tags(
            self.taxonomy,
            self.file,
            self.parser_format,
        )

    def test_start_task_after_success(self):
        assert import_export_api.import_tags(
            self.taxonomy,
            self.file,
            self.parser_format,
        )

        # Opening again the file
        json_data = {"tags": self.tags}
        self.file = BytesIO(json.dumps(json_data).encode())

        assert import_export_api.import_tags(
            self.taxonomy,
            self.file,
            self.parser_format,
        )
