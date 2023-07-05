""" Test the System-defined taxonomies """

import ddt

from django.contrib.auth import get_user_model
from django.test.testcases import TestCase, override_settings

from openedx_tagging.core.tagging.models import Taxonomy, ObjectTag, Tag
from openedx_tagging.core.tagging.system_defined_taxonomies.system_defined import (
    LanguageTaxonomy,
    AuthorTaxonomy
)

fixtures_path = "openedx_tagging/core/tagging/system_defined_taxonomies/fixtures"
test_languages = [
    ('en', 'English'),
    ('az', 'Azerbaijani'),
    ('id', 'Indonesian'),
    ('qu', 'Quechua'),
    ('zu', 'Zulu'),
]

class TestSystemDefinedTaxonomyMixin:
    """
    Mixin used on system-defined taxonomy tests
    """

    fixtures = [f"{fixtures_path}/taxonomies.yaml"]

    def setUp(self):
        super().setUp()
        temp_taxonomy = Taxonomy.objects.get(pk=1)
        self.language_taxonomy = LanguageTaxonomy()
        self.language_taxonomy.__dict__ = temp_taxonomy.__dict__
        temp_taxonomy = Taxonomy.objects.get(pk=2)
        self.author_taxonomy = AuthorTaxonomy()
        self.author_taxonomy.__dict__ = temp_taxonomy.__dict__


@ddt.ddt
@override_settings(LANGUAGES=test_languages)
class TestLanguageTaxonomy(TestSystemDefinedTaxonomyMixin, TestCase):
    """
    Test the Language Taxonomy
    """

    def setUp(self):
        super().setUp()
        self.expected_langs_ids = sorted([item[0] for item in test_languages])
        self.expected_langs_values = sorted([item[1] for item in test_languages])
        self.english_tag = Tag.objects.get(value="English")
        self.spanish_tag = Tag.objects.get(value="Spanish")

    fixtures = (
        TestSystemDefinedTaxonomyMixin.fixtures
        + [f"{fixtures_path}/language_taxonomy.yaml"]
    )

    def test_fixture(self):
        self.assertEqual(self.language_taxonomy.name, 'Language')
        for lang_code, lang_value in test_languages:
            lang = self.language_taxonomy.tag_set.get(external_id=lang_code)
            self.assertEqual(lang.value, lang_value)

    def test_get_available_languages(self):
        langs = self.language_taxonomy.get_available_languages()
        self.assertEqual(sorted(langs), self.expected_langs_ids)

    def test_get_tags(self):
        tags = self.language_taxonomy.get_tags()
        for tag in tags:
            self.assertIn(tag.value, self.expected_langs_values)
            self.assertEqual(tag.annotated_field, 0)  # Checking depth

    def test_validate_object_tag(self):
        object_id = 'object_id'
        invalid_object_tag_1 = ObjectTag(
            taxonomy=self.language_taxonomy,
            object_id=object_id,
            tag=self.spanish_tag,
        )
        invalid_object_tag_2 = ObjectTag(
            object_id=object_id,
        )
        valid_object_tag = ObjectTag(
            taxonomy=self.language_taxonomy,
            object_id=object_id,
            tag=self.english_tag,
        )

        # Invalid. Language is not available
        self.language_taxonomy.validate_object_tag(
            object_tag=invalid_object_tag_1,
            check_taxonomy=False,
            check_tag=False,
            check_object=False,
        )

        # Invalid. Testing normal object validations
        self.language_taxonomy.validate_object_tag(
            object_tag=invalid_object_tag_2,
            check_taxonomy=True,
            check_tag=False,
            check_object=False,
        )

        # Valid
        self.language_taxonomy.validate_object_tag(
            object_tag=valid_object_tag,
            check_taxonomy=False,
            check_tag=False,
            check_object=False,
        )


class TestAuthorTaxonomy(TestSystemDefinedTaxonomyMixin, TestCase):
    """
    Test the Author Taxonomy
    """

    def setUp(self):
        super().setUp()
        self.user = get_user_model()(
            username='test',
            email='test@test.com',
        )
        self.user.save()

    def test_user_exists(self):
        self.assertFalse(self.author_taxonomy._user_exists(100))
        self.assertTrue(self.author_taxonomy._user_exists(self.user.id))

    def test_validate_object_tag(self):
        object_id = 'object_id'
        invalid_object_tag_1 = ObjectTag(
            taxonomy=self.author_taxonomy,
            object_id=object_id,
            _value="author:100"
        )
        invalid_object_tag_2 = ObjectTag(
            object_id=object_id,
            _value="author:100"
        )
        valid_object_tag = ObjectTag(
            taxonomy=self.author_taxonomy,
            object_id=object_id,
            _value=f"author:{self.user.id}"
        )

        # Invalid. User doesn't exist
        self.assertFalse(self.author_taxonomy.validate_object_tag(
            object_tag=invalid_object_tag_1,
            check_taxonomy=False,
            check_tag=False,
            check_object=False,
        ))

        # Invalid. Testing normal object validations
        self.assertFalse(self.author_taxonomy.validate_object_tag(
            object_tag=invalid_object_tag_2,
            check_taxonomy=True,
            check_tag=False,
            check_object=False,
        ))

        # Valid
        self.assertTrue(self.author_taxonomy.validate_object_tag(
            object_tag=valid_object_tag,
            check_taxonomy=False,
            check_tag=False,
            check_object=False,
        ))
