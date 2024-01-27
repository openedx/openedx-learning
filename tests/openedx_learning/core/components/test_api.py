"""
Basic tests of the Components API.
"""
from datetime import datetime, timezone

from django.core.exceptions import ObjectDoesNotExist

from openedx_learning.core.components import api as components_api
from openedx_learning.core.contents import api as contents_api
from openedx_learning.core.publishing import api as publishing_api
from openedx_learning.lib.test_utils import TestCase


class TestPerformance(TestCase):
    """
    Performance related tests for Components.

    These are mostly to ensure that when Components are fetched, they're fetched
    with a select_related on the most commonly queried things; draft and
    published version metadata.
    """
    @classmethod
    def setUpTestData(cls) -> None:
        """
        Initialize our base learning package.

        We don't actually need to add content to the ComponentVersions, since
        for this we only care about the metadata on Compnents, their versions,
        and the associated draft/publish status.
        """
        cls.learning_package = publishing_api.create_learning_package(
            "components.TestPerformance",
            "Learning Package for Testing Performance (measured by DB queries)",
        )
        cls.now = datetime(2023, 5, 8, tzinfo=timezone.utc)

    def test_component_num_queries(self) -> None:
        """
        Create a basic component and test that we fetch it back in 1 query.
        """
        component, _version = components_api.create_component_and_version(
            learning_package_id=self.learning_package.id,
            namespace="xblock.v1",
            type="problem",
            local_key="Query Counting",
            title="Querying Counting Problem",
            created=self.now,
            created_by=None,
        )
        publishing_api.publish_all_drafts(
            self.learning_package.pk,
            published_at=self.now
        )

        # We should be fetching all of this with a select-related, so only one
        # database query should happen here.
        with self.assertNumQueries(1):
            component = components_api.get_component(component.pk)
            draft = component.versioning.draft
            published = component.versioning.published
            assert draft.title == published.title

class TestGetComponents(TestCase):
    """
    Test grabbing a queryset of Components.
    """

    @classmethod
    def setUpTestData(cls) -> None:
        """
        Initialize our content data (all our tests are read only).

        We don't actually need to add content to the ComponentVersions, since
        for this we only care about the metadata on Compnents, their versions,
        and the associated draft/publish status.
        """
        cls.learning_package = publishing_api.create_learning_package(
            "components.TestGetComponents",
            "Learning Package for Testing Getting & Filtering Components",
        )
        cls.now = datetime(2023, 5, 8, tzinfo=timezone.utc)

        # Components we're publishing...
        cls.published_problem, _version = components_api.create_component_and_version(
            learning_package_id=cls.learning_package.id,
            namespace="xblock.v2",
            type="problem",
            local_key="published_problem",
            title="Published Problem",
            created=cls.now,
            created_by=None,
        )
        cls.published_html, _version = components_api.create_component_and_version(
            learning_package_id=cls.learning_package.id,
            namespace="xblock.v1",
            type="html",
            local_key="published_html",
            title="Published HTML",
            created=cls.now,
            created_by=None,
        )
        publishing_api.publish_all_drafts(
            cls.learning_package.pk,
            published_at=cls.now
        )

        # Components that exist only as Drafts
        cls.unpublished_problem, _version = components_api.create_component_and_version(
            learning_package_id=cls.learning_package.id,
            namespace="xblock.v2",
            type="problem",
            local_key="unpublished_problem",
            title="Unpublished Problem",
            created=cls.now,
            created_by=None,
        )
        cls.unpublished_html, _version = components_api.create_component_and_version(
            learning_package_id=cls.learning_package.id,
            namespace="xblock.v1",
            type="html",
            local_key="unpublished_html",
            title="Unpublished HTML",
            created=cls.now,
            created_by=None,
        )

        # Component we're putting here to soft delete (this will remove the
        # Draft entry)
        cls.deleted_video, _version =  components_api.create_component_and_version(
            learning_package_id=cls.learning_package.id,
            namespace="xblock.v1",
            type="html",
            local_key="deleted_video",
            title="Deleted Video",
            created=cls.now,
            created_by=None,
        )
        publishing_api.soft_delete_draft(cls.deleted_video.pk)

    def test_no_filters(self):
        """
        Test that we pull back everything, even unpublished or "deleted" items.
        """
        all_components = components_api.get_components(self.learning_package.id)
        assert list(all_components) == [
            self.published_problem,
            self.published_html,
            self.unpublished_problem,
            self.unpublished_html,
            self.deleted_video,
        ]

    def test_draft_filter(self):
        """
        Test the draft flag.
        """
        components_with_draft_version = components_api.get_components(
            self.learning_package.id,
            draft=True,
        )
        assert list(components_with_draft_version) == [
            self.published_problem,
            self.published_html,
            self.unpublished_problem,
            self.unpublished_html
        ]

        components_without_draft_version = components_api.get_components(
            self.learning_package.id,
            draft=False,
        )
        assert list(components_without_draft_version) == [
            self.deleted_video
        ]

    def test_published_filter(self):
        """
        Test the published filter.
        """
        components_with_published_version = components_api.get_components(
            self.learning_package.id,
            published=True,
        )
        assert list(components_with_published_version) == [
            self.published_problem,
            self.published_html,
        ]
        components_without_published_version = components_api.get_components(
            self.learning_package.id,
            published=False,
        )
        assert list(components_without_published_version) == [
            self.unpublished_problem,
            self.unpublished_html,
            self.deleted_video,
        ]

    def test_namespace_filter(self):
        """
        Test the namespace filter.

        Note that xblock.v2 is being used to test filtering, but there's nothing
        that's actually in the system for xblock.v2 at the moment.
        """
        components_with_xblock_v2 = components_api.get_components(
            self.learning_package.id,
            namespace='xblock.v2',
        )
        assert list(components_with_xblock_v2) == [
            self.published_problem,
            self.unpublished_problem,
        ]

    def test_types_filter(self):
        """
        Test the types filter.
        """
        html_and_video_components =  components_api.get_components(
            self.learning_package.id,
            types=['html', 'video']
        )
        assert list(html_and_video_components) == [
            self.published_html,
            self.unpublished_html,
            self.deleted_video,
        ]

    def test_draft_title_filter(self):
        """
        Test the title filter.

        Note that this should be doing a case-insensitive match.
        """
        components = components_api.get_components(
            self.learning_package.id,
            draft_title="PUBLISHED"
        )
        # These all have a draft title with "published" in it somewhere.
        assert list(components) == [
            self.published_problem,
            self.published_html,
            self.unpublished_problem,
            self.unpublished_html,
        ]

    def test_published_title_filter(self):
        """
        Test the title filter.

        Note that this should be doing a case-insensitive match.
        """
        components = components_api.get_components(
            self.learning_package.id,
            published_title="problem"
        )
        # These all have a published title with "problem" in it somewhere,
        # meaning that it won't pick up the components that only exist as
        # drafts.
        assert list(components) == [
            self.published_problem,
        ]


