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
from unittest import TestCase, skip

from fsspec.implementations.dirfs import DirFileSystem

from openedx_content.applets.backup_restore import payload


TEST_DATA_ROOT = Path(__file__).parent / "payload_test_data"


class ExtractRootPackageFileTest(TestCase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.fs = DirFileSystem(TEST_DATA_ROOT / "root_packages")

    @classmethod
    def tearDownClass(cls):
        del cls.fs
        super().tearDownClass()

    def test_file_not_found(self):
        with self.assertRaises(payload.FileNotFoundError) as err:
            payload.extract_root_package_data(self.fs, "does_not_exist.toml")
            assert err.path == "does_not_exist.toml"

    def test_broken_toml(self):
        with self.assertRaises(payload.InvalidTOMLError) as err:
            payload.extract_root_package_data(self.fs, "broken.toml")
            assert err.path == "broken.toml"

    def test_fields_not_in_table(self):
        with self.assertRaises(payload.FieldsNotInTable) as err:
            payload.extract_root_package_data(self.fs, "fields_not_in_table.toml")
            assert err.path == "fields_not_in_table.toml"
            assert err.fields == ["created_by", "format_version"]

    def test_missing_meta_table(self):
        with self.assertRaises(payload.TableNotFoundError) as err:
            payload.extract_root_package_data(self.fs, "missing_meta.toml")
            assert err.path == "missing_meta.toml"
            assert err.table == "meta"
            assert "[meta]" in str(err)

    def test_missing_learning_package_table(self):
        with self.assertRaises(payload.TableNotFoundError) as err:
            payload.extract_root_package_data(self.fs, "missing_learning_package.toml")
            assert err.path == "missing_learning_package.toml"
            assert err.table == "learning_package"
            assert "[learning_package]" in str(err)

    def test_unsupported_format_version(self):
        # We don't support format_version=2
        with self.assertRaises(payload.UnsupportedFormatError) as err:
            payload.extract_root_package_data(
                self.fs, "unsupported_format_version_2.toml"
            )
        # We don't support format_version as anthing other than number
        with self.assertRaises(payload.UnsupportedFormatError) as err:
            payload.extract_root_package_data(
                self.fs, "unsupported_format_version_b.toml"
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
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.fs = DirFileSystem(TEST_DATA_ROOT / "entities")

    @classmethod
    def tearDownClass(cls):
        del cls.fs
        super().tearDownClass()

    def test_broken_toml(self):
        with self.assertRaises(payload.InvalidTOMLError) as err:
            payload.extract_entity_data(self.fs, "broken.toml")

    def test_missing_entity_table(self):
        with self.assertRaises(payload.TableNotFoundError) as err:
            payload.extract_entity_data(self.fs, "missing_entity_table.toml")
            assert err.path == "missing_entity_table.toml"
            assert err.table == "entity"
            assert "[entity]" in str(err)

    def test_missing_entity_key(self):
        with self.assertRaises(payload.FieldMissing) as err:
            payload.extract_entity_data(self.fs, "missing_entity_key.toml")
            assert err.missing_field == "key"
            assert err.table == "entity"

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

    @skip
    def test_ignore_unknown_tables(self):
        # assert "unknown" in payload.extract_root_package_data(self.fs, "unknown_table.toml")
        pass

    @skip
    def test_normal_component(self):
        pass

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


