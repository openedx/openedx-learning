"""
This module works with the actual files in our backup archive. It is agnostic to
the archive container format that the files are bundled in, e.g. a local file
system directory, a zip file archive, or something more exotic down the line.

Some high level considerations for this module:

1. The error checking is for the file format itself, i.e. extracting  values
   from the TOML files and statica assets and assembling them for validation.
   In some cases, this means we do have to look for particular fields to handle
"""

from __future__ import annotations
from numbers import Number
import os.path  # fsspec doesn't work well with Path objects.
import tomllib

import attrs
from fsspec import AbstractFileSystem

ROOT_PACKAGE_PATH = "package.toml"


@attrs.define(frozen=True)
class UnvalidatedLearningPackageInput:
    raw_data: dict
    errors: list[ExtractionError]
    fs: AbstractFileSystem

    # Mapping of entity refs to the paths where we found them.
    entity_path_mapping: dict[str, str]


class ExtractionError(Exception):
    """
    Any error during the extraction process.

    At the moment, any error is fatal. The point of the different errors is to
    provide useful debug logging and to let us write tests that look for
    specific errors.
    """

    def __init__(self, message, path=None):
        super().__init__(message)
        self.message = message
        self.path = path

    def __str__(self):
        return f"{self.path}: {self.message}"


class InvalidTOMLError(ExtractionError):
    def __init__(self, file_description, details, path):
        message = f"Cannot decode TOML for {file_description}: {details}"
        super().__init__(message, path=path)


class TableNotFoundError(ExtractionError):
    def __init__(self, file_description, table, path):
        self.table = table
        message = f"Table [{table}] not found in {file_description}."
        super().__init__(message, path=path)


class FieldsNotInTable(ExtractionError):
    def __init__(self, file_description, fields, path):
        self.fields = sorted(fields)
        message = f"{file_description} has fields not in a table: {', '.join(fields)}"
        super().__init__(message, path=path)


class FieldMissing(ExtractionError):
    def __init__(self, file_description, table, missing_field, path):
        self.table = table
        self.missing_field = missing_field
        message = (
            f'{file_description} is missing required field "{missing_field}" '
            f"from table [{table}]"
        )
        super().__init__(message, path=path)


class FileNotFoundError(ExtractionError):
    def __init__(self, file_description, path):
        message = f"{file_description} file not found at expected path"
        super().__init__(message, path=path)


class DuplicateFoundError(ExtractionError):
    def __init__(self, description, original_path, path):
        self.original_path = original_path
        message = f"{description} already defined in {original_path}"
        super().__init__(message, path=path)


class UnsupportedFormatError(ExtractionError):
    pass


def extract_unvalidated_learning_package(
    fs: AbstractFileSystem,
) -> UnvalidatedLearningPackageInput:
    """
    Extract the raw, unvalidated Learning Package metadata.

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
    single file, with pointers to certain Components in different files.

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
    # The general philosophy here is to always march on and get as much as
    # possible, even if we know the upload is doomed.
    unvalidated = {}
    errors = []

    # Root Package Metadata
    try:
        # This adds the "meta" and "learning_package" keys
        unvalidated |= extract_root_package_data(fs, ROOT_PACKAGE_PATH)
    except ExtractionError as err:
        errors.append(err)

    # PublishableEntities & versions (components, units, sections, subsections)
    entities_data, entity_path_mapping, entities_errors = extract_entities_data(
        fs, get_entity_file_paths(fs)
    )
    unvalidated["entities"] = entities_data
    errors.extend(entities_errors)

    # Collections
    # TODO: Duplicate collections are a problem too.
    collections = []
    for collection_file_path in sorted(fs.glob("collections/*.toml")):
        try:
            collections.append(extract_collection_data(fs, collection_file_path))
        except ExtractionError as err:
            errors.append(err)
    unvalidated["collections"] = collections

    return UnvalidatedLearningPackageInput(
        raw_data=unvalidated,
        errors=errors,
        fs=fs,
        entity_path_mapping=entity_path_mapping,
    )


def extract_root_package_data(fs: AbstractFileSystem, path: str) -> dict:
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
    function is error handling. The error checking at this layer is minimal, and
    is mostly focused on making sure that the file exists, is parseable, and has
    the two tables we expect it to have.
    """
    file_description = "Root Package"

    # Check: Root Package file exists at all.
    if not fs.exists(path):
        raise FileNotFoundError(file_description, path=path)

    # Check: Is it a valid TOML file?
    with fs.open(path, "rb") as package_toml_file:
        try:
            root_package_dict = tomllib.load(package_toml_file)
        except tomllib.TOMLDecodeError as dec_err:
            raise InvalidTOMLError(
                file_description, details=str(dec_err), path=path
            ) from dec_err

    # Check: Don't allow top-level fields outside a [table]
    _check_all_fields_in_tables(root_package_dict, file_description, path)

    # Check: The "[meta]" and "[learning_package]" tables are mandatory
    if "meta" not in root_package_dict:
        raise TableNotFoundError(file_description, table="meta", path=path)
    if "learning_package" not in root_package_dict:
        raise TableNotFoundError(file_description, table="learning_package", path=path)

    # Check: We only support format_version 1, and don't know what to do with
    # anything higher. This leaves us some wiggle-room to declare a 1.x version
    # that is backwards compatible, i.e. it will reject 2 and higher, but accept
    # 1.1, 1.2, etc.
    format_version = root_package_dict["meta"].get("format_version")
    if not isinstance(format_version, Number) or format_version >= 2:
        raise UnsupportedFormatError(
            f"Format version {format_version} is unsupported (only 1 is supported).",
            path=path,
        )

    return root_package_dict


