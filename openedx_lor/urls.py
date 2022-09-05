from django.urls import include, path

urlpatterns = [
    path('authoring/v1/', include('openedx_lor.authoring.rest_api.v1.urls')),
]
