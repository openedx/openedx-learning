"""
Container and ContainerVersion models
"""

from __future__ import annotations

from functools import cached_property
from typing import final

from django.core.exceptions import ValidationError
from django.db import models

from openedx_django_lib.fields import case_sensitive_char_field

from ..publishing.models.publishable_entity import (
    PublishableEntity,
    PublishableEntityMixin,
    PublishableEntityVersion,
    PublishableEntityVersionMixin,
)

__all__ = [
    "Container",
    "ContainerVersion",
    # ContainerType is not public
    "EntityList",
    "EntityListRow",
]


class EntityList(models.Model):
    """
    EntityLists are a common structure to hold parent-child relations.

    EntityLists are not PublishableEntities in and of themselves. That's because
    sometimes we'll want the same kind of data structure for things that we
    dynamically generate for individual students (e.g. Variants). EntityLists are
    anonymous in a sense–they're pointed to by ContainerVersions and
    other models, rather than being looked up by their own identifiers.
    """

    @cached_property
    def rows(self):
        """
        Convenience method to iterate rows.

        I'd normally make this the reverse lookup name for the EntityListRow ->
        EntityList foreign key relation, but we already have references to
        entitylistrow_set in various places, and I thought this would be better
        than breaking compatibility.
        """
        return self.entitylistrow_set.order_by("order_num")


class EntityListRow(models.Model):
    """
    Each EntityListRow points to a PublishableEntity, optionally at a specific
    version.

    There is a row in this table for each member of an EntityList. The order_num
    field is used to determine the order of the members in the list.
    """

    entity_list = models.ForeignKey(EntityList, on_delete=models.CASCADE)

    # This ordering should be treated as immutable–if the ordering needs to
    # change, we create a new EntityList and copy things over.
    order_num = models.PositiveIntegerField()

    # Simple case would use these fields with our convention that null versions
    # means "get the latest draft or published as appropriate". These entities
    # could be Selectors, in which case we'd need to do more work to find the right
    # variant. The publishing app itself doesn't know anything about Selectors
    # however, and just treats it as another PublishableEntity.
    entity = models.ForeignKey(PublishableEntity, on_delete=models.RESTRICT)

    # The version references point to the specific PublishableEntityVersion that
    # this EntityList has for this PublishableEntity for both the draft and
    # published states. However, we don't want to have to create new EntityList
    # every time that a member is updated, because that would waste a lot of
    # space and make it difficult to figure out when the metadata of something
    # like a Unit *actually* changed, vs. when its child members were being
    # updated. Doing so could also potentially lead to race conditions when
    # updating multiple layers of containers.
    #
    # So our approach to this is to use a value of None (null) to represent an
    # unpinned reference to a PublishableEntity. It's shorthand for "just use
    # the latest draft or published version of this, as appropriate".
    entity_version = models.ForeignKey(
        PublishableEntityVersion,
        on_delete=models.RESTRICT,
        null=True,
        related_name="+",  # Do we need the reverse relation?
    )

    def is_pinned(self):
        return self.entity_version_id is not None

    def is_unpinned(self):
        return self.entity_version_id is None

    class Meta:
        ordering = ["order_num"]
        constraints = [
            # If (entity_list, order_num) is not unique, it likely indicates a race condition - so force uniqueness.
            models.UniqueConstraint(
                fields=["entity_list", "order_num"],
                name="oel_publishing_elist_row_order",
            ),
        ]


_registered_container_types: dict[str, type[Container]] = {}


class ContainerImplementationMissingError(Exception):
    """Raised when trying to modify a container whose implementation [plugin] is no longer available."""


class ContainerType(models.Model):
    """
    Normalized representation of the type of Container.

    Typical container types are "unit", "subsection", and "section", but there
    may be others in the future.
    """

    id = models.AutoField(primary_key=True)

    # type_code uniquely identifies the type of container, e.g. "unit", "subsection", etc.
    # Plugins/apps that add their own ContainerTypes should prefix it, e.g.
    # "myapp_custom_unit" instead of "custom_unit", to avoid collisions.
    type_code = case_sensitive_char_field(
        max_length=100,
        blank=False,
        unique=True,
    )

    class Meta:
        constraints = [
            models.CheckConstraint(
                # No whitespace, uppercase, or special characters allowed in "type_code".
                condition=models.lookups.Regex(models.F("type_code"), r"^[a-z0-9\-_\.]+$"),
                name="oex_publishing_containertype_type_code_rx",
            ),
        ]

    def __str__(self) -> str:  # pylint: disable=invalid-str-returned
        return self.type_code


