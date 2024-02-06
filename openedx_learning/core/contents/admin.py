"""
Django admin for contents models
"""
from django.contrib import admin
from django.utils.html import format_html

from openedx_learning.lib.admin_utils import ReadOnlyModelAdmin

from .models import Content


@admin.register(Content)
class ContentAdmin(ReadOnlyModelAdmin):
    """
    Django admin for Content model
    """
    list_display = [
        "hash_digest",
        "file_link",
        "learning_package",
        "media_type",
        "size",
        "created",
        "has_file",
    ]
    fields = [
        "learning_package",
        "hash_digest",
        "media_type",
        "size",
        "created",
        "file_link",
        "text_preview",
        "has_file",
    ]
    list_filter = ("media_type", "learning_package")
    search_fields = ("hash_digest",)

    def file_link(self, content: Content):
        if not content.has_file:
            return ""

        return format_html(
            '<a href="{}">Download</a>',
            content.file_url(),
        )

    def text_preview(self, content: Content):
        return format_html(
            '<pre style="white-space: pre-wrap;">\n{}\n</pre>',
            content.text,
        )
