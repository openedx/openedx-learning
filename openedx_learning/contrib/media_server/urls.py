"""
URLs for the media server application
"""
from django.urls import path

from .views import component_asset

urlpatterns = [
    path(
        (
            "component_asset/"
            "<str:learning_package_key>/"
            "<str:component_key>/"
            "<int:version_num>/"
            "<path:asset_path>"
        ),
        component_asset,
    )
]
