"""
Django management commands to handle restore learning packages (WIP)
"""
import logging

from django.core.management import CommandError
from django.core.management.base import BaseCommand

from openedx_learning.apps.authoring.backup_restore.api import extract_zip_file

logger = logging.getLogger(__name__)


class Command(BaseCommand):
    """
    Django management command to import a learning package from a zip file.
    """
    help = 'Import a learning package from a zip file.'

    def add_arguments(self, parser):
        parser.add_argument('file_name', type=str, help='The name of the input zip file')

    def handle(self, *args, **options):
        file_name = options['file_name']
        if not file_name.endswith(".zip"):
            raise CommandError("Input file name must end with .zip")
        try:
            extract_zip_file(file_name)
            message = f'{file_name} imported successfully'
            self.stdout.write(self.style.SUCCESS(message))
        except FileNotFoundError as exc:
            message = f"Learning package file {file_name} not found"
            raise CommandError(message) from exc
        except Exception as e:
            message = f"Failed to import '{file_name}': {e}"
            logger.exception(
                "Failed to import zip file %s ",
                file_name,
            )
            raise CommandError(message) from e
