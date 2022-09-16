from rest_framework.routers import DefaultRouter

from . import components, items

router = DefaultRouter()
router.register(r'components', components.ComponentViewSet, basename='component')
router.register(r'items', items.ItemViewSet, basename='item')
urlpatterns = router.urls
