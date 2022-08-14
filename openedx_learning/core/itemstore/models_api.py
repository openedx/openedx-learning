from django.db import models

from .models import ComponentVersion


class ComponentVersionDataMixin(models.Model):
    """
    Minimal abstract model to let people attach data to ComponentVersions.

    The idea is that if you have a model that is associated with a specific
    version of an item, the join is going to be 1:1 with an ComponentVersion, and
    potentially M:1 with your data model.
    """
    component_version = models.OneToOneField(
        ComponentVersion,
        on_delete=models.CASCADE,
        primary_key=True,
    )

    class Meta:
        abstract = True
