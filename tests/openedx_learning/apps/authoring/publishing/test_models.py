"""
Tests related to the Publishing model mixins
"""
from typing import TYPE_CHECKING, assert_type

from openedx_learning.apps.authoring.publishing.models import PublishableEntityMixin, PublishableEntityVersionMixin
from openedx_learning.lib.managers import WithRelationsManager

if TYPE_CHECKING:
    # Test that our mixins provide the right typing for 'objects'
    class FooEntity(PublishableEntityMixin):
        pass

    assert_type(FooEntity.objects.create(), FooEntity)
    assert_type(FooEntity.objects, WithRelationsManager[FooEntity])

    class FooEntityVersion(PublishableEntityVersionMixin):
        pass

    assert_type(FooEntityVersion.objects.create(), FooEntityVersion)
    assert_type(FooEntityVersion.objects, WithRelationsManager[FooEntityVersion])
