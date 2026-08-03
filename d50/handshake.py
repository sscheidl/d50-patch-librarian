"""Roland D-50 bidirectional handshake messages for reliable bulk transfer."""

from __future__ import annotations

from dataclasses import dataclass

from domain.errors import D50ValidationError, ValidationIssue

from .addresses import Address, validate_address
from .checksum import checksum_is_valid, roland_checksum
from .constants import (
    ACK_COMMAND_ID,
    DAT_COMMAND_ID,
    D50_MODEL_ID,
    DEFAULT_DEVICE_ID,
    EOD_COMMAND_ID,
    ERR_COMMAND_ID,
    MAX_DEVICE_ID,
    MAX_DT1_DATA_BYTES,
    MIN_DEVICE_ID,
    RJC_COMMAND_ID,
    ROLAND_MANUFACTURER_ID,
    RQD_COMMAND_ID,
    WSD_COMMAND_ID,
)
from .sysex_frames import SYSEX_END, SYSEX_START

REQUEST_COMMANDS = frozenset((WSD_COMMAND_ID, RQD_COMMAND_ID))
CONTROL_COMMANDS = frozenset((ACK_COMMAND_ID, EOD_COMMAND_ID, ERR_COMMAND_ID, RJC_COMMAND_ID))
HANDSHAKE_COMMANDS = REQUEST_COMMANDS | CONTROL_COMMANDS | {DAT_COMMAND_ID}


@dataclass(frozen=True, slots=True)
class HandshakeMessage:
    command: int
    device_id: int
    raw: bytes
    address: Address | None = None
    size: Address | None = None
    data: bytes = b""


def _validate_device_id(device_id: int) -> None:
    if not MIN_DEVICE_ID <= device_id <= MAX_DEVICE_ID:
        raise ValueError("Device ID muss zwischen 00h und 1Fh liegen")


def _prefix(device_id: int, command: int) -> list[int]:
    _validate_device_id(device_id)
    return [SYSEX_START, ROLAND_MANUFACTURER_ID, device_id, D50_MODEL_ID, command]


def build_handshake_request(
    command: int,
    address: Address,
    size: Address,
    *,
    device_id: int = DEFAULT_DEVICE_ID,
) -> bytes:
    if command not in REQUEST_COMMANDS:
        raise ValueError("Handshake-Anfrage muss WSD oder RQD sein")
    selected_address = validate_address(address)
    selected_size = validate_address(size)
    checksum = roland_checksum(selected_address, selected_size)
    return bytes([*_prefix(device_id, command), *selected_address, *selected_size, checksum, SYSEX_END])


def build_dat_frame(
    address: Address,
    data: bytes,
    *,
    device_id: int = DEFAULT_DEVICE_ID,
) -> bytes:
    selected_address = validate_address(address)
    if not 1 <= len(data) <= MAX_DT1_DATA_BYTES:
        raise ValueError(f"DAT-Nutzdaten müssen 1 bis {MAX_DT1_DATA_BYTES} Byte lang sein")
    if any(value > 0x7F for value in data):
        raise ValueError("DAT-Nutzdaten müssen vollständig 7-Bit sein")
    checksum = roland_checksum(selected_address, data)
    return bytes([*_prefix(device_id, DAT_COMMAND_ID), *selected_address, *data, checksum, SYSEX_END])


def build_handshake_control(
    command: int,
    *,
    device_id: int = DEFAULT_DEVICE_ID,
) -> bytes:
    if command not in CONTROL_COMMANDS:
        raise ValueError("Unbekannte Handshake-Steuernachricht")
    return bytes([*_prefix(device_id, command), SYSEX_END])


def parse_handshake_frame(frame: bytes) -> HandshakeMessage:
    raw = bytes(frame)
    if len(raw) < 6 or raw[0] != SYSEX_START or raw[-1] != SYSEX_END:
        raise D50ValidationError(ValidationIssue("invalid_handshake", "Ungültiger Handshake-SysEx-Rahmen"))
    if any(value > 0x7F for value in raw[1:-1]):
        raise D50ValidationError(ValidationIssue("non_7bit_data", "Handshake enthält ungültige Datenbytes"))
    if raw[1] != ROLAND_MANUFACTURER_ID or raw[3] != D50_MODEL_ID:
        raise D50ValidationError(ValidationIssue("foreign_handshake", "SysEx ist kein D-50-Handshake"))
    device_id = raw[2]
    if not MIN_DEVICE_ID <= device_id <= MAX_DEVICE_ID:
        raise D50ValidationError(ValidationIssue("invalid_device_id", f"Ungültige Device ID 0x{device_id:02X}"))
    command = raw[4]
    if command not in HANDSHAKE_COMMANDS:
        raise D50ValidationError(ValidationIssue("unsupported_command", f"Unbekanntes Handshake-Kommando 0x{command:02X}"))

    if command in CONTROL_COMMANDS:
        if len(raw) != 6:
            raise D50ValidationError(ValidationIssue("invalid_control", "Ungültige Handshake-Steuernachricht"))
        return HandshakeMessage(command, device_id, raw)

    if command in REQUEST_COMMANDS:
        if len(raw) != 13:
            raise D50ValidationError(ValidationIssue("invalid_request", "WSD/RQD besitzt eine ungültige Länge"))
        address = validate_address(raw[5:8])
        size = validate_address(raw[8:11])
        if not checksum_is_valid(address, size, raw[11]):
            raise D50ValidationError(ValidationIssue("invalid_checksum", "Ungültige WSD/RQD-Prüfsumme"))
        return HandshakeMessage(command, device_id, raw, address=address, size=size)

    if len(raw) < 11:
        raise D50ValidationError(ValidationIssue("invalid_dat", "DAT-Nachricht ist zu kurz"))
    address = validate_address(raw[5:8])
    data = raw[8:-2]
    if not 1 <= len(data) <= MAX_DT1_DATA_BYTES:
        raise D50ValidationError(ValidationIssue("invalid_dat", "DAT-Nutzdaten besitzen eine ungültige Länge"))
    if not checksum_is_valid(address, data, raw[-2]):
        raise D50ValidationError(ValidationIssue("invalid_checksum", "Ungültige DAT-Prüfsumme"))
    return HandshakeMessage(command, device_id, raw, address=address, data=data)
