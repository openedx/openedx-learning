"""
Backup Restore API

This module is responsible for creating a backup archive of a Learning Package,
as well as creating a new Learning Package based on a backup archive file.
"""
from dataclasses import asdict
from datetime import datetime, timezone
from io import StringIO

from django.contrib.auth.models import User as UserType  # pylint: disable=imported-auth-user
from django.db.transaction import atomic

from ..publishing import api as publishing_api
from . import archive, loading, payload, validation
from .errors import BackupRestoreError, RestoreFailedError
from .results import RestoreResult, generate_staged_package_ref
from .zipper import LearningPackageZipper

__all__ = [
    "create_zip_file",
    "create_learning_package",
    "load_learning_package",
]


def create_learning_package(
    path_str: str,
    user: UserType,
    package_ref: str | None = None,
) -> RestoreResult:
    """
    Loads a learning package from a file system at the given path.

    The ``path_str`` will usually point to a Zip file archive that holds the
    backup of the Learning Package data. For testing and debugging purposes, you
    can also specify ``path_str`` to be the root directory of an unzipped
    version of the archive data.

    The overall pipeline looks like this:

      archive.py: Archive location (Path) → FileSystem (fsspec)
      payload.py: FileSystem (fsspec) → UnvalidatedLearningPackageInput
      validation.py: UnvalidatedLearningPackageInput → ValidatedLearningPackageInput
      loading.py: ValidatedLearningPackageInput → LearningPackage

    If ``package_ref`` is not supplied, we generate a staged one namespaced to
    ``user``. We can't just use the ref from the archive, because the archive
    can claim any ref it likes and the user may not be allowed to create it.

    Errors that can be raised:

    * ``ArchiveNotReadableError`` if we can't open ``path_str`` at all.
    * ``RestoreFailedError`` if the archive's contents don't validate. Nothing
      is written to the database in that case.

    Both descend from ``BackupRestoreError``.
    """
    fs = archive.read_fs_for_path(path_str)
    unvalidated_input = payload.extract_unvalidated_learning_package(fs)
    validated_input = validation.validate(unvalidated_input)

    # Bail out before touching the database. We deliberately don't do a partial
    # restore: a half-loaded Learning Package is harder to reason about than no
    # Learning Package at all.
    if validated_input.errors:
        raise RestoreFailedError(validated_input.errors)

    loader = loading.Loader(validated_input)
    archive_lp_input = loader.data.learning_package  # LearningPackageInputData
    if package_ref is None:
        package_ref = generate_staged_package_ref(archive_lp_input.key, user)

    now = datetime.now(tz=timezone.utc)
    with atomic(savepoint=False):
        learning_package = publishing_api.create_learning_package(
            package_ref,
            archive_lp_input.title,
            description=archive_lp_input.description or "",
            created=archive_lp_input.created or now,
        )
        load_target = loading.Loader.Target(learning_package, user, now)
        result = loader.load_into(load_target)

    return result


def load_learning_package(
    path_str: str,
    user: UserType,
    package_ref: str | None = None,
) -> dict:
    """
    ``create_learning_package``, in the dict shape that 1.0 clients expect.

    Returns a dict with the status of the operation and any errors encountered
    during that process, rather than raising.

    TODO: This exists so that callers written against the pre-pydantic restore
    keep working. New callers should use ``load_learning_package`` and catch
    ``BackupRestoreError``, so that this can eventually go away.
    """
    try:
        result = create_learning_package(path_str, user, package_ref)
    except RestoreFailedError as err:
        return asdict(
            RestoreResult(status="error", log_file_error=StringIO(err.as_text()))
        )
    except BackupRestoreError as err:
        return asdict(
            RestoreResult(status="error", log_file_error=StringIO(f"{err}\n"))
        )

    return asdict(result)


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
