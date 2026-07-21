"""Address-based D-50 validation and conflict-safe memory reconstruction."""

from __future__ import annotations

from dataclasses import dataclass

from domain.errors import D50ValidationError, ValidationIssue

from .addresses import Address, address_to_linear, format_address, linear_to_address
from .constants import (
    ADDRESS_SPACE_SIZE,
    FULL_BANK_END,
    FULL_BANK_START,
    TEMP_PATCH_END,
    TEMP_PATCH_START,
)
from .sysex_frames import DT1Message, SysExFrame, parse_dt1_frame, parse_sysex_stream


@dataclass(frozen=True, slots=True)
class ReconstructedMemory:
    cells: dict[int, int]
    messages: tuple[DT1Message, ...]
    device_id: int

    @property
    def data_byte_count(self) -> int:
        return len(self.cells)

    @property
    def addresses(self) -> frozenset[int]:
        return frozenset(self.cells)

    def read(self, start: Address | int, length: int) -> bytes:
        start_linear = address_to_linear(start) if isinstance(start, tuple) else start
        missing = next((address for address in range(start_linear, start_linear + length) if address not in self.cells), None)
        if missing is not None:
            raise D50ValidationError(
                ValidationIssue(
                    "missing_data",
                    f"Adressierter Speicher ist unvollständig; Daten an Adresse {format_address(linear_to_address(missing))} fehlen",
                )
            )
        return bytes(self.cells[address] for address in range(start_linear, start_linear + length))


def reconstruct_messages(frames: tuple[SysExFrame, ...]) -> ReconstructedMemory:
    if not frames:
        raise D50ValidationError(ValidationIssue("not_sysex", "Keine SysEx-Datei"))
    messages: list[DT1Message] = []
    cells: dict[int, int] = {}
    source_message: dict[int, int] = {}
    device_id: int | None = None

    for index, frame in enumerate(frames, start=1):
        message = parse_dt1_frame(frame, index=index)
        if device_id is None:
            device_id = message.device_id
        elif device_id != message.device_id:
            raise D50ValidationError(
                ValidationIssue(
                    "mixed_device_ids",
                    f"Datei mischt Device IDs 0x{device_id:02X} und 0x{message.device_id:02X}",
                    message_index=index,
                )
            )
        start = address_to_linear(message.address)
        if start + len(message.data) > ADDRESS_SPACE_SIZE:
            raise D50ValidationError(
                ValidationIssue("address_overflow", "DT1-Daten überschreiten den D-50-Adressraum", message_index=index)
            )
        end = start + len(message.data) - 1
        temp_start = address_to_linear(TEMP_PATCH_START)
        temp_end = address_to_linear(TEMP_PATCH_END)
        bank_start = address_to_linear(FULL_BANK_START)
        bank_end = address_to_linear(FULL_BANK_END)
        within_temporary = temp_start <= start <= end <= temp_end
        within_bank = bank_start <= start <= end <= bank_end
        if not (within_temporary or within_bank):
            raise D50ValidationError(
                ValidationIssue(
                    "invalid_d50_address",
                    "DT1-Nachricht liegt außerhalb der unterstützten D-50 Temporary-/Work-Areas "
                    f"({format_address(message.address)})",
                    message_index=index,
                )
            )
        for relative, value in enumerate(message.data):
            address = start + relative
            previous = cells.get(address)
            if previous is not None and previous != value:
                formatted = format_address(linear_to_address(address))
                raise D50ValidationError(
                    ValidationIssue(
                        "conflicting_overlap",
                        f"Bank enthält widersprüchliche Daten an Adresse {formatted}; zuerst Nachricht {source_message[address]}",
                        message_index=index,
                    )
                )
            cells[address] = value
            source_message.setdefault(address, index)
        messages.append(message)

    assert device_id is not None
    return ReconstructedMemory(cells, tuple(messages), device_id)


def validate_and_reconstruct(data: bytes) -> ReconstructedMemory:
    stream = parse_sysex_stream(data, strict=True)
    return reconstruct_messages(stream.frames)
