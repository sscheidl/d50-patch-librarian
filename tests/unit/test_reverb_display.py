from domain.enums import ReverbStatus
from gui.reverb_display import present_reverb_status


def test_reverb_status_presentations_are_explicit() -> None:
    fixed = present_reverb_status(ReverbStatus.FIXED_1_16)
    available = present_reverb_status(ReverbStatus.SOURCE_AVAILABLE)
    missing = present_reverb_status(ReverbStatus.SOURCE_MISSING)
    conflict = present_reverb_status(ReverbStatus.CONFLICT)

    assert fixed.marker == ""
    assert "vorhanden" in available.label
    assert available.background == "#e2f0d9"
    assert "fehlt" in missing.label
    assert missing.background == "#fff3cd"
    assert conflict.background == "#f8d7da"
