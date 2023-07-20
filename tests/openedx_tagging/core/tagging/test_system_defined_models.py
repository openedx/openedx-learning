""" Test the tagging system-defined taxonomy models """
import ddt

from django.test.testcases import TestCase, override_settings
from django.contrib.auth import get_user_model

from openedx_tagging.core.tagging.models import (
    ObjectTag,
    Tag,
)
from openedx_tagging.core.tagging.models.system_defined import (
    ModelObjectTag,
    ModelSystemDefinedTaxonomy,
    SystemDefinedTaxonomy,
    UserSystemDefinedTaxonomy,
)

from .test_models import TestTagTaxonomyMixin


test_languages = [
    ("en", "English"),
    ("az", "Azerbaijani"),
    ("id", "Indonesian"),
    ("qu", "Quechua"),
    ("zu", "Zulu"),
]


class EmptyTestClass:
    """
    Empty class used for testing
    """


class InvalidModelTaxonomy(ModelSystemDefinedTaxonomy):
    """
    Model used for testing
    """

    @property
    def object_tag_class(self):
        return EmptyTestClass

    class Meta:
        proxy = True
        managed = False
        app_label = "oel_tagging"


class TestModelTag(ModelObjectTag):
    """
    Model used for testing
    """

    @property
    def tag_class_model(self):
        return get_user_model()

    class Meta:
        proxy = True
        managed = False
        app_label = "oel_tagging"


class TestModelTaxonomy(ModelSystemDefinedTaxonomy):
    """
    Model used for testing
    """

    @property
    def object_tag_class(self):
        return TestModelTag

    class Meta:
        proxy = True
        managed = False
        app_label = "oel_tagging"

@ddt.ddt
class TestSystemDefinedTaxonomy(TestTagTaxonomyMixin, TestCase):
    """
    Test for System defined Taxonomy
    """

    @ddt.data(
        ("system_taxonomy", "system_taxonomy", True),  # Valid
        ("taxonomy", "taxonomy", False),  # Not a system defined
        ("system_taxonomy", "taxonomy", False),  # Testing parent validations
    )
    @ddt.unpack
    def test_validations(self, taxonomy, second_taxonomy, expected):
        taxonomy = getattr(self, taxonomy)
        taxonomy.taxonomy_class = SystemDefinedTaxonomy
        taxonomy = taxonomy.cast()

        second_taxonomy = getattr(self, second_taxonomy)

        assert (
            taxonomy.validate_object_tag(
                object_tag=ObjectTag(object_id="id", taxonomy=second_taxonomy),
                check_taxonomy=True,
                check_tag=False,
                check_object=False,
            )
            == expected
        )


