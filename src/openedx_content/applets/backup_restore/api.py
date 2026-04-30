"""
Backup Restore API
"""
import zipfile

from django.contrib.auth.models import User as UserType  # pylint: disable=imported-auth-user

from ..publishing.api import get_learning_package_by_ref
from .zipper import LearningPackageUnzipper, LearningPackageZipper

# The public API that will be re-exported by openedx_content.api
# is listed in the __all__ entries below. Internal helper functions that are
# private to this module should start with an underscore. If a function does not
# start with an underscore AND it is not in __all__, that function is considered
# to be callable only by other applets in the openedx_content package.
__all__ = [
    "create_zip_file",
    "load_learning_package",
]


def create_zip_file(
        package_ref: str, path: str, user: UserType | None = None, origin_server: str | None = None
) -> None:
    """
    Creates a dump zip file for the given learning package key at the given path.
    The zip file contains a TOML representation of the learning package and its contents.

    Can throw a NotFoundError at get_learning_package_by_ref
    """
    learning_package = get_learning_package_by_ref(package_ref)
    LearningPackageZipper(learning_package, user, origin_server).create_zip(path)


def load_learning_package(path: str, package_ref: str | None = None, user: UserType | None = None) -> dict:
    """
    Loads a learning package from a zip file at the given path.
    Restores the learning package and its contents to the database.
    Returns a dictionary with the status of the operation and any errors encountered.
    """
    with zipfile.ZipFile(path, "r") as zipf:
        return LearningPackageUnzipper(zipf, package_ref, user).load()
