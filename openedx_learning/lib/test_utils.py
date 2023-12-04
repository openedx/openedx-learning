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
