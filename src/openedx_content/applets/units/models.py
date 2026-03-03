"""
Models that implement units
"""

from typing import override

from django.db import models

from ..publishing.models import Container, ContainerVersion, PublishableEntity

__all__ = [
    "Unit",
    "UnitVersion",
]


@Container.register_subclass
class Unit(Container):
    """
    A Unit is type of Container that holds Components.

    Via Container and its PublishableEntityMixin, Units are also publishable
    entities and can be added to other containers.
    """

    type_code = "unit"

    container = models.OneToOneField(
        Container,
        on_delete=models.CASCADE,
        parent_link=True,
        primary_key=True,
    )

    @override
    @classmethod
    def validate_entity(cls, entity: PublishableEntity) -> None:
        """Check if the given entity is allowed as a child of a Unit"""
        # Units only allow Components as children, so the entity must be 1:1 with Component:
        # This could raise PublishableEntity.component.RelatedObjectDoesNotExist
        getattr(entity, "component")  # pylint: disable=literal-used-as-attribute


class UnitVersion(ContainerVersion):
    """
    A UnitVersion is a specific version of a Unit.

    Via ContainerVersion and its EntityList, it defines the list of Components
    in this version of the Unit.
    """

    container_version = models.OneToOneField(
        ContainerVersion,
        on_delete=models.CASCADE,
        parent_link=True,
        primary_key=True,
    )

    @property
    def unit(self):
        """Convenience accessor to the Unit this version is associated with"""
        return self.container_version.container.unit  # pylint: disable=no-member