class Container(PublishableEntityMixin):
    """
    A Container is a type of PublishableEntity that holds other
    PublishableEntities. For example, a "Unit" Container might hold several
    Components.

    For now, all containers have a static "entity list" that defines which
    containers/components/enities they hold. As we complete the Containers API,
    we will also add support for dynamic containers which may contain different
    entities for different learners or at different times.
    """

    type_code: str  # Subclasses must override this, e.g. "unit"
    # olx_code: the OLX <tag_name> for XML serialization. Subclasses _may_ override this.
    # Only used in openedx-platform at the moment. We'll likely have to replace this with something more sophisticated.
    olx_tag_name: str = ""
    _type_instance: ContainerType  # Cache used by get_container_type()

    # The type of the container. Cannot be changed once the container is created.
    container_type = models.ForeignKey(
        ContainerType,
        null=False,
        on_delete=models.RESTRICT,
        editable=False,
    )

    @classmethod
    def validate_entity(cls, entity: PublishableEntity) -> None:
        """
        Check if the given entity is allowed as a child of this Container type

        Subclasses should raise ValidationError if "entity" is invalid.
        """

    @final
    @classmethod
    def get_container_type(cls) -> ContainerType:
        """
        Get the ContainerType for this type of container, auto-creating it if need be.
        """
        if cls is Container:
            raise TypeError("Manipulating plain Containers is not allowed. Use a Container subclass, like Unit.")
        assert cls.type_code, f"Container subclasses like {cls.__name__} must override type_code"
        if not hasattr(cls, "_type_instance"):
            cls._type_instance, _ = ContainerType.objects.get_or_create(type_code=cls.type_code)
        return cls._type_instance

    @final
    @staticmethod
    def reset_cache() -> None:
        """
        Helper for test cases that truncate the database between tests.
        Call this to delete the cache used in get_container_type(), which will be invalid after the ContainerType table
        is truncated.
        """
        for cls in _registered_container_types.values():
            if hasattr(cls, "_type_instance"):
                del cls._type_instance

    @staticmethod
    def register_subclass(container_subclass: type[Container]):
        """
        Register a Container subclass
        """
        assert container_subclass.type_code, "Container subclasses must override type_code"
        assert container_subclass.type_code not in _registered_container_types, (
            f"{container_subclass.type_code} already registered"
        )
        _registered_container_types[container_subclass.type_code] = container_subclass
        return container_subclass

    @staticmethod
    def subclass_for_type_code(type_code: str) -> type[Container]:
        """
        Get the subclass for the specified container type_code.
        """
        try:
            return _registered_container_types[type_code]
        except KeyError as exc:
            raise ContainerImplementationMissingError(
                f'An implementation for "{type_code}" containers is not currently installed. '
                "Such containers can be read but not modified."
            ) from exc

    @staticmethod
    def all_subclasses() -> list[type[Container]]:
        """Get a list of all installed container types"""
        return sorted(_registered_container_types.values(), key=lambda ct: ct.type_code)


class ContainerVersion(PublishableEntityVersionMixin):
    """
    A version of a Container.

    By convention, we would only want to create new versions when the Container
    itself changes, and not when the Container's child elements change. For
    example:

    * Something was added to the Container.
    * We re-ordered the rows in the container.
    * Something was removed to the container.
    * The Container's metadata changed, e.g. the title.
    * We pin to different versions of the Container.

    The last looks a bit odd, but it's because *how we've defined the Unit* has
    changed if we decide to explicitly pin a set of versions for the children,
    and then later change our minds and move to a different set. It also just
    makes things easier to reason about if we say that entity_list never
    changes for a given ContainerVersion.
    """

    container = models.ForeignKey(
        Container,
        on_delete=models.CASCADE,
        related_name="versions",
    )

    # The list of entities (frozen and/or unfrozen) in this container
    entity_list = models.ForeignKey(
        EntityList,
        on_delete=models.RESTRICT,
        null=False,
        related_name="container_versions",
    )

    def clean(self):
        """
        Validate this model before saving. Not called normally, but will be
        called if anything is edited via a ModelForm like the Django admin.
        """
        super().clean()
        if self.container_id != self.publishable_entity_version.entity.container.pk:  # pylint: disable=no-member
            raise ValidationError("Inconsistent foreign keys to Container")
