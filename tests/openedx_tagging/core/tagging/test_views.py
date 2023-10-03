"""
Tests tagging rest api views
"""
from __future__ import annotations

from urllib.parse import parse_qs, urlparse

import ddt  # type: ignore[import]
# typing support in rules depends on https://github.com/dfunckt/django-rules/pull/177
import rules  # type: ignore[import]
from django.contrib.auth import get_user_model
from rest_framework import status
from rest_framework.test import APITestCase

from openedx_tagging.core.tagging.models import ObjectTag, Tag, Taxonomy
from openedx_tagging.core.tagging.models.system_defined import SystemDefinedTaxonomy
from openedx_tagging.core.tagging.rest_api.paginators import TagsPagination

User = get_user_model()

TAXONOMY_LIST_URL = "/tagging/rest_api/v1/taxonomies/"
TAXONOMY_DETAIL_URL = "/tagging/rest_api/v1/taxonomies/{pk}/"
TAXONOMY_TAGS_URL = "/tagging/rest_api/v1/taxonomies/{pk}/tags/"


OBJECT_TAGS_RETRIEVE_URL = "/tagging/rest_api/v1/object_tags/{object_id}/"
OBJECT_TAGS_UPDATE_URL = "/tagging/rest_api/v1/object_tags/{object_id}/?taxonomy={taxonomy_id}"

LANGUAGE_TAXONOMY_ID = -1


def check_taxonomy(
    data,
    taxonomy_id,
    name,
    description="",
    enabled=True,
    allow_multiple=True,
    allow_free_text=False,
    system_defined=False,
    visible_to_authors=True,
):
    """
    Check taxonomy data
    """
    assert data["id"] == taxonomy_id
    assert data["name"] == name
    assert data["description"] == description
    assert data["enabled"] == enabled
    assert data["allow_multiple"] == allow_multiple
    assert data["allow_free_text"] == allow_free_text
    assert data["system_defined"] == system_defined
    assert data["visible_to_authors"] == visible_to_authors


