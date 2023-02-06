import base64

from django.contrib import admin
from django.utils.html import format_html
from django.utils.safestring import mark_safe

from .models import (
    Component,
    ComponentVersion,
    ComponentVersionContent,
    Content,
)


@admin.register(Component)
class ComponentAdmin(admin.ModelAdmin):
    list_display = ("identifier", "uuid", "namespace", "type", "created", "modified")
    readonly_fields = [
        "learning_package",
        "uuid",
        "namespace",
        "type",
        "identifier",
        "created",
        "modified",
    ]


class ContentInline(admin.TabularInline):
    model = ComponentVersion.contents.through
    fields = ["identifier", "size", "rendered_data"]
    readonly_fields = ["content", "identifier", "size", "rendered_data"]
    extra = 0

    def rendered_data(self, cv_obj):
        return content_preview(cv_obj.content, 100_000)

    def size(self, cv_obj):
        return cv_obj.content.size


@admin.register(ComponentVersion)
class ComponentVersionAdmin(admin.ModelAdmin):
    readonly_fields = [
        "component",
        "uuid",
        "title",
        "version_num",
        "created",
        "contents",
    ]
    fields = [
        "component",
        "uuid",
        "title",
        "version_num",
        "created",
    ]
    inlines = [ContentInline]


@admin.register(Content)
class ContentAdmin(admin.ModelAdmin):
    list_display = [
        "learning_package",
        "hash_digest",
        "type",
        "sub_type",
        "size",
        "created",
    ]
    fields = [
        "learning_package",
        "hash_digest",
        "type",
        "sub_type",
        "size",
        "created",
        "rendered_data",
    ]
    readonly_fields = [
        "learning_package",
        "hash_digest",
        "type",
        "sub_type",
        "size",
        "created",
        "rendered_data",
    ]

    def rendered_data(self, content_obj):
        return content_preview(content_obj, 1_000_000)


def is_displayable_text(type, sub_type):
    # Our usual text files, includiing things like text/markdown, text/html
    if type == "text":
        return True

    # Our OLX goes here, but so do some other things like
    if sub_type.endswith("+xml"):
        return True

    # Other application/* types that we know we can display.
    if sub_type in ["javascript", "json", "x-subrip"]:
        return True

    return False


def content_preview(content_obj, size_limit):
    if content_obj.size > size_limit:
        return "Too large to preview."

    # image before text check, since SVGs can be either, but we probably want to
    # see the image version in the admin.
    if content_obj.type == "image":
        b64_str = base64.b64encode(content_obj.data).decode("ascii")
        encoded_img_src = f"data:image/{content_obj.sub_type};base64,{b64_str}"
        return format_html('<img src="{}" style="max-width: 100%;" />', encoded_img_src)

    if is_displayable_text(content_obj.type, content_obj.sub_type):
        return format_html(
            '<pre style="white-space: pre-wrap;">\n{}\n</pre>',
            content_obj.data.decode("utf-8"),
        )

    return format_html("This content type cannot be displayed.")
