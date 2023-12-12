"""
TLDR Guidelines:

1. DO NOT modify these models to store full version snapshots.
2. DO NOT use these models to try to reconstruct historical versions of
   Collections for fast querying.

If you're trying to do either of these things, you probably want a new model or
app. For more details, read on.

The goal of these models is to provide a lightweight method of organizing
PublishableEntities. The first use case for this is modeling the structure of a
v1 Content Library within a LearningPackage. This is what we'll use the
Collection model for.

An important thing to note here is that Collections are *NOT* publishable
entities themselves. They have no "Draft" or "Published" versions. Collections
are never "published", though the things inside of them are.

When a LibraryContentBlock makes use of a Content Library, it copies all of
the items it will use into the Course itself. It will also store a version
on the LibraryContentBlock–this is a MongoDB ObjectID in v1 and an integer in
v2 Libraries. Later on, the LibraryContentBlock will want to check back to see
if any updates have been made, using its version as a key. If a new version
exists, the course team has the option of re-copying data from the Library.

ModuleStore based v1 Libraries and Blockstore-based v2 libraries both version
the entire library in a series of snapshots. This makes it difficult to have
very large libraries, which is an explicit goal for Modular Learning. In
Learning Core, we've moved to tracking the versions of individual Components to
address this issue. But that means we no longer have a single version indicator
for "has anything here changed"?

We *could* have put that version in the ``publishing`` app's PublishLog, but
that would make it too broad. We want the ability to eventually collapse many v1
Libraries into a single Learning Core backed v2 Library. If we tracked the
versioning in only a central location, then we'd have many false positives where
the version was bumped because something else in the Learning Package changed.
So instead, we're creating a new Collection model inside the LearningPackage to
track that concept.

A critical takeaway is that we don't have to store snapshots of every version of
a Collection, because that data has been copied over by the LibraryContentBlock.
We only need to store the current state of the Collection, and increment the
version numbers when changes happen. This will allow the LibraryContentBlock to
check in and re-copy over the latest version if the course team desires.

That's why these models only store the current state of a Collection. Unlike the
``components`` app,  ``collections`` does not store fully materialized snapshots
of past versions. This is done intentionally in order to save space and reduce
the cost of writes. Collections may grow to be very large, and we don't want to
be writing N rows with every version, where N is the number of
PublishableEntities in a Collection.

These models do store changesets, where the number of rows grows in proportion
to the number of things that are actually changing (instead of copying over
everything on every version). This is intended to make it easier to figure out
what changed between two given versions of a Collection. A LibraryContentBlock
in a course will have stored the version number of the last time it copied data
from the Collection, and we can eventually surface this data to the user.

While it's possible to reconstruct past versions of Collections based off of
this changeset data, it's going to be a very slow process to do so, and it is
strongly discouraged.
"""
from __future__ import annotations

from django.conf import settings
from django.core.validators import MinValueValidator
from django.db import models

from ..publishing.models import (
    LearningPackage,
    PublishableEntity,
    PublishableEntityVersion,
    PublishLogRecord,
)

from openedx_learning.lib.fields import (
    case_insensitive_char_field,
    immutable_uuid_field,
    key_field,
    manual_date_time_field,
)


class Collection(models.Model):
    """
    A Collection is a tracked grouping of PublishableEntities.
    """
    uuid = immutable_uuid_field()
    learning_package = models.ForeignKey(LearningPackage, on_delete=models.CASCADE)
    key = key_field()

    title = case_insensitive_char_field(max_length=500, blank=True, default="")
    created = manual_date_time_field()
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
    )

    publishable_entities: models.ManyToManyField[
            PublishableEntity, CollectionPublishableEntity
        ] = models.ManyToManyField(
        PublishableEntity,
        through="CollectionPublishableEntity",
        related_name="collections",
    )

    class Meta:
        constraints = [
            # The version_num must be unique for any given Collection.
            models.UniqueConstraint(
                fields=[
                    "learning_package",
                    "key",
                ],
                name="oel_collections_col_uniq_lp_key",
            )
        ]

    def __str__(self):
        return f"Collection {self.key} ({self.uuid})"


