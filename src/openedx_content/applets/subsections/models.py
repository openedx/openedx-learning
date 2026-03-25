"""
Models that implement subsections
"""

from typing import override

from django.core.exceptions import ValidationError
from django.db import models

from ..containers.api import get_container_subclass_of
from ..containers.models import Container, ContainerVersion
from ..publishing.models import PublishableEntity
from ..units.models import Unit

__all__ = [
    "Subsection",
    "SubsectionVersion",
]


@Container.register_subclass
class Subsection(Container):
    """
    A Subsection is type of Container that holds Units.

    Via Container and its PublishableEntityMixin, Subsections are also publishable
    entities and can be added to other containers.
    """

    type_code = "subsection"
    olx_tag_name = "sequential"  # Serializes to OLX as `<sequential>...</sequential>`.

    container = models.OneToOneField(
        Container,
        on_delete=models.CASCADE,
        parent_link=True,
        primary_key=True,
    )

    @override
    @classmethod
    def validate_entity(cls, entity: PublishableEntity) -> None:
        """Check if the given entity is allowed as a child of a Subsection"""
        # Subsections only allow Units as children, so the entity must be 1:1 with Container:
        if not hasattr(entity, "container"):
            raise ValidationError("Only Units can be added as children of a Subsection (found non-Container child)")
        if get_container_subclass_of(entity.container) is not Unit:
            raise ValidationError("Only Units can be added as children of a Subsection")


class SubsectionVersion(ContainerVersion):
    """
    A SubsectionVersion is a specific version of a Subsection.

    Via ContainerVersion and its EntityList, it defines the list of Units
    in this version of the Subsection.
    """

    container_version = models.OneToOneField(
        ContainerVersion,
        on_delete=models.CASCADE,
        parent_link=True,
        primary_key=True,
    )

    @property
    def subsection(self) -> Subsection:
        """Convenience accessor to the Subsection this version is associated with"""
        return self.container_version.container.subsection  # pylint: disable=no-member
