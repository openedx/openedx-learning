"""
Tests for restoring a Learning Package from a backup archive.

These drive the public API (``backup_restore.api``) rather than the loader
directly, so that the whole pipeline -- archive, payload, validation, loading --
is exercised the way a caller would use it.

The ``library_backup`` fixture is the workhorse here. It is a real archive
produced by the backup side, and several of its quirks are deliberate:

* ``unit1`` has a blank version title, because untitled units are common in
  content imported from courses.
* ``section1-extra-8ca126.toml`` and ``...-extra.toml`` have filenames that don't
  match the entity key inside them, because the backup side hashes filenames to
  avoid collisions.
* Its entities cover every draft/published combination we care about.
"""
import os
import shutil
import tempfile
from datetime import datetime, timezone
from io import StringIO

from django.contrib.auth import get_user_model
from django.core.management import CommandError, call_command
from django.test import TestCase

from openedx_content.applets.backup_restore import api
from openedx_content.applets.backup_restore.errors import (
    ArchiveNotReadableError,
    DuplicateFoundError,
    MissingFileError,
    RestoreFailedError,
    SchemaError,
    TableNotFoundError,
    UnknownContainerTypeError,
    UnresolvedChildError,
    UnsupportedFormatError,
)
from openedx_content.applets.backup_restore.loading import Loader
from openedx_content.applets.backup_restore.results import generate_staged_package_ref
from openedx_content.applets.backup_restore.schema import CompletePackageInputData, EntityInputData
from openedx_content.applets.backup_restore.validation import ValidatedLearningPackageInput
from openedx_content.applets.collections import api as collections_api
from openedx_content.applets.components import api as components_api
from openedx_content.applets.containers import api as containers_api
from openedx_content.applets.publishing import api as publishing_api
from test_utils.zip_file_utils import folder_to_zip_path

User = get_user_model()

FIXTURES_DIR = os.path.join(os.path.dirname(__file__), "fixtures")
LIBRARY_BACKUP_DIR = os.path.join(FIXTURES_DIR, "library_backup")


def broken_fixture(name: str) -> str:
    return os.path.join(FIXTURES_DIR, "broken", name)


class RestoreTestCase(TestCase):
    """Base test case for restore tests."""

    def setUp(self):
        super().setUp()
        self.fixtures_folder = LIBRARY_BACKUP_DIR
        self.package_ref = "lib:WGU:LIB_C001"
        self.user = User.objects.create_user(username="lp_user", password="12345")

    def as_zip(self, folder: str) -> str:
        """Write a fixture folder out as a real zip file and return its path."""
        tmp_dir = tempfile.TemporaryDirectory()
        self.addCleanup(tmp_dir.cleanup)
        return folder_to_zip_path(folder, tmp_dir.name)


