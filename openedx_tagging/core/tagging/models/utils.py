"""
Utilities for tagging and taxonomy models
"""
from django.db.models import Aggregate, CharField
from django.db.models.expressions import Func

# This is NOT the separator of export csv file.
# This is the separator of the individual group of tags per taxonomy.
# eg. languages-v1: en;es;fr
#
# This character is not allowed to be placed in the value of a tag,
# to avoid inconsistencies when exporting and importing tags.
TAGS_CSV_SEPARATOR = ';'


class ConcatNull(Func):  # pylint: disable=abstract-method
    """
    Concatenate two arguments together. Like normal SQL but unlike Django's
    "Concat", if either argument is NULL, the result will be NULL.
    """

    function = "CONCAT"

    def as_sqlite(self, compiler, connection, **extra_context):
        """ SQLite doesn't have CONCAT() but has a concatenation operator """
        return super().as_sql(
            compiler,
            connection,
            template="%(expressions)s",
            arg_joiner=" || ",
            **extra_context,
        )


class StringAgg(Aggregate):  # pylint: disable=abstract-method
    """
    Aggregate function that collects the values of some column across all rows,
    and creates a string by concatenating those values, with "," as a separator.

    This is the same as Django's django.contrib.postgres.aggregates.StringAgg,
    but this version works with MySQL and SQLite.
    """
    function = 'GROUP_CONCAT'
    template = '%(function)s(%(distinct)s%(expressions)s)'

    def __init__(self, expression, distinct=False, **extra):
        super().__init__(
            expression,
            distinct='DISTINCT ' if distinct else '',
            output_field=CharField(),
            **extra,
        )
