"""
Django management commands to handle restore learning packages (WIP)
"""
import logging
import time

from django.contrib.auth import get_user_model
from django.core.management import CommandError
from django.core.management.base import BaseCommand

from openedx_content.applets.backup_restore.api import load_learning_package
from openedx_content.applets.backup_restore.errors import BackupRestoreError, RestoreFailedError

logger = logging.getLogger(__name__)

User = get_user_model()


class Command(BaseCommand):
    """
    Django management command to load a learning package from a backup archive.
    """
    help = 'Load a learning package from a backup archive (a .zip file or an unzipped directory).'

    def add_arguments(self, parser):
        parser.add_argument(
            'path',
            type=str,
            help='The path of the archive to load: either a .zip file or a directory.',
        )
        parser.add_argument('username', type=str, help='The username of the user performing the load operation.')
        parser.add_argument(
            '--package-ref',
            type=str,
            default=None,
            help=(
                "The package ref to restore under. If omitted, a staged ref "
                "namespaced to the user is generated."
            ),
        )

    def handle(self, *args, **options):
        path = options['path']
        username = options['username']
        package_ref = options['package_ref']

        try:
            user = User.objects.get(username=username)
        except User.DoesNotExist as exc:
            raise CommandError(f"No such user: {username}") from exc

        start_time = time.time()
        try:
            result = load_learning_package(path, user=user, package_ref=package_ref)
        except RestoreFailedError as exc:
            # The archive is bad. Show every problem we found, not just the first.
            raise CommandError(exc.as_text()) from exc
        except BackupRestoreError as exc:
            raise CommandError(f"Failed to load '{path}': {exc}") from exc
        except Exception as exc:
            logger.exception("Failed to load archive %s", path)
            raise CommandError(f"Failed to load '{path}': {exc}") from exc

        duration = time.time() - start_time
        restored = result.lp_restored_data
        self.stdout.write(self.style.SUCCESS(
            f'{path} loaded successfully as "{restored.package_ref}" '
            f'(duration: {duration:.2f} seconds)'
        ))
