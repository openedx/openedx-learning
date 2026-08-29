"""
This module works with the actual files in our backup archive. It is agnostic to
the archive container format that the files are bundled in, e.g. a local file
system directory, a zip file archive, or something more exotic down the line.

The error checking here is for the file format itself, i.e. extracting values
from the TOML files and static assets and assembling them for validation.
"""

from __future__ import annotations

import os.path  # fsspec doesn't work well with Path objects.
import tomllib

import attrs
from fsspec import AbstractFileSystem
from fsspec.implementations.dirfs import DirFileSystem

from .errors import (
    DuplicateFoundError,
    ExtractionError,
    FieldMissing,
    FieldsNotInTable,
    InvalidTOMLError,
    MissingFileError,
    TableNotFoundError,
    UnsupportedFormatError,
)

ROOT_PACKAGE_PATH = "package.toml"

# Debris that archiving tools leave at the top level. These shouldn't count when
# we're working out whether an archive wraps its contents in a single folder.
# macOS's "Compress" in particular always adds __MACOSX, and often .DS_Store.
IGNORED_TOP_LEVEL_NAMES = frozenset({"__MACOSX"})


@attrs.define(frozen=True)
class UnvalidatedLearningPackageInput:
    """
    Everything we could pull out of an archive, before validation.

    ``raw_data`` is the assembled document we hand to pydantic.
    ``errors`` holds anything that stopped us assembling part of it.
    """

    raw_data: dict
    errors: list[ExtractionError]
    fs: AbstractFileSystem

    # Mapping of entity refs to the paths where we found them.
    entity_path_mapping: dict[str, str]

    # The folder inside the archive that we treated as the root, or None if the
    # archive's contents were at the top level. Every path in ``raw_data``,
    # ``entity_path_mapping`` and ``errors`` is relative to this, so it's only
    # useful for telling a human what we decided.
    root: str | None = None


def find_archive_root(
    fs: AbstractFileSystem,
    root_package_path: str = ROOT_PACKAGE_PATH,
) -> str | None:
    """
    Find the folder to treat as the archive root, or None to use ``fs`` as-is.

    People often build an archive by compressing a folder rather than that
    folder's contents, e.g. ``zip -r MyLib.zip MyLib/``. The result has a single
    top-level directory with everything (including package.toml) inside it. That
    is a reasonable thing to hand us, so we accept it.

    We only look one level down, and we require that the candidate directory
    actually contains a ``root_package_path``. That second condition matters more
    than it looks: without it, *any* archive whose top level happens to hold a
    single directory would be re-rooted into it.

    This function never raises. An archive with no package.toml anywhere returns
    None, and the missing file is reported later as an extraction error, which is
    where that error belongs.
    """
    if fs.exists(root_package_path):
        return None

    candidates = []
    # Note: this must be ls("") rather than ls("."), which returns [] on a
    # ZipFileSystem -- i.e. exactly the case we're here to handle.
    for entry in fs.ls("", detail=False):
        name = entry.rsplit("/", 1)[-1]
        if name in IGNORED_TOP_LEVEL_NAMES or name.startswith("."):
            continue
        if not fs.isdir(entry):
            continue
        if fs.exists(f"{entry}/{root_package_path}"):
            candidates.append(entry)

    # More than one candidate is ambiguous, and guessing would be worse than
    # saying we couldn't find the file.
    if len(candidates) == 1:
        return candidates[0]

    return None


