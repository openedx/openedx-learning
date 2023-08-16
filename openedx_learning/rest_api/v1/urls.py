"""
URLs for the Learning Core REST API v1
"""
from rest_framework.routers import DefaultRouter

from . import components

router = DefaultRouter()
router.register(r"components", components.ComponentViewSet, basename="component")
urlpatterns = router.urls