class RestoreLearningPackageTest(RestoreTestCase):
    """Restoring a well-formed archive."""

    def test_restore_with_explicit_package_ref(self):
        result = api.load_learning_package_from_path(
            self.fixtures_folder, user=self.user, package_ref="lib-xx:WGU:LIB_C001"
        )

        assert result.status == "success"
        assert result.log_file_error is None

        restored = result.lp_restored_data
        assert restored.package_ref == "lib-xx:WGU:LIB_C001"
        assert restored.archive_package_ref == "lib:WGU:LIB_C001"
        assert restored.archive_org_code == "WGU"
        assert restored.archive_package_code == "LIB_C001"
        assert restored.title == "Library test"
        assert restored.num_containers == 3
        assert restored.num_sections == 1
        assert restored.num_subsections == 1
        assert restored.num_units == 1
        assert restored.num_components == 7
        assert restored.num_collections == 1

        lp = publishing_api.LearningPackage.objects.filter(
            package_ref="lib-xx:WGU:LIB_C001"
        ).first()
        assert lp is not None, "Learning package was not restored."

    def test_learning_package_fields_come_from_the_archive(self):
        result = api.load_learning_package_from_path(
            self.fixtures_folder, user=self.user, package_ref="lib-xx:WGU:LIB_C001"
        )

        lp = publishing_api.LearningPackage.objects.get(id=result.lp_restored_data.id)
        assert lp.title == "Library test"
        assert lp.description == ""
        assert lp.created == datetime(2025, 8, 19, 4, 25, 10, 988166, tzinfo=timezone.utc)

    def test_restore_with_staged_package_ref(self):
        """Without an explicit ref we generate one namespaced to the user."""
        result = api.load_learning_package_from_path(self.fixtures_folder, user=self.user)

        assert result.status == "success"
        restored_ref = result.lp_restored_data.package_ref
        assert result.lp_restored_data.archive_package_ref == "lib:WGU:LIB_C001"
        assert restored_ref.startswith("lp-restore:lp_user:WGU:LIB_C001:")

        lp = publishing_api.LearningPackage.objects.filter(
            package_ref=restored_ref
        ).first()
        assert lp is not None, "Learning package with staged ref was not restored."

    def test_backup_metadata(self):
        result = api.load_learning_package_from_path(self.fixtures_folder, user=self.user)

        assert result.status == "success"
        assert result.backup_metadata.format_version == 1
        assert result.backup_metadata.created_by == "lp_user"
        assert result.backup_metadata.created_by_email == "lp_user@example.com"
        assert result.backup_metadata.created_at == datetime(
            2025, 10, 5, 18, 23, 45, 180535, tzinfo=timezone.utc
        )
        assert result.backup_metadata.original_server == "cms.test"

    def test_restore_from_zip_matches_restore_from_directory(self):
        """
        A zip archive and the same archive unzipped must load identically.

        Reading directly from a directory is new -- the old implementation only
        accepted zip files -- so it's worth pinning that the two agree.
        """
        from_dir = api.load_learning_package_from_path(
            self.fixtures_folder, user=self.user, package_ref="lib:from:dir"
        )
        from_zip = api.load_learning_package_from_path(
            self.as_zip(self.fixtures_folder), user=self.user, package_ref="lib:from:zip"
        )

        def comparable(result):
            data = dict(vars(result.lp_restored_data))
            # These differ by construction.
            del data["id"]
            del data["package_ref"]
            return data

        assert comparable(from_dir) == comparable(from_zip)
        assert vars(from_dir.backup_metadata) == vars(from_zip.backup_metadata)

    def test_blank_container_title(self):
        """
        Restoring should succeed when a container version has a blank title.

        Blank titles are legal and common -- content imported from courses
        (e.g. via the modulestore migrator) frequently has untitled units, and
        such content can be backed up. Restoring that same archive must work.

        The ``library_backup`` fixture's ``unit1`` deliberately has a blank
        title to exercise this path.
        """
        result = api.load_learning_package_from_path(
            self.fixtures_folder, user=self.user, package_ref="lib-xx:WGU:LIB_C001"
        )

        assert result.status == "success"
        lp = publishing_api.LearningPackage.objects.get(id=result.lp_restored_data.id)
        unit = containers_api.get_containers(learning_package_id=lp.id).get(
            publishable_entity__entity_ref="unit1-b7eafb"
        )
        draft_version = publishing_api.get_draft_version(unit.publishable_entity.id)
        assert draft_version.title == ""

    def test_entity_key_need_not_match_filename(self):
        """
        The key inside the file wins, not the filename.

        The backup side hashes filenames to keep them unique and filesystem-safe,
        so the two routinely differ. Two fixture files are named to make sure we
        don't accidentally start trusting the filename.
        """
        result = api.load_learning_package_from_path(
            self.fixtures_folder, user=self.user, package_ref="lib-xx:WGU:LIB_C001"
        )
        lp_id = result.lp_restored_data.id

        entity_refs = set(
            publishing_api.get_publishable_entities(lp_id).values_list(
                "entity_ref", flat=True
            )
        )
        assert "section1-8ca126" in entity_refs
        assert "section1-extra-8ca126" not in entity_refs
        assert "xblock.v1:html:c22b9f97-f1e9-4e8f-87f0-d5a3c26083e2" in entity_refs


