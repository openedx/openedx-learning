"""
Models that implement containers
"""
from django.db import models

from openedx_learning.apps.authoring.publishing.models import PublishableEntity, PublishableEntityVersion

from ..publishing.model_mixins import PublishableEntityMixin, PublishableEntityVersionMixin

__all__ = [
    "ContainerEntity",
    "ContainerEntityVersion",
]


class EntityList(models.Model):
    """
    EntityLists are a common structure to hold parent-child relations.

    EntityLists are not PublishableEntities in and of themselves. That's because
    sometimes we'll want the same kind of data structure for things that we
    dynamically generate for individual students (e.g. Variants). EntityLists are
    anonymous in a sense–they're pointed to by ContainerEntityVersions and
    other models, rather than being looked up by their own identifers.
    """


class EntityListRow(models.Model):
    """
    Each EntityListRow points to a PublishableEntity, optionally at a specific
    version.

    There is a row in this table for each member of an EntityList. The order_num
    field is used to determine the order of the members in the list.
    """

    entity_list = models.ForeignKey(EntityList, on_delete=models.CASCADE)

    # This ordering should be treated as immutable–if the ordering needs to
    # change, we create a new EntityList and copy things over.
    order_num = models.PositiveIntegerField()

    # Simple case would use these fields with our convention that null versions
    # means "get the latest draft or published as appropriate". These entities
    # could be Selectors, in which case we'd need to do more work to find the right
    # variant. The publishing app itself doesn't know anything about Selectors
    # however, and just treats it as another PublishableEntity.
    entity = models.ForeignKey(PublishableEntity, on_delete=models.RESTRICT)

    # The version references point to the specific PublishableEntityVersion that
    # this EntityList has for this PublishableEntity for both the draft and
    # published states. However, we don't want to have to create new EntityList
    # every time that a member is updated, because that would waste a lot of
    # space and make it difficult to figure out when the metadata of something
    # like a Unit *actually* changed, vs. when its child members were being
    # updated. Doing so could also potentially lead to race conditions when
    # updating multiple layers of containers.
    #
    # So our approach to this is to use a value of None (null) to represent an
    # unpinned reference to a PublishableEntity. It's shorthand for "just use
    # the latest draft or published version of this, as appropriate".
    entity_version = models.ForeignKey(
        PublishableEntityVersion,
        on_delete=models.RESTRICT,
        null=True,
        related_name="+",  # Do we need the reverse relation?
    )


class ContainerEntity(PublishableEntityMixin):
    """
    NOTE: We're going to want to eventually have some association between the
    PublishLog and Containers that were affected in a publish because their
    child elements were published.
    """


class ContainerEntityVersion(PublishableEntityVersionMixin):
    """
    A version of a ContainerEntity.

    By convention, we would only want to create new versions when the Container
    itself changes, and not when the Container's child elements change. For
    example:

    * Something was added to the Container.
    * We re-ordered the rows in the container.
    * Something was removed to the container.
    * The Container's metadata changed, e.g. the title.
    * We pin to different versions of the Container.

    The last looks a bit odd, but it's because *how we've defined the Unit* has
    changed if we decide to explicitly pin a set of versions for the children,
    and then later change our minds and move to a different set. It also just
    makes things easier to reason about if we say that defined_list never
    changes for a given ContainerEntityVersion.
    """

    container = models.ForeignKey(
        ContainerEntity,
        on_delete=models.CASCADE,
        related_name="versions",
    )

    # This is the EntityList that the author defines. This should never change,
    # even if the things it references get soft-deleted (because we'll need to
    # maintain it for reverts).
    defined_list = models.ForeignKey(
        EntityList,
        on_delete=models.RESTRICT,
        null=False,
        related_name="defined_list",
    )

    # inital_list is an EntityList where all the versions are pinned, to show
    # what the exact versions of the children were at the time that the
    # Container was created. We could technically derive this, but it would be
    # awkward to query.
    #
    # If the Container was defined so that all references were pinned, then this
    # can point to the exact same EntityList as defined_list.
    initial_list = models.ForeignKey(
        EntityList,
        on_delete=models.RESTRICT,
        null=False,
        related_name="initial_list",
    )

    # This is the EntityList that's created when the next ContainerEntityVersion
    # is created. All references in this list should be pinned, and it serves as
    # "the last state the children were in for this version of the Container".
    # If defined_list has only pinned references, this should point to the same
    # EntityList as defined_list and initial_list.
    #
    # This value is mutable if and only if there are unpinned references in
    # defined_list. In that case, frozen_list should start as None, and be
    # updated to pin references when another version of this Container becomes
    # the Draft version. But if this version ever becomes the Draft *again*
    # (e.g. the user hits "discard changes" or some kind of revert happens),
    # then we need to clear this back to None.
    frozen_list = models.ForeignKey(
        EntityList,
        on_delete=models.RESTRICT,
        null=True,
        default=None,
        related_name="frozen_list",
    )
