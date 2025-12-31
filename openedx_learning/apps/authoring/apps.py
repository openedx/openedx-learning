from django.apps import AppConfig

class AuthoringConfig(AppConfig):
    name = "openedx_learning.apps.authoring"
    verbose_name = "Learning Core > Authoring"
    default_auto_field = "django.db.models.BigAutoField"
    label = "oel_authoring"

    def ready(self):
        from .api import register_publishable_models
        from .models import (
            Component, ComponentVersion,
            Container, ContainerVersion,
            Section, SectionVersion,
            Subsection, SubsectionVersion,
            Unit, UnitVersion,
        )
        register_publishable_models(Component, ComponentVersion)
        register_publishable_models(Container, ContainerVersion)
        register_publishable_models(Section, SectionVersion)
        register_publishable_models(Subsection, SubsectionVersion)
        register_publishable_models(Unit, UnitVersion)
