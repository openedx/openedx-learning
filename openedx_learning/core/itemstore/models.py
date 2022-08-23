"""
The model hierarchy is Item -> Component -> Content.

Content is a simple model holding unversioned, raw data, along with some simple
metadata like size and MIME type.

Multiple pieces of Content may be associated with a Component. A Component is a
versioned thing that maps to a single Component Handler. This might be a Video,
a Problem, or some explanatatory HTML.

An Item is a single, coherent piece of learning material from the student's
perspective. It has one or more Components, but these Components are tightly
coupled (e.g. a Video followed by a Problem that asks a question about the
Video). Items are also versioned.
"""
from django.db import models
from django.core.validators import MaxValueValidator

from openedx_learning.lib.fields import (
    hash_field,
    identifier_field,
    immutable_uuid_field,
    manual_date_time_field,
)
from ..publishing.models import (
    LearningContext,
    LearningContextVersion,
)


class Item(models.Model):
    """
    A single piece of learning material from the student's perspective.

    An Item has an ordered list of one or more Components, but those Components
    must be tightly coupled to each other. For instance, a Video Component +
    a Problem Component that references the Video.

    Students may see the identifier of the Item in the address bar of their
    browser.
    """

    uuid = immutable_uuid_field()
    learning_context = models.ForeignKey(LearningContext, on_delete=models.CASCADE)

    # Mutable, app defined identifier.
    identifier = identifier_field()

    created = manual_date_time_field()
    modified = manual_date_time_field()

    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=["learning_context", "identifier"],
                name="item_uniq_lc_identifier",
            )
        ]

    def __str__(self):
        return f"{self.identifier}"


class ItemVersion(models.Model):
    """
    A particular version of an Item.

    A new version should be created when there is a change to the set of
    Components in a Item.
    """

    uuid = immutable_uuid_field()
    item = models.ForeignKey(Item, on_delete=models.CASCADE)
    title = models.CharField(max_length=1000, null=False, blank=True)

    component_versions = models.ManyToManyField(
        "ComponentVersion",
        through="ItemVersionComponentVersion",
        related_name="item_versions",
    )

    learning_context_versions = models.ManyToManyField(
        LearningContextVersion,
        through="LearningContextVersionItemVersion",
        related_name="item_versions",
    )


class ItemVersionComponentVersion(models.Model):
    """
    TODO: Should this have optional title?
    """
    item_version = models.ForeignKey(ItemVersion, on_delete=models.CASCADE)
    component_version = models.ForeignKey('ComponentVersion', on_delete=models.RESTRICT)
    order_num = models.PositiveIntegerField()

    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=["item_version", "order_num"],
                name="ivcv_uniq_item_component_order",
            )
        ]


class LearningContextVersionItemVersion(models.Model):
    """
    Mapping of all ItemVersions for a given LearningContextVersion.

    This answers, "What version of these items is in this version of a course?"
    There can be at most one version of a given Item for a given
    LearningContextVersion.
    """

    learning_context_version = models.ForeignKey(
        LearningContextVersion, on_delete=models.CASCADE
    )
    item_version = models.ForeignKey(ItemVersion, on_delete=models.RESTRICT)
    item = models.ForeignKey(Item, on_delete=models.RESTRICT)

    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=["learning_context_version", "item_version"],
                name="lcvsv_uniq_lcv_item_version",
            ),
            # For any given LearningContentVersion, there should be only one
            # version of an Item.
            models.UniqueConstraint(
                fields=["learning_context_version", "item"],
                name="lcvsv_uniq_lcv_item",
            ),
        ]


class Component(models.Model):
    """
    This represents any content that has ever existed in a LearningContext.

    A Component will have many ComponentVersions over time, and most metadata is
    associated with the ComponentVersion model. Make a foreign key to this model when
    you need a stable reference that will exist for as long as the
    LearningContext itself exists. It is possible for an Component to have no active
    ComponentVersion in the current LearningContextVersion (i.e. this content was at
    some point removed from the "published" version).

    An Component belongs to one and only one LearningContext.

    The UUID should be treated as immutable. The identifier field *is* mutable,
    but changing it will affect all ComponentVersions.
    """

    uuid = immutable_uuid_field()
    learning_context = models.ForeignKey(LearningContext, on_delete=models.CASCADE)

    # namespace and type work together to help figure out what Component needs
    # to handle this data. A namespace is *required*.
    namespace = models.CharField(max_length=100, null=False, blank=False)

    # type is a way to help sub-divide namespace if that's convenient. This
    # field cannot be null, but it can be blank if it's not necessary.
    type = models.CharField(max_length=100, null=False, blank=True)
    
    # identifier is local to a learning_context + namespace + type. 
    identifier = identifier_field()

    created = manual_date_time_field()
    modified = manual_date_time_field()

    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=[
                    "learning_context",
                    "namespace",
                    "type",
                    "identifier",
                ],
                name="component_uniq_lc_ns_type_identifier",
            )
        ]

    def __str__(self):
        return f"{self.identifier}"


class ComponentVersion(models.Model):
    """
    A particular version of an Component.

    A new ComponentVersion should be created anytime there is either a change to the
    content or a change to the policy around a piece of content (e.g. schedule
    change).

    Each ComponentVersion belongs to one and only one Component.

    TODO: created_by field?
    """

    uuid = immutable_uuid_field()
    component = models.ForeignKey(Component, on_delete=models.CASCADE)
    created = manual_date_time_field()

    learning_context_versions = models.ManyToManyField(
        LearningContextVersion,
        through="LearningContextVersionComponentVersion",
        related_name="component_versions",
    )
    contents = models.ManyToManyField(
        "Content",
        through="ComponentVersionContent",
        related_name="component_versions",
    )

    def __str__(self):
        return f"{self.uuid}: {self.title}"


