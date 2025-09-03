"""
This module provides functionality to create a zip file containing the learning package data,
including a TOML representation of the learning package and its entities.
"""
import hashlib
import zipfile
from pathlib import Path
from typing import List, Optional

from django.db.models import Prefetch, QuerySet
from django.utils.text import slugify

from openedx_learning.api.authoring_models import (
    Collection,
    ComponentVersion,
    ComponentVersionContent,
    Content,
    LearningPackage,
    PublishableEntity,
    PublishableEntityVersion,
)
from openedx_learning.apps.authoring.backup_restore.toml import (
    toml_collection,
    toml_learning_package,
    toml_publishable_entity,
)
from openedx_learning.apps.authoring.collections import api as collections_api
from openedx_learning.apps.authoring.publishing import api as publishing_api

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

    def get_publishable_entities(self) -> QuerySet[PublishableEntity]:
        """
        Retrieve the publishable entities associated with the learning package.
        Prefetches related data for efficiency.
        """
        lp_id = self.learning_package.pk
        publishable_entities: QuerySet[PublishableEntity] = publishing_api.get_publishable_entities(lp_id)
        return (
            publishable_entities
            .select_related(
                "container",
                "component__component_type",
                "draft__version__componentversion",
                "published__version__componentversion",
            )
            .prefetch_related(
                # We should re-evaluate the prefetching strategy here,
                # as the current approach may cause performance issues—
                # especially with large libraries (up to 100K items),
                # which is too large for this type of prefetch.
                Prefetch(
                    "draft__version__componentversion__componentversioncontent_set",
                    queryset=ComponentVersionContent.objects.select_related("content"),
                    to_attr="prefetched_contents",
                ),
                Prefetch(
                    "published__version__componentversion__componentversioncontent_set",
                    queryset=ComponentVersionContent.objects.select_related("content"),
                    to_attr="prefetched_contents",
                ),
            )
        )

    def get_collections(self) -> QuerySet[Collection]:
        """
        Get the collections associated with the learning package.
        """
        return (
            collections_api.get_collections(self.learning_package.pk)
            .prefetch_related("entities")
        )

    def get_versions_to_write(self, entity: PublishableEntity):
        """
        Get the versions of a publishable entity that should be written to the zip file.
        It retrieves both draft and published versions.
        """
        draft_version: Optional[PublishableEntityVersion] = publishing_api.get_draft_version(entity)
        published_version: Optional[PublishableEntityVersion] = publishing_api.get_published_version(entity)

        versions_to_write = [draft_version] if draft_version else []

        if published_version and published_version != draft_version:
            versions_to_write.append(published_version)
        return versions_to_write

    def create_zip(self, path: str) -> None:
        """
        Creates a zip file containing the learning package data.
        Args:
            path (str): The path where the zip file will be created.
        Raises:
            Exception: If the learning package cannot be found or if the zip creation fails.
        """

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
            publishable_entities: QuerySet[PublishableEntity] = self.get_publishable_entities()

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
                    versions_to_write: List[PublishableEntityVersion] = self.get_versions_to_write(entity)

                    for version in versions_to_write:
                        # Create a folder for the version
                        version_number = f"v{version.version_num}"
                        version_folder = component_version_folder / version_number
                        self.create_folder(version_folder, zipf)

                        # Add static folder for the version
                        static_folder = version_folder / "static"
                        self.create_folder(static_folder, zipf)

                        # ------ COMPONENT STATIC CONTENT -------------
                        component_version: ComponentVersion = version.componentversion

                        # Get content data associated with this version
                        contents: QuerySet[
                            ComponentVersionContent
                        ] = component_version.prefetched_contents  # type: ignore[attr-defined]

                        for component_version_content in contents:
                            content: Content = component_version_content.content

                            # Important: The component_version_content.key contains implicitly
                            # the file name and the file extension
                            file_path = version_folder / component_version_content.key

                            if content.has_file and content.path:
                                # If has_file, we pull it from the file system
                                with content.read_file() as f:
                                    file_data = f.read()
                            elif not content.has_file and content.text:
                                # Otherwise, we use the text content as the file data
                                file_data = content.text
                            else:
                                # If no file and no text, we skip this content
                                continue
                            zipf.writestr(str(file_path), file_data)

            # ------ COLLECTION SERIALIZATION -------------
            collections = self.get_collections()

            for collection in collections:
                collection_hash_slug = slugify_hashed_filename(collection.key)
                collection_toml_file_path = collections_folder / f"{collection_hash_slug}.toml"
                zipf.writestr(str(collection_toml_file_path), toml_collection(collection))