class TestComponentGetAndExists(TestCase):
    """
    Test getting a Component by primary key or key string.
    """
    @classmethod
    def setUpTestData(cls) -> None:
        """
        Initialize our content data (all our tests are read only).

        We don't actually need to add content to the ComponentVersions, since
        for this we only care about the metadata on Compnents, their versions,
        and the associated draft/publish status.
        """
        cls.learning_package = publishing_api.create_learning_package(
            "components.TestComponentGetAndExists",
            "Learning Package for Testing Getting a Component",
        )
        cls.now = datetime(2023, 5, 8, tzinfo=timezone.utc)
        cls.problem = components_api.create_component(
            learning_package_id=cls.learning_package.id,
            namespace='xblock.v1',
            type='problem',
            local_key='my_component',
            created=cls.now,
            created_by=None,
        )
        cls.html = components_api.create_component(
            learning_package_id=cls.learning_package.id,
            namespace='xblock.v1',
            type='html',
            local_key='my_component',
            created=cls.now,
            created_by=None,
        )

    def test_simple_get(self):
        assert components_api.get_component(self.problem.pk) == self.problem
        with self.assertRaises(ObjectDoesNotExist):
            components_api.get_component(-1)

    def test_get_by_key(self):
        assert self.html == components_api.get_component_by_key(
            self.learning_package.id,
            namespace='xblock.v1',
            type='html',
            local_key='my_component',
        )
        with self.assertRaises(ObjectDoesNotExist):
            components_api.get_component_by_key(
                self.learning_package.id,
                namespace='xblock.v1',
                type='video',  # 'video' doesn't match anything we have
                local_key='my_component',
            )

    def test_exists_by_key(self):
        assert components_api.component_exists_by_key(
            self.learning_package.id,
            namespace='xblock.v1',
            type='problem',
            local_key='my_component',
        )
        assert not components_api.component_exists_by_key(
            self.learning_package.id,
            namespace='xblock.v1',
            type='problem',
            local_key='not_my_component',
        )


