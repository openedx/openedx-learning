from typing import NewType

from django.db import models

PublishableEntityPK = NewType("PublishableEntityPK", int)

class PublishableEntityPKField(models.BigAutoField[PublishableEntityPK, PublishableEntityPK]):
    _pyi_private_set_type: PublishableEntityPK | int  # type: ignore[assignment]
    _pyi_private_get_type: PublishableEntityPK        # type: ignore[assignment]
