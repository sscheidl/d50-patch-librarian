"""Typed errors carrying actionable validation context."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class ValidationIssue:
    code: str
    message: str
    message_index: int | None = None
    byte_offset: int | None = None

    def __str__(self) -> str:
        context: list[str] = []
        if self.message_index is not None:
            context.append(f"Nachricht {self.message_index}")
        if self.byte_offset is not None:
            context.append(f"Byte {self.byte_offset}")
        prefix = f" ({', '.join(context)})" if context else ""
        return f"{self.message}{prefix}"


class D50Error(ValueError):
    """Base class for data errors that may be shown to users."""


class D50ValidationError(D50Error):
    def __init__(self, issue: ValidationIssue | str, *, code: str = "invalid") -> None:
        if isinstance(issue, str):
            issue = ValidationIssue(code=code, message=issue)
        self.issue = issue
        super().__init__(str(issue))


class SysExParseError(D50ValidationError):
    """Raised when a byte stream is not a clean sequence of SysEx frames."""


class UnsupportedDumpError(D50ValidationError):
    """Raised when valid data is not a supported complete bank or patch."""

