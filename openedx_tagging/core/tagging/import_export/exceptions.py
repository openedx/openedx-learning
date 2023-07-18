from django.utils.translation import gettext_lazy as _

class ImportError(Exception):
    def __init__(self, message:str='', **kargs):
        self.message = message

    def __str__(self):
        return str(self.message)
    
    def __repr__(self):
        return f"{self.__class__.__name__}({str(self)})"
    

class ParserError(ImportError):
    def __init__(self, tag: str, **kargs):
        self.message = _(f"Import error on {tag}")


class ActionError(ImportError):
    def __init__(self, action: str, tag_id: str, message: str, **kargs):
        self.message = _(
            f"Action error in '{action.name}' (#{action.index}) in tag ({tag_id}): {message}"
        )


class ActionConflict(ActionError):
    def __init__(
        self,
        action: str,
        tag_id: str,
        conflict_action_index: int,
        message: str,
        **kargs
    ):
        self.message = _(
            f"Conflict with '{action.name}' (#{action.index}) in tag ({tag_id})"
            f" and action #{conflict_action_index}: {message}"
        )


class InvalidFormat(ParserError):
    def __init__(self, tag: dict, format: str, message: str, **kargs):
        self.tag = tag
        self.message = _(f"Invalid '{format}' format: {message}")


class FieldJSONError(ParserError):
    def __init__(self, tag, field, **kargs):
        self.tag = tag
        self.message = _(f"Missing '{field}' field on {tag}")


class EmptyJSONField(ParserError):
    def __init__(self, tag, field, **kargs):
        self.tag = tag
        self.message = _(f"Empty '{field}' field on {tag}")


class EmptyCSVField(ParserError):
    def __init__(self, tag, field, row, **kargs):
        self.tag = tag
        self.message = _(f"Empty '{field}' field on the row {row}")