def get_entity_file_paths(fs: AbstractFileSystem) -> list[str]:
    """
    Find all the PublishableEntity TOML file paths in our archive.

    We expect our entity TOML files to be in the entities directory, but we have
    two categories right now:

    * Component TOML: entities/xblock.v1/{component_type}/{component_code}
    * Container TOML: entities/{entity_ref}

    This function looks for TOML files in entities/ or any of its subdirs. We
    only exclude matches inside the component_version data, to make sure that we
    don't accidentally match media files in the unlikely event where people have
    TOML files as static assets.
    """
    paths = [
        path
        for path in fs.glob("entities/**/*.toml")
        # Filter out TOML files that are in component media, e.g. static assets:
        if "/component_versions/" not in path
    ]
    return sorted(paths)  # Make the ordering deterministic.


def extract_entities_data(fs: AbstractFileSystem, paths: list[str]):
    entities_data = {}
    entity_path_mapping = {}
    errors = []
    for entity_file_path in paths:
        try:
            entity_ref, entity_data = extract_entity_data(
                fs, entity_file_path, entity_path_mapping
            )
            entities_data[entity_ref] = entity_data
            entity_path_mapping[entity_ref] = entity_file_path
        except ExtractionError as err:
            errors.append(err)

    return entities_data, entity_path_mapping, errors


def extract_entity_data(
    fs: AbstractFileSystem, path: str, entity_path_mapping: dict[str, str] | None = None
) -> tuple[str, dict]:
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
    if entity_path_mapping is None:
        entity_path_mapping = {}

    # Check: Is it a valid TOML file?
    with fs.open(path, "rb") as entity_file:
        try:
            entity_root_dict = tomllib.load(entity_file)
        except tomllib.TOMLDecodeError as dec_err:
            raise InvalidTOMLError(
                file_description, details=str(dec_err), path=path
            ) from dec_err

    # Check: Don't allow top-level fields outside a [table]
    _check_all_fields_in_tables(entity_root_dict, file_description, path)

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

    # Check: Is it a duplicate of an Entity that has already been defined
    # elsewhere in this archive?
    if entity_ref in entity_path_mapping:
        raise DuplicateFoundError(
            f"Entity key {entity_ref}", entity_path_mapping[entity_ref], path
        )

    # Note case difference: we're renaming "version" in the TOML to "versions"
    # in the data dict we're assembling.
    entity["versions"] = entity_root_dict.pop("version", [])
    for version in entity["versions"]:
        # Do our best to put together entity version data (and component version
        # data), but don't worry about validating the results (that can happen
        # during the validation step).
        version_num = version.get("version_num")
        comp_ver_dir = os.path.join(
            os.path.splitext(path)[0],
            "component_versions",
            f"v{version_num}",
        )
        if fs.exists(comp_ver_dir):
            version["component"] = {}
            media = {
                os.path.relpath(path, comp_ver_dir): fs.read_text(path)
                for path in fs.glob(f"{comp_ver_dir}/*")
                if fs.isfile(path)
            }
            # Any static files are encoded as pointers.
            # TODO: Convert this to data-urls later
            for static_file_path in fs.glob(f"{comp_ver_dir}/static/**"):
                if fs.isfile(static_file_path):
                    rel_path = os.path.relpath(static_file_path, comp_ver_dir)
                    media[rel_path] = f"fs:{static_file_path}"

            version["component"]["media"] = media

    return entity_ref, entity


def extract_collection_data(fs: AbstractFileSystem, path: str) -> dict:
    file_description = "Collection"

    with fs.open(path, "rb") as collection_toml_file:
        try:
            collection_root_dict = tomllib.load(collection_toml_file)
        except tomllib.TOMLDecodeError as dec_err:
            raise InvalidTOMLError(file_description, details=str(dec_err), path=path)

    _check_all_fields_in_tables(collection_root_dict, file_description, path)
    if "collection" not in collection_root_dict:
        raise TableNotFoundError(
            file_description, table="collection", path=path
        )

    collection_data = collection_root_dict["collection"]
    collection_data["src_path"] = path

    return collection_data


def _check_all_fields_in_tables(data: dict, file_description, path):
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


def pretty_print(obj):
    from pydantic import TypeAdapter
    from typing import Any
    from rich import print_json

    print_json(TypeAdapter(Any).dump_json(obj, indent=2).decode("utf8"))
