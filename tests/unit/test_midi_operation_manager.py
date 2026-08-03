from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor
from threading import Barrier

from midi.operation_manager import MidiOperation, MidiOperationManager, OperationToken


def test_manager_allows_only_one_concurrent_midi_operation() -> None:
    manager = MidiOperationManager()
    barrier = Barrier(8)

    def start_preview() -> OperationToken | None:
        barrier.wait()
        return manager.try_begin(MidiOperation.PREVIEW)

    with ThreadPoolExecutor(max_workers=8) as executor:
        tokens = list(executor.map(lambda _index: start_preview(), range(8)))

    acquired = [token for token in tokens if token is not None]
    assert len(acquired) == 1
    assert manager.active_operation is MidiOperation.PREVIEW
    assert manager.finish(acquired[0])
    assert manager.active_operation is MidiOperation.IDLE


def test_every_other_operation_is_rejected_while_preview_owns_midi() -> None:
    manager = MidiOperationManager()
    preview = manager.try_begin(MidiOperation.PREVIEW)
    assert preview is not None
    for operation in (
        MidiOperation.PREVIEW,
        MidiOperation.BANK_SEND,
        MidiOperation.BANK_RECEIVE,
        MidiOperation.PORT_TEST,
        MidiOperation.PORT_REFRESH,
    ):
        assert manager.try_begin(operation) is None
    assert manager.finish(preview)


def test_stale_callback_cannot_finish_a_newer_job() -> None:
    manager = MidiOperationManager()
    first = manager.try_begin(MidiOperation.PREVIEW)
    assert first is not None and manager.finish(first)
    second = manager.try_begin(MidiOperation.BANK_RECEIVE)
    assert second is not None

    assert not manager.finish(first)
    assert manager.active_token == second
    assert manager.finish(second)


def test_finish_is_idempotent_and_idle_cannot_be_started() -> None:
    manager = MidiOperationManager()
    token = manager.try_begin(MidiOperation.PORT_TEST)
    assert token is not None
    assert manager.finish(token)
    assert not manager.finish(token)

    try:
        manager.try_begin(MidiOperation.IDLE)
    except ValueError as exc:
        assert "IDLE" in str(exc)
    else:
        raise AssertionError("IDLE must not be startable")
