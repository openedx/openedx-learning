""" Test the tagging models """

import ddt
from django.test.testcases import TestCase

from openedx_tagging.core.tagging.models import ObjectTag, Tag, Taxonomy


def get_tag(value):
    """
    Fetches and returns the tag with the given value.
    """
    return Tag.objects.get(value=value)


class TestTagTaxonomyMixin:
    """
    Base class that uses the taxonomy fixture to load a base taxonomy and tags for testing.
    """

    fixtures = ["tests/openedx_tagging/core/fixtures/tagging.yaml"]

    def setUp(self):
        super().setUp()
        self.taxonomy = Taxonomy.objects.get(name="Life on Earth")
        self.system_taxonomy = Taxonomy.objects.get(name="System Languages")
        self.archaea = get_tag("Archaea")
        self.archaebacteria = get_tag("Archaebacteria")
        self.bacteria = get_tag("Bacteria")
        self.eubacteria = get_tag("Eubacteria")
        self.chordata = get_tag("Chordata")
        self.mammalia = get_tag("Mammalia")

        # Domain tags (depth=0)
        # https://en.wikipedia.org/wiki/Domain_(biology)
        self.domain_tags = [
            get_tag("Archaea"),
            get_tag("Bacteria"),
            get_tag("Eukaryota"),
        ]
        # Kingdom tags (depth=1)
        self.kingdom_tags = [
            # Kingdoms of https://en.wikipedia.org/wiki/Archaea
            get_tag("DPANN"),
            get_tag("Euryarchaeida"),
            get_tag("Proteoarchaeota"),
            # Kingdoms of https://en.wikipedia.org/wiki/Bacterial_taxonomy
            get_tag("Archaebacteria"),
            get_tag("Eubacteria"),
            # Kingdoms of https://en.wikipedia.org/wiki/Eukaryote
            get_tag("Animalia"),
            get_tag("Fungi"),
            get_tag("Monera"),
            get_tag("Plantae"),
            get_tag("Protista"),
        ]
        # Phylum tags (depth=2)
        self.phylum_tags = [
            # Some phyla of https://en.wikipedia.org/wiki/Animalia
            get_tag("Arthropoda"),
            get_tag("Chordata"),
            get_tag("Cnidaria"),
            get_tag("Ctenophora"),
            get_tag("Gastrotrich"),
            get_tag("Placozoa"),
            get_tag("Porifera"),
        ]

    def setup_tag_depths(self):
        """
        Annotate our tags with depth so we can compare them.
        """
        for tag in self.domain_tags:
            tag.depth = 0
        for tag in self.kingdom_tags:
            tag.depth = 1
        for tag in self.phylum_tags:
            tag.depth = 2


@ddt.ddt
class TestModelTagTaxonomy(TestTagTaxonomyMixin, TestCase):
    """
    Test the Tag and Taxonomy models' properties and methods.
    """

    def test_system_defined(self):
        assert not self.taxonomy.system_defined
        assert self.system_taxonomy.system_defined

    def test_representations(self):
        assert (
            str(self.taxonomy) == repr(self.taxonomy) == "<Taxonomy> (1) Life on Earth"
        )
        assert (
            str(self.system_taxonomy)
            == repr(self.system_taxonomy)
            == "<Taxonomy> (2) System Languages"
        )
        assert str(self.bacteria) == repr(self.bacteria) == "<Tag> (1) Bacteria"

    @ddt.data(
        # Root tags just return their own value
        ("bacteria", ["Bacteria"]),
        # Second level tags return two levels
        ("eubacteria", ["Bacteria", "Eubacteria"]),
        # Third level tags return three levels
        ("chordata", ["Eukaryota", "Animalia", "Chordata"]),
        # Lineage beyond TAXONOMY_MAX_DEPTH won't trace back to the root
        ("mammalia", ["Animalia", "Chordata", "Mammalia"]),
    )
    @ddt.unpack
    def test_get_lineage(self, tag_attr, lineage):
        assert getattr(self, tag_attr).get_lineage() == lineage

    def test_get_tags(self):
        self.setup_tag_depths()
        assert self.taxonomy.get_tags() == [
            *self.domain_tags,
            *self.kingdom_tags,
            *self.phylum_tags,
        ]

    def test_get_tags_free_text(self):
        self.taxonomy.allow_free_text = True
        with self.assertNumQueries(0):
            assert self.taxonomy.get_tags() == []

    def test_get_tags_shallow_taxonomy(self):
        taxonomy = Taxonomy.objects.create(name="Difficulty")
        tags = [
            Tag.objects.create(taxonomy=taxonomy, value="1. Easy"),
            Tag.objects.create(taxonomy=taxonomy, value="2. Moderate"),
            Tag.objects.create(taxonomy=taxonomy, value="3. Hard"),
        ]
        with self.assertNumQueries(2):
            assert taxonomy.get_tags() == tags


