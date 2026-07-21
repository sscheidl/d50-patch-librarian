from d50.checksum import checksum_is_valid, roland_checksum


def test_roland_checksum_known_values() -> None:
    assert roland_checksum((0, 0, 0), bytes(64)) == 0
    assert roland_checksum((0, 3, 0), bytes(64)) == 125
    assert roland_checksum((2, 0, 0), bytes([1, 2, 3])) == 120


def test_checksum_validation() -> None:
    address = (2, 3, 64)
    data = bytes(range(64))
    checksum = roland_checksum(address, data)
    assert checksum_is_valid(address, data, checksum)
    assert not checksum_is_valid(address, data, checksum ^ 1)

