from django.urls import path

from .views import component_asset

urlpatterns = [
    path(
        (
            "component_asset/"
            "<str:learning_package_identifier>/"
            "<str:component_identifier>/"
            "<int:version_num>/"
            "<path:asset_path>"
        ),
        component_asset,
    )
]