class LearningContextVersionComponentVersion(models.Model):
    """
    Mapping of all ComponentVersion in a given LearningContextVersion.
    """

    learning_context_version = models.ForeignKey(
        LearningContextVersion, on_delete=models.CASCADE
    )
    component_version = models.ForeignKey(ComponentVersion, on_delete=models.RESTRICT)

    # component should always be derivable from component_version, but it exists
    # in this model directly because MySQL doesn't support constraint conditions
    # (see comments in the constraints section below for details).
    component = models.ForeignKey(Component, on_delete=models.RESTRICT)

    class Meta:
        constraints = [
            # The same ComponentVersion should only show up once for a given
            # LearningContextVersion.
            models.UniqueConstraint(
                fields=[
                    "learning_context_version",
                    "component_version",
                ],
                name="lcviv_uniq_lcv_cv",
            ),
            # A Component should have at most one version of itself published as
            # part of any given LearningContextVersion. Having multiple
            # ComponentVersions from the same Component in a given
            # LearningContextVersion would cause the identifiers to collide,
            # which could cause buggy behavior without much benefit.
            #
            # Ideally, we could enforce this with a constraint condition that
            # queried component_version.component, but MySQL does not support
            # this. So we waste a little extra space to help enforce data
            # integrity by adding a foreign key to the Component directly in
            # this model, and then checking the uniqueness of
            # (LearningContextVersion, Component).
            models.UniqueConstraint(
                fields=["learning_context_version", "component"],
                name="lcviv_uniq_lcv_component",
            ),
        ]


class Content(models.Model):
    """
    This is the most basic piece of raw content data, with no version metadata.

    Content stores data in an immutable Binary BLOB `data` field. This data is
    not auto-normalized in any way, meaning that pieces of content that are
    semantically equivalent (e.g. differently spaced/sorted JSON) will result in
    new entries. This model is intentionally ignorant of what these things mean,
    because it expects supplemental data models to build on top of it.

    Two Content instances _can_ have the same hash_digest if they are of
    different MIME types. For instance, an empty text file and an empty SRT file
    with both hash the same way, but be considered different entities.

    The other fields on Content are for data that is intrinsic to the file data
    itself (e.g. the size). Any smart parsing of the contents into more
    structured metadata should happen in other models that hang off of ItemInfo.

    Content models are not versioned in any way. The concept of versioning
    exists at a higher level.

    Since this model uses a BinaryField to hold its data, we have to be careful
    about scalability issues. For instance, video files should not be stored
    here directly. There is a 10 MB limit set for the moment, to accomodate
    things like PDF files and images, but the itention is for the vast majority
    of rows to be much smaller than that.
    """

    # Cap item size at 10 MB for now.
    MAX_SIZE = 10_000_000

    learning_context = models.ForeignKey(LearningContext, on_delete=models.CASCADE)
    hash_digest = hash_field()

    # Per RFC 4288, MIME type and sub-type may each be 127 chars.
    type = models.CharField(max_length=127, blank=False, null=False)
    sub_type = models.CharField(max_length=127, blank=False, null=False)

    size = models.PositiveBigIntegerField(
        validators=[MaxValueValidator(MAX_SIZE)],
    )

    # This should be manually set so that multiple Content rows being set in the
    # same transaction are created with the same timestamp. The timestamp should
    # be UTC.
    created = manual_date_time_field()

    data = models.BinaryField(null=False, max_length=MAX_SIZE)

    @property
    def mime_type(self):
        return f"{self.type}/{self.sub_type}"

    class Meta:
        constraints = [
            # Make sure we don't store duplicates of this raw data within the
            # same LearningContext, unless they're of different mime types.
            models.UniqueConstraint(
                fields=[
                    "learning_context",
                    "type",
                    "sub_type",
                    "hash_digest",
                ],
                name="content_uniq_lc_hd",
            )
        ]


class ComponentVersionContent(models.Model):
    """
    Determines the Content for a given ComponentVersion.

    An ComponentVersion may be associated with multiple pieces of binary data.
    For instance, a Video ComponentVersion might be associated with multiple
    transcripts in different languages.

    When Content is associated with an ComponentVersion, it has some local
    identifier that is unique within the the context of that ComponentVersion.
    This allows the ComponentVersion to do things like store an image file and
    reference it by a "path" identifier.

    Content is immutable and sharable across multiple ComponentVersions and even
    across LearningContexts.
    """

    component_version = models.ForeignKey(ComponentVersion, on_delete=models.CASCADE)
    content = models.ForeignKey(Content, on_delete=models.RESTRICT)
    identifier = identifier_field()

    class Meta:
        constraints = [
            # Uniqueness is only by ComponentVersion and identifier. If for some
            # reason an ComponentVersion wants to associate the same piece of content
            # with two different identifiers, that is permitted.
            models.UniqueConstraint(
                fields=["component_version", "identifier"],
                name="componentversioncontent_uniq_cv_id",
            ),
        ]
        indexes = [
            models.Index(
                fields=["content", "component_version"],
                name="componentversioncontent_c_cv",
            ),
            models.Index(
                fields=["component_version", "content"],
                name="componentversioncontent_cv_d",
            ),
        ]