class TestModelObjectTag(TestTagTaxonomyMixin, TestCase):
    """
    Test the ObjectTag model and the related Taxonomy methods and fields.
    """

    def setUp(self):
        super().setUp()
        self.tag = self.bacteria

    def test_object_tag_name(self):
        # ObjectTag's name defaults to its taxonomy's name
        object_tag = ObjectTag.objects.create(
            object_id="object:id",
            object_type="any_old_object",
            taxonomy=self.taxonomy,
        )
        assert object_tag.name == self.taxonomy.name

        # Even if we overwrite the name, it still uses the taxonomy's name
        object_tag.name = "Another tag"
        assert object_tag.name == self.taxonomy.name
        object_tag.save()
        assert object_tag.name == self.taxonomy.name

        # But if the taxonomy is deleted, then the object_tag's name reverts to our cached name
        self.taxonomy.delete()
        object_tag.refresh_from_db()
        assert object_tag.name == "Another tag"

    def test_object_tag_value(self):
        # ObjectTag's value defaults to its tag's value
        object_tag = ObjectTag.objects.create(
            object_id="object:id",
            object_type="any_old_object",
            taxonomy=self.taxonomy,
            tag=self.tag,
        )
        assert object_tag.value == self.tag.value

        # Even if we overwrite the value, it still uses the tag's value
        object_tag.value = "Another tag"
        assert object_tag.value == self.tag.value
        object_tag.save()
        assert object_tag.value == self.tag.value

        # But if the tag is deleted, then the object_tag's value reverts to our cached value
        self.tag.delete()
        object_tag.refresh_from_db()
        assert object_tag.value == "Another tag"

    def test_object_tag_lineage(self):
        # ObjectTag's value defaults to its tag's lineage
        object_tag = ObjectTag.objects.create(
            object_id="object:id",
            object_type="any_old_object",
            taxonomy=self.taxonomy,
            tag=self.tag,
        )
        assert object_tag.get_lineage() == self.tag.get_lineage()

        # Even if we overwrite the value, it still uses the tag's lineage
        object_tag.value = "Another tag"
        assert object_tag.get_lineage() == self.tag.get_lineage()
        object_tag.save()
        assert object_tag.get_lineage() == self.tag.get_lineage()

        # But if the tag is deleted, then the object_tag's lineage reverts to our cached value
        self.tag.delete()
        object_tag.refresh_from_db()
        assert object_tag.get_lineage() == ["Another tag"]

    def test_object_tag_is_valid(self):
        object_tag = ObjectTag(
            object_id="object:id",
            object_type="any_old_object",
        )
        assert not object_tag.is_valid

        object_tag.taxonomy = self.taxonomy
        assert not object_tag.is_valid

        object_tag.tag = self.tag
        assert object_tag.is_valid

        # or, we can have no tag, and a free-text taxonomy
        object_tag.tag = None
        self.taxonomy.allow_free_text = True
        assert object_tag.is_valid

    def test_validate_object_tag_invalid(self):
        taxonomy = Taxonomy.objects.create(
            name="Another taxonomy",
        )
        object_tag = ObjectTag(
            taxonomy=self.taxonomy,
        )
        assert not taxonomy.validate_object_tag(object_tag)

        object_tag.taxonomy = taxonomy
        assert not taxonomy.validate_object_tag(object_tag)

        taxonomy.allow_free_text = True
        assert not taxonomy.validate_object_tag(object_tag)

        object_tag.object_id = "object:id"
        object_tag.object_type = "object:type"
        assert taxonomy.validate_object_tag(object_tag)

    def test_tag_object(self):
        self.taxonomy.allow_multiple = True

        test_tags = [
            [
                self.archaea.id,
                self.eubacteria.id,
                self.chordata.id,
            ],
            [
                self.archaebacteria.id,
                self.chordata.id,
            ],
            [
                self.archaea.id,
                self.archaebacteria.id,
            ],
        ]

        # Tag and re-tag the object, checking that the expected tags are returned and deleted
        for tag_list in test_tags:
            object_tags = self.taxonomy.tag_object(
                tag_list,
                "biology101",
                "course",
            )

            # Ensure the expected number of tags exist in the database
            assert ObjectTag.objects.filter(
                taxonomy=self.taxonomy,
                object_id="biology101",
                object_type="course",
            ).count() == len(tag_list)
            # And the expected number of tags were returned
            assert len(object_tags) == len(tag_list)
            for index, object_tag in enumerate(object_tags):
                assert object_tag.tag_id == tag_list[index]
                assert object_tag.is_valid
                assert object_tag.taxonomy == self.taxonomy
                assert object_tag.name == self.taxonomy.name
                assert object_tag.object_id == "biology101"
                assert object_tag.object_type == "course"

    def test_tag_object_free_text(self):
        self.taxonomy.allow_free_text = True
        object_tags = self.taxonomy.tag_object(
            ["Eukaryota Xenomorph"],
            "biology101",
            "course",
        )
        assert len(object_tags) == 1
        object_tag = object_tags[0]
        assert object_tag.is_valid
        assert object_tag.taxonomy == self.taxonomy
        assert object_tag.name == self.taxonomy.name
        assert object_tag.tag_ref == "Eukaryota Xenomorph"
        assert object_tag.get_lineage() == ["Eukaryota Xenomorph"]
        assert object_tag.object_id == "biology101"
        assert object_tag.object_type == "course"

    def test_tag_object_no_multiple(self):
        with self.assertRaises(ValueError) as exc:
            self.taxonomy.tag_object(
                ["A", "B"],
                "biology101",
                "course",
            )
        assert "only allows one tag per object" in str(exc.exception)

    def test_tag_object_required(self):
        self.taxonomy.required = True
        with self.assertRaises(ValueError) as exc:
            self.taxonomy.tag_object(
                [],
                "biology101",
                "course",
            )
        assert "requires at least one tag per object" in str(exc.exception)

    def test_tag_object_invalid_tag(self):
        with self.assertRaises(ValueError) as exc:
            self.taxonomy.tag_object(
                ["Eukaryota Xenomorph"],
                "biology101",
                "course",
            )
        assert "Invalid object tag for taxonomy" in str(exc.exception)
