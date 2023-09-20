"""
Taxonomies API v1 URLs.
"""

from django.urls.conf import include, path
from rest_framework.routers import DefaultRouter

from . import views

router = DefaultRouter()
router.register("taxonomies", views.TaxonomyView, basename="taxonomy")
router.register("object_tags", views.ObjectTagView, basename="object_tag")

urlpatterns = [
    path("", include(router.urls)),
    path(
        "taxonomies/<str:pk>/tags/",
        views.TaxonomyTagsView.as_view(),
        name="taxonomy-tags",
    ),
]
