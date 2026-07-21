"""Reliable bidirectional D-50 full-bank transfer using Roland handshake SysEx."""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
import time

from d50.addresses import add_to_address, address_to_linear, linear_to_address
from d50.bank_codec import bank_payload, parse_bank
from d50.constants import (
    ACK_COMMAND_ID,
    DAT_COMMAND_ID,
    EOD_COMMAND_ID,
    ERR_COMMAND_ID,
    FULL_BANK_PAYLOAD_SIZE,
    FULL_BANK_START,
    MAX_DT1_DATA_BYTES,
    RJC_COMMAND_ID,
    WSD_COMMAND_ID,
)
from d50.handshake import (
    HandshakeMessage,
    build_dat_frame,
    build_handshake_control,
    build_handshake_request,
    parse_handshake_frame,
)
from d50.sysex_frames import build_dt1_frame
from domain.bank import D50Bank

from .temporary_sender import MidiBackend, MidiTransferError, MidoBackend, SysexInputPort, SysexOutputPort

ProgressCallback = Callable[[str, int, int], None]
CancelCallback = Callable[[], bool]

DEFAULT_RESPONSE_TIMEOUT_SECONDS = 8.0
DEFAULT_INITIAL_RECEIVE_TIMEOUT_SECONDS = 90.0
FINAL_PORT_SETTLE_SECONDS = 0.15
FULL_BANK_SIZE = linear_to_address(FULL_BANK_PAYLOAD_SIZE)


class BankTransferCancelled(MidiTransferError):
    """Raised when the user cancels an active bank handshake."""


@dataclass(frozen=True, slots=True)
class BankSendReport:
    port_name: str
    bank_label: str
    device_id: int
    data_message_count: int
    data_byte_count: int
    elapsed_ms: int


@dataclass(frozen=True, slots=True)
class BankReceiveReport:
    input_port_name: str
    bank: D50Bank
    data_message_count: int
    data_byte_count: int
    elapsed_ms: int


def _check_cancelled(cancelled: CancelCallback | None) -> None:
    if cancelled is not None and cancelled():
        raise BankTransferCancelled("Bankübertragung wurde abgebrochen")


def _wait_for_message(
    port: SysexInputPort,
    *,
    device_id: int,
    timeout_seconds: float,
    cancelled: CancelCallback | None,
) -> HandshakeMessage:
    deadline = time.monotonic() + timeout_seconds
    while time.monotonic() < deadline:
        _check_cancelled(cancelled)
        raw = port.poll_sysex()
        if raw is None:
            time.sleep(0.005)
            continue
        if len(raw) < 5 or raw[0] != 0xF0 or raw[1] != 0x41 or raw[3] != 0x14:
            continue
        message = parse_handshake_frame(raw)
        if message.device_id == device_id:
            return message
    raise MidiTransferError(
        f"Keine D-50-Handshake-Antwort mit Device ID {device_id:02X} innerhalb von {timeout_seconds:g} s"
    )


def _send_and_expect_ack(
    output: SysexOutputPort,
    input_port: SysexInputPort,
    frame: bytes,
    *,
    device_id: int,
    timeout_seconds: float,
    cancelled: CancelCallback | None,
) -> None:
    for attempt in range(2):
        _check_cancelled(cancelled)
        output.send_sysex(frame)
        response = _wait_for_message(
            input_port,
            device_id=device_id,
            timeout_seconds=timeout_seconds,
            cancelled=cancelled,
        )
        if response.command == ACK_COMMAND_ID:
            return
        if response.command == ERR_COMMAND_ID and attempt == 0:
            continue
        if response.command == RJC_COMMAND_ID:
            raise MidiTransferError("Der D-50 hat die Bankübertragung zurückgewiesen (RJC)")
        raise MidiTransferError(f"Unerwartete D-50-Antwort 0x{response.command:02X} statt ACK")
    raise MidiTransferError("Der D-50 meldet wiederholt einen Übertragungsfehler (ERR)")


