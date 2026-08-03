"""Reliable bidirectional D-50 full-bank transfer using Roland handshake SysEx."""

from __future__ import annotations

from collections.abc import Callable, Collection
from dataclasses import dataclass
import logging
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
DEFAULT_RECEIVE_TOTAL_TIMEOUT_SECONDS = 180.0
DEFAULT_INPUT_FLUSH_QUIET_SECONDS = 0.05
DEFAULT_INPUT_FLUSH_MAX_SECONDS = 0.5
DEFAULT_MAX_IDENTICAL_DAT_DUPLICATES = 32
FINAL_PORT_SETTLE_SECONDS = 0.15
FULL_BANK_SIZE = linear_to_address(FULL_BANK_PAYLOAD_SIZE)

_LOGGER = logging.getLogger(__name__)


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
    discarded_input_message_count: int


@dataclass(frozen=True, slots=True)
class BankReceiveReport:
    input_port_name: str
    bank: D50Bank
    data_message_count: int
    unique_data_block_count: int
    duplicate_data_message_count: int
    data_byte_count: int
    elapsed_ms: int
    discarded_input_message_count: int


def _check_cancelled(cancelled: CancelCallback | None) -> None:
    if cancelled is not None and cancelled():
        raise BankTransferCancelled("Bankübertragung wurde abgebrochen")


def _flush_input(
    port: SysexInputPort,
    *,
    quiet_seconds: float,
    max_seconds: float,
    cancelled: CancelCallback | None,
) -> int:
    """Discard stale input until a short quiet period, only before a handshake."""
    if quiet_seconds <= 0 or max_seconds <= 0:
        return 0
    started = time.monotonic()
    quiet_deadline = started + quiet_seconds
    hard_deadline = started + max_seconds
    discarded = 0
    while time.monotonic() < hard_deadline:
        _check_cancelled(cancelled)
        raw = port.poll_sysex()
        now = time.monotonic()
        if raw is None:
            if now >= quiet_deadline:
                break
            time.sleep(min(0.005, max(0.0, quiet_deadline - now)))
            continue
        discarded += 1
        quiet_deadline = min(now + quiet_seconds, hard_deadline)
    return discarded


def _is_d50_frame_for_device(raw: bytes, device_id: int) -> bool:
    return (
        len(raw) >= 4
        and raw[0] == 0xF0
        and raw[1] == 0x41
        and raw[2] == device_id
        and raw[3] == 0x14
    )


def _wait_for_message(
    port: SysexInputPort,
    *,
    device_id: int,
    allowed_commands: Collection[int],
    timeout_seconds: float,
    cancelled: CancelCallback | None,
    echoed_frames: Collection[bytes] = (),
    overall_deadline: float | None = None,
    tag: str = "#-",
) -> HandshakeMessage:
    expected = frozenset(allowed_commands)
    echoes = frozenset(bytes(frame) for frame in echoed_frames)
    started = time.monotonic()
    response_deadline = started + timeout_seconds
    deadline = min(response_deadline, overall_deadline) if overall_deadline is not None else response_deadline
    while time.monotonic() < deadline:
        _check_cancelled(cancelled)
        raw = port.poll_sysex()
        if raw is None:
            time.sleep(0.005)
            continue
        raw = bytes(raw)
        if raw in echoes:
            _LOGGER.debug("[MIDI BANK %s] Ignoring echoed own frame command=%s", tag, _command_label(raw))
            continue
        if not _is_d50_frame_for_device(raw, device_id):
            _LOGGER.debug("[MIDI BANK %s] Ignoring foreign SysEx (%d bytes)", tag, len(raw))
            continue
        try:
            message = parse_handshake_frame(raw)
        except Exception as exc:
            command = raw[4] if len(raw) >= 5 else None
            if command in expected:
                raise MidiTransferError(
                    f"Beschädigte D-50-Handshake-Nachricht für den aktiven Transfer: {exc}"
                ) from exc
            _LOGGER.warning("[MIDI BANK %s] Ignoring malformed unrelated D-50 SysEx: %s", tag, exc)
            continue
        if message.command not in expected:
            _LOGGER.debug(
                "[MIDI BANK %s] Ignoring command 0x%02X; expected one of %s",
                tag,
                message.command,
                ", ".join(f"0x{command:02X}" for command in sorted(expected)),
            )
            continue
        return message
    if overall_deadline is not None and time.monotonic() >= overall_deadline:
        raise MidiTransferError("Gesamtzeitlimit für den D-50-Bankempfang wurde überschritten")
    raise MidiTransferError(
        f"Keine erwartete D-50-Handshake-Antwort mit Device ID {device_id:02X} "
        f"innerhalb von {timeout_seconds:g} s"
    )


