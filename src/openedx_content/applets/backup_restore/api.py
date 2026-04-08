"""
Backup Restore API

Archive → Filesystem → Learning Package Doc + Resources → Input Models → LearningPackage

Extract -> Validate -> Load


(FS + root) -> UnvalidatedLearningPackage -> ValidatedLearningPackageInput

"""
from datetime import datetime, timezone
from pathlib import Path

import attrs
from django.contrib.auth.models import User as UserType  # pylint: disable=imported-auth-user
from django.db.transaction import atomic
from fsspec.implementations.dirfs import DirFileSystem
from fsspec.implementations.zip import ZipFileSystem

from ..publishing import api as publishing_api
from .payload import extract_unvalidated_learning_package
from .loading import Loader
from .validation import validate
from .zipper import LearningPackageZipper, generate_staged_lp_key


@attrs.define(frozen=True)
class ImportResult:
    entities_created: int  # Should this be a list of entity refs instead?


def load_learning_package(
    path_str: str,
    user: UserType,
    package_ref: str | None = None,
) -> dict:
    """
    Loads a learning package from a zip file at the given path.

    Restores the learning package and its contents to the database.

    TODO: Returns a dictionary with the status of the operation and any errors encountered.

    Loads a learning package from a zip file at the given path.
    Restores the learning package and its contents to the database.
    Returns a dictionary with the status of the operation and any errors encountered.
    """
    fs = _fs_for_path(path_str)
    unvalidated_input = extract_unvalidated_learning_package(fs)

    # TODO: need to be able to exit early here if errors make the rest of this
    # pointless. The Loader class currently knows how to make output that we can
    # send up to platform, but maybe that knowledge should be in this module
    # instead?
    # if unvalidated_input.errors:

    validated_input = validate(unvalidated_input)

    if package_ref is None:
        package_ref = generate_staged_lp_key(
            validated_input.data.learning_package.key, user,
        )

    loader = Loader(validated_input)
    now = datetime.now(tz=timezone.utc)
    with atomic():
        learning_package = publishing_api.create_learning_package(
            package_ref, "Temp Title", created=now
        )
        load_target = Loader.Target(learning_package, user, now)
        result = loader.load_into(load_target)

    return result


def _fs_for_path(path_str: str):
    """
    If the path_str passed in is a directory, we treat that as the root of the
    archive to be restored. Otherwise, we assume you're passing a Zip file.

    For future consideration: Using LibArchiveFileSystem would allow us to
    support tar.gz, zip, 7z, and a bunch of other archiving formats in read-only
    mode. I'm not doing it now because I'm not clear on whether the reliance on
    libarchive makes things problematic, I don't understand the performance
    implications, and I don't want to open the door on "supported archive
    formats" to include everything under the sun. But it's an intriguing option
    to consider.
    """
    # TODO: Handling of the special types of path here
    path = Path(path_str)
    if path.is_dir():
        return DirFileSystem(path)
    elif path.is_file() and path.suffix.lower() == ".zip":
        return ZipFileSystem(path)

    raise ValueError(f"Could not load path {path_str}")




def pretty_print(obj):
    from pydantic import TypeAdapter
    from typing import Any
    from rich import print_json

    print_json(TypeAdapter(Any).dump_json(obj, indent=2).decode("utf8"))


### This was pre-existing:

def create_zip_file(
    lp_key: str,
    path: str,
    user: UserType | None = None,
    origin_server: str | None = None,
) -> None:
    """
    Creates a dump zip file for the given learning package key at the given path.
    The zip file contains a TOML representation of the learning package and its contents.

    This is used by lp_dump.

    Can throw a NotFoundError at get_learning_package_by_key
    """
    learning_package = publishing_api.get_learning_package_by_key(lp_key)
    LearningPackageZipper(learning_package, user, origin_server).create_zip(path)