class RestoreContentTest(RestoreTestCase):
    """Verifies what actually landed in the database."""

    def setUp(self):
        super().setUp()
        result = api.load_learning_package_from_path(
            self.fixtures_folder, user=self.user, package_ref="lib-xx:WGU:LIB_C001"
        )
        self.lp = publishing_api.LearningPackage.objects.get(
            id=result.lp_restored_data.id
        )

    def draft_and_published(self, entity_id):
        return (
            publishing_api.get_draft_version(entity_id),
            publishing_api.get_published_version(entity_id),
        )

    def test_containers(self):
        """Verify the containers and their versions were restored correctly."""
        container_qs = containers_api.get_containers(learning_package_id=self.lp.id)
        expected = {
            # entity_ref: (type, draft version, published version)
            "unit1-b7eafb": ("unit", 2, 2),
            "subsection1-48afa3": ("subsection", 2, None),
            "section1-8ca126": ("section", 2, None),
        }
        assert {c.entity_ref for c in container_qs} == set(expected)

        for container in container_qs:
            container_type, draft_num, published_num = expected[container.entity_ref]
            assert containers_api.get_container_type_code_of(container) == container_type
            assert container.created_by is not None
            assert container.created_by.username == "lp_user"

            draft, published = self.draft_and_published(container.publishable_entity.id)
            assert draft is not None
            assert draft.version_num == draft_num
            assert draft.created_by.username == "lp_user"
            if published_num is None:
                assert published is None
            else:
                assert published is not None
                assert published.version_num == published_num
                assert published.created_by.username == "lp_user"

    def test_components(self):
        """
        Verify the components and their versions were restored correctly.

        The version numbers here are the interesting part: they cover draft ==
        published, draft ahead of published, and never-published.
        """
        expected = {
            # entity_ref: (component type, draft version, published version)
            "xblock.v1:drag-and-drop-v2:4d1b2fac-8b30-42fb-872d-6b10ab580b27":
                ("drag-and-drop-v2", 2, None),
            "xblock.v1:html:e32d5479-9492-41f6-9222-550a7346bc37": ("html", 5, 4),
            "xblock.v1:openassessment:1ee38208-a585-4455-a27e-4930aa541f53":
                ("openassessment", 2, None),
            "xblock.v1:problem:256739e8-c2df-4ced-bd10-8156f6cfa90b": ("problem", 2, None),
            "xblock.v1:survey:6681da3f-b056-4c6e-a8f9-040967907471": ("survey", 1, None),
            "xblock.v1:video:22601ebd-9da8-430b-9778-cfe059a98568": ("video", 3, None),
            "xblock.v1:html:c22b9f97-f1e9-4e8f-87f0-d5a3c26083e2": ("html", 2, 2),
        }
        component_qs = components_api.get_components(self.lp.id)
        assert {c.entity_ref for c in component_qs} == set(expected)

        for component in component_qs:
            type_name, draft_num, published_num = expected[component.entity_ref]
            assert component.component_type.name == type_name
            assert component.component_type.namespace == "xblock.v1"
            assert component.created_by is not None
            assert component.created_by.username == "lp_user"

            draft, published = self.draft_and_published(component.publishable_entity.id)
            assert draft is not None
            assert draft.version_num == draft_num
            assert draft.created_by.username == "lp_user"
            if published_num is None:
                assert published is None
            else:
                assert published is not None
                assert published.version_num == published_num
                assert published.created_by.username == "lp_user"

    def test_block_xml_becomes_text_media(self):
        component = components_api.get_components(self.lp.id).get(
            publishable_entity__entity_ref=(
                "xblock.v1:drag-and-drop-v2:4d1b2fac-8b30-42fb-872d-6b10ab580b27"
            )
        )
        draft = publishing_api.get_draft_version(component.publishable_entity.id)

        media = draft.componentversion.media.all()
        assert media.count() == 1
        block_xml = media.first()
        assert "<drag-and-drop-v2" in block_xml.text
        assert not block_xml.has_file
        assert str(block_xml.media_type) == (
            "application/vnd.openedx.xblock.v1.drag-and-drop-v2+xml"
        )

    def test_static_assets_become_file_media(self):
        """
        Static files are carried across as real file-backed Media.

        The html component's v4 and v5 both reference the same static image, so
        this also covers a static asset appearing in more than one version.
        """
        component = components_api.get_components(self.lp.id).get(
            publishable_entity__entity_ref=(
                "xblock.v1:html:e32d5479-9492-41f6-9222-550a7346bc37"
            )
        )
        entity_id = component.publishable_entity.id
        draft = publishing_api.get_draft_version(entity_id)
        published = publishing_api.get_published_version(entity_id)

        for version in (draft, published):
            by_path = {
                cvm.path: cvm.media
                for cvm in version.componentversion.componentversionmedia_set.all()
            }
            assert set(by_path) == {"block.xml", "static/me.png"}
            assert by_path["static/me.png"].has_file
            assert str(by_path["static/me.png"].media_type) == "image/png"
            assert not by_path["block.xml"].has_file

    def test_collections(self):
        """Verify the collections were restored correctly."""
        collections = collections_api.get_collections(self.lp.id)
        assert collections.count() == 1

        collection = collections.first()
        assert collection.title == "Collection test1"
        assert collection.collection_code == "collection-test"
        assert collection.description == ""
        assert collection.created_by is not None
        assert collection.created_by.username == "lp_user"

        assert {entity.entity_ref for entity in collection.entities.all()} == {
            "xblock.v1:html:e32d5479-9492-41f6-9222-550a7346bc37",
            "xblock.v1:problem:256739e8-c2df-4ced-bd10-8156f6cfa90b",
        }


