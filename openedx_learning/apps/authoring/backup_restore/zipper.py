"""
This module provides functionality to create a zip file containing the learning package data,
including a TOML representation of the learning package and its entities.
"""
import zipfile

from openedx_learning.apps.authoring.backup_restore.toml import TOMLLearningPackageFile, TOMLPublishableEntityFile
from openedx_learning.apps.authoring.publishing.models.learning_package import LearningPackage

TOML_PACKAGE_NAME = "package.toml"


class LearningPackageZipper:
    """
    A class to handle the zipping of learning content for backup and restore.
    """

    def __init__(self, learning_package: LearningPackage):
        self.learning_package = learning_package

    def create_zip(self, path: str) -> None:
        """
        Creates a zip file containing the learning package data.
        Args:
            path (str): The path where the zip file will be created.
        Raises:
            Exception: If the learning package cannot be found or if the zip creation fails.
        """
        package_toml_file = TOMLLearningPackageFile(self.learning_package)
        package_toml_file.create()
        packafe_toml_content: str = package_toml_file.get()

        with zipfile.ZipFile(path, "w", compression=zipfile.ZIP_DEFLATED) as zipf:
            # Add the package.toml string as a file in the ZIP
            zipf.writestr(TOML_PACKAGE_NAME, packafe_toml_content)

            # Add entities folder
            target_folder = "entities"
            zip_info = zipfile.ZipInfo(target_folder + '/')
            zipf.writestr(zip_info, '')

            # Add the entities
            for entity in self.learning_package.component_set.all():
                entity_toml = TOMLPublishableEntityFile(entity)
                entity_toml.create()
                entity_toml_content = entity_toml.get()
                filename = f"{entity.key}.toml"
                arcname = f"{target_folder.rstrip('/')}/{filename}"
                zipf.writestr(arcname, entity_toml_content)
