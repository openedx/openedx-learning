"""
"""
from io import BytesIO

from django.utils.translation import gettext_lazy as _

from ..models import Taxonomy, TagImportTask, TagImportTaskState
from .parsers import get_parser, ParserFormat
from .import_plan import TagImportDSL, TagImportTask


def import_tags(
    taxonomy: Taxonomy,
    file: BytesIO,
    parser_format: ParserFormat,
    replace=False,
) -> bool:
    _import_export_validations(taxonomy)

    # Checks that exists only one tag
    if not _check_unique_import_task(taxonomy):
        raise ValueError(
            _(
                "There is an import task running. "
                "Only one task per taxonomy can be created at a time."
            )
        )

    # Creating import task
    task = TagImportTask.create(taxonomy)

    try:
        # Get the parser and parse the file
        task.log_parser_start()
        parser = get_parser(parser_format)
        tags, errors = parser.parse_import(file)

        # Check if there are errors in the parse
        if errors:
            task.handle_parser_errors(errors)
            return False

        task.log_parser_end()

        # Generate actions
        task.log_start_planning()
        dsl = TagImportDSL(taxonomy)
        dsl.generate_actions(tags, replace)
        task.log_plan(dsl)

        if dsl.errors:
            task.handle_plan_errors()
            return False

        task.log_start_execute()
        dsl.execute(task)
        task.end_success()
        return True
    except Exception as exception:
        # Log any exception
        task.log_exception(exception)
        return False


def get_last_import_status(taxonomy: Taxonomy) -> TagImportTaskState:
    task = _get_last_tags(taxonomy)
    return task.status


def get_last_import_log(taxonomy: Taxonomy) -> str:
    task = _get_last_tags(taxonomy)
    return task.log


def export_tags(taxonomy: Taxonomy, output_format: ParserFormat) -> str:
    _import_export_validations(taxonomy)
    parser = get_parser(output_format)
    return parser.export(taxonomy)


def _check_unique_import_task(taxonomy: Taxonomy) -> bool:
    last_task = _get_last_tags(taxonomy)
    if not last_task:
        return True
    return (
        last_task.status == TagImportTaskState.SUCCESS.value
        or last_task.status == TagImportTaskState.ERROR.value
    )


def _get_last_tags(taxonomy: Taxonomy) -> TagImportTask:
    return (
        TagImportTask.objects.filter(taxonomy=taxonomy)
        .order_by("-creation_date")
        .first()
    )


def _import_export_validations(taxonomy: Taxonomy):
    taxonomy = taxonomy.cast()
    if taxonomy.allow_free_text:
        raise ValueError(
            _(
                f"Invalid taxonomy ({taxonomy.id}): You cannot import/export a free-form taxonomy."
            )
        )
    if taxonomy.system_defined:
        raise ValueError(
            _(
                f"Invalid taxonomy ({taxonomy.id}): You cannot import/export a system-defined taxonomy."
            )
        )
