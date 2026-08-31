"""
IMPORTANT: If you are adding new fields/behaviors, they should take the form of
*new* tests on new test data files, and not modifications to existing ones.
Please be very cautious about whether you are breaking backwards compatibility.

This module tests our ability to extract data from the backup archive TOML files
and resources, and assemble them into a combined document that represents the
entire LearningPackage, and is encapsulated in UnvalidatedLearningPackageInput.
Most of these test methods examine individual files. PayloadExtractor takes the
filesystem once, at construction, and its methods take a path, so it should be
possible to do simple test calls on TOML files and dirs without having to mock
anything.

These tests are strictly for the payload module, and therefore don't need Django
to run.
"""

import io
import tempfile
import zipfile
from datetime import datetime, timezone
from pathlib import Path
from unittest import TestCase

from fsspec.implementations.dirfs import DirFileSystem
from fsspec.implementations.zip import ZipFileSystem

from openedx_content.applets.backup_restore import payload

TEST_DATA_ROOT = Path(__file__).parent / "payload_test_data"
FIXTURES_ROOT = Path(__file__).parent / "fixtures"


class ExtractRootPackageFileTest(TestCase):
    """Tests for reading package.toml."""

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.fs = DirFileSystem(TEST_DATA_ROOT / "root_packages")
        cls.extractor = payload.PayloadExtractor(cls.fs)

    @classmethod
    def tearDownClass(cls):
        del cls.fs
        del cls.extractor
        super().tearDownClass()

    def test_file_not_found(self):
        with self.assertRaises(payload.MissingFileError) as ctx:
            self.extractor.extract_root_package_data("does_not_exist.toml")
        assert ctx.exception.path == "does_not_exist.toml"

    def test_broken_toml(self):
        with self.assertRaises(payload.InvalidTOMLError) as ctx:
            self.extractor.extract_root_package_data("broken.toml")
        assert ctx.exception.path == "broken.toml"

    def test_fields_not_in_table(self):
        with self.assertRaises(payload.FieldsNotInTable) as ctx:
            self.extractor.extract_root_package_data("fields_not_in_table.toml")
        assert ctx.exception.path == "fields_not_in_table.toml"
        assert ctx.exception.fields == ["created_by", "format_version"]

    def test_missing_meta_table(self):
        with self.assertRaises(payload.TableNotFoundError) as ctx:
            self.extractor.extract_root_package_data("missing_meta.toml")
        assert ctx.exception.path == "missing_meta.toml"
        assert ctx.exception.table == "meta"
        assert "[meta]" in str(ctx.exception)

    def test_missing_learning_package_table(self):
        with self.assertRaises(payload.TableNotFoundError) as ctx:
            self.extractor.extract_root_package_data("missing_learning_package.toml")
        assert ctx.exception.path == "missing_learning_package.toml"
        assert ctx.exception.table == "learning_package"
        assert "[learning_package]" in str(ctx.exception)

    def test_unsupported_format_version(self):
        # We don't support format_version=2
        with self.assertRaises(payload.UnsupportedFormatError):
            self.extractor.extract_root_package_data("unsupported_format_version_2.toml")
        # We don't support format_version as anthing other than number
        with self.assertRaises(payload.UnsupportedFormatError):
            self.extractor.extract_root_package_data("unsupported_format_version_b.toml")

        # ...and a boolean is not a number, even though Python's bool is a
        # subclass of int and would otherwise read as version 1.
        with self.assertRaises(payload.UnsupportedFormatError):
            self.extractor.extract_root_package_data("unsupported_format_version_true.toml")

        # We will allow format_version 1.x though, in case we want to extend our
        # format in a fully backwards compatible way.
        root_data = self.extractor.extract_root_package_data("unsupported_format_version_1_1.toml")
        assert root_data["meta"]["format_version"] == 1.1

    def test_ignore_unknown_tables(self):
        """Allow for forwards compatibility."""
        assert "unknown" in self.extractor.extract_root_package_data("unknown_table.toml")

    def test_minimal(self):
        data = self.extractor.extract_root_package_data("minimal.toml")
        assert data == {
            "meta": {
                "format_version": 1,
            },
            "learning_package": {},
        }

    def test_normal(self):
        data = self.extractor.extract_root_package_data("normal_ulmo_v1.toml")
        assert data == {
            "meta": {
                "format_version": 1,
                "created_by": "eddy",
                "created_by_email": "eddy@axim.org",
                "created_at": datetime(
                    2026, 3, 11, 19, 20, 20, 394360, tzinfo=timezone.utc
                ),
                "origin_server": "studio.local.openedx.io",
            },
            "learning_package": {
                "title": "Fun Library",
                "key": "lib:Axim:FunLib",
                "description": "My very fun library! 🐢",
                "created": datetime(
                    2026, 2, 11, 16, 32, 47, 524556, tzinfo=timezone.utc
                ),
                "updated": datetime(
                    2026, 2, 20, 16, 32, 47, 524556, tzinfo=timezone.utc
                ),
            },
        }


