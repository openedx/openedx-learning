"""
Tagging permissions
"""
import rules  # type: ignore[import]
from rest_framework.permissions import DjangoObjectPermissions

from ...models import Tag, Taxonomy


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


class TagObjectPermissions(DjangoObjectPermissions):
    """
    Maps each REST API methods to its corresponding Tag permission.
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

    # This is to handle the special case for GET list of Taxonomy Tags
    def has_object_permission(self, request, view, obj):
        """
        Returns True if the user on the given request is allowed the given view for the given object.
        """
        obj = obj.taxonomy if isinstance(obj, Tag) else obj
        return rules.has_perm("oel_tagging.list_tag", request.user, obj)

    def has_permission(self, request, view):
        """
        Returns True if the request user is allowed the given view on the Taxonomy model.

        We override this method to avoid calling our view's get_queryset(), which performs database queries.
        """
        # Workaround to ensure DjangoModelPermissions are not applied
        # to the root view when using DefaultRouter.
        if getattr(view, '_ignore_model_permissions', False):
            return True

        if not request.user or (
           not request.user.is_authenticated and self.authenticated_users_only):
            return False

        queryset = Taxonomy.objects
        perms = self.get_required_permissions(request.method, queryset.model)

        return request.user.has_perms(perms)
