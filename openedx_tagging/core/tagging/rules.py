"""
Django rules-based permissions for tagging
"""
from __future__ import annotations

from typing import Callable, Union

import django.contrib.auth.models
# typing support in rules depends on https://github.com/dfunckt/django-rules/pull/177
import rules  # type: ignore

from .models import ObjectTag, Tag, Taxonomy

UserType = Union[django.contrib.auth.models.User, django.contrib.auth.models.AnonymousUser]


# Global staff are taxonomy admins.
# (Superusers can already do anything)
is_taxonomy_admin: Callable[[UserType], bool] = rules.is_staff


@rules.predicate
def can_view_taxonomy(user: UserType, taxonomy: Taxonomy | None = None) -> bool:
    """
    Anyone can view an enabled taxonomy or list all taxonomies,
    but only taxonomy admins can view a disabled taxonomy.
    """
    return not taxonomy or taxonomy.cast().enabled or is_taxonomy_admin(user)


@rules.predicate
def can_change_taxonomy(user: UserType, taxonomy: Taxonomy | None = None) -> bool:
    """
    Even taxonomy admins cannot change system taxonomies.
    """
    return is_taxonomy_admin(user) and (
        not taxonomy or bool(taxonomy and not taxonomy.cast().system_defined)
    )


@rules.predicate
def can_change_tag(user: UserType, tag: Tag | None = None) -> bool:
    """
    Even taxonomy admins cannot add tags to system taxonomies (their tags are system-defined), or free-text taxonomies
    (these don't have predefined tags).
    """
    taxonomy = tag.taxonomy.cast() if (tag and tag.taxonomy) else None
    return is_taxonomy_admin(user) and (
        not tag
        or not taxonomy
        or (taxonomy and not taxonomy.allow_free_text and not taxonomy.system_defined)
    )


@rules.predicate
def can_change_object_tag(user: UserType, object_tag: ObjectTag | None = None) -> bool:
    """
    Taxonomy admins can create or modify object tags on enabled taxonomies.
    """
    taxonomy = (
        object_tag.taxonomy.cast() if (object_tag and object_tag.taxonomy) else None
    )
    object_tag = taxonomy.object_tag_class.cast(object_tag) if taxonomy else object_tag
    return is_taxonomy_admin(user) and (
        not object_tag or not taxonomy or (taxonomy and taxonomy.enabled)
    )


# Taxonomy
rules.add_perm("oel_tagging.add_taxonomy", can_change_taxonomy)
rules.add_perm("oel_tagging.change_taxonomy", can_change_taxonomy)
rules.add_perm("oel_tagging.delete_taxonomy", can_change_taxonomy)
rules.add_perm("oel_tagging.view_taxonomy", can_view_taxonomy)

# Tag
rules.add_perm("oel_tagging.add_tag", can_change_tag)
rules.add_perm("oel_tagging.change_tag", can_change_tag)
rules.add_perm("oel_tagging.delete_tag", is_taxonomy_admin)
rules.add_perm("oel_tagging.view_tag", rules.always_allow)

# ObjectTag
rules.add_perm("oel_tagging.add_objecttag", can_change_object_tag)
rules.add_perm("oel_tagging.change_objecttag", can_change_object_tag)
rules.add_perm("oel_tagging.delete_objecttag", is_taxonomy_admin)
rules.add_perm("oel_tagging.view_objecttag", rules.always_allow)
