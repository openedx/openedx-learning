"""
The values we hand back after restoring a Learning Package from an archive.

These live in their own module (rather than next to either the reading or the
writing code) because both the archive format and the database models change
independently of the summary we report to callers.

TODO: ``RestoreResult`` and friends are shaped by what the frontend currently
expects, not by what's natural here. When we revisit the REST API, the loader
should return something structured and let ``api.py`` do the translation.
"""
from __future__ import annotations

import time
from dataclasses import dataclass
from datetime import datetime
from io import StringIO
from typing import Literal

from django.contrib.auth.models import User as UserType  # pylint: disable=imported-auth-user


@dataclass
class RestoreLearningPackageData:
    """
    Data about the restored learning package.
    """
    id: int  # The ID of the restored learning package
    package_ref: str  # The package_ref of the restored learning package (may be different if staged)
    archive_package_ref: str  # The original package_ref from the archive
    archive_org_code: str | None  # The org code parsed from archive_package_ref, or None if unparseable
    archive_package_code: str | None  # The package code parsed from archive_package_ref, or None if unparseable
    title: str
    num_containers: int
    num_sections: int
    num_subsections: int
    num_units: int
    num_components: int
    num_collections: int


@dataclass
class BackupMetadata:
    """
    Metadata about the backup operation.
    """
    format_version: int
    created_at: datetime | str | None
    created_by: str | None = None
    created_by_email: str | None = None
    original_server: str | None = None


@dataclass
class RestoreResult:
    """
    Result of the restore operation.
    """
    status: Literal["success", "error"]
    log_file_error: StringIO | None = None
    lp_restored_data: RestoreLearningPackageData | None = None
    backup_metadata: BackupMetadata | None = None


def unpack_package_ref(package_ref: str) -> tuple[str | None, str | None]:
    """
    Try to parse org_code and package_code from a package_ref.

    By convention, package_refs take the form ``"{prefix}:{org_code}:{package_code}"``,
    but this is only a convention — package_ref is opaque and the parse may fail.
    Returns ``(None, None)`` if the ref does not match the expected format.
    """
    parts = package_ref.split(":")
    if len(parts) < 3:
        return None, None
    _, org_code, package_code = parts[:3]
    return org_code, package_code


def generate_staged_package_ref(archive_package_ref: str, user: UserType) -> str:
    """
    Generate a staged learning package ref based on the archive's package_ref.

    We can't trust package_ref from the archive directly, because the archive
    could specify *any* arbitrary package_ref, and the user may or may not be
    permitted to create an Package using that ref. So, instead, this function
    generates a unique and semi-human-readable package_ref which is namespaced
    to the current user and appropriate to provisionally save the package under.
    The package_ref from the archive can then be presented to the user as a
    *suggestion*, which they may or may not choose to use.

    Please note that the ref returned by this function is valid for Packages is
    a generic sense, but it's not a valid Content Library key.  Callers who are
    restoring a Package for Library usage will need to replace this staged
    package_ref before being able to render the Library's content.

    Arguments:
        archive_package_ref (str): The original package_ref from the archive.
        user (UserType | None): The user performing the restore operation.

    Example:
        Input:  "lib:WGU:LIB_C001"
        Output: "lp-restore:dave:WGU:LIB_C001:1728575321"
    """
    username = user.username
    org_code, package_code = unpack_package_ref(archive_package_ref)
    timestamp = int(time.time() * 1000)  # Current time in milliseconds
    if org_code and package_code:
        return f"lp-restore:{username}:{org_code}:{package_code}:{timestamp}"
    # Fallback for non-conventional package_refs
    return f"lp-restore:{username}:{archive_package_ref}:{timestamp}"
