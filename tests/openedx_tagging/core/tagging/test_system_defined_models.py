"""
Test the tagging system-defined taxonomy models
"""
from __future__ import annotations

from datetime import datetime

import ddt  # type: ignore[import]
import pytest
from django.test import TestCase, override_settings

from openedx_learning.core.publishing.models import LearningPackage
from openedx_tagging.core.tagging import api
from openedx_tagging.core.tagging.models import Taxonomy
from openedx_tagging.core.tagging.models.system_defined import ModelSystemDefinedTaxonomy, UserSystemDefinedTaxonomy

from .test_models import TestTagTaxonomyMixin

test_languages = [
    ("en", "English"),
    ("en-uk", "English (United Kingdom)"),
    ("az", "Azerbaijani"),
    ("id", "Indonesian"),
    ("qu", "Quechua"),
    ("zu", "Zulu"),
]


class EmptyTestClass:
    """
    Empty class used for testing
    """


class TestLPTaxonomy(ModelSystemDefinedTaxonomy):
    """
    Model used for testing - points to LearningPackage instances
    """
    @property
    def tag_class_model(self):
        return LearningPackage

    @property
    def tag_class_value_field(self) -> str:
        return "key"

    @property
    def tag_class_key_field(self) -> str:
        return "uuid"

    class Meta:
        proxy = True
        managed = False
        app_label = "oel_tagging"


