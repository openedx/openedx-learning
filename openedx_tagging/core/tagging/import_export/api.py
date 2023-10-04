"""
Import/export API functions

A modular implementation has been followed for both functionalities.

Import
------------

In this functionality we have the following pipeline with the following classes:

Parser.parse_import() -> TagImportPlan.generate_actions() -> [ImportActions]
-> TagImportPlan.plan() -> TagImportPlan.execute()

Parsers are in charge of reading the input file,
making the respective verifications of its format and returning a list of TagItems.
You need to create parser for each format that the system will accept.
For more information see parsers.py

TagImportPlan receives a list of TagItems. With this, it generates each
action that will be executed in the import.
Each Action are in charge of verifying and executing specific
and simple operations in the database, such as creating or rename tag.
For more information see actions.py

In each action it is verified if there are no errors or inconsistencies
with taxonomy tags or with previous actions.
In the end, TagImportPlan contains all actions and possible errors.
You can run `plan()` to see the actions and errors or you can run `execute()`
to execute each action.

Export
----------

The export only uses Parsers. Calls the respective function and
returns a string with the data.


TODO for next versions
---------
- Function to force clean the status of an import task, or a way to avoid
  a lock: a task not in SUCCESS or ERROR due to something unexpected
  (ex. server crash)
- Join/reduce actions on TagImportPlan. See `generate_actions()`
"""
from __future__ import annotations

from io import BytesIO

from django.utils.translation import gettext as _

from ..models import TagImportTask, TagImportTaskState, Taxonomy
from .exceptions import TagImportError
from .import_plan import TagImportPlan, TagImportTask
from .parsers import ParserFormat, get_parser


def import_tags(
    taxonomy: Taxonomy,
    file: BytesIO,
    parser_format: ParserFormat,
    replace=False,
) -> bool:
    """
    Execute the necessary actions to import the tags from `file`

    You can read the docstring of the top for more info about the
    modular architecture.

    It creates an TagImportTask to keep logs of the execution
    of each import step and the current status.
    There can only be one task in progress at a time per taxonomy

    Set `replace` to True to delete all not readed Tag of the given taxonomy.
    Ex. Given a taxonomy with `tag_1`, `tag_2` and `tag_3`. If there is only `tag_1`
    in the file (regardless of action), then `tag_2` and `tag_3` will be deleted
    if `replace=True`
    """
    _import_export_validations(taxonomy)

    # Checks that exists only one task import in progress at a time per taxonomy
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
        tag_import_plan = TagImportPlan(taxonomy)
        tag_import_plan.generate_actions(tags, replace)
        task.log_plan(tag_import_plan)

        if tag_import_plan.errors:
            task.handle_plan_errors()
            return False

        task.log_start_execute()
        tag_import_plan.execute(task)
        task.end_success()
        return True
    except (TagImportError, ValueError) as exception:
        # Log any exception
        task.log_exception(exception)
        return False


def get_last_import_status(taxonomy: Taxonomy) -> TagImportTaskState:
    """
    Get status of the last import task of the given taxonomy
    """
    task = _get_last_import_task(taxonomy)
    if task is None:
        raise ValueError("No import task was created yet.")
    return TagImportTaskState(task.status)


def get_last_import_log(taxonomy: Taxonomy) -> str:
    """
    Get logs of the last import task of the given taxonomy
    """
    task = _get_last_import_task(taxonomy)
    if task is None:
        raise ValueError("No import task was created yet.")
    return task.log


def export_tags(taxonomy: Taxonomy, output_format: ParserFormat) -> str:
    """
    Returns a string with all tag data of the given taxonomy
    """
    _import_export_validations(taxonomy)
    parser = get_parser(output_format)
    return parser.export(taxonomy)


def _check_unique_import_task(taxonomy: Taxonomy) -> bool:
    """
    Verifies if there is another in progress import task for the
    given taxonomy
    """
    last_task = _get_last_import_task(taxonomy)
    if not last_task:
        return True
    return (
        last_task.status in {
            TagImportTaskState.SUCCESS.value,
            TagImportTaskState.ERROR.value
        }
    )


def _get_last_import_task(taxonomy: Taxonomy) -> TagImportTask | None:
    """
    Get the last import task for the given taxonomy
    """
    return (
        TagImportTask.objects.filter(taxonomy=taxonomy)
        .order_by("-creation_date")
        .first()
    )


def _import_export_validations(taxonomy: Taxonomy):
    """
    Validates if the taxonomy is allowed to import or export tags
    """
    taxonomy = taxonomy.cast()
    if taxonomy.allow_free_text:
        raise NotImplementedError(
            _(
                "Import/export for free-form taxonomies will be implemented in the future."
            )
        )
    if taxonomy.system_defined:
        raise ValueError(
            _(
                "Invalid taxonomy ({id}): You cannot import/export a system-defined taxonomy."
            ).format(id=taxonomy.id)
        )
