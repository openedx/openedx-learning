"""
Django admin for components models
"""
from django.contrib import admin
from django.template.defaultfilters import filesizeformat
from django.urls import reverse
from django.utils.html import format_html
from django.utils.safestring import SafeText

from openedx_learning.lib.admin_utils import ReadOnlyModelAdmin

from .models import Component, ComponentVersion, ComponentVersionContent


class ComponentVersionInline(admin.TabularInline):
    """
    Inline admin view of ComponentVersion from the Component Admin
    """
    model = ComponentVersion
    fields = ["version_num", "created", "title", "format_uuid"]
    readonly_fields = ["version_num", "created", "title", "uuid", "format_uuid"]
    extra = 0

    @admin.display(description="UUID")
    def format_uuid(self, cv_obj):
        return format_html(
            '<a href="{}">{}</a>',
            reverse("admin:oel_components_componentversion_change", args=(cv_obj.pk,)),
            cv_obj.uuid,
        )


@admin.register(Component)
class ComponentAdmin(ReadOnlyModelAdmin):
    """
    Django admin configuration for Component
    """
    list_display = ("key", "uuid", "component_type", "created")
    readonly_fields = [
        "learning_package",
        "uuid",
        "component_type",
        "key",
        "created",
    ]
    list_filter = ("component_type", "learning_package")
    search_fields = ["publishable_entity__uuid", "publishable_entity__key"]
    inlines = [ComponentVersionInline]


class ContentInline(admin.TabularInline):
    """
    Django admin configuration for Content
    """
    model = ComponentVersion.contents.through

    def get_queryset(self, request):
        queryset = super().get_queryset(request)
        return queryset.select_related(
            "content",
            "content__learning_package",
            "content__media_type",
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
        "content",
        "format_key",
        "format_size",
        "rendered_data",
    ]
    extra = 0

    def rendered_data(self, cvc_obj):
        return content_preview(cvc_obj)

    @admin.display(description="Size")
    def format_size(self, cvc_obj):
        return filesizeformat(cvc_obj.content.size)

    @admin.display(description="Key")
    def format_key(self, cvc_obj):
        return format_html(
            '<a href="{}">{}</a>',
            link_for_cvc(cvc_obj),
            # reverse("admin:components_content_change", args=(cvc_obj.content_id,)),
            cvc_obj.key,
        )


@admin.register(ComponentVersion)
class ComponentVersionAdmin(ReadOnlyModelAdmin):
    """
    Django admin configuration for ComponentVersion
    """
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
    list_display = ["component", "version_num", "uuid", "created"]
    inlines = [ContentInline]

    def get_queryset(self, request):
        queryset = super().get_queryset(request)
        return queryset.select_related(
            "component",
            "component__publishable_entity",
            "publishable_entity_version",
        )


def link_for_cvc(cvc_obj: ComponentVersionContent) -> str:
    """
    Get the download URL for the given ComponentVersionContent instance
    """
    return "/media_server/component_asset/{}/{}/{}/{}".format(
        cvc_obj.content.learning_package.key,
        cvc_obj.component_version.component.key,
        cvc_obj.component_version.version_num,
        cvc_obj.key,
    )


def format_text_for_admin_display(text: str) -> SafeText:
    """
    Get the HTML to display the given plain text (preserving formatting)
    """
    return format_html(
        '<pre style="white-space: pre-wrap;">\n{}\n</pre>',
        text,
    )


def content_preview(cvc_obj: ComponentVersionContent) -> SafeText:
    """
    Get the HTML to display a preview of the given ComponentVersionContent
    """
    content_obj = cvc_obj.content

    if content_obj.media_type.type == "image":
        return format_html(
            '<img src="{}" style="max-width: 100%;" />',
            content_obj.file_url(),
        )

    return format_text_for_admin_display(
        content_obj.text or ""
    )
