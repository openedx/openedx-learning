from io import BytesIO

from django.utils.translation import gettext_lazy as _

from ..models import Taxonomy
from .parsers import get_parser, ParserFormat
from .models import TagImportDSL, TagImportTask, TagImportTaskState


def import_tags(
    taxonomy: Taxonomy,
    file: BytesIO,
    parser_format: ParserFormat,
    replace=False,
) -> bool:
    # Checks that exists only one tag
    if not _check_unique_import_task(taxonomy):
        raise ValueError(_(
            "There is an import task running. "
            "Only one task per taxonomy can be created at a time."
        ))
    
    # Creating import task
    task = TagImportTask.create(taxonomy)

    try:
        # Get the parser and parse the file
        task.log_parser_start()
        parser = get_parser(parser_format)
        tags, errors = parser.parse_import(file)
        task.log_parser_end()

        # Check if there are errors in the parse
        if errors:
            task.handle_parser_errors(errors)
            return False

        # Generate actions
        task.log_start_planning()
        dsl = TagImportDSL()
        dsl.generate_actions(tags, taxonomy, replace)
        task.log_end_planning(dsl)

        if dsl.errors:
            task.handle_plan_errors()
            return False

        return dsl.execute()
    except Exception as exception:
        # Log any exception
        task.log_exception(exception)
        return False


def _check_unique_import_task(taxonomy: Taxonomy) -> bool:
    last_task = (
        TagImportTask.objects
            .filter(taxonomy=taxonomy)
            .order_by('-creation_date')
            .first()
    )
    if not last_task:
        return False
    return (last_task.status != TagImportTaskState.SUCCESS
            and last_task.status != TagImportTaskState.ERROR)


def check_import_staus():
    pass
