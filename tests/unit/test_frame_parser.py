import pytest

from d50.sysex_frames import build_dt1_frame, parse_dt1_frame, parse_sysex_stream
from domain.errors import D50ValidationError, SysExParseError


def test_strict_stream_allows_realtime_bytes() -> None:
    frame = build_dt1_frame((0, 0, 0), bytes(64))
    interleaved = frame[:12] + b"\xF8\xFE" + frame[12:] + b"\xFF"
    stream = parse_sysex_stream(interleaved, strict=True)
    assert stream.realtime_byte_count == 3
    assert stream.frames[0].raw == frame


def test_strict_stream_rejects_outside_bytes_and_truncation() -> None:
    frame = build_dt1_frame((0, 0, 0), bytes(64))
    with pytest.raises(SysExParseError, match="Fremdbytes"):
        parse_sysex_stream(b"noise" + frame, strict=True)
    with pytest.raises(SysExParseError, match="endet ohne F7"):
        parse_sysex_stream(frame[:-1], strict=True)


def test_dt1_rejects_checksum_and_device_id() -> None:
    frame = bytearray(build_dt1_frame((0, 0, 0), bytes(64)))
    frame[-2] ^= 1
    with pytest.raises(D50ValidationError, match="Prüfsumme"):
        parse_dt1_frame(bytes(frame))

    frame = bytearray(build_dt1_frame((0, 0, 0), bytes(64)))
    frame[2] = 0x20
    with pytest.raises(D50ValidationError, match="Device ID"):
        parse_dt1_frame(bytes(frame))


def test_dt1_rejects_payload_larger_than_256_bytes() -> None:
    # Build manually because the serializer correctly refuses this input.
    data = bytes([0] * 257)
    raw = bytes([0xF0, 0x41, 0x10, 0x14, 0x12, 0, 0, 0, *data, 0, 0xF7])
    with pytest.raises(D50ValidationError, match="überschreiten 256"):
        parse_dt1_frame(raw)

