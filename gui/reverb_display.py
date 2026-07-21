"""Human-readable presentation of D-50 reverb dependency states."""

from __future__ import annotations

from dataclasses import dataclass

from domain.enums import ReverbStatus


@dataclass(frozen=True, slots=True)
class ReverbPresentation:
    label: str
    marker: str
    background: str


PRESENTATIONS = {
    ReverbStatus.FIXED_1_16: ReverbPresentation(
        "Fest im D-50 (Reverb 1–16)",
        "",
        "#ffffff",
    ),
    ReverbStatus.SOURCE_AVAILABLE: ReverbPresentation(
        "Bank-Reverb vorhanden (17–32)",
        " ✓",
        "#e2f0d9",
    ),
    ReverbStatus.SOURCE_MISSING: ReverbPresentation(
        "Original-Reverb fehlt oder ist unbekannt",
        " !",
        "#fff3cd",
    ),
    ReverbStatus.RESOLVED: ReverbPresentation(
        "Bank-Reverb zugeordnet",
        " ✓",
        "#d1e7dd",
    ),
    ReverbStatus.CONFLICT: ReverbPresentation(
        "Reverbkonflikt",
        " !!",
        "#f8d7da",
    ),
}


def present_reverb_status(status: ReverbStatus) -> ReverbPresentation:
    return PRESENTATIONS[status]
