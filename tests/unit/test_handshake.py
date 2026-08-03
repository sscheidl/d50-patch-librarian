from __future__ import annotations

from d50.constants import ACK_COMMAND_ID, DAT_COMMAND_ID, RQD_COMMAND_ID
from d50.handshake import (
    build_dat_frame,
    build_handshake_control,
    build_handshake_request,
    parse_handshake_frame,
)


def test_handshake_request_data_and_control_roundtrip() -> None:
    request = parse_handshake_frame(
        build_handshake_request(RQD_COMMAND_ID, (2, 0, 0), (2, 93, 16), device_id=0)
    )
    assert request.command == RQD_COMMAND_ID
    assert request.device_id == 0
    assert request.address == (2, 0, 0)
    assert request.size == (2, 93, 16)

    data = parse_handshake_frame(build_dat_frame((2, 0, 0), bytes(range(64)), device_id=0))
    assert data.command == DAT_COMMAND_ID
    assert data.data == bytes(range(64))

    acknowledge = parse_handshake_frame(build_handshake_control(ACK_COMMAND_ID, device_id=0))
    assert acknowledge.command == ACK_COMMAND_ID
    assert acknowledge.address is None
    assert acknowledge.raw == bytes((0xF0, 0x41, 0x00, 0x14, 0x43, 0xF7))
