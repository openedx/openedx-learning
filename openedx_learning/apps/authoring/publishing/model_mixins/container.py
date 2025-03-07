"""
ContainerMixin and ContainerVersionMixin
"""
from __future__ import annotations

from datetime import datetime
from typing import TYPE_CHECKING, ClassVar, Self

from django.db import models

from openedx_learning.lib.managers import WithRelationsManager

from .publishable_entity import PublishableEntityMixin, PublishableEntityVersionMixin

if TYPE_CHECKING:
    from ..models.container import Container, ContainerVersion
else:
    # To avoid circular imports, we need to reference these models using strings only
    Container = "oel_publishing.Container"
    ContainerVersion = "oel_publishing.ContainerVersion"

__all__ = [
    "ContainerMixin",
    "ContainerVersionMixin",
]


class ContainerMixin(PublishableEntityMixin):
    """
    Convenience mixin to link your models against Container.

    Please see docstring for Container for more details.

    If you use this class, you *MUST* also use ContainerVersionMixin
    """

    # select these related entities by default for all queries
    objects: ClassVar[WithRelationsManager[Self]] = WithRelationsManager(  # type: ignore[assignment]
        "container",
        "publishable_entity",
        "publishable_entity__published",
        "publishable_entity__draft",
    )

    container = models.OneToOneField(
        Container,
        on_delete=models.CASCADE,
    )

    @property
    def uuid(self) -> str:
        return self.container.uuid

    @property
    def created(self) -> datetime:
        return self.container.created

    class Meta:
        abstract = True


class ContainerVersionMixin(PublishableEntityVersionMixin):
    """
    Convenience mixin to link your models against ContainerVersion.

    Please see docstring for ContainerVersion for more details.

    If you use this class, you *MUST* also use ContainerMixin
    """

    # select these related entities by default for all queries
    objects: ClassVar[WithRelationsManager[Self]] = WithRelationsManager(  # type: ignore[assignment]
        "container_version",
    )

    container_version = models.OneToOneField(
        ContainerVersion,
        on_delete=models.CASCADE,
    )

    @property
    def uuid(self) -> str:
        return self.container_version.uuid

    @property
    def title(self) -> str:
        return self.container_version.title

    @property
    def created(self) -> datetime:
        return self.container_version.created

    @property
    def version_num(self):
        return self.container_version.version_num

    class Meta:
        abstract = True
