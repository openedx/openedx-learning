from django.utils.translation import gettext_lazy as _


class TagImportError(Exception):
    def __init__(self, message: str = "", **kargs):
        self.message = message

    def __str__(self):
        return str(self.message)

    def __repr__(self):
        return f"{self.__class__.__name__}({str(self)})"


class TagParserError(TagImportError):
    def __init__(self, tag, **kargs):
        self.message = _(f"Import parser error on {tag}")


class ImportActionError(TagImportError):
    def __init__(self, action: str, tag_id: str, message: str, **kargs):
        self.message = _(
            f"Action error in '{action.name}' (#{action.index}): {message}"
        )


class ImportActionConflict(ImportActionError):
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
    def __init__(self, tag: dict, format: str, message: str, **kargs):
        self.tag = tag
        self.message = _(f"Invalid '{format}' format: {message}")


class FieldJSONError(TagParserError):
    def __init__(self, tag, field, **kargs):
        self.tag = tag
        self.message = _(f"Missing '{field}' field on {tag}")


class EmptyJSONField(TagParserError):
    def __init__(self, tag, field, **kargs):
        self.tag = tag
        self.message = _(f"Empty '{field}' field on {tag}")


class EmptyCSVField(TagParserError):
    def __init__(self, tag, field, row, **kargs):
        self.tag = tag
        self.message = _(f"Empty '{field}' field on the row {row}")
