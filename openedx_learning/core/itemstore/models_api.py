from django.db import models

from .models import ItemVersion


class ItemVersionDataMixin(models.Model):
    """
    Minimal abstract model to let people attach data to ItemVersions.

    The idea is that if you have a model that is associated with a 
    """
    item_version = models.OneToOneField(ItemVersion, on_delete=models.CASCADE, primary_key=True)

    class Meta:
        abstract = True
