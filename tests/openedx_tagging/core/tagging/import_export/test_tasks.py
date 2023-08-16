"""
Test import/export celery tasks
"""
from io import BytesIO
from unittest.mock import patch

from django.test.testcases import TestCase

from openedx_tagging.core.tagging.import_export import ParserFormat
import openedx_tagging.core.tagging.import_export.tasks as import_export_tasks

from .mixins import TestImportExportMixin


class TestImportExportCeleryTasks(TestImportExportMixin, TestCase):
    """
    Test import/export celery tasks
    """

    def test_import_tags_task(self):
        file = BytesIO(b"some_data")
        parser_format = ParserFormat.CSV
        replace = True

        with patch('openedx_tagging.core.tagging.import_export.api.import_tags') as mock_import_tags:
            mock_import_tags.return_value = True

            result = import_export_tasks.import_tags_task(self.taxonomy, file, parser_format, replace)

            self.assertTrue(result)
            mock_import_tags.assert_called_once_with(self.taxonomy, file, parser_format, replace)

    def test_export_tags_task(self):
        output_format = ParserFormat.JSON

        with patch('openedx_tagging.core.tagging.import_export.api.export_tags') as mock_export_tags:
            mock_export_tags.return_value = "exported_data"

            result = import_export_tasks.export_tags_task(self.taxonomy, output_format)

            self.assertEqual(result, "exported_data")
            mock_export_tags.assert_called_once_with(self.taxonomy, output_format)
