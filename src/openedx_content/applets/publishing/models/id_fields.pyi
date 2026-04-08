"""Type-only overrides/definitions of `id_fields`.py"""

from typing import NewType

from django.db import models

PublishableEntityPK = NewType("PublishableEntityPK", int)
LearningPackagePK = NewType("LearningPackagePK", int)

class PublishableEntityPKField(models.BigAutoField[PublishableEntityPK, PublishableEntityPK]):
    _pyi_private_set_type: PublishableEntityPK | int  # type: ignore[assignment]
    _pyi_private_get_type: PublishableEntityPK  # type: ignore[assignment]

class LearningPackagePKField(models.BigAutoField[LearningPackagePK, LearningPackagePK]):
    _pyi_private_set_type: LearningPackagePK | int  # type: ignore[assignment]
    _pyi_private_get_type: LearningPackagePK  # type: ignore[assignment]
