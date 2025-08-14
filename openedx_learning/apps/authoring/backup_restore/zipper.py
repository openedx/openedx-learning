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

    def create_folder(self, folder_path: Path, zip_file: zipfile.ZipFile) -> None:
        """
        Create a folder for the zip file structure.
        Args:
            folder_path (Path): The path of the folder to create.
        """
        zip_info = zipfile.ZipInfo(str(folder_path) + "/")
        zip_file.writestr(zip_info, "")  # Add explicit empty directory entry

    def create_zip(self, path: str) -> None:
        """
        Creates a zip file containing the learning package data.
        Args:
            path (str): The path where the zip file will be created.
        Raises:
            Exception: If the learning package cannot be found or if the zip creation fails.
        """
        package_toml_content: str = toml_learning_package(self.learning_package)
        folders_already_created = set()

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
            for entity in publishing_api.get_entities(self.learning_package.pk):
                # entity: PublishableEntity = entity  # Type hint for clarity

                # Create a TOML representation of the entity
                entity_toml_content: str = toml_publishable_entity(entity)
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
                    if component_namespace_folder not in folders_already_created:
                        self.create_folder(component_namespace_folder, zipf)
                        folders_already_created.add(component_namespace_folder)

                    component_type_folder = component_namespace_folder / entity.component.component_type.name
                    # Example of component type is: "html"
                    if component_type_folder not in folders_already_created:
                        self.create_folder(component_type_folder, zipf)
                        folders_already_created.add(component_type_folder)

                    component_id_folder = component_type_folder / entity.component.local_key  # entity.key
                    # Example of component id is: "i-dont-like-the-sidebar-aa1645ade4a7"
                    if component_id_folder not in folders_already_created:
                        self.create_folder(component_id_folder, zipf)
                        folders_already_created.add(component_id_folder)

                    # Add the entity TOML file inside the component type folder as well
                    component_entity_toml_path = component_type_folder / f"{entity.component.local_key}.toml"
                    zipf.writestr(str(component_entity_toml_path), entity_toml_content)

                    # Add component version folder into the component id folder
                    component_version_folder = component_id_folder / "component_versions"
                    if component_version_folder not in folders_already_created:
                        self.create_folder(component_version_folder, zipf)
                        folders_already_created.add(component_version_folder)

                    for entity_version in entity.component.versions.all():
                        component_number_version_folder = component_version_folder / f"v{entity_version.version_num}"
                        # Create a folder for each version of the component. Example: "v1", "v2", etc.
                        if component_number_version_folder not in folders_already_created:
                            self.create_folder(component_number_version_folder, zipf)
                            folders_already_created.add(component_number_version_folder)

                        # Add the static folder inside the component version folder
                        static_folder = component_number_version_folder / "static"
                        if static_folder not in folders_already_created:
                            self.create_folder(static_folder, zipf)
                            folders_already_created.add(static_folder)
