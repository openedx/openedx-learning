"""
Paginators uses by the REST API
"""

from edx_rest_framework_extensions.paginators import DefaultPagination  # type: ignore[import]

# From this point, the tags begin to be paginated
MAX_FULL_DEPTH_THRESHOLD = 10_000


class TagsPagination(DefaultPagination):
    """
    Custom pagination configuration for taxonomies
    with a large number of tags. Used on the get tags API view.
    """
    page_size = 10
    max_page_size = 300


class DisabledTagsPagination(DefaultPagination):
    """
    Custom pagination configuration for taxonomies
    with a small number of tags. Used on the get tags API view

    This class allows to bring all the tags of the taxonomy.
    It should be used if the number of tags within
    the taxonomy does not exceed `TAGS_THRESHOLD`.
    """
    page_size = MAX_FULL_DEPTH_THRESHOLD
    max_page_size = MAX_FULL_DEPTH_THRESHOLD + 1
