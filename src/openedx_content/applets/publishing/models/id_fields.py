from typing import NewType

from django.db import models

PublishableEntityPK = NewType("PublishableEntityPK", int)

class PublishableEntityPKField(models.BigAutoField):
    """
    Superficial subclass of models.BigAutoField that tells mypy/django-stubs to
    use `PublishableEntityPK` instead of `int`
    """
    # No implementation here - the magic is in the .pyi file.
