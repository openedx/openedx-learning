from django.contrib import admin
from django.template.defaultfilters import filesizeformat
from django.urls import reverse
from django.utils.html import format_html

from .models import (
    Component,
    ComponentVersion,
    ComponentVersionRawContent,
)
from openedx_learning.lib.admin_utils import ReadOnlyModelAdmin


class ComponentVersionInline(admin.TabularInline):
    model = ComponentVersion
    fields = ["version_num", "created", "title", "format_uuid"]
    readonly_fields = ["version_num", "created", "title", "uuid", "format_uuid"]
    extra = 0

    def format_uuid(self, cv_obj):
        return format_html(
            '<a href="{}">{}</a>',
            reverse("admin:oel_components_componentversion_change", args=(cv_obj.pk,)),
            cv_obj.uuid,
        )

    format_uuid.short_description = "UUID"


@admin.register(Component)
class ComponentAdmin(ReadOnlyModelAdmin):
    list_display = ("key", "uuid", "namespace", "type", "created")
    readonly_fields = [
        "learning_package",
        "uuid",
        "namespace",
        "type",
        "key",
        "created",
    ]
    list_filter = ("type", "learning_package")
    search_fields = ["publishable_entity__uuid", "publishable_entity__key"]
    inlines = [ComponentVersionInline]


class RawContentInline(admin.TabularInline):
    model = ComponentVersion.raw_contents.through

    def get_queryset(self, request):
        queryset = super().get_queryset(request)
        return queryset.select_related(
            "raw_content",
            "raw_content__learning_package",
            "raw_content__text_content",
            "component_version",
            "component_version__publishable_entity_version",
            "component_version__component",
            "component_version__component__publishable_entity",
        )

    fields = [
        "format_key",
        "format_size",
        "learner_downloadable",
        "rendered_data",
    ]
    readonly_fields = [
        "raw_content",
        "format_key",
        "format_size",
        "rendered_data",
    ]
    extra = 0

    def rendered_data(self, cvc_obj):
        return content_preview(cvc_obj)

    def format_size(self, cvc_obj):
        return filesizeformat(cvc_obj.raw_content.size)

    format_size.short_description = "Size"

    def format_key(self, cvc_obj):
        return format_html(
            '<a href="{}">{}</a>',
            link_for_cvc(cvc_obj),
            # reverse("admin:components_content_change", args=(cvc_obj.content_id,)),
            cvc_obj.key,
        )

    format_key.short_description = "Key"


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
    list_display = ["component", "version_num", "uuid", "created"]
    inlines = [RawContentInline]

    def get_queryset(self, request):
        queryset = super().get_queryset(request)
        return queryset.select_related(
            "component",
            "component__publishable_entity",
            "publishable_entity_version",
        )


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
        cvc_obj.raw_content.learning_package.key,
        cvc_obj.component_version.component.key,
        cvc_obj.component_version.version_num,
        cvc_obj.key,
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
                cvc_obj.raw_content.learning_package.key,
                cvc_obj.component_version.component.key,
                cvc_obj.component_version.version_num,
                cvc_obj.key,
            ),
        )

    if hasattr(raw_content_obj, "text_content"):
        return format_text_for_admin_display(
            raw_content_obj.text_content.text,
        )

    return format_html("This content type cannot be displayed.")
