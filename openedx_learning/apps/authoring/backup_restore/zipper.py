"""
This module provides functionality to create a zip file containing the learning package data,
including a TOML representation of the learning package and its entities.
"""
import hashlib
import zipfile
from collections import defaultdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, List, Optional, Tuple, TypedDict

from django.db import transaction
from django.db.models import Prefetch, QuerySet
from django.utils.text import slugify
from rest_framework import serializers

from openedx_learning.api.authoring_models import (
    Collection,
    ComponentType,
    ComponentVersion,
    ComponentVersionContent,
    Content,
    LearningPackage,
    PublishableEntity,
    PublishableEntityVersion,
)
from openedx_learning.apps.authoring.backup_restore.serializers import (
    CollectionSerializer,
    ComponentSerializer,
    ComponentVersionSerializer,
    ContainerSerializer,
    ContainerVersionSerializer,
)
from openedx_learning.apps.authoring.backup_restore.toml import (
    parse_collection_toml,
    parse_learning_package_toml,
    parse_publishable_entity_toml,
    toml_collection,
    toml_learning_package,
    toml_publishable_entity,
)
from openedx_learning.apps.authoring.collections import api as collections_api
from openedx_learning.apps.authoring.components import api as components_api
from openedx_learning.apps.authoring.publishing import api as publishing_api
from openedx_learning.apps.authoring.sections import api as sections_api
from openedx_learning.apps.authoring.subsections import api as subsections_api
from openedx_learning.apps.authoring.units import api as units_api

TOML_PACKAGE_NAME = "package.toml"


class ComponentDefaults(TypedDict):
    content_to_replace: dict[str, int | bytes | None]
    created: datetime
    created_by: Optional[int]


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
            publishable_entities  # type: ignore[no-redef]
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