class TestTaxonomyViewMixin(APITestCase):
    """
    Mixin for taxonomy views. Adds users.
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


@ddt.ddt
class TestTaxonomyViewSet(TestTaxonomyViewMixin):
    """
    Test taxonomy view set
    """

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
    def test_list_taxonomy_queryparams(self, enabled, expected_status: int, expected_count: int | None):
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
    def test_list_taxonomy(self, user_attr: str | None, expected_status: int):
        url = TAXONOMY_LIST_URL

        if user_attr:
            user = getattr(self, user_attr)
            self.client.force_authenticate(user=user)

        response = self.client.get(url)
        assert response.status_code == expected_status

    def test_list_taxonomy_pagination(self) -> None:
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

        next_page = parse_qs(parsed_url.query).get("page", [""])[0]
        assert next_page == "3"

    def test_list_invalid_page(self) -> None:
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
    def test_detail_taxonomy(self, user_attr: str | None, taxonomy_data: dict[str, bool], expected_status: int):
        create_data = {"name": "taxonomy detail test", **taxonomy_data}
        taxonomy = Taxonomy.objects.create(**create_data)
        url = TAXONOMY_DETAIL_URL.format(pk=taxonomy.pk)

        if user_attr:
            user = getattr(self, user_attr)
            self.client.force_authenticate(user=user)

        response = self.client.get(url)
        assert response.status_code == expected_status

        if status.is_success(expected_status):
            check_taxonomy(response.data, taxonomy.pk, **create_data)

    def test_detail_taxonomy_404(self) -> None:
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
    def test_create_taxonomy(self, user_attr: str | None, expected_status: int):
        url = TAXONOMY_LIST_URL

        create_data = {
            "name": "taxonomy_data_2",
            "description": "This is a description",
            "enabled": False,
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
        {"name": "Error taxonomy 3", "enabled": "Invalid value"},
    )
    def test_create_taxonomy_error(self, create_data: dict[str, str]):
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
        assert not response.data["system_defined"]

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
        taxonomy = Taxonomy.objects.create(name="test patch taxonomy", enabled=False)
        taxonomy.save()

        url = TAXONOMY_DETAIL_URL.format(pk=taxonomy.pk)

        if user_attr:
            user = getattr(self, user_attr)
            self.client.force_authenticate(user=user)

        response = self.client.patch(url, {"name": "new name", "enabled": True}, format="json")
        assert response.status_code == expected_status

        # If we were able to update the taxonomy, check if the name changed
        if status.is_success(expected_status):
            response = self.client.get(url)
            check_taxonomy(
                response.data,
                response.data["id"],
                **{
                    "name": "new name",
                    "enabled": True,
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
        assert response.status_code == status.HTTP_404_NOT_FOUND


@ddt.ddt
class TestObjectTagViewSet(APITestCase):
    """
    Testing various cases for the ObjectTagView.
    """

    def setUp(self):

        def _object_permission(_user, object_id: str) -> bool:
            """
            Everyone have object permission on object_id "abc"
            """
            return object_id in ("abc", "limit_tag_count")

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
        self.system_taxonomy = SystemDefinedTaxonomy.objects.create(name="System Taxonomy")
        self.tag1 = Tag.objects.create(taxonomy=self.system_taxonomy, value="Tag 1")
        ObjectTag.objects.create(object_id="abc", taxonomy=self.system_taxonomy, tag=self.tag1)

        # Language system-defined language taxonomy
        self.language_taxonomy = Taxonomy.objects.get(pk=LANGUAGE_TAXONOMY_ID)

        # Closed Taxonomies created by taxonomy admins, each with 20 ObjectTags
        self.enabled_taxonomy = Taxonomy.objects.create(name="Enabled Taxonomy", allow_multiple=False)
        self.disabled_taxonomy = Taxonomy.objects.create(name="Disabled Taxonomy", enabled=False, allow_multiple=False)
        self.multiple_taxonomy = Taxonomy.objects.create(name="Multiple Taxonomy", allow_multiple=True)
        for i in range(20):
            # Valid ObjectTags
            tag_enabled = Tag.objects.create(taxonomy=self.enabled_taxonomy, value=f"Tag {i}")
            tag_disabled = Tag.objects.create(taxonomy=self.disabled_taxonomy, value=f"Tag {i}")
            tag_multiple = Tag.objects.create(taxonomy=self.multiple_taxonomy, value=f"Tag {i}")
            ObjectTag.objects.create(
                object_id="abc", taxonomy=self.enabled_taxonomy, tag=tag_enabled, _value=tag_enabled.value
            )
            ObjectTag.objects.create(
                object_id="abc", taxonomy=self.disabled_taxonomy, tag=tag_disabled, _value=tag_disabled.value
            )
            ObjectTag.objects.create(
                object_id="abc", taxonomy=self.multiple_taxonomy, tag=tag_multiple, _value=tag_multiple.value
            )

        # Free-Text Taxonomies created by taxonomy admins, each linked
        # to 10 ObjectTags
        self.open_taxonomy_enabled = Taxonomy.objects.create(
            name="Enabled Free-Text Taxonomy", allow_free_text=True, allow_multiple=False,
        )
        self.open_taxonomy_disabled = Taxonomy.objects.create(
            name="Disabled Free-Text Taxonomy", allow_free_text=True, enabled=False, allow_multiple=False,
        )
        for i in range(10):
            ObjectTag.objects.create(object_id="abc", taxonomy=self.open_taxonomy_enabled, _value=f"Free Text {i}")
            ObjectTag.objects.create(object_id="abc", taxonomy=self.open_taxonomy_disabled, _value=f"Free Text {i}")

        self.dummy_taxonomies = []
        for i in range(100):
            taxonomy = Taxonomy.objects.create(
                name=f"Dummy Taxonomy {i}",
                allow_free_text=True,
                allow_multiple=True
            )
            ObjectTag.objects.create(
                object_id="limit_tag_count",
                taxonomy=taxonomy,
                _name=taxonomy.name,
                _value="Dummy Tag"
            )
            self.dummy_taxonomies.append(taxonomy)

        # Override the object permission for the test
        rules.set_perm("oel_tagging.change_objecttag_objectid", _object_permission)

    @ddt.data(
        (None, "abc", status.HTTP_403_FORBIDDEN, None),
        ("user", "abc", status.HTTP_200_OK, 81),
        ("staff", "abc", status.HTTP_200_OK, 81),
        (None, "non-existing-id", status.HTTP_403_FORBIDDEN, None),
        ("user", "non-existing-id", status.HTTP_200_OK, 0),
        ("staff", "non-existing-id", status.HTTP_200_OK, 0),
    )
    @ddt.unpack
    def test_retrieve_object_tags(self, user_attr, object_id, expected_status, expected_count):
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
            assert len(response.data) == expected_count

    @ddt.data(
        (None, "abc", status.HTTP_403_FORBIDDEN, None),
        ("user", "abc", status.HTTP_200_OK, 20),
        ("staff", "abc", status.HTTP_200_OK, 20),
    )
    @ddt.unpack
    def test_retrieve_object_tags_taxonomy_queryparam(
        self, user_attr, object_id, expected_status, expected_count
    ):
        """
        Test retrieving object tags for specific taxonomies provided
        """
        url = OBJECT_TAGS_RETRIEVE_URL.format(object_id=object_id)

        if user_attr:
            user = getattr(self, user_attr)
            self.client.force_authenticate(user=user)

        response = self.client.get(url, {"taxonomy": self.enabled_taxonomy.pk})
        assert response.status_code == expected_status
        if status.is_success(expected_status):
            assert len(response.data) == expected_count
            for object_tag in response.data:
                assert object_tag.get("is_deleted") is False
                assert object_tag.get("taxonomy_id") == self.enabled_taxonomy.pk

    @ddt.data(
        (None, "abc", status.HTTP_403_FORBIDDEN),
        ("user", "abc", status.HTTP_400_BAD_REQUEST),
        ("staff", "abc", status.HTTP_400_BAD_REQUEST),
    )
    @ddt.unpack
    def test_retrieve_object_tags_invalid_taxonomy_queryparam(self, user_attr, object_id, expected_status):
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
        (None, "POST", status.HTTP_403_FORBIDDEN),
        (None, "PATCH", status.HTTP_403_FORBIDDEN),
        (None, "DELETE", status.HTTP_403_FORBIDDEN),
        ("user", "POST", status.HTTP_405_METHOD_NOT_ALLOWED),
        ("user", "PATCH", status.HTTP_405_METHOD_NOT_ALLOWED),
        ("user", "DELETE", status.HTTP_405_METHOD_NOT_ALLOWED),
        ("staff", "POST", status.HTTP_405_METHOD_NOT_ALLOWED),
        ("staff", "PATCH", status.HTTP_405_METHOD_NOT_ALLOWED),
        ("staff", "DELETE", status.HTTP_405_METHOD_NOT_ALLOWED),
    )
    @ddt.unpack
    def test_object_tags_remaining_http_methods(
        self,
        user_attr,
        http_method,
        expected_status,
    ):
        """
        Test POST/PATCH/DELETE method for ObjectTagView

        Only staff users should have permissions to perform the actions,
        however the methods are currently not allowed.
        """
        url = OBJECT_TAGS_RETRIEVE_URL.format(object_id="abc")

        if user_attr:
            user = getattr(self, user_attr)
            self.client.force_authenticate(user=user)

        if http_method == "POST":
            response = self.client.post(url, {"test": "payload"}, format="json")
        elif http_method == "PATCH":
            response = self.client.patch(url, {"test": "payload"}, format="json")
        elif http_method == "DELETE":
            response = self.client.delete(url)

        assert response.status_code == expected_status

    @ddt.data(
        # Users and staff can add tags to a taxonomy
        (None, "language_taxonomy", ["Portuguese"], status.HTTP_403_FORBIDDEN),
        ("user", "language_taxonomy", ["Portuguese"], status.HTTP_200_OK),
        ("staff", "language_taxonomy", ["Portuguese"], status.HTTP_200_OK),
        # Users and staff can clear add tags to a taxonomy
        (None, "enabled_taxonomy", ["Tag 1"], status.HTTP_403_FORBIDDEN),
        ("user", "enabled_taxonomy", ["Tag 1"], status.HTTP_200_OK),
        ("staff", "enabled_taxonomy", ["Tag 1"], status.HTTP_200_OK),
        # Only staff can add tag to a disabled taxonomy
        (None, "disabled_taxonomy", ["Tag 1"], status.HTTP_403_FORBIDDEN),
        ("user", "disabled_taxonomy", ["Tag 1"], status.HTTP_403_FORBIDDEN),
        ("staff", "disabled_taxonomy", ["Tag 1"], status.HTTP_200_OK),
        # Users and staff can add a single tag to a allow_multiple=True taxonomy
        (None, "multiple_taxonomy", ["Tag 1"], status.HTTP_403_FORBIDDEN),
        ("user", "multiple_taxonomy", ["Tag 1"], status.HTTP_200_OK),
        ("staff", "multiple_taxonomy", ["Tag 1"], status.HTTP_200_OK),
        # Users and staff can add tags to an open taxonomy
        (None, "open_taxonomy_enabled", ["tag1"], status.HTTP_403_FORBIDDEN),
        ("user", "open_taxonomy_enabled", ["tag1"], status.HTTP_200_OK),
        ("staff", "open_taxonomy_enabled", ["tag1"], status.HTTP_200_OK),
        # Only staff can add tags to a disabled open taxonomy
        (None, "open_taxonomy_disabled", ["tag1"], status.HTTP_403_FORBIDDEN),
        ("user", "open_taxonomy_disabled", ["tag1"], status.HTTP_403_FORBIDDEN),
        ("staff", "open_taxonomy_disabled", ["tag1"], status.HTTP_200_OK),
    )
    @ddt.unpack
    def test_tag_object(self, user_attr, taxonomy_attr, tag_values, expected_status):
        if user_attr:
            user = getattr(self, user_attr)
            self.client.force_authenticate(user=user)

        taxonomy = getattr(self, taxonomy_attr)

        url = OBJECT_TAGS_UPDATE_URL.format(object_id="abc", taxonomy_id=taxonomy.pk)

        response = self.client.put(url, {"tags": tag_values}, format="json")
        assert response.status_code == expected_status
        if status.is_success(expected_status):
            assert len(response.data) == len(tag_values)
            assert set(t["value"] for t in response.data) == set(tag_values)

    @ddt.data(
        # Can't add invalid tags to a closed taxonomy
        (None, "language_taxonomy", ["Invalid"], status.HTTP_403_FORBIDDEN),
        ("user", "language_taxonomy", ["Invalid"], status.HTTP_400_BAD_REQUEST),
        ("staff", "language_taxonomy", ["Invalid"], status.HTTP_400_BAD_REQUEST),
        (None, "enabled_taxonomy", ["invalid"], status.HTTP_403_FORBIDDEN),
        ("user", "enabled_taxonomy", ["invalid"], status.HTTP_400_BAD_REQUEST),
        ("staff", "enabled_taxonomy", ["invalid"], status.HTTP_400_BAD_REQUEST),
        (None, "multiple_taxonomy", ["invalid"], status.HTTP_403_FORBIDDEN),
        ("user", "multiple_taxonomy", ["invalid"], status.HTTP_400_BAD_REQUEST),
        ("staff", "multiple_taxonomy", ["invalid"], status.HTTP_400_BAD_REQUEST),
        # Users can't edit tags from a disabled taxonomy. Staff can't add invalid tags to a closed taxonomy
        (None, "disabled_taxonomy", ["invalid"], status.HTTP_403_FORBIDDEN),
        ("user", "disabled_taxonomy", ["invalid"], status.HTTP_403_FORBIDDEN),
        ("staff", "disabled_taxonomy", ["invalid"], status.HTTP_400_BAD_REQUEST),
    )
    @ddt.unpack
    def test_tag_object_invalid(self, user_attr, taxonomy_attr, tag_values, expected_status):
        if user_attr:
            user = getattr(self, user_attr)
            self.client.force_authenticate(user=user)

        taxonomy = getattr(self, taxonomy_attr)

        url = OBJECT_TAGS_UPDATE_URL.format(object_id="abc", taxonomy_id=taxonomy.pk)

        response = self.client.put(url, {"tags": tag_values}, format="json")
        assert response.status_code == expected_status
        assert not status.is_success(expected_status)  # No success cases here

    @ddt.data(
        # Users and staff can clear tags from a taxonomy
        (None, "enabled_taxonomy", [], status.HTTP_403_FORBIDDEN),
        ("user", "enabled_taxonomy", [], status.HTTP_200_OK),
        ("staff", "enabled_taxonomy", [], status.HTTP_200_OK),
        # Users and staff can clear tags from a allow_multiple=True taxonomy
        (None, "multiple_taxonomy", [], status.HTTP_403_FORBIDDEN),
        ("user", "multiple_taxonomy", [], status.HTTP_200_OK),
        ("staff", "multiple_taxonomy", [], status.HTTP_200_OK),
        # Only staff can clear tags from a disabled taxonomy
        (None, "disabled_taxonomy", [], status.HTTP_403_FORBIDDEN),
        ("user", "disabled_taxonomy", [], status.HTTP_403_FORBIDDEN),
        ("staff", "disabled_taxonomy", [], status.HTTP_200_OK),
        (None, "open_taxonomy_disabled", [], status.HTTP_403_FORBIDDEN),
        ("user", "open_taxonomy_disabled", [], status.HTTP_403_FORBIDDEN),
        ("staff", "open_taxonomy_disabled", [], status.HTTP_200_OK),
    )
    @ddt.unpack
    def test_tag_object_clear(self, user_attr, taxonomy_attr, tag_values, expected_status):
        if user_attr:
            user = getattr(self, user_attr)
            self.client.force_authenticate(user=user)

        taxonomy = getattr(self, taxonomy_attr)

        url = OBJECT_TAGS_UPDATE_URL.format(object_id="abc", taxonomy_id=taxonomy.pk)

        response = self.client.put(url, {"tags": tag_values}, format="json")
        assert response.status_code == expected_status
        if status.is_success(expected_status):
            assert len(response.data) == len(tag_values)
            assert set(t["value"] for t in response.data) == set(tag_values)

    @ddt.data(
        # Users and staff can add multiple tags to a allow_multiple=True taxonomy
        (None, "multiple_taxonomy", ["Tag 1", "Tag 2"], status.HTTP_403_FORBIDDEN),
        ("user", "multiple_taxonomy", ["Tag 1", "Tag 2"], status.HTTP_200_OK),
        ("staff", "multiple_taxonomy", ["Tag 1", "Tag 2"], status.HTTP_200_OK),
        (None, "open_taxonomy_enabled", ["tag1", "tag2"], status.HTTP_403_FORBIDDEN),
        ("user", "open_taxonomy_enabled", ["tag1", "tag2"], status.HTTP_400_BAD_REQUEST),
        ("staff", "open_taxonomy_enabled", ["tag1", "tag2"], status.HTTP_400_BAD_REQUEST),
        # Users and staff can't add multple tags to a allow_multiple=False taxonomy
        (None, "enabled_taxonomy", ["Tag 1", "Tag 2"], status.HTTP_403_FORBIDDEN),
        ("user", "enabled_taxonomy", ["Tag 1", "Tag 2"], status.HTTP_400_BAD_REQUEST),
        ("staff", "enabled_taxonomy", ["Tag 1", "Tag 2"], status.HTTP_400_BAD_REQUEST),
        (None, "language_taxonomy", ["Portuguese", "English"], status.HTTP_403_FORBIDDEN),
        ("user", "language_taxonomy", ["Portuguese", "English"], status.HTTP_400_BAD_REQUEST),
        ("staff", "language_taxonomy", ["Portuguese", "English"], status.HTTP_400_BAD_REQUEST),
        # Users can't edit tags from a disabled taxonomy. Staff can't add multiple tags to
        # a taxonomy with allow_multiple=False
        (None, "disabled_taxonomy", ["Tag 1", "Tag 2"], status.HTTP_403_FORBIDDEN),
        ("user", "disabled_taxonomy", ["Tag 1", "Tag 2"], status.HTTP_403_FORBIDDEN),
        ("staff", "disabled_taxonomy", ["Tag 1", "Tag 2"], status.HTTP_400_BAD_REQUEST),
    )
    @ddt.unpack
    def test_tag_object_multiple(self, user_attr, taxonomy_attr, tag_values, expected_status):
        if user_attr:
            user = getattr(self, user_attr)
            self.client.force_authenticate(user=user)

        taxonomy = getattr(self, taxonomy_attr)

        url = OBJECT_TAGS_UPDATE_URL.format(object_id="abc", taxonomy_id=taxonomy.pk)

        response = self.client.put(url, {"tags": tag_values}, format="json")
        assert response.status_code == expected_status
        if status.is_success(expected_status):
            assert len(response.data) == len(tag_values)
            assert set(t["value"] for t in response.data) == set(tag_values)

    @ddt.data(
        (None, status.HTTP_403_FORBIDDEN),
        ("user", status.HTTP_403_FORBIDDEN),
        ("staff", status.HTTP_403_FORBIDDEN),
    )
    @ddt.unpack
    def test_tag_object_without_permission(self, user_attr, expected_status):
        if user_attr:
            user = getattr(self, user_attr)
            self.client.force_authenticate(user=user)

        url = OBJECT_TAGS_UPDATE_URL.format(object_id="not abc", taxonomy_id=self.enabled_taxonomy.pk)

        response = self.client.put(url, {"tags": ["Tag 1"]}, format="json")
        assert response.status_code == expected_status
        assert not status.is_success(expected_status)  # No success cases here

    def test_tag_object_count_limit(self):
        """
        Checks if the limit of 100 tags per object is enforced
        """
        object_id = "limit_tag_count"
        url = OBJECT_TAGS_UPDATE_URL.format(object_id=object_id, taxonomy_id=self.enabled_taxonomy.pk)
        self.client.force_authenticate(user=self.staff)
        response = self.client.put(url, {"tags": ["Tag 1"]}, format="json")
        # Can't add another tag because the object already has 100 tags
        assert response.status_code == status.HTTP_400_BAD_REQUEST

        # The user can edit the tags that are already on the object
        for taxonomy in self.dummy_taxonomies:
            url = OBJECT_TAGS_UPDATE_URL.format(object_id=object_id, taxonomy_id=taxonomy.pk)
            response = self.client.put(url, {"tags": ["New Tag"]}, format="json")
            assert response.status_code == status.HTTP_200_OK

        # Editing tags adding another one will fail
        for taxonomy in self.dummy_taxonomies:
            url = OBJECT_TAGS_UPDATE_URL.format(object_id=object_id, taxonomy_id=taxonomy.pk)
            response = self.client.put(url, {"tags": ["New Tag 1", "New Tag 2"]}, format="json")
            assert response.status_code == status.HTTP_400_BAD_REQUEST


class TestTaxonomyTagsView(TestTaxonomyViewMixin):
    """
    Tests the list tags of taxonomy view
    """

    fixtures = ["tests/openedx_tagging/core/fixtures/tagging.yaml"]

    def setUp(self):
        self.small_taxonomy = Taxonomy.objects.get(name="Life on Earth")
        self.large_taxonomy = Taxonomy(name="Large Taxonomy")
        self.large_taxonomy.save()

        self.small_taxonomy_url = TAXONOMY_TAGS_URL.format(pk=self.small_taxonomy.pk)
        self.large_taxonomy_url = TAXONOMY_TAGS_URL.format(pk=self.large_taxonomy.pk)

        self.root_tags_count = 51
        self.children_tags_count = [12, 12]  # 51 * 12 * 12 = 7344 tags

        self.page_size = TagsPagination().page_size

        return super().setUp()

    def _create_tag(self, depth: int, parent: Tag | None = None):
        """
        Creates tags and children in a recursive way.
        """
        tag_count = self.large_taxonomy.tag_set.count()
        tag = Tag(
            taxonomy=self.large_taxonomy,
            parent=parent,
            value=f"Tag {tag_count}",
        )
        tag.save()
        if depth < len(self.children_tags_count):
            for _ in range(self.children_tags_count[depth]):
                self._create_tag(depth + 1, parent=tag)
        return tag

    def _build_large_taxonomy(self):
        # Pupulates the large taxonomy with tags
        for _ in range(self.root_tags_count):
            self._create_tag(0)

    def test_invalid_taxonomy(self):
        url = TAXONOMY_TAGS_URL.format(pk=212121)

        self.client.force_authenticate(user=self.staff)
        response = self.client.get(url)

        assert response.status_code == status.HTTP_404_NOT_FOUND

    def test_not_authorized_user(self):
        # Not authenticated user
        response = self.client.get(self.small_taxonomy_url)
        assert response.status_code == status.HTTP_403_FORBIDDEN

        self.small_taxonomy.enabled = False
        self.small_taxonomy.save()
        self.client.force_authenticate(user=self.user)
        response = self.client.get(self.small_taxonomy_url)

        assert response.status_code == status.HTTP_403_FORBIDDEN

    def test_small_taxonomy(self):
        self.client.force_authenticate(user=self.staff)
        response = self.client.get(self.small_taxonomy_url)
        assert response.status_code == status.HTTP_200_OK

        data = response.data
        results = data.get("results", [])

        # Count of root tags
        root_count = self.small_taxonomy.tag_set.filter(parent=None).count()
        assert len(results) == root_count

        # Checking tag fields
        root_tag = self.small_taxonomy.tag_set.get(id=results[0].get("id"))
        root_children_count = root_tag.children.count()
        assert results[0].get("value") == root_tag.value
        assert results[0].get("taxonomy_id") == self.small_taxonomy.id
        assert results[0].get("children_count") == root_children_count
        assert len(results[0].get("sub_tags")) == root_children_count

        # Checking pagination values
        assert data.get("next") is None
        assert data.get("previous") is None
        assert data.get("count") == root_count
        assert data.get("num_pages") == 1
        assert data.get("current_page") == 1

    def test_small_search(self):
        search_term = 'eU'
        url = f"{self.small_taxonomy_url}?search_term={search_term}"
        self.client.force_authenticate(user=self.staff)
        response = self.client.get(url)
        assert response.status_code == status.HTTP_200_OK

        data = response.data
        results = data.get("results", [])

        assert len(results) == 3

        # Checking pagination values
        assert data.get("next") is None
        assert data.get("previous") is None
        assert data.get("count") == 3
        assert data.get("num_pages") == 1
        assert data.get("current_page") == 1

    def test_large_taxonomy(self):
        self._build_large_taxonomy()
        self.client.force_authenticate(user=self.staff)
        response = self.client.get(self.large_taxonomy_url)
        assert response.status_code == status.HTTP_200_OK

        data = response.data
        results = data.get("results", [])

        # Count of paginated root tags
        assert len(results) == self.page_size

        # Checking tag fields
        root_tag = self.large_taxonomy.tag_set.get(id=results[0].get("id"))
        assert results[0].get("value") == root_tag.value
        assert results[0].get("taxonomy_id") == self.large_taxonomy.id
        assert results[0].get("parent_id") == root_tag.parent_id
        assert results[0].get("children_count") == root_tag.children.count()
        assert results[0].get("sub_tags_link") == (
            "http://testserver/tagging/"
            f"rest_api/v1/taxonomies/{self.large_taxonomy.id}"
            f"/tags/?parent_tag_id={root_tag.id}"
        )

        # Checking pagination values
        assert data.get("next") == (
            "http://testserver/tagging/"
            f"rest_api/v1/taxonomies/{self.large_taxonomy.id}/tags/?page=2"
        )
        assert data.get("previous") is None
        assert data.get("count") == self.root_tags_count
        assert data.get("num_pages") == 6
        assert data.get("current_page") == 1

    def test_next_page_large_taxonomy(self):
        self._build_large_taxonomy()
        self.client.force_authenticate(user=self.staff)

        # Gets the root tags to obtain the next links
        response = self.client.get(self.large_taxonomy_url)

        # Gets the next root tags
        response = self.client.get(response.data.get("next"))
        assert response.status_code == status.HTTP_200_OK

        data = response.data

        # Checking pagination values
        assert data.get("next") == (
            "http://testserver/tagging/"
            f"rest_api/v1/taxonomies/{self.large_taxonomy.id}/tags/?page=3"
        )
        assert data.get("previous") == (
            "http://testserver/tagging/"
            f"rest_api/v1/taxonomies/{self.large_taxonomy.id}/tags/"
        )
        assert data.get("count") == self.root_tags_count
        assert data.get("num_pages") == 6
        assert data.get("current_page") == 2

    def test_large_search(self):
        self._build_large_taxonomy()
        search_term = '1'
        url = f"{self.large_taxonomy_url}?search_term={search_term}"
        self.client.force_authenticate(user=self.staff)
        response = self.client.get(url)
        assert response.status_code == status.HTTP_200_OK

        data = response.data
        results = data.get("results", [])

        # Count of paginated root tags
        assert len(results) == self.page_size

        # Checking pagination values
        assert data.get("next") == (
            "http://testserver/tagging/"
            f"rest_api/v1/taxonomies/{self.large_taxonomy.id}"
            f"/tags/?page=2&search_term={search_term}"
        )
        assert data.get("previous") is None
        assert data.get("count") == 51
        assert data.get("num_pages") == 6
        assert data.get("current_page") == 1

    def test_next_large_search(self):
        self._build_large_taxonomy()
        search_term = '1'
        url = f"{self.large_taxonomy_url}?search_term={search_term}"

        # Get first page of the search
        self.client.force_authenticate(user=self.staff)
        response = self.client.get(url)

        # Get next page
        response = self.client.get(response.data.get("next"))

        data = response.data
        results = data.get("results", [])

        # Count of paginated root tags
        assert len(results) == self.page_size

        # Checking pagination values
        assert data.get("next") == (
            "http://testserver/tagging/"
            f"rest_api/v1/taxonomies/{self.large_taxonomy.id}"
            f"/tags/?page=3&search_term={search_term}"
        )
        assert data.get("previous") == (
            "http://testserver/tagging/"
            f"rest_api/v1/taxonomies/{self.large_taxonomy.id}"
            f"/tags/?search_term={search_term}"
        )
        assert data.get("count") == 51
        assert data.get("num_pages") == 6
        assert data.get("current_page") == 2

    def test_get_children(self):
        self._build_large_taxonomy()
        self.client.force_authenticate(user=self.staff)

        # Get root tags to obtain the children link of a tag.
        response = self.client.get(self.large_taxonomy_url)
        results = response.data.get("results", [])

        # Get children tags
        response = self.client.get(results[0].get("sub_tags_link"))
        assert response.status_code == status.HTTP_200_OK

        data = response.data
        results = data.get("results", [])

        # Count of paginated children tags
        assert len(results) == self.page_size

        # Checking tag fields
        tag = self.large_taxonomy.tag_set.get(id=results[0].get("id"))
        assert results[0].get("value") == tag.value
        assert results[0].get("taxonomy_id") == self.large_taxonomy.id
        assert results[0].get("parent_id") == tag.parent_id
        assert results[0].get("children_count") == tag.children.count()
        assert results[0].get("sub_tags_link") == (
            "http://testserver/tagging/"
            f"rest_api/v1/taxonomies/{self.large_taxonomy.id}"
            f"/tags/?parent_tag_id={tag.id}"
        )

        # Checking pagination values
        assert data.get("next") == (
            "http://testserver/tagging/"
            f"rest_api/v1/taxonomies/{self.large_taxonomy.id}"
            f"/tags/?page=2&parent_tag_id={tag.parent_id}"
        )
        assert data.get("previous") is None
        assert data.get("count") == self.children_tags_count[0]
        assert data.get("num_pages") == 2
        assert data.get("current_page") == 1

    def test_get_leaves(self):
        # Get tags depth=2
        self.client.force_authenticate(user=self.staff)
        parent_tag = Tag.objects.get(value="Animalia")

        # Build url to get tags depth=2
        url = f"{self.small_taxonomy_url}?parent_tag_id={parent_tag.id}"
        response = self.client.get(url)
        results = response.data.get("results", [])

        # Checking tag fields
        tag = self.small_taxonomy.tag_set.get(id=results[0].get("id"))
        assert results[0].get("value") == tag.value
        assert results[0].get("taxonomy_id") == self.small_taxonomy.id
        assert results[0].get("parent_id") == tag.parent_id
        assert results[0].get("children_count") == tag.children.count()
        assert results[0].get("sub_tags_link") is None

    def test_next_children(self):
        self._build_large_taxonomy()
        self.client.force_authenticate(user=self.staff)

        # Get roots to obtain children link of a tag
        response = self.client.get(self.large_taxonomy_url)
        results = response.data.get("results", [])

        # Get children to obtain next link
        response = self.client.get(results[0].get("sub_tags_link"))

        # Get next children
        response = self.client.get(response.data.get("next"))
        assert response.status_code == status.HTTP_200_OK

        data = response.data
        results = data.get("results", [])
        tag = self.large_taxonomy.tag_set.get(id=results[0].get("id"))

        # Checking pagination values
        assert data.get("next") is None
        assert data.get("previous") == (
            "http://testserver/tagging/"
            f"rest_api/v1/taxonomies/{self.large_taxonomy.id}/tags/?parent_tag_id={tag.parent_id}"
        )
        assert data.get("count") == self.children_tags_count[0]
        assert data.get("num_pages") == 2
        assert data.get("current_page") == 2
