"""
Backup Restore API
"""
from openedx_learning.apps.authoring.backup_restore.zipper import LearningPackageUnzipper, LearningPackageZipper
from openedx_learning.apps.authoring.publishing.api import get_learning_package_by_key


def create_zip_file(lp_key: str, path: str) -> None:
    """
    Creates a zip file with a toml file so far (WIP)

    Can throw a NotFoundError at get_learning_package_by_key
    """
    learning_package = get_learning_package_by_key(lp_key)
    LearningPackageZipper(learning_package).create_zip(path)


def extract_zip_file(path: str) -> None:
    """
    Extracts a zip file (WIP)
    """
    LearningPackageUnzipper().extract_zip(path)
