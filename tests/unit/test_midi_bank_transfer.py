from __future__ import annotations

from collections import deque

import pytest

from d50.addresses import add_to_address
from d50.bank_codec import bank_payload, parse_bank
from d50.constants import (
    ACK_COMMAND_ID,
    DAT_COMMAND_ID,
    EOD_COMMAND_ID,
    FULL_BANK_PAYLOAD_SIZE,
    FULL_BANK_START,
    MAX_DT1_DATA_BYTES,
    WSD_COMMAND_ID,
)
from d50.handshake import (
    build_dat_frame,
    build_handshake_control,
    build_handshake_request,
    parse_handshake_frame,
)
from midi.bank_transfer import FULL_BANK_SIZE, receive_full_bank_handshake, send_full_bank_handshake
from midi.temporary_sender import MidiTransferError


class FakeInput:
    def __init__(self, frames: tuple[bytes, ...] = ()) -> None:
        self.frames = deque(frames)
        self.closed = False

    def poll_sysex(self) -> bytes | None:
        return self.frames.popleft() if self.frames else None

    def close(self) -> None:
        self.closed = True


class FakeOutput:
    def __init__(
        self,
        input_port: FakeInput,
        *,
        acknowledge_sends: bool,
        echo_sends: bool = False,
        close_error: Exception | None = None,
    ) -> None:
        self.input_port = input_port
        self.acknowledge_sends = acknowledge_sends
        self.echo_sends = echo_sends
        self.close_error = close_error
        self.frames: list[bytes] = []
        self.closed = False

    def send_sysex(self, frame: bytes) -> None:
        self.frames.append(bytes(frame))
        if self.echo_sends:
            self.input_port.frames.append(bytes(frame))
        if self.acknowledge_sends:
            command = parse_handshake_frame(frame).command
            if command in {WSD_COMMAND_ID, DAT_COMMAND_ID, EOD_COMMAND_ID}:
                self.input_port.frames.append(build_handshake_control(ACK_COMMAND_ID, device_id=0))

    def close(self) -> None:
        self.closed = True
        if self.close_error is not None:
            raise self.close_error


class FakeDuplexBackend:
    def __init__(
        self,
        incoming: tuple[bytes, ...] = (),
        *,
        acknowledge_sends: bool = False,
        echo_sends: bool = False,
        output_close_error: Exception | None = None,
    ) -> None:
        self.input = FakeInput(incoming)
        self.output = FakeOutput(
            self.input,
            acknowledge_sends=acknowledge_sends,
            echo_sends=echo_sends,
            close_error=output_close_error,
        )

    def input_names(self) -> tuple[str, ...]:
        return ("D-50 IN",)

    def output_names(self) -> tuple[str, ...]:
        return ("D-50 OUT",)

    def open_input(self, _name: str) -> FakeInput:
        return self.input

    def open_output(self, _name: str) -> FakeOutput:
        return self.output


def _handshake_dump(payload: bytes) -> tuple[bytes, ...]:
    frames = [build_handshake_request(WSD_COMMAND_ID, FULL_BANK_START, FULL_BANK_SIZE, device_id=0)]
    frames.extend(
        build_dat_frame(
            add_to_address(FULL_BANK_START, offset),
            payload[offset : offset + MAX_DT1_DATA_BYTES],
            device_id=0,
        )
        for offset in range(0, len(payload), MAX_DT1_DATA_BYTES)
    )
    frames.append(build_handshake_control(EOD_COMMAND_ID, device_id=0))
    return tuple(frames)


def test_full_bank_sender_uses_acknowledged_handshake(valid_bank_bytes: bytes) -> None:
    bank = parse_bank(valid_bank_bytes)
    backend = FakeDuplexBackend(acknowledge_sends=True)
    progress: list[tuple[str, int, int]] = []

    report = send_full_bank_handshake(
        bank,
        output_port_name="D-50 OUT",
        input_port_name="D-50 IN",
        device_id=0,
        backend=backend,
        progress=lambda phase, current, total: progress.append((phase, current, total)),
        sleeper=lambda _seconds: None,
        input_flush_quiet_seconds=0,
    )

    commands = [parse_handshake_frame(frame).command for frame in backend.output.frames]
    assert commands[0] == WSD_COMMAND_ID
    assert commands[-1] == EOD_COMMAND_ID
    assert commands.count(DAT_COMMAND_ID) == 136
    assert report.data_byte_count == FULL_BANK_PAYLOAD_SIZE
    assert report.discarded_input_message_count == 0
    assert progress[-1] == ("Bank senden", 136, 136)
    assert backend.input.closed and backend.output.closed


