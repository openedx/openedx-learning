"""
Test for import/export parsers
"""
from io import BytesIO
import json
import ddt

from django.test.testcases import TestCase

from openedx_tagging.core.tagging.import_export.parsers import (
    get_parser,
    JSONParser,
    CSVParser,
    ParserFormat,
)


class TestParser(TestCase):
    """
    Test for general parser functions
    """

    def test_get_parser(self):
        for parser_format in ParserFormat:
            parser = get_parser(parser_format)
            self.assertEqual(parser.format, parser_format)

    def test_parser_not_found(self):
        with self.assertRaises(ValueError):
            get_parser(None)

@ddt.ddt
class TestJSONParser(TestCase):
    """
    Test for .json parser
    """

    def test_load_data_errors(self):
        json_data = {"invalid": [
            {"id": "tag_1", "name": "Tag 1"},
        ]}

        json_file = BytesIO(json.dumps(json_data).encode())

        tags, errors = JSONParser.parse_import(json_file)
        self.assertEqual(len(tags), 0)
        self.assertEqual(len(errors), 1)
        self.assertEqual(
            str(errors[0]),
            "Invalid '.json' format: Missing 'tags' field on the .json file"
        )

    @ddt.data(
        (
            {"tags": [
                {"id": "tag_1", "value": "Tag 1"}, # Valid
            ]},
            []
        ),
        (
            {"tags": [
                {"id": "tag_1"},
                {"value": "tag_1"},
                {},
            ]},
            [
                "Missing 'value' field on {'id': 'tag_1'}",
                "Missing 'id' field on {'value': 'tag_1'}",
                "Missing 'value' field on {}",
                "Missing 'id' field on {}",
            ]
        ),
        (
            {"tags": [
                {"id": "", "value": "tag 1"},
                {"id": "tag_2", "value": ""},
                {"id": "tag_3", "value": "tag 3", "parent_id": ""}, # Valid
            ]},
            [
                "Empty 'id' field on {'id': '', 'value': 'tag 1'}",
                "Empty 'value' field on {'id': 'tag_2', 'value': ''}",
            ]
        )
    )
    @ddt.unpack
    def test_parse_tags_errors(self, json_data, expected_errors):
        json_file = BytesIO(json.dumps(json_data).encode())

        _, errors = JSONParser.parse_import(json_file)
        self.assertEqual(len(errors), len(expected_errors))

        for error in errors:
            self.assertIn(str(error), expected_errors)

    def test_parse_tags(self):
        expected_tags = [
            {"id": "tag_1", "value": "tag 1"},
            {"id": "tag_2", "value": "tag 2"},
            {"id": "tag_3", "value": "tag 3", "parent_id": "tag_1"},
            {"id": "tag_4", "value": "tag 4", "action": "delete"},
        ]
        json_data = {"tags": expected_tags}

        json_file = BytesIO(json.dumps(json_data).encode())

        tags, errors = JSONParser.parse_import(json_file)
        self.assertEqual(len(errors), 0)
        self.assertEqual(len(tags), 4)

        # Result tags must be in the same order of the file
        for index, expected_tag in enumerate(expected_tags):
            self.assertEqual(
                tags[index].id,
                expected_tag.get('id')
            )
            self.assertEqual(
                tags[index].value,
                expected_tag.get('value')
            )
            self.assertEqual(
                tags[index].parent_id,
                expected_tag.get('parent_id')
            )
            self.assertEqual(
                tags[index].action,
                expected_tag.get('action')
            )
            self.assertEqual(
                tags[index].index,
                index + JSONParser.inital_row
            )

@ddt.ddt
class TestCSVParser(TestCase):
    """
    Test for .csv parser
    """

    @ddt.data(
        (
            "value\n",
            ["Invalid '.csv' format: Missing 'id' field on CSV headers"],
        ),
        (
            "id\n",
            ["Invalid '.csv' format: Missing 'value' field on CSV headers"],
        ),
        (
            "id_name,value_name\n",
            [
                "Invalid '.csv' format: Missing 'id' field on CSV headers",
                "Invalid '.csv' format: Missing 'value' field on CSV headers"
            ],
        ),
        (
            # Valid
            "id,value\n",
            []
        )
    )
    @ddt.unpack
    def test_load_data_errors(self, csv_data, expected_errors):
        csv_file = BytesIO(csv_data.encode())

        tags, errors = CSVParser.parse_import(csv_file)
        self.assertEqual(len(tags), 0)
        self.assertEqual(len(errors), len(expected_errors))

        for error in errors:
            self.assertIn(str(error), expected_errors)

    @ddt.data(
        (
            "id,value\ntag_1\ntag_2,\n",
            [
                "Empty 'value' field on the row 2",
                "Empty 'value' field on the row 3",
            ]
        ),
        (
            "id,value\ntag_1,tag 1\n", # Valid
            []
        )
    )
    @ddt.unpack
    def test_parse_tags_errors(self, csv_data, expected_errors):
        csv_file = BytesIO(csv_data.encode())

        _, errors = CSVParser.parse_import(csv_file)
        self.assertEqual(len(errors), len(expected_errors))

        for error in errors:
            self.assertIn(str(error), expected_errors)

    def _build_csv(self, tags):
        """
        Builds a csv from 'tags' dict
        """
        csv = "id,value,parent_id,action\n"
        for tag in tags:
            csv += (
                f"{tag.get('id')},{tag.get('value')},"
                f"{tag.get('parent_id') or ''},{tag.get('action') or ''}\n"
            )
        return csv

    def test_parse_tags(self):
        expected_tags = [
            {"id": "tag_1", "value": "tag 1"},
            {"id": "tag_2", "value": "tag 2"},
            {"id": "tag_3", "value": "tag 3", "parent_id": "tag_1"},
            {"id": "tag_4", "value": "tag 4", "action": "delete"},
        ]
        csv_data = self._build_csv(expected_tags)
        csv_file = BytesIO(csv_data.encode())
        tags, errors = CSVParser.parse_import(csv_file)

        self.assertEqual(len(errors), 0)
        self.assertEqual(len(tags), 4)

        # Result tags must be in the same order of the file
        for index, expected_tag in enumerate(expected_tags):
            self.assertEqual(
                tags[index].id,
                expected_tag.get('id')
            )
            self.assertEqual(
                tags[index].value,
                expected_tag.get('value')
            )
            self.assertEqual(
                tags[index].parent_id,
                expected_tag.get('parent_id')
            )
            self.assertEqual(
                tags[index].action,
                expected_tag.get('action')
            )
            self.assertEqual(
                tags[index].index,
                index + CSVParser.inital_row
            )