""" Tagging app data models """
from django.db import models

class TagContent(models.Model):
    """
    TODO: This is a basic representation of TagContent, it may change
    depending on the discovery in:
    https://docs.google.com/document/d/13zfsGDfomSTCp_G-_ncevQHAb4Y4UW0d_6N8R2PdHlA/edit#heading=h.o6fm1hktwp7b

    This is the representation of a tag that is linked to a content

    Name-Value pair
    -----------------

    We use a Field-Value Pair representation, where `name` functions 
    as the constant that defines the field data set, and `value` functions 
    as the variable tag lineage that belong to the set.
    
    Value lineage
    ---------------

    `value` are stored as null character-delimited strings to preserve the tag's lineage. 
    We use the null character to avoid choosing a character that may exist in a tag's name.
    We don't use the Taxonomy's user-facing delimiter so that this delimiter can be changed 
    without disrupting stored tags.
    """

    # Content id to which this tag is associated
    content_id = models.CharField(max_length=255)

    # It's not usually large
    name = models.CharField(max_length=255)

    # Tag lineage value.
    #
    # The lineage can be large.
    # TODO: The length is under discussion
    value = models.CharField(max_length=765)
