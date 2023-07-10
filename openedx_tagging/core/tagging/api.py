""""
Tagging API

Anyone using the openedx_tagging app should use these APIs instead of creating
or modifying the models directly, since there might be other related model
changes that you may not know about.

No permissions/rules are enforced by these methods -- these must be enforced in the views.

Please look at the models.py file for more information about the kinds of data
are stored in this app.
"""
from typing import Iterator, List, Type, Union

from django.db.models import QuerySet
from django.utils.translation import gettext_lazy as _

from .models import ClosedObjectTag, ObjectTag, OpenObjectTag, Tag, Taxonomy
from .registry import get_object_tag_class


def create_taxonomy(
    name: str,
    description: str = None,
    enabled=True,
    required=False,
    allow_multiple=False,
    allow_free_text=False,
    object_tag_class: Type = None,
) -> Taxonomy:
    """
    Creates, saves, and returns a new Taxonomy with the given attributes.
    """
    taxonomy = Taxonomy(
        name=name,
        description=description,
        enabled=enabled,
        required=required,
        allow_multiple=allow_multiple,
        allow_free_text=allow_free_text,
    )
    if object_tag_class:
        taxonomy.object_tag_class = object_tag_class
    taxonomy.save()
    return taxonomy


def get_taxonomy(id: int) -> Union[Taxonomy, None]:
    """
    Returns a Taxonomy of the appropriate subclass which has the given ID.
    """
    return Taxonomy.objects.filter(id=id).first()


def get_taxonomies(enabled=True) -> QuerySet:
    """
    Returns a queryset containing the enabled taxonomies, sorted by name.
    If you want the disabled taxonomies, pass enabled=False.
    If you want all taxonomies (both enabled and disabled), pass enabled=None.
    """
    queryset = Taxonomy.objects.order_by("name", "id")
    if enabled is None:
        return queryset.all()
    return queryset.filter(enabled=enabled)


def get_tags(taxonomy: Taxonomy) -> List[Tag]:
    """
    Returns a list of predefined tags for the given taxonomy.

    Note that if the taxonomy allows free-text tags, then the returned list will be empty.
    """
    return taxonomy.get_tags()


def cast_object_tag(object_tag: ObjectTag) -> ObjectTag:
    """
    Casts/copies the given object tag data into the ObjectTag subclass most appropriate for this tag.

    E.g. if the tag's taxonomy has a custom ObjectTag class it prefers, use that.
    Recommends using OpenObjectTag by default, because that is the least restrictive type.
    """
    ObjectTagClass = get_object_tag_class(
        taxonomy=object_tag.taxonomy,
        object_type=object_tag.object_type,
        object_id=object_tag.object_id,
        tag=object_tag.tag,
        value=object_tag.value,
        name=object_tag.name,
    )
    new_object_tag = ObjectTagClass().copy(object_tag)
    return new_object_tag


def resync_object_tags(object_tags: QuerySet = None) -> int:
    """
    Reconciles ObjectTag entries with any changes made to their associated taxonomies and tags.

    By default, we iterate over all ObjectTags. Pass a filtered ObjectTags queryset to limit which tags are resynced.
    """
    if not object_tags:
        object_tags = ObjectTag.objects.select_related("tag", "taxonomy")

    num_changed = 0
    for tag in object_tags:
        object_tag = cast_object_tag(tag)
        changed = object_tag.resync()
        if changed:
            object_tag.save()
            num_changed += 1
    return num_changed


def get_object_tags(
    object_id: str, object_type: str = None, taxonomy: Taxonomy = None, valid_only=True
) -> Iterator[ObjectTag]:
    """
    Generates a list of object tags for a given object.

    Pass taxonomy to limit the returned object_tags to a specific taxonomy.

    Pass valid_only=False when displaying tags to content authors, so they can see invalid tags too.
    Invalid tags will (probably) be hidden from learners.
    """
    tags = (
        ObjectTag.objects.filter(
            object_id=object_id,
        )
        .select_related("tag", "taxonomy")
        .order_by("id")
    )
    if object_type:
        tags = tags.filter(object_type=object_type)
    if taxonomy:
        tags = tags.filter(taxonomy=taxonomy)

    for tag in tags:
        # We can only validate tags with taxonomies, because we need the object_tag_class
        object_tag = cast_object_tag(tag)
        if not valid_only or object_tag.is_valid():
            yield object_tag


def tag_object(
    taxonomy: Taxonomy, tags: List, object_id: str, object_type: str
) -> List[ObjectTag]:
    """
    Replaces the existing ObjectTag entries for the given taxonomy + object_id with the given list of tags.

    If taxonomy.allows_free_text, then the list should be a list of tag values.
    Otherwise, it should be a list of existing Tag IDs.

    Raised ValueError if the proposed tags are invalid for this taxonomy.
    Preserves existing (valid) tags, adds new (valid) tags, and removes omitted (or invalid) tags.
    """

    if not taxonomy.allow_multiple and len(tags) > 1:
        raise ValueError(_(f"Taxonomy ({taxonomy.id}) only allows one tag per object."))

    if taxonomy.required and len(tags) == 0:
        raise ValueError(
            _(f"Taxonomy ({taxonomy.id}) requires at least one tag per object.")
        )

    current_tags = {
        tag.tag_ref: tag
        for tag in ObjectTag.objects.filter(
            taxonomy=taxonomy, object_id=object_id, object_type=object_type
        )
    }
    updated_tags = []
    for tag_ref in tags:
        if tag_ref in current_tags:
            object_tag = cast_object_tag(current_tags.pop(tag_ref))
        else:
            try:
                tag = taxonomy.tag_set.get(
                    id=tag_ref,
                )
                value = tag.value
            except (ValueError, Tag.DoesNotExist):
                # This might be ok, e.g. if taxonomy.allow_free_text.
                # We'll validate below before saving.
                tag = None
                value = tag_ref

            ObjectTagClass = get_object_tag_class(
                taxonomy=taxonomy,
                object_id=object_id,
                object_type=object_type,
                tag=tag,
                value=value,
                name=taxonomy.name,
            )
            object_tag = ObjectTagClass()
            object_tag.taxonomy = taxonomy
            object_tag.tag = tag
            object_tag.object_id = object_id
            object_tag.object_type = object_type
            object_tag.value = value

        object_tag.resync()
        if not object_tag.is_valid():
            raise ValueError(
                _(f"Invalid object tag for taxonomy ({taxonomy.id}): {object_tag}")
            )
        updated_tags.append(object_tag)

    # Save all updated tags at once to avoid partial updates
    for object_tag in updated_tags:
        object_tag.save()

    # ...and delete any omitted existing tags
    for old_tag in current_tags.values():
        old_tag.delete()

    return updated_tags
