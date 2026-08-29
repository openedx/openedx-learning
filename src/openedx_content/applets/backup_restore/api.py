"""
Backup Restore API

This module is responsible for creating a backup archive of a Learning Package,
as well as creating a new Learning Package based on a backup archive file.
"""
from datetime import datetime, timezone

import attrs
from django.contrib.auth.models import User as UserType  # pylint: disable=imported-auth-user
from django.db.transaction import atomic

from ..publishing import api as publishing_api
from . import archive, loading, payload, validation


from .zipper import LearningPackageZipper, generate_staged_package_ref


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

    The overall pipeline looks like this:

        Archive location (Path) →
        FileSystem (fsspec) →
        UnvalidatedLearningPackageInput →
        ValidatedLearningPackageInput →
        LearningPackage

    Loads a learning package from a zip file at the given path. Restores the
    learning package and its contents to the database.

    Returns a dictionary with the status of the operation and any errors
    encountered during that process.
    """
    fs = archive.read_fs_for_path(path_str)
    unvalidated_input = payload.extract_unvalidated_learning_package(fs)

    # TODO: need to be able to exit early here if errors make the rest of this
    # pointless. The Loader class currently knows how to make output that we can
    # send up to platform, but maybe that knowledge should be in this module
    # instead?
    # if unvalidated_input.errors:
    validated_input = validation.validate(unvalidated_input)

    if package_ref is None:
        package_ref = generate_staged_package_ref(
            validated_input.data.learning_package.key, user,
        )

    loader = loading.Loader(validated_input)
    now = datetime.now(tz=timezone.utc)
    with atomic(savepoint=False):
        learning_package = publishing_api.create_learning_package(
            package_ref, "Temp Title", created=now
        )
        load_target = loading.Loader.Target(learning_package, user, now)
        result = loader.load_into(load_target)

    return result


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

    Can throw a NotFoundError at get_learning_package_by_ref
    """
    learning_package = publishing_api.get_learning_package_by_ref(lp_key)
    LearningPackageZipper(learning_package, user, origin_server).create_zip(path)
