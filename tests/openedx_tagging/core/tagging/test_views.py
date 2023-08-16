"""
Tests tagging rest api views
"""
from urllib.parse import urlparse, parse_qs

import ddt
from django.contrib.auth import get_user_model
from rest_framework import status
from rest_framework.test import APITestCase

from openedx_tagging.core.tagging.models import Taxonomy
from openedx_tagging.core.tagging.models.system_defined import SystemDefinedTaxonomy

User = get_user_model()

TAXONOMY_LIST_URL = "/tagging/rest_api/v1/taxonomies/"
TAXONOMY_DETAIL_URL = "/tagging/rest_api/v1/taxonomies/{pk}/"


def check_taxonomy(
    data,
    id,  # pylint: disable=redefined-builtin
    name,
    description=None,
    enabled=True,
    required=False,
    allow_multiple=False,
    allow_free_text=False,
    system_defined=False,
    visible_to_authors=True,
):
    """Helper method to check expected fields of a Taxonomy"""
    assert data["id"] == id
    assert data["name"] == name
    assert data["description"] == description
    assert data["enabled"] == enabled
    assert data["required"] == required
    assert data["allow_multiple"] == allow_multiple
    assert data["allow_free_text"] == allow_free_text
    assert data["system_defined"] == system_defined
    assert data["visible_to_authors"] == visible_to_authors


