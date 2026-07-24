from __future__ import annotations

import pytest

from d50.constants import TEMP_PATCH_BLOCK_ADDRESSES
from d50.single_patch_codec import parse_single_patch
from d50.sysex_frames import parse_dt1_frame
from midi.temporary_sender import (
    MidiTransferError,
    build_temporary_patch_plan,
    list_midi_output_ports,
    send_temporary_patch,
    test_midi_output_port as check_midi_output_port,
)


class FakePort:
    def __init__(self) -> None:
        self.frames: list[bytes] = []
        self.closed = False

    def send_sysex(self, frame: bytes) -> None:
        self.frames.append(bytes(frame))

    def close(self) -> None:
        self.closed = True


class FakeBackend:
    def __init__(self) -> None:
        self.port = FakePort()
        self.opened_name: str | None = None

    def output_names(self) -> tuple[str, ...]:
        return ("D-50 TEST OUT",)

    def open_output(self, name: str) -> FakePort:
        self.opened_name = name
        return self.port


def test_temporary_plan_targets_only_seven_buffer_blocks(valid_single_bytes: bytes) -> None:
    patch = parse_single_patch(valid_single_bytes)
    plan = build_temporary_patch_plan(patch, device_id=0x10)

    assert plan.message_count == 7
    assert plan.data_byte_count == 448
    assert plan.addresses == TEMP_PATCH_BLOCK_ADDRESSES
    assert all(parse_dt1_frame(frame).device_id == 0x10 for frame in plan.frames)


def test_sender_uses_safe_spacing_and_closes_port(valid_single_bytes: bytes) -> None:
    patch = parse_single_patch(valid_single_bytes)
    backend = FakeBackend()
    sleeps: list[float] = []
    progress: list[tuple[int, int]] = []

    report = send_temporary_patch(
        patch,
        port_name="D-50 TEST OUT",
        device_id=0x10,
        delay_ms=30,
        backend=backend,
        sleeper=sleeps.append,
        progress=lambda current, total: progress.append((current, total)),
    )

    assert backend.opened_name == "D-50 TEST OUT"
    assert len(backend.port.frames) == 7
    assert backend.port.closed
    assert sleeps == [*([0.03] * 6), 0.15]
    assert progress[-1] == (7, 7)
    assert report.message_count == 7
    assert report.data_byte_count == 448


def test_port_discovery_and_open_check_use_backend() -> None:
    backend = FakeBackend()
    assert list_midi_output_ports(backend=backend) == ("D-50 TEST OUT",)
    check_midi_output_port("D-50 TEST OUT", backend=backend)
    assert backend.port.closed


def test_sender_rejects_unsafe_settings(valid_single_bytes: bytes) -> None:
    patch = parse_single_patch(valid_single_bytes)
    with pytest.raises(ValueError, match="mindestens 20 ms"):
        send_temporary_patch(
            patch,
            port_name="D-50 TEST OUT",
            device_id=0x10,
            delay_ms=19,
            backend=FakeBackend(),
        )
    with pytest.raises(MidiTransferError, match="Kein MIDI-Ausgang"):
        send_temporary_patch(
            patch,
            port_name="",
            device_id=0x10,
            backend=FakeBackend(),
        )


class FailingClosePort(FakePort):
    def __init__(self, *, fail_send: bool) -> None:
        super().__init__()
        self.fail_send = fail_send
        self.close_calls = 0

    def send_sysex(self, frame: bytes) -> None:
        if self.fail_send:
            raise RuntimeError("send failure")
        super().send_sysex(frame)

    def close(self) -> None:
        self.close_calls += 1
        raise RuntimeError("close failure")


class SinglePortBackend(FakeBackend):
    def __init__(self, port: FakePort) -> None:
        self.port = port
        self.opened_name = None


def test_close_error_does_not_hide_primary_send_error(valid_single_bytes: bytes) -> None:
    patch = parse_single_patch(valid_single_bytes)
    port = FailingClosePort(fail_send=True)

    with pytest.raises(MidiTransferError, match="send failure"):
        send_temporary_patch(
            patch,
            port_name="D-50 TEST OUT",
            device_id=0,
            backend=SinglePortBackend(port),
            sleeper=lambda _seconds: None,
        )
    assert port.close_calls == 1


def test_close_error_is_reported_when_send_succeeded(valid_single_bytes: bytes) -> None:
    patch = parse_single_patch(valid_single_bytes)
    port = FailingClosePort(fail_send=False)

    with pytest.raises(MidiTransferError, match="geschlossen"):
        send_temporary_patch(
            patch,
            port_name="D-50 TEST OUT",
            device_id=0,
            backend=SinglePortBackend(port),
            sleeper=lambda _seconds: None,
        )
    assert port.close_calls == 1


def test_sender_emits_bounded_diagnostics_without_sysex_hex(valid_single_bytes: bytes) -> None:
    patch = parse_single_patch(valid_single_bytes)
    messages: list[str] = []

    send_temporary_patch(
        patch,
        port_name="D-50 TEST OUT",
        device_id=0,
        backend=FakeBackend(),
        sleeper=lambda _seconds: None,
        job_id=17,
        diagnostic=messages.append,
    )

    assert messages[0].startswith("[TX PREVIEW #17] Start")
    assert sum("Frame " in message for message in messages) == 7
    assert "address=00-03-00 data=64 Byte" in messages[-2]
    assert messages[-1].startswith("[TX PREVIEW #17] Complete")
