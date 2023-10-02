"""
Tests the import/export template files.
"""
from __future__ import annotations

import os

import ddt  # type: ignore[import]
from django.test.testcases import TestCase

from openedx_tagging.core.tagging.api import get_tags
from openedx_tagging.core.tagging.import_export import ParserFormat
from openedx_tagging.core.tagging.import_export import api as import_api

from .mixins import TestImportExportMixin


@ddt.ddt
class TestImportTemplate(TestImportExportMixin, TestCase):
    """
    Test the CSV import/export template.
    """

    def open_template_file(self, template_file):
        """
        Returns an open file handler for the template file.
        """
        dirname = os.path.dirname(__file__)
        filename = os.path.join(
            dirname,
            '../../../../..',
            template_file,
        )
        return open(filename, "rb")

    @ddt.data(
        ('openedx_tagging/core/tagging/import_export/template.csv', ParserFormat.CSV),
        ('openedx_tagging/core/tagging/import_export/template.json', ParserFormat.JSON),
    )
    @ddt.unpack
    def test_import_template(self, template_file, parser_format):
        with self.open_template_file(template_file) as import_file:
            assert import_api.import_tags(
                self.taxonomy,
                import_file,
                parser_format,
                replace=True,
            ), import_api.get_last_import_log(self.taxonomy)

        imported_tags = [
            {
                "external_id": tag.external_id,
                "value": tag.value,
                "parent": tag.parent.external_id if tag.parent else None,
            }
            for tag in get_tags(self.taxonomy)
        ]
        assert imported_tags == [
            {'external_id': "ELECTRIC", 'parent': None, 'value': 'Electronic instruments'},
            {'external_id': 'PERCUSS', 'parent': None, 'value': 'Percussion instruments'},
            {'external_id': 'STRINGS', 'parent': None, 'value': 'String instruments'},
            {'external_id': 'WINDS', 'parent': None, 'value': 'Wind instruments'},
            {'external_id': 'SYNTH', 'parent': 'ELECTRIC', 'value': 'Synthesizer'},
            {'external_id': 'THERAMIN', 'parent': 'ELECTRIC', 'value': 'Theramin'},
            {'external_id': 'CHORD', 'parent': 'PERCUSS', 'value': 'Chordophone'},
            {'external_id': 'BELLS', 'parent': 'PERCUSS', 'value': 'Idiophone'},
            {'external_id': 'DRUMS', 'parent': 'PERCUSS', 'value': 'Membranophone'},
            {'external_id': 'BOW', 'parent': 'STRINGS', 'value': 'Bowed strings'},
            {'external_id': 'PLUCK', 'parent': 'STRINGS', 'value': 'Plucked strings'},
            {'external_id': 'BRASS', 'parent': 'WINDS', 'value': 'Brass'},
            {'external_id': 'WOODS', 'parent': 'WINDS', 'value': 'Woodwinds'},
            {'external_id': 'CELLO', 'parent': 'BOW', 'value': 'Cello'},
            {'external_id': 'VIOLIN', 'parent': 'BOW', 'value': 'Violin'},
            {'external_id': 'TRUMPET', 'parent': 'BRASS', 'value': 'Trumpet'},
            {'external_id': 'TUBA', 'parent': 'BRASS', 'value': 'Tuba'},
            {'external_id': 'PIANO', 'parent': 'CHORD', 'value': 'Piano'},
            # This tag is present in the import files, but it will be omitted from get_tags()
            # because it sits beyond TAXONOMY_MAX_DEPTH.
            # {'external_id': 'PYLE', 'parent': 'CAJÓN', 'value': 'Pyle Stringed Jam Cajón'},
            {'external_id': 'CELESTA', 'parent': 'BELLS', 'value': 'Celesta'},
            {'external_id': 'HI-HAT', 'parent': 'BELLS', 'value': 'Hi-hat'},
            {'external_id': 'CAJÓN', 'parent': 'DRUMS', 'value': 'Cajón'},
            {'external_id': 'TABLA', 'parent': 'DRUMS', 'value': 'Tabla'},
            {'external_id': 'BANJO', 'parent': 'PLUCK', 'value': 'Banjo'},
            {'external_id': 'HARP', 'parent': 'PLUCK', 'value': 'Harp'},
            {'external_id': 'MANDOLIN', 'parent': 'PLUCK', 'value': 'Mandolin'},
            {'external_id': 'CLARINET', 'parent': 'WOODS', 'value': 'Clarinet'},
            {'external_id': 'FLUTE', 'parent': 'WOODS', 'value': 'Flute'},
            {'external_id': 'OBOE', 'parent': 'WOODS', 'value': 'Oboe'},
        ]
