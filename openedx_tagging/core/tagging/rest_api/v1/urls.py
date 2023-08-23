"""
Taxonomies API v1 URLs.
"""

from rest_framework.routers import DefaultRouter

from django.urls.conf import path, include

from . import views

router = DefaultRouter()
router.register("taxonomies", views.TaxonomyView, basename="taxonomy")
router.register("object_tags", views.ObjectTagView, basename="object_tag")

urlpatterns = [path("", include(router.urls))]
