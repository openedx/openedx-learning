"""
Django management commands to handle backup and restore learning packages (WIP)
"""

from django.core.management.base import BaseCommand

from openedx_learning.apps.authoring.backup_restore.api import create_zip_file


class Command(BaseCommand):
    """
    Django management command to export a learning package on a zip file
    """
    help = 'Export a learning package on a zip file'

    def add_arguments(self, parser):
        parser.add_argument('lp_key', type=str, help='The key of the LearningPackage to dump')
        parser.add_argument('file_name', type=str, help='The name of the output zip file')

    def handle(self, *args, **options):
        lp_key = options['lp_key']
        file_name = options['file_name']
        try:
            create_zip_file(lp_key, file_name)
            message = f'The [{file_name}] was created with [{lp_key}] learning package key'
            self.stdout.write(self.style.SUCCESS(message))
        except Exception as e:  # pylint: disable=broad-exception-caught
            message = f"Error on create the zip file {e}"
            self.stdout.write(self.style.ERROR(message))
