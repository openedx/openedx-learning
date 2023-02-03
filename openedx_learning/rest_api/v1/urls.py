from rest_framework.routers import DefaultRouter

from . import components, items

router = DefaultRouter()
router.register(r'components', components.ComponentViewSet, basename='component')
router.register(r'items', items.ItemViewSet, basename='item')
router.register(r'item_versions', items.ItemVersionViewSet, basename='item')
urlpatterns = router.urls
