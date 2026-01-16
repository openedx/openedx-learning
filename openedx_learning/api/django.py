"""
Module for parts of the Learning Core API that exist to make it easier to use in
Django projects.
"""

def learning_core_apps_to_install():
    """
    Return all app names for appending to INSTALLED_APPS.

    This function exists to better insulate edx-platform and potential plugins
    over time, as we eventually plan to remove the backcompat apps.
    """
    return [
        "openedx_learning.apps.authoring",
        "openedx_learning.apps.authoring.backcompat.backup_restore",
        "openedx_learning.apps.authoring.backcompat.collections",
        "openedx_learning.apps.authoring.backcompat.components",
        "openedx_learning.apps.authoring.backcompat.contents",
        "openedx_learning.apps.authoring.backcompat.publishing",
        "openedx_learning.apps.authoring.backcompat.sections",
        "openedx_learning.apps.authoring.backcompat.subsections",
        "openedx_learning.apps.authoring.backcompat.units",
    ]