class RestoreErrorTest(RestoreTestCase):
    """
    Archives we refuse to load.

    In every case, nothing may be written to the database -- a half-restored
    Learning Package is harder to deal with than none at all.
    """

    def assert_refuses(self, fixture_name, error_type):
        """Load a broken fixture, expecting it to be rejected untouched."""
        packages_before = publishing_api.LearningPackage.objects.count()

        with self.assertRaises(RestoreFailedError) as ctx:
            api.load_learning_package_from_path(broken_fixture(fixture_name), user=self.user)

        assert publishing_api.LearningPackage.objects.count() == packages_before, (
            "A failed restore must not leave anything behind."
        )
        matching = [e for e in ctx.exception.errors if isinstance(e, error_type)]
        assert matching, (
            f"Expected a {error_type.__name__}, got: "
            f"{[type(e).__name__ for e in ctx.exception.errors]}"
        )
        return matching[0]

    def test_missing_package_toml(self):
        error = self.assert_refuses("empty_archive", MissingFileError)
        assert error.path == "package.toml"

    def test_missing_learning_package_key(self):
        error = self.assert_refuses("missing_lp_key", SchemaError)
        assert error.path == "package.toml"
        assert error.location == ("learning_package", "key")

    def test_missing_meta_table(self):
        error = self.assert_refuses("missing_meta", TableNotFoundError)
        assert error.table == "meta"

    def test_unsupported_format_version(self):
        error = self.assert_refuses("unsupported_format_version", UnsupportedFormatError)
        assert "2" in error.message

    def test_duplicate_entities(self):
        error = self.assert_refuses("duplicate_entities", DuplicateFoundError)
        assert error.path == "entities/second.toml"
        assert error.original_path == "entities/first.toml"

    def test_unknown_container_type(self):
        error = self.assert_refuses("unknown_container", UnknownContainerTypeError)
        assert "chapter" in error.message

    def test_unresolved_child(self):
        error = self.assert_refuses("unresolved_child", UnresolvedChildError)
        assert "xblock.v1:html:does-not-exist" in error.message

    def test_unreadable_archive(self):
        with self.assertRaises(ArchiveNotReadableError):
            api.load_learning_package_from_path("/no/such/path.zip", user=self.user)

    def test_error_text_lists_every_problem(self):
        with self.assertRaises(RestoreFailedError) as ctx:
            api.load_learning_package_from_path(broken_fixture("missing_lp_key"), user=self.user)

        text = ctx.exception.as_text()
        assert text.startswith("Errors encountered during restore:\n")
        assert "package.toml" in text


class LoadLearningPackageAsDictTest(RestoreTestCase):
    """
    The compatibility shim for callers written against the old restore.

    TODO: This can go away once those callers move to load_learning_package and
    catching BackupRestoreError.
    """

    def test_success_shape(self):
        result = api.load_learning_package(
            self.fixtures_folder, user=self.user, package_ref="lib-xx:WGU:LIB_C001"
        )

        assert result["status"] == "success"
        assert result["log_file_error"] is None
        assert set(result) == {
            "status", "log_file_error", "lp_restored_data", "backup_metadata"
        }
        assert set(result["lp_restored_data"]) == {
            "id", "package_ref", "archive_package_ref", "archive_org_code",
            "archive_package_code", "title", "num_containers", "num_sections",
            "num_subsections", "num_units", "num_components", "num_collections",
        }
        assert set(result["backup_metadata"]) == {
            "format_version", "created_at", "created_by", "created_by_email",
            "original_server",
        }

    def test_error_shape(self):
        result = api.load_learning_package(
            broken_fixture("missing_lp_key"), user=self.user
        )

        assert result["status"] == "error"
        assert result["lp_restored_data"] is None
        assert result["backup_metadata"] is None
        assert isinstance(result["log_file_error"], StringIO)
        assert "package.toml" in result["log_file_error"].getvalue()

    def test_unreadable_archive_is_also_reported_as_a_dict(self):
        result = api.load_learning_package("/no/such/path.zip", user=self.user)

        assert result["status"] == "error"
        assert "/no/such/path.zip" in result["log_file_error"].getvalue()


