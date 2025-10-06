"""
Django management commands to handle restore learning packages (WIP)
"""
import logging
import time

from django.core.management import CommandError
from django.core.management.base import BaseCommand

from openedx_learning.apps.authoring.backup_restore.api import load_dump_zip_file

logger = logging.getLogger(__name__)


class Command(BaseCommand):
    """
    Django management command to load a learning package from a zip file.
    """
    help = 'Load a learning package from a zip file.'

    def add_arguments(self, parser):
        parser.add_argument('file_name', type=str, help='The path of the input zip file to load.')

    def handle(self, *args, **options):
        file_name = options['file_name']
        if not file_name.lower().endswith(".zip"):
            raise CommandError("Input file name must end with .zip")
        try:
            start_time = time.time()
            response = load_dump_zip_file(file_name)
            duration = time.time() - start_time
            if response["status"] == "error":
                message = "Errors encountered during restore:\n"
                log_buffer = response.get("log_file_error")
                if log_buffer:
                    message += log_buffer.getvalue()
                raise CommandError(message)
            message = f'{file_name} loaded successfully (duration: {duration:.2f} seconds)'
            self.stdout.write(self.style.SUCCESS(message))
        except FileNotFoundError as exc:
            message = f"Learning package file {file_name} not found: {exc}"
            raise CommandError(message) from exc
        except Exception as e:
            message = f"Failed to load '{file_name}': {e}"
            logger.exception(
                "Failed to load zip file %s ",
                file_name,
            )
            raise CommandError(message) from e
