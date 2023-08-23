"""
Tests tagging rest api views
"""
from urllib.parse import urlparse, parse_qs

import ddt
from django.contrib.auth import get_user_model
from rest_framework import status
from rest_framework.test import APITestCase

from openedx_tagging.core.tagging.models import Taxonomy, ObjectTag, Tag
from openedx_tagging.core.tagging.models.system_defined import SystemDefinedTaxonomy

User = get_user_model()

TAXONOMY_LIST_URL = "/tagging/rest_api/v1/taxonomies/"
TAXONOMY_DETAIL_URL = "/tagging/rest_api/v1/taxonomies/{pk}/"


OBJECT_TAGS_RETRIEVE_URL = '/tagging/rest_api/v1/object_tags/{object_id}/'


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


@ddt.ddt
class TestObjectTagViewSet(APITestCase):
    """
    Testing various cases for the ObjectTagView.
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

        # System-defined language taxonomy with valid ObjectTag
        self.system_taxonomy = SystemDefinedTaxonomy.objects.create(
            name="System Taxonomy"
        )
        self.tag1 = Tag.objects.create(
            taxonomy=self.system_taxonomy, value="Tag 1"
        )
        ObjectTag.objects.create(
            object_id="abc",
            taxonomy=self.system_taxonomy,
            tag=self.tag1
        )

        # Closed Taxonomies created by taxonomy admins, each with 20 ObjectTags
        self.enabled_taxonomy = Taxonomy.objects.create(name="Enabled Taxonomy")
        for i in range(20):
            # Valid ObjectTags
            tag = Tag.objects.create(
                taxonomy=self.enabled_taxonomy, value=f"Tag {i}"
            )
            ObjectTag.objects.create(
                object_id="abc", taxonomy=self.enabled_taxonomy,
                tag=tag, _value=tag.value
            )

        # Taxonomy with invalid ObjectTag
        self.taxonomy_with_invalid_object_tag = Taxonomy.objects.create()
        self.to_be_deleted_tag = Tag.objects.create(
            taxonomy=self.enabled_taxonomy, value="Deleted Tag"
        )
        ObjectTag.objects.create(
            object_id="abc", taxonomy=self.taxonomy_with_invalid_object_tag,
            tag=self.to_be_deleted_tag, _value=self.to_be_deleted_tag.value
        )
        self.to_be_deleted_tag.delete()  # Delete tag so ObjectTag is invalid

        # Free-Text Taxonomies created by taxonomy admins, each linked
        # to 200 ObjectTags
        self.open_taxonomy_enabled = Taxonomy.objects.create(
            name="Enabled Free-Text Taxonomy", allow_free_text=True
        )
        self.open_taxonomy_disabled = Taxonomy.objects.create(
            name="Disabled Free-Text Taxonomy", enabled=False, allow_free_text=True
        )
        for i in range(200):
            ObjectTag.objects.create(
                object_id="abc", taxonomy=self.open_taxonomy_enabled, _value=f"Free Text {i}"
            )
            ObjectTag.objects.create(
                object_id="abc", taxonomy=self.open_taxonomy_disabled, _value=f"Free Text {i}"
            )

    @ddt.data(
        (None, "abc", status.HTTP_403_FORBIDDEN, None, None),
        ("user", "abc", status.HTTP_200_OK, 422, 10),
        ("staff", "abc", status.HTTP_200_OK, 422, 10),
        (None, "non-existing-id", status.HTTP_403_FORBIDDEN, None, None),
        ("user", "non-existing-id", status.HTTP_200_OK, 0, 0),
        ("staff", "non-existing-id", status.HTTP_200_OK, 0, 0),
    )
    @ddt.unpack
    def test_retrieve_object_tags(
        self, user_attr, object_id, expected_status, expected_count, expected_results

    ):
        """
        Test retrieving object tags
        """
        url = OBJECT_TAGS_RETRIEVE_URL.format(object_id=object_id)

        if user_attr:
            user = getattr(self, user_attr)
            self.client.force_authenticate(user=user)

        response = self.client.get(url)
        assert response.status_code == expected_status

        if status.is_success(expected_status):
            assert response.data.get("count") == expected_count
            assert response.data.get("results") is not None
            assert len(response.data.get("results")) == expected_results

    @ddt.data(
        (None, "abc", status.HTTP_403_FORBIDDEN, None, None, None, None),
        ("user", "abc", status.HTTP_200_OK, 20, 10, 1, 1),
        ("staff", "abc", status.HTTP_200_OK, 20, 10, 1, 1),
    )
    @ddt.unpack
    def test_retrieve_object_tags_taxonomy_queryparam(
        self, user_attr, object_id, expected_status,
        expected_count, expected_results,
        expected_invalid_count, expected_invalid_results
    ):
        """
        Test retrieving object tags for specific taxonomies provided
        """
        url = OBJECT_TAGS_RETRIEVE_URL.format(object_id=object_id)

        if user_attr:
            user = getattr(self, user_attr)
            self.client.force_authenticate(user=user)

        # Check valid object tags
        response = self.client.get(url, {"taxonomy": self.enabled_taxonomy.pk})
        assert response.status_code == expected_status
        if status.is_success(expected_status):
            assert response.data.get("count") == expected_count
            assert response.data.get("results") is not None
            assert len(response.data.get("results")) == expected_results
            object_tags = response.data.get("results")
            for object_tag in object_tags:
                assert object_tag.get("is_valid") is True
                assert object_tag.get("taxonomy_id") == self.enabled_taxonomy.pk

        # Check invalid object tags
        response = self.client.get(
            url, {"taxonomy": self.taxonomy_with_invalid_object_tag.pk}
        )
        assert response.status_code == expected_status
        if status.is_success(expected_status):
            assert response.data.get("count") == expected_invalid_count
            assert response.data.get("results") is not None
            assert len(response.data.get("results")) == expected_invalid_results
            object_tags = response.data.get("results")
            for object_tag in object_tags:
                assert object_tag.get("is_valid") is False
                assert object_tag.get("taxonomy_id") == \
                    self.taxonomy_with_invalid_object_tag.pk

    @ddt.data(
        (None, "abc", status.HTTP_403_FORBIDDEN),
        ("user", "abc", status.HTTP_400_BAD_REQUEST),
        ("staff", "abc", status.HTTP_400_BAD_REQUEST),
    )
    @ddt.unpack
    def test_retrieve_object_tags_invalid_taxonomy_queryparam(
        self, user_attr, object_id, expected_status
    ):
        """
        Test retrieving object tags for invalid taxonomy
        """
        url = OBJECT_TAGS_RETRIEVE_URL.format(object_id=object_id)

        if user_attr:
            user = getattr(self, user_attr)
            self.client.force_authenticate(user=user)

        # Invalid Taxonomy
        response = self.client.get(url, {"taxonomy": 123123})
        assert response.status_code == expected_status

    @ddt.data(
        # Page 1, default page size 10, total count 200, returns 10 results
        (None, 1, None, status.HTTP_403_FORBIDDEN, None, None),
        ("user", 1, None, status.HTTP_200_OK, 200, 10),
        ("staff", 1, None, status.HTTP_200_OK, 200, 10),
        # Page 2, default page size 10, total count 200, returns 10 results
        (None, 2, None, status.HTTP_403_FORBIDDEN, None, None),
        ("user", 2, None, status.HTTP_200_OK, 200, 10),
        ("staff", 2, None, status.HTTP_200_OK, 200, 10),
        # Page 21, default page size 10, total count 200, no more results
        (None, 21, None, status.HTTP_403_FORBIDDEN, None, None),
        ("user", 21, None, status.HTTP_404_NOT_FOUND, None, None),
        ("staff", 21, None, status.HTTP_404_NOT_FOUND, None, None),
        # Page 3, page size 2, total count 200, returns 2 results
        (None, 3, 2, status.HTTP_403_FORBIDDEN, 200, 2),
        ("user", 3, 2, status.HTTP_200_OK, 200, 2),
        ("staff", 3, 2, status.HTTP_200_OK, 200, 2),
    )
    @ddt.unpack
    def test_retrieve_object_tags_pagination(
        self, user_attr, page, page_size, expected_status, expected_count, expected_results
    ):
        """
        Test pagination for retrieve object tags
        """
        url = OBJECT_TAGS_RETRIEVE_URL.format(object_id="abc")

        if user_attr:
            user = getattr(self, user_attr)
            self.client.force_authenticate(user=user)

        query_params = {
            "taxonomy": self.open_taxonomy_enabled.pk,
            "page": page
        }
        if page_size:
            query_params["page_size"] = page_size

        response = self.client.get(url, query_params)
        assert response.status_code == expected_status
        if status.is_success(expected_status):
            assert response.data.get("count") == expected_count
            assert response.data.get("results") is not None
            assert len(response.data.get("results")) == expected_results
            object_tags = response.data.get("results")
            for object_tag in object_tags:
                assert object_tag.get("taxonomy_id") == self.open_taxonomy_enabled.pk

    @ddt.data(
        (None, "POST", status.HTTP_403_FORBIDDEN),
        (None, "PUT", status.HTTP_403_FORBIDDEN),
        (None, "PATCH", status.HTTP_403_FORBIDDEN),
        (None, "DELETE", status.HTTP_403_FORBIDDEN),
        ("user", "POST", status.HTTP_403_FORBIDDEN),
        ("user", "PUT", status.HTTP_403_FORBIDDEN),
        ("user", "PATCH", status.HTTP_403_FORBIDDEN),
        ("user", "DELETE", status.HTTP_403_FORBIDDEN),
        ("staff", "POST", status.HTTP_405_METHOD_NOT_ALLOWED),
        ("staff", "PUT", status.HTTP_405_METHOD_NOT_ALLOWED),
        ("staff", "PATCH", status.HTTP_405_METHOD_NOT_ALLOWED),
        ("staff", "DELETE", status.HTTP_405_METHOD_NOT_ALLOWED),
    )
    @ddt.unpack
    def test_object_tags_remaining_http_methods(
        self, user_attr, http_method, expected_status,

    ):
        """
        Test POST/PUT/PATCH/DELETE method for ObjectTagView

        Only staff users should have permissions to perform the actions,
        however the methods are currently not allowed.
        """
        url = OBJECT_TAGS_RETRIEVE_URL.format(object_id="abc")

        if user_attr:
            user = getattr(self, user_attr)
            self.client.force_authenticate(user=user)

        if http_method == "POST":
            response = self.client.post(
                url, {"test": "payload"}, format="json"
            )
        elif http_method == "PUT":
            response = self.client.put(
                url, {"test": "payload"}, format="json"
            )
        elif http_method == "PATCH":
            response = self.client.patch(
                url, {"test": "payload"}, format="json"
            )
        elif http_method == "DELETE":
            response = self.client.delete(url)

        assert response.status_code == expected_status
