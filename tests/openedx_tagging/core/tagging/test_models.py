"""
Test the tagging base models
"""
from __future__ import annotations

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



@ddt.ddt
class TestFilteredTagsClosedTaxonomy(TestTagTaxonomyMixin, TestCase):
    """
    Test the the get_filtered_tags() method of closed taxonomies
    """
    def test_get_root(self) -> None:
        """
        Test basic retrieval of root tags in the closed taxonomy, using
        get_filtered_tags(). Without counts included.
        """
        result = list(self.taxonomy.get_filtered_tags(depth=1, include_counts=False))
        common_fields = {"depth": 0, "parent_value": None, "external_id": None}
        assert result == [
            # These are the root tags, in alphabetical order:
            {"value": "Archaea", "child_count": 3, **common_fields},
            {"value": "Bacteria", "child_count": 2, **common_fields},
            {"value": "Eukaryota", "child_count": 5, **common_fields},
        ]

    def test_get_child_tags_one_level(self) -> None:
        """
        Test basic retrieval of tags one level below the "Eukaryota" root tag in
        the closed taxonomy, using get_filtered_tags(). With counts included.
        """
        result = list(self.taxonomy.get_filtered_tags(depth=1, parent_tag_value="Eukaryota"))
        common_fields = {"depth": 1, "parent_value": "Eukaryota", "usage_count": 0, "external_id": None}
        assert result == [
            # These are the Eukaryota tags, in alphabetical order:
            {"value": "Animalia", "child_count": 7, **common_fields},
            {"value": "Fungi", "child_count": 0, **common_fields},
            {"value": "Monera", "child_count": 0, **common_fields},
            {"value": "Plantae", "child_count": 0, **common_fields},
            {"value": "Protista", "child_count": 0, **common_fields},
        ]

    def test_get_grandchild_tags_one_level(self) -> None:
        """
        Test basic retrieval of a single level of tags at two level belows the
        "Eukaryota" root tag in the closed taxonomy, using get_filtered_tags().
        """
        result = list(self.taxonomy.get_filtered_tags(depth=1, parent_tag_value="Animalia"))
        common_fields = {"depth": 2, "parent_value": "Animalia", "usage_count": 0, "external_id": None}
        assert result == [
            # These are the Eukaryota tags, in alphabetical order:
            {"value": "Arthropoda", "child_count": 0, **common_fields},
            {"value": "Chordata", "child_count": 1, **common_fields},
            {"value": "Cnidaria", "child_count": 0, **common_fields},
            {"value": "Ctenophora", "child_count": 0, **common_fields},
            {"value": "Gastrotrich", "child_count": 0, **common_fields},
            {"value": "Placozoa", "child_count": 0, **common_fields},
            {"value": "Porifera", "child_count": 0, **common_fields},
        ]

    def test_get_depth_1_search_term(self) -> None:
        """
        Filter the root tags to only those that match a search term
        """
        result = list(self.taxonomy.get_filtered_tags(depth=1, search_term="ARCH"))
        assert result == [
            {
                "value": "Archaea",
                "child_count": 3,
                "depth": 0,
                "usage_count": 0,
                "parent_value": None,
                "external_id": None,
            },
        ]
        # Note that other tags in the taxonomy match "ARCH" but are excluded because of the depth=1 search

    def test_get_depth_1_child_search_term(self) -> None:
        """
        Filter the child tags of "Bacteria" to only those that match a search term
        """
        result = list(self.taxonomy.get_filtered_tags(depth=1, search_term="ARCH", parent_tag_value="Bacteria"))
        assert result == [
            {
                "value": "Archaebacteria",
                "child_count": 0,
                "depth": 1,
                "usage_count": 0,
                "parent_value": "Bacteria",
                "external_id": None,
            },
        ]
        # Note that other tags in the taxonomy match "ARCH" but are excluded because of the depth=1 search

    def test_depth_1_queries(self) -> None:
        """
        Test the number of queries used by get_filtered_tags() with closed
        taxonomies when depth=1. This should be a constant, not O(n).
        """
        with self.assertNumQueries(1):
            self.test_get_root()
        with self.assertNumQueries(1):
            self.test_get_depth_1_search_term()
        # When listing the tags below a specific tag, there is one additional query to load each ancestor tag:
        with self.assertNumQueries(2):
            self.test_get_child_tags_one_level()
        with self.assertNumQueries(2):
            self.test_get_depth_1_child_search_term()
        with self.assertNumQueries(3):
            self.test_get_grandchild_tags_one_level()

    ##################

    @staticmethod
    def _pretty_format_result(result) -> list[str]:
        """
        Format a result to be more human readable.
        """
        return [
            f"{t['depth'] * '  '}{t['value']} ({t['parent_value']}) " +
            f"(used: {t['usage_count']}, children: {t['child_count']})"
            for t in result
        ]

    def test_get_all(self) -> None:
        """
        Test getting all of the tags in the taxonomy, using get_filtered_tags()
        """
        result = self._pretty_format_result(self.taxonomy.get_filtered_tags())
        assert result == [
            "Archaea (None) (used: 0, children: 3)",
            "  DPANN (Archaea) (used: 0, children: 0)",
            "  Euryarchaeida (Archaea) (used: 0, children: 0)",
            "  Proteoarchaeota (Archaea) (used: 0, children: 0)",
            "Bacteria (None) (used: 0, children: 2)",
            "  Archaebacteria (Bacteria) (used: 0, children: 0)",
            "  Eubacteria (Bacteria) (used: 0, children: 0)",
            "Eukaryota (None) (used: 0, children: 5)",
            "  Animalia (Eukaryota) (used: 0, children: 7)",
            "    Arthropoda (Animalia) (used: 0, children: 0)",
            "    Chordata (Animalia) (used: 0, children: 1)",  # note this has a child but the child is not included
            "    Cnidaria (Animalia) (used: 0, children: 0)",
            "    Ctenophora (Animalia) (used: 0, children: 0)",
            "    Gastrotrich (Animalia) (used: 0, children: 0)",
            "    Placozoa (Animalia) (used: 0, children: 0)",
            "    Porifera (Animalia) (used: 0, children: 0)",
            "  Fungi (Eukaryota) (used: 0, children: 0)",
            "  Monera (Eukaryota) (used: 0, children: 0)",
            "  Plantae (Eukaryota) (used: 0, children: 0)",
            "  Protista (Eukaryota) (used: 0, children: 0)",
        ]

    def test_search(self) -> None:
        """
        Search the whole taxonomy (up to max depth) for a given term. Should
        return all tags that match the term as well as their ancestors.
        """
        result = self._pretty_format_result(self.taxonomy.get_filtered_tags(search_term="ARCH"))
        assert result == [
            "Archaea (None) (used: 0, children: 3)",  # Matches the value of this root tag, ARCHaea
            "  Euryarchaeida (Archaea) (used: 0, children: 0)",  # Matches the value of this child tag
            "  Proteoarchaeota (Archaea) (used: 0, children: 0)",  # Matches the value of this child tag
            "Bacteria (None) (used: 0, children: 2)",  # Does not match this tag but matches a descendant:
            "  Archaebacteria (Bacteria) (used: 0, children: 0)",  # Matches the value of this child tag
        ]

    def test_search_2(self) -> None:
        """
        Another search test, that matches a tag deeper in the taxonomy to check
        that all its ancestors are returned by the search.
        """
        result = self._pretty_format_result(self.taxonomy.get_filtered_tags(search_term="chordata"))
        assert result == [
            "Eukaryota (None) (used: 0, children: 5)",
            "  Animalia (Eukaryota) (used: 0, children: 7)",
            "    Chordata (Animalia) (used: 0, children: 1)",  # this is the matching tag.
        ]

    def test_tags_deep(self) -> None:
        """
        Test getting a deep tag in the taxonomy
        """
        result = list(self.taxonomy.get_filtered_tags(parent_tag_value="Chordata"))
        assert result == [
            {
                "value": "Mammalia",
                "parent_value": "Chordata",
                "depth": 3,
                "usage_count": 0,
                "child_count": 0,
                "external_id": None,
            }
        ]

    def test_deep_queries(self) -> None:
        """
        Test the number of queries used by get_filtered_tags() with closed
        taxonomies when depth=None. This should be a constant, not O(n).
        """
        with self.assertNumQueries(1):
            self.test_get_all()
        # Searching below a specific tag requires an additional query to load that tag:
        with self.assertNumQueries(2):
            self.test_tags_deep()
        # Keyword search requires an additional query:
        with self.assertNumQueries(2):
            self.test_search()
        with self.assertNumQueries(2):
            self.test_search_2()

    def test_get_external_id(self) -> None:
        """
        Test that if our tags have external IDs, those external IDs are returned
        """
        self.bacteria.external_id = "bct001"
        self.bacteria.save()
        result = list(self.taxonomy.get_filtered_tags(search_term="Eubacteria"))
        assert result[0]["value"] == "Bacteria"
        assert result[0]["external_id"] == "bct001"

    def test_usage_count(self) -> None:
        """
        Test that the usage count in the results is right
        """
        api.tag_object(object_id="obj01", taxonomy=self.taxonomy, tags=["Bacteria"])
        api.tag_object(object_id="obj02", taxonomy=self.taxonomy, tags=["Bacteria"])
        api.tag_object(object_id="obj03", taxonomy=self.taxonomy, tags=["Bacteria"])
        api.tag_object(object_id="obj04", taxonomy=self.taxonomy, tags=["Eubacteria"])
        # Now the API should reflect these usage counts:
        result = self._pretty_format_result(self.taxonomy.get_filtered_tags(search_term="bacteria"))
        assert result == [
            "Bacteria (None) (used: 3, children: 2)",
            "  Archaebacteria (Bacteria) (used: 0, children: 0)",
            "  Eubacteria (Bacteria) (used: 1, children: 0)",
        ]
        # Same with depth=1, which uses a different query internally:
        result1 = self._pretty_format_result(self.taxonomy.get_filtered_tags(search_term="bacteria", depth=1))
        assert result1 == [
            "Bacteria (None) (used: 3, children: 2)",
        ]