def test_full_bank_receiver_acknowledges_and_reconstructs_bank(valid_bank_bytes: bytes) -> None:
    source = parse_bank(valid_bank_bytes)
    payload = bank_payload(source)
    backend = FakeDuplexBackend(_handshake_dump(payload))

    report = receive_full_bank_handshake(
        output_port_name="D-50 OUT",
        input_port_name="D-50 IN",
        device_id=0,
        backend=backend,
        sleeper=lambda _seconds: None,
        input_flush_quiet_seconds=0,
    )

    assert bank_payload(report.bank) == payload
    assert report.bank.device_id == 0
    assert report.data_message_count == 136
    assert report.unique_data_block_count == 136
    assert report.duplicate_data_message_count == 0
    assert len(backend.output.frames) == 138
    assert all(parse_handshake_frame(frame).command == ACK_COMMAND_ID for frame in backend.output.frames)
    assert backend.input.closed and backend.output.closed


def test_sender_never_advances_without_ack(valid_bank_bytes: bytes) -> None:
    backend = FakeDuplexBackend()
    with pytest.raises(MidiTransferError, match="Keine erwartete D-50-Handshake-Antwort"):
        send_full_bank_handshake(
            parse_bank(valid_bank_bytes),
            output_port_name="D-50 OUT",
            input_port_name="D-50 IN",
            device_id=0,
            backend=backend,
            response_timeout_seconds=0.01,
            sleeper=lambda _seconds: None,
            input_flush_quiet_seconds=0,
        )
    commands = [parse_handshake_frame(frame).command for frame in backend.output.frames]
    assert commands == [WSD_COMMAND_ID, 0x4F]


def test_receiver_rejects_incomplete_bank_before_project_creation() -> None:
    incoming = (
        build_handshake_request(WSD_COMMAND_ID, FULL_BANK_START, FULL_BANK_SIZE, device_id=0),
        build_dat_frame(FULL_BANK_START, bytes(64), device_id=0),
        build_handshake_control(EOD_COMMAND_ID, device_id=0),
    )
    backend = FakeDuplexBackend(incoming)
    with pytest.raises(MidiTransferError, match="unvollständig"):
        receive_full_bank_handshake(
            output_port_name="D-50 OUT",
            input_port_name="D-50 IN",
            device_id=0,
            backend=backend,
            sleeper=lambda _seconds: None,
            input_flush_quiet_seconds=0,
        )


def test_sender_flushes_stale_ack_before_start(valid_bank_bytes: bytes) -> None:
    stale_ack = build_handshake_control(ACK_COMMAND_ID, device_id=0)
    backend = FakeDuplexBackend((stale_ack,), acknowledge_sends=True)

    report = send_full_bank_handshake(
        parse_bank(valid_bank_bytes),
        output_port_name="D-50 OUT",
        input_port_name="D-50 IN",
        device_id=0,
        backend=backend,
        input_flush_quiet_seconds=0.005,
        input_flush_max_seconds=0.05,
        sleeper=lambda _seconds: None,
    )

    assert report.discarded_input_message_count == 1


def test_receiver_ignores_old_ack_before_wsd(valid_bank_bytes: bytes) -> None:
    payload = bank_payload(parse_bank(valid_bank_bytes))
    incoming = (build_handshake_control(ACK_COMMAND_ID, device_id=0), *_handshake_dump(payload))
    backend = FakeDuplexBackend(incoming)

    report = receive_full_bank_handshake(
        output_port_name="D-50 OUT",
        input_port_name="D-50 IN",
        device_id=0,
        backend=backend,
        input_flush_quiet_seconds=0,
        sleeper=lambda _seconds: None,
    )

    assert report.data_byte_count == FULL_BANK_PAYLOAD_SIZE


def test_sender_ignores_echoed_wsd_and_dat_frames(valid_bank_bytes: bytes) -> None:
    backend = FakeDuplexBackend(acknowledge_sends=True, echo_sends=True)

    report = send_full_bank_handshake(
        parse_bank(valid_bank_bytes),
        output_port_name="D-50 OUT",
        input_port_name="D-50 IN",
        device_id=0,
        backend=backend,
        input_flush_quiet_seconds=0,
        sleeper=lambda _seconds: None,
    )

    assert report.data_message_count == 136


