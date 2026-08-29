"""
IMPORTANT: If you are adding new fields/behaviors, they should take the form of
*new* tests on new test data files, and not modifications to existing ones.
Please be very cautious about whether you are breaking backwards compatibility.

This module tests our ability to extract data from the backup archive TOML files
and resources, and assemble them into a combined document that represents the
entire LearningPackage, and is encapsulated in UnvalidatedLearningPackageInput.
Most of these test functions that examine individual files. The functions in
payload.py were designed to mostly accept an AbstractFileSystem and path as
arguments, so it should be possible to do simple test calls on TOML files and
dirs without having to mock anything.

These tests are strictly for the payload module, and therefore don't need Django
to run.
"""

from datetime import datetime, timezone
from pathlib import Path
from unittest import TestCase

from fsspec.implementations.dirfs import DirFileSystem

from openedx_content.applets.backup_restore import payload

TEST_DATA_ROOT = Path(__file__).parent / "payload_test_data"
FIXTURES_ROOT = Path(__file__).parent / "fixtures"


class ExtractRootPackageFileTest(TestCase):
    """Tests for reading package.toml."""

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.fs = DirFileSystem(TEST_DATA_ROOT / "root_packages")

    @classmethod
    def tearDownClass(cls):
        del cls.fs
        super().tearDownClass()

    def test_file_not_found(self):
        with self.assertRaises(payload.MissingFileError) as ctx:
            payload.extract_root_package_data(self.fs, "does_not_exist.toml")
        assert ctx.exception.path == "does_not_exist.toml"

    def test_broken_toml(self):
        with self.assertRaises(payload.InvalidTOMLError) as ctx:
            payload.extract_root_package_data(self.fs, "broken.toml")
        assert ctx.exception.path == "broken.toml"

    def test_fields_not_in_table(self):
        with self.assertRaises(payload.FieldsNotInTable) as ctx:
            payload.extract_root_package_data(self.fs, "fields_not_in_table.toml")
        assert ctx.exception.path == "fields_not_in_table.toml"
        assert ctx.exception.fields == ["created_by", "format_version"]

    def test_missing_meta_table(self):
        with self.assertRaises(payload.TableNotFoundError) as ctx:
            payload.extract_root_package_data(self.fs, "missing_meta.toml")
        assert ctx.exception.path == "missing_meta.toml"
        assert ctx.exception.table == "meta"
        assert "[meta]" in str(ctx.exception)

    def test_missing_learning_package_table(self):
        with self.assertRaises(payload.TableNotFoundError) as ctx:
            payload.extract_root_package_data(self.fs, "missing_learning_package.toml")
        assert ctx.exception.path == "missing_learning_package.toml"
        assert ctx.exception.table == "learning_package"
        assert "[learning_package]" in str(ctx.exception)

    def test_unsupported_format_version(self):
        # We don't support format_version=2
        with self.assertRaises(payload.UnsupportedFormatError):
            payload.extract_root_package_data(
                self.fs, "unsupported_format_version_2.toml"
            )
        # We don't support format_version as anthing other than number
        with self.assertRaises(payload.UnsupportedFormatError):
            payload.extract_root_package_data(
                self.fs, "unsupported_format_version_b.toml"
            )

        # ...and a boolean is not a number, even though Python's bool is a
        # subclass of int and would otherwise read as version 1.
        with self.assertRaises(payload.UnsupportedFormatError):
            payload.extract_root_package_data(
                self.fs, "unsupported_format_version_true.toml"
            )

        # We will allow format_version 1.x though, in case we want to extend our
        # format in a fully backwards compatible way.
        root_data = payload.extract_root_package_data(
            self.fs, "unsupported_format_version_1_1.toml"
        )
        assert root_data["meta"]["format_version"] == 1.1

    def test_ignore_unknown_tables(self):
        """Allow for forwards compatibility."""
        assert "unknown" in payload.extract_root_package_data(
            self.fs, "unknown_table.toml"
        )

    def test_minimal(self):
        data = payload.extract_root_package_data(self.fs, "minimal.toml")
        assert data == {
            "meta": {
                "format_version": 1,
            },
            "learning_package": {},
        }

    def test_normal(self):
        data = payload.extract_root_package_data(self.fs, "normal_ulmo_v1.toml")
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

    @classmethod
    def tearDownClass(cls):
        del cls.fs
        super().tearDownClass()

    def test_broken_toml(self):
        with self.assertRaises(payload.InvalidTOMLError) as ctx:
            payload.extract_entity_data(self.fs, "broken.toml")
        assert ctx.exception.path == "broken.toml"

    def test_missing_entity_table(self):
        with self.assertRaises(payload.TableNotFoundError) as ctx:
            payload.extract_entity_data(self.fs, "missing_entity_table.toml")
        assert ctx.exception.path == "missing_entity_table.toml"
        assert ctx.exception.table == "entity"
        assert "[entity]" in str(ctx.exception)

    def test_missing_entity_key(self):
        with self.assertRaises(payload.FieldMissing) as ctx:
            payload.extract_entity_data(self.fs, "missing_entity_key.toml")
        assert ctx.exception.missing_field == "key"
        assert ctx.exception.table == "entity"

    def test_dupes(self):
        """
        Test for duplicate entities.

        If we didn't explicitly check for this, a second file defining the same
        entity one entity would just overwrite
        the other, which would confuse people who might be assembling an archive
        file for restoring.

        This test is different from the others because extract_entities_data
        doesn't raise exceptions, it collects them from its calls to
        extract_entity_data().
        """
        paths = ["dupe_1.toml", "dupe_2.toml"]
        data, _path_mapping, errors = payload.extract_entities_data(self.fs, paths)
        assert "dupe-key" in data  # The first one should have succeeded...
        assert len(data) == 1  # but the duplicate never made it in.
        assert len(errors) == 1  # There should be only one error.

        error = errors[0]
        assert error.original_path == "dupe_1.toml"  # path of the original
        assert error.path == "dupe_2.toml"  # path where error was marked

    def test_ignore_unknown_tables(self):
        """
        Allow for forwards compatibility.

        Unknown tables *inside* [entity] are preserved, so that a newer export
        can add attributes without older code choking on them. Unknown tables at
        the top level are not part of the entity, so they don't come along.
        """
        _ref, data = payload.extract_entity_data(self.fs, "unknown_table.toml")
        assert data["future_thing"] == {"some_setting": "hello"}
        assert "future_top_level" not in data

    def test_missing_versions(self):
        """
        An entity with no [[version]] tables extracts to an empty version list.

        Whether that's actually loadable is the validation step's problem, not
        ours -- our job is only to faithfully report what's in the file.
        """
        ref, data = payload.extract_entity_data(self.fs, "missing_versions.toml")
        assert ref == "no-versions-c0ffee"
        assert data["versions"] == []
        assert data["container"] == {"unit": {}}

    def test_normal_component(self):
        ref, data = payload.extract_entity_data(self.fs, "normal_component.toml")
        assert ref == "xblock.v1:html:9f221fc4-42f1-4d07-ada4-653409bc5fff"
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
        # ...while static assets are encoded as "fs:" pointers back into the
        # archive, so that we don't hold binary files in memory.
        v3_media = versions_by_num[3]["component"]["media"]
        assert v3_media["block.xml"] == "<html><p>Version 3 text.</p></html>\n"
        assert v3_media["static/figure.png"].startswith("fs:")
        assert v3_media["static/figure.png"].endswith(
            "normal_component/component_versions/v3/static/figure.png"
        )

    def test_normal_container(self):
        ref, data = payload.extract_entity_data(self.fs, "normal_container.toml")
        assert ref == "section-9-ac4b9f"
        assert data == {
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

    @classmethod
    def tearDownClass(cls):
        del cls.fs
        super().tearDownClass()

    def test_broken_toml(self):
        with self.assertRaises(payload.InvalidTOMLError) as ctx:
            payload.extract_collection_data(self.fs, "broken.toml")
        assert ctx.exception.path == "broken.toml"

    def test_fields_not_in_table(self):
        with self.assertRaises(payload.FieldsNotInTable) as ctx:
            payload.extract_collection_data(self.fs, "fields_not_in_table.toml")
        assert ctx.exception.path == "fields_not_in_table.toml"
        assert ctx.exception.fields == ["key", "title"]

    def test_missing_collection_table(self):
        with self.assertRaises(payload.TableNotFoundError) as ctx:
            payload.extract_collection_data(self.fs, "missing_collection_table.toml")
        assert ctx.exception.path == "missing_collection_table.toml"
        assert ctx.exception.table == "collection"
        assert "[collection]" in str(ctx.exception)

    def test_normal(self):
        data = payload.extract_collection_data(self.fs, "normal.toml")
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
        dupe_1 = payload.extract_collection_data(self.fs, "dupe_1.toml")
        dupe_2 = payload.extract_collection_data(self.fs, "dupe_2.toml")
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
        unvalidated = payload.extract_unvalidated_learning_package(fs)

        assert unvalidated.errors == []
        assert unvalidated.raw_data["learning_package"]["key"] == "lib:WGU:LIB_C001"
        assert unvalidated.raw_data["meta"]["format_version"] == 1
        assert len(unvalidated.raw_data["entities"]) == 10
        assert len(unvalidated.raw_data["collections"]) == 1

    def test_entity_path_mapping_uses_declared_key(self):
        """
        The mapping is keyed by the entity's declared key, not its filename.

        Two fixture files deliberately have names that don't match the key
        inside them, because the export side hashes filenames to avoid
        collisions.
        """
        fs = DirFileSystem(FIXTURES_ROOT / "library_backup")
        unvalidated = payload.extract_unvalidated_learning_package(fs)

        assert (
            unvalidated.entity_path_mapping["section1-8ca126"]
            == "entities/section1-extra-8ca126.toml"
        )
        assert unvalidated.entity_path_mapping[
            "xblock.v1:html:c22b9f97-f1e9-4e8f-87f0-d5a3c26083e2"
        ].endswith("c22b9f97-f1e9-4e8f-87f0-d5a3c26083e2-extra.toml")

    def test_missing_root_package_is_collected_not_raised(self):
        fs = DirFileSystem(TEST_DATA_ROOT / "empty_archive")
        unvalidated = payload.extract_unvalidated_learning_package(fs)

        assert len(unvalidated.errors) == 1
        error = unvalidated.errors[0]
        assert isinstance(error, payload.MissingFileError)
        assert error.path == "package.toml"

        # We still return a usable object, just an empty one.
        assert unvalidated.raw_data["entities"] == {}
        assert unvalidated.raw_data["collections"] == []

    def test_duplicate_entities_are_collected(self):
        fs = DirFileSystem(TEST_DATA_ROOT / "duplicate_entities")
        unvalidated = payload.extract_unvalidated_learning_package(fs)

        duplicate_errors = [
            err for err in unvalidated.errors
            if isinstance(err, payload.DuplicateFoundError)
        ]
        assert len(duplicate_errors) == 1
        # The first file to declare the key wins; the second is the error.
        assert duplicate_errors[0].original_path == "entities/dupe_1.toml"
        assert duplicate_errors[0].path == "entities/dupe_2.toml"
        assert "dupe-key" in unvalidated.raw_data["entities"]

    def test_static_assets_are_not_mistaken_for_entities(self):
        """
        TOML files under component_versions/ are static assets, not entities.
        """
        fs = DirFileSystem(FIXTURES_ROOT / "library_backup")
        paths = payload.get_entity_file_paths(fs)

        assert paths == sorted(paths)  # deterministic ordering
        assert all("/component_versions/" not in path for path in paths)

    def test_collection_errors_are_collected(self):
        fs = DirFileSystem(TEST_DATA_ROOT / "broken_collection")
        unvalidated = payload.extract_unvalidated_learning_package(fs)

        assert len(unvalidated.errors) == 1
        error = unvalidated.errors[0]
        assert isinstance(error, payload.InvalidTOMLError)
        assert error.path == "collections/broken.toml"

        # The rest of the archive still came through.
        assert unvalidated.raw_data["learning_package"]["key"] == "lib:Axim:FunLib"
