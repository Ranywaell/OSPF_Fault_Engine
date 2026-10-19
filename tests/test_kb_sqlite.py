"""Tests for the optional SQLite knowledge-base mirror."""

from __future__ import annotations

from pathlib import Path

import pytest

from ospf_engine.reasoning.kb_sqlite import load_from_db, snapshot_to_db
from ospf_engine.reasoning.knowledge_base import FAULT_CATALOG


def test_snapshot_round_trip(tmp_path: Path) -> None:
    db = tmp_path / "faults.db"
    snapshot_to_db(db)
    loaded = load_from_db(db)

    assert set(loaded) == set(FAULT_CATALOG)
    for name, fault in FAULT_CATALOG.items():
        round_tripped = loaded[name]
        assert round_tripped.name == fault.name
        assert round_tripped.category == fault.category
        assert round_tripped.cause == fault.cause
        assert round_tripped.verify == fault.verify
        assert round_tripped.fix == fault.fix
        assert round_tripped.fix_dependencies == fault.fix_dependencies


def test_snapshot_is_idempotent(tmp_path: Path) -> None:
    db = tmp_path / "faults.db"
    snapshot_to_db(db)
    first = load_from_db(db)
    snapshot_to_db(db)
    second = load_from_db(db)
    assert first == second


def test_load_missing_db_raises(tmp_path: Path) -> None:
    with pytest.raises(FileNotFoundError):
        load_from_db(tmp_path / "does_not_exist.db")
