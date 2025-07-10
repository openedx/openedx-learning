"""
Backup Restore API
"""
import zipfile

from openedx_learning.apps.authoring.publishing.api import get_learning_package_by_key

from .toml import TOMLLearningPackageFile

TOML_PACKAGE_NAME = "package.toml"


def create_zip_file(lp_key: str, path: str) -> None:
    """
    Creates a zip file with a toml file so far (WIP)

    Can throw a NotFoundError at get_learning_package_by_key
    """
    learning_package = get_learning_package_by_key(lp_key)
    toml_file = TOMLLearningPackageFile(learning_package)
    toml_file.create()
    toml_content: str = toml_file.get()
    with zipfile.ZipFile(path, "w", compression=zipfile.ZIP_DEFLATED) as zipf:
        # Add the TOML string as a file in the ZIP
        zipf.writestr(TOML_PACKAGE_NAME, toml_content)
