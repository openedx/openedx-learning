"""
Parsers to import and export tags
"""
import csv
import json
from enum import Enum
from io import BytesIO, TextIOWrapper
from typing import List, Tuple

from django.utils.translation import gettext_lazy as _

from .models import TagDSL
from .exceptions import (
    TagParserError,
    InvalidFormat,
    FieldJSONError,
    EmptyJSONField,
    EmptyCSVField,
)


class ParserFormat(Enum):
    """
    Format of import tags to taxonomies
    """

    JSON = ".json"
    CSV = ".csv"


class Parser:
    """
    Base class to create a parser

    This contains the base functions to load data,
    validate required fields and convert tags to DLS format
    """

    required_fields = ["id", "value"]
    optional_fields = ["parent_id", "action"]

    # Set the format associated to the parser
    format = None
    # We can change the error when is missing a required field
    missing_field_error = TagParserError
    # We can change the error when a required field is empty
    empty_field_error = TagParserError
    # We can change the initial row/index
    inital_row = 1

    @classmethod
    def parse_import(cls, file: BytesIO) -> Tuple[List[TagDSL], List[TagParserError]]:
        """
        Top function that calls `_load_data` and `_parse_tags`.
        Handle the errors returned both functions
        """
        try:
            tags_data, load_errors = cls._load_data(file)
            if load_errors:
                return [], load_errors
        except Exception as error:
            raise error
        finally:
            file.close()

        return cls._parse_tags(tags_data)

    @classmethod
    def _load_data(cls, file: BytesIO) -> Tuple[List[dict], List[TagParserError]]:
        """
        Each parser implements this function according to its format.
        This function reads the file and returns a list with the values of each tag.

        This function does not do field validations, it only does validations of the
        file structure in the parser format. Field validations are done in `_parse_tags`
        """
        raise NotImplementedError

    @classmethod
    def _parse_tags(cls, tags_data: dict) -> Tuple[List[TagDSL], List[TagParserError]]:
        """
        Validate the required fields of each tag.

        Return a list of tags in the DSL format
        and a list of validation errors.
        """
        tags = []
        errors = []
        row = cls.inital_row
        for tag in tags_data:
            has_error = False

            # Verify the required fields
            for req_field in cls.required_fields:
                if req_field not in tag:
                    # Verify if the field exists
                    errors.append(
                        cls.missing_field_error(
                            tag,
                            field=req_field,
                            row=row,
                        )
                    )
                    has_error = True
                elif not tag.get(req_field):
                    # Verify if the value of the field is not empty
                    errors.append(
                        cls.empty_field_error(
                            tag,
                            field=req_field,
                            row=row,
                        )
                    )
                    has_error = True

            tag["index"] = row
            row += 1

            # Skip parse if there is an error
            if has_error:
                continue

            # Updating any empty optional field to None
            for opt_field in cls.optional_fields:
                if opt_field in tag and not tag.get(opt_field):
                    tag[opt_field] = None

            tags.append(TagDSL(**tag))

        return tags, errors


class JSONParser(Parser):
    """
    Parser used with .json files

    Valid file:
    ```
      {
        "tags": [
          {
            "id": "tag_1",
            "value": "tag 1",
            "parent_id": "tag_2",
          }
        ]
      }
    ```
    """

    format = ParserFormat.JSON
    missing_field_error = FieldJSONError
    empty_field_error = EmptyJSONField
    inital_row = 0

    @classmethod
    def _load_data(cls, file: BytesIO) -> Tuple[List[dict], List[TagParserError]]:
        """
        Read a .json file and validates the root structure of the json
        """
        file.seek(0)
        tags_data = json.load(file)
        if "tags" not in tags_data:
            return None, [
                InvalidFormat(
                    tag=None,
                    format=cls.format.value,
                    message=_("Missing 'tags' field on the .json file"),
                )
            ]

        tags_data = tags_data.get("tags")
        return tags_data, []


class CSVParser(Parser):
    """
    Parser used with .csv files

    Valid file:
    ```
    id,value,parent_id
    tag_1,tag 1,
    tag_2,tag 2,tag_1
    ```
    """

    format = ParserFormat.CSV
    empty_field_error = EmptyCSVField
    inital_row = 2

    @classmethod
    def _load_data(cls, file: BytesIO) -> Tuple[List[dict], List[TagParserError]]:
        """
        Read a .csv file and validates the header fields
        """
        file.seek(0)
        text_tags = TextIOWrapper(file, encoding="utf-8")
        csv_reader = csv.DictReader(text_tags)
        header_fields = csv_reader.fieldnames
        errors = cls._veify_header(header_fields)
        if errors:
            return None, errors
        return list(csv_reader), []

    @classmethod
    def _veify_header(cls, header_fields: List[str]) -> List[TagParserError]:
        """
        Verify that the header contains the required fields
        """
        errors = []
        print(header_fields)
        for req_field in cls.required_fields:
            if req_field not in header_fields:
                errors.append(
                    InvalidFormat(
                        tag=None,
                        format=cls.format.value,
                        message=_(f"Missing '{req_field}' field on CSV headers"),
                    )
                )
        return errors


# Add parsers here
_parsers = [JSONParser, CSVParser]


def get_parser(parser_format: ParserFormat) -> Parser:
    """
    Get the parser for the respective `format`

    Raise `ValueError` if no parser found
    """
    for parser in _parsers:
        if parser_format == parser.format:
            return parser

    raise ValueError(_(f"Parser not found for format {parser_format}"))
