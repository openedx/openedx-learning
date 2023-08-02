"""Tests tagging rules-based permissions"""

import ddt
from django.contrib.auth import get_user_model
from django.test.testcases import TestCase

from openedx_tagging.core.tagging.models import ObjectTag, Tag

from .test_models import TestTagTaxonomyMixin

User = get_user_model()


@ddt.ddt
class TestRulesTagging(TestTagTaxonomyMixin, TestCase):
    """
    Tests that the expected rules have been applied to the tagging models.
    """

    def setUp(self):
        super().setUp()
        self.superuser = User.objects.create(
            username="superuser",
            email="superuser@example.com",
            is_superuser=True,
        )
        self.staff = User.objects.create(
            username="staff",
            email="staff@example.com",
            is_staff=True,
        )
        self.learner = User.objects.create(
            username="learner",
            email="learner@example.com",
        )
        self.object_tag = ObjectTag.objects.create(
            taxonomy=self.taxonomy,
            tag=self.bacteria,
        )
        self.object_tag.save()

    # Taxonomy

    @ddt.data(
        "oel_tagging.add_taxonomy",
        "oel_tagging.change_taxonomy",
    )
    def test_add_change_taxonomy(self, perm):
        """Taxonomy administrators can create or modify any Taxonomy"""
        assert self.superuser.has_perm(perm)
        assert self.superuser.has_perm(perm, self.taxonomy)
        assert self.staff.has_perm(perm)
        assert self.staff.has_perm(perm, self.taxonomy)
        assert not self.learner.has_perm(perm)
        assert not self.learner.has_perm(perm, self.taxonomy)

    @ddt.data(
        "oel_tagging.add_taxonomy",
        "oel_tagging.change_taxonomy",
        "oel_tagging.delete_taxonomy",
    )
    def test_system_taxonomy(self, perm):
        """Taxonomy administrators cannot edit system taxonomies"""
        assert self.superuser.has_perm(perm, self.system_taxonomy)
        assert not self.staff.has_perm(perm, self.system_taxonomy)
        assert not self.learner.has_perm(perm, self.system_taxonomy)

    @ddt.data(
        True,
        False,
    )
    def test_delete_taxonomy(self, enabled):
        """Taxonomy administrators can delete any Taxonomy"""
        self.taxonomy.enabled = enabled
        assert self.superuser.has_perm("oel_tagging.delete_taxonomy")
        assert self.superuser.has_perm("oel_tagging.delete_taxonomy", self.taxonomy)
        assert self.staff.has_perm("oel_tagging.delete_taxonomy")
        assert self.staff.has_perm("oel_tagging.delete_taxonomy", self.taxonomy)
        assert not self.learner.has_perm("oel_tagging.delete_taxonomy")
        assert not self.learner.has_perm("oel_tagging.delete_taxonomy", self.taxonomy)

    @ddt.data(
        True,
        False,
    )
    def test_view_taxonomy_enabled(self, enabled):
        """Anyone can see enabled taxonomies, but learners cannot see disabled taxonomies"""
        self.taxonomy.enabled = enabled
        assert self.superuser.has_perm("oel_tagging.view_taxonomy")
        assert self.superuser.has_perm("oel_tagging.view_taxonomy", self.taxonomy)
        assert self.staff.has_perm("oel_tagging.view_taxonomy")
        assert self.staff.has_perm("oel_tagging.view_taxonomy", self.taxonomy)
        assert self.learner.has_perm("oel_tagging.view_taxonomy")
        assert (
            self.learner.has_perm("oel_tagging.view_taxonomy", self.taxonomy) == enabled
        )

    # Tag

    @ddt.data(
        "oel_tagging.add_tag",
        "oel_tagging.change_tag",
    )
    def test_add_change_tag(self, perm):
        """Taxonomy administrators can modify tags on non-free-text taxonomies"""
        assert self.superuser.has_perm(perm)
        assert self.superuser.has_perm(perm, self.bacteria)
        assert self.staff.has_perm(perm)
        assert self.staff.has_perm(perm, self.bacteria)
        assert not self.learner.has_perm(perm)
        assert not self.learner.has_perm(perm, self.bacteria)

    @ddt.data(
        "oel_tagging.add_tag",
        "oel_tagging.change_tag",
    )
    def test_tag_free_text_taxonomy(self, perm):
        """Taxonomy administrators cannot modify tags on a free-text Taxonomy"""
        self.taxonomy.allow_free_text = True
        self.taxonomy.save()
        assert self.superuser.has_perm(perm, self.bacteria)
        assert not self.staff.has_perm(perm, self.bacteria)
        assert not self.learner.has_perm(perm, self.bacteria)

    @ddt.data(
        "oel_tagging.add_tag",
        "oel_tagging.change_tag",
        "oel_tagging.delete_tag",
    )
    def test_tag_no_taxonomy(self, perm):
        """Taxonomy administrators can modify any Tag, even those with no Taxonnmy."""
        tag = Tag()
        assert self.superuser.has_perm(perm, tag)
        assert self.staff.has_perm(perm, tag)
        assert not self.learner.has_perm(perm, tag)

    @ddt.data(
        True,
        False,
    )
    def test_delete_tag(self, allow_free_text):
        """Taxonomy administrators can delete any Tag, even those associated with a free-text Taxonomy."""
        self.taxonomy.allow_free_text = allow_free_text
        self.taxonomy.save()
        assert self.superuser.has_perm("oel_tagging.delete_tag")
        assert self.superuser.has_perm("oel_tagging.delete_tag", self.bacteria)
        assert self.staff.has_perm("oel_tagging.delete_tag")
        assert self.staff.has_perm("oel_tagging.delete_tag", self.bacteria)
        assert not self.learner.has_perm("oel_tagging.delete_tag")
        assert not self.learner.has_perm("oel_tagging.delete_tag", self.bacteria)

    def test_view_tag(self):
        """Anyone can view any Tag"""
        assert self.superuser.has_perm("oel_tagging.view_tag")
        assert self.superuser.has_perm("oel_tagging.view_tag", self.bacteria)
        assert self.staff.has_perm("oel_tagging.view_tag")
        assert self.staff.has_perm("oel_tagging.view_tag", self.bacteria)
        assert self.learner.has_perm("oel_tagging.view_tag")
        assert self.learner.has_perm("oel_tagging.view_tag", self.bacteria)

    # ObjectTag

    @ddt.data(
        "oel_tagging.add_objecttag",
        "oel_tagging.change_objecttag",
    )
    def test_add_change_object_tag(self, perm):
        """Taxonomy administrators can create/edit an ObjectTag with an enabled Taxonomy"""
        assert self.superuser.has_perm(perm)
        assert self.superuser.has_perm(perm, self.object_tag)
        assert self.staff.has_perm(perm)
        assert self.staff.has_perm(perm, self.object_tag)
        assert not self.learner.has_perm(perm)
        assert not self.learner.has_perm(perm, self.object_tag)

    @ddt.data(
        "oel_tagging.add_objecttag",
        "oel_tagging.change_objecttag",
    )
    def test_object_tag_disabled_taxonomy(self, perm):
        """Taxonomy administrators cannot create/edit an ObjectTag with a disabled Taxonomy"""
        self.taxonomy.enabled = False
        self.taxonomy.save()
        assert self.superuser.has_perm(perm, self.object_tag)
        assert not self.staff.has_perm(perm, self.object_tag)
        assert not self.learner.has_perm(perm, self.object_tag)

    @ddt.data(
        True,
        False,
    )
    def test_delete_objecttag(self, enabled):
        """Taxonomy administrators can delete any ObjectTag, even those associated with a disabled Taxonomy."""
        self.taxonomy.enabled = enabled
        self.taxonomy.save()
        assert self.superuser.has_perm("oel_tagging.delete_objecttag")
        assert self.superuser.has_perm("oel_tagging.delete_objecttag", self.object_tag)
        assert self.staff.has_perm("oel_tagging.delete_objecttag")
        assert self.staff.has_perm("oel_tagging.delete_objecttag", self.object_tag)
        assert not self.learner.has_perm("oel_tagging.delete_objecttag")
        assert not self.learner.has_perm(
            "oel_tagging.delete_objecttag", self.object_tag
        )

    @ddt.data(
        "oel_tagging.add_objecttag",
        "oel_tagging.change_objecttag",
        "oel_tagging.delete_objecttag",
    )
    def test_object_tag_no_taxonomy(self, perm):
        """Taxonomy administrators can modify an ObjectTag with no Taxonomy"""
        object_tag = ObjectTag()
        assert self.superuser.has_perm(perm, object_tag)
        assert self.staff.has_perm(perm, object_tag)
        assert not self.learner.has_perm(perm, object_tag)

    def test_view_object_tag(self):
        """Anyone can view any ObjectTag"""
        assert self.superuser.has_perm("oel_tagging.view_objecttag")
        assert self.superuser.has_perm("oel_tagging.view_objecttag", self.object_tag)
        assert self.staff.has_perm("oel_tagging.view_objecttag")
        assert self.staff.has_perm("oel_tagging.view_objecttag", self.object_tag)
        assert self.learner.has_perm("oel_tagging.view_objecttag")
        assert self.learner.has_perm("oel_tagging.view_objecttag", self.object_tag)
