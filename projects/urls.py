from django.contrib import admin
from django.urls import include, path

urlpatterns = [
    path('admin/doc/', include('django.contrib.admindocs.urls')),
    path('admin/', admin.site.urls),
    path('', include('openedx_lor.urls'))
]
