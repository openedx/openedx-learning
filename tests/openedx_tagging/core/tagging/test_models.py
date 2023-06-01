from django.test.testcases import TestCase

from openedx_tagging.core.tagging.models import TagContent


class TestModelTagContent(TestCase):
    """
    Test that TagContent objects can be created and edited.
    """

    def test_tag_content(self):
        content_tag = TagContent.objects.create(
            content_id="lb:Axim:video:abc",
            name="Subject areas",
            value="Chemistry",
        )
        assert content_tag.id
