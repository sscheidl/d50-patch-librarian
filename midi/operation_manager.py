"""Thread-safe ownership for all MIDI operations in the application."""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from threading import Lock


class MidiOperation(Enum):
    IDLE = "idle"
    PREVIEW = "preview"
    BANK_SEND = "bank_send"
    BANK_RECEIVE = "bank_receive"
    PORT_TEST = "port_test"
    PORT_REFRESH = "port_refresh"


OPERATION_LABELS = {
    MidiOperation.IDLE: "Keine MIDI-Operation",
    MidiOperation.PREVIEW: "Patch-Vorschau",
    MidiOperation.BANK_SEND: "Bank-Senden",
    MidiOperation.BANK_RECEIVE: "Bank-Empfang",
    MidiOperation.PORT_TEST: "MIDI-Porttest",
    MidiOperation.PORT_REFRESH: "MIDI-Portaktualisierung",
}


@dataclass(frozen=True, slots=True)
class OperationToken:
    job_id: int
    operation: MidiOperation


class MidiOperationManager:
    """Allow exactly one owner of the application's MIDI resources."""

    def __init__(self) -> None:
        self._lock = Lock()
        self._active: OperationToken | None = None
        self._next_job_id = 1

    def try_begin(self, operation: MidiOperation) -> OperationToken | None:
        if operation is MidiOperation.IDLE:
            raise ValueError("IDLE kann nicht als MIDI-Operation gestartet werden")
        with self._lock:
            if self._active is not None:
                return None
            token = OperationToken(self._next_job_id, operation)
            self._next_job_id += 1
            self._active = token
            return token

    def finish(self, token: OperationToken) -> bool:
        """Release only the exact active token; stale callbacks are ignored."""
        with self._lock:
            if self._active != token:
                return False
            self._active = None
            return True

    @property
    def is_busy(self) -> bool:
        with self._lock:
            return self._active is not None

    @property
    def active_token(self) -> OperationToken | None:
        with self._lock:
            return self._active

    @property
    def active_operation(self) -> MidiOperation:
        token = self.active_token
        return MidiOperation.IDLE if token is None else token.operation

    @property
    def active_label(self) -> str:
        return OPERATION_LABELS[self.active_operation]
