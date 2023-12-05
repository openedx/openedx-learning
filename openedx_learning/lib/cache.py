"""
Test-friendly helpers for caching.

LRU caching can be especially helpful for Learning Core data models because so
much of it is immutable, e.g. Media Type lookups. But while these data models
are immutable within a given site, we also want to be able to track and clear
these caches across test runs. Later on, we may also want to inspect them to
make sure they are not growing overly large.
"""
import functools

# List of functions that have our
_lru_cached_fns = []


def lru_cache(*args, **kwargs):
    """
    Thin wrapper over functools.lru_cache that lets us clear all caches later.
    """
    def decorator(fn):
        wrapped_fn = functools.lru_cache(*args, **kwargs)(fn)
        _lru_cached_fns.append(wrapped_fn)
        return wrapped_fn
    return decorator


def clear_lru_caches():
    """
    Clear all LRU caches that use our lru_cache decorator.

    Useful for tests.
    """
    for fn in _lru_cached_fns:
        fn.cache_clear()
