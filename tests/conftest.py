from __future__ import annotations

from pathlib import Path

import pytest

FIXTURES_DIR = Path(__file__).parent / "fixtures"


@pytest.fixture
def generic_saas_dir() -> Path:
    return FIXTURES_DIR / "generic_saas"


@pytest.fixture
def human_portfolio_dir() -> Path:
    return FIXTURES_DIR / "human_portfolio"
