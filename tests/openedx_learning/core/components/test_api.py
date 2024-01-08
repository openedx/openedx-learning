"""
Basic tests of the Components API.
"""
from datetime import datetime, timezone

from openedx_learning.core.components import api as components_api
from openedx_learning.core.publishing import api as publishing_api
from openedx_learning.lib.test_utils import TestCase


class TestPerformance(TestCase):
    """
    Performance related tests to make sure we don't get n + 1 queries.
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
        all_components = components_api.get_components(self.learning_package.id).all()
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
        ).all()
        assert list(components_with_draft_version) == [
            self.published_problem,
            self.published_html,
            self.unpublished_problem,
            self.unpublished_html
        ]

        components_without_draft_version = components_api.get_components(
            self.learning_package.id,
            draft=False,
        ).all()
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
        ).all()
        assert list(components_with_published_version) == [
            self.published_problem,
            self.published_html,
        ]
        components_without_published_version = components_api.get_components(
            self.learning_package.id,
            published=False,
        ).all()
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
        ).all()
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
        ).all()
        assert list(html_and_video_components) == [
            self.published_html,
            self.unpublished_html,
            self.deleted_video,
        ]

    def test_title_filter(self):
        """
        Test the title filter.

        Note that this should be doing a case-insensitive match.
        """
        components = components_api.get_components(
            self.learning_package.id,
            title="PUBLISHED"
        ).all()
        # These all have a title with "published" in it somewhere.
        assert list(components) == [
            self.published_problem,
            self.published_html,
            self.unpublished_problem,
            self.unpublished_html,
        ]
