from d50.addresses import add_to_address, address_to_linear, linear_to_address, reverb_base, slot_base
from d50.constants import FULL_BANK_PAYLOAD_SIZE


def test_address_roundtrip_across_7bit_boundaries() -> None:
    for address in ((0, 0, 0), (0, 0, 127), (0, 1, 0), (3, 95, 127), (4, 14, 127)):
        assert linear_to_address(address_to_linear(address)) == address
    assert add_to_address((0, 0, 127), 1) == (0, 1, 0)
    assert add_to_address((0, 127, 127), 1) == (1, 0, 0)


def test_golden_patch_addresses() -> None:
    assert slot_base(0) == (0x02, 0x00, 0x00)
    assert slot_base(1) == (0x02, 0x03, 0x40)
    assert slot_base(63) == (0x03, 0x5C, 0x40)
    assert add_to_address(slot_base(63), 447) == (0x03, 0x5F, 0x7F)


def test_golden_reverb_addresses() -> None:
    assert reverb_base(17) == (0x03, 0x60, 0x00)
    assert reverb_base(18) == (0x03, 0x62, 0x78)
    assert reverb_base(32) == (0x04, 0x0C, 0x08)
    assert add_to_address(reverb_base(32), 375) == (0x04, 0x0E, 0x7F)
    assert FULL_BANK_PAYLOAD_SIZE == 34_688

