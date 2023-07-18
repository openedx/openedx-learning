from io import BytesIO
from typing import List

from ..models import Taxonomy
from .parsers import get_parser, ParserFormat
from .exceptions import ImportError
from .dsl import TagImportDSL

# TODO This function must be a celery task
def import_tags(
    taxonomy: Taxonomy,
    file: BytesIO,
    parser_format: ParserFormat,
    replace=False,
    execute=False,
):
    # Get the parser and parse the file
    parser = get_parser(parser_format)
    tags, errors = parser.parse_import(file)

    # Check if there are errors in the parse
    if errors:
        return errors
    
    # Generate the actions
    dsl = TagImportDSL()
    dsl.generate_actions(tags, taxonomy, replace)
    
    # Execute the plan
    if execute:
        return dsl.execute()
    
    # Or return the plan
    return dsl.plan()
