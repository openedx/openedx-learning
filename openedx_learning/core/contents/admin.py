"""
Django admin for contents models
"""
from django.contrib import admin
from django.utils.html import format_html

from openedx_learning.lib.admin_utils import ReadOnlyModelAdmin

from .models import RawContent


@admin.register(RawContent)
class RawContentAdmin(ReadOnlyModelAdmin):
    """
    Django admin for RawContent model
    """
    list_display = [
        "hash_digest",
        "file_link",
        "learning_package",
        "mime_type",
        "size",
        "created",
    ]
    fields = [
        "learning_package",
        "hash_digest",
        "mime_type",
        "size",
        "created",
        "file_link",
        "text_preview",
    ]
    readonly_fields = [
        "learning_package",
        "hash_digest",
        "mime_type",
        "size",
        "created",
        "file_link",
        "text_preview",
    ]
    list_filter = ("mime_type", "learning_package")
    search_fields = ("hash_digest",)

    def file_link(self, raw_content):
        return format_html(
            '<a href="{}">Download</a>',
            raw_content.file.url,
        )

    def text_preview(self, raw_content):
        if not hasattr(raw_content, "text_content"):
            return "(not available)"

        return format_html(
            '<pre style="white-space: pre-wrap;">\n{}\n</pre>',
            raw_content.text_content.text,
        )
