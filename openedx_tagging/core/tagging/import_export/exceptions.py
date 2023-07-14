from django.utils.translation import gettext_lazy as _

class ImportError(Exception):
    def __init__(self, **kargs):
        self.message = _(f"Import error")

    def __str__(self):
        return str(self.message)
    

class ParserError(ImportError):
    def __init__(self, tag: str, **kargs):
        self.message = _(f"Import error on {tag}")


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