def _abort_handshake(output: SysexOutputPort, *, device_id: int) -> None:
    try:
        output.send_sysex(build_handshake_control(RJC_COMMAND_ID, device_id=device_id))
    except Exception:
        pass


def _bank_dat_frames(bank: D50Bank, *, device_id: int) -> tuple[bytes, ...]:
    payload = bank_payload(bank)
    return tuple(
        build_dat_frame(
            add_to_address(FULL_BANK_START, offset),
            payload[offset : offset + MAX_DT1_DATA_BYTES],
            device_id=device_id,
        )
        for offset in range(0, len(payload), MAX_DT1_DATA_BYTES)
    )


def send_full_bank_handshake(
    bank: D50Bank,
    *,
    output_port_name: str,
    input_port_name: str,
    device_id: int,
    backend: MidiBackend | None = None,
    response_timeout_seconds: float = DEFAULT_RESPONSE_TIMEOUT_SECONDS,
    progress: ProgressCallback | None = None,
    cancelled: CancelCallback | None = None,
    sleeper: Callable[[float], None] = time.sleep,
) -> BankSendReport:
    """Send 64 patches and Reverbs 17–32 after per-block ACK verification."""
    if not output_port_name or not input_port_name:
        raise MidiTransferError("Für Handshake-Senden werden MIDI-Ausgang und MIDI-Eingang benötigt")
    selected_backend = backend or MidoBackend()
    input_port = selected_backend.open_input(input_port_name)
    try:
        output = selected_backend.open_output(output_port_name)
    except BaseException:
        input_port.close()
        raise
    frames = _bank_dat_frames(bank, device_id=device_id)
    started = time.perf_counter()
    try:
        if progress is not None:
            progress("Handshake starten", 0, len(frames))
        request = build_handshake_request(
            WSD_COMMAND_ID,
            FULL_BANK_START,
            FULL_BANK_SIZE,
            device_id=device_id,
        )
        _send_and_expect_ack(
            output,
            input_port,
            request,
            device_id=device_id,
            timeout_seconds=response_timeout_seconds,
            cancelled=cancelled,
        )
        for index, frame in enumerate(frames, start=1):
            _send_and_expect_ack(
                output,
                input_port,
                frame,
                device_id=device_id,
                timeout_seconds=response_timeout_seconds,
                cancelled=cancelled,
            )
            if progress is not None:
                progress("Bank senden", index, len(frames))
        _send_and_expect_ack(
            output,
            input_port,
            build_handshake_control(EOD_COMMAND_ID, device_id=device_id),
            device_id=device_id,
            timeout_seconds=response_timeout_seconds,
            cancelled=cancelled,
        )
        sleeper(FINAL_PORT_SETTLE_SECONDS)
    except BaseException:
        _abort_handshake(output, device_id=device_id)
        raise
    finally:
        output.close()
        input_port.close()
    return BankSendReport(
        port_name=output_port_name,
        bank_label=bank.label,
        device_id=device_id,
        data_message_count=len(frames),
        data_byte_count=FULL_BANK_PAYLOAD_SIZE,
        elapsed_ms=round((time.perf_counter() - started) * 1000),
    )


def _canonical_bank_stream(payload: bytes, *, device_id: int) -> bytes:
    return b"".join(
        build_dt1_frame(
            add_to_address(FULL_BANK_START, offset),
            payload[offset : offset + MAX_DT1_DATA_BYTES],
            device_id=device_id,
        )
        for offset in range(0, len(payload), MAX_DT1_DATA_BYTES)
    )


