"""Django rules-based permissions for tagging"""

import rules

# Global staff are taxonomy admins.
# (Superusers can already do anything)
is_taxonomy_admin = rules.is_staff


@rules.predicate
def can_view_taxonomy(user, taxonomy=None):
    """
    Anyone can view an enabled taxonomy,
    but only taxonomy admins can view a disabled taxonomy.
    """
    return (taxonomy and taxonomy.enabled) or is_taxonomy_admin(user)


@rules.predicate
def can_change_taxonomy(user, taxonomy=None):
    """
    Even taxonomy admins cannot change system taxonomies.
    """
    return is_taxonomy_admin(user) and (
        not taxonomy or not taxonomy or (taxonomy and not taxonomy.system_defined)
    )


@rules.predicate
def can_change_taxonomy_tag(user, tag=None):
    """
    Even taxonomy admins cannot add tags to system taxonomies (their tags are system-defined), or free-text taxonomies
    (these don't have predefined tags).
    """
    return is_taxonomy_admin(user) and (
        not tag
        or not tag.taxonomy
        or (
            tag.taxonomy
            and not tag.taxonomy.allow_free_text
            and not tag.taxonomy.system_defined
        )
    )


@rules.predicate
def can_change_object_tag(user, object_tag=None):
    """
    Taxonomy admins can create or modify object tags on enabled taxonomies.
    """
    return is_taxonomy_admin(user) and (
        not object_tag
        or not object_tag.taxonomy
        or (object_tag.taxonomy and object_tag.taxonomy.enabled)
    )


# Taxonomy
rules.add_perm("oel_tagging.add_taxonomy", can_change_taxonomy)
rules.add_perm("oel_tagging.change_taxonomy", can_change_taxonomy)
rules.add_perm("oel_tagging.delete_taxonomy", can_change_taxonomy)
rules.add_perm("oel_tagging.view_taxonomy", can_view_taxonomy)

# Tag
rules.add_perm("oel_tagging.add_tag", can_change_taxonomy_tag)
rules.add_perm("oel_tagging.change_tag", can_change_taxonomy_tag)
rules.add_perm("oel_tagging.delete_tag", is_taxonomy_admin)
rules.add_perm("oel_tagging.view_tag", rules.always_allow)

# ObjectTag
rules.add_perm("oel_tagging.add_object_tag", can_change_object_tag)
rules.add_perm("oel_tagging.change_object_tag", can_change_object_tag)
rules.add_perm("oel_tagging.delete_object_tag", is_taxonomy_admin)
rules.add_perm("oel_tagging.view_object_tag", rules.always_allow)
