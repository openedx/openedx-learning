"""
Shared testing utilities for openedx-core tests.
"""

from __future__ import annotations

from contextlib import contextmanager
from dataclasses import dataclass
from typing import Generator

from django.db import transaction
from openedx_events.tooling import OpenEdxPublicSignal  # type: ignore[import-untyped]


@dataclass
class CapturedEvent:
    """A single captured event emission."""

    signal: OpenEdxPublicSignal
    kwargs: dict


@contextmanager
def capture_events(
    signals: list[OpenEdxPublicSignal] | None = None,
    expected_count: int | None = None,
) -> Generator[list[CapturedEvent], None, None]:
    """
    Context manager that captures Open edX events emitted during the block.

    Args:
        signals: Optional list of ``OpenEdxPublicSignal`` instances to monitor.
                 Defaults to all registered signals (OpenEdxPublicSignal.all_events()).
        expected_count: How many events are expected (optional). If specified,
                        will assert that the resulting list has this length.

    Yields:
        list[CapturedEvent]: A list that is populated as each event fires.
                             Each entry has a ``signal`` attribute and a ``kwargs``
                             dict containing the event data (learning_package,
                             changed_by, etc.) plus ``metadata`` and
                             ``from_event_bus``.

    Example usage::

        with capture_events(expected_count=1) as captured:
            api.do_something(entity.id, ...)

        assert captured[0].signal is ENTITIES_DRAFT_CHANGED
        assert captured[0].kwargs['learning_package'].id == learning_package.id
    """
    if signals is None:
        signals = list(OpenEdxPublicSignal.all_events())

    captured: list[CapturedEvent] = []
    receivers: dict[OpenEdxPublicSignal, object] = {}

    for signal in signals:

        def make_receiver(sig: OpenEdxPublicSignal):
            def receiver(sender, **kwargs):  # pylint: disable=unused-argument
                kwargs.pop("signal", None)
                captured.append(CapturedEvent(signal=sig, kwargs=kwargs))

            return receiver

        receiver = make_receiver(signal)
        signal.connect(receiver)
        receivers[signal] = receiver

    try:
        yield captured
    finally:
        for signal, receiver in receivers.items():
            signal.disconnect(receiver)

    if expected_count is not None:
        assert len(captured) == expected_count, (
            f"Expected {expected_count} event(s), got {len(captured)}: {[e.signal for e in captured]}"
        )


class DeliberateRollbackException(Exception):
    """Exception used to deliberately cancel and roll back a DB transaction"""


@contextmanager
def abort_transaction() -> Generator[None, None, None]:
    """
    Context manager that wraps the block in a transaction that gets rolled back.

    Example usage::

        with abort_transaction():
            api.do_something(...)

        assert nothing was done
    """
    try:
        with transaction.atomic():
            yield
            raise DeliberateRollbackException
    except DeliberateRollbackException:
        pass
