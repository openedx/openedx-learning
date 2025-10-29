"""
Backup Restore API
"""
import zipfile

from django.contrib.auth.models import User as UserType  # pylint: disable=imported-auth-user

from openedx_learning.apps.authoring.backup_restore.zipper import LearningPackageUnzipper, LearningPackageZipper
from openedx_learning.apps.authoring.publishing.api import get_learning_package_by_key


def create_zip_file(lp_key: str, path: str, user: UserType | None = None) -> None:
    """
    Creates a dump zip file for the given learning package key at the given path.
    The zip file contains a TOML representation of the learning package and its contents.

    Can throw a NotFoundError at get_learning_package_by_key
    """
    learning_package = get_learning_package_by_key(lp_key)
    LearningPackageZipper(learning_package, user).create_zip(path)


def load_learning_package(path: str, key: str | None = None, user: UserType | None = None) -> dict:
    """
    Loads a learning package from a zip file at the given path.
    Restores the learning package and its contents to the database.
    Returns a dictionary with the status of the operation and any errors encountered.
    """
    with zipfile.ZipFile(path, "r") as zipf:
        return LearningPackageUnzipper(zipf, key, user).load()
