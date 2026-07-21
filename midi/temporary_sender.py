"""Safe MIDI sender limited to the D-50 temporary patch area."""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
import time
from typing import Protocol

from d50.constants import MAX_DEVICE_ID, MIN_DEVICE_ID, PATCH_SIZE, TEMP_PATCH_BLOCK_ADDRESSES
from d50.single_patch_codec import serialize_single_patch
from d50.sysex_frames import parse_dt1_frame, parse_sysex_stream
from domain.patch import D50Patch


MIN_MESSAGE_DELAY_MS = 20
DEFAULT_MESSAGE_DELAY_MS = 50


class MidiTransferError(RuntimeError):
    """Actionable MIDI port or transfer failure."""


class SysexOutputPort(Protocol):
    def send_sysex(self, frame: bytes) -> None: ...

    def close(self) -> None: ...


class SysexInputPort(Protocol):
    def poll_sysex(self) -> bytes | None: ...

    def close(self) -> None: ...


class MidiBackend(Protocol):
    def output_names(self) -> tuple[str, ...]: ...

    def input_names(self) -> tuple[str, ...]: ...

    def open_output(self, name: str) -> SysexOutputPort: ...

    def open_input(self, name: str) -> SysexInputPort: ...


class _MidoOutputPort:
    def __init__(self, port, mido_module) -> None:
        self._port = port
        self._mido = mido_module

    def send_sysex(self, frame: bytes) -> None:
        self._port.send(self._mido.Message.from_bytes(list(frame)))

    def close(self) -> None:
        self._port.close()


class _MidoInputPort:
    def __init__(self, port) -> None:
        self._port = port

    def poll_sysex(self) -> bytes | None:
        while True:
            message = self._port.poll()
            if message is None:
                return None
            if message.type == "sysex":
                return bytes(message.bytes())

    def close(self) -> None:
        self._port.close()


class MidoBackend:
    def __init__(self) -> None:
        try:
            import mido
        except ImportError as exc:
            raise MidiTransferError(
                "MIDI-Unterstützung fehlt. Installiere mido und python-rtmidi."
            ) from exc
        self._mido = mido

    def output_names(self) -> tuple[str, ...]:
        try:
            return tuple(self._mido.get_output_names())
        except Exception as exc:
            raise MidiTransferError(f"MIDI-Ausgänge konnten nicht gelesen werden: {exc}") from exc

    def input_names(self) -> tuple[str, ...]:
        try:
            return tuple(self._mido.get_input_names())
        except Exception as exc:
            raise MidiTransferError(f"MIDI-Eingänge konnten nicht gelesen werden: {exc}") from exc

    def open_output(self, name: str) -> SysexOutputPort:
        try:
            return _MidoOutputPort(self._mido.open_output(name), self._mido)
        except Exception as exc:
            raise MidiTransferError(f"MIDI-Ausgang '{name}' konnte nicht geöffnet werden: {exc}") from exc

    def open_input(self, name: str) -> SysexInputPort:
        try:
            return _MidoInputPort(self._mido.open_input(name))
        except Exception as exc:
            raise MidiTransferError(f"MIDI-Eingang '{name}' konnte nicht geöffnet werden: {exc}") from exc


@dataclass(frozen=True, slots=True)
class TemporaryPatchTransferPlan:
    patch_name: str
    device_id: int
    frames: tuple[bytes, ...]
    addresses: tuple[tuple[int, int, int], ...]
    data_byte_count: int

    @property
    def message_count(self) -> int:
        return len(self.frames)


@dataclass(frozen=True, slots=True)
class TemporaryPatchTransferReport:
    port_name: str
    patch_name: str
    device_id: int
    message_count: int
    data_byte_count: int
    elapsed_ms: int


def build_temporary_patch_plan(
    patch: D50Patch,
    *,
    device_id: int,
) -> TemporaryPatchTransferPlan:
    if not MIN_DEVICE_ID <= device_id <= MAX_DEVICE_ID:
        raise ValueError("Device ID muss zwischen 00h und 1Fh liegen")
    stream = parse_sysex_stream(serialize_single_patch(patch, device_id=device_id), strict=True)
    messages = tuple(
        parse_dt1_frame(frame, index=index)
        for index, frame in enumerate(stream.frames, start=1)
    )
    addresses = tuple(message.address for message in messages)
    if addresses != TEMP_PATCH_BLOCK_ADDRESSES:
        raise AssertionError("Temporary-Buffer-Plan enthält unerwartete Zieladressen")
    data_byte_count = sum(len(message.data) for message in messages)
    if data_byte_count != PATCH_SIZE:
        raise AssertionError("Temporary-Buffer-Plan enthält keine vollständigen Patchdaten")
    return TemporaryPatchTransferPlan(
        patch_name=patch.name,
        device_id=device_id,
        frames=tuple(message.raw for message in messages),
        addresses=addresses,
        data_byte_count=data_byte_count,
    )


def list_midi_output_ports(*, backend: MidiBackend | None = None) -> tuple[str, ...]:
    return (backend or MidoBackend()).output_names()


def list_midi_input_ports(*, backend: MidiBackend | None = None) -> tuple[str, ...]:
    return (backend or MidoBackend()).input_names()


def test_midi_output_port(name: str, *, backend: MidiBackend | None = None) -> None:
    if not name:
        raise MidiTransferError("Kein MIDI-Ausgang ausgewählt")
    port = (backend or MidoBackend()).open_output(name)
    port.close()


def test_midi_input_port(name: str, *, backend: MidiBackend | None = None) -> None:
    if not name:
        raise MidiTransferError("Kein MIDI-Eingang ausgewählt")
    port = (backend or MidoBackend()).open_input(name)
    port.close()


def send_temporary_patch(
    patch: D50Patch,
    *,
    port_name: str,
    device_id: int,
    delay_ms: int = DEFAULT_MESSAGE_DELAY_MS,
    backend: MidiBackend | None = None,
    sleeper: Callable[[float], None] = time.sleep,
    progress: Callable[[int, int], None] | None = None,
) -> TemporaryPatchTransferReport:
    if not port_name:
        raise MidiTransferError("Kein MIDI-Ausgang ausgewählt")
    if delay_ms < MIN_MESSAGE_DELAY_MS:
        raise ValueError(f"Zwischen DT1-Nachrichten sind mindestens {MIN_MESSAGE_DELAY_MS} ms erforderlich")
    plan = build_temporary_patch_plan(patch, device_id=device_id)
    selected_backend = backend or MidoBackend()
    port = selected_backend.open_output(port_name)
    started = time.perf_counter()
    try:
        for index, frame in enumerate(plan.frames, start=1):
            port.send_sysex(frame)
            if progress is not None:
                progress(index, plan.message_count)
            if index < plan.message_count:
                sleeper(delay_ms / 1000)
    except Exception as exc:
        if isinstance(exc, MidiTransferError):
            raise
        raise MidiTransferError(f"MIDI-Sendung wurde abgebrochen: {exc}") from exc
    finally:
        # WinMM can still have the final SysEx message queued when send()
        # returns. Keep the port alive briefly so the patch block is not lost.
        sleeper(0.15)
        port.close()
    elapsed_ms = round((time.perf_counter() - started) * 1000)
    return TemporaryPatchTransferReport(
        port_name=port_name,
        patch_name=patch.name,
        device_id=device_id,
        message_count=plan.message_count,
        data_byte_count=plan.data_byte_count,
        elapsed_ms=elapsed_ms,
    )
