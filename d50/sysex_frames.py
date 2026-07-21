"""Strict generic SysEx stream parsing plus Roland D-50 DT1 frames."""

from __future__ import annotations

from dataclasses import dataclass

from domain.errors import D50ValidationError, SysExParseError, ValidationIssue

from .addresses import Address, validate_address
from .checksum import checksum_is_valid, roland_checksum
from .constants import (
    D50_MODEL_ID,
    DEFAULT_DEVICE_ID,
    DT1_COMMAND_ID,
    MAX_DEVICE_ID,
    MAX_DT1_DATA_BYTES,
    MIN_DEVICE_ID,
    ROLAND_MANUFACTURER_ID,
)

SYSEX_START = 0xF0
SYSEX_END = 0xF7
REALTIME_BYTES = frozenset(range(0xF8, 0x100))


@dataclass(frozen=True, slots=True)
class StreamIssue:
    code: str
    offset: int
    message: str


@dataclass(frozen=True, slots=True)
class SysExFrame:
    raw: bytes
    offset: int


@dataclass(frozen=True, slots=True)
class SysExStream:
    raw: bytes
    frames: tuple[SysExFrame, ...]
    issues: tuple[StreamIssue, ...]
    realtime_byte_count: int


@dataclass(frozen=True, slots=True)
class DT1Message:
    index: int
    device_id: int
    address: Address
    data: bytes
    checksum: int
    raw: bytes


def parse_sysex_stream(data: bytes, *, strict: bool = False) -> SysExStream:
    frames: list[SysExFrame] = []
    issues: list[StreamIssue] = []
    current: bytearray | None = None
    frame_start = 0
    outside_start: int | None = None
    realtime_count = 0

    def note_outside(offset: int) -> None:
        nonlocal outside_start
        if outside_start is None:
            outside_start = offset

    def flush_outside(end: int) -> None:
        nonlocal outside_start
        if outside_start is not None:
            issues.append(
                StreamIssue(
                    "outside_sysex",
                    outside_start,
                    f"Fremdbytes außerhalb von SysEx bei Byte {outside_start} bis {end - 1}",
                )
            )
            outside_start = None

    for offset, value in enumerate(data):
        if value in REALTIME_BYTES:
            realtime_count += 1
            continue
        if current is None:
            if value == SYSEX_START:
                flush_outside(offset)
                current = bytearray([value])
                frame_start = offset
            elif value == SYSEX_END:
                flush_outside(offset)
                issues.append(StreamIssue("orphan_f7", offset, "SysEx-Endbyte F7 ohne Startbyte"))
            else:
                note_outside(offset)
            continue

        if value == SYSEX_START:
            issues.append(
                StreamIssue(
                    "truncated_frame",
                    frame_start,
                    f"Neue SysEx-Nachricht beginnt, bevor die Nachricht bei Byte {frame_start} beendet wurde",
                )
            )
            current = bytearray([value])
            frame_start = offset
            continue
        if value == SYSEX_END:
            current.append(value)
            frames.append(SysExFrame(bytes(current), frame_start))
            current = None
            continue
        if value > 0x7F:
            issues.append(
                StreamIssue(
                    "non_7bit_data",
                    offset,
                    f"Ungültiges Datenbyte 0x{value:02X} innerhalb einer SysEx-Nachricht",
                )
            )
        current.append(value)

    if current is not None:
        issues.append(
            StreamIssue("truncated_frame", frame_start, f"SysEx-Nachricht bei Byte {frame_start} endet ohne F7")
        )
    flush_outside(len(data))
    if not frames and not issues:
        issues.append(StreamIssue("not_sysex", 0, "Keine SysEx-Datei"))

    stream = SysExStream(bytes(data), tuple(frames), tuple(issues), realtime_count)
    if strict and stream.issues:
        issue = stream.issues[0]
        raise SysExParseError(
            ValidationIssue(issue.code, issue.message, byte_offset=issue.offset)
        )
    return stream


def parse_dt1_frame(frame: SysExFrame | bytes, *, index: int = 1) -> DT1Message:
    raw = frame.raw if isinstance(frame, SysExFrame) else bytes(frame)
    if len(raw) < 11:
        raise D50ValidationError(
            ValidationIssue("short_frame", "D-50-DT1-Nachricht ist zu kurz", message_index=index)
        )
    if raw[0] != SYSEX_START or raw[-1] != SYSEX_END:
        raise D50ValidationError(
            ValidationIssue("invalid_frame", "SysEx-Nachricht benötigt F0 am Anfang und F7 am Ende", message_index=index)
        )
    if any(value > 0x7F for value in raw[1:-1]):
        raise D50ValidationError(
            ValidationIssue("non_7bit_data", "SysEx enthält ein Datenbyte außerhalb des 7-Bit-Bereichs", message_index=index)
        )
    if raw[1] != ROLAND_MANUFACTURER_ID:
        raise D50ValidationError(
            ValidationIssue("foreign_manufacturer", "SysEx stammt nicht von Roland", message_index=index)
        )
    device_id = raw[2]
    if not MIN_DEVICE_ID <= device_id <= MAX_DEVICE_ID:
        raise D50ValidationError(
            ValidationIssue("invalid_device_id", f"Ungültige D-50 Device ID 0x{device_id:02X}", message_index=index)
        )
    if raw[3] != D50_MODEL_ID:
        raise D50ValidationError(
            ValidationIssue("other_roland_model", "Roland-SysEx erkannt, aber nicht D-50", message_index=index)
        )
    if raw[4] != DT1_COMMAND_ID:
        raise D50ValidationError(
            ValidationIssue(
                "unsupported_command",
                f"Nicht unterstützte D-50 Command ID 0x{raw[4]:02X}",
                message_index=index,
            )
        )
    address = validate_address(raw[5:8])
    data = raw[8:-2]
    if not data:
        raise D50ValidationError(
            ValidationIssue("empty_dt1", "D-50-DT1-Nachricht enthält keine Nutzdaten", message_index=index)
        )
    if len(data) > MAX_DT1_DATA_BYTES:
        raise D50ValidationError(
            ValidationIssue(
                "dt1_too_large",
                f"D-50-DT1-Nutzdaten überschreiten {MAX_DT1_DATA_BYTES} Byte",
                message_index=index,
            )
        )
    checksum = raw[-2]
    if not checksum_is_valid(address, data, checksum):
        raise D50ValidationError(
            ValidationIssue(
                "invalid_checksum",
                f"Ungültige D-50-Prüfsumme in Nachricht {index}",
                message_index=index,
            )
        )
    return DT1Message(index, device_id, address, data, checksum, raw)


def build_dt1_frame(
    address: Address,
    data: bytes,
    *,
    device_id: int = DEFAULT_DEVICE_ID,
) -> bytes:
    address = validate_address(address)
    if not MIN_DEVICE_ID <= device_id <= MAX_DEVICE_ID:
        raise ValueError("Device ID muss zwischen 00h und 1Fh liegen")
    if not 1 <= len(data) <= MAX_DT1_DATA_BYTES:
        raise ValueError(f"DT1-Nutzdaten müssen 1 bis {MAX_DT1_DATA_BYTES} Byte lang sein")
    if any(value > 0x7F for value in data):
        raise ValueError("DT1-Nutzdaten müssen vollständig 7-Bit sein")
    checksum = roland_checksum(address, data)
    return bytes(
        [
            SYSEX_START,
            ROLAND_MANUFACTURER_ID,
            device_id,
            D50_MODEL_ID,
            DT1_COMMAND_ID,
            *address,
            *data,
            checksum,
            SYSEX_END,
        ]
    )

