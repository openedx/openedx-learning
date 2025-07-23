"""
This module provides functionality to create a zip file containing the learning package data,
including a TOML representation of the learning package and its entities.
"""
import zipfile
from pathlib import Path

from openedx_learning.apps.authoring.backup_restore.toml import (
    TOMLLearningPackageFile,
    TOMLPublishableEntityFile,
    TOMLPublishableEntityVersionFile,
)
from openedx_learning.apps.authoring.components import api as components_api
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
        package_toml_content: str = package_toml_file.get()

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
            for entity in components_api.get_components(self.learning_package.pk):
                # Create a TOML representation of the entity
                entity_toml = TOMLPublishableEntityFile(entity)
                entity_toml.create()

                for entity_version in entity.versioning.versions.all():
                    # Create a TOML representation of the entity version
                    entity_version_toml = TOMLPublishableEntityVersionFile(
                        entity_version, entity_toml.aot, entity_toml.get_document()
                    )
                    entity_version_toml.create()

                entity_toml.add_versions_to_document()
                entity_toml_content = entity_toml.get()
                entity_toml_filename = f"{entity.key}.toml"
                entity_toml_path = entities_folder / entity_toml_filename
                zipf.writestr(str(entity_toml_path), entity_toml_content)
