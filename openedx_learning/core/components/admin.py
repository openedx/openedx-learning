from django.contrib import admin
from django.conf import settings
from django.db.models.aggregates import Count, Sum
from django.template.defaultfilters import filesizeformat
from django.urls import reverse
from django.utils.html import format_html

from .models import (
    Component,
    ComponentVersion,
    ComponentVersionContent,
    Content,
    PublishedComponent,
)


class ReadOnlyModelAdmin(admin.ModelAdmin):
    def has_add_permission(self, request):
        return False

    def has_change_permission(self, request, obj=None):
        return False

    def has_delete_permission(self, request, obj=None):
        return False


class ComponentVersionInline(admin.TabularInline):
    model = ComponentVersion
    fields = ["version_num", "created", "title", "format_uuid"]
    readonly_fields = ["version_num", "created", "title", "format_uuid"]
    extra = 0

    def format_uuid(self, cv_obj):
        return format_html(
            '<a href="{}">{}</a>',
            reverse("admin:components_componentversion_change", args=(cv_obj.id,)),
            cv_obj.uuid,
        )

    format_uuid.short_description = "UUID"


@admin.register(Component)
class ComponentAdmin(ReadOnlyModelAdmin):
    list_display = ("identifier", "uuid", "namespace", "type", "created")
    readonly_fields = [
        "learning_package",
        "uuid",
        "namespace",
        "type",
        "identifier",
        "created",
    ]
    list_filter = ("type", "learning_package")
    search_fields = ["uuid", "identifier"]
    inlines = [ComponentVersionInline]


@admin.register(PublishedComponent)
class PublishedComponentAdmin(ReadOnlyModelAdmin):
    model = PublishedComponent

    def get_queryset(self, request):
        queryset = super().get_queryset(request)
        return (
            queryset.select_related(
                "component",
                "component__learning_package",
                "component_version",
                "component_publish_log_entry__publish_log_entry",
            )
            .annotate(size=Sum("component_version__contents__size"))
            .annotate(content_count=Count("component_version__contents"))
        )

    readonly_fields = ["component", "component_version", "component_publish_log_entry"]
    list_display = [
        "identifier",
        "version",
        "title",
        "published_at",
        "type",
        "content_count",
        "size",
        "learning_package",
    ]
    list_filter = ["component__type", "component__learning_package"]
    search_fields = [
        "component__uuid",
        "component__identifier",
        "component_version__uuid",
        "component_version__title",
    ]

    def learning_package(self, pc):
        return pc.component.learning_package.identifier

    def published_at(self, pc):
        return pc.component_publish_log_entry.publish_log_entry.published_at

    def identifier(self, pc):
        """
        Link to published ComponentVersion with Component identifier as text.

        This is a little weird in that we're showing the Component identifier,
        but linking to the published ComponentVersion. But this is what you want
        to link to most of the time, as the link to the Component has almost no
        information in it (and can be accessed from the ComponentVersion details
        page anyhow).
        """
        return format_html(
            '<a href="{}">{}</a>',
            reverse("admin:components_componentversion_change", args=(pc.component_version_id,)),
            pc.component.identifier,
        )

    def content_count(self, pc):
        return pc.content_count
    content_count.short_description = "#"

    def size(self, pc):
        return filesizeformat(pc.size)

    def namespace(self, pc):
        return pc.component.namespace

    def type(self, pc):
        return pc.component.type

    def version(self, pc):
        return pc.component_version.version_num

    def title(self, pc):
        return pc.component_version.title


def content_path(cvc_obj: ComponentVersionContent):
    """
    NOTE: This is probably really inefficient with sql lookups at the moment.
    """
    learning_package_identifier = cvc_obj.content.learning_package.identifier
    component_identifier = cvc_obj.component_version.component.identifier
    version_num = cvc_obj.component_version.version_num
    asset_path = cvc_obj.identifier

    return "{}/components/{}/{}/{}/{}".format(
        settings.FILEPONY['HOST'],
        learning_package_identifier,
        component_identifier,
        version_num,
        asset_path,
    )


class ContentInline(admin.TabularInline):
    model = ComponentVersion.contents.through
    fields = ["format_identifier", "format_size", "rendered_data"]
    readonly_fields = ["content", "format_identifier", "format_size", "rendered_data"]
    extra = 0

    def rendered_data(self, cvc_obj):
        return content_preview(cvc_obj, 100_000)

    def format_size(self, cv_obj):
        return filesizeformat(cv_obj.content.size)
    format_size.short_description = "Size"

    def format_identifier(self, cv_obj):
        return format_html(
            '<a href="{}">{}</a>',
            reverse("admin:components_content_change", args=(cv_obj.content_id,)),
            cv_obj.identifier,
        )

    format_identifier.short_description = "Identifier"


@admin.register(ComponentVersion)
class ComponentVersionAdmin(ReadOnlyModelAdmin):
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
class ContentAdmin(ReadOnlyModelAdmin):
    list_display = [
        "hash_digest",
        "learning_package",
        "mime_type",
        "format_size",
        "created",
    ]
    fields = [
        "learning_package",
        "hash_digest",
        "mime_type",
        "format_size",
        "created",
        "file",
        "rendered_data",
    ]
    readonly_fields = [
        "learning_package",
        "hash_digest",
        "mime_type",
        "format_size",
        "created",
        "file",
        "rendered_data",
    ]
    list_filter = ("mime_type", "learning_package")
    search_fields = ("hash_digest", "size")

    def format_size(self, content_obj):
        return filesizeformat(content_obj.size)
    format_size.short_description = "Size"

    def rendered_data(self, content_obj):
        return content_preview(content_obj, 10_000_000)


def is_displayable_text(mime_type):
    # Our usual text files, includiing things like text/markdown, text/html
    media_type, media_subtype = mime_type.split('/')

    if media_type == "text":
        return True

    # Our OLX goes here, but so do some other things like
    if media_subtype.endswith("+xml"):
        return True

    # Other application/* types that we know we can display.
    if media_subtype in ["json", "x-subrip"]:
        return True
    
    # Other formats that are really specific types of JSON
    if media_subtype.endswith("+json"):
        return True

    return False


def content_preview(cvc_obj, size_limit):
    content_obj = cvc_obj.content

    if content_obj.size > size_limit:
        return f"Too large to preview."

    # image before text check, since SVGs can be either, but we probably want to
    # see the image version in the admin.
    if content_obj.mime_type.startswith("image/"):
        return format_html(
            '<img src="{}" style="max-width: 100%;" />',
            content_path(cvc_obj),
        )

    if is_displayable_text(content_obj.mime_type):
        return format_html(
            '<pre style="white-space: pre-wrap;">\n{}\n</pre>',
            content_obj.data.decode("utf-8"),
        )

    return format_html("This content type cannot be displayed.")


def content_preview_old(content_obj, size_limit):
    if content_obj.size > size_limit:
        return f"Too large to preview."

    # image before text check, since SVGs can be either, but we probably want to
    # see the image version in the admin.
    #if content_obj.mime_type.startswith("image/"):
    #    return format_html(
    #        '<img src="{}" style="max-width: 100%;" />',
    #        f"{settings.FILEPONY['HOST']}/components/{content_obj.learning_package.identifier}/"
    #    )

    if is_displayable_text(content_obj.mime_type):
        return format_html(
            '<pre style="white-space: pre-wrap;">\n{}\n</pre>',
            content_obj.data.decode("utf-8"),
        )

    return format_html("This content type cannot be displayed.")
