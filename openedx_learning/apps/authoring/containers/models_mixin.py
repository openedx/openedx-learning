"""
Mixins for models that implement containers
"""
from __future__ import annotations

from typing import ClassVar, Self

from django.db import models

from openedx_learning.apps.authoring.containers.models import ContainerEntity, ContainerEntityVersion
from openedx_learning.apps.authoring.publishing.model_mixins import (
    PublishableEntityMixin,
    PublishableEntityVersionMixin,
)
from openedx_learning.lib.managers import WithRelationsManager

__all__ = [
    "ContainerEntityMixin",
    "ContainerEntityVersionMixin",
]


class ContainerEntityMixin(PublishableEntityMixin):
    """
    Convenience mixin to link your models against ContainerEntity.

    Please see docstring for ContainerEntity for more details.

    If you use this class, you *MUST* also use ContainerEntityVersionMixin
    """

    # select these related entities by default for all queries
    objects: ClassVar[WithRelationsManager[Self]] = WithRelationsManager("container_entity")  # type: ignore[assignment]

    container_entity = models.OneToOneField(
        ContainerEntity,
        on_delete=models.CASCADE,
    )

    @property
    def uuid(self):
        return self.container_entity.uuid

    @property
    def created(self):
        return self.container_entity.created

    class Meta:
        abstract = True


class ContainerEntityVersionMixin(PublishableEntityVersionMixin):
    """
    Convenience mixin to link your models against ContainerEntityVersion.

    Please see docstring for ContainerEntityVersion for more details.

    If you use this class, you *MUST* also use ContainerEntityMixin
    """

    # select these related entities by default for all queries
    objects: ClassVar[WithRelationsManager[Self]] = WithRelationsManager(  # type: ignore[assignment]
        "container_entity_version",
    )

    container_entity_version = models.OneToOneField(
        ContainerEntityVersion,
        on_delete=models.CASCADE,
    )

    @property
    def uuid(self):
        return self.container_entity_version.uuid

    @property
    def title(self):
        return self.container_entity_version.title

    @property
    def created(self):
        return self.container_entity_version.created

    @property
    def version_num(self):
        return self.container_entity_version.version_num

    class Meta:
        abstract = True
