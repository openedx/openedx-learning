"""
Tests relating to dumping learning packages to disk
"""
import zipfile
from datetime import datetime, timezone
from io import StringIO
from pathlib import Path

from django.contrib.auth import get_user_model
from django.core.management import CommandError, call_command

from openedx_learning.api import authoring as api
from openedx_learning.api.authoring_models import LearningPackage
from openedx_learning.lib.test_utils import TestCase

User = get_user_model()


class LpDumpCommandTestCase(TestCase):
    """
    Test serving static assets (Content files, via Component lookup).
    """

    learning_package: LearningPackage

    @classmethod
    def setUpTestData(cls):
        """
        Initialize our content data
        """
        cls.user = User.objects.create(
            username="user",
            email="user@example.com",
        )

        cls.learning_package = api.create_learning_package(
            key="ComponentTestCase-test-key",
            title="Components Test Case Learning Package",
        )
        cls.learning_package_2 = api.create_learning_package(
            key="ComponentTestCase-test-key-2",
            title="Components Test Case another Learning Package",
        )
        cls.now = datetime(2024, 8, 5, tzinfo=timezone.utc)

        cls.html_type = api.get_or_create_component_type("xblock.v1", "html")
        cls.problem_type = api.get_or_create_component_type("xblock.v1", "problem")
        created_time = datetime(2025, 4, 1, tzinfo=timezone.utc)
        cls.draft_unit = api.create_unit(
            learning_package_id=cls.learning_package.id,
            key="unit-1",
            created=created_time,
            created_by=cls.user.id,
        )

        # Make and publish one Component
        cls.published_component, _ = api.create_component_and_version(
            cls.learning_package.id,
            cls.problem_type,
            local_key="my_published_example",
            title="My published problem",
            created=cls.now,
            created_by=cls.user.id,
        )
        api.publish_all_drafts(
            cls.learning_package.id,
            message="Publish from CollectionTestCase.setUpTestData",
            published_at=cls.now,
        )

        # Create a Draft component, one in each learning package
        cls.draft_component, _ = api.create_component_and_version(
            cls.learning_package.id,
            cls.html_type,
            local_key="my_draft_example",
            title="My draft html",
            created=cls.now,
            created_by=cls.user.id,
        )

    def check_zip_file_structure(self, zip_path: Path):
        """
        Check that the zip file has the expected structure.
        """

        with zipfile.ZipFile(zip_path, 'r') as zip_file:
            # Check that the zip file contains the expected files
            expected_files = [
                "package.toml",
                "entities/",
                "entities/xblock.v1:problem:my_published_example.toml",
                "entities/xblock.v1:html:my_draft_example.toml",
            ]
            for expected_file in expected_files:
                self.assertIn(expected_file, zip_file.namelist())

    def test_lp_dump_command(self):
        lp_key = self.learning_package.key
        file_name = f"{lp_key}.zip"
        try:
            out = StringIO()

            # Call the management command to dump the learning package
            call_command("lp_dump", lp_key, file_name, stdout=out)

            # Check that the zip file was created
            self.assertTrue(Path(file_name).exists())
            # Check the structure of the zip file
            self.check_zip_file_structure(Path(file_name))

            # Check the output message
            message = f'{lp_key} written to {file_name}'
            self.assertIn(message, out.getvalue())
        except Exception as e:  # pylint: disable=broad-exception-caught
            self.fail(f"lp_dump command failed with error: {e}")
        finally:
            # Clean up the created zip file
            if Path(file_name).exists():
                Path(file_name).unlink(missing_ok=True)

    def test_dump_nonexistent_learning_package(self):
        out = StringIO()
        lp_key = "nonexistent_lp"
        file_name = f"{lp_key}.zip"
        with self.assertRaises(CommandError):
            # Attempt to dump a learning package that does not exist
            call_command("lp_dump", lp_key, file_name, stdout=out)
            self.assertIn("Learning package 'nonexistent_lp' does not exist", out.getvalue())
