import base64

from django.contrib import admin
from django.urls import reverse
from django.utils.html import format_html

from .models import (
    Component,
    ComponentVersion,
    Content,
)


class ComponentVersionInline(admin.TabularInline):
    model = ComponentVersion
    fields = ["version_num", "created", "title", "format_uuid"]
    readonly_fields = ["version_num", "created", "title", "format_uuid"]
    extra = 0

    def format_uuid(self, cv_obj):
        return format_html(
            '<a href="{}">{}</a>',
            reverse('admin:components_componentversion_change', args=(cv_obj.id,)),
            cv_obj.uuid,
        )
    format_uuid.short_description = "UUID"


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
    list_filter = ('type', 'learning_package')
    search_fields = ["uuid", "identifier"]
    inlines = [ComponentVersionInline]


class ContentInline(admin.TabularInline):
    model = ComponentVersion.contents.through
    fields = ["format_identifier", "size", "rendered_data"]
    readonly_fields = ["content", "format_identifier", "size", "rendered_data"]
    extra = 0

    def rendered_data(self, cv_obj):
        return content_preview(cv_obj.content, 100_000)

    def size(self, cv_obj):
        return cv_obj.content.size
    
    def format_identifier(self, cv_obj):
        return format_html(
            '<a href="{}">{}</a>',
            reverse('admin:components_content_change', args=(cv_obj.content_id,)),
            cv_obj.identifier,
        )
    format_identifier.short_description = "Identifier"


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
        "media_type",
        "media_subtype",
        "size",
        "created",
    ]
    fields = [
        "learning_package",
        "hash_digest",
        "media_type",
        "media_subtype",
        "size",
        "created",
        "rendered_data",
    ]
    readonly_fields = [
        "learning_package",
        "hash_digest",
        "media_type",
        "media_subtype",
        "size",
        "created",
        "rendered_data",
    ]
    list_filter = ('media_type', 'media_subtype', 'learning_package')

    def rendered_data(self, content_obj):
        return content_preview(content_obj, 10_000_000)


def is_displayable_text(media_type, media_subtype):
    # Our usual text files, includiing things like text/markdown, text/html
    if media_type == "text":
        return True

    # Our OLX goes here, but so do some other things like
    if media_subtype.endswith("+xml"):
        return True

    # Other application/* types that we know we can display.
    if media_subtype in ["javascript", "json", "x-subrip"]:
        return True

    return False


def content_preview(content_obj, size_limit):
    if content_obj.size > size_limit:
        return f"Too large to preview."

    # image before text check, since SVGs can be either, but we probably want to
    # see the image version in the admin.
    if content_obj.media_type == "image":
        b64_str = base64.b64encode(content_obj.data).decode("ascii")
        encoded_img_src = f"data:image/{content_obj.media_subtype};base64,{b64_str}"
        return format_html('<img src="{}" style="max-width: 100%;" />', encoded_img_src)

    if is_displayable_text(content_obj.media_type, content_obj.media_subtype):
        return format_html(
            '<pre style="white-space: pre-wrap;">\n{}\n</pre>',
            content_obj.data.decode("utf-8"),
        )

    return format_html("This content type cannot be displayed.")
