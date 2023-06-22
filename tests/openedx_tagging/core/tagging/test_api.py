""" Test the tagging APIs """

from io import BytesIO
import json
from unittest.mock import patch
import ddt

from django.test.testcases import TestCase

import openedx_tagging.core.tagging.api as tagging_api
from openedx_tagging.core.tagging.models import ObjectTag, Tag

from .test_models import TestTagTaxonomyMixin

@ddt.ddt
class TestApiTagging(TestTagTaxonomyMixin, TestCase):
    """
    Test the Tagging API methods.
    """

    def get_tag(self, tags, tag_value):
        return next((item for item in tags if item.value == tag_value), None)

    def test_create_taxonomy(self):
        params = {
            "name": "Difficulty",
            "description": "This taxonomy contains tags describing the difficulty of an activity",
            "enabled": False,
            "required": True,
            "allow_multiple": True,
            "allow_free_text": True,
        }
        taxonomy = tagging_api.create_taxonomy(**params)
        for param, value in params.items():
            assert getattr(taxonomy, param) == value

    def test_get_taxonomies(self):
        tax1 = tagging_api.create_taxonomy("Enabled")
        tax2 = tagging_api.create_taxonomy("Disabled", enabled=False)
        enabled = tagging_api.get_taxonomies()
        assert list(enabled) == [tax1, self.taxonomy]

        disabled = tagging_api.get_taxonomies(enabled=False)
        assert list(disabled) == [tax2]

        both = tagging_api.get_taxonomies(enabled=None)
        assert list(both) == [tax2, tax1, self.taxonomy]

    def test_get_tags(self):
        self.setup_tag_depths()
        assert tagging_api.get_tags(self.taxonomy) == [
            *self.domain_tags,
            *self.kingdom_tags,
            *self.phylum_tags,
        ]

    def check_object_tag(self, object_tag, taxonomy, tag, name, value):
        """
        Verifies that the properties of the given object_tag (once refreshed from the database) match those given.
        """
        object_tag.refresh_from_db()
        assert object_tag.taxonomy == taxonomy
        assert object_tag.tag == tag
        assert object_tag.name == name
        assert object_tag.value == value

    def test_resync_object_tags(self):
        missing_links = ObjectTag(object_id="abc", object_type="alpha")
        missing_links.name = self.taxonomy.name
        missing_links.value = self.mammalia.value
        missing_links.save()
        changed_links = ObjectTag(
            object_id="def",
            object_type="alpha",
            taxonomy=self.taxonomy,
            tag=self.mammalia,
        )
        changed_links.name = "Life"
        changed_links.value = "Animals"
        changed_links.save()

        no_changes = ObjectTag(
            object_id="ghi",
            object_type="beta",
            taxonomy=self.taxonomy,
            tag=self.mammalia,
        )
        no_changes.name = self.taxonomy.name
        no_changes.value = self.mammalia.value
        no_changes.save()

        changed = tagging_api.resync_object_tags()
        assert changed == 2
        for object_tag in (missing_links, changed_links, no_changes):
            self.check_object_tag(
                object_tag, self.taxonomy, self.mammalia, "Life on Earth", "Mammalia"
            )

        # Once all tags are resynced, they stay that way
        changed = tagging_api.resync_object_tags()
        assert changed == 0

        # ObjectTag value preserved even if linked tag is deleted
        self.mammalia.delete()
        for object_tag in (missing_links, changed_links, no_changes):
            self.check_object_tag(
                object_tag, self.taxonomy, None, "Life on Earth", "Mammalia"
            )

        # ObjectTag name preserved even if linked taxonomy is deleted
        self.taxonomy.delete()
        for object_tag in (missing_links, changed_links, no_changes):
            self.check_object_tag(object_tag, None, None, "Life on Earth", "Mammalia")

        # Resyncing the tags for code coverage
        changed = tagging_api.resync_object_tags()
        assert changed == 0

        # Recreate the taxonomy and resync some tags
        first_taxonomy = tagging_api.create_taxonomy("Life on Earth")
        second_taxonomy = tagging_api.create_taxonomy("Life on Earth")
        new_tag = Tag.objects.create(
            value="Mammalia",
            taxonomy=second_taxonomy,
        )

        with patch(
            "openedx_tagging.core.tagging.models.Taxonomy.validate_object_tag",
            side_effect=[False, True, False, True],
        ):
            changed = tagging_api.resync_object_tags(
                ObjectTag.objects.filter(object_type="alpha")
            )
            assert changed == 2
        for object_tag in (missing_links, changed_links):
            self.check_object_tag(
                object_tag, second_taxonomy, new_tag, "Life on Earth", "Mammalia"
            )

        # Ensure the omitted tag was not updated
        self.check_object_tag(no_changes, None, None, "Life on Earth", "Mammalia")

        # Update that one too (without the patching)
        changed = tagging_api.resync_object_tags(
            ObjectTag.objects.filter(object_type="beta")
        )
        assert changed == 1
        self.check_object_tag(
            no_changes, first_taxonomy, None, "Life on Earth", "Mammalia"
        )

    def test_tag_object(self):
        self.taxonomy.allow_multiple = True
        test_tags = [
            [
                self.archaea.id,
                self.eubacteria.id,
                self.chordata.id,
            ],
            [
                self.chordata.id,
                self.archaebacteria.id,
            ],
            [
                self.archaebacteria.id,
                self.archaea.id,
            ],
        ]

        # Tag and re-tag the object, checking that the expected tags are returned and deleted
        for tag_list in test_tags:
            object_tags = tagging_api.tag_object(
                self.taxonomy,
                tag_list,
                "biology101",
                "course",
            )

            # Ensure the expected number of tags exist in the database
            assert (
                tagging_api.get_object_tags(
                    taxonomy=self.taxonomy,
                    object_id="biology101",
                    object_type="course",
                )
                == object_tags
            )
            # And the expected number of tags were returned
            assert len(object_tags) == len(tag_list)
            for index, object_tag in enumerate(object_tags):
                assert object_tag.tag_id == tag_list[index]
                assert object_tag.is_valid
                assert object_tag.taxonomy == self.taxonomy
                assert object_tag.name == self.taxonomy.name
                assert object_tag.object_id == "biology101"
                assert object_tag.object_type == "course"

    def test_import_tags_csv(self):
        csv_data = "id,name,parent_id,parent_name\n1,Tag 1,,\n2,Tag 2,1,Tag 1\n"
        csv_file = BytesIO(csv_data.encode())

        taxonomy = tagging_api.create_taxonomy("CSV_Taxonomy")
        tagging_api.import_tags(taxonomy, csv_file, tagging_api.TaxonomyDataFormat.CSV)
        tags = tagging_api.get_tags(taxonomy)

        # Assert that the tags are imported correctly
        self.assertEqual(len(tags), 2)
        item = self.get_tag(tags, 'Tag 1')
        self.assertIsNotNone(item)
        item = self.get_tag(tags, 'Tag 2')
        self.assertIsNotNone(item)
        self.assertEqual(item.parent.value, 'Tag 1')

    def test_import_tags_json(self):
        json_data = {"tags": [
            {"id": "tag_1", "name": "Tag 1"},
            {"id": "tag_2", "name": "Tag 2", "parent_id": "tag_1", "parent_name": "Tag 1"}
        ]}
        json_file = BytesIO(json.dumps(json_data).encode())

        taxonomy = tagging_api.create_taxonomy("JSON_Taxonomy")
        tagging_api.import_tags(taxonomy, json_file, tagging_api.TaxonomyDataFormat.JSON)
        tags = tagging_api.get_tags(taxonomy)

        # Assert that the tags are imported correctly
        self.assertEqual(len(tags), 2)
        item = self.get_tag(tags, 'Tag 1')
        self.assertIsNotNone(item)
        item = self.get_tag(tags, 'Tag 2')
        self.assertIsNotNone(item)
        self.assertEqual(item.parent.value, 'Tag 1')

    def test_import_tags_replace(self):
        self.assertEqual(len(tagging_api.get_tags(self.taxonomy)), 20)

        json_data = {"tags": [{'id': "tag_1", "name": "Bacteria"},{'id': "tag_2", "name": "Archaea"}]}
        json_file = BytesIO(json.dumps(json_data).encode())

        tagging_api.import_tags(self.taxonomy, json_file, tagging_api.TaxonomyDataFormat.JSON, replace=True)
        tags = tagging_api.get_tags(self.taxonomy)
        self.assertEqual(len(tags), 2)
        item = self.get_tag(tags, 'Bacteria')
        self.assertIsNotNone(item)
        item = self.get_tag(tags, 'Archaea')
        self.assertIsNotNone(item)

    def test_import_tags_update(self):
        self.assertEqual(len(tagging_api.get_tags(self.taxonomy)), 20)

        json_data = {"tags": [
            # Name update
            {"id": "tag_1", "name": "Bacteria 2.0"},
            # Parent update
            {"id": "tag_4", "name": "Eubacteria 2.0", "parent_id": "tag_2", "parent_name": "Archaea"},
            # Parent deletion
            {"id": "tag_5", "name": "Archaebacteria 2.0"},
            # New Tag
            {"id": "tag_22", "name": "My new tag 2.0", "parent_id": "tag_1", "parent_name": "Bacteria 2.0"},
        ]}

        json_file = BytesIO(json.dumps(json_data).encode())
        tagging_api.import_tags(self.taxonomy, json_file, tagging_api.TaxonomyDataFormat.JSON)
        tags = tagging_api.get_tags(self.taxonomy)
        self.assertEqual(len(tags), 21)

        # Check name update
        item = self.get_tag(tags, 'Bacteria 2.0')
        self.assertIsNotNone(item)

        # Check parent update
        item = self.get_tag(tags, 'Eubacteria 2.0')
        self.assertIsNotNone(item)

        # Check parent deletion
        self.assertEqual(item.parent.value, 'Archaea')
        item = self.get_tag(tags, 'Archaebacteria 2.0')
        self.assertIsNotNone(item)
        self.assertIsNone(item.parent)

        # Check new tag
        item = self.get_tag(tags, 'My new tag 2.0')
        self.assertIsNotNone(item)
        self.assertEqual(item.parent.value, 'Bacteria 2.0')

        # Check existing tag
        item = self.get_tag(tags, 'Porifera')
        self.assertIsNotNone(item)

    def test_import_tags_validations(self):
        invalid_csv_data = "id,name,tag_parent_id,tag_parent_name\n1,Tag 1,,\n2,Tag 2,1,Tag 1\n"
        taxonomy = tagging_api.create_taxonomy("Validations_Taxonomy")
        taxonomy_free_text = tagging_api.create_taxonomy("Free_Taxonomy", allow_free_text=True)

        # Open the file in each test since it always closes even if there is an error
        with self.assertRaises(ValueError):
            invalid_csv_file = BytesIO(invalid_csv_data.encode())
            tagging_api.import_tags(taxonomy_free_text, invalid_csv_file, tagging_api.TaxonomyDataFormat.CSV)

        with self.assertRaises(ValueError):
            invalid_csv_file = BytesIO(invalid_csv_data.encode())
            tagging_api.import_tags(taxonomy, invalid_csv_file, "XML")

        with self.assertRaises(ValueError):
            invalid_csv_file = BytesIO(invalid_csv_data.encode())
            tagging_api.import_tags(taxonomy, invalid_csv_file, tagging_api.TaxonomyDataFormat.CSV)

    @ddt.data(
        # Invalid json format
        {"taxonomy_tags": [
            {"id": "1", "name": "Tag 1"},
            {"id": "2", "name": "Tag 2", "parent_id": "1", "parent_name": "Tag 1"}
        ]},
        # Invalid 'id' key
        {"tags": [
            {"tag_id": "1", "name": "Tag 1"},
        ]},
        # Invalid 'name' key
        {"tags": [
            {"id": "1", "tag_name": "Tag 1"},
        ]}
    )
    def test_import_tags_json_validations(self, json_data):
        json_file = BytesIO(json.dumps(json_data).encode())
        taxonomy = tagging_api.create_taxonomy("Validations_Taxonomy")

        with self.assertRaises(ValueError):
            tagging_api.import_tags(taxonomy, json_file, tagging_api.TaxonomyDataFormat.JSON)

    def test_import_tags_resync(self):
        object_id = 'course_1'
        object_tag = ObjectTag(
            object_id=object_id,
            object_type='course',
            taxonomy=self.taxonomy,
            tag=self.bacteria,
        )
        tagging_api.resync_object_tags([object_tag])
        object_tag = ObjectTag.objects.get(object_id=object_id)
        self.assertEqual(object_tag.tag.value, 'Bacteria')
        self.assertEqual(object_tag._value, 'Bacteria')

        json_data = {"tags": [{"id": "tag_1", "name": "Bacteria 2.0"}]}
        json_file = BytesIO(json.dumps(json_data).encode())

        # Import
        tagging_api.import_tags(self.taxonomy, json_file, tagging_api.TaxonomyDataFormat.JSON)
        object_tag = ObjectTag.objects.get(object_id=object_id)
        self.assertEqual(object_tag.tag.value, 'Bacteria 2.0')
        self.assertEqual(object_tag._value, 'Bacteria 2.0')

        json_data = {"tags": [{"id": "tag_1", "name": "Bacteria 3.0"}]}
        json_file = BytesIO(json.dumps(json_data).encode())

        # Import and replace
        tagging_api.import_tags(self.taxonomy, json_file, tagging_api.TaxonomyDataFormat.JSON, replace=True)
        object_tag = ObjectTag.objects.get(object_id=object_id)
        self.assertEqual(object_tag.tag.value, 'Bacteria 3.0')
        self.assertEqual(object_tag._value, 'Bacteria 3.0')

    def test_export_tags_json(self):
        json_data = {
            "name": "Life on Earth",
            "description": "This taxonomy contains the Kingdoms of the Earth",
            "tags": [
                {'id': "tag_2", "name": "Archaea"},
                {'id': "tag_1", "name": "Bacteria"},
                {'id': "tag_4", "name": "Euryarchaeida", "parent_id": "tag_2", "parent_name": "Archaea"},
                {'id': "tag_3", "name": "Eubacteria", "parent_id": "tag_1", "parent_name": "Bacteria"},
            ]
        }
        json_file = BytesIO(json.dumps(json_data).encode())

        # Import and replace
        tagging_api.import_tags(self.taxonomy, json_file, tagging_api.TaxonomyDataFormat.JSON, replace=True)

        result = tagging_api.export_tags(self.taxonomy, tagging_api.TaxonomyDataFormat.JSON)
        self.assertEqual(json.loads(result), json_data)

    def test_export_tags_csv(self):
        csv_data = "id,name,parent_id,parent_name\r\ntag_2,Archaea,,\r\ntag_1,Bacteria,,\r\n" \
                   "tag_4,Euryarchaeida,tag_2,Archaea\r\ntag_3,Eubacteria,tag_1,Bacteria\r\n"

        csv_file = BytesIO(csv_data.encode())

        # Import and replace
        tagging_api.import_tags(self.taxonomy, csv_file, tagging_api.TaxonomyDataFormat.CSV, replace=True)
        result = tagging_api.export_tags(self.taxonomy, tagging_api.TaxonomyDataFormat.CSV)
        self.assertEqual(result, csv_data)

    def test_export_tags_validation(self):
        taxonomy_free_text = tagging_api.create_taxonomy("Free_Taxonomy", allow_free_text=True)
        taxonomy_xml = tagging_api.create_taxonomy("XML_Taxonomy")

        with self.assertRaises(ValueError):
            tagging_api.export_tags(taxonomy_free_text, tagging_api.TaxonomyDataFormat.JSON)

        with self.assertRaises(ValueError):
            tagging_api.export_tags(taxonomy_xml, "XML")
