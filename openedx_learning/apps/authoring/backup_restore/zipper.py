"""
This module provides functionality to create a zip file containing the learning package data,
including a TOML representation of the learning package and its entities.
"""
import zipfile
from pathlib import Path

from openedx_learning.apps.authoring.backup_restore.toml import toml_learning_package, toml_publishable_entity
from openedx_learning.apps.authoring.publishing import api as publishing_api
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
        package_toml_content: str = toml_learning_package(self.learning_package)

        with zipfile.ZipFile(path, "w", compression=zipfile.ZIP_DEFLATED) as zipf:
            # Add the package.toml string
            zipf.writestr(TOML_PACKAGE_NAME, package_toml_content)

            # Add the entities directory
            entities_folder = Path("entities")
            zip_info = zipfile.ZipInfo(str(entities_folder) + "/")  # Ensure trailing slash
            zipf.writestr(zip_info, "")  # Add explicit empty directory entry

            # Add the collections directory
            collections_folder = Path("collections")
            collections_info = zipfile.ZipInfo(str(collections_folder) + "/")  # Ensure trailing slash
            zipf.writestr(collections_info, "")  # Add explicit empty directory

            # Add each entity's TOML file
            for entity in publishing_api.get_entities(self.learning_package.pk):
                # Entity it is a PublishableEntity type

                # Create a TOML representation of the entity
                entity_toml_content: str = toml_publishable_entity(entity)
                entity_toml_filename = f"{entity.key}.toml"
                entity_toml_path = entities_folder / entity_toml_filename
                zipf.writestr(str(entity_toml_path), entity_toml_content)