@ddt.ddt
class TestTaxonomyViewSet(APITestCase):
    """Test of the Taxonomy REST API"""
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

    @ddt.data(
        (None, status.HTTP_200_OK, 4),
        (1, status.HTTP_200_OK, 3),
        (0, status.HTTP_200_OK, 1),
        (True, status.HTTP_200_OK, 3),
        (False, status.HTTP_200_OK, 1),
        ("True", status.HTTP_200_OK, 3),
        ("False", status.HTTP_200_OK, 1),
        ("1", status.HTTP_200_OK, 3),
        ("0", status.HTTP_200_OK, 1),
        (2, status.HTTP_400_BAD_REQUEST, None),
        ("invalid", status.HTTP_400_BAD_REQUEST, None),
    )
    @ddt.unpack
    def test_list_taxonomy_queryparams(self, enabled, expected_status, expected_count):
        Taxonomy.objects.create(name="Taxonomy enabled 1", enabled=True).save()
        Taxonomy.objects.create(name="Taxonomy enabled 2", enabled=True).save()
        Taxonomy.objects.create(name="Taxonomy disabled", enabled=False).save()

        url = TAXONOMY_LIST_URL

        self.client.force_authenticate(user=self.staff)
        if enabled is not None:
            response = self.client.get(url, {"enabled": enabled})
        else:
            response = self.client.get(url)
        assert response.status_code == expected_status

        # If we were able to list the taxonomies, check that we got the expected number back
        # We take into account the Language Taxonomy that is created by the system in a migration
        if status.is_success(expected_status):
            assert len(response.data["results"]) == expected_count

    @ddt.data(
        (None, status.HTTP_403_FORBIDDEN),
        ("user", status.HTTP_200_OK),
        ("staff", status.HTTP_200_OK),
    )
    @ddt.unpack
    def test_list_taxonomy(self, user_attr, expected_status):
        url = TAXONOMY_LIST_URL

        if user_attr:
            user = getattr(self, user_attr)
            self.client.force_authenticate(user=user)

        response = self.client.get(url)
        assert response.status_code == expected_status

    def test_list_taxonomy_pagination(self):
        url = TAXONOMY_LIST_URL
        Taxonomy.objects.create(name="T1", enabled=True).save()
        Taxonomy.objects.create(name="T2", enabled=True).save()
        Taxonomy.objects.create(name="T3", enabled=False).save()
        Taxonomy.objects.create(name="T4", enabled=False).save()
        Taxonomy.objects.create(name="T5", enabled=False).save()

        self.client.force_authenticate(user=self.staff)

        query_params = {"page_size": 2, "page": 2}
        response = self.client.get(url, query_params, format="json")

        assert response.status_code == status.HTTP_200_OK

        self.assertEqual(set(t["name"] for t in response.data["results"]), set(("T2", "T3")))
        parsed_url = urlparse(response.data["next"])

        next_page = parse_qs(parsed_url.query).get("page", [None])[0]
        assert next_page == "3"

    def test_list_invalid_page(self):
        url = TAXONOMY_LIST_URL

        self.client.force_authenticate(user=self.user)

        query_params = {"page": 123123}

        response = self.client.get(url, query_params, format="json")

        assert response.status_code == status.HTTP_404_NOT_FOUND

    @ddt.data(
        (None, {"enabled": True}, status.HTTP_403_FORBIDDEN),
        (None, {"enabled": False}, status.HTTP_403_FORBIDDEN),
        ("user", {"enabled": True}, status.HTTP_200_OK),
        ("user", {"enabled": False}, status.HTTP_404_NOT_FOUND),
        ("staff", {"enabled": True}, status.HTTP_200_OK),
        ("staff", {"enabled": False}, status.HTTP_200_OK),
    )
    @ddt.unpack
    def test_detail_taxonomy(self, user_attr, taxonomy_data, expected_status):
        create_data = {**{"name": "taxonomy detail test"}, **taxonomy_data}
        taxonomy = Taxonomy.objects.create(**create_data)
        url = TAXONOMY_DETAIL_URL.format(pk=taxonomy.pk)

        if user_attr:
            user = getattr(self, user_attr)
            self.client.force_authenticate(user=user)

        response = self.client.get(url)
        assert response.status_code == expected_status

        if status.is_success(expected_status):
            check_taxonomy(response.data, taxonomy.pk, **create_data)

    def test_detail_taxonomy_404(self):
        url = TAXONOMY_DETAIL_URL.format(pk=123123)

        self.client.force_authenticate(user=self.staff)
        response = self.client.get(url)
        assert response.status_code == status.HTTP_404_NOT_FOUND

    @ddt.data(
        (None, status.HTTP_403_FORBIDDEN),
        ("user", status.HTTP_403_FORBIDDEN),
        ("staff", status.HTTP_201_CREATED),
    )
    @ddt.unpack
    def test_create_taxonomy(self, user_attr, expected_status):
        url = TAXONOMY_LIST_URL

        create_data = {
            "name": "taxonomy_data_2",
            "description": "This is a description",
            "enabled": False,
            "required": True,
            "allow_multiple": True,
        }

        if user_attr:
            user = getattr(self, user_attr)
            self.client.force_authenticate(user=user)

        response = self.client.post(url, create_data, format="json")
        assert response.status_code == expected_status

        # If we were able to create the taxonomy, check if it was created
        if status.is_success(expected_status):
            check_taxonomy(response.data, response.data["id"], **create_data)
            url = TAXONOMY_DETAIL_URL.format(pk=response.data["id"])

            response = self.client.get(url)
            check_taxonomy(response.data, response.data["id"], **create_data)

    @ddt.data(
        {},
        {"name": "Error taxonomy 2", "required": "Invalid value"},
        {"name": "Error taxonomy 3", "enabled": "Invalid value"},
    )
    def test_create_taxonomy_error(self, create_data):
        url = TAXONOMY_LIST_URL

        self.client.force_authenticate(user=self.staff)
        response = self.client.post(url, create_data, format="json")
        assert response.status_code == status.HTTP_400_BAD_REQUEST

    @ddt.data({"name": "System defined taxonomy", "system_defined": True})
    def test_create_taxonomy_system_defined(self, create_data):
        """
        Cannont create a taxonomy with system_defined=true
        """
        url = TAXONOMY_LIST_URL

        self.client.force_authenticate(user=self.staff)
        response = self.client.post(url, create_data, format="json")
        assert response.status_code == status.HTTP_201_CREATED
        assert response.data["system_defined"] is False

    @ddt.data(
        (None, status.HTTP_403_FORBIDDEN),
        ("user", status.HTTP_403_FORBIDDEN),
        ("staff", status.HTTP_200_OK),
    )
    @ddt.unpack
    def test_update_taxonomy(self, user_attr, expected_status):
        taxonomy = Taxonomy.objects.create(
            name="test update taxonomy",
            description="taxonomy description",
            enabled=True,
            required=False,
        )
        taxonomy.save()

        url = TAXONOMY_DETAIL_URL.format(pk=taxonomy.pk)

        if user_attr:
            user = getattr(self, user_attr)
            self.client.force_authenticate(user=user)

        response = self.client.put(url, {"name": "new name"}, format="json")
        assert response.status_code == expected_status

        # If we were able to update the taxonomy, check if the name changed
        if status.is_success(expected_status):
            response = self.client.get(url)
            check_taxonomy(
                response.data,
                response.data["id"],
                **{
                    "name": "new name",
                    "description": "taxonomy description",
                    "enabled": True,
                    "required": False,
                },
            )

    @ddt.data(
        (False, status.HTTP_200_OK),
        (True, status.HTTP_403_FORBIDDEN),
    )
    @ddt.unpack
    def test_update_taxonomy_system_defined(self, system_defined, expected_status):
        """
        Test that we can't update system_defined field
        """
        taxonomy = Taxonomy.objects.create(name="test system taxonomy")
        if system_defined:
            taxonomy.taxonomy_class = SystemDefinedTaxonomy
        taxonomy.save()
        url = TAXONOMY_DETAIL_URL.format(pk=taxonomy.pk)

        self.client.force_authenticate(user=self.staff)
        response = self.client.put(url, {"name": "new name"}, format="json")
        assert response.status_code == expected_status

    def test_update_taxonomy_404(self):
        url = TAXONOMY_DETAIL_URL.format(pk=123123)

        self.client.force_authenticate(user=self.staff)
        response = self.client.put(url, {"name": "new name"}, format="json")
        assert response.status_code == status.HTTP_404_NOT_FOUND

    @ddt.data(
        (None, status.HTTP_403_FORBIDDEN),
        ("user", status.HTTP_403_FORBIDDEN),
        ("staff", status.HTTP_200_OK),
    )
    @ddt.unpack
    def test_patch_taxonomy(self, user_attr, expected_status):
        taxonomy = Taxonomy.objects.create(name="test patch taxonomy", enabled=False, required=True)
        taxonomy.save()

        url = TAXONOMY_DETAIL_URL.format(pk=taxonomy.pk)

        if user_attr:
            user = getattr(self, user_attr)
            self.client.force_authenticate(user=user)

        response = self.client.patch(url, {"name": "new name", "required": False}, format="json")
        assert response.status_code == expected_status

        # If we were able to update the taxonomy, check if the name changed
        if status.is_success(expected_status):
            response = self.client.get(url)
            check_taxonomy(
                response.data,
                response.data["id"],
                **{
                    "name": "new name",
                    "enabled": False,
                    "required": False,
                },
            )

    @ddt.data(
        (False, status.HTTP_200_OK),
        (True, status.HTTP_403_FORBIDDEN),
    )
    @ddt.unpack
    def test_patch_taxonomy_system_defined(self, system_defined, expected_status):
        """
        Test that we can't patch system_defined field
        """
        taxonomy = Taxonomy.objects.create(name="test system taxonomy")
        if system_defined:
            taxonomy.taxonomy_class = SystemDefinedTaxonomy
        taxonomy.save()
        url = TAXONOMY_DETAIL_URL.format(pk=taxonomy.pk)

        self.client.force_authenticate(user=self.staff)
        response = self.client.patch(url, {"name": "New name"}, format="json")
        assert response.status_code == expected_status

    def test_patch_taxonomy_404(self):
        url = TAXONOMY_DETAIL_URL.format(pk=123123)

        self.client.force_authenticate(user=self.staff)
        response = self.client.patch(url, {"name": "new name"}, format="json")
        assert response.status_code == status.HTTP_404_NOT_FOUND

    @ddt.data(
        (None, status.HTTP_403_FORBIDDEN),
        ("user", status.HTTP_403_FORBIDDEN),
        ("staff", status.HTTP_204_NO_CONTENT),
    )
    @ddt.unpack
    def test_delete_taxonomy(self, user_attr, expected_status):
        taxonomy = Taxonomy.objects.create(name="test delete taxonomy")
        taxonomy.save()

        url = TAXONOMY_DETAIL_URL.format(pk=taxonomy.pk)

        if user_attr:
            user = getattr(self, user_attr)
            self.client.force_authenticate(user=user)

        response = self.client.delete(url)
        assert response.status_code == expected_status

        # If we were able to delete the taxonomy, check that it's really gone
        if status.is_success(expected_status):
            response = self.client.get(url)
            assert response.status_code == status.HTTP_404_NOT_FOUND

    def test_delete_taxonomy_404(self):
        url = TAXONOMY_DETAIL_URL.format(pk=123123)

        self.client.force_authenticate(user=self.staff)
        response = self.client.delete(url)
        assert response.status_code, status.HTTP_404_NOT_FOUND
