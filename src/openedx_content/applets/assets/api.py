"""
Assets API, for assets shared by multiple entities in the Learning Package.

Please look at the models.py file for more information about the kinds of data
stored in this app.
"""

from __future__ import annotations

import logging
import mimetypes
from datetime import datetime, timezone

from django.core.exceptions import ValidationError
from django.db.models import QuerySet
from django.db.transaction import atomic
from django.db.utils import IntegrityError

from ..media import api as media_api
from ..media.models import Media
from ..publishing import api as publishing_api
from ..publishing.models import LearningPackage
from .models import INVALID_PATH_MSG, Asset, AssetPermissions, AssetVersion

# The public API that will be re-exported by openedx_content.api
# is listed in the __all__ entries below. Internal helper functions that are
# private to this module should start with an underscore. If a function does not
# start with an underscore AND it is not in __all__, that function is considered
# to be callable only by other applets in the openedx_content package.
__all__ = [
    "create_asset",
    "create_next_asset_version",
    "create_asset_and_version",
    "get_asset",
    "get_asset_by_path",
]


log = logging.getLogger(__name__)


def create_asset(
    learning_package_id: LearningPackage.ID,
    /,
    path: str,
    created: datetime,
    created_by: int | None,
    *,
    permissions: AssetPermissions = AssetPermissions.PUBLIC,
    allow_scripts: bool = False,
) -> Asset:
    """
    Create a new Asset (a shared file, like an image or a PDF document).
    """
    entity_ref = f"openedx-asset:{path}"
    with atomic():
        try:
            publishable_entity = publishing_api.create_publishable_entity(
                learning_package_id, entity_ref, created, created_by, can_stand_alone=True
            )
        except IntegrityError as e:
            # If the 'path' is already in use, the entity_ref will raise an exception before our constraint on 'path'
            # does below, since the PublishableEntity gets created first.
            if "entity_ref" in str(e):
                raise ValidationError(f'Asset with path "{path}" already exists.') from e
            raise e
        try:
            asset = Asset.objects.create(
                publishable_entity=publishable_entity,
                learning_package_id=learning_package_id,
                path=path,
                permissions=permissions,
                allow_scripts=allow_scripts,
            )
        except IntegrityError as e:
            if "oe_content_asset_valid_path" in str(e):
                # Use a consistent exception+message regardless of whether it's raised by full_clean() or the DB:
                raise ValidationError(INVALID_PATH_MSG) from e
            raise e
    return asset


def create_asset_version(
    asset: Asset,
    /,
    version_num: int,
    created: datetime,
    created_by: int | None,
    *,
    title: str,
    media: Media.ID | Media | bytes,
) -> AssetVersion:
    """
    Create a new ComponentVersion. Internal - most should use
    ``create_next_asset_version`` or ``create_asset_and_version``.
    """
    with atomic(savepoint=False):
        publishable_entity_version = publishing_api.create_publishable_entity_version(
            asset.id,
            version_num=version_num,
            title=title,
            created=created,
            created_by=created_by,
        )
        media = _create_version_media(asset.learning_package_id, path=asset.path, media=media, created=created)
        asset_version = AssetVersion.objects.create(
            publishable_entity_version=publishable_entity_version,
            asset_id=asset.id,
            media=media,
        )

    return asset_version


def create_next_asset_version(
    asset_id: Asset.ID,
    /,
    media: Media.ID | Media | bytes,
    created: datetime,
    created_by: int | None = None,
    *,
    title: str | None = None,
    force_version_num: int | None = None,
) -> AssetVersion:
    """
    Create a new AssetVersion based on the most recent version.
    """
    # This needs to grab the highest version_num for this Publishable Entity.
    # This will often be the Draft version, but not always. For instance, if
    # an entity was soft-deleted, the draft would be None, but the version_num
    # should pick up from the last edited version. Likewise, a Draft might get
    # reverted to an earlier version, but we want the latest version_num when
    # creating the next version.
    asset = Asset.objects.get(pk=asset_id)
    last_version = asset.versioning.latest
    if last_version is None:
        next_version_num = 1
        if title is None:
            title = asset.path
    else:
        next_version_num = last_version.version_num + 1
        if title is None:
            title = last_version.title

    if force_version_num is not None:
        next_version_num = force_version_num

    return create_asset_version(
        asset, version_num=next_version_num, created=created, created_by=created_by, title=title, media=media
    )