class ExtractEntityDataTest(TestCase):
    """Tests for reading a single entity TOML file."""

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.fs = DirFileSystem(TEST_DATA_ROOT / "entities")
        cls.extractor = payload.PayloadExtractor(cls.fs)

    @classmethod
    def tearDownClass(cls):
        del cls.fs
        del cls.extractor
        super().tearDownClass()

    def test_broken_toml(self):
        with self.assertRaises(payload.InvalidTOMLError) as ctx:
            self.extractor.extract_entity_data("broken.toml")
        assert ctx.exception.path == "broken.toml"

    def test_missing_entity_table(self):
        with self.assertRaises(payload.TableNotFoundError) as ctx:
            self.extractor.extract_entity_data("missing_entity_table.toml")
        assert ctx.exception.path == "missing_entity_table.toml"
        assert ctx.exception.table == "entity"
        assert "[entity]" in str(ctx.exception)

    def test_missing_entity_key(self):
        """
        An entity with no key extracts fine; rejecting it is validation's job.

        See test_validation.DuplicateEntityTest.test_missing_entity_key.
        """
        data = self.extractor.extract_entity_data("missing_entity_key.toml")
        assert "key" not in data
        assert data["src_path"] == "missing_entity_key.toml"

    def test_dupes(self):
        """
        Two files declaring the same entity key both survive extraction.

        This is the property that lets validation reject the duplicate and name
        both files. If we collapsed entities into a dict keyed by their ref, the
        second definition would overwrite the first and there would be nothing
        left to report.
        """
        paths = ["dupe_1.toml", "dupe_2.toml"]
        data, errors = self.extractor.extract_entities_data(paths)

        assert not errors
        assert [entity["key"] for entity in data] == ["dupe-key", "dupe-key"]
        # Each one knows where it came from, which is what makes the eventual
        # error message actionable.
        assert [entity["src_path"] for entity in data] == paths

    def test_broken_files_are_collected_not_raised(self):
        """
        extract_entities_data gathers per-file errors instead of raising.

        One unreadable entity shouldn't stop us reporting on the rest of them.
        """
        data, errors = self.extractor.extract_entities_data(
            ["broken.toml", "normal_container.toml"]
        )

        assert [type(err) for err in errors] == [payload.InvalidTOMLError]
        assert errors[0].path == "broken.toml"
        assert [entity["key"] for entity in data] == ["section-9-ac4b9f"]

    def test_ignore_unknown_tables(self):
        """
        Allow for forwards compatibility.

        Unknown tables *inside* [entity] are preserved, so that a newer export
        can add attributes without older code choking on them. Unknown tables at
        the top level are not part of the entity, so they don't come along.
        """
        data = self.extractor.extract_entity_data("unknown_table.toml")
        assert data["future_thing"] == {"some_setting": "hello"}
        assert "future_top_level" not in data

    def test_missing_versions(self):
        """
        An entity with no [[version]] tables extracts to an empty version list.

        Whether that's actually loadable is the validation step's problem, not
        ours -- our job is only to faithfully report what's in the file.
        """
        data = self.extractor.extract_entity_data("missing_versions.toml")
        assert data["key"] == "no-versions-c0ffee"
        assert data["versions"] == []
        assert data["container"] == {"unit": {}}

    def test_normal_component(self):
        data = self.extractor.extract_entity_data("normal_component.toml")
        assert data["key"] == "xblock.v1:html:9f221fc4-42f1-4d07-ada4-653409bc5fff"
        assert data["src_path"] == "normal_component.toml"
        assert data["can_stand_alone"] is True
        assert data["created"] == datetime(
            2026, 4, 8, 15, 22, 12, 780012, tzinfo=timezone.utc
        )
        assert data["draft"] == {"version_num": 3}
        assert data["published"] == {"version_num": 2}

        # Components have no container table at all.
        assert "container" not in data

        versions_by_num = {v["version_num"]: v for v in data["versions"]}
        assert sorted(versions_by_num) == [2, 3]

        # Text media is inlined...
        assert versions_by_num[2]["component"]["media"] == {
            "block.xml": "<html><p>Version 2 text.</p></html>\n",
        }
        # ...while static assets are encoded as pointers back into the
        # archive, so that we don't hold binary files in memory.
        v3_media = versions_by_num[3]["component"]["media"]
        assert v3_media["block.xml"] == "<html><p>Version 3 text.</p></html>\n"
        assert v3_media["static/figure.png"] == "normal_component/component_versions/v3/static/figure.png"

    def test_normal_container(self):
        data = self.extractor.extract_entity_data("normal_container.toml")
        assert data == {
            'key': 'section-9-ac4b9f',
            'src_path': 'normal_container.toml',
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


class ExtractCollectionDataTest(TestCase):
    """Tests for reading a single collection TOML file."""

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.fs = DirFileSystem(TEST_DATA_ROOT / "collections")
        cls.extractor = payload.PayloadExtractor(cls.fs)

    @classmethod
    def tearDownClass(cls):
        del cls.fs
        del cls.extractor
        super().tearDownClass()

    def test_broken_toml(self):
        with self.assertRaises(payload.InvalidTOMLError) as ctx:
            self.extractor.extract_collection_data("broken.toml")
        assert ctx.exception.path == "broken.toml"

    def test_fields_not_in_table(self):
        with self.assertRaises(payload.FieldsNotInTable) as ctx:
            self.extractor.extract_collection_data("fields_not_in_table.toml")
        assert ctx.exception.path == "fields_not_in_table.toml"
        assert ctx.exception.fields == ["key", "title"]

    def test_missing_collection_table(self):
        with self.assertRaises(payload.TableNotFoundError) as ctx:
            self.extractor.extract_collection_data("missing_collection_table.toml")
        assert ctx.exception.path == "missing_collection_table.toml"
        assert ctx.exception.table == "collection"
        assert "[collection]" in str(ctx.exception)

    def test_normal(self):
        data = self.extractor.extract_collection_data("normal.toml")
        assert data == {
            "title": "Difficult Problems",
            "key": "difficult-problems",
            "description": "The tricky ones. 🐢",
            "created": datetime(2026, 3, 11, 19, 20, 20, 394360, tzinfo=timezone.utc),
            "entities": [
                "xblock.v1:problem:e1f4b0a2-0000-4000-8000-000000000001",
                "xblock.v1:problem:e1f4b0a2-0000-4000-8000-000000000002",
            ],
            # Tracked so that validation errors can name the file they came from.
            "src_path": "normal.toml",
        }

    def test_dupes_are_not_caught_here(self):
        """
        Duplicate Collection keys are a validation-level problem, not an
        extraction-level one.

        Unlike entities -- which are assembled into a dict keyed by entity ref,
        so a duplicate would silently overwrite -- collections are assembled into
        a list. Nothing is lost at this layer, so we extract both and let
        CompletePackageInputData.check_for_duplicate_keys reject them.
        """
        dupe_1 = self.extractor.extract_collection_data("dupe_1.toml")
        dupe_2 = self.extractor.extract_collection_data("dupe_2.toml")
        assert dupe_1["key"] == dupe_2["key"] == "dupe-collection-key"
        assert dupe_1["src_path"] != dupe_2["src_path"]


class ExtractUnvalidatedLearningPackageTest(TestCase):
    """
    Tests for assembling a whole archive, rather than a single file.

    The important behavior here is that this function *collects* errors instead
    of raising them, so that someone repairing an archive by hand sees every
    problem at once.
    """

    def test_normal(self):
        fs = DirFileSystem(FIXTURES_ROOT / "library_backup")
        unvalidated = payload.PayloadExtractor(fs).extract()

        assert unvalidated.errors == []
        assert unvalidated.raw_data["learning_package"]["key"] == "lib:WGU:LIB_C001"
        assert unvalidated.raw_data["meta"]["format_version"] == 1
        assert len(unvalidated.raw_data["entities"]) == 10
        assert len(unvalidated.raw_data["collections"]) == 1

    def test_each_entity_records_its_own_source_file(self):
        """
        src_path is the file, key is what's declared inside it.

        Two fixture files deliberately have names that don't match the key
        inside them, because the export side hashes filenames to avoid
        collisions.
        """
        fs = DirFileSystem(FIXTURES_ROOT / "library_backup")
        unvalidated = payload.PayloadExtractor(fs).extract()

        paths_by_key = {
            entity["key"]: entity["src_path"]
            for entity in unvalidated.raw_data["entities"]
        }
        assert (
            paths_by_key["section1-8ca126"] == "entities/section1-extra-8ca126.toml"
        )
        assert paths_by_key[
            "xblock.v1:html:c22b9f97-f1e9-4e8f-87f0-d5a3c26083e2"
        ].endswith("c22b9f97-f1e9-4e8f-87f0-d5a3c26083e2-extra.toml")

    def test_missing_root_package_is_collected_not_raised(self):
        fs = DirFileSystem(TEST_DATA_ROOT / "empty_archive")
        unvalidated = payload.PayloadExtractor(fs).extract()

        assert len(unvalidated.errors) == 1
        error = unvalidated.errors[0]
        assert isinstance(error, payload.MissingFileError)
        assert error.path == "package.toml"

        # We still return a usable object, just an empty one.
        assert unvalidated.raw_data["entities"] == []
        assert unvalidated.raw_data["collections"] == []

    def test_duplicate_entities_both_survive_extraction(self):
        """
        Extraction doesn't reject duplicates -- it preserves them for validation.
        """
        fs = DirFileSystem(TEST_DATA_ROOT / "duplicate_entities")
        unvalidated = payload.PayloadExtractor(fs).extract()

        # This fixture is only the two entity files, so the absent package.toml
        # is expected. What matters is that the duplicate isn't an error here.
        assert [type(err) for err in unvalidated.errors] == [payload.MissingFileError]

        entities = unvalidated.raw_data["entities"]
        assert [entity["key"] for entity in entities] == ["dupe-key", "dupe-key"]
        assert [entity["src_path"] for entity in entities] == [
            "entities/dupe_1.toml",
            "entities/dupe_2.toml",
        ]

    def test_static_assets_are_not_mistaken_for_entities(self):
        """
        TOML files under component_versions/ are static assets, not entities.
        """
        fs = DirFileSystem(FIXTURES_ROOT / "library_backup")
        paths = payload.PayloadExtractor(fs).get_entity_file_paths()

        assert paths == sorted(paths)  # deterministic ordering
        assert all("/component_versions/" not in path for path in paths)

    def test_collection_errors_are_collected(self):
        fs = DirFileSystem(TEST_DATA_ROOT / "broken_collection")
        unvalidated = payload.PayloadExtractor(fs).extract()

        assert len(unvalidated.errors) == 1
        error = unvalidated.errors[0]
        assert isinstance(error, payload.InvalidTOMLError)
        assert error.path == "collections/broken.toml"

        # The rest of the archive still came through.
        assert unvalidated.raw_data["learning_package"]["key"] == "lib:Axim:FunLib"


def dir_fs_with(tmp_path, layout: dict) -> DirFileSystem:
    """
    Build a throwaway directory tree and return a filesystem over it.

    ``layout`` maps relative paths to file contents.
    """
    for rel_path, contents in layout.items():
        target = Path(tmp_path) / rel_path
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(contents)
    return DirFileSystem(tmp_path)


def zip_fs_with(names) -> ZipFileSystem:
    """Build an in-memory zip containing ``names``, and return a filesystem over it."""
    buffer = io.BytesIO()
    with zipfile.ZipFile(buffer, "w") as zipf:
        for name in names:
            zipf.writestr(name, "[meta]\nformat_version = 1\n")
    buffer.seek(0)
    return ZipFileSystem(fo=buffer, mode="r")


class FindArchiveRootTest(TestCase):
    """
    Tests for accepting archives that wrap their contents in a single folder.

    People routinely build an archive with ``zip -r MyLib.zip MyLib`` rather than
    compressing the folder's *contents*, and the result is perfectly sensible to
    them. We accept it rather than reporting a missing package.toml.

    Both a zip and a plain directory are covered, because fsspec's ``ls("")``
    behaves differently on each.
    """

    PACKAGE = "[meta]\nformat_version = 1\n"

    def setUp(self):
        super().setUp()
        self._tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self._tmp.cleanup)
        self.tmp_path = self._tmp.name

    def test_package_at_top_level_zip(self):
        fs = zip_fs_with(["package.toml", "entities/unit1.toml"])
        assert payload.PayloadExtractor.find_archive_root(fs) == "/"

    def test_package_at_top_level_dir(self):
        fs = dir_fs_with(self.tmp_path, {"package.toml": self.PACKAGE})
        assert payload.PayloadExtractor.find_archive_root(fs) == "/"

    def test_single_wrapper_folder_zip(self):
        fs = zip_fs_with(["MyLib/package.toml", "MyLib/entities/unit1.toml"])
        assert payload.PayloadExtractor.find_archive_root(fs) == "MyLib"

    def test_single_wrapper_folder_dir(self):
        fs = dir_fs_with(self.tmp_path, {"MyLib/package.toml": self.PACKAGE})
        assert payload.PayloadExtractor.find_archive_root(fs) == "MyLib"

    def test_macos_style_zip(self):
        """
        macOS's "Compress" adds __MACOSX and often .DS_Store beside the folder.

        This is the single most common way a non-technical user produces a zip,
        so a rule that just counted top-level entries would fail on most of them.
        """
        fs = zip_fs_with([
            "MyLib/package.toml",
            "MyLib/entities/unit1.toml",
            "__MACOSX/._MyLib",
            ".DS_Store",
        ])
        assert payload.PayloadExtractor.find_archive_root(fs) == "MyLib"

    def test_wrapper_folder_beside_a_stray_file(self):
        fs = zip_fs_with(["MyLib/package.toml", "README.txt"])
        assert payload.PayloadExtractor.find_archive_root(fs) == "MyLib"

    def test_folder_without_a_package_toml_is_not_a_root(self):
        """
        Requiring package.toml inside the candidate is what makes this safe.

        Without that check, any archive whose top level happened to hold a single
        directory would be re-rooted into it.
        """
        fs = zip_fs_with(["MyLib/entities/unit1.toml"])
        assert payload.PayloadExtractor.find_archive_root(fs) == "/"

    def test_two_candidate_folders_are_ambiguous(self):
        fs = zip_fs_with(["LibA/package.toml", "LibB/package.toml"])
        assert payload.PayloadExtractor.find_archive_root(fs) == "/"

    def test_nested_two_levels_is_not_followed(self):
        """We only look one level down; deeper nesting isn't worth guessing at."""
        fs = zip_fs_with(["Outer/MyLib/package.toml"])
        assert payload.PayloadExtractor.find_archive_root(fs) == "/"

    def test_empty_archive(self):
        fs = dir_fs_with(self.tmp_path, {})
        assert payload.PayloadExtractor.find_archive_root(fs) == "/"

    def test_entities_fixture_is_not_re_rooted(self):
        """
        Regression guard for the fixture that nearly broke this.

        ``payload_test_data/entities/`` holds exactly one subdirectory,
        ``normal_component/``. A rule based on "a single top-level folder" would
        silently re-root into it and break every entity test in this module.
        """
        fs = DirFileSystem(TEST_DATA_ROOT / "entities")
        assert payload.PayloadExtractor.find_archive_root(fs) == "/"
        assert payload.PayloadExtractor(fs).fs.path == ""


