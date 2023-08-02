from io import BytesIO
from celery import shared_task

from .api import import_tags
from ..models import Taxonomy
from .parsers import ParserFormat


@shared_task
def import_tags_async(
    taxonomy: Taxonomy,
    file: BytesIO,
    parser_format: ParserFormat,
    replace=False,
):
    import_tags(
        taxonomy,
        file,
        parser_format,
        replace,
    )