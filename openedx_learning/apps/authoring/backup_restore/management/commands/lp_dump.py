"""
Django management commands to handle backup and restore learning packages (WIP)
"""
import logging

from django.core.exceptions import ObjectDoesNotExist
from django.core.management.base import BaseCommand

from openedx_learning.apps.authoring.backup_restore.api import create_zip_file

logger = logging.getLogger(__name__)


class Command(BaseCommand):
    """
    Django management command to export a learning package to a zip file.
    """
    help = 'Export a learning package to a zip file.'

    def add_arguments(self, parser):
        parser.add_argument('lp_key', type=str, help='The key of the LearningPackage to dump')
        parser.add_argument('file_name', type=str, help='The name of the output zip file')

    def handle(self, *args, **options):
        lp_key = options['lp_key']
        file_name = options['file_name']
        try:
            create_zip_file(lp_key, file_name)
            message = f'{lp_key} written to {file_name}'
            self.stdout.write(self.style.SUCCESS(message))
        except ObjectDoesNotExist:
            message = f"Learning package with key {lp_key} not found"
            self.stderr.write(self.style.ERROR(message))
        except Exception as e:  # pylint: disable=broad-exception-caught
            message = f"Error creating zip file: error {e}"
            self.stderr.write(self.style.ERROR(message))
            logger.exception(
                "Failed to create zip file %s (learning‑package key %s)",
                file_name,
                lp_key,
            )
