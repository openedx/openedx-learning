"""
Mixins for ImportExport tests
"""
from openedx_tagging.core.tagging.models import Taxonomy


class TestImportExportMixin:
    """
    Mixin that loads the base data for import/export tests
    """

    fixtures = ["tests/openedx_tagging/core/fixtures/tagging.yaml"]

    def setUp(self):
        self.taxonomy = Taxonomy.objects.get(name="Import Taxonomy Test")
        return super().setUp()