def test_sender_ignores_foreign_and_unrelated_malformed_sysex(valid_bank_bytes: bytes) -> None:
    class NoisyOutput(FakeOutput):
        def send_sysex(self, frame: bytes) -> None:
            self.frames.append(bytes(frame))
            command = parse_handshake_frame(frame).command
            if command in {WSD_COMMAND_ID, DAT_COMMAND_ID, EOD_COMMAND_ID}:
                self.input_port.frames.extend(
                    (
                        bytes((0xF0, 0x7D, 0x01, 0xF7)),
                        bytes((0xF0, 0x41, 0x00, 0x14, 0x12, 0xF7)),
                        build_handshake_control(ACK_COMMAND_ID, device_id=0),
                    )
                )

    backend = FakeDuplexBackend()
    backend.output = NoisyOutput(backend.input, acknowledge_sends=False)

    report = send_full_bank_handshake(
        parse_bank(valid_bank_bytes),
        output_port_name="D-50 OUT",
        input_port_name="D-50 IN",
        device_id=0,
        backend=backend,
        input_flush_quiet_seconds=0,
        sleeper=lambda _seconds: None,
    )

    assert report.data_message_count == 136


def test_receiver_total_timeout_stops_hanging_transfer() -> None:
    backend = FakeDuplexBackend()
    with pytest.raises(MidiTransferError, match="Gesamtzeitlimit"):
        receive_full_bank_handshake(
            output_port_name="D-50 OUT",
            input_port_name="D-50 IN",
            device_id=0,
            backend=backend,
            initial_timeout_seconds=1,
            overall_timeout_seconds=0.01,
            input_flush_quiet_seconds=0,
            sleeper=lambda _seconds: None,
        )


def test_receiver_counts_limited_identical_dat_duplicates(valid_bank_bytes: bytes) -> None:
    payload = bank_payload(parse_bank(valid_bank_bytes))
    frames = list(_handshake_dump(payload))
    frames.insert(2, frames[1])
    backend = FakeDuplexBackend(tuple(frames))

    report = receive_full_bank_handshake(
        output_port_name="D-50 OUT",
        input_port_name="D-50 IN",
        device_id=0,
        backend=backend,
        input_flush_quiet_seconds=0,
        sleeper=lambda _seconds: None,
    )

    assert report.data_message_count == 137
    assert report.unique_data_block_count == 136
    assert report.duplicate_data_message_count == 1
    assert report.data_byte_count == FULL_BANK_PAYLOAD_SIZE


def test_receiver_rejects_excessive_identical_dat_duplicates(valid_bank_bytes: bytes) -> None:
    payload = bank_payload(parse_bank(valid_bank_bytes))
    frames = list(_handshake_dump(payload))
    frames[2:2] = [frames[1], frames[1], frames[1]]
    backend = FakeDuplexBackend(tuple(frames))

    with pytest.raises(MidiTransferError, match="Zu viele identische DAT-Dubletten"):
        receive_full_bank_handshake(
            output_port_name="D-50 OUT",
            input_port_name="D-50 IN",
            device_id=0,
            backend=backend,
            max_identical_dat_duplicates=2,
            input_flush_quiet_seconds=0,
            sleeper=lambda _seconds: None,
        )


def test_receiver_rejects_conflicting_dat_repetition(valid_bank_bytes: bytes) -> None:
    payload = bank_payload(parse_bank(valid_bank_bytes))
    frames = list(_handshake_dump(payload))
    first = parse_handshake_frame(frames[1])
    assert first.address is not None
    changed = bytes((first.data[0] ^ 1, *first.data[1:]))
    frames.insert(2, build_dat_frame(first.address, changed, device_id=0))
    backend = FakeDuplexBackend(tuple(frames))

    with pytest.raises(MidiTransferError, match="widersprüchliche DAT-Daten"):
        receive_full_bank_handshake(
            output_port_name="D-50 OUT",
            input_port_name="D-50 IN",
            device_id=0,
            backend=backend,
            input_flush_quiet_seconds=0,
            sleeper=lambda _seconds: None,
        )


def test_bank_close_error_does_not_hide_primary_transfer_error(valid_bank_bytes: bytes) -> None:
    backend = FakeDuplexBackend(output_close_error=RuntimeError("close failed"))
    with pytest.raises(MidiTransferError, match="Keine erwartete D-50-Handshake-Antwort"):
        send_full_bank_handshake(
            parse_bank(valid_bank_bytes),
            output_port_name="D-50 OUT",
            input_port_name="D-50 IN",
            device_id=0,
            backend=backend,
            response_timeout_seconds=0.01,
            input_flush_quiet_seconds=0,
            sleeper=lambda _seconds: None,
        )
    assert backend.output.closed and backend.input.closed
