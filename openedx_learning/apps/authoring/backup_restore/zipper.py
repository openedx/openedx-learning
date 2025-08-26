"""
This module provides functionality to create a zip file containing the learning package data,
including a TOML representation of the learning package and its entities.
"""
import hashlib
import zipfile
from pathlib import Path
from typing import Optional

from django.db.models import QuerySet
from django.utils.text import slugify

from openedx_learning.apps.authoring.backup_restore.toml import toml_learning_package, toml_publishable_entity
from openedx_learning.apps.authoring.components.models import ComponentVersion, ComponentVersionContent
from openedx_learning.apps.authoring.publishing import api as publishing_api
from openedx_learning.apps.authoring.publishing.models import (
    LearningPackage,
    PublishableEntity,
    PublishableEntityVersion,
)

TOML_PACKAGE_NAME = "package.toml"


def slugify_hashed_filename(identifier: str) -> str:
    """
    Generate a filesystem-safe filename from an identifier.

    Why:
        Identifiers may contain characters that are invalid or ambiguous
        in filesystems (e.g., slashes, colons, case differences).
        Additionally, two different identifiers might normalize to the same
        slug after cleaning. To avoid collisions and ensure uniqueness,
        we append a short blake2b hash.

    What:
        - Slugify the identifier (preserves most characters, only strips
          filesystem-invalid ones).
        - Append a short hash for uniqueness.
        - Result: human-readable but still unique and filesystem-safe filename.
    """
    slug = slugify(identifier, allow_unicode=True)
    # Short digest ensures uniqueness without overly long filenames
    short_hash = hashlib.blake2b(
        identifier.encode("utf-8"),
        digest_size=3,
    ).hexdigest()
    return f"{slug}_{short_hash}"


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
        lp_id = self.learning_package.pk

        with zipfile.ZipFile(path, "w", compression=zipfile.ZIP_DEFLATED) as zipf:
            # Add the package.toml file
            package_toml_content: str = toml_learning_package(self.learning_package)
            zipf.writestr(TOML_PACKAGE_NAME, package_toml_content)

            # Add the entities directory
            entities_folder = Path("entities")
            self.create_folder(entities_folder, zipf)

            # Add the collections directory
            collections_folder = Path("collections")
            self.create_folder(collections_folder, zipf)

            # ------ ENTITIES SERIALIZATION -------------

            # get the publishable entities
            publishable_entities: QuerySet[PublishableEntity] = publishing_api.get_publishable_entities(lp_id)
            publishable_entities = publishable_entities.select_related("container", "component__component_type")

            for entity in publishable_entities:
                # entity: PublishableEntity = entity  # Type hint for clarity

                # Create a TOML representation of the entity
                entity_toml_content: str = toml_publishable_entity(entity)

                if hasattr(entity, 'container'):
                    entity_slugify_hash = slugify_hashed_filename(entity.key)
                    entity_toml_filename = f"{entity_slugify_hash}.toml"
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

                    # Generate the slugified hash for the component local key
                    # Example: if the local key is "my_component", the slugified hash might be "my_component_123456"
                    # It's a combination of the local key and a hash and should be unique
                    entity_slugify_hash = slugify_hashed_filename(entity.component.local_key)

                    # Create the component namespace folder
                    # Example of component namespace is: "entities/xblock.v1/"
                    component_namespace_folder = entities_folder / entity.component.component_type.namespace
                    self.create_folder(component_namespace_folder, zipf)

                    # Create the component type folder
                    # Example of component type is: "entities/xblock.v1/html/"
                    component_type_folder = component_namespace_folder / entity.component.component_type.name
                    self.create_folder(component_type_folder, zipf)

                    # Create the component id folder
                    # Example of component id is: "entities/xblock.v1/html/my_component_123456/"
                    component_id_folder = component_type_folder / entity_slugify_hash
                    self.create_folder(component_id_folder, zipf)

                    # Add the entity TOML file inside the component type folder as well
                    # Example: "entities/xblock.v1/html/my_component_123456.toml"
                    component_entity_toml_path = component_type_folder / f"{entity_slugify_hash}.toml"
                    zipf.writestr(str(component_entity_toml_path), entity_toml_content)

                    # Add component version folder into the component id folder
                    # Example: "entities/xblock.v1/html/my_component_123456/component_versions/"
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

                        # ------ COMPONENT STATIC CONTENT -------------
                        # Get component version
                        component_version: ComponentVersion = version.componentversion

                        # Get content data associated with this version
                        # content_list: QuerySet[Content] = component_version.contents.all()
                        content_list: QuerySet[ComponentVersionContent] = component_version.componentversioncontent_set.all()  # pylint: disable=line-too-long  # noqa: E501

                        for component_version_content in content_list:
                            content = component_version_content.content

                            if content.has_file and content.path:
                                # Add the file to the static folder
                                # file_path = static_folder / content.path
                                file_path = static_folder / component_version_content.key
                                with content.read_file() as f:
                                    file_data = f.read()
                                    zipf.writestr(str(file_path), file_data)
                            elif not content.has_file and content.text:
                                # Create file for the text file according to the mime_type attr
                                text_file_path = static_folder / component_version_content.key
                                zipf.writestr(str(text_file_path), content.text)
