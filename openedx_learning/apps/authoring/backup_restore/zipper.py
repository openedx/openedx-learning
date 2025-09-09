"""
This module provides functionality to create a zip file containing the learning package data,
including a TOML representation of the learning package and its entities.
"""
import hashlib
import zipfile
from datetime import datetime, timezone
from pathlib import Path
from typing import List, Optional, Tuple

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
        self.entities_filenames_already_created: set[str] = set()
        self.utc_now = datetime.now(tz=timezone.utc)

    def _ensure_parent_folders(
        self,
        zip_file: zipfile.ZipFile,
        path: Path,
        timestamp: datetime,
    ) -> None:
        """
        Ensure all parent folders for the given path exist in the zip.
        """
        for parent in path.parents[::-1]:
            if parent != Path(".") and parent not in self.folders_already_created:
                folder_info = zipfile.ZipInfo(str(parent) + "/")
                folder_info.date_time = timestamp.timetuple()[:6]
                zip_file.writestr(folder_info, "")
                self.folders_already_created.add(parent)

    def add_folder_to_zip(
        self,
        zip_file: zipfile.ZipFile,
        folder: Path,
        timestamp: datetime | None = None,
    ) -> None:
        """
        Explicitly add an empty folder into the zip structure.
        """
        if folder in self.folders_already_created:
            return

        if timestamp is None:
            timestamp = self.utc_now

        self._ensure_parent_folders(zip_file, folder, timestamp)

        folder_info = zipfile.ZipInfo(str(folder) + "/")
        folder_info.date_time = timestamp.timetuple()[:6]
        zip_file.writestr(folder_info, "")
        self.folders_already_created.add(folder)

    def add_file_to_zip(
        self,
        zip_file: zipfile.ZipFile,
        file_path: Path,
        content: bytes | str | None = None,
        timestamp: datetime | None = None,
    ) -> None:
        """
        Add a file into the zip structure.
        """
        if timestamp is None:
            timestamp = self.utc_now

        self._ensure_parent_folders(zip_file, file_path, timestamp)

        file_info = zipfile.ZipInfo(str(file_path))
        file_info.date_time = timestamp.timetuple()[:6]

        if isinstance(content, str):
            content = content.encode("utf-8")

        zip_file.writestr(file_info, content or b"")

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
            .order_by("key")
        )

    def get_collections(self) -> QuerySet[Collection]:
        """
        Get the collections associated with the learning package.
        """
        return (
            collections_api.get_collections(self.learning_package.pk)
            .prefetch_related("entities")
        )

    def get_versions_to_write(
            self, entity: PublishableEntity
        ) -> Tuple[List[PublishableEntityVersion],
                   Optional[PublishableEntityVersion],
                   Optional[PublishableEntityVersion]]:
        """
        Get the versions of a publishable entity that should be written to the zip file.
        It retrieves both draft and published versions.

        Returns:
            Tuple containing:
            - versions_to_write: List of PublishableEntityVersion to write.
            - draft_version: The current draft version, if any.
            - published_version: The current published version, if any.
        """
        draft_version: Optional[PublishableEntityVersion] = publishing_api.get_draft_version(entity)
        published_version: Optional[PublishableEntityVersion] = publishing_api.get_published_version(entity)

        versions_to_write = [draft_version] if draft_version else []

        if published_version and published_version != draft_version:
            versions_to_write.append(published_version)
        return versions_to_write, draft_version, published_version

    def get_entity_toml_filename(self, entity_key: str) -> str:
        """
        Generate a unique TOML filename for a publishable entity.
        Ensures that the filename is unique within the zip file.

        Behavior:
        - If the slugified key has not been used yet, use it as the filename.
        - If it has been used, append a short hash to ensure uniqueness.

        Args:
            entity_key (str): The key of the publishable entity.

        Returns:
            str: A unique TOML filename for the entity.
        """
        slugify_name = slugify(entity_key, allow_unicode=True)

        if slugify_name in self.entities_filenames_already_created:
            filename = slugify_hashed_filename(entity_key)
        else:
            filename = slugify_name

        self.entities_filenames_already_created.add(slugify_name)
        return filename

    def get_latest_modified(self, versions_to_check: List[PublishableEntityVersion]) -> datetime:
        """
        Get the latest modification timestamp among the learning package and its entities.
        """
        latest = self.learning_package.updated
        for version in versions_to_check:
            if version and version.created > latest:
                latest = version.created
        return latest

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
            package_toml_content: str = toml_learning_package(self.learning_package, self.utc_now)
            self.add_file_to_zip(zipf, Path(TOML_PACKAGE_NAME), package_toml_content, self.learning_package.updated)

            # Add the entities directory
            entities_folder = Path("entities")
            self.add_folder_to_zip(zipf, entities_folder, timestamp=self.learning_package.updated)

            # Add the collections directory
            collections_folder = Path("collections")
            self.add_folder_to_zip(zipf, collections_folder, timestamp=self.learning_package.updated)

            # ------ ENTITIES SERIALIZATION -------------

            # get the publishable entities
            publishable_entities: QuerySet[PublishableEntity] = self.get_publishable_entities()

            for entity in publishable_entities:
                # entity: PublishableEntity = entity  # Type hint for clarity

                # Get the versions to serialize for this entity
                versions_to_write, draft_version, published_version = self.get_versions_to_write(entity)

                latest_modified = self.get_latest_modified(versions_to_write)

                # Create a TOML representation of the entity
                entity_toml_content: str = toml_publishable_entity(
                    entity, versions_to_write, draft_version, published_version
                )

                if hasattr(entity, 'container'):
                    entity_filename = self.get_entity_toml_filename(entity.key)
                    entity_toml_filename = f"{entity_filename}.toml"
                    entity_toml_path = entities_folder / entity_toml_filename
                    self.add_file_to_zip(zipf, entity_toml_path, entity_toml_content, timestamp=latest_modified)

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

                    entity_filename = self.get_entity_toml_filename(entity.component.local_key)

                    component_root_folder = (
                        # Example: "entities/xblock.v1/html/"
                        entities_folder
                        / entity.component.component_type.namespace
                        / entity.component.component_type.name
                    )

                    component_folder = (
                        # Example: "entities/xblock.v1/html/my_component_123456/"
                        component_root_folder
                        / entity_filename
                    )

                    component_version_folder = (
                        # Example: "entities/xblock.v1/html/my_component_123456/component_versions/"
                        component_folder
                        / "component_versions"
                    )

                    # Add the entity TOML file inside the component type folder as well
                    # Example: "entities/xblock.v1/html/my_component_123456.toml"
                    component_entity_toml_path = component_root_folder / f"{entity_filename}.toml"
                    self.add_file_to_zip(zipf, component_entity_toml_path, entity_toml_content, latest_modified)

                    # ------ COMPONENT VERSIONING -------------
                    # Focusing on draft and published versions only
                    for version in versions_to_write:
                        # Create a folder for the version
                        version_number = f"v{version.version_num}"
                        version_folder = component_version_folder / version_number
                        self.add_folder_to_zip(zipf, version_folder, timestamp=version.created)

                        # Add static folder for the version
                        static_folder = version_folder / "static"
                        self.add_folder_to_zip(zipf, static_folder, timestamp=version.created)

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
                            self.add_file_to_zip(zipf, file_path, file_data, timestamp=content.created)

            # ------ COLLECTION SERIALIZATION -------------
            collections = self.get_collections()

            for collection in collections:
                collection_hash_slug = self.get_entity_toml_filename(collection.key)
                collection_toml_file_path = collections_folder / f"{collection_hash_slug}.toml"
                entity_keys_related = collection.entities.order_by("key").values_list("key", flat=True)
                self.add_file_to_zip(
                    zipf,
                    collection_toml_file_path,
                    toml_collection(collection, list(entity_keys_related)),
                    timestamp=collection.modified,
                )
