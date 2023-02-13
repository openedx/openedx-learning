"""
All Django access should be encapsulated here.
"""
from django.db.models import Q

from openedx_learning.core.components.models import ComponentVersionContent


def get_content(package_identifier, component_identifier, version_num, asset_path):
    """
    """
    cv = ComponentVersionContent.objects.select_related(
        "content",
        "component_version",
        "component_version__component",
        "component_version__component__learning_package",
    ).get(
        Q(component_version__component__learning_package__identifier=package_identifier)
        & Q(component_version__component__identifier=component_identifier)
        & Q(component_version__version_num=version_num)
        & Q(identifier=asset_path)
    )
    return cv.content