def create_asset_and_version(
    learning_package_id: LearningPackage.ID,
    /,
    path: str,
    *,
    title: str | None = None,
    created: datetime | None = None,
    created_by: int | None = None,
    media: Media.ID | Media | bytes,
    permissions: AssetPermissions = AssetPermissions.PUBLIC,
    allow_scripts: bool = False,
) -> tuple[Asset, AssetVersion]:
    """
    Create a Asset and associated AssetVersion atomically.
    """
    if created is None:
        created = datetime.now(tz=timezone.utc)
    if title is None:
        title = path
    with atomic(savepoint=False):
        asset = create_asset(
            learning_package_id,
            path,
            created,
            created_by,
            permissions=permissions,
            allow_scripts=allow_scripts,
        )
        asset_version = create_asset_version(
            asset,
            version_num=1,
            title=title,
            created=created,
            created_by=created_by,
            media=media,
        )

    return (asset, asset_version)


def _create_version_media(
    learning_package_id: LearningPackage.ID,
    path: str,
    media: Media.ID | Media | bytes,
    created: datetime,
) -> Media:
    """
    Internal helper to set the Media for this AssetVersion.

    Only call this when we're first initializing a AssetVersion.

    Media can be specified as ``bytes`` for testing convenience, but you will
    almost always want to create a Media object first in actual app code,
    because that will give you better control over the MIME type and storage
    specifics (file vs. database).
    """

    match media:
        case int():  # MediaID
            media_obj = media_api.get_media(media)
        case Media():
            media_obj = media
        case bytes():
            media_type_str, _encoding = mimetypes.guess_type(path)
            # We use "application/octet-stream" as a generic fallback media type, per
            # RFC 2046: https://datatracker.ietf.org/doc/html/rfc2046
            media_type_str = media_type_str or "application/octet-stream"
            media_type = media_api.get_or_create_media_type(media_type_str)
            media_obj = media_api.get_or_create_file_media(
                learning_package_id,
                media_type.id,
                data=media,
                created=created,
            )
            return media_obj
        case _:
            raise ValueError(f"Invalid object for Asset media: {media!r}")

    if media_obj.learning_package_id != learning_package_id:
        raise ValueError(
            f"Media LearningPackage does not match Asset: "
            f"(Media Learning Package ID {media_obj.learning_package_id!r})"
            f"(Asset Learning Package ID {learning_package_id!r})"
        )
    return media_obj


def get_asset(asset_id: Asset.ID, /) -> Asset:
    """
    Get an Asset by its primary key.

    This is the same as the PublishableEntity's ID primary key.
    """
    return Asset.with_publishing_relations.get(pk=asset_id)


def get_asset_by_path(
    learning_package_id: LearningPackage.ID,
    /,
    path: str,
) -> Asset:
    """
    Get an Asset by its path (filename, e.g. "image.jpg")
    """
    return Asset.with_publishing_relations.get(learning_package_id=learning_package_id, path=path)


def get_assets(
    learning_package_id: LearningPackage.ID,
    /,
    draft: bool | None = None,
    published: bool | None = None,
) -> QuerySet[Asset]:
    """
    Fetch a QuerySet of Assets for a LearningPackage using various filters.

    This method will pre-load all the relations that we need in order to get
    info from the Asset's draft and published versions, since we'll be
    referencing these a lot.
    """
    qset = Asset.with_publishing_relations.filter(learning_package_id=learning_package_id).order_by("pk")
    if draft is not None:
        qset = qset.filter(publishable_entity__draft__version__isnull=not draft)
    if published is not None:
        qset = qset.filter(publishable_entity__published__version__isnull=not published)
    return qset
