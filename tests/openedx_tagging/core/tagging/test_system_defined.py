""" Test the System-defined taxonomies and object tags """

import ddt

from django.contrib.auth import get_user_model
from django.db import models
from django.test.testcases import TestCase, override_settings

from openedx_tagging.core.tagging.system_defined_taxonomies.object_tags import (
    ModelObjectTag,
    UserObjectTag,
    LanguageObjectTag,
)
from openedx_tagging.core.tagging.models import Tag, Taxonomy

from .test_models import TestTagTaxonomyMixin

test_languages = [
    ('en', 'English'),
    ('az', 'Azerbaijani'),
    ('id', 'Indonesian'),
    ('qu', 'Quechua'),
    ('zu', 'Zulu'),
]


class EmptyTestClass:
    """
    Empty class used for testing
    """


class EmptyTestModel(models.Model):
    """
    Model used for testing
    """
    mi_id = models.AutoField(primary_key=True)

    class Meta:
        managed = False
        app_label = 'oel_tagging'


class EmptyModelObjectTag(ModelObjectTag):
    """
    Model ObjectTag used for testing
    """

    system_defined_taxonomy_id = 3

    class Meta:
        proxy = True
        managed = False
        app_label = 'oel_tagging'


class NotDjangoModelObjectTag(ModelObjectTag):
    """
    Model ObjectTag used for testing
    """

    system_defined_taxonomy_id = 3

    class Meta:
        proxy = True
        managed = False
        app_label = 'oel_tagging'

    tag_class_model = EmptyTestClass


class NotIdModelObjectTag(ModelObjectTag):
    """
    Model ObjectTag used for testing
    """

    system_defined_taxonomy_id = 3

    class Meta:
        proxy = True
        managed = False
        app_label = 'oel_tagging'

    tag_class_model = EmptyTestModel


class TestUserObjectTag(UserObjectTag):
    """
    User ObjectTag used for testing
    """

    system_defined_taxonomy_id = 3

    class Meta:
        proxy = True
        managed = False
        app_label = 'oel_tagging'


@ddt.ddt
class TestSystemDefinedObjectTags(TestTagTaxonomyMixin, TestCase):
    """
    Test for generic system defined object tags
    """
    def test_system_defined_is_valid(self):
        # Valid
        assert TestUserObjectTag()._check_system_taxonomy(taxonomy=self.user_system_taxonomy)

        # Null taxonomy
        assert not UserObjectTag()._check_system_taxonomy()

        # Not system defined taxonomy
        assert not UserObjectTag()._check_system_taxonomy(taxonomy=self.taxonomy)

        # Not connected with the taxonomy
        assert not UserObjectTag()._check_system_taxonomy(taxonomy=self.user_system_taxonomy)

    @ddt.data(
        (EmptyModelObjectTag, False),  # Without associated model
        (NotDjangoModelObjectTag, False),  # Associated class is not a Django model
        (NotIdModelObjectTag, False),  # Associated model has not 'id' field
        (ModelObjectTag, False), # Testing parent class validations
        (TestUserObjectTag, True),  #Valid
    )
    @ddt.unpack
    def test_model_object_is_valid(self, object_tag, assert_value):
        args = {
            'taxonomy': self.user_system_taxonomy,
            'object_id': 'id',
            'object_type': 'object',
            'value': 'value',
        }
        result = object_tag(**args).is_valid(check_object=False, check_tag=False, check_taxonomy=True)
        self.assertEqual(result, assert_value)

    @ddt.data(
        (None, True),  # Valid
        ('user_id', False),  # Invalid user id
        ('10000', False),  # User don't exits
        (None, False),  # Testing parent class validations
    )
    @ddt.unpack
    def test_user_object_is_valid(self, value, assert_value):
        if assert_value:
            user = get_user_model()(
                username='username',
                email='email'
            )
            user.save()
            value = user.id

        object_tag = TestUserObjectTag(
            taxonomy=self.user_system_taxonomy,
            object_id='id',
            object_type='object',
            value=value,
        )

        result = object_tag.is_valid(
            check_taxonomy=True,
            check_object=True,
            check_tag=True,
        )

        self.assertEqual(result, assert_value)


@override_settings(LANGUAGES=test_languages)
class TestLanguageObjectClass(TestCase):
    """
    Test for Language object class
    """

    fixtures = [
        "tests/openedx_tagging/core/fixtures/system_defined.yaml",
        "openedx_tagging/core/tagging/fixtures/language_taxonomy.yaml"
    ]

    def setUp(self):
        super().setUp()
        self.taxonomy = Taxonomy.objects.get(name="System Languages")
        self.expected_langs_ids = sorted([item[0] for item in test_languages])
        self.expected_langs_values = sorted([item[1] for item in test_languages])
        self.english_tag = Tag.objects.get(value="English")
        self.spanish_tag = Tag.objects.get(value="Spanish")

    def test_get_available_languages(self):
        langs = LanguageObjectTag._get_available_languages()
        self.assertEqual(sorted(langs), self.expected_langs_ids)

    def test_is_valid(self):
        valid_object_tag = LanguageObjectTag(
            taxonomy=self.taxonomy,
            object_id='id 1',
            object_type='object',
            tag=self.english_tag,
        )

        invalid_onbject_tag_1 = LanguageObjectTag(
            taxonomy=self.taxonomy,
            object_id='id 2',
            object_type='object',
            tag=self.spanish_tag,
        )

        invalid_onbject_tag_2 = LanguageObjectTag(
            taxonomy=self.taxonomy,
            object_id='id 2',
            object_type='object',
        )

        # Tag is not in available languages
        assert not invalid_onbject_tag_1.is_valid(
            check_taxonomy=True,
            check_object=True,
            check_tag=True,
        )

        # Testing parent class validations
        assert not invalid_onbject_tag_2.is_valid(
            check_taxonomy=True,
            check_object=True,
            check_tag=True,
        )

        # Valid
        assert valid_object_tag.is_valid(
            check_taxonomy=True,
            check_object=True,
            check_tag=True,
        )

    def test_get_tags_query_set(self):
        tags = LanguageObjectTag.get_tags_query_set(self.taxonomy)
        for tag in tags:
            self.assertIn(tag.value, self.expected_langs_values)
