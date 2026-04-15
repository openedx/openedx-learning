"""
Tests related to the Catalog signal handlers
"""

from datetime import datetime, timezone

import pytest

from openedx_content import api
from openedx_content.applets.publishing.signals import LEARNING_PACKAGE_ENTITIES_CHANGED

from tests.utils import capture_events

pytestmark = pytest.mark.django_db
now_time = datetime.now(tz=timezone.utc)


def test_unbatched_events() -> None:
    """
    Test that LEARNING_PACKAGE_ENTITIES_CHANGED is emitted when we change a
    publishable entity.
    """
    learning_package = api.create_learning_package(key="lp1", title="Test LP")

    entity = api.create_publishable_entity(learning_package.id, key="entity1", created=now_time, created_by=None)
    # create_publishable_entity_version also calls set_draft_version internally, so
    with capture_events(expected_count=1) as captured:
        v1 = api.create_publishable_entity_version(
            entity.id, version_num=1, title="Entity 1 V1", created=now_time, created_by=None
        )

    entity.refresh_from_db()
    assert api.get_draft_version(entity.id) == v1

    event = captured[0]
    assert event.signal is LEARNING_PACKAGE_ENTITIES_CHANGED
    assert event.kwargs["learning_package"].id == learning_package.id
    assert event.kwargs["changed_by"].user_id is None
    assert event.kwargs["change_log"].draft_change_log_id > 0
    assert event.kwargs["metadata"].time == now_time