def receive_full_bank_handshake(
    *,
    output_port_name: str,
    input_port_name: str,
    device_id: int,
    label: str = "D-50 MIDI Bank",
    backend: MidiBackend | None = None,
    initial_timeout_seconds: float = DEFAULT_INITIAL_RECEIVE_TIMEOUT_SECONDS,
    response_timeout_seconds: float = DEFAULT_RESPONSE_TIMEOUT_SECONDS,
    progress: ProgressCallback | None = None,
    cancelled: CancelCallback | None = None,
    sleeper: Callable[[float], None] = time.sleep,
) -> BankReceiveReport:
    """Receive a D-50 B.Dump, acknowledging every validated DAT block."""
    if not output_port_name or not input_port_name:
        raise MidiTransferError("Für Handshake-Empfang werden MIDI-Ausgang und MIDI-Eingang benötigt")
    selected_backend = backend or MidoBackend()
    input_port = selected_backend.open_input(input_port_name)
    try:
        output = selected_backend.open_output(output_port_name)
    except BaseException:
        input_port.close()
        raise
    started = time.perf_counter()
    cells: dict[int, int] = {}
    message_count = 0
    bank_start = address_to_linear(FULL_BANK_START)
    bank_end = bank_start + FULL_BANK_PAYLOAD_SIZE
    try:
        if progress is not None:
            progress("Warte auf D-50 B.Dump", 0, FULL_BANK_PAYLOAD_SIZE)
        opening = _wait_for_message(
            input_port,
            device_id=device_id,
            timeout_seconds=initial_timeout_seconds,
            cancelled=cancelled,
        )
        if opening.command != WSD_COMMAND_ID:
            raise MidiTransferError(f"D-50 sendet 0x{opening.command:02X} statt WSD/B.Dump")
        if opening.address != FULL_BANK_START or opening.size != FULL_BANK_SIZE:
            raise MidiTransferError(
                f"D-50 kündigt nicht die vollständige Bank an: Adresse {opening.address}, Größe {opening.size}"
            )
        output.send_sysex(build_handshake_control(ACK_COMMAND_ID, device_id=device_id))

        while True:
            message = _wait_for_message(
                input_port,
                device_id=device_id,
                timeout_seconds=response_timeout_seconds,
                cancelled=cancelled,
            )
            if message.command == EOD_COMMAND_ID:
                if len(cells) != FULL_BANK_PAYLOAD_SIZE:
                    _abort_handshake(output, device_id=device_id)
                    raise MidiTransferError(
                        f"D-50 beendete den Dump unvollständig: {len(cells)} von {FULL_BANK_PAYLOAD_SIZE} Byte"
                    )
                output.send_sysex(build_handshake_control(ACK_COMMAND_ID, device_id=device_id))
                sleeper(FINAL_PORT_SETTLE_SECONDS)
                break
            if message.command == RJC_COMMAND_ID:
                raise MidiTransferError("Der D-50 hat den Bankdump abgebrochen (RJC)")
            if message.command != DAT_COMMAND_ID or message.address is None:
                raise MidiTransferError(f"Unerwartete D-50-Nachricht 0x{message.command:02X} während B.Dump")

            start = address_to_linear(message.address)
            end = start + len(message.data)
            if start < bank_start or end > bank_end:
                _abort_handshake(output, device_id=device_id)
                raise MidiTransferError("D-50-DAT liegt außerhalb des vollständigen Bankadressraums")
            for relative, value in enumerate(message.data):
                address = start + relative
                previous = cells.get(address)
                if previous is not None and previous != value:
                    output.send_sysex(build_handshake_control(ERR_COMMAND_ID, device_id=device_id))
                    raise MidiTransferError("D-50 sendete widersprüchliche Daten für dieselbe Bankadresse")
                cells[address] = value
            message_count += 1
            output.send_sysex(build_handshake_control(ACK_COMMAND_ID, device_id=device_id))
            if progress is not None:
                progress("Bank empfangen", len(cells), FULL_BANK_PAYLOAD_SIZE)
    except BaseException:
        _abort_handshake(output, device_id=device_id)
        raise
    finally:
        output.close()
        input_port.close()

    payload = bytes(cells[address] for address in range(bank_start, bank_end))
    bank = parse_bank(_canonical_bank_stream(payload, device_id=device_id), label=label)
    return BankReceiveReport(
        input_port_name=input_port_name,
        bank=bank,
        data_message_count=message_count,
        data_byte_count=len(payload),
        elapsed_ms=round((time.perf_counter() - started) * 1000),
    )
