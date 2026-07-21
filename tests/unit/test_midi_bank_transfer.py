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
    def __init__(self, input_port: FakeInput, *, acknowledge_sends: bool) -> None:
        self.input_port = input_port
        self.acknowledge_sends = acknowledge_sends
        self.frames: list[bytes] = []
        self.closed = False

    def send_sysex(self, frame: bytes) -> None:
        self.frames.append(bytes(frame))
        if self.acknowledge_sends:
            command = parse_handshake_frame(frame).command
            if command in {WSD_COMMAND_ID, DAT_COMMAND_ID, EOD_COMMAND_ID}:
                self.input_port.frames.append(build_handshake_control(ACK_COMMAND_ID, device_id=0))

    def close(self) -> None:
        self.closed = True


class FakeDuplexBackend:
    def __init__(self, incoming: tuple[bytes, ...] = (), *, acknowledge_sends: bool = False) -> None:
        self.input = FakeInput(incoming)
        self.output = FakeOutput(self.input, acknowledge_sends=acknowledge_sends)

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
    )

    commands = [parse_handshake_frame(frame).command for frame in backend.output.frames]
    assert commands[0] == WSD_COMMAND_ID
    assert commands[-1] == EOD_COMMAND_ID
    assert commands.count(DAT_COMMAND_ID) == 136
    assert report.data_byte_count == FULL_BANK_PAYLOAD_SIZE
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
    )

    assert bank_payload(report.bank) == payload
    assert report.bank.device_id == 0
    assert report.data_message_count == 136
    assert len(backend.output.frames) == 138
    assert all(parse_handshake_frame(frame).command == ACK_COMMAND_ID for frame in backend.output.frames)
    assert backend.input.closed and backend.output.closed


def test_sender_never_advances_without_ack(valid_bank_bytes: bytes) -> None:
    backend = FakeDuplexBackend()
    with pytest.raises(MidiTransferError, match="Keine D-50-Handshake-Antwort"):
        send_full_bank_handshake(
            parse_bank(valid_bank_bytes),
            output_port_name="D-50 OUT",
            input_port_name="D-50 IN",
            device_id=0,
            backend=backend,
            response_timeout_seconds=0.01,
            sleeper=lambda _seconds: None,
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
        )
