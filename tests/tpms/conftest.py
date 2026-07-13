from __future__ import annotations

import pytest

from src.tpms.config import Config


@pytest.fixture
def config(tmp_path) -> Config:
    return Config(
        db_path=tmp_path / "tpms.sqlite3",
        stale_seconds=900,
        low_psi=30.0,
    )
