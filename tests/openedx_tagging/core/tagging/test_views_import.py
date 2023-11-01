"""
Tests import REST API views.
"""
from __future__ import annotations

import json

import ddt  # type: ignore[import]
from django.core.files.uploadedfile import SimpleUploadedFile
from rest_framework import status
from rest_framework.test import APITestCase

from openedx_tagging.core.tagging.models import Tag, Taxonomy

TAXONOMY_TEMPLATE_URL = "/tagging/rest_api/v1/import/{filename}"
TAXONOMY_IMPORT_URL = "/tagging/rest_api/v1/import/"


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


class TestImportView(APITestCase):
    """
    Tests the import taxonomy view.
    """

    def test_import(self):
        url = TAXONOMY_IMPORT_URL
        new_tags = [
            {"id": "tag_1", "value": "Tag 1"},
            {"id": "tag_2", "value": "Tag 2"},
            {"id": "tag_3", "value": "Tag 3"},
            {"id": "tag_4", "value": "Tag 4"},
        ]
        json_data = {"tags": new_tags}
        file = SimpleUploadedFile("taxonomy.json", json.dumps(json_data).encode(), content_type="application/json")

        response = self.client.post(
            url,
            {
                "taxonomy_name": "Imported Taxonomy name",
                "taxonomy_description": "Imported Taxonomy description",
                "file": file
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