@ddt.ddt
class TestModelSystemDefinedTaxonomy(TestTagTaxonomyMixin, TestCase):
    """
    Test for Model Model System defined taxonomy
    """

    @staticmethod
    def _create_learning_pkg(**kwargs) -> LearningPackage:
        timestamp = datetime.now()
        return LearningPackage.objects.create(**kwargs, created=timestamp, updated=timestamp)

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        # Create two learning packages and a taxonomy that can tag any object using learning packages as tags:
        cls.learning_pkg_1 = cls._create_learning_pkg(key="p1", title="Learning Package 1")
        cls.learning_pkg_2 = cls._create_learning_pkg(key="p2", title="Learning Package 2")
        cls.lp_taxonomy = TestLPTaxonomy.objects.create(
            taxonomy_class=TestLPTaxonomy,
            name="LearningPackage Taxonomy",
            allow_multiple=True,
        )
        # Also create an "Author" taxonomy that can tag any object using user IDs/usernames:
        cls.author_taxonomy = UserSystemDefinedTaxonomy.objects.create(
            taxonomy_class=UserSystemDefinedTaxonomy,
            name="Authors",
            allow_multiple=True,
        )

    def test_lp_taxonomy_validation(self):
        """
        Test that the validation methods of the Learning Package Taxonomy are working
        """
        # Create a new LearningPackage - we know no Tag instances will exist for it yet.
        valid_lp = self._create_learning_pkg(key="valid-lp", title="New Learning Packacge")
        # The taxonomy can validate tags by value which we've defined as they 'key' of the LearningPackage:
        assert self.lp_taxonomy.validate_value(self.learning_pkg_2.key) is True
        assert self.lp_taxonomy.validate_value(self.learning_pkg_2.key) is True
        assert self.lp_taxonomy.validate_value(valid_lp.key) is True
        assert self.lp_taxonomy.validate_value("foo") is False
        # The taxonomy can also validate tags by external_id, which we've defined as the UUID of the LearningPackage:
        assert self.lp_taxonomy.validate_external_id(self.learning_pkg_2.uuid) is True
        assert self.lp_taxonomy.validate_external_id(self.learning_pkg_2.uuid) is True
        assert self.lp_taxonomy.validate_external_id(valid_lp.uuid) is True
        assert self.lp_taxonomy.validate_external_id("ba11225e-9ec9-4a50-87ea-3155c7c20466") is False

    def test_author_taxonomy_validation(self):
        """
        Test the validation methods of the Author Taxonomy (Author = User)
        """
        assert self.author_taxonomy.validate_value(self.user_1.username) is True
        assert self.author_taxonomy.validate_value(self.user_2.username) is True
        assert self.author_taxonomy.validate_value("not a user") is False
        # And we can validate by ID if we want:
        assert self.author_taxonomy.validate_external_id(str(self.user_1.id)) is True
        assert self.author_taxonomy.validate_external_id(str(self.user_2.id)) is True
        assert self.author_taxonomy.validate_external_id("8742590") is False

    @ddt.data(
        "validate_value", "tag_for_value", "validate_external_id", "tag_for_external_id",
    )
    def test_warns_uncasted(self, method):
        """
        Test that if we use a taxonomy directly without cast(), we get warned.
        """
        base_taxonomy = Taxonomy.objects.get(pk=self.lp_taxonomy.pk)
        with pytest.raises(TypeError) as excinfo:
            # e.g. base_taxonomy.validate_value("foo")
            getattr(base_taxonomy, method)("foo")
        assert "Taxonomy was used incorrectly - without .cast()" in str(excinfo.value)

    def test_simple_tag_object(self):
        """
        Test applying tags to an object.
        """
        object1_id, object2_id = "obj1", "obj2"
        api.tag_object(self.lp_taxonomy, ["p1"], object1_id)
        api.tag_object(self.lp_taxonomy, ["p1", "p2"], object2_id)
        assert [t.value for t in api.get_object_tags(object1_id)] == ["p1"]
        assert [t.value for t in api.get_object_tags(object2_id)] == ["p1", "p2"]

    def test_invalid_tag(self):
        """
        Trying to apply an invalid tag raises TagDoesNotExist
        """
        with pytest.raises(api.TagDoesNotExist):
            api.tag_object(self.lp_taxonomy, ["nonexistent"], "obj1")

    def test_case_insensitive_values(self):
        """
        For now, values are case insensitive. We may change that in the future.
        """
        object1_id, object2_id = "obj1", "obj2"
        api.tag_object(self.lp_taxonomy, ["P1"], object1_id)
        api.tag_object(self.lp_taxonomy, ["p1", "P2"], object2_id)
        assert [t.value for t in api.get_object_tags(object1_id)] == ["p1"]
        assert [t.value for t in api.get_object_tags(object2_id)] == ["p1", "p2"]

    def test_multiple_taxonomies(self):
        """
        Test using several different instances of a taxonomy to tag the same object
        """
        reviewer_taxonomy = UserSystemDefinedTaxonomy.objects.create(
            taxonomy_class=UserSystemDefinedTaxonomy,
            name="Reviewer",
            allow_multiple=True,
        )
        pr_1_id, pr_2_id = "pull_request_1", "pull_request_2"

        # Tag PR 1 as having "Author: user1, user2; Reviewer: user2"
        api.tag_object(self.author_taxonomy, [self.user_1.username, self.user_2.username], pr_1_id)
        api.tag_object(reviewer_taxonomy, [self.user_2.username], pr_1_id)

        # Tag PR 2 as having "Author: user2, reviewer: user1"
        api.tag_object(self.author_taxonomy, [self.user_2.username], pr_2_id)
        api.tag_object(reviewer_taxonomy, [self.user_1.username], pr_2_id)

        # Check the results:
        assert [f"{t.taxonomy.name}:{t.value}" for t in api.get_object_tags(pr_1_id)] == [
            f"Authors:{self.user_1.username}",
            f"Authors:{self.user_2.username}",
            f"Reviewer:{self.user_2.username}",
        ]
        assert [f"{t.taxonomy.name}:{t.value}" for t in api.get_object_tags(pr_2_id)] == [
            f"Authors:{self.user_2.username}",
            f"Reviewer:{self.user_1.username}",
        ]

    def test_tag_object_resync(self):
        """
        If the value changes, we can use the new value to tag objects, and the
        Tag will be updated automatically.
        """
        # Tag two objects with "Author: user_1"
        object1_id, object2_id, other_obj_id = "obj1", "obj2", "other"
        api.tag_object(self.author_taxonomy, [self.user_1.username], object1_id)
        api.tag_object(self.author_taxonomy, [self.user_1.username], object2_id)
        initial_object_tags = api.get_object_tags(object1_id)
        assert [t.value for t in initial_object_tags] == [self.user_1.username]
        assert not list(api.get_object_tags(other_obj_id))
        # Change user_1's username:
        new_username = "new_username"
        self.user_1.username = new_username
        self.user_1.save()
        # Now we update the tags on just one of the objects:
        api.tag_object(self.author_taxonomy, [new_username], object1_id)
        assert [t.value for t in api.get_object_tags(object1_id)] == [new_username]
        # But because this will have updated the shared Tag instance, object2 will also be updated as a side effect.
        # This is good - all the objects throughout the system with this tag now show the new value.
        assert [t.value for t in api.get_object_tags(object2_id)] == [new_username]
        # And just to make sure there are no other random changes to other objects:
        assert not list(api.get_object_tags(other_obj_id))

    def test_tag_object_delete_user(self):
        """
        Using a deleted model instance as a tag will raise TagDoesNotExist
        """
        # Tag an object with "Author: user_1"
        object_id = "obj123"
        api.tag_object(self.author_taxonomy, [self.user_1.username], object_id)
        assert [t.value for t in api.get_object_tags(object_id)] == [self.user_1.username]
        # Test after delete user
        self.user_1.delete()
        with self.assertRaises(api.TagDoesNotExist):
            api.tag_object(self.author_taxonomy, [self.user_1.username], object_id)


@ddt.ddt
@override_settings(LANGUAGES=test_languages)
class TestLanguageTaxonomy(TestTagTaxonomyMixin, TestCase):
    """
    Test for Language taxonomy
    """

    def test_validate_lang_ids(self):
        """
        Whether or not languages are available as tags depends on the django settings
        """
        assert self.language_taxonomy.validate_external_id("en") is True
        assert self.language_taxonomy.tag_for_external_id("en").value == "English"
        assert self.language_taxonomy.tag_for_external_id("en-uk").value == "English (United Kingdom)"
        assert self.language_taxonomy.tag_for_external_id("id").value == "Indonesian"

        assert self.language_taxonomy.validate_external_id("xx") is False
        with pytest.raises(api.TagDoesNotExist):
            self.language_taxonomy.tag_for_external_id("xx")

    @override_settings(LANGUAGES=[("fr", "Français")])
    def test_minimal_languages(self):
        """
        Whether or not languages are available as tags depends on the django settings
        """
        assert self.language_taxonomy.validate_external_id("en") is False
        with pytest.raises(api.TagDoesNotExist):
            self.language_taxonomy.tag_for_external_id("en")
        assert self.language_taxonomy.tag_for_external_id("fr").value == "Français"
