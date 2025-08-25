"""
Test cases for the slugify_hashed_filename function.

These tests ensure consistent and predictable behavior when
generating slugified, hash-based filenames.
"""

from openedx_learning.apps.authoring.backup_restore.zipper import slugify_hashed_filename
from openedx_learning.lib.test_utils import TestCase


class SlugHashTestCase(TestCase):
    """
    Test the slugify_hashed_filename function.
    """

    def test_slugify_hashed_filename(self):
        # Test the slugify_hashed_filename function
        self.assertEqual(slugify_hashed_filename("my_example"), "my_example_880989")

    def test_slugify_hashed_filename_special_chars(self):
        # Test the slugify_hashed_filename function with special characters
        self.assertEqual(slugify_hashed_filename("my@ex#ample!"), "myexample_3366b5")

    def test_slugify_hashed_filename_long_string(self):
        # Test the slugify_hashed_filename function with a long string
        long_string = "a" * 100
        self.assertEqual(slugify_hashed_filename(long_string), f"{long_string}_4e84b3")

    def test_slugify_hashed_filename_case_insensitivity(self):
        # Test the slugify_hashed_filename function for case insensitivity
        self.assertEqual(slugify_hashed_filename("My_Example"), "my_example_4f859c")
        self.assertEqual(slugify_hashed_filename("MY_EXAMPLE"), "my_example_49be65")
        self.assertEqual(slugify_hashed_filename("my_example"), "my_example_880989")
        self.assertEqual(slugify_hashed_filename("mY_eXamPle"), "my_example_d28c02")
        self.assertEqual(slugify_hashed_filename("My_ExAmPlE"), "my_example_79232e")
        self.assertEqual(slugify_hashed_filename("mY_EXAMPLE"), "my_example_b91dc0")
