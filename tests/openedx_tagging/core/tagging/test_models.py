"""
Test the tagging base models
"""
import ddt  # type: ignore[import]
import pytest
from django.contrib.auth import get_user_model
from django.core.exceptions import ValidationError
from django.db import transaction
from django.db.utils import IntegrityError
from django.test.testcases import TestCase

from openedx_tagging.core.tagging import api
from openedx_tagging.core.tagging.models import LanguageTaxonomy, ObjectTag, Tag, Taxonomy


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
        self.system_taxonomy = Taxonomy.objects.get(
            name="System defined taxonomy"
        )
        self.language_taxonomy = LanguageTaxonomy.objects.get(name="Languages")
        self.user_taxonomy = Taxonomy.objects.get(name="User Authors").cast()
        self.archaea = get_tag("Archaea")
        self.archaebacteria = get_tag("Archaebacteria")
        self.bacteria = get_tag("Bacteria")
        self.eubacteria = get_tag("Eubacteria")
        self.chordata = get_tag("Chordata")
        self.mammalia = get_tag("Mammalia")
        self.animalia = get_tag("Animalia")
        self.system_taxonomy_tag = get_tag("System Tag 1")
        self.english_tag = self.language_taxonomy.tag_for_external_id("en")
        self.user_1 = get_user_model()(
            id=1,
            username="test_user_1",
        )
        self.user_1.save()
        self.user_2 = get_user_model()(
            id=2,
            username="test_user_2",
        )
        self.user_2.save()

        # Domain tags (depth=0)
        # https://en.wikipedia.org/wiki/Domain_(biology)
        self.domain_tags = [
            get_tag("Archaea"),
            get_tag("Bacteria"),
            get_tag("Eukaryota"),
        ]
        # Domain tags that contains 'ar'
        self.filtered_domain_tags = [
            get_tag("Archaea"),
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
        # Phylum tags that contains 'da'
        self.filtered_phylum_tags = [
            get_tag("Arthropoda"),
            get_tag("Chordata"),
            get_tag("Cnidaria"),
        ]

        # Biology tags that contains 'eu'
        self.filtered_tags = [
            get_tag("Eubacteria"),
            get_tag("Eukaryota"),
            get_tag("Euryarchaeida"),
        ]

        self.system_tags = [
            get_tag("System Tag 1"),
            get_tag("System Tag 2"),
            get_tag("System Tag 3"),
            get_tag("System Tag 4"),
        ]

        self.dummy_taxonomies = []
        for i in range(100):
            taxonomy = Taxonomy.objects.create(
                name=f"ZZ Dummy Taxonomy {i:03}",
                allow_free_text=True,
                allow_multiple=True
            )
            ObjectTag.objects.create(
                object_id="limit_tag_count",
                taxonomy=taxonomy,
                _name=taxonomy.name,
                _value="Dummy Tag",
            )
            self.dummy_taxonomies.append(taxonomy)

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


class TaxonomyTestSubclassA(Taxonomy):
    """
    Model A for testing the taxonomy subclass casting.
    """

    class Meta:
        managed = False
        proxy = True
        app_label = "oel_tagging"


class TaxonomyTestSubclassB(TaxonomyTestSubclassA):
    """
    Model B for testing the taxonomy subclass casting.
    """

    class Meta:
        managed = False
        proxy = True
        app_label = "oel_tagging"


class ObjectTagTestSubclass(ObjectTag):
    """
    Model for testing the ObjectTag copy.
    """

    class Meta:
        managed = False
        proxy = True
        app_label = "oel_tagging"


@ddt.ddt
class TestTagTaxonomy(TestTagTaxonomyMixin, TestCase):
    """
    Test the Tag and Taxonomy models' properties and methods.
    """

    def test_system_defined(self):
        assert not self.taxonomy.system_defined
        assert self.system_taxonomy.cast().system_defined

    def test_representations(self):
        assert (
            str(self.taxonomy) == repr(self.taxonomy) == "<Taxonomy> (1) Life on Earth"
        )
        assert (
            str(self.language_taxonomy)
            == repr(self.language_taxonomy)
            == "<LanguageTaxonomy> (-1) Languages"
        )
        assert str(self.bacteria) == repr(self.bacteria) == "<Tag> (1) Bacteria"

    def test_taxonomy_cast(self):
        for subclass in (
            TaxonomyTestSubclassA,
            # Ensure that casting to a sub-subclass works as expected
            TaxonomyTestSubclassB,
            # and that we can un-set the subclass
            None,
        ):
            self.taxonomy.taxonomy_class = subclass
            cast_taxonomy = self.taxonomy.cast()
            if subclass:
                expected_class = subclass.__name__
            else:
                expected_class = "Taxonomy"
                assert self.taxonomy == cast_taxonomy
            assert (
                str(cast_taxonomy)
                == repr(cast_taxonomy)
                == f"<{expected_class}> (1) Life on Earth"
            )

    def test_taxonomy_cast_import_error(self):
        taxonomy = Taxonomy.objects.create(
            name="Invalid cast", _taxonomy_class="not.a.class"
        )
        # Error is logged, but ignored.
        cast_taxonomy = taxonomy.cast()
        assert cast_taxonomy == taxonomy
        assert (
            str(cast_taxonomy)
            == repr(cast_taxonomy)
            == f"<Taxonomy> ({taxonomy.id}) Invalid cast"
        )

    def test_taxonomy_cast_bad_value(self):
        with self.assertRaises(ValueError) as exc:
            self.taxonomy.taxonomy_class = str
        assert "<class 'str'> must be a subclass of Taxonomy" in str(exc.exception)

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

    def test_get_root_tags(self):
        assert list(self.taxonomy.get_filtered_tags()) == self.domain_tags
        assert list(
            self.taxonomy.get_filtered_tags(search_term='aR')
        ) == self.filtered_domain_tags

    def test_get_tags_free_text(self):
        self.taxonomy.allow_free_text = True
        with self.assertNumQueries(0):
            assert self.taxonomy.get_tags() == []

    def test_get_children_tags(self):
        assert list(
            self.taxonomy.get_filtered_tags(parent_tag_id=self.animalia.id)
        ) == self.phylum_tags
        assert list(
            self.taxonomy.get_filtered_tags(
                parent_tag_id=self.animalia.id,
                search_term='dA',
            )
        ) == self.filtered_phylum_tags
        assert not list(
            self.system_taxonomy.get_filtered_tags(
                parent_tag_id=self.system_taxonomy_tag.id
            )
        )

    def test_get_children_tags_free_text(self):
        self.taxonomy.allow_free_text = True
        assert not list(self.taxonomy.get_filtered_tags(
            parent_tag_id=self.animalia.id
        ))
        assert not list(self.taxonomy.get_filtered_tags(
            parent_tag_id=self.animalia.id,
            search_term='dA',
        ))

    def test_search_tags(self):
        assert list(self.taxonomy.get_filtered_tags(
            search_term='eU',
            search_in_all=True
        )) == self.filtered_tags

    def test_get_tags_shallow_taxonomy(self):
        taxonomy = Taxonomy.objects.create(name="Difficulty")
        tags = [
            Tag.objects.create(taxonomy=taxonomy, value="1. Easy"),
            Tag.objects.create(taxonomy=taxonomy, value="2. Moderate"),
            Tag.objects.create(taxonomy=taxonomy, value="3. Hard"),
        ]
        with self.assertNumQueries(2):
            assert taxonomy.get_tags() == tags

    def test_unique_tags(self):
        # Creating new tag
        Tag(
            taxonomy=self.taxonomy,
            value='New value'
        ).save()

        # Creating repeated tag
        with self.assertRaises(IntegrityError):
            Tag(
                taxonomy=self.taxonomy,
                value=self.archaea.value,
            ).save()


class TestObjectTag(TestTagTaxonomyMixin, TestCase):
    """
    Test the ObjectTag model and the related Taxonomy methods and fields.
    """

    def setUp(self):
        super().setUp()
        self.tag = self.bacteria
        self.object_tag = ObjectTag.objects.create(
            object_id="object:id:1",
            taxonomy=self.taxonomy,
            tag=self.tag,
        )

    def test_representations(self):
        assert (
            str(self.object_tag)
            == repr(self.object_tag)
            == "<ObjectTag> object:id:1: Life on Earth=Bacteria"
        )

    def test_cast(self):
        copy_tag = ObjectTagTestSubclass.cast(self.object_tag)
        assert (
            str(copy_tag)
            == repr(copy_tag)
            == "<ObjectTagTestSubclass> object:id:1: Life on Earth=Bacteria"
        )

    def test_object_tag_name(self):
        # ObjectTag's name defaults to its taxonomy's name
        assert self.object_tag.name == self.taxonomy.name

        # Even if we overwrite the name, it still uses the taxonomy's name
        self.object_tag.name = "Another tag"
        assert self.object_tag.name == self.taxonomy.name
        self.object_tag.save()
        assert self.object_tag.name == self.taxonomy.name

        # But if the taxonomy is deleted, then the object_tag's name reverts to our cached name
        self.taxonomy.delete()
        self.object_tag.refresh_from_db()
        assert self.object_tag.name == "Another tag"

    def test_object_tag_value(self):
        # ObjectTag's value defaults to its tag's value
        object_tag = ObjectTag.objects.create(
            object_id="object:id",
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

    def test_validate_value_free_text(self):
        open_taxonomy = Taxonomy.objects.create(
            name="Freetext Life",
            allow_free_text=True,
        )
        # An empty string or other non-string is not valid in a free-text taxonomy
        assert open_taxonomy.validate_value("") is False
        assert open_taxonomy.validate_value(None) is False
        assert open_taxonomy.validate_value(True) is False
        # But any other string value is valid:
        assert open_taxonomy.validate_value("Any text we want") is True

    def test_validate_value_closed(self):
        """
        Test validate_value() in a closed taxonomy
        """
        assert self.taxonomy.validate_value("Eukaryota") is True
        assert self.taxonomy.validate_value("Foobarensia") is False
        assert self.taxonomy.tag_for_value("Eukaryota").value == "Eukaryota"
        with pytest.raises(api.TagDoesNotExist):
            self.taxonomy.tag_for_value("Foobarensia")

    def test_clean(self):
        # ObjectTags in a closed taxonomy require a tag in that taxonomy
        object_tag = ObjectTag(taxonomy=self.taxonomy, tag=Tag.objects.create(
            taxonomy=self.system_taxonomy,  # Different taxonomy
            value="PT",
        ))
        with pytest.raises(ValidationError):
            object_tag.full_clean()
        object_tag.tag = self.tag
        object_tag._value = self.tag.value  # pylint: disable=protected-access
        object_tag.full_clean()

    def test_tag_case(self) -> None:
        """
        Test that the object_id is case sensitive.
        """
        # Tag with object_id with lower case
        api.tag_object(self.taxonomy, [self.domain_tags[0].value], object_id="case:id:2")

        # Tag with object_id with upper case should not trigger IntegrityError
        api.tag_object(self.taxonomy, [self.domain_tags[0].value], object_id="CASE:id:2")

        # Create another ObjectTag with lower case object_id should trigger IntegrityError
        with transaction.atomic():
            with pytest.raises(IntegrityError):
                ObjectTag(
                    object_id="case:id:2",
                    taxonomy=self.taxonomy,
                    tag=self.domain_tags[0],
                ).save()

        # Create another ObjectTag with upper case object_id should trigger IntegrityError
        with transaction.atomic():
            with pytest.raises(IntegrityError):
                ObjectTag(
                    object_id="CASE:id:2",
                    taxonomy=self.taxonomy,
                    tag=self.domain_tags[0],
                ).save()

    def test_is_deleted(self):
        self.taxonomy.allow_multiple = True
        self.taxonomy.save()
        open_taxonomy = Taxonomy.objects.create(name="Freetext Life", allow_free_text=True, allow_multiple=True)

        object_id = "obj1"
        # Create some tags:
        api.tag_object(self.taxonomy, [self.archaea.value, self.bacteria.value], object_id)  # Regular tags
        api.tag_object(open_taxonomy, ["foo", "bar", "tribble"], object_id)  # Free text tags

        # At first, none of these will be deleted:
        assert [(t.value, t.is_deleted) for t in api.get_object_tags(object_id)] == [
            (self.archaea.value, False),
            (self.bacteria.value, False),
            ("foo", False),
            ("bar", False),
            ("tribble", False),
        ]

        # Delete "bacteria" from the taxonomy:
        self.bacteria.delete()  # TODO: add an API method for this

        assert [(t.value, t.is_deleted) for t in api.get_object_tags(object_id)] == [
            (self.archaea.value, False),
            (self.bacteria.value, True),  # <--- deleted! But the value is preserved.
            ("foo", False),
            ("bar", False),
            ("tribble", False),
        ]

        # Then delete the whole free text taxonomy
        open_taxonomy.delete()

        assert [(t.value, t.is_deleted) for t in api.get_object_tags(object_id)] == [
            (self.archaea.value, False),
            (self.bacteria.value, True),  # <--- deleted! But the value is preserved.
            ("foo", True),  # <--- Deleted, but the value is preserved
            ("bar", True),  # <--- Deleted, but the value is preserved
            ("tribble", True),  # <--- Deleted, but the value is preserved
        ]
