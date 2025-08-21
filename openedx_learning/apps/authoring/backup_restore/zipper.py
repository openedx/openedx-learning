"""
This module provides functionality to create a zip file containing the learning package data,
including a TOML representation of the learning package and its entities.
"""
import zipfile
from pathlib import Path
from typing import Optional

from openedx_learning.apps.authoring.backup_restore.toml import toml_learning_package, toml_publishable_entity
from openedx_learning.apps.authoring.publishing import api as publishing_api
from openedx_learning.apps.authoring.publishing.models import LearningPackage, PublishableEntityVersion

TOML_PACKAGE_NAME = "package.toml"


class LearningPackageZipper:
    """
    A class to handle the zipping of learning content for backup and restore.
    """

    def __init__(self, learning_package: LearningPackage):
        self.learning_package = learning_package
        self.folders_already_created: set[Path] = set()

    def create_folder(self, folder_path: Path, zip_file: zipfile.ZipFile) -> None:
        """
        Create a folder for the zip file structure.
        Skips creating the folder if it already exists based on the folder path.
        Args:
            folder_path (Path): The path of the folder to create.
        """
        if folder_path not in self.folders_already_created:
            zip_info = zipfile.ZipInfo(str(folder_path) + "/")
            zip_file.writestr(zip_info, "")  # Add explicit empty directory entry
            self.folders_already_created.add(folder_path)

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
            self.create_folder(entities_folder, zipf)

            # Add the collections directory
            collections_folder = Path("collections")
            self.create_folder(collections_folder, zipf)

            # Add each entity's TOML file
            for entity in publishing_api.get_publishable_entities(self.learning_package.pk):
                # entity: PublishableEntity = entity  # Type hint for clarity

                # Create a TOML representation of the entity
                entity_toml_content: str = toml_publishable_entity(entity)

                if hasattr(entity, 'container'):
                    entity_toml_filename = f"{entity.key}.toml"
                    entity_toml_path = entities_folder / entity_toml_filename
                    zipf.writestr(str(entity_toml_path), entity_toml_content)

                if hasattr(entity, 'component'):
                    # Create the component folder structure for the entity. The structure is as follows:
                    # entities/
                    #     xblock.v1/  (component namespace)
                    #         html/  (component type)
                    #             my_component.toml  (entity TOML file)
                    #             my_component/  (component id)
                    #                 component_versions/
                    #                     v1/
                    #                         static/

                    component_namespace_folder = entities_folder / entity.component.component_type.namespace
                    # Example of component namespace is: "xblock.v1"
                    self.create_folder(component_namespace_folder, zipf)

                    component_type_folder = component_namespace_folder / entity.component.component_type.name
                    # Example of component type is: "html"
                    self.create_folder(component_type_folder, zipf)

                    component_id_folder = component_type_folder / entity.component.local_key  # entity.key
                    # Example of component id is: "i-dont-like-the-sidebar-aa1645ade4a7"
                    self.create_folder(component_id_folder, zipf)

                    # Add the entity TOML file inside the component type folder as well
                    component_entity_toml_path = component_type_folder / f"{entity.component.local_key}.toml"
                    zipf.writestr(str(component_entity_toml_path), entity_toml_content)

                    # Add component version folder into the component id folder
                    component_version_folder = component_id_folder / "component_versions"
                    self.create_folder(component_version_folder, zipf)

                    # ------ COMPONENT VERSIONING -------------
                    # Focusing on draft and published versions

                    # Get the draft and published versions
                    draft_version: Optional[PublishableEntityVersion] = publishing_api.get_draft_version(entity)
                    published_version: Optional[PublishableEntityVersion] = publishing_api.get_published_version(entity)

                    versions_to_write = [draft_version] if draft_version else []

                    if published_version and published_version != draft_version:
                        versions_to_write.append(published_version)

                    for version in versions_to_write:
                        # Create a folder for the version
                        version_number = f"v{version.version_num}"
                        version_folder = component_version_folder / version_number
                        self.create_folder(version_folder, zipf)

                        # Add static folder for the version
                        static_folder = version_folder / "static"
                        self.create_folder(static_folder, zipf)
