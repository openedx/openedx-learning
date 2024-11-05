from __future__ import annotations

from django.db import models

from openedx_learning.apps.authoring.containers.models import (
    ContainerEntity,
    ContainerEntityVersion,
)

from django.db.models.query import QuerySet

from openedx_learning.apps.authoring.publishing.model_mixins import (
    PublishableEntityMixin,
    PublishableEntityVersionMixin,
)

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

    class ContainerEntityMixinManager(models.Manager):
        def get_queryset(self) -> QuerySet:
            return (
                super()
                .get_queryset()
                .select_related(
                    "container_entity",
                )
            )

    objects: models.Manager[ContainerEntityMixin] = ContainerEntityMixinManager()

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

    class ContainerEntityVersionMixinManager(models.Manager):
        def get_queryset(self) -> QuerySet:
            return (
                super()
                .get_queryset()
                .select_related(
                    "container_entity_version",
                )
            )

    objects: models.Manager[ContainerEntityVersionMixin] = (
        ContainerEntityVersionMixinManager()
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