class AlwaysRerootedTest(TestCase):
    """
    PayloadExtractor always wraps its source filesystem, wrapper or not.

    This is what lets ``fs.path`` be the single answer to "what did we treat as
    the root?", which is why nothing stores that separately any more. Skipping
    the wrap when no wrapper folder is found would pass every other test in this
    module and quietly leave ``fs.path`` meaning two different things: "" for a
    zip, but an absolute local path for a directory.
    """

    PACKAGE = "[meta]\nformat_version = 1\n"

    def setUp(self):
        super().setUp()
        self._tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self._tmp.cleanup)
        self.tmp_path = self._tmp.name

    def test_flat_zip_is_still_wrapped(self):
        extractor = payload.PayloadExtractor(zip_fs_with(["package.toml"]))

        assert isinstance(extractor.fs, DirFileSystem)
        assert extractor.fs.path == ""

    def test_flat_directory_is_still_wrapped(self):
        source_fs = dir_fs_with(self.tmp_path, {"package.toml": self.PACKAGE})
        extractor = payload.PayloadExtractor(source_fs)

        assert isinstance(extractor.fs, DirFileSystem)
        # Not the absolute local path that source_fs is rooted at.
        assert extractor.fs.path == ""
        assert source_fs.path != ""

    def test_wrapped_archive_records_the_folder(self):
        extractor = payload.PayloadExtractor(zip_fs_with(["MyLib/package.toml"]))

        assert isinstance(extractor.fs, DirFileSystem)
        assert extractor.fs.path == "MyLib"

    def test_the_wrapper_is_a_pass_through_when_there_is_no_root(self):
        """An identity wrap must not disturb any path operation."""
        source_fs = dir_fs_with(self.tmp_path, {
            "package.toml": self.PACKAGE,
            "entities/unit1.toml": "[entity]\nkey = \"unit1\"\n",
        })
        extractor = payload.PayloadExtractor(source_fs)

        assert extractor.fs.exists("package.toml")
        assert extractor.fs.glob("entities/*.toml") == ["entities/unit1.toml"]
        assert extractor.fs.read_text("package.toml") == self.PACKAGE


