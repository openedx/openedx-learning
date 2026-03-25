"""
Django admin for containers models
"""

from __future__ import annotations

import functools
from typing import TYPE_CHECKING

from django.contrib import admin
from django.db.models import Count, QuerySet
from django.urls import reverse
from django.utils.html import format_html
from django.utils.safestring import SafeText

from openedx_django_lib.admin_utils import ReadOnlyModelAdmin, model_detail_link, one_to_one_related_model_html

from .api import ContainerImplementationMissingError, get_container_subclass
from .models import Container, ContainerType, ContainerVersion, EntityList, EntityListRow

if TYPE_CHECKING:

    class ContainerTypeWithNumContainers(ContainerType):
        num_containers: int


@admin.register(ContainerType)
class ContainerTypeAdmin(ReadOnlyModelAdmin):
    """Very basic Django admin for ContainerType"""

    list_display = ("type_code", "num_containers", "installed")

    def get_queryset(self, request) -> QuerySet[ContainerTypeWithNumContainers]:
        return super().get_queryset(request).annotate(num_containers=Count("container"))

    @admin.display(description="# of Containers")
    def num_containers(self, obj: ContainerTypeWithNumContainers) -> str:
        """# of containers of this type and a link to view them"""
        url = reverse("admin:openedx_content_container_changelist") + f"?container_type={obj.pk}"
        return format_html('<a href="{}">{}</a>', url, obj.num_containers)

    @admin.display(boolean=True)
    def installed(self, obj: ContainerType) -> bool:
        """Is the implementation of this container subclass installed?"""
        try:
            get_container_subclass(obj.type_code)
            return True
        except ContainerImplementationMissingError:
            return False


def _entity_list_detail_link(el: EntityList) -> SafeText:
    """
    A link to the detail page for an EntityList which includes its PK and length.
    """
    num_rows = el.entitylistrow_set.count()
    rows_noun = "row" if num_rows == 1 else "rows"
    return model_detail_link(el, f"EntityList #{el.pk} with {num_rows} {rows_noun}")


class ContainerVersionInlineForContainer(admin.TabularInline):
    """
    Inline admin view of ContainerVersions in a given Container
    """

    model = ContainerVersion
    ordering = ["-publishable_entity_version__version_num"]
    fields = [
        "pk",
        "version_num",
        "title",
        "children",
        "created",
        "created_by",
    ]
    readonly_fields = fields  # type: ignore[assignment]
    extra = 0

    def get_queryset(self, request):
        return super().get_queryset(request).select_related("publishable_entity_version")

    def children(self, obj: ContainerVersion):
        return _entity_list_detail_link(obj.entity_list)


@admin.register(Container)
class ContainerAdmin(ReadOnlyModelAdmin):
    """
    Django admin configuration for Container
    """

    list_display = ("key", "container_type_display", "published", "draft", "created")
    fields = [
        "pk",
        "publishable_entity",
        "learning_package",
        "published",
        "draft",
        "created",
        "created_by",
        "see_also",
        "most_recent_parent_entity_list",
    ]
    readonly_fields = fields  # type: ignore[assignment]
    search_fields = ["publishable_entity__uuid", "publishable_entity__key"]
    inlines = [ContainerVersionInlineForContainer]

    def learning_package(self, obj: Container) -> SafeText:
        return model_detail_link(
            obj.publishable_entity.learning_package,
            obj.publishable_entity.learning_package.key,
        )

    def get_queryset(self, request):
        return (
            super()
            .get_queryset(request)
            .select_related(
                "container_type",
                "publishable_entity",
                "publishable_entity__learning_package",
                "publishable_entity__published__version",
                "publishable_entity__draft__version",
            )
        )

    @admin.display(description="Type")
    def container_type_display(self, obj: Container) -> str:
        """What type of container this is"""
        type_code = obj.container_type.type_code
        try:
            container_type_name = get_container_subclass(type_code).__name__
        except ContainerImplementationMissingError:
            container_type_name = "?????"
        return format_html(
            '{}<br><span style="color: var(--body-quiet-color);">({})</span>', container_type_name, type_code
        )

    def draft(self, obj: Container) -> str:
        """
        Link to this Container's draft ContainerVersion
        """
        if draft := obj.versioning.draft:
            if obj.versioning.published and draft.pk == obj.versioning.published.pk:
                return format_html(
                    '<span style="color: var(--body-quiet-color);">{}</span>', "(no changes from published)"
                )
            return format_html(
                'Version {} "{}" ({})', draft.version_num, draft.title, _entity_list_detail_link(draft.entity_list)
            )
        return "-"

    def published(self, obj: Container) -> str:
        """
        Link to this Container's published ContainerVersion
        """
        if published := obj.versioning.published:
            return format_html(
                'Version {} "{}" ({})',
                published.version_num,
                published.title,
                _entity_list_detail_link(published.entity_list),
            )
        return "-"

    def see_also(self, obj: Container):
        return one_to_one_related_model_html(obj)

    def most_recent_parent_entity_list(self, obj: Container) -> str:
        if latest_row := EntityListRow.objects.filter(entity_id=obj.publishable_entity_id).order_by("-pk").first():
            return _entity_list_detail_link(latest_row.entity_list)
        return "-"


