from django.contrib import admin
from django.urls import include, path

urlpatterns = [
    path("admin/doc/", include("django.contrib.admindocs.urls")),
    path("admin/", admin.site.urls),
    path("media_server/", include("openedx_learning.contrib.media_server.urls")),
    path("rest_api/", include("openedx_learning.rest_api.urls")),
]
