"""
Test utilities for Learning Core.

The only thing here now is a TestCase class that knows how to clean up the
caching used by the cache module in this package.
"""
import django.test

from .cache import clear_lru_caches


class TestCase(django.test.TestCase):
    """
    Subclass of Django's TestCase that knows how to reset caching we might use.
    """
    def setUp(self) -> None:
        clear_lru_caches()
        super().setUp()

    def tearDown(self) -> None:
        clear_lru_caches()
        super().tearDown()
