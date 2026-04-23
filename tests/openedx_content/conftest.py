"""Shared fixtures for openedx_content tests."""

import pytest
from celery import current_app  # type: ignore[import]


@pytest.fixture(autouse=True)
def _celery_task_always_eager():
    """
    Run Celery tasks synchronously so per-entity CONTENT_OBJECT_ASSOCIATIONS_CHANGED
    events fire inline during tests without needing a real broker.
    """
    current_app.conf.task_always_eager = True
    yield
    current_app.conf.task_always_eager = False
