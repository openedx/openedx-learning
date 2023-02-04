from django.db import models

from .models import ComponentVersion


class ComponentVersionMixin(models.Model):
    """
    Minimal abstract model to let people attach data to ComponentVersions.

    The idea is that if you have a model that is associated with a specific
    version of a Component, the join is going to be 1:1 with a
    ComponentVersion, and potentially M:1 with your data model.

    Example that I need to think through more:

    For example, if you associate static assets with component versions, the
    same static asset may be associated with many different versions of a
    component. You could create a ComponentVersionAsset that subclasses this
    mixin and add a foreign key to an Asset model. However in this case, you'd
    want to make separate rows per-Component (because of the on_delete cascade
    cleanup behavior).
    """

    component_version = models.OneToOneField(
        ComponentVersion,
        on_delete=models.CASCADE,
        primary_key=True,
    )

    class Meta:
        abstract = True