class CollectionPublishableEntity(models.Model):
    """
    Collection -> PublishableEntity association.
    """
    collection = models.ForeignKey(
        Collection,
        on_delete=models.CASCADE,
    )
    entity = models.ForeignKey(
        PublishableEntity,
        on_delete=models.CASCADE,
    )

    class Meta:
        constraints = [
            # Prevent race conditions from making multiple rows associating the
            # same Collection to the same Entity.
            models.UniqueConstraint(
                fields=[
                    "collection",
                    "entity",
                ],
                name="oel_collections_cpe_uniq_col_ent",
            )
        ]


class CollectionChangeSet(models.Model):
    """
    Represents an atomic set of changes to a Collection.

    There are currently three ways a Collection can change:

    1. PublishableEntities are added (AddToCollection)
    2. PublishableEntities are removed (RemoveFromCollection)
    3. The published version of a PublishableEntity changes (PublishLogRecord)
    """
    collection = models.ForeignKey(
        Collection, on_delete=models.CASCADE, related_name="change_sets"
    )
    version_num = models.PositiveBigIntegerField(
        null=False,
        validators=[MinValueValidator(1)],
    )
    created = manual_date_time_field()

    class Meta:
        constraints = [
            # The version_num must be unique for any given Collection.
            models.UniqueConstraint(
                fields=[
                    "collection",
                    "version_num",
                ],
                name="oel_collections_ccs_uniq_col_vn",
            )
        ]


class AddToCollection(models.Model):
    """
    A record for when a PublishableEntity is added to a Collection.

    We also record the published version of the PublishableEntity at the time
    it's added to the Collection. This will make it easier to reconstruct the
    state of a given version of a Collection if it's necessary to do so.

    Note that something may be removed from a Collection and then re-added at a
    later time.
    """
    change_set = models.ForeignKey(CollectionChangeSet, on_delete=models.CASCADE)
    entity = models.ForeignKey(PublishableEntity, on_delete=models.CASCADE)

    # We want to capture the published version of the entity at the time it's
    # added to the Collection. This may be null for entities that have not yet
    # been published.
    published_version = models.ForeignKey(
        PublishableEntityVersion, on_delete=models.CASCADE, null=True,
    )

    class Meta:
        constraints = [
            # We can't add the same Entity more than once in the same ChangeSet.
            models.UniqueConstraint(
                fields=[
                    "change_set",
                    "entity",
                ],
                name="oel_collections_aetc_uniq_cs_ent",
            )
        ]

    def __str__(self):
        return f"Add {self.entity_id} in changeset {self.change_set_id}"


class RemoveFromCollection(models.Model):
    """
    A record for when a PublishableEntity is removed from a Collection.

    Note that something may be removed from a Collection, re-added at a later
    time, and then removed again.
    """
    change_set = models.ForeignKey(CollectionChangeSet, on_delete=models.CASCADE)
    entity = models.ForeignKey(PublishableEntity, on_delete=models.CASCADE)

    class Meta:
        constraints = [
            # We can't add the same Entity more than once in the same ChangeSet.
            models.UniqueConstraint(
                fields=[
                    "change_set",
                    "entity",
                ],
                name="oel_collections_refc_uniq_cs_ent",
            )
        ]


class PublishEntity(models.Model):
    """
    A record for when the published version of a PublishableEntity changes.
    """
    change_set = models.ForeignKey(CollectionChangeSet, on_delete=models.CASCADE)
    log_record = models.ForeignKey(PublishLogRecord, on_delete=models.CASCADE)

    class Meta:
        constraints = [
            # The same PublishLogRecord shouldn't show up multiple times for the
            # same ChangeSet.
            models.UniqueConstraint(
                fields=[
                    "change_set",
                    "log_record",
                ],
                name="oel_collections_pe_uniq_cs_lr",
            )
        ]
