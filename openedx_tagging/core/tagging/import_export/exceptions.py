"""
Exceptions for tag import/export actions
"""
from django.utils.translation import gettext_lazy as _


class TagImportError(Exception):
    """
    Base exception for import
    """

    def __init__(self, message: str = "", **kargs):
        self.message = message

    def __str__(self):
        return str(self.message)

    def __repr__(self):
        return f"{self.__class__.__name__}({str(self)})"


class TagParserError(TagImportError):
    """
    Base exception for parsers
    """

    def __init__(self, tag, **kargs):
        self.message = _(f"Import parser error on {tag}")


class ImportActionError(TagImportError):
    """
    Base exception for actions
    """

    def __init__(self, action: str, tag_id: str, message: str, **kargs):
        self.message = _(
            f"Action error in '{action.name}' (#{action.index}): {message}"
        )


class ImportActionConflict(ImportActionError):
    """
    Exception used when exists a conflict between actions
    """

    def __init__(
        self,
        action: str,
        tag_id: str,
        conflict_action_index: int,
        message: str,
        **kargs,
    ):
        self.message = _(
            f"Conflict with '{action.name}' (#{action.index}) "
            f"and action #{conflict_action_index}: {message}"
        )


class InvalidFormat(TagParserError):
    """
    Exception used when there is an error with the format
    """

    def __init__(self, tag: dict, format: str, message: str, **kargs):
        self.tag = tag
        self.message = _(f"Invalid '{format}' format: {message}")


class FieldJSONError(TagParserError):
    """
    Exception used when missing a required field on the .json
    """

    def __init__(self, tag, field, **kargs):
        self.tag = tag
        self.message = _(f"Missing '{field}' field on {tag}")


class EmptyJSONField(TagParserError):
    """
    Exception used when a required field is empty on the .json
    """

    def __init__(self, tag, field, **kargs):
        self.tag = tag
        self.message = _(f"Empty '{field}' field on {tag}")


class EmptyCSVField(TagParserError):
    """
    Exception used when a required field is empty on the .csv
    """

    def __init__(self, tag, field, row, **kargs):
        self.tag = tag
        self.message = _(f"Empty '{field}' field on the row {row}")