@ddt.ddt
class TestModelSystemDefinedTaxonomy(TestTagTaxonomyMixin, TestCase):
    """
    Test for Model Model System defined taxonomy
    """

    @ddt.data(
        (ModelSystemDefinedTaxonomy, NotImplementedError),
        (ModelObjectTag, NotImplementedError),
        (InvalidModelTaxonomy, AssertionError),
        (UserSystemDefinedTaxonomy, None),
    )
    @ddt.unpack
    def test_implementation_error(self, taxonomy_cls, expected_exception):
        if not expected_exception:
            assert taxonomy_cls()
        else:
            with self.assertRaises(expected_exception):
                taxonomy_cls()

    @ddt.data(
        (1, "tag_id"),  # Valid
        (0, "tag_id"),  # Invalid user
        (1, None),  # Testing parent validations
    )
    @ddt.unpack
    def test_validations(self, tag_external_id, tag_id):
        tag = Tag(
            id=tag_id,
            taxonomy=self.user_taxonomy,
            value="_val",
            external_id=tag_external_id,
        )
        object_tag = ObjectTag(
            object_id="id",
            tag=tag,
        )

        self.user_taxonomy.validate_object_tag(
            object_tag=object_tag,
            check_object=False,
            check_taxonomy=False,
            check_tag=True,
        )

    def test_tag_object_invalid_user(self):
        # Test user that doesn't exist
        with self.assertRaises(ValueError):
            self.user_taxonomy.tag_object(tags=[4], object_id="object_id")

    def _tag_object(self):
        return self.user_taxonomy.tag_object(
            tags=[self.user_1.id], object_id="object_id"
        )

    def test_tag_object_tag_creation(self):
        # Test creation of a new Tag with user taxonomy
        assert self.user_taxonomy.tag_set.count() == 0
        updated_tags = self._tag_object()
        assert self.user_taxonomy.tag_set.count() == 1
        assert len(updated_tags) == 1
        assert updated_tags[0].tag.external_id == str(self.user_1.id)
        assert updated_tags[0].tag.value == self.user_1.get_username()

        # Test parent functions
        taxonomy = TestModelTaxonomy(
            name="Test",
            description="Test",
            system_defined=True,
        )
        taxonomy.save()
        assert taxonomy.tag_set.count() == 0
        updated_tags = taxonomy.tag_object(tags=[self.user_1.id], object_id="object_id")
        assert taxonomy.tag_set.count() == 1
        assert taxonomy.tag_set.count() == 1
        assert len(updated_tags) == 1
        assert updated_tags[0].tag.external_id == str(self.user_1.id)
        assert updated_tags[0].tag.value == str(self.user_1.id)

    def test_tag_object_existing_tag(self):
        # Test add an existing Tag
        self._tag_object()
        assert self.user_taxonomy.tag_set.count() == 1
        updated_tags = self._tag_object()
        assert self.user_taxonomy.tag_set.count() == 1
        assert len(updated_tags) == 1
        assert updated_tags[0].tag.external_id == str(self.user_1.id)
        assert updated_tags[0].tag.value == self.user_1.get_username()

    def test_tag_object_resync(self):
        self._tag_object()

        self.user_1.username = "new_username"
        self.user_1.save()
        updated_tags = self._tag_object()
        assert self.user_taxonomy.tag_set.count() == 1
        assert len(updated_tags) == 1
        assert updated_tags[0].tag.external_id == str(self.user_1.id)
        assert updated_tags[0].tag.value == self.user_1.get_username()

    def test_tag_object_delete_user(self):
        # Test after delete user
        self._tag_object()
        user_1_id = self.user_1.id
        self.user_1.delete()
        with self.assertRaises(ValueError):
            self.user_taxonomy.tag_object(
                tags=[user_1_id],
                object_id="object_id",
            )

    def test_tag_ref(self):
        object_tag = TestModelTag()
        object_tag.tag_ref = 1
        object_tag.save()
        assert object_tag.tag is None
        assert object_tag.value == 1

    def test_get_instance(self):
        object_tag = TestModelTag()
        assert object_tag.get_instance() is None


@ddt.ddt
@override_settings(LANGUAGES=test_languages)
class TestLanguageTaxonomy(TestTagTaxonomyMixin, TestCase):
    """
    Test for Language taxonomy
    """

    @ddt.data(
        ("en", "tag_id"),  # Valid
        ("es", "tag_id"),  # Not available lang
        ("en", None),  # Test parent validations
    )
    @ddt.unpack
    def test_validations(self, lang, tag_id):
        tag = Tag(
            id=tag_id,
            taxonomy=self.language_taxonomy,
            value="_val",
            external_id=lang,
        )
        object_tag = ObjectTag(
            object_id="id",
            tag=tag,
        )
        self.language_taxonomy.validate_object_tag(
            object_tag=object_tag,
            check_object=False,
            check_taxonomy=False,
            check_tag=True,
        )

    def test_get_tags(self):
        tags = self.language_taxonomy.get_tags()
        for tag in tags:
            assert tag.external_id in test_languages
            assert tag.annotated_field == 0