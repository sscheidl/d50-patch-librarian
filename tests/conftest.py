from __future__ import annotations

from pathlib import Path

import pytest


@pytest.fixture(scope="session")
def fixture_dir() -> Path:
    return Path(__file__).parent / "fixtures"


@pytest.fixture(scope="session")
def valid_bank_bytes(fixture_dir: Path) -> bytes:
    return (fixture_dir / "valid_full_bank.syx").read_bytes()


@pytest.fixture(scope="session")
def valid_single_bytes(fixture_dir: Path) -> bytes:
    return (fixture_dir / "valid_generated_single.syx").read_bytes()

