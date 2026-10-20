"""
Tests of the Asset API
"""

from __future__ import annotations

import base64
from datetime import datetime, timedelta, timezone
from typing import TYPE_CHECKING, assert_type, cast

import pytest
from django.core.exceptions import ValidationError

from openedx_content.applets.assets import api
from openedx_content.applets.assets.models import Asset, AssetPermissions, AssetVersion
from openedx_content.applets.media import api as media_api
from openedx_content.applets.media.models import Media
from openedx_content.applets.publishing import api as publishing_api
from openedx_content.applets.publishing.models import LearningPackage

if TYPE_CHECKING:
    from django.contrib.auth.models import User  # pylint: disable=imported-auth-user

    # Test that our model manager has correct typing
    assert_type(Asset.objects.create(), Asset)
    assert_type(Asset.objects.get(), Asset)
    assert_type(AssetVersion.objects.create(), AssetVersion)
    assert_type(AssetVersion.objects.get(), AssetVersion)

pytestmark = pytest.mark.django_db

now = datetime.now(tz=timezone.utc)
later = now + timedelta(seconds=10)

BLACK_PNG_BYTES: bytes = base64.b64decode(  # A valid PNG image, that is a single black pixel
    "iVBORw0KGgoAAAANSUhEUgAAAAEAAAABAQAAAAA3bvkkAAAACklEQVR4AWNgAAAAAgABc3UBGAAAAABJRU5ErkJggg=="
)
GREY_PNG_BYTES: bytes = base64.b64decode(  # A valid PNG image that is a single grey pixel
    "iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAAAAAA6fptVAAAACklEQVR4AWOwBQAAPwA+Eq7IEAAAAABJRU5ErkJggg=="
)


@pytest.fixture(name="lp")
def _lp() -> LearningPackage:
    """Get a Learning Package."""
    return publishing_api.create_learning_package(package_ref="assets-test-lp", title="Assets Test LP 1")


@pytest.fixture(name="lp2")
def _lp2() -> LearningPackage:
    return publishing_api.create_learning_package(package_ref="assets-test-lp2", title="Assets Test LP 2")


@pytest.fixture(name="user1")
def _user1(django_user_model) -> User:
    return django_user_model.objects.create(username="user1")


@pytest.fixture(name="black_png")
def _black_png(lp: LearningPackage) -> Media:
    media_type_id = media_api.get_or_create_media_type("image/png").id
    return media_api.get_or_create_file_media(lp.id, media_type_id, data=BLACK_PNG_BYTES, created=now)


@pytest.fixture(name="grey_png")
def _grey_png(lp: LearningPackage) -> Media:
    media_type_id = media_api.get_or_create_media_type("image/png").id
    return media_api.get_or_create_file_media(lp.id, media_type_id, data=GREY_PNG_BYTES, created=now)


@pytest.fixture(name="black")
def _black(lp: LearningPackage, black_png: Media) -> Asset:
    return api.create_asset_and_version(lp.id, path="black.png", created=now, media=black_png)[0]


@pytest.fixture(name="grey")
def _grey(lp: LearningPackage, grey_png: Media) -> Asset:
    return api.create_asset_and_version(lp.id, path="grey.png", created=now, media=grey_png)[0]


# Creating Assets (without versions/data) ######################################


def test_create_asset(lp: LearningPackage, user1: User) -> None:
    """Basic test of ``create_asset()``: Create an asset with no version."""
    path = "instructions.txt"

    asset = api.create_asset(lp.id, path=path, created=now, created_by=user1.id)
    asset.refresh_from_db()  # Ensure we check what was actually saved to database, not just returned

    assert_type(asset, Asset)
    assert asset.id
    assert_type(asset.id, Asset.ID)
    assert asset.publishable_entity.id == asset.id
    assert asset.publishable_entity.learning_package_id == lp.id
    assert asset.learning_package == lp
    assert asset.publishable_entity.can_stand_alone
    assert asset.publishable_entity.created == now
    assert asset.publishable_entity.created_by
    assert asset.publishable_entity.created_by.id == user1.id
    assert asset.path == path
    assert asset.permissions == AssetPermissions.PUBLIC.value
    assert not asset.allow_scripts  # Default must be False
    assert asset.versioning.latest is None
    assert asset.versioning.draft is None
    assert asset.versioning.published is None