class RestoreLearningPackageCommandTest(RestoreTestCase):
    """Tests for the lp_load management command."""

    def test_restore_command_with_zip(self):
        out = StringIO()
        call_command(
            "lp_load", self.as_zip(self.fixtures_folder), "lp_user", stdout=out
        )

        assert "loaded successfully" in out.getvalue()
        lp = publishing_api.LearningPackage.objects.get()
        assert lp.title == "Library test"
        assert lp.package_ref.startswith("lp-restore:lp_user:WGU:LIB_C001:")

    def test_restore_command_with_directory(self):
        """The old command rejected anything that wasn't a .zip."""
        out = StringIO()
        call_command("lp_load", self.fixtures_folder, "lp_user", stdout=out)

        assert "loaded successfully" in out.getvalue()
        assert publishing_api.LearningPackage.objects.count() == 1

    def test_restore_command_with_explicit_package_ref(self):
        out = StringIO()
        call_command(
            "lp_load",
            self.fixtures_folder,
            "lp_user",
            "--package-ref",
            "lib-xx:WGU:LIB_C001",
            stdout=out,
        )

        lp = publishing_api.LearningPackage.objects.get()
        assert lp.package_ref == "lib-xx:WGU:LIB_C001"

    def test_restore_command_reports_archive_errors(self):
        with self.assertRaises(CommandError) as ctx:
            call_command("lp_load", broken_fixture("missing_lp_key"), "lp_user")

        assert "Errors encountered during restore:" in str(ctx.exception)
        assert "package.toml" in str(ctx.exception)
        assert publishing_api.LearningPackage.objects.count() == 0

    def test_restore_command_with_unknown_user(self):
        with self.assertRaises(CommandError) as ctx:
            call_command("lp_load", self.fixtures_folder, "nobody")

        assert "No such user" in str(ctx.exception)


class RestoreUtilitiesTest(TestCase):
    """Tests for utility functions used in the restore process."""

    def test_generate_staged_package_ref(self):
        """Test generating a staged learning package ref."""

        user_mock = type("User", (), {"username": "dan"})
        package_ref = "lib:WGU:LIB_C001"
        staged_key = generate_staged_package_ref(package_ref, user_mock)

        assert staged_key.startswith("lp-restore:dan:WGU:LIB_C001:")
        parts = staged_key.split(":")
        assert len(parts) == 5
        timestamp_part = parts[-1]
        assert timestamp_part.isdigit()

    def test_generate_staged_lp_key_non_conventional_format(self):
        """Test that a non-conventional package_ref falls back gracefully."""
        user_mock = type("User", (), {"username": "dan"})
        staged_key = generate_staged_package_ref("no-colons-here", user_mock)
        assert staged_key.startswith("lp-restore:dan:no-colons-here:")


class LoaderGuardTest(TestCase):
    """
    The loader's guard rails.

    Neither of these should be reachable through the public API, because
    validation rejects the input first. They exist so that a future caller who
    skips validation fails loudly instead of writing partial data.
    """

    def _validated(self, data):
        return ValidatedLearningPackageInput(data=data, fs=None, errors=[])

    def test_refuses_input_that_failed_validation(self):
        with self.assertRaises(ValueError):
            Loader(self._validated(None))

    def test_refuses_an_unrecognized_container_type(self):
        data = CompletePackageInputData.model_construct(
            entities={
                "chapter-1": EntityInputData.model_construct(
                    container={"chapter": {}}, versions=[]
                )
            }
        )
        with self.assertRaises(UnknownContainerTypeError):
            Loader(self._validated(data))


class RestoreFailedErrorStrTest(TestCase):
    """``str()`` on the aggregate error shows every problem, not a summary."""

    def test_str_lists_the_individual_errors(self):
        error = RestoreFailedError([MissingFileError("Root Package", path="package.toml")])
        assert str(error) == error.as_text()
        assert "Root Package file not found" in str(error)


