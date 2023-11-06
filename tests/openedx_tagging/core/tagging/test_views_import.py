"""
Tests import REST API views.
"""
from __future__ import annotations

import json

import ddt  # type: ignore[import]
from django.contrib.auth import get_user_model
from django.core.files.uploadedfile import SimpleUploadedFile
from rest_framework import status
from rest_framework.test import APITestCase

from openedx_tagging.core.tagging.models import Tag, Taxonomy

TAXONOMY_TEMPLATE_URL = "/tagging/rest_api/v1/import/{filename}"
TAXONOMY_IMPORT_URL = "/tagging/rest_api/v1/import/"

User = get_user_model()

@ddt.ddt
class TestTemplateView(APITestCase):
    """
    Tests the taxonomy template downloads.
    """
    @ddt.data(
        ("template.csv", "text/csv"),
        ("template.json", "application/json"),
    )
    @ddt.unpack
    def test_download(self, filename, content_type):
        url = TAXONOMY_TEMPLATE_URL.format(filename=filename)
        response = self.client.get(url)
        assert response.status_code == status.HTTP_200_OK
        assert response.headers['Content-Type'] == content_type
        assert response.headers['Content-Disposition'] == f'attachment; filename="{filename}"'
        assert int(response.headers['Content-Length']) > 0

    def test_download_not_found(self):
        url = TAXONOMY_TEMPLATE_URL.format(filename="template.txt")
        response = self.client.get(url)
        assert response.status_code == status.HTTP_404_NOT_FOUND

    def test_download_method_not_allowed(self):
        url = TAXONOMY_TEMPLATE_URL.format(filename="template.txt")
        response = self.client.post(url)
        assert response.status_code == status.HTTP_405_METHOD_NOT_ALLOWED


@ddt.ddt
class TestImportView(APITestCase):
    """
    Tests the import taxonomy view.
    """
    def setUp(self):
        super().setUp()

        self.user = User.objects.create(
            username="user",
            email="user@example.com",
        )

        self.staff = User.objects.create(
            username="staff",
            email="staff@example.com",
            is_staff=True,
        )


    def _get_file(self, tags: list, file_format: str) -> SimpleUploadedFile:
        """
        Returns a file for the given format.
        """
        if file_format == "csv":
            csv_data = "id,value"
            for tag in tags:
                csv_data += f"\n{tag['id']},{tag['value']}"
            return SimpleUploadedFile("taxonomy.csv", csv_data.encode(), content_type="text/csv")
        else:  # json
            json_data = {"tags": tags}
            return SimpleUploadedFile("taxonomy.json", json.dumps(json_data).encode(), content_type="application/json")

    @ddt.data(
        "csv",
        "json",
    )
    def test_import(self, file_format: str) -> None:
        """
        Tests importing a valid taxonomy file.
        """
        url = TAXONOMY_IMPORT_URL
        new_tags = [
            {"id": "tag_1", "value": "Tag 1"},
            {"id": "tag_2", "value": "Tag 2"},
            {"id": "tag_3", "value": "Tag 3"},
            {"id": "tag_4", "value": "Tag 4"},
        ]
        file = self._get_file(new_tags, file_format)

        self.client.force_authenticate(user=self.staff)
        response = self.client.post(
            url,
            {
                "taxonomy_name": "Imported Taxonomy name",
                "taxonomy_description": "Imported Taxonomy description",
                "file": file,
            },
            format="multipart"
        )
        assert response.status_code == status.HTTP_200_OK

        # Check if the taxonomy was created
        taxonomy = Taxonomy.objects.get(name="Imported Taxonomy name")
        assert taxonomy.description == "Imported Taxonomy description"

        # Check if the tags were created
        tags = list(Tag.objects.filter(taxonomy=taxonomy))
        assert len(tags) == len(new_tags)
        for i, tag in enumerate(tags):
            assert tag.value == new_tags[i]["value"]

    def test_import_no_file(self) -> None:
        """
        Tests importing a taxonomy without a file.
        """
        url = TAXONOMY_IMPORT_URL
        self.client.force_authenticate(user=self.staff)
        response = self.client.post(
            url,
            {
                "taxonomy_name": "Imported Taxonomy name",
                "taxonomy_description": "Imported Taxonomy description",
            },
            format="multipart"
        )
        assert response.status_code == status.HTTP_400_BAD_REQUEST
        assert response.data["file"][0] == "No file was submitted."

    @ddt.data(
        "csv",
        "json",
    )
    def test_import_no_name(self, file_format) -> None:
        """
        Tests importing a taxonomy without specifing a name.
        """
        url = TAXONOMY_IMPORT_URL
        file = SimpleUploadedFile(f"taxonomy.{file_format}", b"invalid file content")
        self.client.force_authenticate(user=self.staff)
        response = self.client.post(
            url,
            {
                "taxonomy_description": "Imported Taxonomy description",
                "file": file,
            },
            format="multipart"
        )
        assert response.status_code == status.HTTP_400_BAD_REQUEST
        assert response.data["taxonomy_name"][0] == "This field is required."

    def test_import_invalid_format(self) -> None:
        """
        Tests importing a taxonomy with an invalid file format.
        """
        url = TAXONOMY_IMPORT_URL
        file = SimpleUploadedFile("taxonomy.invalid", b"invalid file content")
        self.client.force_authenticate(user=self.staff)
        response = self.client.post(
            url,
            {
                "taxonomy_name": "Imported Taxonomy name",
                "taxonomy_description": "Imported Taxonomy description",
                "file": file,
            },
            format="multipart"
        )
        assert response.status_code == status.HTTP_400_BAD_REQUEST
        assert response.data["file"][0] == "File type not supported: invalid"

    @ddt.data(
        "csv",
        "json",
    )
    def test_import_invalid_content(self, file_format) -> None:
        """
        Tests importing a taxonomy with an invalid file content.
        """
        url = TAXONOMY_IMPORT_URL
        file = SimpleUploadedFile(f"taxonomy.{file_format}", b"invalid file content")
        self.client.force_authenticate(user=self.staff)
        response = self.client.post(
            url,
            {
                "taxonomy_name": "Imported Taxonomy name",
                "taxonomy_description": "Imported Taxonomy description",
                "file": file,
            },
            format="multipart"
        )
        assert response.status_code == status.HTTP_400_BAD_REQUEST
        assert response.content == b"Error importing taxonomy"

    def test_import_no_perm(self) -> None:
        """
        Tests importing a taxonomy using a user without permission.
        """
        url = TAXONOMY_IMPORT_URL
        new_tags = [
            {"id": "tag_1", "value": "Tag 1"},
            {"id": "tag_2", "value": "Tag 2"},
            {"id": "tag_3", "value": "Tag 3"},
            {"id": "tag_4", "value": "Tag 4"},
        ]
        file = self._get_file(new_tags, "json")

        self.client.force_authenticate(user=self.user)
        response = self.client.post(
            url,
            {
                "taxonomy_name": "Imported Taxonomy name",
                "taxonomy_description": "Imported Taxonomy description",
                "file": file,
            },
            format="multipart"
        )
        assert response.status_code == status.HTTP_403_FORBIDDEN