class PayloadExtractor:
    """
    Extracts files from a file system and generates unvalidated input.

    We scan through the archive and compile a Python dictionary that can be
    validated against CompletePackageInputData. This mostly involves reading a
    bunch of TOML-serialized files and copying their contents, with some minor
    data transformations where idiomatic TOML doesn't really give the structure
    we want in our final model.

    The purpose of this abstraction is to later allow different ways to assemble
    the JSON that we want to do our validation on. By default, this is a bunch
    of TOML files, but folks who have specialized authoring needs may prefer a
    different set of conventions. For instance, the MIT Disciplinary Experts in
    Learning Technology and Applications team prefers to author in a way that
    encodes large parts of the hierarchy (Section -> Subsection -> Unit) in a
    single file, with pointers to certain Components in different files. Such a
    team would subclass this and override the handful of methods that know about
    where files live and how they're shaped.

    Errors can happen at this layer, but they are errors related to the
    consistency of the archive payload format itself. So errors that need to be
    checked here are things like:

    * Missing critical files, like package.toml
    * Duplicated entity files, as this is not possible to represent in the
      CompletePackageInputData schema.

    Things like missing fields and incorrect field values will be handled at the
    validation step which happens after this. In other words, the only things
    that are errors here are the things that prevent us from creating a
    UnvalidatedLearningPackageInput at all.
    """

    # Declared as a class attribute so that a subclass using a different layout
    # can point it somewhere else.
    root_package_path = ROOT_PACKAGE_PATH

    def __init__(self, fs: AbstractFileSystem):
        self.source_fs = fs
        self.root = find_archive_root(fs, self.root_package_path)

        # Re-rooting with a DirFileSystem means nothing below this line has to
        # know whether the archive wrapped its contents in a folder: every path
        # we read or report is relative to self.fs either way.
        self.fs = DirFileSystem(path=self.root, fs=fs) if self.root else fs

    def extract(self) -> UnvalidatedLearningPackageInput:
        """
        Read the whole archive, gathering errors rather than raising them.
        """
        # The general philosophy here is to always march on and get as much as
        # possible, even if we know the upload is doomed.
        unvalidated: dict = {}
        errors: list[ExtractionError] = []

        # Root Package Metadata
        try:
            # This adds the "meta" and "learning_package" keys
            unvalidated |= self.extract_root_package_data()
        except ExtractionError as err:
            errors.append(err)

        # PublishableEntities & versions (components, units, sections, subsections)
        entities_data, entity_path_mapping, entities_errors = self.extract_entities_data(
            self.get_entity_file_paths()
        )
        unvalidated["entities"] = entities_data
        errors.extend(entities_errors)

        # Collections. Note that duplicate Collection keys are *not* checked
        # here: unlike entities, collections are assembled into a list, so a
        # duplicate loses no data at this layer. It's caught during validation by
        # CompletePackageInputData.check_for_duplicate_keys, which can give a
        # better message because it has both files' data by then.
        collections = []
        for collection_file_path in self.get_collection_file_paths():
            try:
                collections.append(self.extract_collection_data(collection_file_path))
            except ExtractionError as err:
                errors.append(err)
        unvalidated["collections"] = collections

        return UnvalidatedLearningPackageInput(
            raw_data=unvalidated,
            errors=errors,
            # This must be the re-rooted filesystem, because the "fs:" static
            # asset pointers we write below are relative to it.
            fs=self.fs,
            entity_path_mapping=entity_path_mapping,
            root=self.root,
        )

    def extract_root_package_data(self, path: str | None = None) -> dict:
        """
        Extract the "meta" and "learning_package" from the TOML file at path.

        This is a straightforward extraction because we don't have to transform the
        actual fields in the data. We expect to see a TOML file that looks something
        like this:

            [meta]
            format_version = 1
            created_by = "eddy"
            created_by_email = "eddy@axim.org"
            created_at = 2026-03-11T19:20:20.394360Z
            origin_server = "studio.local.openedx.io"

            [learning_package]
            title = "Fun Library"
            key = "lib:Axim:FunLib"
            description = "My very fun library! 🐢"
            created = 2026-02-11T16:32:47.524556Z
            updated = 2026-02-20T16:32:47.524556Z

        The output should look like:

            {
                'meta': {
                    'format_version': 1,
                    'created_by': 'eddy',
                    'created_by_email': 'eddy@axim.org',
                    'created_at': datetime(2026, 3, 11, 19, 20, 20, 394360, tzinfo=timezone.utc),
                    'origin_server': 'studio.local.openedx.io'
                },
                'learning_package': {
                    'title': 'Fun Library',
                    'key': 'lib:Axim:FunLib',
                    'description': 'My very fun library! 🐢',
                    'created': datetime(2026, 2, 11, 16, 32, 47, 524556, tzinfo=timezone.utc),
                    'updated': datetime(2026, 2, 20, 16, 32, 47, 524556, tzinfo=timezone.utc),
                }
            }

        We need to return a Python dict that we get from parsing this. Most of this
        method is error handling. The error checking at this layer is minimal, and
        is mostly focused on making sure that the file exists, is parseable, and has
        the two tables we expect it to have.
        """
        file_description = "Root Package"
        if path is None:
            path = self.root_package_path

        # Check: Root Package file exists at all.
        if not self.fs.exists(path):
            raise MissingFileError(file_description, path=path)

        root_package_dict = self._load_toml(path, file_description)

        # Check: Don't allow top-level fields outside a [table]
        self._check_all_fields_in_tables(root_package_dict, file_description, path)

        # Check: The "[meta]" and "[learning_package]" tables are mandatory
        if "meta" not in root_package_dict:
            raise TableNotFoundError(file_description, table="meta", path=path)
        if "learning_package" not in root_package_dict:
            raise TableNotFoundError(
                file_description, table="learning_package", path=path
            )

        # Check: We only support format_version 1, and don't know what to do with
        # anything higher. This leaves us some wiggle-room to declare a 1.x version
        # that is backwards compatible, i.e. it will reject 2 and higher, but accept
        # 1.1, 1.2, etc.
        format_version = root_package_dict["meta"].get("format_version")
        is_number = isinstance(format_version, (int, float)) and not isinstance(
            format_version, bool
        )
        if not is_number or format_version >= 2:
            raise UnsupportedFormatError(
                f"Format version {format_version} is unsupported (only 1 is supported).",
                path=path,
            )

        return root_package_dict

    def get_entity_file_paths(self) -> list[str]:
        """
        Find all the PublishableEntity TOML file paths in our archive.

        We expect our entity TOML files to be in the entities directory, but we have
        two categories right now:

        * Component TOML: entities/xblock.v1/{component_type}/{component_code}
        * Container TOML: entities/{entity_ref}

        This method looks for TOML files in entities/ or any of its subdirs. We
        only exclude matches inside the component_version data, to make sure that we
        don't accidentally match media files in the unlikely event where people have
        TOML files as static assets.
        """
        paths = [
            path
            for path in self.fs.glob("entities/**/*.toml")
            # Filter out TOML files that are in component media, e.g. static assets:
            if "/component_versions/" not in path
        ]
        return sorted(paths)  # Make the ordering deterministic.

    def get_collection_file_paths(self) -> list[str]:
        """
        Find all the Collection TOML file paths in our archive.
        """
        return sorted(self.fs.glob("collections/*.toml"))

    def extract_entities_data(self, paths: list[str]):
        """
        Extract every entity file, collecting errors instead of raising them.

        Returns a ``(entities_data, entity_path_mapping, errors)`` tuple. The
        path mapping lets later stages report errors against the file an entity
        came from, which is not derivable from the entity ref.

        Duplicate detection lives here rather than in ``extract_entity_data``
        because it's a property of the *set* of files, not of any one file.
        """
        entities_data: dict[str, dict] = {}
        entity_path_mapping: dict[str, str] = {}
        errors: list[ExtractionError] = []
        for entity_file_path in paths:
            try:
                entity_ref, entity_data = self.extract_entity_data(entity_file_path)

                # Check: Is it a duplicate of an Entity that has already been
                # defined elsewhere in this archive? Without this, the second
                # definition would silently overwrite the first, which would be
                # baffling to someone assembling an archive by hand.
                if entity_ref in entity_path_mapping:
                    raise DuplicateFoundError(
                        f"Entity key {entity_ref}",
                        entity_path_mapping[entity_ref],
                        entity_file_path,
                    )

                entities_data[entity_ref] = entity_data
                entity_path_mapping[entity_ref] = entity_file_path
            except ExtractionError as err:
                errors.append(err)

        return entities_data, entity_path_mapping, errors

    def extract_entity_data(self, path: str) -> tuple[str, dict]:
        """
        This extracts raw entity data from an Entity TOML file.

        PublishableEntities can be both Components (XBlock problems, videos, etc.),
        as well as Containers like Units, Subsections, and Sections. Some sample
        TOML:

            [entity]
            can_stand_alone = true
            key = "section-9-ac4b9f"
            created = 2026-04-08T15:22:12.780012Z

            [entity.draft]
            version_num = 2

            [entity.published]
            version_num = 1

            [entity.container.section]

            # ### Versions

            [[version]]
            title = "Section 9"
            version_num = 2

            [version.container]
            children = ["week-7-e73782", "subsection-001-e4bbe5"]

            [[version]]
            title = "Section 9"
            version_num = 1

            [version.container]
            children = ["week-7-e73782"]

        We return a tuple where the first element is the Entity's key
        ("section-9-ac4b9f"), and the second is a dict that would look like:

        {
            'can_stand_alone': True,
            'created': datetime(2026, 4, 8, 15, 22, 12, 780012, tzinfo=timezone.utc),
            'draft': {
                'version_num': 2
            },
            'published': {
                'version_num': 1
            },
            'container': {
                'section': {}
            },
            'versions': [
                {
                    'title': 'Section 9',
                    'version_num': 2,
                    'container': {
                        'children': [
                            'week-7-e73782',
                            'subsection-001-e4bbe5'
                        ]
                    }
                },
                {
                    'title': 'Section 9',
                    'version_num': 1,
                    'container': {
                        'children': [
                            'week-7-e73782'
                        ]
                    }
                }
            ]
        }

        Note some key differences:

        1. The "entity" table elements have been popped out to the top level.
        2. The "version" list has been renamed to "versions" to feel more natural.
        3. The "key" field (a.k.a. entity_ref) has been popped out to pass back as
           part of the tuple. This will become a key/value pair in an "entities"
           dict that will hold all publishable entity input data.
        """
        file_description = "Entity"

        entity_root_dict = self._load_toml(path, file_description)

        # Check: Don't allow top-level fields outside a [table]
        self._check_all_fields_in_tables(entity_root_dict, file_description, path)

        # Check: Does it define a top level "[entity]" table? Note that this can
        # pass if they define a sub-table like "[entity.draft]", since the existence
        # of "[entity]" is implicit in that case. If we get that far, rely on
        # catching it at the validation step (i.e. after payload extraction).
        if "entity" not in entity_root_dict:
            raise TableNotFoundError(file_description, "entity", path=path)

        # Check: Does it define an Entity key (i.e. entity_ref)? We need to check
        # this now because the dict we have to assemble will use these as keys.
        entity = entity_root_dict["entity"]
        entity_ref = entity.pop("key", None)
        if not entity_ref:
            raise FieldMissing(file_description, "entity", "key", path)

        # Note case difference: we're renaming "version" in the TOML to "versions"
        # in the data dict we're assembling.
        entity["versions"] = entity_root_dict.pop("version", [])
        for version in entity["versions"]:
            self._add_component_version_media(version, path)

        return entity_ref, entity

    def extract_collection_data(self, path: str) -> dict:
        """
        Extract the contents of a single Collection TOML file.

        We record the source path on the way out, so that a later duplicate-key
        error can name both of the files involved.
        """
        file_description = "Collection"

        collection_root_dict = self._load_toml(path, file_description)

        self._check_all_fields_in_tables(collection_root_dict, file_description, path)
        if "collection" not in collection_root_dict:
            raise TableNotFoundError(file_description, table="collection", path=path)

        collection_data = collection_root_dict["collection"]
        collection_data["src_path"] = path

        return collection_data

    def _add_component_version_media(self, version: dict, entity_path: str) -> None:
        """
        Attach a Component version's media, if this version has any on disk.

        Do our best to put together entity version data (and component version
        data), but don't worry about validating the results (that can happen
        during the validation step).
        """
        version_num = version.get("version_num")
        comp_ver_dir = os.path.join(
            os.path.splitext(entity_path)[0],
            "component_versions",
            f"v{version_num}",
        )
        if not self.fs.exists(comp_ver_dir):
            return

        media = {
            os.path.relpath(media_path, comp_ver_dir): self.fs.read_text(media_path)
            for media_path in self.fs.glob(f"{comp_ver_dir}/*")
            if self.fs.isfile(media_path)
        }
        # Any static files are encoded as pointers.
        # TODO: Convert this to data-urls later
        for static_file_path in self.fs.glob(f"{comp_ver_dir}/static/**"):
            if self.fs.isfile(static_file_path):
                rel_path = os.path.relpath(static_file_path, comp_ver_dir)
                media[rel_path] = f"fs:{static_file_path}"

        version["component"] = {"media": media}

    def _load_toml(self, path: str, file_description: str) -> dict:
        """
        Parse the TOML file at ``path``, or raise InvalidTOMLError.
        """
        with self.fs.open(path, "rb") as toml_file:
            try:
                return tomllib.load(toml_file)
            except tomllib.TOMLDecodeError as dec_err:
                raise InvalidTOMLError(
                    file_description, details=str(dec_err), path=path
                ) from dec_err

    @staticmethod
    def _check_all_fields_in_tables(data: dict, file_description: str, path: str):
        """
        Raise an error if fields are declared outside of a table.

        The convention for our TOML files is that keys are always in a table, so if
        it's *not* in a table, that's likely an omission/error that might otherwise
        be difficult to catch because they'd be "missing" from the place they're
        supposed to be in the parsed data structure, but that wouldn't be obvious to
        someone editing the files by hand.
        """
        fields_outside_of_tables = [
            field
            for field, val in data.items()
            if not isinstance(val, dict) and not isinstance(val, list)
        ]
        if fields_outside_of_tables:
            raise FieldsNotInTable(
                file_description, fields=fields_outside_of_tables, path=path
            )
