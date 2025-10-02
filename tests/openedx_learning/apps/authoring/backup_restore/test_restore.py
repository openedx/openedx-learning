"""Tests for the lp_load management command."""
import os
from io import StringIO
from unittest.mock import patch

from django.core.management import call_command

from openedx_learning.apps.authoring.backup_restore.zipper import LearningPackageUnzipper
from openedx_learning.apps.authoring.collections import api as collections_api
from openedx_learning.apps.authoring.components import api as components_api
from openedx_learning.apps.authoring.publishing import api as publishing_api
from openedx_learning.lib.test_utils import TestCase
from test_utils.zip_file_utils import folder_to_inmemory_zip


class RestoreLearningPackageCommandTest(TestCase):
    """Tests for the lp_load management command."""

    def setUp(self):
        super().setUp()
        self.fixtures_folder = os.path.join(os.path.dirname(__file__), "fixtures/library_backup")
        self.zip_file = folder_to_inmemory_zip(self.fixtures_folder)
        self.lp_key = "lib:WGU:LIB_C001"

    @patch("openedx_learning.apps.authoring.backup_restore.management.commands.lp_load.load_dump_zip_file")
    def test_restore_command(self, mock_load_dump_zip_file):
        # Mock load_dump_zip_file to return our in-memory zip file
        mock_load_dump_zip_file.return_value = LearningPackageUnzipper().load(self.zip_file)

        out = StringIO()
        # You can pass any dummy path, since load_dump_zip_file is mocked
        call_command("lp_load", "dummy.zip", stdout=out)

        lp = self.verify_lp()
        self.verify_containers(lp)
        self.verify_components(lp)
        self.verify_collections(lp)

    def verify_lp(self):
        """Verify the learning package was restored correctly."""
        lp = publishing_api.LearningPackage.objects.filter(key=self.lp_key).first()
        assert lp is not None, "Learning package was not restored."
        assert lp.title == "Library test"
        assert lp.description == ""
        return lp

    def verify_containers(self, lp):
        """Verify the containers and their versions were restored correctly."""
        container_qs = publishing_api.get_containers(learning_package_id=lp.id)
        expected_container_keys = ["unit1-b7eafb", "subsection1-48afa3", "section1-8ca126"]

        for container in container_qs:
            assert container.key in expected_container_keys
            draft_version = publishing_api.get_draft_version(container.publishable_entity.id)
            published_version = publishing_api.get_published_version(container.publishable_entity.id)
            if container.key == "unit1-b7eafb":
                assert getattr(container, 'unit', None) is not None
                assert draft_version is not None
                assert draft_version.version_num == 1
                assert published_version is None
            elif container.key == "subsection1-48afa3":
                assert getattr(container, 'subsection', None) is not None
                assert draft_version is not None
                assert draft_version.version_num == 1
                assert published_version is None
            elif container.key == "section1-8ca126":
                assert getattr(container, 'section', None) is not None
                assert draft_version is not None
                assert draft_version.version_num == 1
                assert published_version is None
            else:
                assert False, f"Unexpected container key: {container.key}"

    def verify_components(self, lp):
        """Verify the components and their versions were restored correctly."""
        component_qs = components_api.get_components(lp.id)
        expected_component_keys = [
            "xblock.v1:drag-and-drop-v2:4d1b2fac-8b30-42fb-872d-6b10ab580b27",
            "xblock.v1:html:e32d5479-9492-41f6-9222-550a7346bc37",
            "xblock.v1:openassessment:1ee38208-a585-4455-a27e-4930aa541f53",
            "xblock.v1:problem:256739e8-c2df-4ced-bd10-8156f6cfa90b",
            "xblock.v1:survey:6681da3f-b056-4c6e-a8f9-040967907471",
            "xblock.v1:video:22601ebd-9da8-430b-9778-cfe059a98568",
        ]
        for component in component_qs:
            assert component.key in expected_component_keys
            draft_version = publishing_api.get_draft_version(component.publishable_entity.id)
            published_version = publishing_api.get_published_version(component.publishable_entity.id)
            if component.key == "xblock.v1:drag-and-drop-v2:4d1b2fac-8b30-42fb-872d-6b10ab580b27":
                assert component.component_type.name == "drag-and-drop-v2"
                assert component.component_type.namespace == "xblock.v1"
                assert draft_version is not None
                assert draft_version.version_num == 1
                assert published_version is None

            elif component.key == "xblock.v1:html:e32d5479-9492-41f6-9222-550a7346bc37":
                assert component.component_type.name == "html"
                assert component.component_type.namespace == "xblock.v1"
                assert draft_version is not None
                assert draft_version.version_num == 2
                assert published_version is not None
                assert published_version.version_num == 1

            elif component.key == "xblock.v1:openassessment:1ee38208-a585-4455-a27e-4930aa541f53":
                assert component.component_type.name == "openassessment"
                assert component.component_type.namespace == "xblock.v1"
                assert draft_version is not None
                assert draft_version.version_num == 1
                assert published_version is None
            elif component.key == "xblock.v1:problem:256739e8-c2df-4ced-bd10-8156f6cfa90b":
                assert component.component_type.name == "problem"
                assert component.component_type.namespace == "xblock.v1"
                assert draft_version is not None
                assert draft_version.version_num == 1
                assert published_version is None
            elif component.key == "xblock.v1:survey:6681da3f-b056-4c6e-a8f9-040967907471":
                assert component.component_type.name == "survey"
                assert component.component_type.namespace == "xblock.v1"
                assert draft_version is not None
                assert draft_version.version_num == 1
                assert published_version is None
            elif component.key == "xblock.v1:video:22601ebd-9da8-430b-9778-cfe059a98568":
                assert component.component_type.name == "video"
                assert component.component_type.namespace == "xblock.v1"
                assert draft_version is not None
                assert draft_version.version_num == 1
                assert published_version is None
            else:
                assert False, f"Unexpected component key: {component.key}"

    def verify_collections(self, lp):
        """Verify the collections were restored correctly."""
        collections = collections_api.get_collections(lp.id)
        assert collections.count() == 1
        collection = collections.first()
        assert collection.title == "Collection test1"
        assert collection.key == "collection-test"
        assert collection.description == ""
        expected_entity_keys = [
            "xblock.v1:html:e32d5479-9492-41f6-9222-550a7346bc37",
            "xblock.v1:problem:256739e8-c2df-4ced-bd10-8156f6cfa90b",
        ]
        entity_keys = [entity.key for entity in collection.entities.all()]
        assert set(entity_keys) == set(expected_entity_keys)
