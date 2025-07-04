"""
Backup Restore API
"""
import zipfile

from openedx_learning.apps.authoring.backup_restore.constants import TOML_PACKAGE_NAME
from openedx_learning.apps.authoring.backup_restore.utils import LpTomlFile


def create_zip_file(lp_key: str, path: str) -> None:
    """
    Creates a zip file with a toml file so far (WIP)
    """
    toml_file = LpTomlFile()
    toml_file.create(lp_key)
    toml_content: str = toml_file.get()
    with zipfile.ZipFile(path, "w", compression=zipfile.ZIP_DEFLATED) as zipf:
        # Add the TOML string as a file in the ZIP
        zipf.writestr(TOML_PACKAGE_NAME, toml_content)