class ContainerVersionInlineForEntityList(admin.TabularInline):
    """
    Inline admin view of ContainerVersions which use a given EntityList
    """

    model = ContainerVersion
    verbose_name = "Container Version that references this Entity List"
    verbose_name_plural = "Container Versions that reference this Entity List"
    ordering = ["-pk"]  # Newest first
    fields = [
        "pk",
        "version_num",
        "container_key",
        "title",
        "created",
        "created_by",
    ]
    readonly_fields = fields  # type: ignore[assignment]
    extra = 0

    def get_queryset(self, request):
        return (
            super()
            .get_queryset(request)
            .select_related(
                "container",
                "container__publishable_entity",
                "publishable_entity_version",
            )
        )

    def container_key(self, obj: ContainerVersion) -> SafeText:
        return model_detail_link(obj.container, obj.container.key)


class EntityListRowInline(admin.TabularInline):
    """
    Table of entity rows in the entitylist admin
    """

    model = EntityListRow
    readonly_fields = [
        "order_num",
        "pinned_version_num",
        "entity_models",
        "container_models",
        "container_children",
    ]
    fields = readonly_fields  # type: ignore[assignment]

    def get_queryset(self, request):
        return (
            super()
            .get_queryset(request)
            .select_related(
                "entity",
                "entity_version",
            )
        )

    def pinned_version_num(self, obj: EntityListRow):
        return str(obj.entity_version.version_num) if obj.entity_version else "(Unpinned)"

    def entity_models(self, obj: EntityListRow):
        return format_html(
            "{}<ul>{}</ul>",
            model_detail_link(obj.entity, obj.entity.key),
            one_to_one_related_model_html(obj.entity),
        )

    def container_models(self, obj: EntityListRow) -> SafeText:
        if not hasattr(obj.entity, "container"):
            return SafeText("(Not a Container)")
        return format_html(
            "{}<ul>{}</ul>",
            model_detail_link(obj.entity.container, str(obj.entity.container)),
            one_to_one_related_model_html(obj.entity.container),
        )

    def container_children(self, obj: EntityListRow) -> SafeText:
        """
        If this row holds a Container, then link *its* EntityList, allowing easy hierarchy browsing.

        When determining which ContainerVersion to grab the EntityList from, prefer the pinned
        version if there is one; otherwise use the Draft version.
        """
        if not hasattr(obj.entity, "container"):
            return SafeText("(Not a Container)")
        child_container_version: ContainerVersion = (
            obj.entity_version.containerversion if obj.entity_version else obj.entity.container.versioning.draft
        )
        return _entity_list_detail_link(child_container_version.entity_list)


@admin.register(EntityList)
class EntityListAdmin(ReadOnlyModelAdmin):
    """
    Django admin configuration for EntityList
    """

    list_display = [
        "entity_list",
        "row_count",
        "recent_container_version_num",
        "recent_container",
        "recent_container_package",
    ]
    inlines = [ContainerVersionInlineForEntityList, EntityListRowInline]

    def entity_list(self, obj: EntityList) -> SafeText:
        return model_detail_link(obj, f"EntityList #{obj.pk}")

    def row_count(self, obj: EntityList) -> int:
        return obj.entitylistrow_set.count()

    def recent_container_version_num(self, obj: EntityList) -> str:
        """
        Number of the newest ContainerVersion that references this EntityList
        """
        if latest := _latest_container_version(obj):
            return f"Version {latest.version_num}"
        else:
            return "-"

    def recent_container(self, obj: EntityList) -> SafeText | None:
        """
        Link to the Container of the newest ContainerVersion that references this EntityList
        """
        if latest := _latest_container_version(obj):
            return format_html("of: {}", model_detail_link(latest.container, latest.container.key))
        else:
            return None

    def recent_container_package(self, obj: EntityList) -> SafeText | None:
        """
        Link to the LearningPackage of the newest ContainerVersion that references this EntityList
        """
        if latest := _latest_container_version(obj):
            return format_html(
                "in: {}",
                model_detail_link(
                    latest.container.publishable_entity.learning_package,
                    latest.container.publishable_entity.learning_package.key,
                ),
            )
        else:
            return None

    # We'd like it to appear as if these three columns are just a single
    # nicely-formatted column, so only give the left one a description.
    recent_container_version_num.short_description = (  # type: ignore[attr-defined]
        "Most recent container version using this entity list"
    )
    recent_container.short_description = ""  # type: ignore[attr-defined]
    recent_container_package.short_description = ""  # type: ignore[attr-defined]


@functools.cache
def _latest_container_version(obj: EntityList) -> ContainerVersion | None:
    """
    Any given EntityList can be used by multiple ContainerVersion (which may even
    span multiple Containers). We only have space here to show one ContainerVersion
    easily, so let's show the one that's most likely to be interesting to the Django
    admin user: the most-recently-created one.
    """
    return obj.container_versions.order_by("-pk").first()
