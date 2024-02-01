"""
A few tests to make sure our MediaType lookups are working as expected.
"""
from openedx_learning.core.contents import api as contents_api
from openedx_learning.lib.test_utils import TestCase


class MediaTypeCachingTestCase(TestCase):
    """
    Test that our LRU caching is working as expected.
    """
    def test_media_query_caching(self):
        """Test MediaType queries auto-create and caching."""
        assert contents_api.get_or_create_media_type_id.cache_info().currsize == 0

        mime_type_str = "application/vnd.openedx.xblock.v1.problem+xml"
        media_type_id = contents_api.get_or_create_media_type_id(mime_type_str)

        # Now it should be loaded in the cache
        assert contents_api.get_or_create_media_type_id.cache_info().currsize == 1

        # Second call pulls from cache instead of the database
        with self.assertNumQueries(0):
            # Should also return the same thing it did last time.
            assert media_type_id == contents_api.get_or_create_media_type_id(mime_type_str)

    def test_media_query_caching_reset(self):
        """
        Test that setUp/tearDown reset the get_media_type_id LRU cache.

        This test method's *must* execute after test_media_query_caching to be
        meaningful (they execute in string sort order).
        """
        assert contents_api.get_or_create_media_type_id.cache_info().currsize == 0