def test_path_unique_per_lp(lp: LearningPackage, lp2: LearningPackage) -> None:
    """Test that path (filename) must be unique per learning package."""
    path = "instructions.txt"
    other_path = "other.pdf"

    asset1 = api.create_asset(lp.id, path=path, created=now, created_by=None)
    assert asset1.id

    with pytest.raises(ValidationError, match=f'Asset with path "{path}" already exists.'):
        # Cannot create an asset with the same path (filename) in the same LP:
        api.create_asset(lp.id, path=path, created=now, created_by=None)

    # But creating an asset with the same path in a different LP is fine:
    asset2 = api.create_asset(lp2.id, path=path, created=now, created_by=None)
    assert asset2.id
    assert asset1.id != asset2.id
    assert asset1.path == asset2.path

    # And creating an asset with a different path is fine:
    asset3 = api.create_asset(lp.id, path=other_path, created=now, created_by=None)
    assert asset3.id
    assert asset1.id != asset3.id


def test_path_case_sensitive(lp: LearningPackage) -> None:
    """Test that path (filename) is case sensitive."""
    path1 = "case.txt"
    path2 = "Case.txt"

    asset1 = api.create_asset(lp.id, path=path1, created=now, created_by=None)
    asset2 = api.create_asset(lp.id, path=path2, created=now, created_by=None)
    asset1.refresh_from_db()
    asset2.refresh_from_db()
    assert asset1.id != asset2.id
    assert asset1.path == path1
    assert asset2.path == path2


@pytest.mark.parametrize(
    "path, valid",
    [
        # ✅ Valid:
        ("image.jpg", True),
        ("image (2).jpg", True),
        ("python_lib.zip", True),
        ("course.elmwtqp8.tar.gz", True),
        ("IMG-004.JPEG", True),
        ("folder/example.pdf", True),
        ("textbooks/intro textbook/ch1.pdf", True),
        (".hidden.conf", True),
        ("Αθήνα.md", True),
        ("😎.md", True),
        # The next filename has a narrow no break space before "AM" since that's what MacOS puts in screenshot names
        ("screen shots/Screenshot 2026-10-23 at 11.26.13\u202fAM.png", True),
        # ❌ Invalid:
        ("/image.jpg", False),
        ("./image.jpg", False),
        ("//image.jpg", False),
        ("../image.jpg", False),
        ("folder/", False),
        ("backslash\\image.jpg", False),
        ("folder/../image.jpg", False),
        ("double//image.jpg", False),
        ("../../../etc/passwd", False),
        ("", False),
        (".", False),
        ("..", False),
    ],
)
def test_valid_invalid_paths(path: str, valid: bool, lp: LearningPackage) -> None:
    """Test validation of filenames"""

    def create():
        return api.create_asset(lp.id, path=path, created=now, created_by=None)

    if valid:
        asset = create()
        assert asset.id
        asset.refresh_from_db()
        assert asset.path == path
    else:
        with pytest.raises(ValidationError, match="Asset path is invalid."):
            create()


# Creating Assets (with initial version/data) ##################################


def test_create_asset_and_version(lp: LearningPackage, user1: User) -> None:
    """Basic test of ``test_create_asset_and_version()``: Create an asset with initial version."""
    path = "black.png"

    (asset, asset_v1) = api.create_asset_and_version(
        lp.id,
        path=path,
        created=now,
        created_by=user1.id,
        media=BLACK_PNG_BYTES,
    )
    asset.refresh_from_db()  # Ensure we check what was actually saved to database, not just returned
    asset_v1.refresh_from_db()

    assert_type(asset, Asset)
    assert asset.id
    assert_type(asset.id, Asset.ID)
    assert asset.publishable_entity.id == asset.id
    assert asset.publishable_entity.learning_package_id == lp.id
    assert asset.learning_package == lp
    assert asset.publishable_entity.can_stand_alone
    assert asset.publishable_entity.created == now
    assert asset.publishable_entity.created_by
    assert asset.publishable_entity.created_by.id == user1.id
    assert asset.path == path
    assert asset.permissions == AssetPermissions.PUBLIC.value
    assert not asset.allow_scripts  # Default must be False
    assert asset.versioning.published is None  # Not published by default
    assert asset.versioning.draft
    assert asset.versioning.draft.pk is asset_v1.pk
    assert asset.versioning.latest
    assert asset.versioning.latest.pk is asset_v1.pk

    assert asset_v1.asset.id == asset.id
    assert_type(asset_v1.asset, Asset)
    assert asset_v1.title == path  # By default, title is set to path if not specified
    assert asset_v1.created == now
    assert asset_v1.created_by
    assert asset_v1.created_by.id == user1.id

    media = asset_v1.media
    assert media
    assert media.learning_package.id == lp.id
    assert str(media.media_type) == "image/png"
    assert media.hash_digest == "8d55c179d5f1516fa5594d7c76f3ef6a971c6c8a"
    assert media.size == len(BLACK_PNG_BYTES)
    assert media.has_file
    assert media.created == now