class TestCreateNewVersions(TestCase):
    """
    Create new ComponentVersions in various ways.
    """

    @classmethod
    def setUpTestData(cls) -> None:
        cls.learning_package = publishing_api.create_learning_package(
            "components.TestCreateNextVersion",
            "Learning Package for Testing Next Version Creation",
        )
        cls.now = datetime(2023, 5, 8, tzinfo=timezone.utc)
        cls.problem = components_api.create_component(
            learning_package_id=cls.learning_package.id,
            namespace='xblock.v1',
            type='problem',
            local_key='my_component',
            created=cls.now,
            created_by=None,
        )

    def test_add(self):
        new_version = components_api.create_component_version(
            self.problem.pk,
            version_num=1,
            title="My Title",
            created=self.now,
            created_by=None,
        )
        new_content, _created = contents_api.get_or_create_raw_content(
            self.learning_package.pk,
            b"This is some data",
            mime_type="text/plain",
            created=self.now,
        )
        components_api.add_content_to_component_version(
            new_version.pk,
            raw_content_id=new_content.pk,
            key="hello.txt",
            learner_downloadable=False,
        )
        # re-fetch from the database to check to see if we wrote it correctly
        new_version = (
            components_api
                .get_component(self.problem.pk)
                .versions
                .get(publishable_entity_version__version_num=1)
        )
        assert (
            new_content ==
            new_version.raw_contents.get(componentversionrawcontent__key="hello.txt")
        )


    def test_multiple_versions(self):
        hello_content, _created = contents_api.get_or_create_text_content_from_bytes(
            learning_package_id=self.learning_package.id,
            data_bytes="Hello World!".encode('utf-8'),
            mime_type="text/plain",
            created=self.now,
        )
        goodbye_content, _created = contents_api.get_or_create_text_content_from_bytes(
            learning_package_id=self.learning_package.id,
            data_bytes="Goodbye World!".encode('utf-8'),
            mime_type="text/plain",
            created=self.now,
        )
        blank_content, _created = contents_api.get_or_create_text_content_from_bytes(
            learning_package_id=self.learning_package.id,
            data_bytes="".encode('utf-8'),
            mime_type="text/plain",
            created=self.now,
        )

        # Two text files, hello.txt and goodbye.txt
        version_1 = components_api.create_next_version(
            self.problem.pk,
            title="Problem Version 1",
            content_to_replace={
                "hello.txt": hello_content.pk,
                "goodbye.txt": goodbye_content.pk,
            },
            created=self.now,
        )
        assert version_1.version_num == 1
        assert version_1.title == "Problem Version 1"
        version_1_contents = list(version_1.raw_contents.all())
        assert len(version_1_contents) == 2
        assert (
            hello_content ==
            version_1.raw_contents
                     .get(componentversionrawcontent__key="hello.txt")
                     .text_content
        )
        assert (
            goodbye_content ==
            version_1.raw_contents
                     .get(componentversionrawcontent__key="goodbye.txt")
                     .text_content
        )

        # This should keep the old value for goodbye.txt, add blank.txt, and set
        # hello.txt to be a new value (blank).
        version_2 = components_api.create_next_version(
            self.problem.pk,
            title="Problem Version 2",
            content_to_replace={
                "hello.txt": blank_content.pk,
                "blank.txt": blank_content.pk,
            },
            created=self.now,
        )
        assert version_2.version_num == 2
        assert version_2.raw_contents.count() == 3
        assert (
            blank_content ==
            version_2
                .raw_contents
                .get(componentversionrawcontent__key="hello.txt")
                .text_content
        )
        assert (
            goodbye_content ==
            version_2
                .raw_contents
                .get(componentversionrawcontent__key="goodbye.txt")
                .text_content
        )
        assert (
            blank_content ==
            version_2
                .raw_contents
                .get(componentversionrawcontent__key="blank.txt")
                .text_content
        )

        # Now we're going to set "hello.txt" back to hello_content, but remove
        # blank.txt, goodbye.txt, and an unknown "nothere.txt".
        version_3 = components_api.create_next_version(
            self.problem.pk,
            title="Problem Version 3",
            content_to_replace={
                "hello.txt": hello_content.pk,
                "blank.txt": None,
                "goodbye.txt": None,
                "nothere.txt": None,  # should not error
            },
            created=self.now,
        )
        assert version_3.version_num == 3
        assert version_3.raw_contents.count() == 1
        assert (
            hello_content ==
            version_3
                .raw_contents
                .get(componentversionrawcontent__key="hello.txt")
                .text_content
        )
