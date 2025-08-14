"""
Tests relating to dumping learning packages to disk
"""
import zipfile
from datetime import datetime, timezone
from io import StringIO
from pathlib import Path

from django.contrib.auth import get_user_model
from django.core.management import CommandError, call_command
from django.db.models import QuerySet

from openedx_learning.api import authoring as api
from openedx_learning.api.authoring_models import Component, LearningPackage
from openedx_learning.lib.test_utils import TestCase

User = get_user_model()


class LpDumpCommandTestCase(TestCase):
    """
    Test serving static assets (Content files, via Component lookup).
    """

    learning_package: LearningPackage
    all_components: QuerySet[Component]

    @classmethod
    def setUpTestData(cls):
        """
        Initialize our content data
        """

        # Create a user for the test
        cls.user = User.objects.create(
            username="user",
            email="user@example.com",
        )

        # Create a Learning Package for the test
        cls.learning_package = api.create_learning_package(
            key="ComponentTestCase-test-key",
            title="Components Test Case Learning Package",
            description="This is a test learning package for components.",
        )
        cls.now = datetime(2024, 8, 5, tzinfo=timezone.utc)

        cls.xblock_v1_namespace = "xblock.v1"

        # Create component types
        cls.html_type = api.get_or_create_component_type(cls.xblock_v1_namespace, "html")
        cls.problem_type = api.get_or_create_component_type(cls.xblock_v1_namespace, "problem")

        # Make and publish one Component
        cls.published_component, _ = api.create_component_and_version(
            cls.learning_package.id,
            cls.problem_type,
            local_key="my_published_example",
            title="My published problem",
            created=cls.now,
            created_by=cls.user.id,
        )

        # Create a Content entry for the published Component
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

        api.create_component_version(
            cls.draft_component.pk,
            version_num=cls.draft_component.versioning.draft.version_num + 1,
            title="My draft html v2",
            created=cls.now,
            created_by=cls.user.id,
        )

        components = api.get_entities(cls.learning_package)
        cls.all_components = components

    def check_toml_file(self, zip_path: Path, zip_member_name: Path, content_to_check: list):
        """
        Check that a specific entity TOML file in the zip matches the expected content.
        """
        with zipfile.ZipFile(zip_path, "r") as zip_file:
            with zip_file.open(str(zip_member_name)) as toml_file:
                toml_content = toml_file.read().decode("utf-8")
                for value in content_to_check:
                    self.assertIn(value, toml_content)

    def check_zip_file_structure(self, zip_path: Path):
        """
        Check that the zip file has the expected structure.
        """

        with zipfile.ZipFile(zip_path, "r") as zip_file:
            # Check that the zip file contains the expected files
            expected_files = [
                "package.toml",
                "entities/",
                "collections/",
                "entities/xblock.v1/",
                "entities/xblock.v1/html/",
                "entities/xblock.v1/html/my_draft_example/",
                "entities/xblock.v1/html/my_draft_example/component_versions/",
                "entities/xblock.v1/html/my_draft_example/component_versions/v1/",
                "entities/xblock.v1/html/my_draft_example/component_versions/v1/static/",
                "entities/xblock.v1/problem/",
                "entities/xblock.v1/problem/my_published_example/",
                "entities/xblock.v1/problem/my_published_example/component_versions/",
                "entities/xblock.v1/problem/my_published_example/component_versions/v1/",
                "entities/xblock.v1/problem/my_published_example/component_versions/v1/static/",
            ]

            # Add expected entity files
            for entity in self.all_components:
                expected_files.append(f"entities/{entity.key}.toml")

            # Check that all expected files are present
            for expected_file in expected_files:
                self.assertIn(expected_file, zip_file.namelist())

    def check_content_in_zip(self, zip_path: Path, expected_file_path: Path, zip_member_name: str):
        """
        Compare a file inside the zip with an expected file.
        """
        with zipfile.ZipFile(zip_path, "r") as zip_file:
            with zip_file.open(zip_member_name) as content_file:
                actual_content = content_file.read().decode("utf-8")
        expected_content = expected_file_path.read_text()
        self.assertEqual(actual_content, expected_content)

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

            zip_path = Path(file_name)

            # Check the content of the package.toml file
            self.check_toml_file(
                zip_path,
                Path("package.toml"),
                [
                    '[learning_package]',
                    f'key = "{self.learning_package.key}"',
                    f'title = "{self.learning_package.title}"',
                    f'description = "{self.learning_package.description}"',
                ]
            )

            # Check the content of the entity TOML files
            for entity in self.all_components:
                current_draft_version = getattr(entity, "draft", None)
                current_published_version = getattr(entity, "published", None)
                expected_content = [
                    '[entity]',
                    f'uuid = "{entity.uuid}"',
                    'can_stand_alone = true',
                    '[entity.draft]',
                    f'version_num = {current_draft_version.version.version_num}',
                    '[entity.published]',
                ]
                if current_published_version:
                    expected_content.append(f'version_num = {current_published_version.version.version_num}')
                else:
                    expected_content.append('# unpublished: no published_version_num')

                for entity_version in entity.versions.all():
                    expected_content.append(f'title = "{entity_version.title}"')
                    expected_content.append(f'uuid = "{entity_version.uuid}"')
                    expected_content.append(f'version_num = {entity_version.version_num}')
                    expected_content.append('[version.container]')
                    expected_content.append('[version.container.unit]')

                self.check_toml_file(
                    zip_path,
                    Path(f"entities/{entity.key}.toml"),
                    expected_content
                )

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