class TestFilteredTagsFreeTextTaxonomy(TestCase):
    """
    Tests for listing/autocompleting/searching for tags in a free text taxonomy.

    Free text taxonomies only return tags that are actually used.
    """

    def setUp(self):
        super().setUp()
        self.taxonomy = Taxonomy.objects.create(allow_free_text=True, name="FreeText")
        # The "triple" tag will be applied to three objects, "double" to two, and "solo" to one:
        api.tag_object(object_id="obj1", taxonomy=self.taxonomy, tags=["triple"])
        api.tag_object(object_id="obj2", taxonomy=self.taxonomy, tags=["triple", "double"])
        api.tag_object(object_id="obj3", taxonomy=self.taxonomy, tags=["triple", "double"])
        api.tag_object(object_id="obj4", taxonomy=self.taxonomy, tags=["solo"])

    def test_get_filtered_tags(self):
        """
        Test basic retrieval of all tags in the taxonomy.
        Without counts included.
        """
        result = list(self.taxonomy.get_filtered_tags(include_counts=False))
        common_fields = {"child_count": 0, "depth": 0, "parent_value": None, "external_id": None}
        assert result == [
            # These should appear in alphabetical order:
            {"value": "double", **common_fields},
            {"value": "solo", **common_fields},
            {"value": "triple", **common_fields},
        ]

    def test_get_filtered_tags_with_count(self):
        """
        Test basic retrieval of all tags in the taxonomy.
        Without counts included.
        """
        result = list(self.taxonomy.get_filtered_tags(include_counts=True))
        common_fields = {"child_count": 0, "depth": 0, "parent_value": None, "external_id": None}
        assert result == [
            # These should appear in alphabetical order:
            {"value": "double", "usage_count": 2, **common_fields},
            {"value": "solo", "usage_count": 1, **common_fields},
            {"value": "triple", "usage_count": 3, **common_fields},
        ]

    def test_get_filtered_tags_num_queries(self):
        """
        Test that the number of queries used by get_filtered_tags() is fixed
        and not O(n) or worse.
        """
        with self.assertNumQueries(1):
            self.test_get_filtered_tags()
        with self.assertNumQueries(1):
            self.test_get_filtered_tags_with_count()

    def test_get_filtered_tags_with_search(self) -> None:
        """
        Test basic retrieval of only matching tags.
        """
        result1 = list(self.taxonomy.get_filtered_tags(search_term="le"))
        common_fields = {"child_count": 0, "depth": 0, "parent_value": None, "external_id": None}
        assert result1 == [
            # These should appear in alphabetical order:
            {"value": "double", "usage_count": 2, **common_fields},
            {"value": "triple", "usage_count": 3, **common_fields},
        ]
        # And it should be case insensitive:
        result2 = list(self.taxonomy.get_filtered_tags(search_term="LE"))
        assert result1 == result2


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
        api.tag_object(self.taxonomy, [self.chordata.value], object_id="case:id:2")

        # Tag with object_id with upper case should not trigger IntegrityError
        api.tag_object(self.taxonomy, [self.chordata.value], object_id="CASE:id:2")

        # Create another ObjectTag with lower case object_id should trigger IntegrityError
        with transaction.atomic():
            with pytest.raises(IntegrityError):
                ObjectTag(
                    object_id="case:id:2",
                    taxonomy=self.taxonomy,
                    tag=self.chordata,
                ).save()

        # Create another ObjectTag with upper case object_id should trigger IntegrityError
        with transaction.atomic():
            with pytest.raises(IntegrityError):
                ObjectTag(
                    object_id="CASE:id:2",
                    taxonomy=self.taxonomy,
                    tag=self.chordata,
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