class ExtractThroughWrapperTest(TestCase):
    """
    Extracting a wrapper-style archive gives the same result as a flat one.

    Everything the extractor reports is relative to the detected root, so the
    only observable difference should be ``root`` itself.
    """

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        flat_fs = DirFileSystem(FIXTURES_ROOT / "library_backup")
        cls.flat = payload.PayloadExtractor(flat_fs).extract()

        # The same fixture, but nested one level down inside "MyLib/".
        wrapped_fs = DirFileSystem(FIXTURES_ROOT)
        cls.wrapped_extractor = payload.PayloadExtractor(wrapped_fs)

    def test_flat_archive_has_no_root(self):
        assert self.flat.fs.path == ""

    def test_wrapper_root_is_detected(self):
        """
        ``fixtures/`` holds library_backup (with a package.toml) and broken/
        (without one), so library_backup is the only candidate.
        """
        assert self.wrapped_extractor.fs.path == "library_backup"

    def test_raw_data_matches_the_flat_archive(self):
        wrapped = self.wrapped_extractor.extract()

        assert wrapped.errors == []
        assert wrapped.raw_data == self.flat.raw_data

    def test_paths_are_relative_to_the_detected_root(self):
        wrapped = self.wrapped_extractor.extract()

        paths_by_key = {
            entity["key"]: entity["src_path"]
            for entity in wrapped.raw_data["entities"]
        }
        assert paths_by_key["section1-8ca126"] == "entities/section1-extra-8ca126.toml"

    def test_static_asset_pointers_resolve_against_the_returned_fs(self):
        """
        The file pointers are relative to the *re-rooted* filesystem.

        This is the subtle one: if extract() returned the original filesystem
        instead of the re-rooted one, these pointers would not resolve, and
        static assets would silently go missing for wrapper archives only.
        """
        wrapped = self.wrapped_extractor.extract()
        entity = next(
            e for e in wrapped.raw_data["entities"]
            if e["key"] == "xblock.v1:html:e32d5479-9492-41f6-9222-550a7346bc37"
        )
        version = next(v for v in entity["versions"] if v["version_num"] == 5)
        pointer = version["component"]["media"]["static/me.png"]

        assert wrapped.fs.read_bytes(pointer)
