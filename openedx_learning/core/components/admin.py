from django.contrib import admin
from django.db.models.aggregates import Count, Sum
from django.template.defaultfilters import filesizeformat
from django.urls import reverse
from django.utils.html import format_html

from .models import (
    Component,
    ComponentVersion,
    ComponentVersionRawContent,
    PublishedComponent,
    RawContent,
)
from openedx_learning.lib.admin_utils import ReadOnlyModelAdmin


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
            .annotate(size=Sum("component_version__raw_contents__size"))
            .annotate(content_count=Count("component_version__raw_contents"))
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
            reverse(
                "admin:components_componentversion_change",
                args=(pc.component_version_id,),
            ),
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


class RawContentInline(admin.TabularInline):
    model = ComponentVersion.raw_contents.through
    fields = [
        "format_identifier",
        "format_size",
        "learner_downloadable",
        "rendered_data",
    ]
    readonly_fields = [
        "raw_content",
        "format_identifier",
        "format_size",
        "rendered_data",
    ]
    extra = 0

    def rendered_data(self, cvc_obj):
        return content_preview(cvc_obj)

    def format_size(self, cvc_obj):
        return filesizeformat(cvc_obj.raw_content.size)

    format_size.short_description = "Size"

    def format_identifier(self, cvc_obj):
        return format_html(
            '<a href="{}">{}</a>',
            link_for_cvc(cvc_obj),
            # reverse("admin:components_content_change", args=(cvc_obj.content_id,)),
            cvc_obj.identifier,
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
        "raw_contents",
    ]
    fields = [
        "component",
        "uuid",
        "title",
        "version_num",
        "created",
    ]
    inlines = [RawContentInline]


@admin.register(RawContent)
class RawContentAdmin(ReadOnlyModelAdmin):
    list_display = [
        "hash_digest",
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
        "text_preview",
    ]
    readonly_fields = [
        "learning_package",
        "hash_digest",
        "mime_type",
        "size",
        "created",
        "text_preview",
    ]
    list_filter = ("mime_type", "learning_package")
    search_fields = ("hash_digest",)

    def text_preview(self, raw_content_obj):
        if hasattr(raw_content_obj, "text_content"):
            return format_text_for_admin_display(raw_content_obj.text_content.text)
        return ""


def is_displayable_text(mime_type):
    # Our usual text files, including things like text/markdown, text/html
    media_type, media_subtype = mime_type.split("/")

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


def link_for_cvc(cvc_obj: ComponentVersionRawContent):
    return "/media_server/component_asset/{}/{}/{}/{}".format(
        cvc_obj.raw_content.learning_package.identifier,
        cvc_obj.component_version.component.identifier,
        cvc_obj.component_version.version_num,
        cvc_obj.identifier,
    )


def format_text_for_admin_display(text):
    return format_html(
        '<pre style="white-space: pre-wrap;">\n{}\n</pre>',
        text,
    )


def content_preview(cvc_obj: ComponentVersionRawContent):
    raw_content_obj = cvc_obj.raw_content

    if raw_content_obj.mime_type.startswith("image/"):
        return format_html(
            '<img src="{}" style="max-width: 100%;" />',
            # TODO: configure with settings value:
            "/media_server/component_asset/{}/{}/{}/{}".format(
                cvc_obj.raw_content.learning_package.identifier,
                cvc_obj.component_version.component.identifier,
                cvc_obj.component_version.version_num,
                cvc_obj.identifier,
            ),
        )

    if hasattr(raw_content_obj, "text_content"):
        return format_text_for_admin_display(
            raw_content_obj.text_content.text,
        )

    return format_html("This content type cannot be displayed.")
