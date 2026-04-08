"""
Django management commands to handle restore learning packages (WIP)
"""
import logging
import time

from django.contrib.auth import get_user_model
from django.core.management import CommandError
from django.core.management.base import BaseCommand

from openedx_content.applets.backup_restore.api import load_learning_package

logger = logging.getLogger(__name__)

User = get_user_model()



class Command(BaseCommand):
    """
    Django management command to load a Learning Package.
    """
    help = 'Load a learning package from a zip file.'

    def add_arguments(self, parser):
        parser.add_argument('path', type=str, help='The path of the directory or file to load from.')
        parser.add_argument('package_ref', type=str, help="Learning Package Ref: often a v2 library key.")
        parser.add_argument('username', type=str, help='The username of the user performing the load operation.')


    def handle(self, *args, **options):
        path = options['path']
        package_ref = options['package_ref']
        username = options['username']

        user = User.objects.get(username=username)

        load_learning_package(path, user=user, package_ref=package_ref)

        return 0
        if not path.lower().endswith(".zip"):
            raise CommandError("Input file name must end with .zip")
        try:
            start_time = time.time()
            # Get the user performing the operation
            user = User.objects.get(username=username)

            result = load_learning_package(path, user=user)
            duration = time.time() - start_time
            if result["status"] == "error":
                message = "Errors encountered during restore:\n"
                log_buffer = result.get("log_file_error")
                if log_buffer:
                    message += log_buffer.getvalue()
                raise CommandError(message)
            message = f'{path} loaded successfully (duration: {duration:.2f} seconds)'
            self.stdout.write(self.style.SUCCESS(message))
        except FileNotFoundError as exc:
            message = f"Learning package file {path} not found: {exc}"
            raise CommandError(message) from exc
        except Exception as e:
            message = f"Failed to load '{path}': {e}"
            logger.exception(
                "Failed to load zip file %s ",
                path,
            )
            raise CommandError(message) from e
