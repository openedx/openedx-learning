"""
Is there enough commonality for this to even make sense as one app, or should
images be treated separately from downloads, e.g. ImageItem, DownloadableItem

Thought: These separate extension models aren't like subclasses, but more like
aspects. So it's not like an ImageItemVersion is a subclass of DownloadableItem,
but that some ItemVersions will have a downloadable file aspect, and some will
have an image aspect, and all those that have the image aspect will also have
the downloadable piece.
"""
from django.db import models

from openedx_learning.core.itemstore.models_api import ItemVersionDataMixin


class Asset(models.Model):
    """
    An Asset may be more than just a single file.
    """
    pass

class ItemVersionAsset(ItemVersionDataMixin):
    asset = models.ForeignKey(Asset, on_delete=models.RESTRICT, null=False)
