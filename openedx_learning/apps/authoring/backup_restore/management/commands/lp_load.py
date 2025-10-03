"""
Django management commands to handle restore learning packages (WIP)
"""
import logging

from django.core.management import CommandError
from django.core.management.base import BaseCommand

from openedx_learning.apps.authoring.backup_restore.api import load_dump_zip_file, tmp_delete_learning_package

logger = logging.getLogger(__name__)


class Command(BaseCommand):
    """
    Django management command to load a learning package from a zip file.
    """
    help = 'Load a learning package from a zip file.'

    def add_arguments(self, parser):
        parser.add_argument('file_name', type=str, help='The name of the input zip file to load.')

    def handle(self, *args, **options):
        file_name = options['file_name']
        if not file_name.lower().endswith(".zip"):
            raise CommandError("Input file name must end with .zip")
        try:
            tmp_delete_learning_package("lib:WGU:LIB_C001")  # Temporary line to help with testing
            response = load_dump_zip_file(file_name)
            print(response)  # For debugging purposes
            message = f'{file_name} loaded successfully'
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
