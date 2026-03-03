"""
Container and ContainerVersion models
"""

from __future__ import annotations

from typing import final

from django.core.exceptions import ValidationError
from django.db import models

from openedx_django_lib.fields import case_sensitive_char_field

from .entity_list import EntityList
from .publishable_entity import PublishableEntity, PublishableEntityMixin, PublishableEntityVersionMixin

_registered_container_types: dict[str, type[Container]] = {}


class ContainerImplementationMissingError(Exception):
    """Raised when trying to modify a container whose implementation [plugin] is no longer available."""


class ContainerTypeRecord(models.Model):
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
                name="oex_publishing_containertyperecord_type_code_rx",
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
    _type_instance: ContainerTypeRecord  # Cache used by get_type_record()

    # The type of the container. Cannot be changed once the container is created.
    container_type_record = models.ForeignKey(
        ContainerTypeRecord,
        null=False,
        on_delete=models.RESTRICT,
        editable=False,
    )

    @classmethod
    def validate_entity(cls, entity: PublishableEntity) -> None:
        """Check if the given entity is allowed as a child of this Container type"""

    @final
    @classmethod
    def get_type_record(cls) -> ContainerTypeRecord:
        """
        Get the ContainerTypeRecord for this type of container, auto-creating it
        if need be.
        """
        if cls is Container:
            raise TypeError('Manipulating "naked" Containers is not allowed. Use a specific Container type like Unit.')
        assert cls.type_code, f"Container subclasses like {cls.__name__} must override type_code"
        if not hasattr(cls, "_type_instance"):
            cls._type_instance, _ = ContainerTypeRecord.objects.get_or_create(type_code=cls.type_code)
        return cls._type_instance

    @final
    @staticmethod
    def reset_cache() -> None:
        """
        Helper for test cases that truncate the database between tests.
        Call this to delete the cache used in get_type_record(), which will be
        invalid after the ContainerTypeRecord table is truncated.
        """
        for cls in _registered_container_types.values():
            if hasattr(cls, "_type_instance"):
                del cls._type_instance

    @staticmethod
    def register_subclass(container_type: type[Container]):
        """
        Register a Container subclass
        """
        assert container_type.type_code, "Container subclasses must override type_code"
        assert container_type.type_code not in _registered_container_types, (
            f"{container_type.type_code} already registered"
        )
        _registered_container_types[container_type.type_code] = container_type
        return container_type

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
