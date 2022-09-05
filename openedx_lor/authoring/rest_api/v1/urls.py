from rest_framework.routers import DefaultRouter

from . import components, items, libraries

router = DefaultRouter()
router.register(r'components', components.ComponentViewSet, basename='component')
router.register(r'items', items.ItemViewSet, basename='item')
router.register(r'libraries', libraries.LibraryViewSet, basename='library')
urlpatterns = router.urls
