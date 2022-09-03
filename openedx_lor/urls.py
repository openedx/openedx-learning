from django.urls import include, path

urlpatterns = [
    path('authoring/', include('openedx_lor.authoring.urls')),
]