class RestoreWrapperArchiveTest(RestoreTestCase):
    """
    Archives that wrap their contents in a single folder.

    ``zip -r MyLib.zip MyLib`` compresses the folder rather than its contents,
    which is a perfectly reasonable thing to hand us. Such an archive must
    restore identically to a flat one.
    """

    def as_wrapper_dir(self, folder: str, wrapper: str = "MyLib") -> str:
        """Copy a fixture folder one level down inside a fresh temp directory."""
        tmp_dir = tempfile.TemporaryDirectory()
        self.addCleanup(tmp_dir.cleanup)
        shutil.copytree(folder, os.path.join(tmp_dir.name, wrapper))
        return tmp_dir.name

    def comparable(self, result):
        """Everything about a restore except what differs by construction."""
        data = dict(vars(result.lp_restored_data))
        del data["id"]
        del data["package_ref"]
        return data

    def test_wrapper_zip_matches_flat_archive(self):
        tmp_dir = tempfile.TemporaryDirectory()
        self.addCleanup(tmp_dir.cleanup)
        wrapped_zip = folder_to_zip_path(
            self.fixtures_folder, tmp_dir.name, prefix="MyLib/"
        )

        flat = api.load_learning_package_from_path(
            self.fixtures_folder, user=self.user, package_ref="lib:flat:one"
        )
        wrapped = api.load_learning_package_from_path(
            wrapped_zip, user=self.user, package_ref="lib:wrapped:zip"
        )

        assert self.comparable(wrapped) == self.comparable(flat)
        assert vars(wrapped.backup_metadata) == vars(flat.backup_metadata)

    def test_wrapper_directory_matches_flat_archive(self):
        flat = api.load_learning_package_from_path(
            self.fixtures_folder, user=self.user, package_ref="lib:flat:two"
        )
        wrapped = api.load_learning_package_from_path(
            self.as_wrapper_dir(self.fixtures_folder),
            user=self.user,
            package_ref="lib:wrapped:dir",
        )

        assert self.comparable(wrapped) == self.comparable(flat)

    def test_macos_style_zip(self):
        """A zip made with Finder's "Compress" carries __MACOSX and .DS_Store."""
        tmp_dir = tempfile.TemporaryDirectory()
        self.addCleanup(tmp_dir.cleanup)
        mac_zip = folder_to_zip_path(
            self.fixtures_folder,
            tmp_dir.name,
            prefix="MyLib/",
            extra_names=("__MACOSX/._MyLib", ".DS_Store"),
        )

        result = api.load_learning_package_from_path(
            mac_zip, user=self.user, package_ref="lib:wrapped:mac"
        )

        assert result.status == "success"
        assert result.lp_restored_data.num_components == 7

    def test_static_assets_survive_a_wrapper(self):
        """
        Static files still resolve when the archive is wrapped.

        The ``fs:`` pointers written during extraction are relative to the
        re-rooted filesystem, so this is what catches the case where the wrong
        filesystem gets handed downstream -- it would break images for wrapper
        archives only.
        """
        tmp_dir = tempfile.TemporaryDirectory()
        self.addCleanup(tmp_dir.cleanup)
        wrapped_zip = folder_to_zip_path(
            self.fixtures_folder, tmp_dir.name, prefix="MyLib/"
        )

        result = api.load_learning_package_from_path(
            wrapped_zip, user=self.user, package_ref="lib:wrapped:static"
        )

        component = components_api.get_components(result.lp_restored_data.id).get(
            publishable_entity__entity_ref=(
                "xblock.v1:html:e32d5479-9492-41f6-9222-550a7346bc37"
            )
        )
        draft = publishing_api.get_draft_version(component.publishable_entity.id)
        by_path = {
            cvm.path: cvm.media
            for cvm in draft.componentversion.componentversionmedia_set.all()
        }
        assert set(by_path) == {"block.xml", "static/me.png"}
        assert by_path["static/me.png"].has_file
        assert by_path["static/me.png"].read_file().read()

    def test_ambiguous_archive_is_refused(self):
        """
        Several candidate folders means we don't guess.

        ``fixtures/broken/`` holds a handful of directories that each contain a
        package.toml, so there is no single obvious root.
        """
        packages_before = publishing_api.LearningPackage.objects.count()

        with self.assertRaises(RestoreFailedError) as ctx:
            api.load_learning_package_from_path(
                os.path.join(FIXTURES_DIR, "broken"), user=self.user
            )

        assert publishing_api.LearningPackage.objects.count() == packages_before
        assert any(
            isinstance(err, MissingFileError) for err in ctx.exception.errors
        )

    def test_detected_root_is_reported_in_the_error_text(self):
        """
        When we do re-root, say so -- every path we report is relative to it.
        """
        wrapper_dir = self.as_wrapper_dir(broken_fixture("missing_lp_key"))

        with self.assertRaises(RestoreFailedError) as ctx:
            api.load_learning_package_from_path(wrapper_dir, user=self.user)

        text = ctx.exception.as_text()
        assert "Archive root: MyLib/" in text
        assert "package.toml: learning_package.key" in text
