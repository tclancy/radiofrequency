"""Env-driven config for the TPMS ingest + API services.

Both services read the same config so a shared DB path and vehicle set stay in sync
without hand-wiring flags. `TPMS_DB` is the only required env var — everything else
falls back to sensible defaults for a plexpi single-vehicle install.
"""

from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path

DEFAULT_DB_PATH = Path("/var/lib/tpms/tpms.sqlite3")
DEFAULT_STALE_SECONDS = 15 * 60
DEFAULT_LOW_PSI = 30.0


@dataclass(frozen=True)
class Config:
    db_path: Path
    stale_seconds: int
    low_psi: float

    @classmethod
    def from_env(cls, env: dict[str, str] | None = None) -> "Config":
        e = env if env is not None else os.environ
        return cls(
            db_path=Path(e.get("TPMS_DB", str(DEFAULT_DB_PATH))),
            stale_seconds=int(e.get("TPMS_STALE_SECONDS", str(DEFAULT_STALE_SECONDS))),
            low_psi=float(e.get("TPMS_LOW_PSI", str(DEFAULT_LOW_PSI))),
        )