class LearningPackageUnzipper:
    """
    Handles extraction and restoration of learning package data from a zip archive.

    Responsibilities:
      - Parse and organize files from the zip structure.
      - Restore learning package, containers, components, and collections to the database.
      - Ensure atomicity of the restore process.

    Usage:
        unzipper = LearningPackageUnzipper()
        summary = unzipper.load("/path/to/backup.zip")
    """

    def __init__(self) -> None:
        self.utc_now: datetime = datetime.now(tz=timezone.utc)
        self.component_types_cache: dict[tuple[str, str], ComponentType] = {}
        self.errors: list[dict[str, Any]] = []
        # Maps for resolving relationships
        self.components_map_by_key: dict[str, Any] = {}
        self.units_map_by_key: dict[str, Any] = {}
        self.subsections_map_by_key: dict[str, Any] = {}
        self.sections_map_by_key: dict[str, Any] = {}
        self.all_publishable_entities_keys: set[str] = set()

    # --------------------------
    # Public API
    # --------------------------

    @transaction.atomic
    def load(self, zipf: zipfile.ZipFile) -> dict[str, Any]:
        """Extracts and restores all objects from the ZIP archive in an atomic transaction."""
        organized_files = self._get_organized_file_list(zipf.namelist())

        if not organized_files["learning_package"]:
            raise FileNotFoundError(f"Missing required {TOML_PACKAGE_NAME} in archive.")

        learning_package = self._load_learning_package(zipf, organized_files["learning_package"])
        components_validated = self._extract_entities(
            zipf, organized_files["components"], ComponentSerializer, ComponentVersionSerializer
        )
        containers_validated = self._extract_entities(
            zipf, organized_files["containers"], ContainerSerializer, ContainerVersionSerializer
        )

        collections_validated = self._extract_collections(
            zipf, organized_files["collections"]
        )

        self._write_errors()
        if not self.errors:
            self._save(learning_package, components_validated, containers_validated, collections_validated)

        return {
            "learning_package": learning_package.key,
            "containers": len(organized_files["containers"]),
            "components": len(organized_files["components"]),
            "collections": len(organized_files["collections"]),
        }

    # --------------------------
    # Extract + Validate
    # --------------------------

    def _extract_entities(
        self,
        zipf: zipfile.ZipFile,
        entity_files: list[str],
        entity_serializer: type[serializers.Serializer],
        version_serializer: type[serializers.Serializer],
    ) -> dict[str, Any]:
        """Generic extraction + validation pipeline for containers or components."""
        results: dict[str, list[Any]] = defaultdict(list)

        for file in entity_files:
            if not file.endswith(".toml"):
                # Skip non-TOML files
                continue

            entity_data, draft_version, published_version = self._load_entity_data(zipf, file)
            serializer = entity_serializer(
                data={"created": self.utc_now, "created_by": None, **entity_data}
            )

            if not serializer.is_valid():
                self.errors.append({"file": file, "errors": serializer.errors})
                continue

            entity_data = serializer.validated_data
            self.all_publishable_entities_keys.add(entity_data["key"])
            entity_type = entity_data.pop("container_type", "components")
            results[entity_type].append(entity_data)

            valid_versions = self._validate_versions(
                entity_data,
                draft_version,
                published_version,
                version_serializer,
                file=file
            )
            if valid_versions["draft"]:
                results[f"{entity_type}_drafts"].append(valid_versions["draft"])
            if valid_versions["published"]:
                results[f"{entity_type}_published"].append(valid_versions["published"])

        return results

    def _extract_collections(
        self,
        zipf: zipfile.ZipFile,
        collection_files: list[str],
    ) -> dict[str, Any]:
        """Extraction + validation pipeline for collections."""
        results: dict[str, list[Any]] = defaultdict(list)

        for file in collection_files:
            if not file.endswith(".toml"):
                # Skip non-TOML files
                continue
            toml_content = self._read_file_from_zip(zipf, file)
            collection_data = parse_collection_toml(toml_content)
            serializer = CollectionSerializer(data={"created_by": None, **collection_data})
            if not serializer.is_valid():
                self.errors.append({"file": file, "errors": serializer.errors})
                continue
            collection_validated = serializer.validated_data
            entities_list = collection_validated["entities"]
            for entity_key in entities_list:
                if entity_key not in self.all_publishable_entities_keys:
                    self.errors.append({
                        "file": file,
                        "errors": f"Entity key {entity_key} not found for collection {collection_validated.get('key')}"
                    })
            results["collections"].append(collection_validated)

        return results

    # --------------------------
    # Save Logic
    # --------------------------

    def _save(
        self,
        learning_package: LearningPackage,
        components: dict[str, Any],
        containers: dict[str, Any],
        collections: dict[str, Any]
    ) -> None:
        """Persist all validated entities in two phases: published then drafts."""

        with publishing_api.bulk_draft_changes_for(learning_package.id):
            self._save_components(learning_package, components)
            self._save_units(learning_package, containers)
            self._save_subsections(learning_package, containers)
            self._save_sections(learning_package, containers)
            self._save_collections(learning_package, collections)
            publishing_api.publish_all_drafts(learning_package.id)

        with publishing_api.bulk_draft_changes_for(learning_package.id):
            self._save_draft_versions(components, containers)

    def _save_collections(self, learning_package, collections):
        """Save collections and their entities."""
        for valid_collection in collections.get("collections", []):
            entities = valid_collection.pop("entities", [])
            collection = collections_api.create_collection(learning_package.id, **valid_collection)
            collection = collections_api.add_to_collection(
                learning_package_id=learning_package.id,
                key=collection.key,
                entities_qset=publishing_api.get_publishable_entities(learning_package.id).filter(key__in=entities)
            )  # type: ignore[arg-type]

    def _save_components(self, learning_package, components):
        """Save components and published component versions."""
        for valid_component in components.get("components", []):
            entity_key = valid_component.pop("key")
            component = components_api.create_component(learning_package.id, **valid_component)
            self.components_map_by_key[entity_key] = component

        for valid_published in components.get("components_published", []):
            entity_key = valid_published.pop("entity_key")
            components_api.create_next_component_version(
                self.components_map_by_key[entity_key].publishable_entity.id,
                **valid_published
            )

    def _save_units(self, learning_package, containers):
        """Save units and published unit versions."""
        for valid_unit in containers.get("unit", []):
            entity_key = valid_unit.get("key")
            unit = units_api.create_unit(learning_package.id, **valid_unit)
            self.units_map_by_key[entity_key] = unit

        for valid_published in containers.get("unit_published", []):
            entity_key = valid_published.pop("entity_key")
            children = self._resolve_children(valid_published, self.components_map_by_key)
            units_api.create_next_unit_version(
                self.units_map_by_key[entity_key], components=children, **valid_published
            )

    def _save_subsections(self, learning_package, containers):
        """Save subsections and published subsection versions."""
        for valid_subsection in containers.get("subsection", []):
            entity_key = valid_subsection.get("key")
            subsection = subsections_api.create_subsection(learning_package.id, **valid_subsection)
            self.subsections_map_by_key[entity_key] = subsection

        for valid_published in containers.get("subsection_published", []):
            entity_key = valid_published.pop("entity_key")
            children = self._resolve_children(valid_published, self.units_map_by_key)
            subsections_api.create_next_subsection_version(
                self.subsections_map_by_key[entity_key], units=children, **valid_published
            )

    def _save_sections(self, learning_package, containers):
        """Save sections and published section versions."""
        for valid_section in containers.get("section", []):
            entity_key = valid_section.get("key")
            section = sections_api.create_section(learning_package.id, **valid_section)
            self.sections_map_by_key[entity_key] = section

        for valid_published in containers.get("section_published", []):
            entity_key = valid_published.pop("entity_key")
            children = self._resolve_children(valid_published, self.subsections_map_by_key)
            sections_api.create_next_section_version(
                self.sections_map_by_key[entity_key], subsections=children, **valid_published
            )

    def _save_draft_versions(self, components, containers):
        """Save draft versions for all entity types."""
        for valid_draft in components.get("components_drafts", []):
            entity_key = valid_draft.pop("entity_key")
            components_api.create_next_component_version(
                self.components_map_by_key[entity_key].publishable_entity.id,
                **valid_draft
            )

        for valid_draft in containers.get("unit_drafts", []):
            entity_key = valid_draft.pop("entity_key")
            children = self._resolve_children(valid_draft, self.components_map_by_key)
            units_api.create_next_unit_version(
                self.units_map_by_key[entity_key], components=children, **valid_draft
            )

        for valid_draft in containers.get("subsection_drafts", []):
            entity_key = valid_draft.pop("entity_key")
            children = self._resolve_children(valid_draft, self.units_map_by_key)
            subsections_api.create_next_subsection_version(
                self.subsections_map_by_key[entity_key], units=children, **valid_draft
            )

        for valid_draft in containers.get("section_drafts", []):
            entity_key = valid_draft.pop("entity_key")
            children = self._resolve_children(valid_draft, self.subsections_map_by_key)
            sections_api.create_next_section_version(
                self.sections_map_by_key[entity_key], subsections=children, **valid_draft
            )

    # --------------------------
    # Utilities
    # --------------------------

    def _write_errors(self) -> str | None:
        """
        Writes restore errors to a timestamped log file and prints them to console.

        Args:
            errors (list[dict]): List of {"file": ..., "errors": ...} dicts.
            log_dir (str): Directory to save the log file (default current dir).
        """
        errors = self.errors
        if not errors:
            return None

        # Create timestamped log filename
        timestamp = datetime.now().strftime("%Y-%m-%d_%H-%M-%S")
        log_filename = f"restore_{timestamp}.log"

        # Format each error on a separate line
        lines = [f"{err['file']}: {err['errors']}" for err in errors]
        content = "Errors encountered during restore:\n" + "\n".join(lines) + "\n"

        # Write to file
        with open(log_filename, "w", encoding="utf-8") as f:
            f.write(content)

        return log_filename

    def _resolve_children(self, entity_data: dict[str, Any], lookup_map: dict[str, Any]) -> list[Any]:
        """Resolve child entity keys into model instances."""
        children_keys = entity_data.pop("children", [])
        return [lookup_map[key] for key in children_keys if key in lookup_map]

    def _load_learning_package(self, zipf: zipfile.ZipFile, package_file: str) -> LearningPackage:
        """Load and persist the learning package TOML file."""
        toml_content = self._read_file_from_zip(zipf, package_file)
        data = parse_learning_package_toml(toml_content)
        return publishing_api.create_learning_package(
            key=data["key"],
            title=data["title"],
            description=data["description"],
        )

    def _load_entity_data(
        self, zipf: zipfile.ZipFile, entity_file: str
    ) -> tuple[dict[str, Any], dict[str, Any] | None, dict[str, Any] | None]:
        """Load entity data and its versions from TOML."""
        content = self._read_file_from_zip(zipf, entity_file)
        entity_data, version_data = parse_publishable_entity_toml(content)
        return entity_data, *self._get_versions_to_write(version_data, entity_data)

    def _validate_versions(self, entity_data, draft, published, serializer_cls, *, file) -> dict[str, Any]:
        """Validate draft/published versions with serializer."""
        valid = {"draft": None, "published": None}
        for label, version in [("draft", draft), ("published", published)]:
            if not version:
                continue
            serializer = serializer_cls(
                data={
                    "entity_key": entity_data["key"],
                    "content_to_replace": {},
                    "created": self.utc_now,
                    "created_by": None,
                    **version
                }
            )
            if serializer.is_valid():
                valid[label] = serializer.validated_data
            else:
                self.errors.append({"file": file, "errors": serializer.errors})
        return valid

    def _read_file_from_zip(self, zipf: zipfile.ZipFile, filename: str) -> str:
        """Read and decode a UTF-8 file from the zip archive."""
        with zipf.open(filename) as f:
            return f.read().decode("utf-8")

    def _get_organized_file_list(self, file_paths: list[str]) -> dict[str, Any]:
        """Organize file paths into categories: learning_package, containers, components, collections."""
        organized: dict[str, Any] = {
            "learning_package": None,
            "containers": [],
            "components": [],
            "collections": [],
        }

        for path in file_paths:
            if path.endswith("/"):
                continue
            if path == TOML_PACKAGE_NAME:
                organized["learning_package"] = path
            elif path.startswith("entities/") and str(Path(path).parent) == "entities":
                organized["containers"].append(path)
            elif path.startswith("entities/"):
                organized["components"].append(path)
            elif path.startswith("collections/"):
                organized["collections"].append(path)

        return organized

    def _get_versions_to_write(
        self,
        version_data: list[dict[str, Any]],
        entity_data: dict[str, Any]
    ) -> tuple[Optional[dict[str, Any]], Optional[dict[str, Any]]]:
        """Return the draft and published versions to write, based on entity data."""
        draft_num = entity_data.get("draft", {}).get("version_num")
        published_num = entity_data.get("published", {}).get("version_num")
        lookup = {v.get("version_num"): v for v in version_data}
        return (
            lookup.get(draft_num) if draft_num else None,
            lookup.get(published_num) if published_num else None,
        )
