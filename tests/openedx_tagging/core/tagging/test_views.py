"""
Tests tagging rest api views
"""

import ddt
from django.contrib.auth import get_user_model
from rest_framework import status
from rest_framework.test import APITestCase

from openedx_tagging.core.tagging.models import Taxonomy

User = get_user_model()

TAXONOMY_LIST_URL = '/tagging/rest_api/v1/taxonomies/'
TAXONOMY_DETAIL_URL = '/tagging/rest_api/v1/taxonomies/{pk}/'

def check_taxonomy(
    data,
    id,
    name,
    description=None,
    enabled=True,
    required=False,
    allow_multiple=False,
    allow_free_text=False,
    system_defined=False,
    visible_to_authors=True,
):
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
        (None, status.HTTP_200_OK, 3),
        (1, status.HTTP_200_OK, 2),
        (0, status.HTTP_200_OK, 1),
        (True, status.HTTP_200_OK, 2),
        (False, status.HTTP_200_OK, 1),
        ("True", status.HTTP_200_OK, 2),
        ("False", status.HTTP_200_OK, 1),
        ("1", status.HTTP_200_OK, 2),
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
        if status.is_success(expected_status):
            assert len(response.data) == expected_count

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

    @ddt.data(
        (None, {"enabled": True}, status.HTTP_403_FORBIDDEN),
        (None, {"enabled": False}, status.HTTP_403_FORBIDDEN),
        (
            "user",
            {"enabled": True},
            status.HTTP_200_OK,
        ),
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
        assert response.data["system_defined"] == False

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
        (False, False, status.HTTP_200_OK),
        (False, True, status.HTTP_200_OK),
        (True, False, status.HTTP_403_FORBIDDEN),
        (True, True, status.HTTP_403_FORBIDDEN),
    )
    @ddt.unpack
    def test_update_taxonomy_system_defined(
        self, create_value, update_value, expected_status
    ):
        '''
        Test that we can't update system_defined field
        '''
        taxonomy = Taxonomy.objects.create(
            name="test system taxonomy", system_defined=create_value
        )
        taxonomy.save()
        url = TAXONOMY_DETAIL_URL.format(pk=taxonomy.pk)

        self.client.force_authenticate(user=self.staff)
        response = self.client.put(
            url, {"name": "new name", "system_defined": update_value}, format="json"
        )
        assert response.status_code == expected_status

        # Verify that system_defined has not changed
        response = self.client.get(url)
        assert response.data["system_defined"] == create_value

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
        taxonomy = Taxonomy.objects.create(
            name="test patch taxonomy", enabled=False, required=True
        )
        taxonomy.save()

        url = TAXONOMY_DETAIL_URL.format(pk=taxonomy.pk)

        if user_attr:
            user = getattr(self, user_attr)
            self.client.force_authenticate(user=user)

        response = self.client.patch(
            url, {"name": "new name", "required": False}, format="json"
        )
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
        (False, False, status.HTTP_200_OK),
        (False, True, status.HTTP_200_OK),
        (True, False, status.HTTP_403_FORBIDDEN),
        (True, True, status.HTTP_403_FORBIDDEN),
    )
    @ddt.unpack
    def test_patch_taxonomy_system_defined(
        self, create_value, update_value, expected_status
    ):
        '''
        Test that we can't patch system_defined field
        '''
        taxonomy = Taxonomy.objects.create(
            name="test system taxonomy", system_defined=create_value
        )
        taxonomy.save()
        url = TAXONOMY_DETAIL_URL.format(pk=taxonomy.pk)

        self.client.force_authenticate(user=self.staff)
        response = self.client.patch(
            url, {"system_defined": update_value}, format="json"
        )
        assert response.status_code == expected_status

        # Verify that system_defined has not changed
        response = self.client.get(url)
        assert response.data["system_defined"] == create_value

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
