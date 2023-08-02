"""
Tagging API Pagination
"""
from rest_framework.pagination import PageNumberPagination


class TaggingPagination(PageNumberPagination):
    page_size_query_param = "page_size"
    page_size = 100
    max_page_size = 1000