def test_create_two_assets(lp: LearningPackage, user1: User, black_png: Media) -> None:
    """Create two assets with the same contents"""
    path1 = "black1.png"
    path2 = "black2.png"

    (_asset1, asset1_v1) = api.create_asset_and_version(
        lp.id, path=path1, created=now, created_by=user1.id, media=black_png
    )
    (_asset2, asset2_v1) = api.create_asset_and_version(
        lp.id, path=path2, created=now, created_by=user1.id, media=black_png
    )

    # V1 of both assets uses the exact same Media instance:
    assert asset1_v1.media.id == black_png.id
    assert asset2_v1.media.id == black_png.id


@pytest.mark.parametrize("permissions", [AssetPermissions.LOCKED, AssetPermissions.STAFF])
def test_create_asset_and_version_permissions(
    lp: LearningPackage, user1: User, black_png: Media, permissions: AssetPermissions
) -> None:
    """Create an asset and version with the specified permissions"""
    path = "black.png"

    (asset, _asset_v1) = api.create_asset_and_version(
        lp.id,
        path=path,
        created=now,
        created_by=user1.id,
        media=black_png,
        permissions=permissions,
        allow_scripts=True,
    )
    assert asset.permissions == permissions.value
    assert asset.allow_scripts


def test_create_asset_and_version_queries(
    lp: LearningPackage, user1: User, black_png: Media, django_assert_num_queries
) -> None:
    """Create an asset and version with the specified permissions"""
    path = "black.png"

    with django_assert_num_queries(23):
        api.create_asset_and_version(
            lp.id,
            path=path,
            created=now,
            created_by=user1.id,
            media=black_png,
        )


# Creating Subsequent Asset Versions ###########################################


def test_create_asset_two_versions(lp: LearningPackage, user1: User, black_png: Media, grey_png: Media) -> None:
    """Create an asset with two versions, v1 black and v2 grey"""
    path = "pixel.png"

    (asset, v1) = api.create_asset_and_version(
        lp.id, path=path, created=now, created_by=user1.id, media=black_png, title="Black Pixel"
    )
    v2 = api.create_next_asset_version(asset.id, media=grey_png, created=later, created_by=user1.id, title="Grey Pixel")

    asset.refresh_from_db()
    assert asset.versioning.draft
    assert asset.versioning.draft.pk == v2.pk

    assert v1.version_num == 1
    assert v1.title == "Black Pixel"

    assert v2.version_num == 2
    assert v2.title == "Grey Pixel"
    assert v2.created == later
    assert v2.media_id == grey_png.id


def test_create_asset_two_versions_manual(lp: LearningPackage, user1: User, black_png: Media, grey_png: Media) -> None:
    """Create an asset with two versions, v1 black and v3 grey, with no v2"""
    path = "pixel.png"

    (asset, v1) = api.create_asset_and_version(lp.id, path=path, created=now, created_by=user1.id, media=black_png)
    v3 = api.create_next_asset_version(
        asset.id, media=grey_png, created=later, created_by=user1.id, force_version_num=3
    )

    asset.refresh_from_db()
    assert asset.versioning.draft
    assert asset.versioning.draft.pk == v3.pk

    assert v1.version_num == 1
    assert v3.created == later
    assert v3.media_id == grey_png.id
    assert v3.version_num == 3


# Getting Assets ###############################################################


def get_asset_by_id(black: Asset, black_png: Media, grey: Asset, grey_png: Media):
    """Test retrieving asset by ID."""
    b = api.get_asset(black.id)
    assert b.id == black.id
    assert b.versioning.draft.media.id == black_png.id

    g = api.get_asset(grey.id)
    assert g.id == grey.id
    assert g.versioning.draft.media.id == grey_png.id

    with pytest.raises(Asset.DoesNotExist):
        api.get_asset(cast(Asset.ID, -400))


def get_asset_by_filename(  # pylint: disable=too-many-positional-arguments
    lp: LearningPackage, lp2: LearningPackage, black: Asset, black_png: Media, grey: Asset, grey_png: Media
):
    """Test retrieving asset by filename."""
    b = api.get_asset_by_path(lp.id, path="black.png")
    assert b.id == black.id
    assert b.versioning.draft.media.id == black_png.id

    g = api.get_asset_by_path(lp.id, path="grey.png")
    assert g.id == grey.id
    assert g.versioning.draft.media.id == grey_png.id

    with pytest.raises(Asset.DoesNotExist):
        # Different learning package:
        api.get_asset_by_path(lp2.id, path="grey.png")

    with pytest.raises(Asset.DoesNotExist):
        api.get_asset_by_path(lp2.id, path="404.png")
