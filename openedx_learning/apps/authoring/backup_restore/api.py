"""
Backup Restore API
"""
import zipfile

from openedx_learning.apps.authoring.backup_restore.zipper import LearningPackageUnzipper, LearningPackageZipper
from openedx_learning.apps.authoring.publishing.api import get_learning_package_by_key


def create_zip_file(lp_key: str, path: str) -> None:
    """
    Creates a dump zip file for the given learning package key at the given path.

    Can throw a NotFoundError at get_learning_package_by_key
    """
    learning_package = get_learning_package_by_key(lp_key)
    LearningPackageZipper(learning_package).create_zip(path)


def load_dump_zip_file(path: str) -> None:
    """
    Loads a zip file derived from create_zip_file
    """
    with zipfile.ZipFile(path, "r") as zipf:
        LearningPackageUnzipper().load(zipf)
