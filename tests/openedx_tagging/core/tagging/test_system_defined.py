""" Test the System-defined taxonomies """

import ddt
from django.test.testcases import TestCase

from openedx_tagging.core.tagging.models import Taxonomy


class TestSystemDefinedTaxonomyMixin:
    """
    Mixin used on system-defined taxonomy tests
    """

    fixtures = ["openedx_tagging/core/tagging/system_defined_taxonomies/fixtures/language_taxonomy.yaml"]

    def setUp(self):
        super().setUp()
        self.language_taxonomy = Taxonomy.objects.get(pk=1)


@ddt.ddt
class TestLanguageTaxonomy(TestSystemDefinedTaxonomyMixin, TestCase):
    """
    Test the Language Taxonomy
    """

    @ddt.data(
        ('en', 'English'),
        ('az', 'Azerbaijani'),
        ('id', 'Indonesian'),
        ('qu', 'Quechua'),
        ('zu', 'Zulu'),
    )
    @ddt.unpack
    def test_fixture(self, lang_code, lang_value):
        self.assertEqual(self.language_taxonomy.name, 'Language')
        lang = self.language_taxonomy.tag_set.get(external_id=lang_code)
        self.assertEqual(lang.value, lang_value)
        