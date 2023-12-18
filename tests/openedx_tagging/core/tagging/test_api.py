"""
Test the tagging APIs
"""
from __future__ import annotations

from typing import Any

import ddt  # type: ignore[import]
import pytest
from django.test import TestCase, override_settings

import openedx_tagging.core.tagging.api as tagging_api
from openedx_tagging.core.tagging.models import ObjectTag, Taxonomy

from .test_models import TestTagTaxonomyMixin, get_tag
from .utils import pretty_format_tags

test_languages = [
    ("az", "Azerbaijani"),
    ("en", "English"),
    ("id", "Indonesian"),
    ("ga", "Irish"),
    ("pl", "Polish"),
    ("qu", "Quechua"),
    ("zu", "Zulu"),
]
# Languages that contains 'ish'
filtered_test_languages = [
    ("en", "English"),
    ("ga", "Irish"),
    ("pl", "Polish"),
]

tag_values_for_autocomplete_test = [
    'Archaea',
    'Archaebacteria',
    'Animalia',
    'Arthropoda',
    'Plantae',
    'Monera',
    'Gastrotrich',
    'Placozoa',
]


@ddt.ddt
class TestApiTagging(TestTagTaxonomyMixin, TestCase):
    """
    Test the Tagging API methods.
    """

    def test_create_taxonomy(self) -> None:  # Note: we must specify '-> None' to opt in to type checking
        params: dict[str, Any] = {
            "name": "Difficulty",
            "description": "This taxonomy contains tags describing the difficulty of an activity",
            "enabled": False,
            "allow_multiple": True,
            "allow_free_text": True,
        }
        taxonomy = tagging_api.create_taxonomy(**params)
        for param, value in params.items():
            assert getattr(taxonomy, param) == value
        assert not taxonomy.system_defined
        assert taxonomy.visible_to_authors

    def test_bad_taxonomy_class(self) -> None:
        with self.assertRaises(ValueError) as exc:
            tagging_api.create_taxonomy(
                name="Bad class",
                taxonomy_class=str,  # type: ignore[arg-type]
            )
        assert "<class 'str'> must be a subclass of Taxonomy" in str(exc.exception)

    def test_get_taxonomy(self) -> None:
        tax1 = tagging_api.get_taxonomy(1)
        assert tax1 == self.taxonomy
        no_tax = tagging_api.get_taxonomy(200)
        assert no_tax is None

    def test_get_taxonomies(self) -> None:
        tax1 = tagging_api.create_taxonomy("Enabled")
        tax2 = tagging_api.create_taxonomy("Disabled", enabled=False)
        tax3 = Taxonomy.objects.get(name="Import Taxonomy Test")
        with self.assertNumQueries(1):
            enabled = list(tagging_api.get_taxonomies())
        assert enabled == [
            tax1,
            self.free_text_taxonomy,
            tax3,
            self.language_taxonomy,
            self.taxonomy,
            self.system_taxonomy,
            self.user_taxonomy,
        ]
        assert str(enabled[0]) == f"<Taxonomy> ({tax1.id}) Enabled"
        assert str(enabled[1]) == f"<Taxonomy> ({self.free_text_taxonomy.id}) Free Text"
        assert str(enabled[2]) == "<Taxonomy> (5) Import Taxonomy Test"
        assert str(enabled[3]) == "<LanguageTaxonomy> (-1) Languages"
        assert str(enabled[4]) == "<Taxonomy> (1) Life on Earth"
        assert str(enabled[5]) == "<SystemDefinedTaxonomy> (4) System defined taxonomy"

        with self.assertNumQueries(1):
            disabled = list(tagging_api.get_taxonomies(enabled=False))
        assert disabled == [tax2]
        assert str(disabled[0]) == f"<Taxonomy> ({tax2.id}) Disabled"

        with self.assertNumQueries(1):
            both = list(tagging_api.get_taxonomies(enabled=None))
        assert both == [
            tax2,
            tax1,
            self.free_text_taxonomy,
            tax3,
            self.language_taxonomy,
            self.taxonomy,
            self.system_taxonomy,
            self.user_taxonomy,
        ]

    def test_get_tags(self) -> None:
        assert pretty_format_tags(tagging_api.get_tags(self.taxonomy), parent=False) == [
            "Archaea (children: 3)",
            "  DPANN (children: 0)",
            "  Euryarchaeida (children: 0)",
            "  Proteoarchaeota (children: 0)",
            "Bacteria (children: 2)",
            "  Archaebacteria (children: 0)",
            "  Eubacteria (children: 0)",
            "Eukaryota (children: 5)",
            "  Animalia (children: 7)",
            "    Arthropoda (children: 0)",
            "    Chordata (children: 1)",  # The child of this is excluded due to depth limit
            "    Cnidaria (children: 0)",
            "    Ctenophora (children: 0)",
            "    Gastrotrich (children: 0)",
            "    Placozoa (children: 0)",
            "    Porifera (children: 0)",
            "  Fungi (children: 0)",
            "  Monera (children: 0)",
            "  Plantae (children: 0)",
            "  Protista (children: 0)",
        ]

    @override_settings(LANGUAGES=test_languages)
    def test_get_tags_system(self) -> None:
        assert pretty_format_tags(tagging_api.get_tags(self.system_taxonomy), parent=False) == [
            "System Tag 1 (children: 0)",
            "System Tag 2 (children: 0)",
            "System Tag 3 (children: 0)",
            "System Tag 4 (children: 0)",
        ]

    def test_get_root_tags(self):
        root_life_on_earth_tags = tagging_api.get_root_tags(self.taxonomy)
        assert pretty_format_tags(root_life_on_earth_tags, parent=False) == [
            'Archaea (children: 3)',
            'Bacteria (children: 2)',
            'Eukaryota (children: 5)',
        ]

    @override_settings(LANGUAGES=test_languages)
    def test_get_root_tags_system(self):
        result = tagging_api.get_root_tags(self.system_taxonomy)
        assert pretty_format_tags(result, parent=False) == [
            'System Tag 1 (children: 0)',
            'System Tag 2 (children: 0)',
            'System Tag 3 (children: 0)',
            'System Tag 4 (children: 0)',
        ]

    @override_settings(LANGUAGES=test_languages)
    def test_get_root_language_tags(self):
        """
        For the language taxonomy, listing and searching tags will only show
        tags that have been used at least once.
        """
        before_langs = [
            tag["external_id"] for tag in
            tagging_api.get_root_tags(self.language_taxonomy)
        ]
        assert before_langs == ["en"]
        # Use a few more tags:
        for _lang_code, lang_value in test_languages:
            tagging_api.tag_object(object_id="foo", taxonomy=self.language_taxonomy, tags=[lang_value])
        # now a search will return matching tags:
        after_langs = [
            tag["external_id"] for tag in
            tagging_api.get_root_tags(self.language_taxonomy)
        ]
        expected_langs = [lang_code for lang_code, _ in test_languages]
        assert after_langs == expected_langs

    def test_search_tags(self) -> None:
        result = tagging_api.search_tags(self.taxonomy, search_term='eU')
        assert pretty_format_tags(result, parent=False) == [
            'Archaea (children: 1)',  # Doesn't match 'eU' but is included because a child is included
            '  Euryarchaeida (children: 0)',
            'Bacteria (children: 1)',  # Doesn't match 'eU' but is included because a child is included
            '  Eubacteria (children: 0)',
            'Eukaryota (children: 0)',
        ]

    @override_settings(LANGUAGES=test_languages)
    def test_search_language_tags(self):
        """
        For the language taxonomy, listing and searching tags will only show
        tags that have been used at least once.
        """
        before_langs = [
            tag["external_id"] for tag in
            tagging_api.search_tags(self.language_taxonomy, search_term='IsH')
        ]
        assert before_langs == ["en"]
        # Use a few more tags:
        for _lang_code, lang_value in test_languages:
            tagging_api.tag_object(object_id="foo", taxonomy=self.language_taxonomy, tags=[lang_value])
        # now a search will return matching tags:
        after_langs = [
            tag["external_id"] for tag in
            tagging_api.search_tags(self.language_taxonomy, search_term='IsH')
        ]
        expected_langs = [lang_code for lang_code, _ in filtered_test_languages]
        assert after_langs == expected_langs

    def test_get_children_tags(self) -> None:
        """
        Test getting the children of a particular tag in a closed taxonomy.
        """
        result1 = tagging_api.get_children_tags(self.taxonomy, "Animalia")
        assert pretty_format_tags(result1, parent=False) == [
            '    Arthropoda (children: 0)',
            '    Chordata (children: 1)',
            # Mammalia is a child of Chordata but excluded here.
            '    Cnidaria (children: 0)',
            '    Ctenophora (children: 0)',
            '    Gastrotrich (children: 0)',
            '    Placozoa (children: 0)',
            '    Porifera (children: 0)',
        ]

    def test_get_children_tags_invalid_taxonomy(self) -> None:
        """
        Calling get_children_tags on free text taxonomies gives an error.
        """
        free_text_taxonomy = Taxonomy.objects.create(allow_free_text=True, name="FreeText")
        tagging_api.tag_object(object_id="obj1", taxonomy=free_text_taxonomy, tags=["some_tag"])
        with self.assertRaises(ValueError) as exc:
            tagging_api.get_children_tags(free_text_taxonomy, "some_tag")
        assert "Cannot specify a parent tag ID for free text taxonomies" in str(exc.exception)

    def test_get_children_tags_no_children(self) -> None:
        """
        Trying to get children of a system tag that has no children yields an empty result:
        """
        assert not list(tagging_api.get_children_tags(self.system_taxonomy, self.system_taxonomy_tag.value))

    def test_resync_object_tags(self) -> None:
        self.taxonomy.allow_multiple = True
        self.taxonomy.save()
        open_taxonomy = Taxonomy.objects.create(name="Freetext Life", allow_free_text=True, allow_multiple=True)

        object_id = "obj1"
        # Create some tags:
        tagging_api.tag_object(self.taxonomy, [self.archaea.value, self.bacteria.value], object_id)  # Regular tags
        tagging_api.tag_object(open_taxonomy, ["foo", "bar"], object_id)  # Free text tags

        # At first, none of these will be deleted:
        assert [(t.value, t.is_deleted) for t in tagging_api.get_object_tags(object_id, include_deleted=True)] == [
            ("bar", False),
            ("foo", False),
            (self.archaea.value, False),
            (self.bacteria.value, False),
        ]

        # Delete "bacteria" from the taxonomy:
        tagging_api.delete_tags_from_taxonomy(self.taxonomy, [self.bacteria.value], with_subtags=True)

        assert [(t.value, t.is_deleted) for t in tagging_api.get_object_tags(object_id, include_deleted=True)] == [
            ("bar", False),
            ("foo", False),
            (self.archaea.value, False),
            (self.bacteria.value, True),  # <--- deleted! But the value is preserved.
        ]

        # Re-syncing the tags at this point does nothing:
        tagging_api.resync_object_tags()

        # Now re-create the tag
        self.bacteria.save()

        # Then re-sync the tags:
        changed = tagging_api.resync_object_tags()
        assert changed == 1

        # Now the tag is not deleted:
        assert [(t.value, t.is_deleted) for t in tagging_api.get_object_tags(object_id, include_deleted=True)] == [
            ("bar", False),
            ("foo", False),
            (self.archaea.value, False),
            (self.bacteria.value, False),  # <--- not deleted
        ]

        # Re-syncing the tags now does nothing:
        changed = tagging_api.resync_object_tags()
        assert changed == 0

    def test_tag_object(self):
        self.taxonomy.allow_multiple = True

        test_tags = [
            [
                self.archaea,
                self.eubacteria,
                self.chordata,
            ],
            [
                self.archaebacteria,
                self.chordata,
            ],
            [
                self.archaea,
                self.archaebacteria,
            ],
        ]

        # Tag and re-tag the object, checking that the expected tags are returned and deleted
        for tag_list in test_tags:
            tagging_api.tag_object(
                self.taxonomy,
                [t.value for t in tag_list],
                "biology101",
            )
            # Ensure the expected number of tags exist in the database
            object_tags = tagging_api.get_object_tags("biology101", taxonomy_id=self.taxonomy.id)
            # And the expected number of tags were returned
            assert len(object_tags) == len(tag_list)
            for index, object_tag in enumerate(object_tags):
                object_tag.full_clean()  # Should not raise any ValidationErrors
                assert object_tag.tag_id == tag_list[index].id
                assert object_tag._value == tag_list[index].value  # pylint: disable=protected-access
                assert object_tag.taxonomy == self.taxonomy
                assert object_tag.name == self.taxonomy.name
                assert object_tag.object_id == "biology101"

    def test_tag_object_free_text(self) -> None:
        """
        Test tagging an object using a free text taxonomy
        """
        tagging_api.tag_object(
            object_id="biology101",
            taxonomy=self.free_text_taxonomy,
            tags=["Eukaryota Xenomorph"],
        )
        object_tags = tagging_api.get_object_tags("biology101")
        assert len(object_tags) == 1
        object_tag = object_tags[0]
        object_tag.full_clean()  # Should not raise any ValidationErrors
        assert object_tag.taxonomy == self.free_text_taxonomy
        assert object_tag.name == self.free_text_taxonomy.name
        assert object_tag._value == "Eukaryota Xenomorph"  # pylint: disable=protected-access
        assert object_tag.get_lineage() == ["Eukaryota Xenomorph"]
        assert object_tag.object_id == "biology101"

    def test_tag_object_no_multiple(self):
        with pytest.raises(ValueError) as excinfo:
            tagging_api.tag_object(self.taxonomy, ["A", "B"], "biology101")
        assert "only allows one tag per object" in str(excinfo.value)

    def test_tag_object_invalid_tag(self):
        with pytest.raises(tagging_api.TagDoesNotExist) as excinfo:
            tagging_api.tag_object(self.taxonomy, ["Eukaryota Xenomorph"], "biology101")
        assert "Tag matching query does not exist." in str(excinfo.value)

    def test_tag_object_string(self) -> None:
        with self.assertRaises(ValueError) as exc:
            tagging_api.tag_object(
                self.taxonomy,
                'string',  # type: ignore[arg-type]
                "biology101",
            )
        assert "Tags must be a list, not str." in str(exc.exception)

    def test_tag_object_integer(self) -> None:
        with self.assertRaises(ValueError) as exc:
            tagging_api.tag_object(
                self.taxonomy,
                1,  # type: ignore[arg-type]
                "biology101",
            )
        assert "Tags must be a list, not int." in str(exc.exception)

    def test_tag_object_same_id(self) -> None:
        # Tag the object with the same tag twice
        tagging_api.tag_object(
            self.taxonomy,
            [self.eubacteria.value],
            "biology101",
        )
        tagging_api.tag_object(
            self.taxonomy,
            [self.eubacteria.value],
            "biology101",
        )
        object_tags = tagging_api.get_object_tags("biology101")
        assert len(object_tags) == 1
        assert str(object_tags[0]) == "<ObjectTag> biology101: Life on Earth=Eubacteria"

    def test_tag_object_same_value(self) -> None:
        # Tag the object with the same value twice
        tagging_api.tag_object(
            self.taxonomy,
            [self.eubacteria.value, self.eubacteria.value],
            "biology101",
        )
        object_tags = tagging_api.get_object_tags("biology101")
        assert len(object_tags) == 1
        assert str(object_tags[0]) == "<ObjectTag> biology101: Life on Earth=Eubacteria"

    def test_tag_object_same_value_multiple_free(self) -> None:
        self.taxonomy.allow_multiple = True
        self.taxonomy.allow_free_text = True
        self.taxonomy.save()
        # Tag the object with the same value twice
        tagging_api.tag_object(
            self.taxonomy,
            ["tag1", "tag1"],
            "biology101",
        )
        object_tags = tagging_api.get_object_tags("biology101")
        assert len(object_tags) == 1

    def test_tag_object_case_id(self) -> None:
        """
        Test that the case of the object_id is preserved.
        """
        tagging_api.tag_object(
            self.taxonomy,
            [self.eubacteria.value],
            "biology101",
        )

        tagging_api.tag_object(
            self.taxonomy,
            [self.archaea.value],
            "BIOLOGY101",
        )

        object_tags_lower = tagging_api.get_object_tags(
            taxonomy_id=self.taxonomy.pk,
            object_id="biology101",
        )

        assert len(object_tags_lower) == 1
        assert object_tags_lower[0].tag_id == self.eubacteria.id

        object_tags_upper = tagging_api.get_object_tags(
            taxonomy_id=self.taxonomy.pk,
            object_id="BIOLOGY101",
        )

        assert len(object_tags_upper) == 1
        assert object_tags_upper[0].tag_id == self.archaea.id

    @override_settings(LANGUAGES=test_languages)
    def test_tag_object_language_taxonomy(self) -> None:
        tags_list = [
            ["Azerbaijani"],
            ["English"],
        ]

        for tags in tags_list:
            tagging_api.tag_object(self.language_taxonomy, tags, "biology101")

            # Ensure the expected number of tags exist in the database
            object_tags = tagging_api.get_object_tags("biology101")
            # And the expected number of tags were returned
            assert len(object_tags) == len(tags)
            for index, object_tag in enumerate(object_tags):
                object_tag.full_clean()  # Check full model validation
                assert object_tag.value == tags[index]
                assert not object_tag.is_deleted
                assert object_tag.taxonomy == self.language_taxonomy
                assert object_tag.name == self.language_taxonomy.name
                assert object_tag.object_id == "biology101"

    @override_settings(LANGUAGES=test_languages)
    def test_tag_object_language_taxonomy_invalid(self) -> None:
        with self.assertRaises(tagging_api.TagDoesNotExist):
            tagging_api.tag_object(
                self.language_taxonomy,
                ["Spanish"],
                "biology101",
            )

    def test_tag_object_model_system_taxonomy(self) -> None:
        users = [
            self.user_1,
            self.user_2,
        ]

        for user in users:
            tags = [user.username]
            tagging_api.tag_object(self.user_taxonomy, tags, "biology101")

            # Ensure the expected number of tags exist in the database
            object_tags = tagging_api.get_object_tags("biology101")
            # And the expected number of tags were returned
            assert len(object_tags) == len(tags)
            for object_tag in object_tags:
                object_tag.full_clean()  # Check full model validation
                assert object_tag.tag
                assert object_tag.tag.external_id == str(user.id)
                assert object_tag.tag.value == user.username
                assert not object_tag.is_deleted
                assert object_tag.taxonomy == self.user_taxonomy
                assert object_tag.name == self.user_taxonomy.name
                assert object_tag.object_id == "biology101"

    def test_tag_object_model_system_taxonomy_invalid(self) -> None:
        tags = ["Invalid id"]
        with self.assertRaises(tagging_api.TagDoesNotExist):
            tagging_api.tag_object(self.user_taxonomy, tags, "biology101")

    def test_tag_object_limit(self) -> None:
        """
        Test that the tagging limit is enforced.
        """
        dummy_taxonomies = self.create_100_taxonomies()
        # The user can add up to 100 tags to a object
        for taxonomy in dummy_taxonomies:
            tagging_api.tag_object(
                taxonomy,
                ["Dummy Tag"],
                "object_1",
            )

        # Adding a new tag should fail
        with self.assertRaises(ValueError) as exc:
            tagging_api.tag_object(
                self.taxonomy,
                ["Eubacteria"],
                "object_1",
            )
        assert exc.exception
        assert "Cannot add more than 100 tags to" in str(exc.exception)

        # Updating existing tags should work
        for taxonomy in dummy_taxonomies:
            tagging_api.tag_object(
                taxonomy,
                ["New Dummy Tag"],
                "object_1",
            )

        # Updating existing tags adding a new one should fail
        for taxonomy in dummy_taxonomies:
            with self.assertRaises(ValueError) as exc:
                tagging_api.tag_object(
                    taxonomy,
                    ["New Dummy Tag 1", "New Dummy Tag 2"],
                    "object_1",
                )
            assert exc.exception
            assert "Cannot add more than 100 tags to" in str(exc.exception)

    def test_get_object_tags_deleted_disabled(self) -> None:
        """
        Test that get_object_tags doesn't return tags from disabled taxonomies
        or tags that have been deleted or taxonomies that have been deleted.
        """
        obj_id = "object_id1"
        self.taxonomy.allow_multiple = True
        self.taxonomy.save()
        disabled_taxonomy = tagging_api.create_taxonomy("Disabled Taxonomy", allow_free_text=True)
        tagging_api.tag_object(object_id=obj_id, taxonomy=self.taxonomy, tags=["DPANN", "Chordata"])
        tagging_api.tag_object(object_id=obj_id, taxonomy=self.language_taxonomy, tags=["English"])
        tagging_api.tag_object(object_id=obj_id, taxonomy=self.free_text_taxonomy, tags=["has a notochord"])
        tagging_api.tag_object(object_id=obj_id, taxonomy=disabled_taxonomy, tags=["disabled tag"])

        def get_object_tags():
            return [f"{ot.name}: {'>'.join(ot.get_lineage())}" for ot in tagging_api.get_object_tags(obj_id)]

        # Before deleting/disabling:
        assert get_object_tags() == [
            "Disabled Taxonomy: disabled tag",
            "Free Text: has a notochord",
            "Languages: English",
            "Life on Earth: Archaea>DPANN",
            "Life on Earth: Eukaryota>Animalia>Chordata",
        ]

        # Now delete and disable things:
        disabled_taxonomy.enabled = False
        disabled_taxonomy.save()
        self.free_text_taxonomy.delete()
        tagging_api.delete_tags_from_taxonomy(self.taxonomy, ["DPANN"], with_subtags=False)

        # Now retrieve the tags again:
        assert get_object_tags() == [
            "Languages: English",
            "Life on Earth: Eukaryota>Animalia>Chordata",
        ]

    @ddt.data(
        ("ChA", [
            "Archaea (used: 1, children: 2)",
            "  Euryarchaeida (used: 0, children: 0)",
            "  Proteoarchaeota (used: 0, children: 0)",
            "Bacteria (used: 0, children: 1)",  # does not contain "cha" but a child does
            "  Archaebacteria (used: 1, children: 0)",
        ]),
        ("ar", [
            "Archaea (used: 1, children: 2)",
            "  Euryarchaeida (used: 0, children: 0)",
            "  Proteoarchaeota (used: 0, children: 0)",
            "Bacteria (used: 0, children: 1)",  # does not contain "ar" but a child does
            "  Archaebacteria (used: 1, children: 0)",
            "Eukaryota (used: 0, children: 1)",
            "  Animalia (used: 1, children: 2)",  # does not contain "ar" but a child does
            "    Arthropoda (used: 1, children: 0)",
            "    Cnidaria (used: 0, children: 0)",
        ]),
        ("aE", [
            "Archaea (used: 1, children: 2)",
            "  Euryarchaeida (used: 0, children: 0)",
            "  Proteoarchaeota (used: 0, children: 0)",
            "Bacteria (used: 0, children: 1)",  # does not contain "ae" but a child does
            "  Archaebacteria (used: 1, children: 0)",
            "Eukaryota (used: 0, children: 1)",  # does not contain "ae" but a child does
            "  Plantae (used: 1, children: 0)",
        ]),
        ("a", [
            "Archaea (used: 1, children: 3)",
            "  DPANN (used: 0, children: 0)",
            "  Euryarchaeida (used: 0, children: 0)",
            "  Proteoarchaeota (used: 0, children: 0)",
            "Bacteria (used: 0, children: 2)",
            "  Archaebacteria (used: 1, children: 0)",
            "  Eubacteria (used: 0, children: 0)",
            "Eukaryota (used: 0, children: 4)",
            "  Animalia (used: 1, children: 7)",
            "    Arthropoda (used: 1, children: 0)",
            "    Chordata (used: 0, children: 0)",  # <<< Chordata has a matching child but we only support searching
            "    Cnidaria (used: 0, children: 0)",  # 3 levels deep at once for now.
            "    Ctenophora (used: 0, children: 0)",
            "    Gastrotrich (used: 1, children: 0)",
            "    Placozoa (used: 1, children: 0)",
            "    Porifera (used: 0, children: 0)",
            "  Monera (used: 1, children: 0)",
            "  Plantae (used: 1, children: 0)",
            "  Protista (used: 0, children: 0)",
        ]),
    )
    @ddt.unpack
    def test_autocomplete_tags_closed(self, search: str, expected: list[str]) -> None:
        """
        Test autocompletion/search for tags using a closed taxonomy.
        """
        closed_taxonomy = self.taxonomy
        for index, value in enumerate(tag_values_for_autocomplete_test):
            # Creating ObjectTags for closed taxonomy
            tag = get_tag(value)
            ObjectTag(
                object_id=f"object_id_{index}",
                taxonomy=closed_taxonomy,
                tag=tag,
                _value=value,
            ).save()

        result = tagging_api.search_tags(closed_taxonomy, search, include_counts=True)
        assert pretty_format_tags(result, parent=False) == expected

    def test_autocomplete_tags_closed_omit_object(self) -> None:
        """
        Test autocomplete search that omits the tags from a specific object
        """
        object_id = 'new_object_id'
        tagging_api.tag_object(object_id=object_id, taxonomy=self.taxonomy, tags=["Archaebacteria"])
        result = tagging_api.search_tags(self.taxonomy, "ChA", exclude_object_id=object_id)
        assert pretty_format_tags(result, parent=False) == [
            "Archaea (children: 2)",
            "  Euryarchaeida (children: 0)",
            "  Proteoarchaeota (children: 0)",
            # These results are no longer included because of exclude_object_id:
            # "Bacteria (children: 1)",  # does not contain "cha" but a child does
            # "  Archaebacteria (children: 0)",
        ]

    def test_get_object_tag_counts(self) -> None:
        """
        Basic test of get_object_tag_counts
        """
        obj1 = "object_id1"
        obj2 = "object_id2"
        other = "other_object"
        # Give each object 1-2 tags:
        tagging_api.tag_object(object_id=obj1, taxonomy=self.taxonomy, tags=["DPANN"])
        tagging_api.tag_object(object_id=obj2, taxonomy=self.taxonomy, tags=["Chordata"])
        tagging_api.tag_object(object_id=obj2, taxonomy=self.free_text_taxonomy, tags=["has a notochord"])
        tagging_api.tag_object(object_id=other, taxonomy=self.free_text_taxonomy, tags=["other"])

        assert tagging_api.get_object_tag_counts(obj1) == {obj1: 1}
        assert tagging_api.get_object_tag_counts(obj2) == {obj2: 2}
        assert tagging_api.get_object_tag_counts(f"{obj1},{obj2}") == {obj1: 1, obj2: 2}
        assert tagging_api.get_object_tag_counts("object_*") == {obj1: 1, obj2: 2}

    def test_get_object_tag_counts_implicit(self) -> None:
        """
        Basic test of get_object_tag_counts, including implicit (parent) tags

        Note that:
            - "DPANN" is "Archaea > DPANN" (2 tags, 1 implicit), and
            - "Chordata" is "Eukaryota > Animalia > Chordata" (3 tags, 2 implicit)
            - "Arthropoda" is "Eukaryota > Animalia > Arthropoda" (same)
        """
        self.taxonomy.allow_multiple = True
        self.taxonomy.save()
        obj1, obj2, obj3 = "object_id1", "object_id2", "object_id3"
        other = "other_object"
        # Give each object 1-2 tags:
        tagging_api.tag_object(object_id=obj1, taxonomy=self.taxonomy, tags=["DPANN"])
        tagging_api.tag_object(object_id=obj2, taxonomy=self.taxonomy, tags=["Chordata"])
        tagging_api.tag_object(object_id=obj2, taxonomy=self.free_text_taxonomy, tags=["has a notochord"])
        tagging_api.tag_object(object_id=obj3, taxonomy=self.taxonomy, tags=["Chordata", "Arthropoda"])
        tagging_api.tag_object(object_id=other, taxonomy=self.free_text_taxonomy, tags=["other"])

        assert tagging_api.get_object_tag_counts(obj1, count_implicit=True) == {obj1: 2}
        assert tagging_api.get_object_tag_counts(obj2, count_implicit=True) == {obj2: 4}
        assert tagging_api.get_object_tag_counts(f"{obj1},{obj2}", count_implicit=True) == {obj1: 2, obj2: 4}
        assert tagging_api.get_object_tag_counts("object_*", count_implicit=True) == {
            obj1: 2,
            obj2: 4,
            obj3: 4,  # obj3 has 2 explicit tags and 2 implicit tags (not 4 because the implicit tags are the same)
        }
        assert tagging_api.get_object_tag_counts(other, count_implicit=True) == {other: 1}

    def test_get_object_tag_counts_deleted_disabled(self) -> None:
        """
        Test that get_object_tag_counts doesn't "count" disabled taxonomies or
        deleted tags.
        """
        obj1 = "object_id1"
        obj2 = "object_id2"
        # Give each object 2 tags:
        tagging_api.tag_object(object_id=obj1, taxonomy=self.taxonomy, tags=["DPANN"])
        tagging_api.tag_object(object_id=obj1, taxonomy=self.language_taxonomy, tags=["English"])
        tagging_api.tag_object(object_id=obj2, taxonomy=self.taxonomy, tags=["Chordata"])
        tagging_api.tag_object(object_id=obj2, taxonomy=self.free_text_taxonomy, tags=["has a notochord"])

        # Before we delete tags / disable taxonomies, the counts are two each:
        assert tagging_api.get_object_tag_counts("object_*") == {obj1: 2, obj2: 2}
        # Delete the "DPANN" tag from self.taxonomy:
        tagging_api.delete_tags_from_taxonomy(self.taxonomy, tags=["DPANN"], with_subtags=False)
        assert tagging_api.get_object_tag_counts("object_*") == {obj1: 1, obj2: 2}
        # Disable the free text taxonomy:
        self.free_text_taxonomy.enabled = False
        self.free_text_taxonomy.save()
        assert tagging_api.get_object_tag_counts("object_*") == {obj1: 1, obj2: 1}
        # Also check the result with count_implicit:
        # "English" has no implicit tags but "Chordata" has two, so we expect these totals:
        assert tagging_api.get_object_tag_counts("object_*", count_implicit=True) == {obj1: 1, obj2: 3}

        # But, by the way, if we re-enable the taxonomy and restore the tag, the counts return:
        self.free_text_taxonomy.enabled = True
        self.free_text_taxonomy.save()
        assert tagging_api.get_object_tag_counts("object_*") == {obj1: 1, obj2: 2}
        tagging_api.add_tag_to_taxonomy(self.taxonomy, "DPANN", parent_tag_value="Archaea")
        assert tagging_api.get_object_tag_counts("object_*") == {obj1: 2, obj2: 2}
