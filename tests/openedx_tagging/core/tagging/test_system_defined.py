""" Test the System-defined taxonomies and object tags """

from django.contrib.auth import get_user_model
from django.db import models
from django.test.testcases import TestCase, override_settings

from openedx_tagging.core.tagging.system_defined_taxonomies.object_tags import (
    OpenSystemObjectTag,
    ClosedSystemObjectTag,
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


class EmptyObjectTag(ModelObjectTag):
    """
    Model Object tag used for testing
    """
    class Meta:
        proxy = True
        managed = False
        app_label = 'oel_tagging'

    tag_class_model = EmptyTestClass


class EmptyModelObjectTag(ModelObjectTag):
    """
    Model Object tag used for testing
    """
    class Meta:
        proxy = True
        managed = False
        app_label = 'oel_tagging'

    tag_class_model = EmptyTestModel


class TestSystemDefinedObjectTags(TestTagTaxonomyMixin, TestCase):
    """
    Test for generic system defined object tags
    """
    def test_open_valid_for(self):
        #Valid
        assert OpenSystemObjectTag.valid_for(taxonomy=self.user_system_taxonomy)

        # Not open system taxonomy
        assert not OpenSystemObjectTag.valid_for(taxonomy=self.system_taxonomy)

        # Not system taxonomy
        assert not OpenSystemObjectTag.valid_for(taxonomy=self.taxonomy)

    def test_closed_valid_for(self):
        #Valid
        assert ClosedSystemObjectTag.valid_for(taxonomy=self.system_taxonomy, tag=self.archaea)

        # Not closed system taxonomy
        assert not ClosedSystemObjectTag.valid_for(taxonomy=self.user_system_taxonomy, tag=self.archaea)

        # Not system taxonomy
        assert not ClosedSystemObjectTag.valid_for(taxonomy=self.taxonomy, tag=self.archaea)

    def test_model_valid_for(self):
        # Without associated model
        assert not ModelObjectTag.valid_for(self.user_system_taxonomy)

        # Associated class is not a Django model
        assert not EmptyObjectTag.valid_for(self.user_system_taxonomy)

        # Associated model has not 'id' field
        assert not EmptyModelObjectTag.valid_for(self.user_system_taxonomy)

        #Valid
        assert UserObjectTag.valid_for(self.user_system_taxonomy)

    def test_model_is_valid(self):
        user = get_user_model()(
            username='username',
            email='email'
        )
        user.save()
        valid_object_tag = UserObjectTag(
            taxonomy=self.user_system_taxonomy,
            object_id='id 1',
            object_type='object',
            value=user.id,
        )
        invalid_object_tag_1 = UserObjectTag(
            taxonomy=self.user_system_taxonomy,
            object_id='id 2',
            object_type='object',
            value='user_id',
        )
        invalid_object_tag_2 = UserObjectTag(
            taxonomy=self.user_system_taxonomy,
            object_id='id 2',
            object_type='object',
            value='10000',
        )
        invalid_object_tag_3 = UserObjectTag(
            taxonomy=self.user_system_taxonomy,
            object_id='id 3',
            object_type='object',
        )

        # Invalid user id
        assert not invalid_object_tag_1.is_valid(
            check_taxonomy=True,
            check_object=True,
            check_tag=True,
        )

        # User don't exits
        assert not invalid_object_tag_2.is_valid(
            check_taxonomy=True,
            check_object=True,
            check_tag=True,
        )

        # Testing parent class validations
        assert not invalid_object_tag_3.is_valid(
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


@override_settings(LANGUAGES=test_languages)
class TestLanguageObjectClass(TestCase):
    """
    Test for Language object class
    """

    fixtures = [
        "tests/openedx_tagging/core/fixtures/system_defined.yaml",
        "openedx_tagging/core/tagging/system_defined_taxonomies/fixtures/language_taxonomy.yaml"
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
