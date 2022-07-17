"""
THIS IS NON-FUNCTIONING scratch code at the moment.

There are broadly three types of UserPartitions:

1. Partitions that are global to a LearningContextType.
2. Partitions that are specific to a LearningContextVersion.

"""
from django.db import models

# from ..publish.models import LearningObjectVersion

from openedx_learning.lib.fields import hash_field, identifier_field, immutable_uuid_field

"""
class LearningContextTypePartitionGroup(models.Model):
    learning_context_type = models.ForeignKey(LearningContextType, on_delete=models.CASCADE)
    partition_id = models.BigIntegerField(null=False)
    group_id = models.BigIntegerField(null=False)


class LearningContextVersionPartitionGroup(models.Model):
    learning_context_version = models.ForeignKey(LearningContextVersion, on_delete=models.CASCADE)
    partition_id = models.BigIntegerField(null=False)
    group_id = models.BigIntegerField(null=False)
"""


#class Block(models.Model):
#    """
#    A Block is the simplest possible piece of content. It has no children.#
#    How do we decompose this? Separate tables for different aspects, like grades?
#    """
#
#    learning_object_version = models.ForeignKey(LearningObjectVersion, on_delete=models.CASCADE)


class Unit(models.Model):
    identifier = identifier_field()


class UnitVersion(models.Model):
    uuid = immutable_uuid_field()
    identifier = identifier_field()
    hash = hash_field()


class UnitContentBlock(models.Model):


    pass



class Partition(models.Model):
    """
    Each row represents a Partition for dividing content into PartitionGroups.

    UserPartitions is a pluggable interface. Some IDs are static (with values
    less than 100). Others are dynamic, picking a range between 100 and 2^31-1.
    That means that technically, we could use IntegerField instead of
    BigIntegerField, but a) that limit isn't actually enforced as far as I can
    tell; and b) it's not _that_ much extra storage, so I'm using BigInteger
    instead (2^63-1).

    It's a pluggable interface (entry points: openedx.user_partition_scheme,
    openedx.dynamic_partition_generator), so there's no "UserPartition" model.
    We need to actually link this against the values passed back from the
    partitions service in order to map them to names and descriptions.
    Any CourseSection or CourseSectionSequence may be associated with any number
    of UserPartitionGroups. An individual _user_ may only be in one Group for
    any given User Partition, but a piece of _content_ can be associated with
    multiple groups. So for instance, for the Enrollment Track user partition,
    a piece of content may be associated with both "Verified" and "Masters"
    tracks, while a user may only be in one or the other.
    """
    partition_num = models.BigIntegerField(null=False)
    

class PartitionGroup(models.Model):
    """
    """
    partition = models.ForeignKey(Partition, on_delete=models.CASCADE)
    group_num = models.BigIntegerField(null=False)

    class Meta:
        constraints = [
            models.UniqueConstraint(
                name='unique_ol_publishing_partition_partition_group_num',
                fields=['partition_id', 'group_num'],
            ),
        ]