def _command_label(raw: bytes) -> str:
    return f"0x{raw[4]:02X}" if len(raw) >= 5 else "unbekannt"


def _send_and_expect_ack(
    output: SysexOutputPort,
    input_port: SysexInputPort,
    frame: bytes,
    *,
    device_id: int,
    timeout_seconds: float,
    cancelled: CancelCallback | None,
    sent_frames: set[bytes],
    tag: str,
) -> None:
    sent_frames.add(bytes(frame))
    for attempt in range(2):
        _check_cancelled(cancelled)
        output.send_sysex(frame)
        response = _wait_for_message(
            input_port,
            device_id=device_id,
            allowed_commands={ACK_COMMAND_ID, ERR_COMMAND_ID, RJC_COMMAND_ID},
            timeout_seconds=timeout_seconds,
            cancelled=cancelled,
            echoed_frames=sent_frames,
            tag=tag,
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


def _close_ports(
    output: SysexOutputPort,
    input_port: SysexInputPort,
    *,
    primary_failure: Exception | None,
    tag: str,
    operation: str,
) -> Exception | None:
    failure = primary_failure
    for label, port in (("Ausgang", output), ("Eingang", input_port)):
        try:
            port.close()
        except Exception as exc:
            if failure is None:
                failure = MidiTransferError(f"MIDI-{label} konnte nicht geschlossen werden: {exc}")
            else:
                _LOGGER.warning("[%s %s] Close error after primary failure (%s): %s", operation, tag, label, exc)
    return failure


def _open_duplex_ports(
    backend: MidiBackend,
    *,
    input_port_name: str,
    output_port_name: str,
) -> tuple[SysexInputPort, SysexOutputPort]:
    input_port = backend.open_input(input_port_name)
    try:
        output = backend.open_output(output_port_name)
    except Exception:
        try:
            input_port.close()
        except Exception as close_exc:
            _LOGGER.warning("MIDI input close error after output-open failure: %s", close_exc)
        raise
    return input_port, output


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
    input_flush_quiet_seconds: float = DEFAULT_INPUT_FLUSH_QUIET_SECONDS,
    input_flush_max_seconds: float = DEFAULT_INPUT_FLUSH_MAX_SECONDS,
    progress: ProgressCallback | None = None,
    cancelled: CancelCallback | None = None,
    sleeper: Callable[[float], None] = time.sleep,
    job_id: int | None = None,
) -> BankSendReport:
    """Send 64 patches and Reverbs 17–32 after per-block ACK verification."""
    if not output_port_name or not input_port_name:
        raise MidiTransferError("Für Handshake-Senden werden MIDI-Ausgang und MIDI-Eingang benötigt")
    selected_backend = backend or MidoBackend()
    input_port, output = _open_duplex_ports(
        selected_backend,
        input_port_name=input_port_name,
        output_port_name=output_port_name,
    )
    frames = _bank_dat_frames(bank, device_id=device_id)
    started = time.perf_counter()
    tag = f"#{job_id}" if job_id is not None else "#-"
    discarded = 0
    failure: Exception | None = None
    report: BankSendReport | None = None
    _LOGGER.info(
        "[TX BANK %s] Start bank=%r out=%r in=%r device=%02X frames=%d",
        tag,
        bank.label,
        output_port_name,
        input_port_name,
        device_id,
        len(frames),
    )
    try:
        discarded = _flush_input(
            input_port,
            quiet_seconds=input_flush_quiet_seconds,
            max_seconds=input_flush_max_seconds,
            cancelled=cancelled,
        )
        _LOGGER.info("[TX BANK %s] Input flush discarded=%d", tag, discarded)
        if progress is not None:
            progress("Handshake starten", 0, len(frames))
        sent_frames: set[bytes] = set()
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
            sent_frames=sent_frames,
            tag=tag,
        )
        for index, frame in enumerate(frames, start=1):
            _send_and_expect_ack(
                output,
                input_port,
                frame,
                device_id=device_id,
                timeout_seconds=response_timeout_seconds,
                cancelled=cancelled,
                sent_frames=sent_frames,
                tag=tag,
            )
            if progress is not None:
                progress("Bank senden", index, len(frames))
            sent = parse_handshake_frame(frame)
            _LOGGER.info(
                "[TX BANK %s] DAT %d/%d address=%02X-%02X-%02X bytes=%d ACK",
                tag,
                index,
                len(frames),
                *sent.address,
                len(sent.data),
            )
        _send_and_expect_ack(
            output,
            input_port,
            build_handshake_control(EOD_COMMAND_ID, device_id=device_id),
            device_id=device_id,
            timeout_seconds=response_timeout_seconds,
            cancelled=cancelled,
            sent_frames=sent_frames,
            tag=tag,
        )
        sleeper(FINAL_PORT_SETTLE_SECONDS)
        report = BankSendReport(
            port_name=output_port_name,
            bank_label=bank.label,
            device_id=device_id,
            data_message_count=len(frames),
            data_byte_count=FULL_BANK_PAYLOAD_SIZE,
            elapsed_ms=round((time.perf_counter() - started) * 1000),
            discarded_input_message_count=discarded,
        )
    except Exception as exc:
        failure = exc
        _abort_handshake(output, device_id=device_id)
    finally:
        failure = _close_ports(
            output,
            input_port,
            primary_failure=failure,
            tag=tag,
            operation="TX BANK",
        )
    if failure is not None:
        _LOGGER.error("[TX BANK %s] Failed discarded=%d: %s", tag, discarded, failure)
        raise failure
    assert report is not None
    _LOGGER.info(
        "[TX BANK %s] Complete frames=%d bytes=%d discarded=%d elapsed=%dms",
        tag,
        report.data_message_count,
        report.data_byte_count,
        report.discarded_input_message_count,
        report.elapsed_ms,
    )
    return report


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
    overall_timeout_seconds: float = DEFAULT_RECEIVE_TOTAL_TIMEOUT_SECONDS,
    input_flush_quiet_seconds: float = DEFAULT_INPUT_FLUSH_QUIET_SECONDS,
    input_flush_max_seconds: float = DEFAULT_INPUT_FLUSH_MAX_SECONDS,
    max_identical_dat_duplicates: int = DEFAULT_MAX_IDENTICAL_DAT_DUPLICATES,
    progress: ProgressCallback | None = None,
    cancelled: CancelCallback | None = None,
    sleeper: Callable[[float], None] = time.sleep,
    job_id: int | None = None,
) -> BankReceiveReport:
    """Receive a D-50 B.Dump, acknowledging every validated DAT block."""
    if not output_port_name or not input_port_name:
        raise MidiTransferError("Für Handshake-Empfang werden MIDI-Ausgang und MIDI-Eingang benötigt")
    if overall_timeout_seconds <= 0:
        raise ValueError("Das Gesamtzeitlimit muss größer als null sein")
    if max_identical_dat_duplicates < 0:
        raise ValueError("Die erlaubte Zahl identischer DAT-Dubletten darf nicht negativ sein")
    selected_backend = backend or MidoBackend()
    input_port, output = _open_duplex_ports(
        selected_backend,
        input_port_name=input_port_name,
        output_port_name=output_port_name,
    )
    started = time.perf_counter()
    tag = f"#{job_id}" if job_id is not None else "#-"
    _LOGGER.info(
        "[RX BANK %s] Start label=%r out=%r in=%r device=%02X total_timeout=%gs",
        tag,
        label,
        output_port_name,
        input_port_name,
        device_id,
        overall_timeout_seconds,
    )
    cells: dict[int, int] = {}
    blocks: dict[tuple[int, int], bytes] = {}
    message_count = 0
    duplicate_count = 0
    discarded = 0
    bank_start = address_to_linear(FULL_BANK_START)
    bank_end = bank_start + FULL_BANK_PAYLOAD_SIZE
    failure: Exception | None = None
    report: BankReceiveReport | None = None
    try:
        discarded = _flush_input(
            input_port,
            quiet_seconds=input_flush_quiet_seconds,
            max_seconds=input_flush_max_seconds,
            cancelled=cancelled,
        )
        _LOGGER.info("[RX BANK %s] Input flush discarded=%d", tag, discarded)
        overall_deadline = time.monotonic() + overall_timeout_seconds
        if progress is not None:
            progress("Warte auf D-50 B.Dump", 0, FULL_BANK_PAYLOAD_SIZE)
        opening = _wait_for_message(
            input_port,
            device_id=device_id,
            allowed_commands={WSD_COMMAND_ID, RJC_COMMAND_ID},
            timeout_seconds=initial_timeout_seconds,
            cancelled=cancelled,
            overall_deadline=overall_deadline,
            tag=tag,
        )
        if opening.command == RJC_COMMAND_ID:
            raise MidiTransferError("Der D-50 hat den Bankdump abgebrochen (RJC)")
        if opening.address != FULL_BANK_START or opening.size != FULL_BANK_SIZE:
            raise MidiTransferError(
                f"D-50 kündigt nicht die vollständige Bank an: Adresse {opening.address}, Größe {opening.size}"
            )
        ack_frame = build_handshake_control(ACK_COMMAND_ID, device_id=device_id)
        own_frames = {ack_frame}
        output.send_sysex(ack_frame)

        while True:
            message = _wait_for_message(
                input_port,
                device_id=device_id,
                allowed_commands={DAT_COMMAND_ID, EOD_COMMAND_ID, RJC_COMMAND_ID},
                timeout_seconds=response_timeout_seconds,
                cancelled=cancelled,
                echoed_frames=own_frames,
                overall_deadline=overall_deadline,
                tag=tag,
            )
            if message.command == EOD_COMMAND_ID:
                if len(cells) != FULL_BANK_PAYLOAD_SIZE:
                    raise MidiTransferError(
                        f"D-50 beendete den Dump unvollständig: {len(cells)} von {FULL_BANK_PAYLOAD_SIZE} Byte"
                    )
                output.send_sysex(ack_frame)
                sleeper(FINAL_PORT_SETTLE_SECONDS)
                break
            if message.command == RJC_COMMAND_ID:
                raise MidiTransferError("Der D-50 hat den Bankdump abgebrochen (RJC)")
            assert message.command == DAT_COMMAND_ID and message.address is not None

            start = address_to_linear(message.address)
            end = start + len(message.data)
            if start < bank_start or end > bank_end:
                raise MidiTransferError("D-50-DAT liegt außerhalb des vollständigen Bankadressraums")
            message_count += 1
            block_key = (start, len(message.data))
            previous_block = blocks.get(block_key)
            if previous_block is not None:
                if previous_block != message.data:
                    output.send_sysex(build_handshake_control(ERR_COMMAND_ID, device_id=device_id))
                    raise MidiTransferError("D-50 sendete widersprüchliche DAT-Daten für denselben Block")
                duplicate_count += 1
                _LOGGER.warning(
                    "[RX BANK %s] Duplicate DAT %d address=%02X-%02X-%02X bytes=%d",
                    tag,
                    duplicate_count,
                    *message.address,
                    len(message.data),
                )
                if duplicate_count > max_identical_dat_duplicates:
                    raise MidiTransferError(
                        f"Zu viele identische DAT-Dubletten ({duplicate_count}); möglicher MIDI-Loop"
                    )
            else:
                for relative, value in enumerate(message.data):
                    address = start + relative
                    previous = cells.get(address)
                    if previous is not None and previous != value:
                        output.send_sysex(build_handshake_control(ERR_COMMAND_ID, device_id=device_id))
                        raise MidiTransferError("D-50 sendete widersprüchliche Daten für dieselbe Bankadresse")
                    cells[address] = value
                blocks[block_key] = message.data
            _LOGGER.info(
                "[RX BANK %s] DAT %d unique=%d duplicates=%d address=%02X-%02X-%02X bytes=%d payload=%d",
                tag,
                message_count,
                len(blocks),
                duplicate_count,
                *message.address,
                len(message.data),
                len(cells),
            )
            output.send_sysex(ack_frame)
            if progress is not None:
                progress("Bank empfangen", len(cells), FULL_BANK_PAYLOAD_SIZE)

        payload = bytes(cells[address] for address in range(bank_start, bank_end))
        bank = parse_bank(_canonical_bank_stream(payload, device_id=device_id), label=label)
        report = BankReceiveReport(
            input_port_name=input_port_name,
            bank=bank,
            data_message_count=message_count,
            unique_data_block_count=len(blocks),
            duplicate_data_message_count=duplicate_count,
            data_byte_count=len(payload),
            elapsed_ms=round((time.perf_counter() - started) * 1000),
            discarded_input_message_count=discarded,
        )
    except Exception as exc:
        failure = exc
        _abort_handshake(output, device_id=device_id)
    finally:
        failure = _close_ports(
            output,
            input_port,
            primary_failure=failure,
            tag=tag,
            operation="RX BANK",
        )
    if failure is not None:
        _LOGGER.error(
            "[RX BANK %s] Failed messages=%d unique=%d duplicates=%d payload=%d discarded=%d: %s",
            tag,
            message_count,
            len(blocks),
            duplicate_count,
            len(cells),
            discarded,
            failure,
        )
        raise failure
    assert report is not None
    _LOGGER.info(
        "[RX BANK %s] Complete messages=%d unique=%d duplicates=%d bytes=%d discarded=%d elapsed=%dms",
        tag,
        report.data_message_count,
        report.unique_data_block_count,
        report.duplicate_data_message_count,
        report.data_byte_count,
        report.discarded_input_message_count,
        report.elapsed_ms,
    )
    return report
