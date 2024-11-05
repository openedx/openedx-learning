from django.db import models

from ..containers.models_mixin import ContainerEntityMixin, ContainerEntityVersionMixin


class Unit(ContainerEntityMixin):
    """
    A Unit is Container, which is a PublishableEntity.
    """


class UnitVersion(ContainerEntityVersionMixin):
    """
    A UnitVersion is a ContainerVersion, which is a PublishableEntityVersion.
    """

    # Not sure what other metadata goes here, but we want to try to separate things
    # like scheduling information and such into different models.
    unit = models.ForeignKey(
        Unit,
        on_delete=models.CASCADE,
        related_name="versions",
    )
