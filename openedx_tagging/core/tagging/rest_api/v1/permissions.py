"""
Tagging permissions
"""
import rules  # type: ignore[import]
from rest_framework.permissions import DjangoObjectPermissions


class TaxonomyObjectPermissions(DjangoObjectPermissions):
    """
    Maps each REST API methods to its corresponding Taxonomy permission.
    """
    perms_map = {
        "GET": ["%(app_label)s.view_%(model_name)s"],
        "OPTIONS": [],
        "HEAD": ["%(app_label)s.view_%(model_name)s"],
        "POST": ["%(app_label)s.add_%(model_name)s"],
        "PUT": ["%(app_label)s.change_%(model_name)s"],
        "PATCH": ["%(app_label)s.change_%(model_name)s"],
        "DELETE": ["%(app_label)s.delete_%(model_name)s"],
    }


class ObjectTagObjectPermissions(DjangoObjectPermissions):
    """
    Maps each REST API methods to its corresponding ObjectTag permission.
    """
    perms_map = {
        "GET": ["%(app_label)s.view_%(model_name)s"],
        "OPTIONS": [],
        "HEAD": ["%(app_label)s.view_%(model_name)s"],
        "POST": ["%(app_label)s.add_%(model_name)s"],
        "PUT": ["%(app_label)s.change_%(model_name)s"],
        "PATCH": ["%(app_label)s.change_%(model_name)s"],
        "DELETE": ["%(app_label)s.delete_%(model_name)s"],
    }


class TagListPermissions(DjangoObjectPermissions):
    """
    Permissions for Tag object views.
    """
    def has_permission(self, request, view):
        """
        Returns True if the user on the given request is allowed the given view.
        """
        if not request.user or (
            not request.user.is_authenticated and self.authenticated_users_only
        ):
            return False
        return True

    def has_object_permission(self, request, view, obj):
        """
        Returns True if the user on the given request is allowed the given view for the given object.
        """
        return rules.has_perm("oel_tagging.list_tag", request.user, obj)
